# Kronode — Full-Stack Scaffold Plan

## Context
Building from a blank slate (only agents.md + README exist). The goal is a full scaffold with a working end-to-end core pipeline (Task Router → Planner → Coder) and stubs for all other agents, plus a complete frontend and backend structure.

**Decisions:** Flat layout (`frontend/` + `backend/` at root), pnpm, uv, Next.js 14 App Router, FastAPI, Clerk auth, Supabase/PostgreSQL, Celery + Redis.

---

## Directory Structure

### Root
```
kronode/
├── frontend/
├── backend/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── agents.md
```

### frontend/
```
frontend/
├── package.json                  (pnpm, Next.js 14, Tailwind, Clerk, Zustand, Axios, TanStack Query)
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── postcss.config.js
├── .env.local.example
├── app/
│   ├── layout.tsx                (ClerkProvider wrapping)
│   ├── globals.css
│   ├── page.tsx                  (Step 0: welcome + Clerk sign-in)
│   ├── onboarding/
│   │   ├── layout.tsx            (shared shell: progress bar + nav)
│   │   └── [step]/
│   │       └── page.tsx          (dynamic step router, steps 1–11)
│   ├── dashboard/
│   │   └── page.tsx              (server component: agent status + task history)
│   └── task/
│       └── [id]/
│           └── page.tsx          (task detail + SSE stream)
├── components/
│   ├── ui/                       (Button, Input, Card, Badge, ProgressBar, Spinner)
│   ├── onboarding/               (Step1Account … Step11ReadingSetup)
│   ├── dashboard/                (AgentHeader, TaskInput, TaskCard, IntegrationRow)
│   └── task/                     (ProgressStream, EventLine)
└── lib/
    ├── api.ts                    (axios instance with Clerk token injection)
    ├── store.ts                  (Zustand: onboarding state, agent config)
    ├── hooks/
    │   ├── useSSE.ts             (EventSource hook with cleanup)
    │   └── useTasks.ts           (TanStack Query wrappers)
    └── types.ts                  (shared TS interfaces matching API schemas)
```

### backend/
```
backend/
├── pyproject.toml                (uv: fastapi, uvicorn, sqlalchemy, alembic, celery, redis, httpx, anthropic, clerk-backend-api, pydantic-settings)
├── .env.example
├── alembic.ini
├── alembic/
│   └── versions/
│       └── 001_initial.py        (users, orgs, onboarding_config, tasks, task_events, memory_records)
└── app/
    ├── main.py                   (FastAPI app, CORS, routers mounted, lifespan)
    ├── celery_app.py             (Celery instance + Redis broker)
    ├── core/
    │   ├── config.py             (pydantic-settings: DATABASE_URL, REDIS_URL, CLERK_SECRET_KEY, ANTHROPIC_API_KEY, etc.)
    │   ├── auth.py               (Clerk JWT validation dependency)
    │   └── database.py           (async SQLAlchemy engine + session)
    ├── models/
    │   ├── user.py
    │   ├── org.py
    │   ├── task.py               (Task + TaskEvent)
    │   └── memory.py
    ├── schemas/
    │   ├── onboarding.py         (Pydantic request/response models)
    │   ├── task.py
    │   └── dashboard.py
    ├── api/
    │   └── v1/
    │       ├── router.py         (include_router for all sub-routers)
    │       ├── onboarding.py     (POST /onboarding/* — store config, stubs)
    │       ├── dashboard.py      (GET /dashboard)
    │       └── tasks.py          (POST /task, GET /task/{id}, SSE /task/{id}/stream)
    ├── pipeline/
    │   ├── pipeline.py           (orchestrator: runs agent chain, emits SSE events)
    │   └── task_queue.py         (Celery task: run_pipeline.delay(task_id))
    ├── agents/
    │   ├── base.py               (AgentBase: abstract run(context) → AgentResult)
    │   ├── router_agent.py       ✅ WORKING — classifies task, returns ordered agent list
    │   ├── planner_agent.py      ✅ WORKING — calls Claude API, returns plan + DoD checklist
    │   ├── coder_agent.py        ✅ WORKING — calls Claude API, returns files + PR metadata
    │   ├── context_builder.py    🔲 STUB
    │   ├── guardrails_agent.py   🔲 STUB (always passes)
    │   ├── clarification_agent.py 🔲 STUB (always says no clarification needed)
    │   ├── tester_agent.py       🔲 STUB
    │   ├── execution_verifier.py 🔲 STUB (always passes)
    │   ├── reviewer_agent.py     🔲 STUB (always approves)
    │   ├── doc_agent.py          🔲 STUB
    │   └── memory_agent.py       🔲 STUB
    └── services/
        ├── github_service.py     (create branch, commit files, open PR via GitHub API)
        ├── jira_service.py       (update ticket status — stub for now)
        └── slack_service.py      (post notification — stub for now)
```

