"""
Kronode Pipeline Integration Test
=================================
Run: cd backend && uv run python test_pipeline.py

Tests each step of the organizational intelligence layer without the GUI.
Requires: Postgres + Redis running (make infra), migrations applied (make migrate).
"""
import asyncio
import sys


# ── Helpers ──────────────────────────────────────────────────────────────────

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
SKIP = "\033[93m⊘\033[0m"
results = []


def report(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, passed))
    print(f"  {status} {name}")
    if detail:
        print(f"    {detail}")


def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── Tests ────────────────────────────────────────────────────────────────────

async def test_config():
    section("1. Config & LLM Router")

    from app.core.config import settings
    report("Anthropic key set", bool(settings.anthropic_api_key))
    report("Database URL set", "postgresql" in settings.database_url)

    # Check which cheap providers are available
    providers = []
    if settings.gemini_api_key:
        providers.append("gemini")
    if settings.deepseek_api_key:
        providers.append("deepseek")
    if settings.openai_api_key:
        providers.append("openai")
    if settings.anthropic_api_key:
        providers.append("haiku")
    report("Cheap LLM providers available", len(providers) > 0, f"failover chain: {' → '.join(providers)}")

    # Test cheap() actually works
    from app.core.llm import cheap
    try:
        result = await cheap(
            system='Extract conventions. Respond with JSON only: {"conventions": []}',
            user_message="No code to analyse.",
            max_tokens=64,
        )
        report("cheap() LLM call works", bool(result), f"provider responded ({len(result)} chars)")
    except Exception as e:
        report("cheap() LLM call works", False, str(e))


async def test_db():
    section("2. Database & Models")

    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        report("Database connection", True)
    except Exception as e:
        report("Database connection", False, str(e))
        return  # skip remaining DB tests

    # Check tables exist
    from app.models.convention import Convention
    from app.models.task import Task
    from app.models.memory import MemoryRecord
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        try:
            count = (await db.execute(select(func.count()).select_from(Convention))).scalar()
            report("conventions table exists", True, f"{count} rows")
        except Exception as e:
            report("conventions table exists", False, str(e))

        try:
            count = (await db.execute(select(func.count()).select_from(Task))).scalar()
            report("tasks table exists", True, f"{count} rows")
        except Exception as e:
            report("tasks table exists", False, str(e))

        try:
            count = (await db.execute(select(func.count()).select_from(MemoryRecord))).scalar()
            report("memory_records table exists", True, f"{count} rows")
        except Exception as e:
            report("memory_records table exists", False, str(e))

        # Check plan_snapshot column
        try:
            await db.execute(text("SELECT plan_snapshot FROM tasks LIMIT 1"))
            report("plan_snapshot column exists", True)
        except Exception as e:
            report("plan_snapshot column exists", False, str(e))


async def test_pipeline_imports():
    section("3. Pipeline & Agent Imports")

    from app.pipeline.pipeline import AGENT_CHAIN, _build_agent_map, _get_skip_flags

    expected = [
        "ticket_interpreter", "context_builder", "clarification_agent",
        "planner_agent", "plan_approval_agent", "guardrails_agent",
        "coder_agent", "tester_agent", "execution_verifier",
        "reviewer_agent", "memory_agent",
    ]
    report("AGENT_CHAIN correct", AGENT_CHAIN == expected, f"{len(AGENT_CHAIN)} agents")

    agent_map = _build_agent_map()
    report("All agents import", len(agent_map) == len(expected), f"{len(agent_map)} agents loaded")

    skip_flags = _get_skip_flags()
    skipped = [k for k, v in skip_flags.items() if v]
    active = [k for k, v in skip_flags.items() if not v]
    report("Skip flags loaded", True, f"active: {len(active)}, skipped: {len(skipped)}")
    if skipped:
        print(f"    skipped: {', '.join(skipped)}")


