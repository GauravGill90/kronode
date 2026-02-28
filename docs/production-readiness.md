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

### 9. LLM Billing Model + Cost Tracking

**Model: single platform key, all orgs on one plan.**
Kronode holds one `ANTHROPIC_API_KEY`. All customer orgs share it. Kronode absorbs the
Anthropic bill and recovers cost through subscription pricing. No BYOK.

This means two things are required:

#### 9a. Per-task token tracking (visibility)
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

#### 9b. Monthly token budget per org (cost protection)
Without a hard cap, one org running complex tasks all day can cause unexpected Anthropic
spend. The T0-2 task rate limit (10/min, 100/day) provides some protection, but a monthly
token budget is the real guardrail.

**Fix — `backend/app/models/org.py`:** add `monthly_token_budget: int` (default 0 = unlimited)

**Fix — `backend/app/pipeline/pipeline.py`** (before starting agents):
```python
# Check monthly token spend for this org
if config and config.monthly_token_budget > 0:
    month_start = datetime.now(utc).replace(day=1, hour=0, minute=0, second=0)
    result = await db.execute(
        select(func.sum(Task.llm_input_tokens + Task.llm_output_tokens))
        .where(Task.org_id == task.org_id, Task.created_at >= month_start)
    )
    used = result.scalar() or 0
    if used >= config.monthly_token_budget:
        # Fail fast before spending a single token
        raise Exception("Monthly token budget exceeded. Contact support to increase your limit.")
```

Set budget via a future admin panel or directly in DB. Default 0 = no cap (fine for MVP,
set real limits once you know typical per-org spend from the tracking data).

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

---

## T3 — Bot Identity (agent acts as itself, not as the human user)

> **Why this matters:** Currently Kronode commits and opens PRs as the *human user's* PAT,
> and comments on Jira as the *human user's* API token. This is wrong for a product —
> the agent should have its own identity (`kronode[bot]`, not `alice@company.com`).
> It also means one employee leaving can silently break all automation.

---

### 16. GitHub App — `kronode[bot]` identity

**Current:** stores `github_access_token` (personal access token) per org.
All commits/PRs show as the human.

**Target:** GitHub App installation tokens. Commits and PRs appear as `kronode[bot]`.

#### Setup (one-time, by Kronode team)
1. Create a **GitHub App** at github.com/settings/apps
2. Set permissions: `Contents: Read & Write`, `Pull Requests: Read & Write`, `Metadata: Read`
3. Generate a private key (PEM) — store as `GITHUB_APP_PRIVATE_KEY` env var
4. Note the `GITHUB_APP_ID` (numeric)

#### Per-customer install flow
1. Onboarding step: "Install Kronode on GitHub" button → links to
   `https://github.com/apps/kronode/installations/new`
2. GitHub redirects back to `GET /v1/oauth/github/callback?installation_id=...&setup_action=install`
3. Backend stores `installation_id` in `onboarding_config.github_installation_id`

#### Token generation (replaces PAT)
```python
# backend/app/core/github_app.py  (new file)
import jwt, time
import httpx

async def get_installation_token(installation_id: int) -> str:
    """Generate a short-lived installation access token (valid 1hr)."""
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": settings.github_app_id}
    app_jwt = jwt.encode(payload, settings.github_app_private_key, algorithm="RS256")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
    return resp.json()["token"]
```

`github_service.py` calls `get_installation_token(cfg.github_installation_id)` instead of
reading `cfg.github_access_token`. Token is generated fresh per pipeline run (not stored).

**New env vars:**
```
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."
```

**Migration:** add `github_installation_id` column to `onboarding_config`, deprecate
`github_access_token` (keep for backwards compat until all orgs migrated).

---

### 17. Atlassian OAuth 2.0 — Jira + Confluence bot identity

**Current:** stores `jira_email` + `jira_api_token` (personal). Actions appear as the human.

**Target:** Atlassian OAuth 2.0 (3-legged). Actions appear as the **Kronode OAuth app**.

#### Setup (one-time, by Kronode team)
1. Create an **OAuth 2.0 (3LO) app** at developer.atlassian.com
2. Add scopes: `read:jira-work`, `write:jira-work`, `read:confluence-content.all`,
   `write:confluence-content`
3. Set redirect URI: `{BACKEND_URL}/v1/oauth/jira/callback`
4. Note `JIRA_CLIENT_ID` and `JIRA_CLIENT_SECRET`

