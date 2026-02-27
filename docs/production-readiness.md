# Kronode — MVP Production Readiness

## Context
Kronode's core pipeline is functional end-to-end (task queuing → agents → GitHub PR → Slack
notifications → PR review loop). This plan hardens the system for real multi-tenant use:
fixing silent failure modes, plugging security gaps, adding observability, and ensuring the
app won't fall over under real load. Changes are organized by priority tier.

---

## T0 — Launch Blockers (must fix before first real customer)

### 1. Stuck Task Recovery + Pipeline Timeout
**Problem:** Tasks that crash mid-pipeline stay `running` or `queued` forever with no
recovery. Workers that die leave tasks orphaned.

**Fix — `backend/app/pipeline/task_queue.py`:**
- Add `recover_stuck_tasks` Celery beat task (runs every 5 min)
- Query: `status IN ('running', 'queued') AND created_at < NOW() - INTERVAL '30 minutes'`
- For each stuck task: set `status = 'failed'`, `completed_at = now()`,
  emit `TaskEvent(event_type="failed", message="Task timed out — no worker heartbeat")`
- Beat schedule entry: `"recover-stuck-tasks": {"task": "recover_stuck_tasks", "schedule": 300.0}`

**Fix — `backend/app/pipeline/task_queue.py` (run_pipeline task):**
- Wrap `asyncio.run(_run_pipeline(task_id))` with a 30-min `asyncio.wait_for` timeout
- On `asyncio.TimeoutError`: set `task.status = "failed"`, emit error event

---

### 2. Per-Org Rate Limiting
**Problem:** One org can flood the Celery queue, starving others. No protection against
accidental runaway automation.

**Fix — `backend/app/api/v1/tasks.py` (POST /task):**
- Before queuing: count tasks created by `org_id` in last 60s
  ```sql
  SELECT COUNT(*) FROM tasks WHERE org_id=:oid AND created_at > NOW() - INTERVAL '1 minute'
  ```
- If count ≥ 10: raise `HTTP 429` with `Retry-After: 60` header
- Also cap daily: if `created_at > today` count ≥ 100, raise 429

---

### 3. Real Health Check Endpoint
**Problem:** `GET /health` returns `{"status": "ok"}` without checking DB or Redis. Load
balancers/k8s liveness probes get false positives on broken deps.

**Fix — `backend/app/main.py`:**
```python
@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))  # DB check
    r = aioredis.from_url(settings.redis_url)
    await r.ping()
    await r.aclose()
    return {"status": "ok", "db": "ok", "redis": "ok"}
```
Return `HTTP 503` if either check fails.

---

### 4. CORS Lockdown
**Status:** Already wired — `main.py` reads `settings.cors_origins_list` from `CORS_ORIGINS`
env var. Default is `http://localhost:3000`.

**Action:** Update `.env.example` and production env to set:
```
CORS_ORIGINS=https://app.kronode.ai,http://localhost:3000
```
No code changes needed — just ensure the production env var is set correctly.

---

### 5. Task Event Cap
**Problem:** Long-running pipelines (especially PR revision loops) can generate thousands
of `TaskEvent` rows per task. No cap exists. DB will bloat and `/task/{id}` will OOM.

**Fix — `backend/app/pipeline/pipeline.py` (`emit_event`):**
```python
# Before inserting, check count
result = await db.execute(
    select(func.count()).where(TaskEvent.task_id == task_id)
)
if result.scalar() >= 500:
    return  # silently drop — last events are redundant detail
```

---

### 6. Multi-tenant Data Isolation Audit
**Status:** All API queries already filter by `org_id`. Confirmed:
- `tasks.py` — `GET /task/{id}`, cancel, SSE: `Task.id == task_id, Task.org_id == org_id` ✓
- `dashboard.py` — task list: `Task.org_id == user.org_id` ✓
- `task_queue.py` — polls by task_id internally (org validated at API layer) ✓

**Action:** Add `# org_id verified upstream` comment in `task_queue.py` internal helpers.

---

## T1 — Launch Quality (critical for reliability and debugging)

