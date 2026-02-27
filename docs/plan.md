# Kronode — Implementation Plan

## Goal
An autonomous AI developer — hired as an organisational actor, not a tool.
The agent picks up Jira tickets, writes code, opens PRs, updates tickets, and notifies Slack.
Memory is the moat: the agent gets smarter about your team with every ticket.

---

## Current Status

### ✅ Milestone 1: E2E Jira → PR (complete)

The core loop works end-to-end:

```
User selects Jira ticket
  → Backend fetches full ticket body (summary + description/ADF)
  → Router Agent classifies task + selects agents
  → Context Builder fetches relevant repo files (GitHub API)
  → Planner Agent creates subtasks + Definition of Done
  → Coder Agent writes files + opens GitHub PR
  → Jira ticket transitions to "In Review" + PR linked as remote link
  → Slack notification posted to configured channel
```

### Agent Status

| Agent | File | Status |
|-------|------|--------|
| Task Router | `router_agent.py` | ✅ Working — Haiku, classifies + routes |
| Context Builder | `context_builder.py` | ✅ Working — fetches tree, selects files, extracts conventions |
| Guardrails | `guardrails_agent.py` | 🔲 Stub — always passes |
| Clarification | `clarification_agent.py` | 🔲 Stub — always skips |
| Planner | `planner_agent.py` | ✅ Working — Sonnet, subtasks + DoD checklist |
| Coder | `coder_agent.py` | ✅ Working — Sonnet, writes files + opens PR |
| Tester | `tester_agent.py` | 🔲 Stub — skips test generation |
| Execution Verifier | `execution_verifier.py` | 🔲 Stub — always passes |
| Reviewer | `reviewer_agent.py` | 🔲 Stub — always approves |
| Memory | `memory_agent.py` | 🔲 Stub — no write-back |

### Service Status

| Service | File | Status |
|---------|------|--------|
| GitHub | `github_service.py` | ✅ Working — tree, file fetch, branch, commit, PR |
| Jira | `jira_service.py` | ✅ Working — fetch tickets, fetch ticket detail (ADF→text), update status, attach PR link |
| Slack | `slack_service.py` | ✅ Working — post notification with PR link |

### Frontend Status

| Page / Component | Status |
|-----------------|--------|
| Auth (Clerk) | ✅ Working |
| Onboarding — card dashboard | ✅ Working — 8 cards, modals, connection tests |
| Dashboard — Jira backlog | ✅ Working — collapsible ticket list, click to assign |
| Dashboard — Task input | ✅ Working — ticket-only, prefill from Jira |
| Task detail — SSE stream | ✅ Working — real-time agent events, deduplicated |
| Task detail — Cancel | ✅ Working — Celery revoke + DB status |

### API Endpoints

