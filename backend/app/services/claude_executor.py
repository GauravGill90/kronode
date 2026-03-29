"""Claude Agent SDK executor.

Clones a repo, runs Claude Code agent with Kronode's context injected,
collects file changes, pushes branch, opens PR.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

from app.core.config import settings

logger = logging.getLogger(__name__)


async def execute_task(
    task_description: str,
    plan: dict,
    context_bundle: dict,
    repo_url: str,
    fork_repo_url: str | None,
    github_token: str,
    profile_injection: str = "",
    coding_standards: str = "",
    on_event: callable = None,
    review_feedback: dict | None = None,
    model_override: str | None = None,
) -> dict:
    """Run Claude Code agent against a cloned repo.

    Returns dict with: branch_name, files_changed, commit_message, pr_url, pr_title, pr_description, etc.
    """
    write_repo = fork_repo_url or repo_url
    clone_dir = None

    try:
        # 1. Shallow clone the fork
        clone_dir = tempfile.mkdtemp(prefix="kronode_")
        if on_event:
            await on_event("Cloning repository...")

        clone_url = _inject_token(write_repo, github_token)
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, clone_dir],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Git clone failed: {proc.stderr[:500]}")

        logger.info(f"[ClaudeExecutor] Cloned {write_repo} to {clone_dir}")

        # 2. Create branch
        subtasks = plan.get("subtasks", [])
        slug = re.sub(r"[^a-z0-9]+", "-", task_description[:40].lower()).strip("-")
        branch_name = f"feature/{slug}"

        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=clone_dir, capture_output=True, text=True,
        )

        # 3. Build system prompt with Kronode context
        system_prompt = _build_system_prompt(
            plan=plan,
            context_bundle=context_bundle,
            profile_injection=profile_injection,
            coding_standards=coding_standards,
        )

        # 4. Build task prompt
        task_prompt = _build_task_prompt(task_description, plan, review_feedback)

        if on_event:
            await on_event("Running Claude Code agent...")

        # 5. Run Claude Agent SDK
        agent_result = await _run_agent(
            cwd=clone_dir,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            on_event=on_event,
            model_override=model_override,
        )

        # 6. Collect changes via git
        files_changed = _get_changed_files(clone_dir)
        if not files_changed:
            logger.warning("[ClaudeExecutor] Agent made no file changes")
            return {
                "branch_name": branch_name,
                "files_changed": [],
                "commit_message": "no changes",
                "pr_url": None,
                "summary": "Agent completed but made no file changes.",
                "agent_response": agent_result.get("response", ""),
                "cost_usd": agent_result.get("cost_usd", 0),
                "num_turns": agent_result.get("num_turns", 0),
            }

        if on_event:
            await on_event(f"Agent modified {len(files_changed)} file(s). Pushing...")

        # 7. Commit and push
        commit_message = f"fix: {task_description[:72]}"
        subprocess.run(["git", "add", "-A"], cwd=clone_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=clone_dir, capture_output=True, text=True,
        )
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=clone_dir, capture_output=True, text=True, timeout=60,
        )
        if push_result.returncode != 0:
            raise RuntimeError(f"Git push failed: {push_result.stderr[:500]}")

        logger.info(f"[ClaudeExecutor] Pushed branch {branch_name}")

        # 8. Open PR via GitHub API
        pr_title = f"fix: {task_description[:70]}"
        pr_description = _build_pr_description(task_description, plan, files_changed, agent_result)

        from app.services.github_service import _parse_repo, _auth_headers, GITHUB_API
        import httpx
        owner, repo = _parse_repo(write_repo)
        headers = _auth_headers(github_token)

        async with httpx.AsyncClient(timeout=30) as client:
            # Get default branch
            resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
            resp.raise_for_status()
            default_branch = resp.json()["default_branch"]

            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=headers,
                json={
                    "title": pr_title,
                    "body": pr_description,
                    "head": branch_name,
                    "base": default_branch,
                },
            )
            resp.raise_for_status()
            pr_url = resp.json()["html_url"]

        logger.info(f"[ClaudeExecutor] PR opened: {pr_url}")

        return {
            "branch_name": branch_name,
            "files_changed": files_changed,
            "commit_message": commit_message,
            "pr_url": pr_url,
            "pr_title": pr_title,
            "pr_description": pr_description,
            "summary": (
                f"Code written: {len(files_changed)} file(s). "
                f"Branch: {branch_name}. PR: {pr_url}. "
                f"Cost: ${agent_result.get('cost_usd', 0):.4f}. "
                f"Turns: {agent_result.get('num_turns', 0)}."
            ),
            "agent_response": agent_result.get("response", ""),
            "cost_usd": agent_result.get("cost_usd", 0),
            "num_turns": agent_result.get("num_turns", 0),
            "slack_summary": f"PR opened: {pr_title}",
            "incomplete_dod_items": [],
        }

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[ClaudeExecutor] Failed: {exc}\n{tb}")
        if on_event:
            try:
                await on_event(f"Error: {exc}")
            except Exception:
                pass
        return {
            "branch_name": "",
            "files_changed": [],
            "pr_url": None,
            "summary": f"Claude executor failed: {exc}",
            "error": str(exc),
            "traceback": tb,
        }

    finally:
        if clone_dir and os.path.exists(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)


async def _run_agent(
    cwd: str,
    system_prompt: str,
    task_prompt: str,
    on_event: callable = None,
    model_override: str | None = None,
) -> dict:
    """Run Claude Agent SDK and collect results."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

    response_text = ""
    cost_usd = 0.0
    num_turns = 0
    tool_calls = []

    # Pass full env — Celery workers may not inherit shell env properly
    agent_env = {
        **os.environ,
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin") + ":/Users/gaurav/.local/bin",
        "HOME": os.environ.get("HOME", "/Users/gaurav"),
    }

    async for message in query(
        prompt=task_prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            permission_mode="bypassPermissions",
            cwd=cwd,
            system_prompt=system_prompt,
            model=model_override or settings.agent_sdk_model,
            max_turns=settings.agent_sdk_max_turns,
            env=agent_env,
        ),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text") and block.text:
                    response_text += block.text + "\n"
                if hasattr(block, "name"):
                    tool_calls.append(block.name)
                    if on_event:
                        tool_input = getattr(block, "input", {})
                        label = block.name
                        if block.name == "Edit" and isinstance(tool_input, dict):
                            label = f"Edit: {tool_input.get('file_path', '')}"
                        elif block.name == "Read" and isinstance(tool_input, dict):
                            label = f"Read: {tool_input.get('file_path', '')}"
                        elif block.name == "Bash" and isinstance(tool_input, dict):
                            cmd = tool_input.get("command", "")
                            label = f"Bash: {cmd[:80]}"
                        await on_event(f"Tool: {label}")

        elif isinstance(message, ResultMessage):
            cost_usd = getattr(message, "total_cost_usd", 0) or 0
            num_turns = getattr(message, "num_turns", 0) or 0
            if hasattr(message, "result") and message.result:
                response_text += str(message.result)
            logger.info(
                f"[ClaudeExecutor] Agent done. Cost: ${cost_usd:.4f}, "
                f"Turns: {num_turns}, Tools: {len(tool_calls)}"
            )

    return {
        "response": response_text.strip(),
        "cost_usd": cost_usd,
        "num_turns": num_turns,
        "tool_calls": tool_calls,
    }


