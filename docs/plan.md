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
| Planner | `planner_agent.py` | ✅ Working — Opus, subtasks + DoD checklist |
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
| Task detail — SSE stream | ✅ Working — real-time agent events |
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

## Milestone 2: Smarter Agent (next)

Fill in the stub agents to improve PR quality and reduce hallucination.

### 2a — Guardrails Agent (enforce config)
- Read `restricted_paths` from context — block if coder targets them
- Read `max_files_per_task` — warn if plan exceeds it
- Check `risk_level` — escalate to clarification if "conservative" + large scope

### 2b — Tester Agent (write tests)
- Receive coder output (files list)
- Write unit tests for new/changed functions
- Add test files to the same PR (append to coder's file list)
- Goal: every PR includes tests

### 2c — Memory Agent (write-back)
- After successful PR: record patterns used, files changed, conventions observed
- Store in `memory_records` table (already exists in schema)
- Feed memory into Context Builder on next run (compounding value)

### 2d — Reviewer Agent (enforce DoD)
- Real critic pass against Planner's Definition of Done checklist
- Flag incomplete items to Slack/Jira comment (not block the PR)

---

## Milestone 3: Better Context

### 3a — Smarter file selection in Context Builder
- Weight files by how often they've been touched in previous tasks (from memory_records)
- Prefer files in the same module/directory as the ticket's component

### 3b — Jira ticket enrichment
- Already fetching: summary, description (ADF→text), type, priority, assignee
- Add: linked issues, comments, acceptance criteria (if in Confluence)
- Pass `jira_ticket.issue_type` to Router to affect routing ("Bug" vs "Story" vs "Epic")

### 3c — Branch hygiene
- Slugify branch name from ticket ID: `feature/KR-42-add-payment-screen`
- Check for existing branches with same ticket ID — avoid duplicates

---

## Milestone 4: OAuth + Secrets

### Current state
- GitHub: manual PAT (stored in `onboarding_config.github_access_token`)
- Jira: manual email + API token
- Slack: manual bot token

### Target
- GitHub App (OAuth) — scoped to repo, no PAT lifetime issues
- Jira OAuth 2.0 (3LO)
- Slack OAuth App install flow
- Move all secrets to AWS Secrets Manager / HashiCorp Vault

---

## Milestone 5: Execution Verifier (E2B sandbox)
- Spin up E2B sandbox with repo contents
- Run `npm test` / `pytest` / `go test`
- Parse output: fail → send back to Coder for retry (up to 2 attempts)
- Pass → PR gets "tests pass" label

---

## Architecture

### Stack
- **Frontend**: Next.js 14 App Router, Tailwind, Clerk, Zustand, Axios, TanStack Query — **pnpm**
- **Backend**: FastAPI, PostgreSQL/Supabase, Celery + Redis, Alembic — **uv**
- **Agents**: Anthropic SDK — Haiku (routing), Opus (planning), Sonnet (coding)
- **Layout**: flat (`frontend/` + `backend/` at root, no monorepo tooling)

### Key Files
| Purpose | Path |
|---------|------|
| Pipeline orchestrator | `backend/app/pipeline/pipeline.py` |
| Celery task | `backend/app/pipeline/task_queue.py` |
| Agent base | `backend/app/agents/base.py` |
| GitHub service | `backend/app/services/github_service.py` |
| Jira service | `backend/app/services/jira_service.py` |
| Slack service | `backend/app/services/slack_service.py` |
| Frontend API client | `frontend/lib/api.ts` |
| Zustand store | `frontend/lib/store.ts` |
| SSE hook | `frontend/lib/hooks/useSSE.ts` |

### Database Schema
- **users** — id, clerk_id, email, name, role
- **organizations** — id, name, clerk_org_id
- **onboarding_config** — org_id (FK), repo_url, github_access_token, jira_*, slack_*, capabilities (JSONB), guardrails (JSONB), agent_name, agent_avatar, project_context
- **tasks** — id (UUID), org_id, description, jira_ticket_id, status, result (JSONB), celery_task_id, created_at, completed_at
- **task_events** — id, task_id, agent_name, event_type, message, payload (JSONB)
- **memory_records** — id, org_id, task_id, record_type, content (JSONB), source

---

## Product Vision
- Kronode is an **organisational actor**, not a tool — hired from headcount budget
- **Memory is the moat** — compounding value vs stateless competitors (Devin, Factory, Sweep)
- Core promise: second ticket better than first, tenth better than fifth
- Every feature decision: "does this make the agent smarter about this team over time?"
- North star metrics: time to first merged PR + PR acceptance rate improvement over time
