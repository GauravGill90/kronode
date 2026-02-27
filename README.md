# kronode

Autonomous AI developer tool. Non-technical users connect GitHub, Jira, and Slack — an agent pipeline handles tasks end-to-end.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), Tailwind CSS, Clerk, Zustand |
| Backend | FastAPI, PostgreSQL, Celery + Redis |
| Agents | Anthropic Claude (claude-haiku-4-5 / claude-sonnet-4-6 / claude-opus-4-6) |
| Auth | Clerk |
| Database | Supabase (PostgreSQL) |

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node.js 20+ and pnpm
- Python 3.12+ and uv

### 1. Environment
```bash
cp .env.example .env
# Fill in CLERK_SECRET_KEY, ANTHROPIC_API_KEY, and GitHub OAuth credentials
```

### 2. Run with Docker
```bash
docker-compose up
```

Frontend: http://localhost:3000
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs

### 3. Run locally (without Docker)

**Backend**
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# In a second terminal:
uv run celery -A app.celery_app worker --loglevel=info
```

**Frontend**
```bash
cd frontend
pnpm install
pnpm dev
```

## Project Structure

```
kronode/
├── frontend/          Next.js app (onboarding, dashboard, task viewer)
├── backend/           FastAPI app (agent pipeline, API, worker)
├── docs/
│   └── plan.md        Full implementation plan
├── agents.md          System design and agent specifications
└── docker-compose.yml
```

## Agent Pipeline

```
Task → Router → Context Builder → Guardrails → Clarification →
Planner → Coder → Tester → Verifier → Reviewer →
GitHub PR + Jira update + Slack notification
```

See [agents.md](agents.md) for the full specification.