| Method | Path | Status |
|--------|------|--------|
| POST | /v1/task | ✅ Working |
| GET | /v1/task/{id} | ✅ Working |
| SSE | /v1/task/{id}/stream | ✅ Working |
| POST | /v1/task/{id}/cancel | ✅ Working |
| GET | /v1/dashboard | ✅ Working |
| POST | /v1/onboarding/* | ✅ Working |
| GET | /v1/jira/tickets | ✅ Working |
| POST | /v1/onboarding/test-github-token | ✅ Working |
| POST | /v1/onboarding/test-jira | ✅ Working |
| POST | /v1/onboarding/test-slack | ✅ Working |

---

## Milestone 2: Agent Profiles

Each Kronode agent has a **developer profile** — a specialist identity with a defined tech stack,
world-class skills injected into its system prompts, and a scoped domain it cannot leave.

### Available Profiles

| Profile | Stack | Scope |
|---------|-------|-------|
| **Web Engineer** | React / Next.js / TypeScript / Tailwind | Frontend components, routing, state, API integration |
| **Backend Engineer** | Python / FastAPI / PostgreSQL / Redis | APIs, data models, background jobs, auth |
| **Mobile (iOS)** | Swift / SwiftUI / Combine | iOS screens, navigation, local storage, API calls |
| **Mobile (Android)** | Kotlin / Jetpack Compose | Android screens, viewmodels, Room, API calls |
| **Full-Stack** | Next.js + FastAPI or Rails or Node | End-to-end features across frontend and backend |
| **DevOps** | Docker / Kubernetes / Terraform / GitHub Actions | CI/CD, infra-as-code, deployments, monitoring |
| **Data Engineer** | Python / dbt / Airflow / Snowflake | Pipelines, transformations, data models |

### What a Profile Controls

1. **System prompt** — every agent in the pipeline receives a profile-specific system prompt written to embed world-class engineering judgement for that stack (not just syntax — e.g. Web: Core Web Vitals, accessibility, component composition; Backend: idempotency, migration safety, query optimisation; DevOps: least-privilege IAM, rollback safety, secret management)
2. **Guardrails scope** — which directories and file extensions the agent is allowed to touch; requests outside scope are blocked before the coder runs
3. **Context Builder priorities** — which file extensions and naming patterns to weight as relevant when selecting files from the repo tree
4. **Router thresholds** — what "simple" vs "complex" means for that stack (a one-line SQL change is simple for a backend agent; a Kubernetes rollout change is complex for a DevOps agent)

### Implementation Plan

**Backend:**
- Add `agent_profile` field to `OnboardingConfig` (migration 006)
- Create `backend/app/profiles/` directory with one file per profile:
  - `web.py`, `backend.py`, `mobile_ios.py`, `mobile_android.py`, `fullstack.py`, `devops.py`, `data.py`
  - Each exports: `SYSTEM_PROMPT_INJECTION`, `ALLOWED_EXTENSIONS`, `ALLOWED_DIRS`, `CONTEXT_PRIORITIES`
- Pipeline reads active profile and injects into each agent's system prompt
- Guardrails Agent reads `ALLOWED_DIRS` / `ALLOWED_EXTENSIONS` to enforce scope

**Frontend (Onboarding):**
- Add profile selector card to onboarding (step before repo setup)
- Show profile cards with name, stack chips, scope description
- Selected profile stored with org config

**Memory scoping:**
- `memory_records` gains `agent_profile` column — conventions learned by a Web agent don't bleed into a Backend agent's context

---

## Milestone 3: Cost Reduction

**Target: < $0.05 per ticket** (currently ~$0.15–0.25)

Every LLM call costs money. The goal is to drive per-ticket cost down aggressively while maintaining or improving output quality. Most of this is achievable without sacrificing capability.

### 3a — Convention caching (extract once, reuse forever)
The Context Builder currently re-extracts conventions on every run via a Haiku call. Instead:
- After first extraction, store conventions in `memory_records` with type `convention`
- On subsequent runs, read from DB — no LLM call at all
- Invalidate cache only when new files are pushed to the repo (webhook or daily check)
- **Saving:** removes 1 Haiku call per ticket after the first

### 3b — File selection without LLM
The Context Builder uses Haiku to pick relevant files. Replace with deterministic scoring:
- Keyword overlap between ticket description and file paths (already in `_heuristic_select`)
- Boost files that have been touched in previous tasks for this org (co-occurrence from `memory_records`)
- Boost files modified recently in the repo (GitHub API `commits` recency)
- **Saving:** removes 1 Haiku call per ticket — and gets smarter over time with no extra cost

### 3c — Context size cap
Fewer input tokens = lower cost. Enforce hard limits:
- Max 20KB of file content sent to Coder (currently 30KB cap, often less in practice)
- Planner receives file paths only, not content (already done)
- Truncate long Jira descriptions at 1,000 chars — agents don't need the full body
- Strip comments and blank lines from fetched files before sending to reduce token count

### 3d — Router short-circuit for simple tasks
Simple tasks (typos, colour changes, copy edits) don't need Context Builder or Planner.
Router already classifies complexity — add a `simple` fast path:
```
simple → skip context_builder, clarification, planner → coder directly
```
- **Saving:** removes 2 agent calls on simple tasks

### 3e — Prompt caching (Anthropic API)
Use Anthropic's prompt caching for the system prompts (profile injection + agent instructions).
System prompts are static per profile — cache them with `cache_control: ephemeral`.
- **Saving:** ~90% reduction on cached input tokens for repeated runs

### 3f — LLM model allocation (move non-critical calls to free/cheap providers)

Keep Claude Sonnet only where code quality is non-negotiable (Coder). Route everything else to
free or near-free inference.

| Agent | Current | Proposed | Provider | Cost/ticket |
|-------|---------|----------|----------|-------------|
| Router | Haiku | Llama 3.1 8B | Groq (free tier) | $0 |
| Context Builder file select | Haiku | Deterministic scoring | No LLM | $0 |
| Context Builder conventions | Haiku | Llama 3.1 8B | Groq (free tier) | $0 |
| Planner | Sonnet | Gemini Flash 2.0 or DeepSeek V3 | Google / DeepSeek | ~$0.001 |
| Coder | Sonnet | **Keep Sonnet** | Anthropic | ~$0.04 |
| Tester *(future)* | — | Codestral | Mistral (free) | $0 |
| Reviewer *(future)* | — | Llama 3.3 70B | Groq (free tier) | $0 |
| Memory / Guardrails *(future)* | — | No LLM | Deterministic | $0 |
| **Total** | **~$0.15–0.25** | | | **< $0.05** |

**Why Coder stays on Sonnet:** The coder produces the actual diff. A bad code generation wipes out
all savings through rework. Every other agent produces text the coder then acts on — those can be
downgraded without affecting output quality.

**Groq free tier:** 14,400 requests/day on Llama models — more than enough for current volume.
**Gemini Flash 2.0:** $0.075/1M input tokens — ~$0.001 per planner call at current context sizes.
**DeepSeek V3:** $0.14/1M input tokens, strong reasoning, good alternative if Gemini latency is high.

---

## Milestone 4: Memory (The Moat)

Memory is the core product differentiator. Unlike competitors that start fresh every run, Kronode compounds. Each of the approaches below is achievable without LLM calls — deterministic extraction from structured data.

### 3a — Memory Agent (write-back)
- After successful PR: record conventions observed, files changed, patterns used
- Store in `memory_records` table (already exists in schema)
- Record types: `convention`, `file_touched`, `pr_outcome`, `pitfall`

### 3b — Context Builder reads Memory
- Before selecting files, query `memory_records` for this org + profile
- Inject past conventions into coder system prompt
- Boost files that have been touched in previous runs for this ticket type
- This is what makes ticket 10 better than ticket 1

### 3c — PR Outcome tracking
- Poll GitHub API every 10 min for open PRs — check merged / changes requested
- On merge: write `pr_outcome` memory record, transition Jira to "Done"
- On changes requested: write `pitfall` record with reviewer comment summary

---

## Milestone 5: Smarter Agents

### 4a — Guardrails Agent (enforce profile scope)
- Read `ALLOWED_DIRS` from active profile — block if coder targets paths outside scope
- Read `max_files_per_task` from guardrails config — warn if plan exceeds it
- Check `risk_level` — escalate to clarification if "conservative" + large scope

### 4b — Tester Agent (write tests)
- Receive coder output (files list)
- Write unit tests for new/changed functions using the profile's test conventions
- Add test files to the same PR (append to coder's file list)

### 4c — Reviewer Agent (enforce DoD)
- Real critic pass against Planner's Definition of Done checklist
- Flag incomplete items to Slack/Jira comment

---

## Milestone 6: OAuth + Secrets

### Current state
- GitHub: manual PAT stored in `onboarding_config.github_access_token`
- Jira: manual email + API token
- Slack: manual bot token

### Target
- GitHub App (OAuth) — scoped to repo, no PAT lifetime issues
- Jira OAuth 2.0 (3LO)
- Slack OAuth App install flow
- Move all secrets to AWS Secrets Manager / HashiCorp Vault

---

## Milestone 7: Execution Verifier (E2B sandbox)
- Spin up E2B sandbox with repo contents
- Run `npm test` / `pytest` / `go test` per profile's test command
- Parse output: fail → send back to Coder for retry (up to 2 attempts)
- Pass → PR gets "tests pass" label

---

## Architecture

### Stack
- **Frontend**: Next.js 14 App Router, Tailwind, Clerk, Zustand, Axios, TanStack Query — **pnpm**
- **Backend**: FastAPI, PostgreSQL/Supabase, Celery + Redis, Alembic — **uv**
- **Agents**: Anthropic SDK — Haiku (routing), Sonnet (planning + coding)
- **Layout**: flat (`frontend/` + `backend/` at root, no monorepo tooling)

### Key Files
| Purpose | Path |
|---------|------|
| Pipeline orchestrator | `backend/app/pipeline/pipeline.py` |
| Celery task | `backend/app/pipeline/task_queue.py` |
| Agent base | `backend/app/agents/base.py` |
| Agent profiles (to create) | `backend/app/profiles/` |
| GitHub service | `backend/app/services/github_service.py` |
| Jira service | `backend/app/services/jira_service.py` |
| Slack service | `backend/app/services/slack_service.py` |
| Frontend API client | `frontend/lib/api.ts` |
| Zustand store | `frontend/lib/store.ts` |
| SSE hook | `frontend/lib/hooks/useSSE.ts` |

### Database Schema
- **users** — id, clerk_id, email, name, role
- **organizations** — id, name, clerk_org_id
- **onboarding_config** — org_id (FK), repo_url, github_access_token, jira_*, slack_*, agent_profile, capabilities (JSONB), guardrails (JSONB), agent_name, agent_avatar, project_context
- **tasks** — id (UUID), org_id, description, jira_ticket_id, status, result (JSONB), celery_task_id, created_at, completed_at
- **task_events** — id, task_id, agent_name, event_type, message, payload (JSONB)
- **memory_records** — id, org_id, task_id, agent_profile, record_type, content (JSONB), source

---

## Product Vision
- Kronode is an **organisational actor**, not a tool — hired from headcount budget
- **Agent profiles** — world-class specialists with enforced scope, not generic agents
- **Memory is the moat** — compounding value vs stateless competitors (Devin, Factory, Sweep)
- Core promise: second ticket better than first, tenth better than fifth
- Every feature decision: "does this make the agent smarter about this team over time?"
- North star metrics: time to first merged PR + PR acceptance rate improvement over time