#### Per-customer OAuth flow
1. Onboarding step: "Connect to Jira" button → redirect to:
   ```
   https://auth.atlassian.com/authorize
     ?audience=api.atlassian.com
     &client_id={JIRA_CLIENT_ID}
     &scope=read:jira-work write:jira-work offline_access
     &redirect_uri={BACKEND_URL}/v1/oauth/jira/callback
     &state={org_id}
     &response_type=code
     &prompt=consent
   ```
2. Callback handler exchanges code for tokens + fetches `cloud_id`:
```python
# backend/app/api/v1/oauth.py  (new file)
@router.get("/oauth/jira/callback")
async def jira_oauth_callback(code: str, state: str, db=Depends(get_db)):
    # 1. Exchange code for access_token + refresh_token
    token_resp = await httpx.post("https://auth.atlassian.com/oauth/token", json={
        "grant_type": "authorization_code",
        "client_id": settings.jira_client_id,
        "client_secret": settings.jira_client_secret,
        "code": code,
        "redirect_uri": f"{settings.backend_url}/v1/oauth/jira/callback",
    })
    tokens = token_resp.json()

    # 2. Fetch accessible resources to get cloud_id (Jira site identifier)
    resources_resp = await httpx.get(
        "https://api.atlassian.com/oauth/token/accessible-resources",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    cloud_id = resources_resp.json()[0]["id"]

    # 3. Store tokens + cloud_id against org (state = org_id)
    cfg = await db.get(OnboardingConfig, int(state))
    cfg.jira_access_token = tokens["access_token"]
    cfg.jira_refresh_token = tokens["refresh_token"]
    cfg.jira_cloud_id = cloud_id
    cfg.jira_token_expires_at = datetime.now(utc) + timedelta(seconds=tokens["expires_in"])
    await db.commit()
    return RedirectResponse("/onboarding/5")  # back to onboarding
```

3. `jira_service.py` calls a `_get_valid_token(cfg)` helper that refreshes if expired:
```python
async def _get_valid_token(cfg: OnboardingConfig) -> str:
    if cfg.jira_token_expires_at > datetime.now(utc) + timedelta(minutes=5):
        return cfg.jira_access_token
    # Refresh
    resp = await httpx.post("https://auth.atlassian.com/oauth/token", json={
        "grant_type": "refresh_token",
        "client_id": settings.jira_client_id,
        "client_secret": settings.jira_client_secret,
        "refresh_token": cfg.jira_refresh_token,
    })
    tokens = resp.json()
    # Update DB + return new access_token
```

All Jira/Confluence API calls switch from Basic Auth to `Authorization: Bearer {token}` and
base URL changes from `{workspace_url}/rest/api/3/...` to
`https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/...`.

**New migration:** add `jira_access_token`, `jira_refresh_token`, `jira_cloud_id`,
`jira_token_expires_at` columns; keep `jira_email` + `jira_api_token` for backwards compat.

---

### 18. Slack — already a bot ✓

No change needed. The existing `xoxb-` bot token is already a Slack Bot User.
Kronode already appears as a named bot in Slack channels.

---

### T3 Files to Create/Modify

| File | Change |
|------|--------|
| `backend/app/core/github_app.py` | New — JWT generation + installation token fetch |
| `backend/app/api/v1/oauth.py` | New — `/oauth/github/callback` + `/oauth/jira/callback` |
| `backend/app/api/v1/router.py` | Include `oauth` router |
| `backend/app/services/github_service.py` | Use `get_installation_token()` instead of PAT |
| `backend/app/services/jira_service.py` | Use OAuth Bearer token + `_get_valid_token()` refresh helper |
| `backend/app/models/org.py` | Add `github_installation_id`, `jira_access_token`, `jira_refresh_token`, `jira_cloud_id`, `jira_token_expires_at` |
| `backend/app/core/config.py` | Add `github_app_id`, `github_app_private_key` |
| `backend/alembic/versions/010_bot_identity.py` | New migration for all new columns |
| `.env.example` | Add `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` |
| `frontend/components/onboarding/SetupCard.tsx` | Replace "paste token" steps with OAuth buttons for GitHub + Jira |
| `frontend/lib/api.ts` | Add `connectGitHub()`, `connectJira()` redirect helpers |

**Dependencies to add:**
- `PyJWT` (for GitHub App JWT signing) — `uv add pyjwt[crypto]`

---

### T3 Verification