### 7. Error Tracking (Sentry)
**Fix — `backend/app/main.py`:**
```python
import sentry_sdk
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment,
                    traces_sample_rate=0.1)
```
**Fix — `backend/app/core/config.py`:** add `sentry_dsn: str = ""`, `environment: str = "development"`

**Fix — `backend/app/pipeline/task_queue.py`:** wrap Celery task bodies in try/except
that calls `sentry_sdk.capture_exception(e)` before re-raising.

**Fix — `.env.example`:** add `SENTRY_DSN=` and `ENVIRONMENT=production`

---

### 8. Production Docker Configuration
**Problem:** No production Dockerfile or compose — dev uses `uv run` with `--reload`.

**Fix — create `backend/Dockerfile`:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Fix — create `docker-compose.prod.yml`:**
- `backend` service: build from Dockerfile, `restart: unless-stopped`
- `worker` service: same image, `command: celery -A app.celery_app worker --loglevel=info`
- `beat` service: same image, `command: celery -A app.celery_app beat --loglevel=info`
- No `--reload` anywhere

---

### 9. LLM Cost Tracking
**Problem:** No visibility into Anthropic spend per task. Easy to blow budget unknowingly.

**Fix — `backend/app/models/task.py`:** add columns:
```python
llm_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
llm_output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

**Fix — each agent's `run()` after `client.messages.create(...)`:**
```python
context.setdefault("_token_totals", {"input": 0, "output": 0})
context["_token_totals"]["input"] += message.usage.input_tokens
context["_token_totals"]["output"] += message.usage.output_tokens
```
Agents to update: `router_agent`, `planner_agent`, `coder_agent`, `context_builder`,
`clarification_agent`, `pr_revision_agent`

**Fix — `backend/app/pipeline/pipeline.py`** (end of pipeline, before commit):
```python
totals = context.get("_token_totals", {})
task_obj.llm_input_tokens = totals.get("input", 0)
task_obj.llm_output_tokens = totals.get("output", 0)
```

**New migration:** `backend/alembic/versions/008_llm_tokens.py`

---

### 10. Dashboard Pagination
**Problem:** `GET /v1/dashboard` returns last 10 tasks hardcoded. No way to see older tasks.

**Fix — `backend/app/api/v1/dashboard.py`:**
- Add `page: int = Query(1, ge=1)` and `page_size: int = Query(10, ge=1, le=50)`
- Return `{"tasks": [...], "total": n, "page": page, "pages": ceil(n/page_size)}`

**Fix — `backend/app/schemas/dashboard.py`:** add `total: int`, `page: int`, `pages: int` to `DashboardOut`

**Fix — `frontend/lib/api.ts`:** update `getDashboard` to accept and pass `page` param

**Fix — `frontend/components/dashboard/DashboardClient.tsx`:** add prev/next pagination controls

---

### 11. Input Validation
**Problem:** No length limits on task descriptions or onboarding text fields. A large input
goes straight to the LLM.

**Fix — `backend/app/schemas/task.py`:**
```python
description: str = Field(..., min_length=10, max_length=2000)
```

**Fix — `backend/app/schemas/onboarding.py` (`ContextPayload`):**
```python
project_context: str = Field(..., max_length=5000)
coding_standards: str = Field("", max_length=3000)
```

---

## T2 — Post-Launch Polish

### 12. Token Encryption at Rest
**Problem:** GitHub/Slack/Jira tokens stored in plaintext in `onboarding_config` columns.

**Approach:** Fernet symmetric encryption. Key in `TOKEN_ENCRYPTION_KEY` env var.
- **New file `backend/app/core/crypto.py`:** `encrypt(plaintext) → str`, `decrypt(ciphertext) → str`
- Encrypt on write in onboarding endpoints (`/onboarding/github-token`, `/onboarding/jira`, `/onboarding/slack`)
- Decrypt on read in service constructors (`github_service`, `jira_service`, `slack_service`)
- No schema change needed — columns stay TEXT; add `TOKEN_ENCRYPTION_KEY` to `.env.example`

---

### 13. Database Indexes
**Problem:** No indexes on hot query columns. Will degrade at scale.

**New migration `backend/alembic/versions/009_indexes.py`:**
```python
op.create_index("ix_tasks_org_id_created_at", "tasks", ["org_id", "created_at"])
op.create_index("ix_tasks_status", "tasks", ["status"])
op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
```
Note: `tasks.org_id` and `tasks.status` already have `index=True` in the model — check if
alembic-generated indexes already exist before creating duplicates.

---

### 14. Frontend Error Boundary
**Problem:** Any unhandled JS error in `TaskDetailClient` or `DashboardClient` crashes
the whole page with a blank screen.

**Fix — new file `frontend/components/ErrorBoundary.tsx`:**
Standard React class component error boundary with fallback UI.

**Fix:** Wrap `TaskDetailClient` and `DashboardClient` in `<ErrorBoundary>` in their
respective page files.

---

### 15. Structured Logging
**Problem:** `logger.info("string")` throughout. No request IDs, no structured fields for
log aggregation (Datadog, CloudWatch, etc.).

**Fix — FastAPI middleware in `backend/app/main.py`:**
```python
import uuid as _uuid
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(_uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```
This gives every request a traceable ID without requiring a new package.
Full structlog migration can follow as a separate task.

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `backend/app/pipeline/task_queue.py` | Add `recover_stuck_tasks` beat task + pipeline timeout |
| `backend/app/pipeline/pipeline.py` | Event cap in `emit_event`, token totals save at end |
| `backend/app/api/v1/tasks.py` | Per-org rate limiting on POST /task |
| `backend/app/main.py` | Real health check, Sentry init, request-id middleware |
| `backend/app/core/config.py` | Add `sentry_dsn`, `environment` fields |
| `backend/app/api/v1/dashboard.py` | Pagination support |
| `backend/app/schemas/dashboard.py` | Add `total`, `page`, `pages` to `DashboardOut` |
| `backend/app/schemas/task.py` | Add `description` length validation |
| `backend/app/schemas/onboarding.py` | Add field length limits to `ContextPayload` |
| `backend/app/models/task.py` | Add `llm_input_tokens`, `llm_output_tokens` columns |
| `backend/app/agents/router_agent.py` | Token accumulation |
| `backend/app/agents/planner_agent.py` | Token accumulation |
| `backend/app/agents/coder_agent.py` | Token accumulation |
| `backend/app/agents/context_builder.py` | Token accumulation |
| `backend/app/agents/clarification_agent.py` | Token accumulation |
| `backend/app/agents/pr_revision_agent.py` | Token accumulation |
| `backend/app/celery_app.py` | Add `recover-stuck-tasks` beat (5min) |
| `backend/alembic/versions/008_llm_tokens.py` | New migration |
| `backend/alembic/versions/009_indexes.py` | New migration |
| `backend/Dockerfile` | New — production image |
| `docker-compose.prod.yml` | New — production compose |
| `.env.example` | Add `SENTRY_DSN`, `ENVIRONMENT`, `TOKEN_ENCRYPTION_KEY` |
| `frontend/lib/api.ts` | `getDashboard` accepts `page` param |
| `frontend/components/dashboard/DashboardClient.tsx` | Pagination UI |
| `frontend/components/ErrorBoundary.tsx` | New — React error boundary |
| `backend/app/core/crypto.py` | New — Fernet encrypt/decrypt helpers |

---

## Verification

**T0:**
1. Kill the worker mid-pipeline → within 5min, task flips to `failed` with error event
2. POST 11 tasks in <60s from same org → 11th gets HTTP 429
3. Stop Postgres → `GET /health` returns 503 (not 200)
4. Confirm production env has `CORS_ORIGINS` set to actual domain (not `*`)
5. Generate 600 events for a task → DB shows ≤500, no OOM on `GET /task/{id}`

**T1:**
6. Check Sentry dashboard after intentional agent exception → error appears with context
7. Submit 9-char description → HTTP 422; 2001-char → HTTP 422; 10-char → accepted
8. Complete a task → `tasks.llm_input_tokens` + `llm_output_tokens` populated in DB
9. `GET /v1/dashboard?page=2&page_size=5` → correct pagination response with `total` field

**T2:**
10. Force a JS error in `TaskDetailClient` → error boundary shows fallback, not blank page
11. Every HTTP response has `X-Request-ID` header
12. Save a GitHub token → verify DB value is Fernet-encrypted ciphertext, not raw token
