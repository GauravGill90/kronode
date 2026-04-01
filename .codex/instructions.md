# Kronode MCP — MANDATORY

You have access to the Kronode MCP server which contains this team's organizational memory.

## RULE: Always call get_context first

Before answering ANY question — whether it's a code change, a read-only question, debugging, tracing, or architecture discussion — you MUST call `kronode:get_context` first.

The team's internal documentation, past mistakes, reviewer preferences, and coding conventions are ONLY available through Kronode. They are NOT in the codebase.

**Call pattern:**
```
kronode:get_context(task_description="<what the user asked>", files_touched=["<relevant file paths>"])
```

**Do NOT skip this step.** Even if you think you can answer from local files, Kronode has team context that local files don't contain:
- Which reviewers will care about this change and what they check for
- Past failures on similar tasks (mistakes to avoid)
- Internal documentation from Confluence (not in the repo)
- File companions (other files that usually change together)

## When to call get_doc

If get_context returns a doc chunk with `full_available: true`, call `kronode:get_doc` to get the full page content.
