import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_TOTAL_BYTES = 30_000
MAX_FILE_BYTES = 3_000

SYSTEM_PROMPT = """You are an expert software test engineer. Given implementation files and coding conventions, write comprehensive unit tests.

Rules:
- Write COMPLETE file contents — never partial snippets or placeholders
- Mirror the test conventions observed in the project
- TypeScript/React: use Jest + React Testing Library; test paths: ComponentName.test.tsx or __tests__/ComponentName.test.tsx
- Python: use pytest with async fixtures where needed; test paths: tests/test_<module_name>.py
- SQL/dbt: write dbt YAML schema tests; test paths: tests/<model_name>.yml
- Include at minimum: one happy-path test, one edge-case test, one error/null-input test per file
- Test observable behaviour through public interfaces, not implementation internals

Respond with a JSON array only. No markdown, no explanation outside the JSON.

JSON structure:
[
  {"path": "tests/test_foo.py", "content": "full test file content here"},
  {"path": "components/__tests__/Foo.test.tsx", "content": "full test file content here"}
]
"""


class TesterAgent(AgentBase):
    display_name = "Tester"

    async def run(self, context: dict) -> dict:
        coder_result = context.get("coder_agent", {})
        impl_files = coder_result.get("files", [])
        branch_name = coder_result.get("branch_name", "")

        context_bundle = context.get("context_builder", {})
        conventions = context_bundle.get("conventions", [])

        skill_names = context.get("agent_profile", "fullstack")

        if not impl_files:
            logger.info("[Tester] No implementation files — skipping")
            return {
                "summary": "No implementation files found — test generation skipped.",
                "test_files": [],
                "coverage_summary": "No tests generated.",
                "committed": False,
            }

        # Build capped file listing for the prompt
        file_sections: list[str] = []
        total = 0
        for f in impl_files:
            snippet = f.get("content", "")
            if len(snippet) > MAX_FILE_BYTES:
                snippet = snippet[:MAX_FILE_BYTES] + "\n… [truncated]"
            section = f"### {f['path']}\n```\n{snippet}\n```"
            if total + len(section) > MAX_TOTAL_BYTES:
                break
            file_sections.append(section)
            total += len(section)

        truncation_note = ""
        if len(file_sections) < len(impl_files):
            truncation_note = f"\nNote: only {len(file_sections)} of {len(impl_files)} files shown due to context limits."

        user_message = (
            f"Skills: {skill_names}\n"
            f"Conventions observed in this codebase:\n"
            f"{json.dumps(conventions, indent=2) if conventions else 'none extracted'}\n"
            f"{truncation_note}\n\n"
            f"Implementation files to test:\n"
            + "\n\n".join(file_sections)
        )

        test_files: list[dict] = []
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = message.content[0].text.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                test_files = [f for f in parsed if f.get("path") and f.get("content")]
            elif isinstance(parsed, dict):
                test_files = parsed.get("files", [])
        except Exception as exc:
            logger.warning(f"[Tester] LLM call or parse failed: {exc}")
            return {
                "summary": f"Test generation failed ({exc}).",
                "test_files": [],
                "coverage_summary": "Test generation failed.",
                "committed": False,
            }

        if not test_files:
            return {
                "summary": "LLM returned no test files.",
                "test_files": [],
                "coverage_summary": "No tests generated.",
                "committed": False,
            }

        # Commit test files to the PR branch
        committed = False
        commit_note = ""
        repo_url = context.get("fork_repo_url") or context.get("repo_url", "")
        github_token = context.get("github_access_token")

        if repo_url and github_token and branch_name:
            from app.services.github_service import add_files_to_branch
            committed = await add_files_to_branch(
                repo_url=repo_url,
                branch_name=branch_name,
                files=test_files,
                commit_message=f"test: add unit tests for {len(impl_files)} implementation file(s)",
                token=github_token,
            )
            commit_note = (
                f" Committed to branch {branch_name}."
                if committed
                else " Warning: failed to commit tests to branch (non-fatal)."
            )
        else:
            commit_note = " No branch/token available — tests not committed."

        summary = (
            f"Generated {len(test_files)} test file(s) covering "
            f"{len(impl_files)} implementation file(s).{commit_note}"
        )
        logger.info(f"[Tester] {summary}")
        return {
            "summary": summary,
            "test_files": test_files,
            "coverage_summary": f"{len(test_files)} test file(s) generated.",
            "committed": committed,
        }
