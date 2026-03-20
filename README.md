# Kronode

Kronode is an autonomous AI developer that lives inside your engineering organization — reading tickets, writing code, opening pull requests, and getting smarter over time.

---

## Prerequisites

Before you begin, make sure you have the following installed:

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

Create a file at `frontend/.env.local` with the following variables:

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

Create a file at `backend/.env` with the following variables:

```
# Clerk — used to verify tokens server-side (same secret key as frontend)
CLERK_SECRET_KEY=sk_test_your_secret_key_here

# PostgreSQL connection string
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/kronode

# Redis connection string
REDIS_URL=redis://localhost:6379/0

# Anthropic API key (used by planner, coder, reviewer agents)
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Gemini API key (used for cheap batch work — ticket interpretation, convention extraction)
GEMINI_API_KEY=your_gemini_api_key_here

# GitHub OAuth (optional)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# Jira OAuth credentials (optional — required for Jira integration)
JIRA_CLIENT_ID=
JIRA_CLIENT_SECRET=

# Slack bot credentials (optional — required for Slack integration)
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=

# App
BACKEND_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000

# Dev / testing — set to true to skip all LLM calls
BYPASS_LLM=false
```

---

## Getting Started

Follow these steps in order to get the full stack running locally.

### 1. Start infrastructure (PostgreSQL + Redis)

```bash
make infra
```

This starts PostgreSQL on port `5432` and Redis on port `6379` using Docker Compose.

### 2. Install all dependencies

```bash
make install
```

This runs two things:
- `cd backend && uv sync` — installs Python dependencies
- `cd frontend && pnpm install` — installs Node dependencies

You can also run each separately:

```bash
# Backend only
cd backend && uv sync

# Frontend only
cd frontend && pnpm install
```

### 3. Run database migrations

```bash
make migrate
```

This applies all Alembic migrations and sets up the database schema. The underlying command is:

```bash
cd backend && uv run alembic upgrade head
```

### 4. Start the backend dev server

```bash
make backend
```

This starts the FastAPI server at **http://localhost:8000** with hot-reload enabled. The underlying command is:

```bash
cd backend && uv run uvicorn app.main:app --reload
```

Verify it is running by visiting http://localhost:8000/health — you should see `{"status": "ok"}`.

### 5. Start the frontend dev server

```bash
make frontend
```

This starts the Next.js app at **http://localhost:3000**. The underlying command is:

```bash
cd frontend && pnpm dev
```

---

## Background Workers (optional)

Kronode uses Celery for background task processing (e.g. running the AI agent, polling PRs). These are optional for basic local development but required for the agent to execute tickets.

### Start the Celery worker

```bash
make worker
```

This starts a Celery worker with auto-reload on Python file changes.

### Start the Celery beat scheduler

```bash
make beat
```

This starts the Celery beat scheduler, which handles recurring tasks such as polling pull requests every 60 seconds.

---

## All Makefile Targets

| Command | What it does |
|---|---|
| `make infra` | Starts PostgreSQL and Redis via Docker Compose |
| `make install` | Installs backend (uv) and frontend (pnpm) dependencies |
| `make migrate` | Runs Alembic database migrations |
| `make backend` | Starts the FastAPI backend dev server on port 8000 |
| `make frontend` | Starts the Next.js frontend dev server on port 3000 |
| `make worker` | Starts the Celery background worker |
| `make beat` | Starts the Celery beat scheduler |

---

## Project Structure

```
kronode/
├── backend/          # FastAPI backend (Python 3.12, uv)
│   ├── app/
│   │   ├── api/      # Route handlers
│   │   ├── core/     # Config, database, auth
│   │   ├── models/   # SQLAlchemy models
│   │   └── main.py   # FastAPI application entry point
│   └── alembic/      # Database migration files
├── frontend/         # Next.js frontend (TypeScript, pnpm)
│   ├── app/          # Next.js App Router pages
│   ├── components/   # Shared React components
│   └── tokens/       # Design system tokens
├── Makefile          # Developer convenience commands
└── docker-compose.yml
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Auth | Clerk |
| Backend | FastAPI, Python 3.12 |
| Database | PostgreSQL (async via SQLAlchemy + asyncpg) |
| Migrations | Alembic |
| Background jobs | Celery + Redis |
| Package management | pnpm (frontend), uv (backend) |
| Local infra | Docker Compose |
