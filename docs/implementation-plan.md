# Kronode — Implementation Plan

*Last updated: 2026-02-26*

## What's Already Built

| Component | Status | Notes |
|-----------|--------|-------|
| Onboarding flow (8 cards) | ✅ Complete | Auth, backend saves working |
| Router Agent | ✅ Real | Uses claude-haiku, classifies task + selects pipeline |
| Planner Agent | ✅ Real | Uses claude-opus-4-6, produces subtasks + DoD |
| Coder Agent | ✅ Real | Uses claude-sonnet-4-6, writes files + attempts GitHub PR |
| Pipeline orchestrator | ✅ Real | Runs agent chain, emits SSE events, handles failures |
| Task model + SSE stream | ✅ Real | `/v1/task`, `/v1/task/{id}`, `/v1/task/{id}/stream` |
| Dashboard API | ✅ Real | `GET /v1/dashboard` returns agent config + recent tasks |
| Memory model | ✅ Schema | `MemoryRecord` table exists, agent is stub |
| Context Builder | 🔶 Stub | Returns empty — no GitHub file fetching yet |
| Memory Agent | 🔶 Stub | No write-back — corrections not stored |
| Guardrails Agent | 🔶 Stub | Always passes |
| Tester / Verifier / Reviewer | 🔶 Stub | No real execution |
| Dashboard UI | ❌ Missing | `DashboardClient` component not built |
| GitHub OAuth | ❌ Missing | Token stored nowhere — coder uses placeholder |
| Standup bot | ❌ Missing | |
| Backlog monitor | ❌ Missing | |

---

## Phase 1 — First Merged PR
*Goal: A human types a task → agent plans → code is pushed → PR opens on GitHub*

### 1.1 Dashboard UI
**Files to create:**
- `frontend/components/dashboard/DashboardClient.tsx` — main client component
- `frontend/components/dashboard/TaskSubmit.tsx` — task input (text + optional Jira ID)
- `frontend/components/dashboard/TaskFeed.tsx` — list of recent tasks with status badges
- `frontend/components/dashboard/TaskStream.tsx` — real-time agent progress view (SSE)
- `frontend/components/dashboard/AgentCard.tsx` — agent name/avatar + integration status strip

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  [Avatar] Forge  ·  GitHub ✓  Jira –  Slack –        │  ← AgentCard
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────┐
│  What should Forge work on?          │  ← TaskSubmit
│  [_____________ text input _______]  │
│  [Optional: Jira ticket ID]          │
│  [Assign to Forge →]                 │
└─────────────────────────────────────┘

Recent work                              ← TaskFeed
  ● queued   Add forgot password screen   2m ago
  ✓ done     Fix login button colour      1h ago
  ✗ failed   Refactor auth module         3h ago
```

When a running task is clicked → TaskStream expands showing live SSE events:
```
  ✓ Router      Task classified as medium. Running 9 agents.
  ✓ Context     Fetched 12 relevant files from repo.
  ⟳ Planner     Creating implementation plan...