1. Install Kronode GitHub App on a test repo → `github_installation_id` stored in DB, no PAT
2. Submit a task → PR opened → PR author shows as `kronode[bot]`, not human user
3. Connect Jira via OAuth → `jira_access_token` stored (encrypted), `jira_email` null
4. Expire the Jira token manually → next pipeline run auto-refreshes + task succeeds
5. Revoke the Jira OAuth app in Atlassian settings → next run returns 401 gracefully
6. Disconnect GitHub App from repo → pipeline fails with clear "app not installed" error

---

---

## T4 — Organisational Memory (10th ticket better than 1st)

> **The core problem:** LLMs are stateless. Every task starts from zero. Without explicit
> memory infrastructure, the agent makes the same mistakes on ticket 50 that it made on
> ticket 1 — the same file it always forgets to update, the same pattern the team always
> asks to change in review, the same architectural decision it re-debates every time.
>
> The solution is **not** a longer context window. It's structured, selective retrieval:
> store learnings outside the model, pull in only what's relevant to the current task,
> inject it at the right point in the pipeline. The LLM stays stateless; the system has memory.

---

### The Memory Architecture

```
After each task:
  memory_agent extracts → structured records → memory_records table (per org)

Before each task:
  context_builder retrieves → relevant records → injected into agent prompts

Weekly:
  consolidation beat task → merges/summarises stale records → reduces noise
```

---

### 19. Memory Record Schema (implement the stub `memory_agent`)

The `memory_records` table already exists. The agent stub runs but stores nothing.
It needs to actually extract and write structured learnings.

**Record types to store:**

| `record_type` | What it captures | When written |
|--------------|-----------------|--------------|
| `convention` | How this team writes code (naming, patterns, file structure) | After first context_builder run; refreshed weekly |
| `pitfall` | What broke or got rejected in PR review | After `changes_requested` detected by PR poll |
| `tech_decision` | Why a certain approach was chosen (captured from PR description) | After PR merges |
| `file_coupling` | Files that always change together | After coder_agent writes files |
| `pr_feedback` | Recurring reviewer comments (e.g., "always add tests for X") | After 2+ pitfalls with same pattern |
| `task_pattern` | Successful approach for a class of task | After PR merges cleanly (no revision) |

**Implement `memory_agent.run()`:**
```python
async def run(self, context: dict) -> dict:
    coder_result = context.get("coder_agent", {})
    files_written = [f["path"] for f in coder_result.get("files", [])]
    pr_description = coder_result.get("pr_description", "")
    task_description = context["description"]

    records_to_write = []

    # 1. File coupling — which files changed together this task
    if len(files_written) > 1:
        records_to_write.append({
            "record_type": "file_coupling",
            "content": {
                "files": files_written,
                "task_type": context.get("routing", {}).get("complexity"),
                "description_hint": task_description[:100],
            },
            "file_paths": files_written,
        })

    # 2. Tech decision — extract from PR description via Haiku
    if pr_description:
        decision = await _extract_tech_decision(task_description, pr_description)
        if decision:
            records_to_write.append({
                "record_type": "tech_decision",
                "content": decision,
                "file_paths": files_written,
            })

    # Batch write to memory_records
    async with AsyncSessionLocal() as db:
        for rec in records_to_write:
            db.add(MemoryRecord(
                org_id=context["org_id"],
                task_id=context["task_id"],
                record_type=rec["record_type"],
                content=rec["content"],
                file_paths=rec.get("file_paths", []),
                source=coder_result.get("pr_url", ""),
            ))
        await db.commit()
```

---

### 20. Selective Memory Injection (retrieval strategy)

The context window problem: you cannot inject all memory. You inject only what's relevant
to the current task. Relevance is determined before the LLM runs — not by the LLM.

**Two retrieval signals:**

1. **File-path overlap** — after planner_agent produces `files_affected`, query records
   tagged with those file paths. Catches pitfalls and coupling for the exact files being touched.

2. **Task-type match** — query records where the task complexity/category matches.
   Catches conventions and tech decisions that apply broadly.

**Inject at two points in the pipeline:**

#### Into `context_builder` (before file fetching)
```python
# Retrieve conventions + pitfalls for this org — always inject
records = await db.execute(
    select(MemoryRecord)
    .where(
        MemoryRecord.org_id == org_id,
        MemoryRecord.record_type.in_(["convention", "pitfall", "pr_feedback"]),
    )
    .order_by(MemoryRecord.relevance_score.desc())
    .limit(15)  # hard cap — conventions are dense but short
)
context["memory_conventions"] = [r.content for r in records]
```

