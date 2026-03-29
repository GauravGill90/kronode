# Kronode

Kronode is an autonomous AI developer that lives inside your engineering organization — reading tickets, writing code, opening pull requests, and getting smarter over time.

---

## Quick Start

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

### Frontend (`frontend/.env.local`)

```
# Clerk — authentication (get these from https://dashboard.clerk.com)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
CLERK_SECRET_KEY=sk_test_your_secret_key_here

# Clerk redirect URLs
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/onboarding
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding

# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

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

---

## Makefile Reference

### Core Workflow

| Command | What it does |
|---|---|
| `make dev` | Start everything (infra + backend + worker + beat + frontend) |
| `make stop` | Kill all running services |
| `make restart` | Stop + restart backend, worker, beat |
| `make status` | Show which services are running |

### Setup

| Command | What it does |
|---|---|
| `make install` | Install backend (uv) and frontend (pnpm) dependencies |
| `make infra` | Start PostgreSQL + Redis via Docker Compose |
| `make migrate` | Run Alembic database migrations |

### Individual Services

| Command | What it does |
|---|---|
| `make backend` | FastAPI on port 8000 (hot-reload) |
| `make frontend` | Next.js on port 3000 |
| `make worker` | Celery worker (auto-reload on file changes) |
| `make beat` | Celery beat scheduler (PR polling, convention refresh) |

### Testing

| Command | What it does |
|---|---|
| `make test-quick` | Quick orchestrator validation |
| `make test-orchestrator` | Full E2E orchestrator test (runs real agents) |
| `make test-full` | Full stack integration test |

---

## Project Structure

```
kronode/
���── backend/
│   ├── app/
│   │   ���── api/v1/            # REST endpoints (tasks, onboarding, conventions, skills, jira)
│   │   ├── agents/            # 16 agents (router, planner, coder, reviewer, memory, etc.)
│   │   ├── core/              # Config, database, auth, LLM router, embeddings
│   │   ├── models/            # SQLAlchemy models (task, org, convention, skill, doc_chunk, memory)
│   │   ├── orchestration/     # Multi-flow LangGraph orchestrator
│   │   │   ├── core/          # Flow base, classifier, registries
│   │   │   └── flows/         # ticket_implementation, onboarding, ingestion
│   │   ├── pipeline/          # Celery tasks, convention extraction, self-onboarding
│   │   ├── services/          # GitHub, Jira, Slack, convention extractor, doc ingestion
│   │   │   └── doc_providers/ # Agnostic doc providers (git, confluence, etc.)
│   │   └── skills/            # Composable skill presets + composer
│   └── alembic/               # Database migrations
├── frontend/
│   ├── app/                   # Next.js App Router pages
│   ├── components/            # UI, dashboard, onboarding, task, conventions
│   ├── lib/                   # API client, types, store, hooks (SSE, tasks)
│   └── tokens/                # Design system color tokens
├── docs/                      # Architecture, pipeline flow, product gaps
├── Makefile
└── docker-compose.yml
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, Clerk, Zustand |
| Backend | FastAPI, Python 3.12, SQLAlchemy (async) |
| Database | PostgreSQL 16 (asyncpg) |
| Migrations | Alembic |
| Orchestration | LangGraph |
| Background jobs | Celery + Redis |
| LLM | Anthropic (Haiku/Sonnet), OpenAI, Gemini, DeepSeek (auto-failover) |
| Integrations | GitHub API, Jira REST API, Slack API |
| Package management | pnpm (frontend), uv (backend) |
| Local infra | Docker Compose |

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system diagram, data model, agent chain, and flow details.

See [docs/router-flow.md](docs/router-flow.md) for the pipeline Mermaid diagram.