```

**API calls used:** `getDashboard()`, `createTask()`, `getTask()`, SSE from `/v1/task/{id}/stream`

---

### 1.2 GitHub Token Storage
The Coder Agent already tries to push PRs but has no auth token.

**Backend changes:**
- Add `github_access_token` (encrypted) to `OnboardingConfig` model
- Add migration
- `POST /v1/onboarding/github-token` endpoint to store it

**Frontend changes:**
- Add "Connect GitHub" button to the repo card on onboarding (or dashboard settings)
- For now: simple PAT (Personal Access Token) input, not full OAuth
- OAuth flow comes in Phase 3

**Pipeline change:**
- Pass `github_access_token` from config into pipeline context
- Coder Agent reads it for `create_pull_request(token=...)`

---

### 1.3 Context Builder (Real Implementation)
Currently returns empty arrays. Needs to fetch relevant files from GitHub.

**Logic:**
1. Use GitHub API to get repo tree (list all files)
2. Use Claude haiku to identify which files are relevant to the task description
3. Fetch content of top N files (cap at ~50KB total to stay within context)
4. Extract conventions (naming patterns, import styles, test patterns)

**Output added to pipeline context:**
```python
{
  "relevant_files": [{"path": "...", "content": "..."}],
  "conventions": ["Uses named exports", "Tests in __tests__/ dir"],
  "repo_structure": "brief tree summary"
}
```

---

## Phase 2 — Memory (The Moat)
*Goal: Ticket 2 is better than ticket 1. The agent learns from every interaction.*

### 2.1 Memory Agent (Real Implementation)
After each completed pipeline run, write back:
- **Code patterns** extracted from the files the coder wrote
- **PR outcome** (merged / changes requested / rejected) — polled from GitHub
- **Conventions learned** from the context builder pass

**New endpoint:** `POST /v1/task/{id}/outcome` — called when a PR is merged/reviewed
Stores: reviewer name, outcome, comments

**Memory record types:**
| type | when written | content |
|------|-------------|---------|
| `convention` | every run | naming, structure patterns seen in repo |
| `pr_outcome` | PR merged/rejected | title, outcome, reviewer |
| `reviewer_feedback` | PR review comment | reviewer, comment, file, corrective action |
| `pitfall` | pipeline failure or changes_requested | what went wrong |

### 2.2 Context Builder reads Memory
After fetching repo files, also query `MemoryRecord` for this org:
- Inject past reviewer feedback into planner context
- Inject known pitfalls into guardrails context
- Inject conventions into coder context

This is what makes ticket 10 better than ticket 1.

### 2.3 PR Outcome Webhook / Polling
To feed memory, we need to know what happened to the PR:
- Option A (simpler): GitHub webhook → `POST /v1/webhooks/github` → store outcome
- Option B: Poll GitHub API every 10 minutes for open PRs

Start with Option B (polling via Celery beat), upgrade to webhooks later.

---

## Phase 3 — Proactive Teammate
*Goal: The agent acts like a team member, not a tool waiting to be used.*

### 3.1 Daily Standup (Slack)
Celery beat task runs at 9am:
- Queries last 24h of completed/failed tasks
- Generates standup message via Claude
- Posts to `slack_channel_id`

Format:
```
*Forge's standup*
✅ Yesterday: Opened PR #42 (Add forgot password) — awaiting review
🔧 Today: Working on KR-18 (Improve error messages on signup)
🚧 Blocked: Need clarification on design for KR-22
```

### 3.2 Backlog Monitor (Jira)
Celery beat task runs hourly:
- Fetches unassigned tickets from configured Jira project
- Router Agent evaluates each: can I do this? confidence level?
- High-confidence tickets → post offer to Slack: *"I can take KR-25. Want me to start?"*
- If no response in 2h → don't auto-start (respect the human in control principle)

### 3.3 GitHub OAuth (Replace PAT)
Proper OAuth flow:
- `GET /v1/oauth/github/start` → redirect to GitHub
- `GET /v1/oauth/github/callback` → exchange code, store encrypted token
- Tokens stored in new `OAuthToken` model (per org, per provider)

---

## Phase 4 — Reviewer Learning
*Goal: The agent knows what each engineer cares about before they say it.*

### 4.1 Reviewer Preference Model
When a PR reviewer leaves a comment:
- Parse comment via Claude: what category? (style / logic / test coverage / naming)
- Store as `reviewer_feedback` memory record keyed to reviewer GitHub username
- Next PR to same reviewer: inject their known preferences into coder context

### 4.2 PR Acceptance Rate Dashboard
Add to dashboard:
- Total PRs opened
- Accepted on first review / required changes / rejected
- Trend over time (chart)
- This is the north star metric visible to customers

---

## Build Order

```
Phase 1:
  1.1  Dashboard UI                        ~1 day
  1.2  GitHub token (PAT input + storage)  ~2 hours
  1.3  Context Builder (GitHub file fetch)  ~half day
  → Demo: type task → watch agent run → PR opens on GitHub

Phase 2:
  2.1  Memory Agent write-back             ~half day
  2.2  Context Builder reads memory        ~half day
  2.3  PR outcome polling                  ~half day
  → Demo: complete task 5, show it addressing feedback from tasks 1–4

Phase 3:
  3.1  Daily standup                       ~half day
  3.2  Backlog monitor                     ~1 day
  3.3  GitHub OAuth                        ~1 day
  → Demo: agent volunteers for a ticket unprompted

Phase 4:
  4.1  Reviewer preference learning        ~1 day
  4.2  PR acceptance rate dashboard        ~half day
  → Demo: show improving acceptance rate chart to customer
```

---

## What NOT to Build Yet
- Execution Verifier (E2E sandbox) — expensive, complex, not needed for first demo
- Tester Agent (real) — stub is fine until memory is working
- Multi-org / team management
- Billing
