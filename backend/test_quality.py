"""
Kronode Stage Quality Inspector
================================
Run: cd backend && uv run python test_quality.py

Runs each pre-coding stage on a REAL ticket and shows the full output
so you can judge the quality of each step.

Usage:
  uv run python test_quality.py                          # default test ticket
  uv run python test_quality.py "Add dark mode toggle"   # custom description
"""
import asyncio
import json
import sys
import textwrap


def header(title):
    print(f"\n{'━' * 70}")
    print(f"  {title}")
    print(f"{'━' * 70}\n")


def show(label, value, indent=4):
    prefix = " " * indent
    if isinstance(value, list):
        print(f"{prefix}{label}:")
        for i, v in enumerate(value, 1):
            if isinstance(v, dict):
                print(f"{prefix}  {i}. {json.dumps(v, indent=6)[:200]}")
            else:
                print(f"{prefix}  {i}. {v}")
    elif isinstance(value, dict):
        print(f"{prefix}{label}:")
        for k, v in value.items():
            print(f"{prefix}  {k}: {v}")
    else:
        wrapped = textwrap.fill(str(value), width=66, initial_indent=f"{prefix}", subsequent_indent=f"{prefix}  ")
        print(f"{prefix}{label}:")
        print(wrapped)


async def main():
    description = sys.argv[1] if len(sys.argv) > 1 else (
        "Add a forgot password screen. Users should be able to enter their email "
        "and receive a password reset link. The screen should match the existing "
        "auth pages styling. Add proper error handling for invalid emails."
    )

    print("\n" + "=" * 70)
    print("  KRONODE STAGE QUALITY INSPECTOR")
    print("=" * 70)
    print(f"\n  Input: {description[:80]}...")

    # ── Stage 1: Ticket Interpreter ──────────────────────────────────────
    header("STAGE 1: Ticket Interpreter")
    print("  What it does: Parse raw ticket → structured task definition")
    print("  Model: cheap (Gemini → DeepSeek → GPT-4.1 nano → Haiku)\n")

    from app.agents.ticket_interpreter import TicketInterpreterAgent
    agent = TicketInterpreterAgent()
    result = await agent.run({
        "description": description,
        "project_context": "Next.js 14 App Router, TypeScript, Tailwind, Clerk for auth, FastAPI backend",
        "jira_ticket": {"issue_type": "Story", "priority": "Medium", "status": "To Do"},
    })

    task = result.get("structured_task", {})
    show("Title", task.get("title", "?"))
    show("Type", task.get("ticket_type", "?"))
    show("Complexity", task.get("estimated_complexity", "?"))
    show("Scope", task.get("scope", "?"))
    show("Requirements", task.get("requirements", []))
    show("Acceptance Criteria", task.get("acceptance_criteria", []))
    show("Ambiguities", task.get("ambiguities", []) or ["None found"])

    print("\n  ⟶ Quality check:")
    print("    - Are requirements specific and actionable?")
    print("    - Is the complexity estimate reasonable?")
    print("    - Are the ambiguities real (not obvious from context)?")

    # ── Stage 2: Context Builder ─────────────────────────────────────────
    header("STAGE 2: Context Builder")
    print("  What it does: Fetch repo files + conventions + pitfalls + reviewer patterns")
    print("  Model: none (GitHub API + DB queries)\n")

    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        cfg = (await db.execute(select(OnboardingConfig).limit(1))).scalar_one_or_none()

    if cfg and cfg.repo_url and cfg.github_access_token:
        from app.agents.context_builder import ContextBuilderAgent
        cb = ContextBuilderAgent()
        context = {
            "repo_url": cfg.repo_url,
            "github_access_token": cfg.github_access_token,
            "description": description,
            "org_id": cfg.org_id,
            "profile_priority_extensions": [".ts", ".tsx", ".py"],
            "cached_conventions": None,
        }
        cb_result = await cb.run(context)

        files = cb_result.get("relevant_files", [])
        conventions = cb_result.get("conventions", [])
        pitfalls = cb_result.get("pitfalls", [])
        patterns = cb_result.get("reviewer_patterns", [])

        print(f"  Files selected: {len(files)}")
        for f in files[:5]:
            print(f"    • {f['path']} ({len(f.get('content', ''))} chars)")
        if len(files) > 5:
            print(f"    ... and {len(files) - 5} more")

        print(f"\n  Conventions from DB: {len(conventions)}")
        for c in conventions[:5]:
            if isinstance(c, dict):
                print(f"    • [{c.get('category', '?')}] {c.get('rule', '?')[:60]}")
            else:
                print(f"    • {c[:60]}")

        print(f"\n  Pitfalls: {len(pitfalls)}")
        for p in pitfalls[:3]:
            print(f"    • {p.get('description', '?')[:60]}")

        print(f"\n  Reviewer patterns: {len(patterns)}")
        for p in patterns[:3]:
            print(f"    • {p.get('preference', '?')[:60]}")
    else:
        cb_result = {"relevant_files": [], "conventions": [], "pitfalls": [], "reviewer_patterns": []}
        print("  ⊘ No repo configured — skipping file fetch")

    print("\n  ⟶ Quality check:")
    print("    - Are the selected files relevant to the task?")
    print("    - Are conventions being loaded from DB (not re-extracted)?")

    # ── Stage 3: Clarification ───────────────────────────────────────────
    header("STAGE 3: Clarification Check")
    print("  What it does: Decide if task needs clarification before coding")
    print("  Model: uses ticket interpreter ambiguities (no LLM call if present)\n")

    ambiguities = task.get("ambiguities", [])
    if ambiguities:
        print(f"  Interpreter found {len(ambiguities)} ambiguity(ies):")
        for a in ambiguities:
            print(f"    ❓ {a}")
        print("\n  → Would post these to Slack and pause pipeline")
    else:
        print("  ✓ No ambiguities — clarification skipped, pipeline continues")

    print("\n  ⟶ Quality check:")
    print("    - Would you actually need these answered before coding?")
    print("    - Are any of these obvious from context (shouldn't be asked)?")

    # ── Stage 4: Planner ─────────────────────────────────────────────────
    header("STAGE 4: Planner")
    print("  What it does: Create subtasks + DoD + confidence score")
    print("  Model: Anthropic Sonnet (quality call)\n")

    from app.agents.planner_agent import PlannerAgent
    planner = PlannerAgent()
    plan_context = {
        "description": description,
        "project_context": "Next.js 14 App Router, TypeScript, Tailwind, Clerk for auth",
        "context_builder": cb_result,
        "ticket_interpreter": result,
        "routing": {"complexity": task.get("estimated_complexity", "medium")},
        "profile_injection": "",
        "coding_standards": "",
    }
    plan = await planner.run(plan_context)

    print("  Subtasks:")
    for s in plan.get("subtasks", []):
        files = ", ".join(s.get("files_affected", [])) or "none"
        print(f"    {s.get('order', '?')}. {s.get('description', '?')[:65]}")
        print(f"       files: {files}")

    print(f"\n  Definition of Done:")
    for d in plan.get("definition_of_done", []):
        print(f"    ☐ {d}")

    print(f"\n  Risk Flags:")
    for r in plan.get("risk_flags", []):
        print(f"    ⚠ {r}")
    if not plan.get("risk_flags"):
        print("    None")

    print(f"\n  Assumptions:")
    for a in plan.get("assumptions", []):
        print(f"    • {a}")
    if not plan.get("assumptions"):
        print("    None")

    conf = plan.get("confidence_level", "?")
    score = plan.get("confidence_score", "?")
    emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
    print(f"\n  Confidence: {emoji} {conf.upper()} ({score})")

    print("\n  ⟶ Quality check:")
    print("    - Are subtasks in the right order?")
    print("    - Is the DoD specific enough to verify?")
    print("    - Does the confidence level feel right?")
    print("    - Would you approve this plan if a junior posted it?")

    # ── Stage 5: Plan Posting ────────────────────────────────────────────
    header("STAGE 5: Plan Posting")
    print("  What it does: Post plan to Slack + Jira for visibility, proceed immediately")
    print("  Model: none (formatting + API calls)\n")
    print("  ✓ No Slack configured — would auto-proceed")
    print("  In production: plan is posted to Slack channel with confidence badge,")
    print("  subtask list, DoD, risks, and assumptions. Team sees it, Kronode continues.")

    # ── Summary ──────────────────────────────────────────────────────────
    header("PIPELINE SUMMARY")
    print(f"  Ticket:       {task.get('title', '?')[:60]}")
    print(f"  Type:         {task.get('ticket_type', '?')}")
    print(f"  Complexity:   {task.get('estimated_complexity', '?')}")
    print(f"  Ambiguities:  {len(ambiguities)}")
    print(f"  Files:        {len(cb_result.get('relevant_files', []))}")
    print(f"  Conventions:  {len(cb_result.get('conventions', []))}")
    print(f"  Subtasks:     {len(plan.get('subtasks', []))}")
    print(f"  DoD items:    {len(plan.get('definition_of_done', []))}")
    print(f"  Confidence:   {emoji} {conf} ({score})")
    print(f"\n  Next step would be: guardrails → coder → PR")
    print()


if __name__ == "__main__":
    asyncio.run(main())
