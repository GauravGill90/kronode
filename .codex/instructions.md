# Kronode MCP

You have access to the Kronode MCP server which contains this team's organizational memory — conventions, internal documentation, reviewer preferences, and past mistakes.

## When to call get_context

Call `kronode:get_context` BEFORE:
- Writing or modifying code
- Reviewing a PR or diff
- Planning an implementation approach
- Answering questions about team conventions, patterns, or best practices
- Debugging something that might relate to known pitfalls

**Call pattern:**
```
kronode:get_context(task_description="<what the user asked>", files_touched=["<relevant file paths>"])
```

## When to skip

Don't call get_context for:
- Simple file reads, grep, or navigation
- Git log / git status / git diff
- Quick syntax questions unrelated to this codebase

## get_doc

If get_context returns a doc chunk with `full_available: true`, call `kronode:get_doc` to get the full page.