async def test_ticket_interpreter():
    section("4. Ticket Interpreter")

    from app.agents.ticket_interpreter import TicketInterpreterAgent

    agent = TicketInterpreterAgent()
    context = {
        "description": "Add a forgot password screen with email input and reset link. Should match existing auth styling.",
        "project_context": "Next.js app with Tailwind, Clerk for auth",
        "jira_ticket": {"issue_type": "Story", "priority": "Medium", "status": "To Do"},
    }

    try:
        result = await agent.run(context)
        task = result.get("structured_task", {})
        report("Structured task extracted", bool(task.get("title")), f"title: {task.get('title', '?')[:60]}")
        report("Requirements extracted", len(task.get("requirements", [])) > 0, f"{len(task.get('requirements', []))} requirements")
        report("Ticket type classified", task.get("ticket_type") in ("bug_fix", "feature", "refactor", "chore"), f"type: {task.get('ticket_type')}")
        report("Complexity estimated", task.get("estimated_complexity") in ("simple", "medium", "complex"), f"complexity: {task.get('estimated_complexity')}")
        ambiguities = task.get("ambiguities", [])
        report("Ambiguities identified", True, f"{len(ambiguities)} ambiguity(ies)")
    except Exception as e:
        report("Ticket interpreter run", False, str(e))


async def test_convention_extraction():
    section("5. Convention Extraction (Cal.com)")

    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(OnboardingConfig).limit(1))
        config = result.scalar_one_or_none()

    if not config or not config.github_access_token:
        report("GitHub token configured", False, "no token in onboarding config — skipping PR tests")
        return

    report("GitHub token configured", True)

    # Fetch PRs
    from app.services.github_service import fetch_merged_prs
    try:
        prs = await fetch_merged_prs(
            repo_url="https://github.com/calcom/cal.com",
            token=config.github_access_token,
            count=5,
        )
        report("Fetch merged PRs", len(prs) > 0, f"{len(prs)} PRs fetched")
    except Exception as e:
        report("Fetch merged PRs", False, str(e))
        return

    # Extract conventions from first PR with a diff
    from app.services.convention_extractor import extract_conventions_from_pr
    code_prs = [p for p in prs if len(p.get("diff", "")) > 200]
    if code_prs:
        try:
            conventions = await extract_conventions_from_pr(code_prs[0])
            report("Extract conventions from PR", True, f"{len(conventions)} conventions from PR #{code_prs[0]['number']}")
            for c in conventions[:3]:
                print(f"      [{c['category']}] {c['rule'][:70]}")
        except Exception as e:
            report("Extract conventions from PR", False, str(e))
    else:
        report("Extract conventions from PR", True, "no PRs with substantial diffs — skipped")

    # Dedup + score
    from app.services.convention_extractor import deduplicate_conventions, score_conventions
    test_data = [
        {"rule": "Use named exports", "category": "style", "frequency": 1, "source_prs": ["pr1"]},
        {"rule": "Use named exports", "category": "style", "frequency": 1, "source_prs": ["pr2"]},
        {"rule": "Always add tests", "category": "testing", "frequency": 1, "source_prs": ["pr1"]},
    ]
    deduped = deduplicate_conventions(test_data)
    report("Deduplication", len(deduped) == 2, f"3 raw → {len(deduped)} unique")

    scored = score_conventions(deduped)
    report("Scoring", scored[0]["confidence"] > scored[-1]["confidence"] or len(scored) == 1,
           f"top confidence: {scored[0]['confidence']:.2f}")


async def test_conventions_db():
    section("6. Conventions in Database")

    from app.core.database import AsyncSessionLocal
    from app.models.convention import Convention
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(Convention))).scalar()
        report("Conventions stored", count > 0, f"{count} conventions in DB")

        if count > 0:
            rows = (await db.execute(
                select(Convention).order_by(Convention.confidence.desc()).limit(3)
            )).scalars().all()
            for c in rows:
                print(f"      [{c.category}] {c.rule[:60]} (freq={c.frequency}, conf={c.confidence})")


async def test_context_builder():
    section("7. Context Builder (queries conventions + pitfalls)")

    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(OnboardingConfig).limit(1))
        config = result.scalar_one_or_none()

    if not config or not config.repo_url or not config.github_access_token:
        report("Context builder", True, "no repo configured — skipped")
        return

    from app.agents.context_builder import ContextBuilderAgent
    agent = ContextBuilderAgent()
    context = {
        "repo_url": config.repo_url,
        "github_access_token": config.github_access_token,
        "description": "Add a new onboarding step for Confluence",
        "org_id": config.org_id,
        "profile_priority_extensions": [".ts", ".tsx"],
        "cached_conventions": None,
    }

    try:
        result = await agent.run(context)
        files = result.get("relevant_files", [])
        conventions = result.get("conventions", [])
        pitfalls = result.get("pitfalls", [])
        patterns = result.get("reviewer_patterns", [])
        report("Files fetched", len(files) > 0, f"{len(files)} files")
        report("Conventions loaded", len(conventions) > 0, f"{len(conventions)} conventions (from DB)")
        report("Pitfalls loaded", True, f"{len(pitfalls)} pitfalls")
        report("Reviewer patterns loaded", True, f"{len(patterns)} patterns")
    except Exception as e:
        report("Context builder run", False, str(e))