def _build_system_prompt(
    plan: dict,
    context_bundle: dict,
    profile_injection: str,
    coding_standards: str,
) -> str:
    """Build system prompt injecting Kronode's organizational context."""
    conventions = context_bundle.get("conventions", [])
    doc_chunks = context_bundle.get("doc_chunks", [])
    reviewer_patterns = context_bundle.get("reviewer_patterns", [])
    pitfalls = context_bundle.get("pitfalls", [])

    parts = []

    if profile_injection:
        parts.append(profile_injection)

    if coding_standards:
        parts.append(f"## Team Coding Standards\n{coding_standards}")

    # Conventions — top 30 by relevance
    if conventions:
        conv_lines = []
        for c in conventions[:30]:
            rule = c["rule"] if isinstance(c, dict) else str(c)
            conv_lines.append(f"- {rule}")
        parts.append(f"## Coding Conventions (from team PR history)\n" + "\n".join(conv_lines))

    # Doc chunks
    if doc_chunks:
        doc_lines = []
        for chunk in doc_chunks[:5]:
            heading = chunk.get("heading", "")
            content = chunk.get("content", "")[:500]
            doc_lines.append(f"### {heading}\n{content}")
        parts.append(f"## Relevant Documentation\n" + "\n\n".join(doc_lines))

    # Reviewer patterns
    if reviewer_patterns:
        rev_lines = [f"- {p.get('preference', '')}" for p in reviewer_patterns[:5] if p.get("preference")]
        if rev_lines:
            parts.append(f"## Reviewer Patterns (address proactively)\n" + "\n".join(rev_lines))

    # Pitfalls
    if pitfalls:
        pit_lines = [f"- {p.get('description', '')}" for p in pitfalls[:5]]
        if pit_lines:
            parts.append(f"## Known Pitfalls\n" + "\n".join(pit_lines))

    return "\n\n---\n\n".join(parts) if parts else ""