#### Into `planner_agent` (after files_affected are known)
```python
# Retrieve file-specific pitfalls and coupling
relevant_files = [f["path"] for f in context_bundle.get("relevant_files", [])]
records = await db.execute(
    select(MemoryRecord)
    .where(
        MemoryRecord.org_id == org_id,
        MemoryRecord.record_type.in_(["pitfall", "file_coupling", "tech_decision"]),
        MemoryRecord.file_paths.overlap(relevant_files),  # PostgreSQL array overlap
    )
    .order_by(MemoryRecord.relevance_score.desc())
    .limit(10)
)
context["memory_pitfalls"] = [r.content for r in records]
```

Inject into each agent's system prompt as a `--- Organisational Memory ---` block:
```python
memory_block = ""
if context.get("memory_pitfalls"):
    memory_block += "\n--- Known pitfalls for these files ---\n"
    memory_block += "\n".join(f"• {p['summary']}" for p in context["memory_pitfalls"][:5])
if context.get("memory_conventions"):
    memory_block += "\n--- Team conventions ---\n"
    memory_block += "\n".join(f"• {c['summary']}" for c in context["memory_conventions"][:5])
```

**Hard limits to prevent context bloat:**
- Max 15 memory records injected per agent
- Each record's `summary` field is pre-truncated to 120 chars when written
- Full detail stored in `content` JSONB — only `summary` injected into prompts

---

### 21. Relevance Scoring + Reinforcement

A pitfall seen once is a hint. A pitfall seen five times is a law.

**Add `relevance_score` and `seen_count` columns to `memory_records`:**
```python
relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
seen_count: Mapped[int] = mapped_column(Integer, default=1)
```

**In `memory_agent`** — before writing a new record, check if a similar one exists:
```python
# Check for duplicate pitfall (same file paths + similar summary)
existing = await _find_similar_record(org_id, record_type, file_paths, summary)
if existing:
    existing.seen_count += 1
    existing.relevance_score = min(10.0, existing.relevance_score * 1.3)  # compound
    # Don't write a duplicate — reinforce the existing one
else:
    # Write new record with base score 1.0
```

Result: after 3 PRs where a reviewer asks "add tests for this module", the pitfall record
has `relevance_score ≈ 2.2` and gets injected first. After 10 PRs it's `≈ 13.8` — a hard
convention the agent treats as a rule.

**After a PR merges cleanly (no revision):** boost all memory records that were injected
for that task by `+0.1` — positive reinforcement for memories that led to a good outcome.

---

### 22. Memory Consolidation (weekly beat task)

Without pruning, memory_records grows without bound and fills with stale/contradictory entries.

**Add `consolidate_memory` Celery beat task (runs Sunday 02:00 UTC):**

```python
async def _consolidate_memory():
    # 1. Find duplicate conventions (same record_type, file_paths overlap > 80%)
    #    → Haiku merges them into a single summary, deletes originals
    # 2. Decay stale records: relevance_score *= 0.95 for records not seen in 30 days
    # 3. Archive records with relevance_score < 0.2 (move to archived=True, exclude from retrieval)
    # 4. Promote: if seen_count >= 5 for a pitfall → upgrade to pr_feedback (stronger signal)
```

This keeps the active memory lean and high-signal. Old patterns that stopped mattering
decay away. Patterns that keep showing up get stronger.

**Beat schedule:**
```python
"consolidate-memory": {
    "task": "consolidate_memory",
    "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 02:00 UTC
},
```

---

### 23. Organisational Knowledge Ingestion (Confluence)

> **The insight:** A developer with tenure isn't just technically skilled — they carry
> business context that took years to accumulate. They know *why* the auth system works the
> way it does, that a certain module is being deprecated in Q3, that "subscriber" in this
> domain means something very specific. All of that lives in Confluence. Feeding it to the
> agent means it stops coding like a contractor on day one and starts coding like someone
> who's been in the room for the last two years.

---

#### Two memory layers

```
Layer 1 — Technical memory (sections 19–22)
  Source: code, PR reviews, merged PRs
  Answers: how does this team write code?

Layer 2 — Organisational memory (this section)
  Source: Confluence pages
  Answers: why do we do it this way? what's the business context?
           what decisions have already been made? what's coming next?
```

When the agent plans a PR, it draws from both. Layer 1 prevents past technical mistakes.
Layer 2 prevents ignoring business constraints the agent has no other way to know.

