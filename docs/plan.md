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
| Task Router | `router_agent.py` | ✅ Working — Haiku, classifies + routes; simple fast-path skips context+planner |
| Context Builder | `context_builder.py` | ✅ Working — deterministic file selection (profile boost + memory boost); Haiku convention extraction with cache |
| Guardrails | `guardrails_agent.py` | ✅ Working — profile scope + restricted paths + conservative risk cap |
| Clarification | `clarification_agent.py` | ✅ Working — Haiku ambiguity detection; posts questions to Slack; pauses pipeline; resumes on reply |
| Planner | `planner_agent.py` | ✅ Working — Sonnet, subtasks + DoD checklist; profile + coding standards injected; prompt caching |
| Coder | `coder_agent.py` | ✅ Working — Sonnet, writes files + opens PR; profile + coding standards injected; prompt caching |
| Tester | `tester_agent.py` | ✅ Working — Haiku test gen (profile-aware); commits to PR branch |
| Execution Verifier | `execution_verifier.py` | 🔲 Stub — always passes |
| Reviewer | `reviewer_agent.py` | ✅ Working — Haiku DoD critic pass; advisory (non-blocking); patterns stored in memory |
| Memory | `memory_agent.py` | ✅ Working — file_touched, convention, pr_outcome write-back; PR poll via Celery Beat |

### Service Status

| Service | File | Status |
|---------|------|--------|
| GitHub | `github_service.py` | ✅ Working — tree, file fetch, branch, commit, PR, PR status + reviews, add files to branch |
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

## ✅ Milestone 2: Agent Profiles (complete)

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

### Org-defined coding standards (gap to fill)

The static profile injects world-class baseline standards. Orgs also have their own conventions
(internal design tokens, ESLint config, naming patterns, API call patterns). These need a home.

**Implementation:**
- Add `coding_standards: Text` column to `onboarding_config` (migration 007)
- Add a "Coding standards" field to the **Project context** onboarding card (textarea, below the
  existing project description) — prompt: *"Any team-specific conventions, style rules, or patterns
  your agent must always follow? (e.g. 'use our internal Button component, never raw `<button>`')"*
- Pipeline injects `coding_standards` between profile injection and agent system prompt:
  ```
  [profile SYSTEM_PROMPT_INJECTION]
  --- Team standards ---
  [org coding_standards]
  --- Agent task ---
  [SYSTEM_PROMPT]
  ```
- Memory compounds on top: learned conventions from PRs get appended automatically over time

This gives the agent three layers of standards: universal profile baseline → org custom rules → learned conventions.

---

## ✅ Milestone 3: Cost Reduction (complete)

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

## ✅ Milestone 4: Memory (The Moat) (complete)

Memory is the core product differentiator. Unlike competitors that start fresh every run, Kronode compounds. Each of the approaches below is achievable without LLM calls — deterministic extraction from structured data.

### M4a — Memory Agent (write-back) ✅
- After successful PR: writes `file_touched` (one per file), `convention` (fresh extractions only), `pr_outcome` (merged=false, updated by poll job)
- All deterministic — no LLM calls

### M4b — Context Builder reads Memory ✅
- Queries `memory_records` for `file_touched` records (last 100) before heuristic file selection
- Previously-touched paths get +2 score boost alongside the profile extension +2 boost
- Makes ticket 10 better than ticket 1 — files the org has modified before surface higher

### M4c — PR Outcome polling ✅
- Celery Beat runs `poll_pr_outcomes` every 10 minutes
- On merge: sets `pr_outcome.merged=True` + transitions Jira to "Done"
- On changes requested: writes `pitfall` record with reviewer comment bodies
- Start beat: `uv run celery -A app.celery_app beat --loglevel=info`

---

## ✅ Milestone 5: Smarter Agents (complete)

### M5a — Guardrails Agent ✅
- Deterministic (no LLM) — runs after planner so it can inspect `files_affected`
- Checks restricted paths (org config), `ALLOWED_DIRS` + `ALLOWED_EXTENSIONS` (profile), `max_files_per_task`, conservative risk cap
- Blocks pipeline (`status=paused`) on any violation

### M5b — Tester Agent ✅
- Haiku LLM generates unit tests profile-aware (Jest/RTL for TS, pytest for Python)
- Commits test files as a second commit to the same PR branch via `add_files_to_branch`
- Non-blocking — failure to commit is logged but doesn't halt pipeline

### M5c — Reviewer Agent ✅
- Haiku LLM does structured DoD critic pass against `planner_agent["definition_of_done"]`
- Returns `approved`, `dod_review`, `changes_requested`, `verdict`
- Non-blocking in M5 — advisory only; rejections written to `memory_records` as `pattern` records
- Three-level JSON fallback prevents parse errors from blocking pipeline

---

## ✅ Milestone 6: Slack Clarification Loop (complete)

When a task description is ambiguous, the clarification agent generates 1-3 specific questions,
posts them to the org's Slack channel via Block Kit, and pauses the pipeline
(`status=waiting_clarification`). Celery Beat polls the Slack thread every 30s. When a human
replies, the pipeline resumes from `planner_agent` with the answer injected into context.
No Slack Events API webhook required.

### Agent Status

| Agent | Status |
|-------|--------|
| Clarification | ✅ Working — Haiku ambiguity detection, Slack post, waiting signal |

### New Beat Tasks

| Task | Schedule |
|------|----------|
| `poll_clarifications` | Every 30s — resumes waiting tasks on Slack reply, times out after 24h |

---

## Milestone 7: Clarification Quality Validation

When a human replies to a Slack clarification thread with a non-answer (gibberish, off-topic, emoji-only), the pipeline currently treats it as a valid clarification and proceeds. This milestone adds an answer quality gate.

### Flow

```
Slack reply detected
  → Haiku: "Does this reply actually answer the questions asked?"
      ├─ Yes → resume_pipeline (current behaviour)
      └─ No  → post follow-up to same Slack thread:
                 "That doesn't seem to answer the question — could you clarify?"
               → keep task in waiting_clarification
               → poll again next cycle (already handles this)
```

### Implementation

**`task_queue.py` — `_poll_clarifications`**

After detecting replies, before calling `run_resume_pipeline.delay`, add a Haiku quality check:

```python
QUALITY_PROMPT = """You are checking whether a human reply answers specific clarification questions.

Questions asked: {questions}
Reply received: {reply}

Respond with JSON only: {"answers_questions": true} or {"answers_questions": false}
"""
```

- If `answers_questions: false` → post a polite follow-up to the same thread ts, do NOT queue resume
- If `answers_questions: true` → queue resume as normal
- If Haiku call fails → assume valid (non-blocking, fail-open)

**`slack_service.py`** — reuse `post_notification` with `thread_ts` param to reply in-thread (set `thread_ts` in the payload to keep it in the original thread).

### What does "answers" mean?

Haiku checks:
- Is the reply at least one full sentence?
- Does it reference any of the topics in the questions?
- Is it not just an emoji, reaction, or filler word?

A reply of "use Postgres" is valid. "yabadaba doo", "ok", "👍" are not.

---

## Milestone 8: OAuth + Secrets

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

## Milestone 9: Execution Verifier (E2B sandbox)
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
