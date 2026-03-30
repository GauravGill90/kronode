# Kronode

Organizational memory for AI coding tools. Kronode learns how your engineering team builds software by watching PRs and review comments, then serves that knowledge to any AI coding agent via MCP.

---

## What it does

Any AI coding tool (Claude Code, Cursor, Windsurf) can call Kronode mid-task to get:
- **Conventions** ranked by relevance to the current task (7-signal scoring)
- **Reviewer preferences** — what each reviewer typically requests
- **Past failures** — mistakes to avoid in specific areas
- **File companions** — files that usually change together (catches missed translations, tests, schemas)

## MCP Server

### Start the server

```bash
cd backend

# Dev mode (direct org ID)
uv run python -m app.mcp.main --org-id 57

# Production mode (API token)
uv run python -m app.mcp.main --token kron_xxxxx
```

### Add to Claude Code

```bash
cd /path/to/your/repo
claude mcp add kronode -- uv run --directory /path/to/kronode/backend python -m app.mcp.main --org-id <your_org_id>
```

### Add to Cursor

In Cursor settings → MCP Servers:
```json
{
  "kronode": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/kronode/backend", "python", "-m", "app.mcp.main", "--org-id", "57"]
  }
}
```

### Auto-trigger on every task

Add to your repo's `CLAUDE.md` (or `.cursor/rules`):

```markdown
Before starting any task, call kronode:get_context with the task description.
Before committing, call kronode:check_completeness with files changed.
```

### MCP Tools

| Tool | Purpose |
|------|---------|
| `get_context` | Get ranked conventions, pitfalls, reviewer patterns, and past failures for a task |
| `get_file_companions` | Find files that typically change together (catches missed translations, tests) |
| `get_reviewer_guidance` | Get specific preferences for likely reviewers |
| `check_completeness` | Verify all companion files were updated before committing |

### Test locally (raw MCP protocol)

```bash
echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run python -m app.mcp.main --org-id 57
```

---

## How Kronode learns

1. **Initial extraction** — analyzes last 200+ merged PRs to extract conventions
2. **Continuous learning** — every PR review comment feeds back into conventions
3. **Failure memory** — rejected PRs are classified and remembered for future tasks
4. **Reviewer modeling** — tracks which reviewers enforce which patterns

---

## Quick Start (Full Stack)

```bash
make install   # install deps (backend + frontend)
make infra     # start postgres + redis
make migrate   # apply database migrations
make dev       # start everything
```

Backend: http://localhost:8000 | Frontend: http://localhost:3000 | API docs: http://localhost:8000/docs

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| **Node.js** | 18+ | Frontend runtime |
| **pnpm** | 8+ | Frontend package manager (`npm install -g pnpm`) |
| **Python** | 3.12+ | Backend runtime |
| **uv** | latest | Python package manager (`pip install uv`) |
| **Docker** | latest | Runs PostgreSQL and Redis locally |

---

## Environment Variables

### Backend (`backend/.env`)

```
# Clerk — used to verify tokens server-side
CLERK_SECRET_KEY=sk_test_your_secret_key_here

# PostgreSQL connection string
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/kronode

# Redis connection string
REDIS_URL=redis://localhost:6379/0

# LLM API keys
ANTHROPIC_API_KEY=sk-ant-your_key_here          # required — coder, reviewer agents
GEMINI_API_KEY=your_gemini_api_key_here          # optional — cheap tier (ticket interpretation, conventions)
DEEPSEEK_API_KEY=                                # optional — cheap tier fallback
OPENAI_API_KEY=                                  # optional — embeddings + cheap/quality fallback

# GitHub OAuth (optional)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# Jira OAuth (optional — required for Jira integration)
JIRA_CLIENT_ID=
JIRA_CLIENT_SECRET=

# Slack bot (optional — required for Slack integration)
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=

# App
BACKEND_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000

# Dev / testing
BYPASS_LLM=false                                 # skip all LLM calls for pipeline testing
```

### Frontend (`frontend/.env.local`)

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
CLERK_SECRET_KEY=sk_test_your_secret_key_here
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/onboarding
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Project Structure

```
kronode/
├── backend/
│   ├── app/
│   │   ├── mcp/               # MCP server (the product)
│   │   │   ├── server.py      # Tool definitions (get_context, check_completeness, etc.)
│   │   │   ├── main.py        # Entry point (stdio transport)
│   │   │   └── auth.py        # API key validation
│   │   ├── api/v1/            # REST endpoints (conventions, onboarding, dashboard)
│   │   ├── agents/            # Convention extraction, context building, feedback extraction
│   │   ├── core/              # Config, database, auth, LLM routing, embeddings
│   │   ├── models/            # SQLAlchemy models (Convention, MemoryRecord, etc.)
│   │   ├── pipeline/          # Convention extraction pipeline, PR outcome polling
│   │   ├── services/          # GitHub/Bitbucket/Jira/Slack integrations
│   │   └── skills/            # Composable skill presets + composer
│   └── alembic/               # Database migrations
├── frontend/
│   ├── app/                   # Next.js App Router pages
│   ├── components/            # Dashboard, onboarding, conventions UI
│   └── lib/                   # API client, types, store, hooks
├── docs/                      # Architecture, pipeline flow, product docs
├── PRODUCT.md                 # Product definition
├── PRODUCT-CONTEXT-API.md     # Context API evaluation
├── Makefile
└── docker-compose.yml
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| MCP Server | Python, `mcp` SDK (stdio transport) |
| Backend | FastAPI, Python 3.12, SQLAlchemy (async) |
| Database | PostgreSQL 16 (asyncpg) |
| Convention Engine | 7-signal relevance ranking with semantic embeddings |
| LLM Routing | Gemini Flash / GPT-4.1 nano / Haiku (auto-failover, cheapest first) |
| Background Jobs | Celery + Redis |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, Clerk, Zustand |
| Integrations | GitHub, Bitbucket, Jira, Slack, Confluence |