---

#### What Confluence pages to ingest

Not all pages are useful. The agent cares about:

| Page type | Example | Why useful |
|-----------|---------|-----------|
| Architecture Decision Records (ADRs) | "Why we chose Celery over Sidekiq" | Stops re-debating settled decisions |
| Team conventions | "Code review checklist", "PR size guidelines" | Enforces team norms automatically |
| Domain glossary | "What is a Subscriber?", "Billing concepts" | Grounds the agent in business language |
| Runbooks | "Deployment process", "On-call escalation" | Relevant when task touches infra/ops |
| Product context | "Q2 roadmap", "Feature flags in use" | Prevents building against planned deprecations |
| API contracts | "External API versioning policy" | Prevents breaking changes |

Pages to **skip**: meeting notes, personal pages, old project post-mortems (too noisy).
Use Confluence page labels to tag which spaces/labels to include — set during onboarding.

---

#### 23a. Confluence sync (daily Celery beat task)

```python
# backend/app/pipeline/task_queue.py
@celery_app.task(name="sync_confluence")
def sync_confluence():
    asyncio.run(_sync_confluence())

async def _sync_confluence():
    # For each org with Confluence configured:
    async with AsyncSessionLocal() as db:
        orgs = await db.execute(
            select(OnboardingConfig)
            .where(OnboardingConfig.confluence_base_url.isnot(None))
        )

    for cfg in orgs.scalars():
        pages = await _fetch_confluence_pages(cfg)
        for page in pages:
            chunks = _chunk_page(page["body"], max_tokens=400)
            for i, chunk in enumerate(chunks):
                summary = await _haiku_summarise(chunk, page["title"])
                tags = await _haiku_extract_tags(chunk, page["title"])
                # Upsert: update if page was already synced, insert if new
                await _upsert_org_knowledge(
                    org_id=cfg.org_id,
                    source_url=page["url"],
                    chunk_index=i,
                    content={"title": page["title"], "body": chunk},
                    summary=summary,       # ≤120 chars — injected into prompts
                    tags=tags,             # ["auth", "billing", "conventions", ...]
                    synced_at=now,
                )
```

**`_chunk_page`** — splits raw Confluence HTML/markdown into ~400-token chunks at
paragraph/heading boundaries. Never mid-sentence.

**`_haiku_summarise`** — single Haiku call per chunk:
```
System: "Extract the single most important fact from this documentation chunk in ≤120 chars.
         Focus on decisions, constraints, and conventions — not descriptions."
User: "{page_title}\n\n{chunk}"
```

**`_haiku_extract_tags`** — extract 3–5 domain tags per chunk:
```
System: "Return a JSON array of 3-5 short tags describing the domain area of this doc chunk.
         Examples: auth, billing, deployment, api-versioning, react-conventions, data-model"
User: "{chunk}"
```

Beat schedule: `"sync-confluence": {"task": "sync_confluence", "schedule": crontab(hour=3, minute=0)}`
(daily at 03:00 UTC — after consolidation, before the work day)

---

#### 23b. Retrieval — matching org knowledge to the current task

Before the planner runs, extract domain tags from the task description (Haiku, fast):

```python
# In context_builder or early in pipeline
task_tags = await _haiku_extract_tags(context["description"], "")
# e.g., task "update the login flow" → tags: ["auth", "frontend", "clerk"]

org_knowledge = await db.execute(
    select(MemoryRecord)
    .where(
        MemoryRecord.org_id == org_id,
        MemoryRecord.record_type == "org_knowledge",
        MemoryRecord.archived == False,
        MemoryRecord.tags.overlap(task_tags),  # PostgreSQL array overlap
    )
    .order_by(MemoryRecord.relevance_score.desc())
    .limit(8)  # hard cap — org knowledge chunks can be denser than conventions
)
context["org_knowledge"] = [r.summary for r in org_knowledge.scalars()]
```

---

#### 23c. Injection — into planner and coder prompts

```python
# Added to planner_agent and coder_agent system prompt construction
if context.get("org_knowledge"):
    org_block = "\n--- Company & Product Context ---\n"
    org_block += "\n".join(f"• {fact}" for fact in context["org_knowledge"])
    # Injected between profile_injection and the agent's own SYSTEM_PROMPT
    # Sits between "who you are" and "what to do" — agent reads it as background truth
```

**What this looks like in practice:**