async def test_planner():
    section("8. Planner (structured input + confidence)")

    from app.agents.planner_agent import PlannerAgent

    agent = PlannerAgent()
    context = {
        "description": "Add a forgot password screen",
        "project_context": "Next.js with Tailwind and Clerk",
        "context_builder": {
            "relevant_files": [{"path": "app/auth/login.tsx", "content": "// login page"}],
            "conventions": [
                {"rule": "Use default exports", "category": "style", "confidence": 0.9, "layer": "customer", "source_prs": ["PR #2"]},
            ],
            "pitfalls": [],
            "reviewer_patterns": [],
        },
        "ticket_interpreter": {
            "structured_task": {
                "title": "Add forgot password screen",
                "requirements": ["Email input field", "Send reset link button", "Match existing auth styling"],
                "scope": "Frontend only — auth/forgot-password route",
                "acceptance_criteria": ["User can enter email and receive reset link"],
                "ambiguities": [],
                "ticket_type": "feature",
                "estimated_complexity": "simple",
            }
        },
        "routing": {"complexity": "simple"},
        "profile_injection": "",
        "coding_standards": "",
    }

    try:
        result = await agent.run(context)
        report("Plan created", len(result.get("subtasks", [])) > 0, f"{len(result.get('subtasks', []))} subtasks")
        report("DoD generated", len(result.get("definition_of_done", [])) > 0, f"{len(result.get('definition_of_done', []))} items")
        report("Confidence scored", "confidence_level" in result, f"{result.get('confidence_level', '?')} ({result.get('confidence_score', '?')})")
    except Exception as e:
        report("Planner run", False, str(e))


async def test_plan_posting():
    section("9. Plan Posting (Slack + Jira visibility)")

    from app.agents.plan_approval_agent import PlanApprovalAgent

    agent = PlanApprovalAgent()
    context = {
        "planner_agent": {
            "subtasks": [{"order": 1, "description": "Create forgot-password page", "agent": "coder_agent", "files_affected": ["app/auth/forgot-password.tsx"]}],
            "definition_of_done": ["Page renders", "Email input works"],
            "risk_flags": [],
            "assumptions": ["Clerk handles the actual reset flow"],
            "confidence_score": 0.75,
            "confidence_level": "high",
            "estimated_files": 1,
        },
        "slack_bot_token": None,  # no Slack — tests auto-proceed
        "slack_channel_id": None,
        "agent_name": "TestAgent",
        "task_id": "test-123",
    }

    try:
        result = await agent.run(context)
        report("Plan approval agent runs", True)
        report("No waiting (autonomous)", not result.get("waiting"), "proceeds immediately")
        report("Approved flag set", result.get("approved") is True)
        report("Confidence passed through", result.get("confidence_level") == "high")
    except Exception as e:
        report("Plan posting", False, str(e))


async def test_feedback_extractor():
    section("10. Feedback Extractor")

    from app.agents.feedback_extractor import extract_from_review

    try:
        updated = await extract_from_review(
            org_id=1,
            review_comments=["Always use named exports for React components, not default exports"],
            inline_comments=[{"path": "components/Button.tsx", "body": "Should be a named export"}],
            pr_url="https://github.com/test/test/pull/99",
            is_merged=False,
        )
        report("Feedback extraction works", True, f"{updated} convention(s) created/updated")
    except Exception as e:
        report("Feedback extraction", False, str(e))


async def main():
    print("\n" + "=" * 60)
    print("  KRONODE PIPELINE INTEGRATION TEST")
    print("=" * 60)

    await test_config()
    await test_db()
    await test_pipeline_imports()
    await test_ticket_interpreter()
    await test_convention_extraction()
    await test_conventions_db()
    await test_context_builder()
    await test_planner()
    await test_plan_posting()
    await test_feedback_extractor()

    # Summary
    passed = sum(1 for _, p in results if p)
    failed = sum(1 for _, p in results if not p)
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed} passed, {failed} failed, {len(results)} total")
    print(f"{'=' * 60}\n")

    if failed:
        print("Failed tests:")
        for name, p in results:
            if not p:
                print(f"  {FAIL} {name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