def _build_task_prompt(task_description: str, plan: dict, review_feedback: dict | None = None) -> str:
    """Build the task prompt from description + plan + optional review feedback."""
    subtasks = plan.get("subtasks", [])
    dod = plan.get("definition_of_done", [])
    assumptions = plan.get("assumptions", [])

    prompt = f"## Task\n{task_description}\n"

    if review_feedback:
        changes = review_feedback.get("changes_requested", [])
        verdict = review_feedback.get("verdict", "")
        revision = review_feedback.get("revision_number", 1)
        prompt += f"\n## REVISION {revision} — Reviewer Feedback\n"
        prompt += f"The previous attempt was reviewed and changes were requested:\n"
        prompt += f"Verdict: {verdict}\n"
        prompt += "Required changes:\n"
        prompt += "\n".join(f"- {c}" for c in changes)
        prompt += "\n\nFix ONLY the issues listed above. Do not reformat unchanged code. Keep changes minimal.\n"

    if subtasks:
        prompt += "\n## Implementation Plan\n"
        for st in subtasks:
            files = ", ".join(st.get("files_affected", []))
            prompt += f"{st['order']}. {st['description']}"
            if files:
                prompt += f" (files: {files})"
            prompt += "\n"

    if dod:
        prompt += "\n## Definition of Done\n"
        prompt += "\n".join(f"- {d}" for d in dod)

    if assumptions:
        prompt += "\n\n## Assumptions\n"
        prompt += "\n".join(f"- {a}" for a in assumptions)

    prompt += "\n\nImplement the plan above. Only modify files necessary for the fix. Do not reformat unchanged code. Run any relevant tests if possible."
    return prompt


def _get_changed_files(clone_dir: str) -> list[str]:
    """Get list of files changed in the working tree."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=clone_dir, capture_output=True, text=True,
    )
    # Also include untracked files
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=clone_dir, capture_output=True, text=True,
    )
    files = set()
    for line in (result.stdout + "\n" + untracked.stdout).strip().split("\n"):
        if line.strip():
            files.add(line.strip())
    return sorted(files)


def _inject_token(repo_url: str, token: str) -> str:
    """Inject GitHub token into clone URL for auth."""
    # https://github.com/owner/repo → https://x-access-token:TOKEN@github.com/owner/repo
    if repo_url.startswith("https://github.com/"):
        return repo_url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")
    return repo_url


def _build_pr_description(
    task_description: str,
    plan: dict,
    files_changed: list[str],
    agent_result: dict,
) -> str:
    """Build a PR description."""
    dod = plan.get("definition_of_done", [])
    lines = [
        f"## Summary",
        f"{task_description}",
        "",
        f"## Files Changed",
        *[f"- `{f}`" for f in files_changed],
        "",
    ]
    if dod:
        lines += [
            "## Definition of Done",
            *[f"- [ ] {d}" for d in dod],
            "",
        ]
    lines += [
        f"---",
        f"*Generated by Kronode (Claude Agent SDK). "
        f"Cost: ${agent_result.get('cost_usd', 0):.4f}, "
        f"Turns: {agent_result.get('num_turns', 0)}.*",
    ]
    return "\n".join(lines)