The planner's effective prompt now includes:
```
--- Company & Product Context ---
• Auth uses Clerk — never implement custom session handling (ADR-004)
• "Subscriber" = user on a paid plan tier; Guest = free tier (domain glossary)
• Payment module being migrated to Stripe in Q3 — avoid adding to legacy billing code
• All API changes must increment version in /v1/ prefix — see API versioning policy
• Tests required for any file under src/services/ — team convention
```

The agent reads this before planning. It will not touch the legacy billing code. It will
write the right tests. It will use the right terminology in PR descriptions.

---

#### 23d. Schema additions for org knowledge

Add to `memory_records`:
```python
tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
source_url: Mapped[str | None] = mapped_column(Text)       # Confluence page URL
chunk_index: Mapped[int] = mapped_column(Integer, default=0)
synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Also add to `onboarding_config`:
```python
confluence_base_url: Mapped[str | None] = mapped_column(Text)
confluence_space_keys: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
confluence_include_labels: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
# e.g., space_keys=["ENG", "ARCH"], include_labels=["agent-context", "adr"]
```

**Onboarding step:** "Which Confluence spaces should your agent learn from?" (multi-select)
with optional label filter: "Only pages tagged with: [agent-context]"

---

### 24. Schema changes needed (full T4 summary)

**`memory_records` table — add all T4 columns in one migration:**
```python
file_paths: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
summary: Mapped[str] = mapped_column(Text, default="")
relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
seen_count: Mapped[int] = mapped_column(Integer, default=1)
archived: Mapped[bool] = mapped_column(Boolean, default=False)
source_url: Mapped[str | None] = mapped_column(Text)
chunk_index: Mapped[int] = mapped_column(Integer, default=0)
synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

**`onboarding_config` table — add Confluence config:**
```python
confluence_base_url: Mapped[str | None] = mapped_column(Text)
confluence_space_keys: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
confluence_include_labels: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
```

**New migration:** `backend/alembic/versions/011_memory_fields.py`

---

### T4 Files to Create/Modify

| File | Change |
|------|--------|
| `backend/app/agents/memory_agent.py` | Implement — extract and write technical records |
| `backend/app/agents/context_builder.py` | Retrieve + inject conventions, pitfalls, org knowledge |
| `backend/app/agents/planner_agent.py` | Inject file-specific pitfalls + org knowledge block |
| `backend/app/agents/coder_agent.py` | Inject org knowledge block |
| `backend/app/pipeline/task_queue.py` | Add `consolidate_memory` + `sync_confluence` beat tasks |
| `backend/app/celery_app.py` | Add weekly consolidation + daily Confluence sync beats |
| `backend/app/models/memory.py` | Add all new columns (see schema above) |
| `backend/app/models/org.py` | Add `confluence_*` config columns |
| `backend/app/api/v1/onboarding.py` | Add Confluence config endpoint |
| `backend/app/schemas/onboarding.py` | Add `ConfluencePayload` schema |
| `backend/alembic/versions/011_memory_fields.py` | New migration — all T4 columns |

---

### T4 Verification

**Technical memory (19–22):**
1. Submit task touching `auth/` → complete → `memory_records` has new `file_coupling` record
2. Get PR reviewed with "missing tests" → `pitfall` record written with `file_paths`
3. Submit second task touching same files → planner prompt contains the pitfall → PR passes review first time
4. Review comment repeated 5× → `seen_count = 5`, `relevance_score ≈ 3.7` → always injected first
5. Run consolidation → stale records decayed, archived records excluded from retrieval

**Organisational knowledge (23):**
6. Connect Confluence space "ENG" → daily sync runs → `memory_records` has `org_knowledge` records with tags
7. Submit task "update the login screen" → planner prompt includes Confluence fact about Clerk ADR
8. Submit task "add a payment method" → planner prompt includes "avoid legacy billing code in Q3" warning
9. Update a Confluence page → next daily sync updates the chunk, new summary injected
10. Disconnect Confluence → `org_knowledge` records archived, not injected (no silent failures)

**Token budget check:**
11. Verify: conventions (5 × 120 chars) + pitfalls (5 × 120 chars) + org knowledge (8 × 120 chars) ≈ 2,160 chars ≈ 540 tokens added per agent — well within budget

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

**T3:**
13. PR author is `kronode[bot]`, not a human user
14. Jira ticket transitions appear as the OAuth app, not `alice@company.com`
15. Removing a human from the org doesn't break any automation