---

## Working Agent Logic

### Task Router (`router_agent.py`)
- Input: task description string
- Calls Claude (claude-haiku-4-5) with few-shot prompt
- Returns: `{ agents: [...], complexity: "simple|medium|complex", steps: int }`
- Routing rules mirror the table in agents.md

### Planner Agent (`planner_agent.py`)
- Input: task + context bundle
- Calls Claude (claude-opus-4-6) with structured system prompt
- Returns: `{ subtasks: [...], definition_of_done: [...], risk_flags: [...] }`
- DoD checklist must be a list of strings the Reviewer can check against

### Coder Agent (`coder_agent.py`)
- Input: task + plan + DoD + context
- Calls Claude (claude-sonnet-4-6) with full context
- Returns: `{ branch_name, files: [{path, content}], commit_message, pr_title, pr_description, slack_summary }`
- Invokes `github_service.py` to create branch + commit + PR

---

## API Endpoints (functional on day 1)

| Method | Path | Status |
|--------|------|--------|
| POST | /v1/task | Working — queues pipeline via Celery |
| GET | /v1/task/{id} | Working — returns status + events |
| SSE | /v1/task/{id}/stream | Working — streams TaskEvent rows |
| GET | /v1/dashboard | Working — returns agent config + last 10 tasks |
| POST | /v1/onboarding/* | Stub — accepts + stores, returns 200 |

---

## Database Schema (Alembic migration 001)

- **users** — id, clerk_id, email, name, role, created_at
- **organizations** — id, name, clerk_org_id, created_at
- **onboarding_config** — org_id (FK), repo_url, jira_project, slack_channel, capabilities (JSONB), guardrails (JSONB), agent_name, agent_avatar, project_context, completed_at
- **tasks** — id (UUID), org_id (FK), description, status (queued/running/done/failed/paused), result (JSONB), created_at, completed_at
- **task_events** — id, task_id (FK), agent_name, event_type, message, payload (JSONB), created_at
- **memory_records** — id, org_id (FK), task_id (FK), record_type, content (JSONB), source, created_at

---

## Key Dependencies

### Frontend (package.json)
```
next@14, react@18, typescript, tailwindcss, @clerk/nextjs,
zustand, axios, @tanstack/react-query, clsx, lucide-react
```

### Backend (pyproject.toml)
```
fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg,
alembic, celery[redis], redis, httpx, anthropic,
clerk-backend-api, pydantic-settings, python-jose, python-multipart
```

---

## docker-compose.yml Services
- `postgres` — postgres:16, port 5432
- `redis` — redis:7-alpine, port 6379
- `backend` — uvicorn app.main:app --reload, port 8000
- `worker` — celery -A app.celery_app worker
- `frontend` — next dev, port 3000

---

## Implementation Order

**Phase 1 — Root + Infrastructure**
1. Root `.gitignore`, `.env.example`, `docker-compose.yml`, updated `README.md`, `docs/plan.md`

**Phase 2 — Backend Foundation**
2. `pyproject.toml`, `alembic.ini`
3. `app/core/` — config, database, auth
4. `app/models/` — all SQLAlchemy models
5. `app/schemas/` — all Pydantic schemas
6. Alembic migration 001

**Phase 3 — Backend API**
7. `app/main.py` + `app/celery_app.py`
8. `app/api/v1/` — all route files
9. `app/pipeline/` — orchestrator + Celery task

**Phase 4 — Agents**
10. `app/agents/base.py`
11. Stub all 8 passive agents
12. Implement Task Router (claude-haiku-4-5)
13. Implement Planner Agent (claude-opus-4-6)
14. Implement Coder Agent (claude-sonnet-4-6)
15. `app/services/github_service.py`

**Phase 5 — Frontend Foundation**
16. `package.json`, `next.config.js`, `tailwind.config.ts`, `tsconfig.json`
17. `app/layout.tsx` (ClerkProvider), `globals.css`
18. `lib/api.ts`, `lib/store.ts`, `lib/types.ts`
19. `lib/hooks/useSSE.ts`, `lib/hooks/useTasks.ts`
20. `components/ui/` — 6 base components

**Phase 6 — Frontend Pages**
21. `app/page.tsx` — Step 0 welcome + Clerk sign-in
22. `app/onboarding/layout.tsx` + `[step]/page.tsx`
23. All 11 onboarding step components
24. `app/dashboard/page.tsx` + dashboard components
25. `app/task/[id]/page.tsx` + SSE stream component

---

## Verification
- `docker-compose up` starts all services cleanly
- POST /v1/task with a plain English task description
- GET /v1/task/{id}/stream shows SSE events: router → planner → coder
- GitHub PR is opened in the connected repo
- Frontend loads at localhost:3000, Clerk sign-in works
- Onboarding steps 1–11 navigate correctly
- Dashboard shows submitted task with status
