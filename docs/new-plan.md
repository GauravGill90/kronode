# Plan: Kronode — Enterprise Organizational Memory Platform

## Context

Kronode ingests an engineering team's PR history, docs, tickets, and tribal knowledge, then serves that organizational memory to any AI coding tool, any team workflow, or any developer — in real time. The core engine works: conventions extract from PRs, docs ingest from Confluence, MCP tools serve ranked context. Now it needs to be a product that a Fortune 500 VP of Engineering or a billion-dollar VC would take seriously — pluggable data sources, universal delivery, enterprise security, and compliance.

**The vision**: Kronode is the organizational memory layer for software teams. Data flows IN from any source (git, docs, tickets, incidents, Slack). Knowledge flows OUT to any surface (AI coding tools, Slack, Jira, PR comments, dashboards, APIs). The memory compounds over time — every PR review, every failure, every resolved incident makes the system smarter.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INFLOW CONNECTORS                            │
│  (pluggable data sources — each a Python class implementing ABC)    │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤
│  GitHub  │Bitbucket │  GitLab  │Confluence│  Notion  │ Google Drive │
│  PRs+Code│PRs+Code  │PRs+Code  │  Pages   │  Pages   │   Docs       │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────────┤
│   Jira   │  Linear  │ GH Issues│  Slack   │PagerDuty │  Webhooks    │
│ Tickets  │ Tickets  │  Issues  │ Threads  │Incidents │  Generic     │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE ENGINE                                │
│                                                                     │
│  Convention Extraction ──→ Ranked Conventions (validated over time)  │
│  Doc Ingestion ──────────→ Chunked + Embedded Documentation         │
│  Reviewer Pattern Mining → Per-Reviewer Preference Models           │
│  Failure Memory ─────────→ What went wrong + How it was fixed       │
│  Companion Analysis ─────→ Files that change together               │
│  Task Similarity ────────→ Learn from analogous past tasks          │
│                                                                     │
│  All data org-isolated (row-level security on org_id)               │
│  Secrets encrypted at rest (Fernet/AES-256)                         │
│  Full audit trail on every access                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      OUTFLOW CONNECTORS                             │
│  (every surface where developers already work)                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤
│  MCP     │  Slack   │  Jira    │  GitHub  │  REST    │  VS Code     │
│  Server  │  Bot     │  Panel   │  App     │  API     │  Extension   │
│ (14 tools)│ @kronode │ Context  │PR Comment│ Generic  │  Sidebar     │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────────┤
│ Claude   │ Cursor   │ Windsurf │ Copilot  │ Cline    │ Continue     │
│ Code     │          │          │          │          │              │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────────┤
│ Amazon Q │ Zed      │ Tabnine  │ Cody     │ Devin    │ Replit       │
│ JetBrains│          │          │          │          │              │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘
```

---

## Part A: MCP Server — Universal AI Tool Integration

### A.1 Transport Strategy

MCP defines two transports. Kronode must support both:

| Transport | Who needs it | How it works |
|-----------|-------------|--------------|
| **stdio** | Claude Code, Cursor, Windsurf, Cline, Continue, Amazon Q, Zed, Tabnine, Cody | Server runs as child process on dev machine. Zero network config. |
| **Streamable HTTP** | All of above (remote mode) + Replit, Devin, GitHub Copilot, JetBrains AI | Server runs as hosted HTTP service. Team-wide access, centralized. |

**Current state**: stdio only (`backend/app/mcp/main.py` line 67: `await mcp.run_stdio_async()`)

**Implementation**:

**Modify** `backend/app/mcp/main.py`:
- Add `--transport` flag: `stdio` (default) or `http`
- When `http`: start with `mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)` or mount on FastAPI
- Auth for HTTP: validate `Authorization: Bearer kron_xxx` header per request, resolve org

**Create** `backend/app/api/v1/mcp.py`:
- Mount MCP SSE/streamable-http endpoint at `/mcp/` on the main FastAPI app
- Per-request auth: extract API key → resolve org → configure MCP instance
- This shares deployment with the main backend (no separate service)

### A.2 Per-Agent Configuration

Every agent uses a different config file and sometimes different JSON keys. Kronode must provide exact, copy-paste-ready configs.

**Agent config matrix** (researched from official docs, March 2026):

| Agent | Config File | Root Key | Transport | Notes |
|-------|-----------|----------|-----------|-------|
| Claude Code | `.mcp.json` or `claude mcp add` | `mcpServers` | stdio + http | Scopes: local/project/user |
| Cursor | `.cursor/mcp.json` | `mcpServers` | stdio + SSE + streamable HTTP | Agent mode only |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | stdio + streamable HTTP | 100-tool limit. `${env:VAR}` syntax |
| GitHub Copilot (VS Code) | `.vscode/mcp.json` | **`servers`** (NOT mcpServers) | stdio + http (tries streamable, falls back SSE) | Agent mode only |
| Cline | `cline_mcp_settings.json` (via UI) | `mcpServers` | stdio + SSE | No streamable HTTP yet |
| Continue | `.continue/mcpServers/*.json` | `mcpServers` | stdio + SSE + streamable HTTP | Supports YAML too |
| Amazon Q | `~/.aws/amazonq/mcp.json` | `mcpServers` | stdio + http | Admin whitelisting via IAM |
| JetBrains AI | `mcp.json` or IDE Settings | `mcpServers` | streamable HTTP + SSE + stdio (Junie only) | Acts as both client AND server |
| Zed | `settings.json` | **`context_servers`** (NOT mcpServers) | stdio only (mcp-remote for http) | No resources support |
| Tabnine | `.tabnine/mcp_servers.json` | `mcpServers` | stdio + SSE + http | Admin allow-lists |
| Sourcegraph Cody | VS Code settings / `.vscode/mcp.json` | `servers` | stdio + http | OAuth Dynamic Client Registration |
| Replit | UI only (Integrations pane) | N/A | Remote HTTP only | Cloud agent, no local |
| Devin | UI/API (cognition.ai) | N/A | Streamable HTTP only | Cloud agent, no local |
| Aider | **NO MCP SUPPORT** | N/A | N/A | Only agent without MCP. REST wrapper needed. |

### A.3 Setup CLI / Config Generator

**Create** `backend/app/mcp/setup.py` — CLI tool that generates configs for each agent:

```bash
kronode setup claude-code    # Outputs claude mcp add command
kronode setup cursor         # Outputs .cursor/mcp.json snippet
kronode setup copilot        # Outputs .vscode/mcp.json snippet (note: "servers" not "mcpServers")
kronode setup windsurf       # Outputs mcp_config.json snippet
kronode setup zed            # Outputs settings.json snippet (note: "context_servers")
kronode setup <agent>        # Any supported agent
kronode setup --all          # Outputs configs for all agents
kronode setup --remote       # Uses HTTP transport with hosted URL
```

Accepts `--token kron_xxx` and `--url https://api.kronode.dev` flags.

### A.4 REST API for Non-MCP Clients

For Aider (no MCP) and any future tool that doesn't support MCP:

**Create** `backend/app/api/v1/context.py`:
- `POST /v1/context` — equivalent to MCP `get_context` tool
- `POST /v1/context/doc` — equivalent to MCP `get_doc` tool
- `POST /v1/context/companions` — equivalent to MCP `get_file_companions`
- `POST /v1/context/completeness` — equivalent to MCP `check_completeness`
- `POST /v1/context/reviewer` — equivalent to MCP `get_reviewer_guidance`
- Auth: same API key (`Authorization: Bearer kron_xxx`)

This also enables custom integrations (CI/CD pipelines, internal tools, webhooks).

### A.5 Onboarding MCP Setup Page

**Create** `frontend/components/onboarding/StepMCPSetup.tsx`:
- Auto-generates API key on step entry (calls `POST /v1/api-keys`)
- Detects or asks which AI tools the team uses
- Shows copy-paste config for each selected tool (using configs from A.2)
- "Test connection" button: calls `get_context` with sample task, shows response
- Shows both stdio (local) and HTTP (remote/team) options

---

## Part B: Outflow Connectors — Where Developers Already Work

### B.1 Slack Bot

Developers should be able to ask Kronode questions directly in Slack:
- `@kronode what are the conventions for auth-service?`
- `@kronode critique this ticket: DEECO-1234`
- `@kronode what files usually change with useCertExchange.ts?`
- `@kronode what would suhil say about this PR?`

**Implementation**:

**Create** `backend/app/integrations/slack_bot.py`:
- Use `slack-bolt` (Python) — Slack's official framework, already fits our Python backend
- **Event handlers**:
  - `@app.event("app_mention")` — parse question, call appropriate context provider, respond with Block Kit formatted answer
  - `@app.command("/kronode")` — slash command for quick queries
  - `@app.action("...")` — handle button clicks (e.g., "Show more", "Suppress convention")
- **Natural language routing**: Use cheap LLM to classify intent → route to correct context provider
- **Thread support**: Conversations in threads maintain context

**Create** `backend/app/integrations/slack_oauth.py`:
- OAuth v2 installation flow (replaces manual bot token entry)
- Stores `bot_token`, `team_id`, maps to `org_id`
- Supports Enterprise Grid (`enterprise_id` handling)

**Modify** `backend/app/main.py` — mount Slack event receiver at `/integrations/slack/events`

**Modify** onboarding: replace manual bot token entry with "Add to Slack" OAuth button

### B.2 Jira Forge App — Context Panel

When a developer views a Jira ticket, a "Kronode Context" panel on the right side shows relevant conventions, pitfalls, similar past tasks, and reviewer guidance for that ticket — before they start coding.

**Implementation**:

**Create** `integrations/jira-forge/` (new directory, separate from backend):
- Atlassian Forge app (Node.js + React, required by Forge)
- **Module**: `jira:issueContext` — adds collapsible panel to issue view
- **On render**: calls Kronode REST API (`POST /v1/context`) with ticket title + description
- **Displays**: ranked conventions, relevant docs, predicted reviewer, similar past tasks
- **Auth**: Forge app calls Kronode API with org's API key (stored as Forge app property)

**Why Forge, not Connect**: Atlassian deprecated Connect apps (September 2025, EOL Q4 2026). Forge runs on Atlassian infra, gets lighter security review for Marketplace.

**Marketplace listing**: enables discovery by Jira teams. Requirements: security questionnaire, KYC/KYB. 2-4 week review.

### B.3 GitHub App — PR Context Comments

When a PR is opened, Kronode automatically posts a comment with relevant conventions, missed companion files, and reviewer guidance.

**Implementation**:

**Create** `backend/app/integrations/github_app.py`:
- **Webhook handler**: receives `pull_request.opened` and `pull_request.synchronize` events
- **On PR open**:
  1. Extract changed files from PR diff
  2. Call context providers (conventions, companions, reviewer guidance)
  3. Post formatted comment: "Kronode found these relevant conventions for your PR..."
  4. Optionally create a Check Run with inline annotations
- **Auth**: GitHub App JWT (RS256 private key) → installation access token
- **Inflow too**: subscribe to `pull_request_review` events to learn reviewer patterns

**Create** `backend/app/integrations/bitbucket_app.py`:
- Equivalent for Bitbucket (webhook-based, no app marketplace yet)

**Modify** `backend/app/main.py` — mount webhook receiver at `/integrations/github/webhooks`

### B.4 REST API (Generic Outflow)

Already covered in A.4. The REST API serves as the universal outflow connector for:
- CI/CD pipelines (pre-commit hooks, PR checks)
- Custom internal tools
- Third-party integrations via Zapier/Make.com
- CLI tools / scripts
- Any future surface we haven't thought of yet

---

## Part C: Inflow Connectors — Pluggable Data Sources

### C.1 Inflow Connector Architecture

Every data source implements the same interface. Adding a new source = one Python file + one registry entry.

**Three connector types:**

#### Git Providers (code + PR history)

**Create** `backend/app/services/git_providers/base.py`:
```python
class GitProvider(ABC):
    async def get_repo_tree(self, repo_url, token) -> list[str]
    async def get_file_content(self, repo_url, path, token) -> str | None
    async def create_pull_request(self, repo_url, branch, files, ...) -> str
    async def add_files_to_branch(self, repo_url, branch, files, ...) -> bool
    async def get_pr_status(self, pr_url, token) -> dict
    async def fetch_merged_prs(self, repo_url, token, count) -> list[dict]
    async def validate_token(self, token, repo_url) -> dict
```

**Create** `backend/app/services/git_providers/__init__.py` — factory + registry
**Create** `backend/app/services/git_providers/github_provider.py` — wraps existing `github_service.py`
**Create** `backend/app/services/git_providers/bitbucket_provider.py` — wraps existing `bitbucket_service.py`
**Create** `backend/app/services/git_providers/gitlab_provider.py` — GitLab REST API v4

**Modify** all 10+ files with hardcoded `if repo_provider == "bitbucket"` dispatch:
- `backend/app/pipeline/self_onboarding.py`
- `backend/app/pipeline/convention_pipeline.py`
- `backend/app/agents/context_builder.py`
- `backend/app/agents/coder_agent.py`
- `backend/app/agents/tester_agent.py`
- `backend/app/agents/reviewer_agent.py`
- `backend/app/services/claude_executor.py`
- `backend/app/pipeline/task_queue.py`
- `backend/app/api/v1/onboarding.py`

#### Doc Providers (documentation)

Already abstracted (clean ABC in `doc_providers/base.py`). Add:

**Create** `backend/app/services/doc_providers/notion_provider.py` — Notion API
**Create** `backend/app/services/doc_providers/gdrive_provider.py` — Google Drive + Docs API
**Create** `backend/app/services/doc_providers/gitlab_provider.py` — GitLab repo markdown
**Modify** `backend/app/services/doc_providers/__init__.py` — register new providers

#### Issue Providers (tickets)

**Create** `backend/app/services/issue_providers/base.py`:
```python
class IssueProvider(ABC):
    async def fetch_open_issues(self, config, max_results) -> list[dict]
    async def fetch_issue_detail(self, config, issue_id) -> dict | None
    async def update_issue_status(self, config, issue_id, status, pr_url) -> bool
    async def post_comment(self, config, issue_id, comment) -> bool
    async def validate_credentials(self, config) -> dict
```

**Create** `backend/app/services/issue_providers/__init__.py` — factory + registry
**Create** `backend/app/services/issue_providers/jira_provider.py` — wraps existing `jira_service.py`
**Create** `backend/app/services/issue_providers/linear_provider.py` — GraphQL API
**Create** `backend/app/services/issue_providers/github_issues_provider.py` — REST API

### C.2 Generic Webhook Inflow

For data sources that push rather than pull (incident management, CI events, custom tools):

**Create** `backend/app/api/v1/webhooks.py`:
- `POST /v1/webhooks/ingest` — generic receiver
- HMAC signature verification per source
- Source-type routing (header `X-Kronode-Source: pagerduty`)
- Async processing via Celery (return 200 immediately)
- Idempotency key support (header `X-Kronode-Idempotency-Key`)

**Create** `backend/app/services/webhook_processors/` — processor per source type:
- `pagerduty_processor.py` — extract incident context, affected services
- `ci_processor.py` — extract build failures, test results
- `generic_processor.py` — store raw payload as memory record

### C.3 Context Provider System

Refactor the monolithic `get_context` MCP tool into composable providers:

**Create** `backend/app/services/context_providers/base.py`:
```python
class ContextProvider(ABC):
    name: str
    weight: float  # ranking weight
    async def get_context(self, org_id, task_description, files_touched) -> dict
```

**Create** providers (extract from `mcp/server.py` lines 47-178):
- `backend/app/services/context_providers/conventions_provider.py`
- `backend/app/services/context_providers/pitfalls_provider.py`
- `backend/app/services/context_providers/reviewer_patterns_provider.py`
- `backend/app/services/context_providers/past_failures_provider.py`
- `backend/app/services/context_providers/doc_chunks_provider.py`
- `backend/app/services/context_providers/coding_standards_provider.py`
- `backend/app/services/context_providers/incident_context_provider.py` (from PagerDuty webhook data)

**Create** `backend/app/services/context_providers/__init__.py` — registry, `get_all_context()` iterates all registered providers, merges results

**Modify** `backend/app/mcp/server.py` — `get_context` tool delegates to `get_all_context()`

Adding a new context source = one provider file + register. The MCP server, Slack bot, Jira panel, and REST API all call the same `get_all_context()`.

---

## Part D: Multi-Tenancy & Data Isolation

### D.1 Current State

- All tables have `org_id` column
- Queries filter by `org_id` (application-level isolation)
- No PostgreSQL Row-Level Security (RLS)
- Secrets stored as plaintext
- No per-org resource limits

### D.2 Row-Level Security

**Create** `backend/alembic/versions/018_row_level_security.py`:
- Enable RLS on all tenant tables (conventions, memory_records, doc_chunks, tasks, task_events, api_keys, onboarding_config)
- Create policies: `SELECT/INSERT/UPDATE/DELETE WHERE org_id = current_setting('app.current_org_id')::int`
- Application sets `SET app.current_org_id = ?` at the start of each request

**Modify** `backend/app/core/database.py` — add middleware/context manager that sets org_id on connection

This prevents any accidental cross-tenant data leak, even if application code has a bug. Defense in depth.

### D.3 Tiered Isolation

| Tier | Isolation | Who |
|------|-----------|-----|
| Standard | Row-Level Security (shared database) | Most customers |
| Enterprise | Schema-per-tenant | Financial services, regulated |
| Dedicated | Database-per-tenant | Defense, government (build when deal requires) |

### D.4 Embedding Isolation

Vector similarity searches must never return results from another tenant. Current implementation already filters by `org_id` before cosine comparison (safe). RLS adds a second layer.

### D.5 Data Handling Policy

**What Kronode stores**:
- Conventions (derived rules, not raw code)
- Doc chunks (from customer's own docs — Confluence, Notion, etc.)
- PR metadata (title, description, reviewer comments — not full diffs)
- Memory records (patterns, pitfalls, failures — derived, not raw)
- Embeddings (vectors, not reversible to source text)

**What Kronode does NOT store**:
- Full source code (cloned, processed, deleted)
- Raw diffs (only metadata extracted)
- Credentials (encrypted at rest, never logged, never sent to LLMs)

**Zero Raw Code Retention mode** (enterprise option):
- Process → extract knowledge → delete source
- Only derived data persists
- Contractual guarantee: "We never store your source code"

---

## Part E: Security & Compliance

### E.1 Encryption at Rest

**Create** `backend/app/core/encryption.py`:
- Fernet symmetric encryption with `ENCRYPTION_KEY` env var
- `encrypt_field()`, `decrypt_field()` helpers
- Custom SQLAlchemy `EncryptedText` column type

**Create** `backend/alembic/versions/019_encrypt_secrets.py` — migrate existing plaintext tokens

**Modify** `backend/app/models/org.py` — `EncryptedText` for `github_access_token`, `jira_api_token`, `slack_bot_token`, and all future credential fields

### E.2 Rate Limiting

**Modify** `backend/app/main.py`:
- `slowapi` with Redis backend
- Global: 100 req/min per IP
- Auth endpoints: 10 req/min
- MCP/context endpoints: 60 req/min per API key
- Per-org quotas (configurable)

### E.3 Audit Logging

**Create** `backend/app/models/audit_log.py`:
```python
class AuditLog(Base):
    id, org_id, user_id, action, resource, details (JSONB),
    ip_address, timestamp, duration_ms
```

**Create** `backend/alembic/versions/020_audit_log.py`

Log every:
- MCP tool invocation (tool name, latency, org_id)
- API endpoint call (method, path, user, org)
- Data access (conventions read, docs queried)
- Admin action (key generated, integration connected)
- Data deletion (who, what, when)

Retention: 1 year minimum (SOC 2 requirement).

### E.4 API Key Management

**Create** `backend/app/api/v1/api_keys.py`:
- `POST /v1/api-keys` — generate key, store SHA-256 hash, return plaintext once
- `GET /v1/api-keys` — list keys (name, created_at, last_used_at, masked)
- `DELETE /v1/api-keys/:id` — revoke
- `PATCH /v1/api-keys/:id` — rename, set expiry
- Key rotation: generate new key, grace period for old key

### E.5 CORS Hardening

**Modify** `backend/app/main.py`:
- Replace `allow_methods=["*"]`, `allow_headers=["*"]` with explicit lists
- Configurable via `CORS_ORIGINS` env var (already partially done)

### E.6 SOC 2 Readiness Roadmap

SOC 2 Type II is non-negotiable for enterprise sales. Timeline: 9-18 months.

| When | What | Cost |
|------|------|------|
| Month 1 | Sign up for Vanta or Drata (compliance automation) | ~$10K/yr |
| Month 1-2 | Implement technical controls (encryption, audit logs, RBAC, MFA) | Engineering time |
| Month 2-3 | Write policies (incident response, change management, data retention) | Templates from Vanta |
| Month 3-4 | SOC 2 Type I audit (point-in-time assessment) | $20-30K |
| Month 4-10 | 6-month observation period | Ongoing |
| Month 10-12 | SOC 2 Type II audit (sustained compliance) | $30-60K |

**Technical controls needed** (most already in this plan):
- [x] Encryption at rest (E.1)
- [x] TLS in transit (cloud provider handles)
- [x] Audit logging with 1-year retention (E.3)
- [x] RBAC (Clerk handles user roles)
- [ ] MFA on production systems (Clerk supports, need to enforce)
- [ ] Quarterly access reviews
- [ ] Vulnerability scanning (add to CI)
- [ ] Incident response plan (document)
- [ ] Change management (git + PR-based, already done)
- [ ] Annual penetration test ($5-25K)

### E.7 GDPR Compliance

- **Data Processing Agreement (DPA)**: template for every customer (mandatory under Article 28)
- **Right to deletion**: `DELETE /v1/org/:id/data` — purges all org data (conventions, memory, docs, audit logs)
- **Individual deletion**: anonymize author data (replace names with pseudonyms, delete mapping)
- **Subprocessor list**: Supabase, AWS/GCP, Anthropic, OpenAI (embeddings) — publish publicly
- **Breach notification**: 72-hour SLA in DPA

### E.8 Self-Hosted Option

For regulated industries that can't send data to a shared cloud:

**Create** `deploy/self-hosted/`:
- `docker-compose.yml` — all-in-one (postgres, redis, backend, worker, frontend)
- `helm/` — Kubernetes Helm chart for enterprise deployment
- `SELF-HOSTED.md` — setup guide
- Customer runs everything in their own VPC. Kronode never sees their data.
- License key validation (phone-home for license check, nothing else)

Build this when a real deal requires it (~2-3 months engineering).

---

## Part F: Cloud Deployment & Monitoring

### F.1 Fix Dockerfiles

**Modify** `backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Modify** `frontend/Dockerfile`:
```dockerfile
FROM node:20-alpine
RUN npm install -g pnpm
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY . .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
```

### F.2 Production Docker Compose

**Create** `docker-compose.prod.yml`:
- No volume mounts, no `--reload`
- Health checks on all services
- `restart: unless-stopped`
- Resource limits (memory, CPU)
- Separate Celery beat service for scheduled tasks
- Proper environment variable injection
- SSL termination via reverse proxy (Traefik/Caddy)

### F.3 Health Checks

**Modify** `backend/app/main.py`:
- `/health` — shallow (process up, returns 200)
- `/health/ready` — deep (check Postgres + Redis connections, return degraded status per dependency)

### F.4 Structured Logging

**Modify** `backend/app/main.py` + `backend/app/core/config.py`:
- `structlog` with JSON output
- Correlation ID per request (propagated through Celery tasks)
- Log level configurable via `LOG_LEVEL` env var

### F.5 Error Tracking

**Modify** `backend/app/main.py`:
- Sentry SDK integration (`SENTRY_DSN` env var)
- FastAPI middleware for automatic error capture
- Celery integration for worker errors
- Environment tagging (staging vs production)

### F.6 Usage Metrics

**Create** `backend/app/api/v1/usage.py`:
- `GET /v1/usage` — per-org metrics:
  - MCP tool calls per day/week/month
  - Most-used tools
  - Convention count, doc chunk count
  - Active API keys
  - Response latency percentiles
- Powers dashboard analytics and billing decisions

### F.7 Environment Documentation

**Modify** `.env.example` — comprehensive, grouped, commented:
```
# ── Required ──────────────────────────────────────
CLERK_SECRET_KEY=             # Auth provider
DATABASE_URL=                 # PostgreSQL (asyncpg)
REDIS_URL=                    # Celery broker + cache
ANTHROPIC_API_KEY=            # Quality LLM
ENCRYPTION_KEY=               # 32-byte base64, for secret encryption

# ── LLM Providers (cheap tier, auto-failover) ────
GEMINI_API_KEY=               # Free tier
OPENAI_API_KEY=               # Embeddings + cheap fallback

# ── Integrations ──────────────────────────────────
GITHUB_APP_PRIVATE_KEY=       # GitHub App (PEM format)
GITHUB_APP_ID=                # GitHub App ID
SLACK_CLIENT_ID=              # Slack OAuth
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=         # Webhook verification

# ── Deployment ────────────────────────────────────
CORS_ORIGINS=                 # Comma-separated allowed origins
SENTRY_DSN=                   # Error tracking (optional)
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
MCP_TRANSPORT=stdio           # stdio or http
```

---

## Part G: Onboarding — Self-Serve in 15 Minutes

### G.1 Updated Onboarding Flow

```
1. Sign up (Clerk)
2. Connect git repo (GitHub / Bitbucket / GitLab) — token test
3. Connect issue tracker (Jira / Linear / GitHub Issues) — optional
4. Connect docs (Confluence / Notion / Google Drive) — optional
5. Connect Slack — OAuth "Add to Slack" button — optional
6. Set project context + coding standards
7. Trigger ingestion (conventions + docs + reviewer patterns)
   └─ Progress bar: "Analyzing 200 PRs... Extracting conventions... Ingesting docs..."
8. Review extracted conventions (edit, suppress, approve)
9. Generate API key → Show MCP config for each AI tool
   └─ Copy-paste snippets for Claude Code, Cursor, Windsurf, Copilot, etc.
10. Done — start using
```

### G.2 Specific Changes

**Modify** `frontend/components/onboarding/Step2Repo.tsx` — add GitLab option
**Modify** `frontend/components/onboarding/Step3Jira.tsx` — add issue tracker provider selector (Jira / Linear / GitHub Issues)
**Modify** `frontend/components/onboarding/Step5Docs.tsx` — add Confluence/Notion/GDrive credential fields
**Create** `frontend/components/onboarding/StepMCPSetup.tsx` — API key generation + per-tool config snippets
**Modify** `frontend/components/onboarding/OnboardingDashboard.tsx` — update step flow

### G.3 SSE Reconnect

**Modify** `frontend/lib/hooks/useSSE.ts` — exponential backoff reconnection (1s, 2s, 4s, max 30s, 5 retries)

---

## Execution Order

### Sprint 1: Foundation (Week 1-2) — Phases C.1 git providers + E.1-E.5 security
Can be parallelized. No cross-dependencies.

| Work | Files | Days |
|------|-------|------|
| Git provider abstraction + GitLab | 6 new files + 10 modified | 3-4 |
| Encryption at rest | 3 new files + 2 modified | 1-2 |
| Rate limiting | 1 modified | 0.5 |
| Audit logging | 2 new files + 1 migration | 1 |
| API key management endpoints | 1 new file + 1 modified | 1 |
| CORS hardening | 1 modified | 0.5 |

### Sprint 2: MCP Universal + Outflow (Week 3-4) — Phases A + B.1-B.3

| Work | Files | Days |
|------|-------|------|
| MCP streamable HTTP transport | 2 new/modified | 2 |
| MCP setup CLI / config generator | 1 new file | 1-2 |
| REST API for non-MCP clients | 1 new file | 1 |
| Slack bot | 2 new files + 1 modified | 3-4 |
| GitHub App (PR comments) | 1 new file + 1 modified | 2-3 |

### Sprint 3: Inflow Expansion + Context System (Week 5-6) — Phases C.2-C.3 + D

| Work | Files | Days |
|------|-------|------|
| Issue tracker abstraction (Linear + GH Issues) | 5 new files + 3 modified | 3-4 |
| Doc providers (Notion + Google Drive) | 2 new files + 1 modified | 2-3 |
| Context provider system | 8 new files + 1 modified | 2-3 |
| Webhook inflow receiver | 3 new files | 1-2 |
| Row-level security migration | 1 migration + 1 modified | 1 |

### Sprint 4: Deploy + Polish (Week 7-8) — Phases F + G

| Work | Files | Days |
|------|-------|------|
| Fix Dockerfiles | 2 modified | 0.5 |
| Production docker-compose | 1 new file | 1 |
| Health checks + structured logging | 2 modified | 1 |
| Sentry integration | 1 modified | 0.5 |
| Usage metrics endpoint | 1 new file | 1 |
| Onboarding flow updates (all steps) | 5 modified + 1 new | 3-4 |
| SSE reconnect | 1 modified | 0.5 |
| Environment documentation | 1 modified | 0.5 |

### Sprint 5: Enterprise Polish (Week 9-10) — Phase E.6-E.8

| Work | Files | Days |
|------|-------|------|
| Jira Forge app (separate project) | New project | 5-7 |
| Data handling policy document | 1 new doc | 1 |
| DPA template | 1 new doc | 1 |
| SOC 2 readiness (Vanta setup, policies) | Non-code | 3-5 |
| Self-hosted deployment option | 3 new files | 2-3 |

---

## MVP for First Customer: Sprints 1 + 2 + half of 4

The minimum to put in front of a real team:
- Git provider abstraction (they might use GitHub, Bitbucket, or GitLab)
- Encrypted secrets (they won't enter tokens into a tool that stores them plaintext)
- MCP over HTTP (they might use Cursor, not just Claude Code)
- API key management (they need to generate and revoke keys)
- Setup instructions for their AI tool
- Working onboarding end-to-end

Everything else adds value but doesn't block the first sale.

---

## Verification

1. **Git providers**: Connect a GitLab repo → extract conventions → MCP returns them
2. **MCP HTTP**: Generate API key → configure Cursor with `{"url": "https://host/mcp/", "headers": {...}}` → call `get_context` → verify response
3. **MCP stdio**: Run `kronode setup claude-code --token kron_xxx` → paste into `.mcp.json` → Claude Code calls `get_context`
4. **Slack bot**: DM `@kronode what are the conventions for auth-service?` → get formatted response
5. **GitHub App**: Open PR → Kronode posts conventions comment within 30s
6. **Jira panel**: View DEECO-1234 → see "Kronode Context" panel with relevant conventions
7. **REST API**: `curl -H "Authorization: Bearer kron_xxx" -d '{"task": "update cert exchange"}' https://host/v1/context` → get context
8. **Encryption**: Check DB directly → tokens are ciphertext, not plaintext
9. **Audit**: Call MCP tool → check audit_log table has entry with org_id, tool_name, timestamp
10. **RLS**: Set wrong `app.current_org_id` → verify zero results returned
11. **Self-onboarding**: New user sign up → complete all steps → MCP working → under 15 minutes
12. **Multi-tenant**: Two orgs using same deployment → verify complete data isolation
