# Agents — Autonomous AI Developer Tool

> A complete reference for every agent in the system — what it does, when it runs, what it needs, and what it produces. Includes context building, guardrails, verification, memory, and failure handling.

---

## Frontend — Onboarding Dashboard

Before any agent runs, the user completes a structured onboarding flow that configures the system, connects integrations, and sets the rules the agents operate within. This is the product's front door — built for non-technical stakeholders, not developers.

---

### Frontend Stack

| Layer | Tool | Why |
|---|---|---|
| Framework | Next.js (App Router) | Fast, production-ready, server-side rendering, easy Vercel deployment |
| Styling | Tailwind CSS | Rapid UI without custom CSS overhead |
| State management | Zustand | Lightweight, sufficient for onboarding flow and dashboard state |
| API calls | Axios + TanStack Query (React Query) | Clean async handling, caching, and request retry |
| Auth | Clerk Next.js SDK | Drop-in auth with social login and OAuth management |
| Real-time updates | Server-Sent Events (EventSource API) | Streams agent task progress live to the browser |
| Hosting | Vercel | One-click deploy, works natively with Next.js |

---

### Backend Stack

| Layer | Tool | Why |
|---|---|---|
| Framework | FastAPI (Python) | Async, fast, production-ready REST and SSE support |
| Auth validation | Clerk Python SDK | Validates JWT tokens issued by Clerk on every request |
| Database | PostgreSQL via Supabase | Stores org config, agent settings, onboarding state |
| Secrets storage | Supabase Vault or AWS Secrets Manager | OAuth tokens never stored in plain DB columns |
| Real-time | Server-Sent Events (SSE) via FastAPI | Streams task progress to the Next.js frontend without polling |
| Task queue | Celery + Redis | Async agent execution — critical for scale |
| Hosting | Railway or Render (POC) → AWS ECS (scale) | Simple start with a clear path to production scale |
| API versioning | /v1/ prefix on all routes | Supports clean versioning as the product evolves |

---

### Connecting Frontend to Backend

Every onboarding step that saves data makes an API call from Next.js to FastAPI. The backend validates the Clerk JWT on every request, stores configuration, and returns a response. OAuth flows for GitHub, Jira, and Slack are initiated from the browser but all token exchange and storage happen on the backend only — never in the browser.

```
Next.js (Frontend)
    ↓ POST /v1/onboarding/account      — saves user and org profile
    ↓ POST /v1/onboarding/repo         — saves GitHub repo selection
    ↓ POST /v1/onboarding/jira         — saves Jira workspace config
    ↓ POST /v1/onboarding/slack        — saves Slack channel config
    ↓ POST /v1/onboarding/docs         — saves Confluence or Google Drive config
    ↓ POST /v1/onboarding/capabilities — saves agent capability selections
    ↓ POST /v1/onboarding/guardrails   — saves restricted paths and risk level
    ↓ POST /v1/onboarding/agent        — saves agent name and avatar
    ↓ POST /v1/onboarding/context      — saves project description
    ↓ POST /v1/onboarding/complete     — marks onboarding done, activates agent
    ↓ GET  /v1/dashboard               — loads agent status and task history
    ↓ POST /v1/task                    — submits a new task to the pipeline
    ↓ SSE  /v1/task/:id/stream         — receives real-time progress updates

FastAPI (Backend)
    ↓ Validates Clerk JWT on every request
    ↓ Stores config in PostgreSQL via Supabase
    ↓ Stores OAuth tokens in Secrets Manager — never in plain DB
    ↓ Queues agent tasks via Celery + Redis
    ↓ Streams progress back via Server-Sent Events
    ↓ Returns confirmation or structured error to frontend
```

---

### Onboarding Step Breakdown

**Step 0 — Welcome Screen**
- What this product does in two sentences
- Social login via Clerk — Google or GitHub OAuth
- No forms, no password, no friction
- Backend: creates user and org record on first login via Clerk webhook

**Step 1 — Account Setup**
- Name, company name, role (PM / Founder / Stakeholder / Other)
- Under four fields total
- Backend: POST /v1/onboarding/account — saves org profile

**Step 2 — Connect Repository**
- Toggle between GitHub and GitLab
- OAuth button — opens provider permission screen in browser
- After auth: dropdown to select which repo to connect
- Shows repo name and last commit date as confirmation it worked
- Trust signal displayed — "Your agent works in branches only, never touches main"
- Backend: POST /v1/onboarding/repo — stores token in Secrets Manager, saves repo selection

**Step 3 — Connect Jira**
- Input field for Jira workspace URL
- OAuth connect button
- After auth: dropdown to select which project to link
- Optional: select which ticket statuses mean "ready for the agent"
- Backend: POST /v1/onboarding/jira — stores token, saves project key and status mappings

**Step 4 — Connect Slack**
- OAuth connect button
- After auth: dropdown to pick notification channel
- Live preview of what an agent update message will look like in that channel
- Backend: POST /v1/onboarding/slack — stores token and channel ID

**Step 5 — Connect Docs (Optional)**
- Toggle between Confluence and Google Drive
- OAuth connect
- Pick a space or folder the agent is allowed to read
- Clearly marked optional with a prominent skip button
- Backend: POST /v1/onboarding/docs — stores token and access scope

**Step 6 — Set Agent Capabilities**
- Checkbox groups organised by category with plain English labels — no jargon
- Categories and defaults:

```
BUILDING
☑ Implement UI screens
☑ Build API connections
☑ Write unit tests
☐ Database schema changes        ← off by default
☐ Infrastructure changes         ← off by default

PLANNING
☑ Create Epics from documents
☑ Create Jira tickets
☑ Estimate story points
☐ Reprioritise existing backlog  ← off by default

REVIEW
☑ Create Pull Requests
☑ Review PRs and leave comments
☐ Approve and merge PRs          ← always off, human-only

COMMUNICATION
☑ Post Slack progress updates
☑ Ask clarifying questions via Slack
☑ Read meeting transcripts
☐ Join live meetings             ← off by default
```

- Backend: POST /v1/onboarding/capabilities — saves config consumed by Guardrails Agent at runtime

**Step 7 — Set Guardrails**
- "Which folders or files should the agent never touch?" — plain text input, e.g. /payments, /auth
- "Maximum files changed per task?" — number input, default 10
- Risk level preference — Conservative / Balanced / Aggressive — radio or slider
- Backend: POST /v1/onboarding/guardrails — saves rules enforced by Guardrails Agent

**Step 8 — Name Your Agent**
- Text input — what do you want to call your developer?
- Name suggestions: Forge, Relay, Scout, Hatch, Stride
- Avatar picker — icon or illustration
- This step is intentional — naming makes the experience feel like hiring, not configuring
- Backend: POST /v1/onboarding/agent — saves name and avatar

**Step 9 — Tell Agent About Your Project**
- Plain English textarea — no technical knowledge required
- Prompted with three questions shown as placeholder text:
  - What does your product do?
  - What tech stack are you using? (rough is fine — "I think it's React")
  - Anything the agent should never do?
- This text is injected into every agent's system prompt as project context
- Backend: POST /v1/onboarding/context — saves project description

**Step 10 — Shadow Teammate Mode (Placeholder)**

> **[PLACEHOLDER — Design and scope TBD]**
>
> During onboarding, the agent observes your existing team's workflow before taking any autonomous action. This "shadow mode" allows the agent to learn patterns, conventions, and working styles from real activity before being given independent tasks.
>
> **Potential behaviours to define:**
> - Agent is added to the Jira project and GitHub repo in read-only mode
> - Observes open PRs, review comments, commit patterns, and ticket descriptions for a defined period (e.g. one sprint)
> - Reads past merged PRs to understand what reviewers approve vs. reject
> - Attends Slack threads and meeting transcripts without posting
> - Builds an initial Memory pack from observed patterns before the first task is assigned
> - User sees a "Your agent is learning from your team" progress view during this window
> - Shadowing period ends when confidence threshold is met or user manually activates the agent
>
> **Open questions:**
> - How long should the shadow period last? User-configurable or fixed?
> - What is the minimum data needed before the agent is considered "ready"?
> - Should shadowing be skippable for teams with no existing history?
> - How do we show the user what the agent has learned in a non-technical way?
> - Does shadow mode replace or supplement Step 10 (Agent Reads Your Setup)?

**Step 11 — Agent Reads Your Setup**
- Full-screen animated progress moment — high-value UX beat, invest in this screen
- Shows the agent getting up to speed in real time:
  - Repo connected and scanned
  - Jira project loaded, past tickets analysed
  - Velocity and story point patterns identified
  - Slack channel confirmed
  - Capabilities and guardrails saved
  - Shadow learning complete (if shadow mode ran)
  - Agent is ready
- Backend: GET /v1/onboarding/status — streams validation events via SSE
- Any invalid token or failed connection surfaces here — user can click to go back and fix

**Step 12 — Dashboard (Post Onboarding)**
- Agent name and avatar at the top — feels like a team member, not a settings panel
- Integration status row — green ticks for everything connected
- Large plain English task input field front and centre
- Optional Jira ticket ID field to link the task to an existing ticket
- Recent task history — what the agent has done, current status, links to PRs
- Pause agent toggle — suspends the agent without disconnecting integrations
- Backend: GET /v1/dashboard — returns agent config, task history, integration health

---

### Key Frontend Rules

- **OAuth always** — never ask users to paste API keys or tokens. If a service does not support OAuth, show a "Need help? Invite your developer" option instead
- **Never show code** — no diffs, no file paths, no terminal output anywhere. Always translate to plain English
- **Progress bar on every step** — 12 steps feels manageable when there is a clear visual indicator. Show step X of 12 throughout
- **Every step skippable where sensible** — only repo connection is truly required to proceed. Everything else has a skip option
- **Trust signals throughout** — non-technical users are cautious about repo access. Reinforce what the agent can and cannot do at every relevant step
- **Server-side rendering for speed** — use Next.js server components for dashboard and task history pages so they load fast without client-side waterfalls

---

### API Endpoints Summary

| Method | Endpoint | What it does |
|---|---|---|
| POST | /v1/onboarding/account | Save user and org profile |
| POST | /v1/onboarding/repo | Store GitHub/GitLab OAuth token and repo selection |
| POST | /v1/onboarding/jira | Store Jira OAuth token and project config |
| POST | /v1/onboarding/slack | Store Slack token and notification channel |
| POST | /v1/onboarding/docs | Store Confluence/Google Drive token and scope |
| POST | /v1/onboarding/capabilities | Save agent capability selections |
| POST | /v1/onboarding/guardrails | Save restricted paths and risk level |
| POST | /v1/onboarding/agent | Save agent name and avatar |
| POST | /v1/onboarding/context | Save project description for system prompt |
| POST | /v1/onboarding/complete | Mark onboarding complete, activate agent |
| GET | /v1/onboarding/status | Validate all connections, stream readiness via SSE |
| GET | /v1/dashboard | Return agent config, task history, integration health |
| POST | /v1/task | Submit a new task to the agent pipeline |
| GET | /v1/task/:id | Get task status and result |
| SSE | /v1/task/:id/stream | Stream real-time progress events for a task |

---

## How Agents Fit Together

Every task flows through a structured pipeline. Agents are not called randomly — each one has a defined role, a clear input, and a specific output that feeds the next agent in the chain.

```
User Task
    ↓
[ 1. Task Router ]         — decides which agents are needed
    ↓
[ 2. Context Builder ]     — assembles codebase awareness before any reasoning begins
    ↓
[ 3. Guardrails Agent ]    — validates scope and classifies risk before touching anything
    ↓
[ 4. Clarification Agent ] — asks questions if intent or requirements are ambiguous
    ↓
[ 5. Planner Agent ]       — breaks task into subtasks and produces Definition of Done
    ↓
[ 6. Coder Agent ]         — implements the code against the plan and context
    ↓
[ 7. Tester Agent ]        — writes unit and integration tests for all implementation
    ↓
[ 8. Execution Verifier ]  — runs build, tests, and lint. Triggers fix loops on failure
    ↓
[ 9. Reviewer Agent ]      — critic pass against Definition of Done before PR is created
    ↓
[ 10. Doc Agent ]          — reads PRDs and generates structured Jira backlogs
    ↓
[ + Memory Agent ]         — runs after completion to record patterns and learnings
    ↓
Output: PR created → Jira updated → Slack notified
```

---

## Autonomy Expectation

In well-scoped scenarios, the agent can complete tasks end-to-end within minutes while requiring minimal human involvement, with built-in guardrails and review visibility at every meaningful checkpoint. Human approval is always required before a PR is merged.

---

## Step 1 — Task Router

**What it does**
The entry point for every task. Reads the plain English input and decides which agents are needed and in what order. Uses a fast, cheap model — this step is classification only, not reasoning.

**When it runs**
Always. First agent called on every task.

**Input**
- Plain English task description from the user

**Output**
- Ordered list of agents to invoke
- Complexity classification — simple, medium, or complex
- Estimated number of steps

**Routing logic examples**

| Task | Agents Selected | Complexity |
|---|---|---|
| "Fix the login button color" | Coder | Simple |
| "Add forgot password screen" | Context Builder → Guardrails → Clarification → Planner → Coder → Tester → Verifier → Reviewer | Medium |
| "Build full authentication system" | Full pipeline | Complex |
| "Review PR #42" | Context Builder → Reviewer | Simple |
| "Upload PRD and create tickets" | Doc Agent → Jira Agent | Medium |

**Model used**
Cheapest available — routing is pattern recognition, not deep reasoning.

---

## Step 2 — Context Builder (Memory Pack Creation)

**What it does**
Before any planning or coding begins, the Context Builder assembles a focused context bundle that gives downstream agents accurate awareness of the codebase. This is the difference between generic AI output and output that actually fits your project.

**When it runs**
Immediately after routing, before the Planner or Coder sees anything.

**What it assembles**

- Relevant repository files related to the task area
- Coding conventions and style guides from the repo
- Design system references — component libraries, naming patterns, theme tokens
- Previous PR patterns related to similar tasks
- Ticket acceptance criteria from Jira if a ticket ID is provided
- Recent reviewer comments on related code areas
- Any memory records from previous similar tasks (fed from the Memory Agent)
- Patterns observed during shadow teammate mode if it ran during onboarding

**Why this matters**
Without this step, agents reason generically. With it, they reason about your specific codebase. A coder that knows your auth module structure, your component library, and your team's naming conventions produces dramatically better output than one working from scratch.

**Input**
- Task description
- Repo access via GitHub integration
- Jira ticket ID (optional)
- Memory store from previous tasks and shadow mode observations

**Output**
- A structured context bundle passed to every downstream agent
- List of relevant files identified
- Summary of applicable conventions
- Related PR patterns found

**Model used**
Mid-tier — needs to understand code structure but does not need the most powerful model.

---

## Step 3 — Guardrails Agent (Scope Validation)

**What it does**
Before any implementation begins, the Guardrails Agent validates that the task is within allowed boundaries. This limits blast radius, increases trust, and prevents the agent from touching areas of the codebase it should not.

**When it runs**
After context is built, before clarification or planning begins. Acts as a gate.

**What it checks**

- **Allowed repositories and directories** — is this task in scope for the agent?
- **Restricted areas** — authentication logic, payment processing, database migrations, and other high-risk zones that require human ownership
- **PR size constraints** — flags tasks likely to produce oversized diffs that are hard to review
- **Task risk classification** — low, medium, or high risk based on what is being changed
- **Dependency changes** — does this task require adding or modifying external dependencies?

**Output**

- Green light to proceed, or
- Blocked with a clear reason sent to Slack and Jira
- Risk classification attached to all downstream context
- PR size estimate

**If blocked**
The task is paused. The user is notified via Slack with a plain English explanation of why the agent cannot proceed and what human input is needed.

**Model used**
Cheap fast model — rule-based validation with light reasoning.

---

## Step 4 — Clarification Agent

**What it does**
If required information is missing or the task is ambiguous, this agent asks targeted questions before any planning or coding begins. Prevents incorrect assumptions from cascading through the entire pipeline.

**When it runs**
After guardrails pass. Only activates when ambiguity is detected — skipped entirely for well-scoped tasks.

**What triggers clarification**

- Platform or framework is not confirmed — React Native vs web, iOS vs Android
- Existing API endpoints are referenced but not specified
- UI component preference is unclear — build new or use existing design system component
- Acceptance criteria are missing or vague
- Conflicting requirements detected between the task and existing code context

**How it works**
Rather than asking everything at once, it asks the minimum set of questions needed to proceed. Questions are sent to the user via Slack in plain English. The task is paused until answers are received.

**Input**
- Task description
- Context bundle from Context Builder
- Identified ambiguities

**Output**
- Set of targeted questions posted to Slack, or
- Confirmation that no clarification is needed and the pipeline can proceed

**Model used**
Mid-tier — needs to reason about what is missing, not just classify.

---

## Step 5 — Planner Agent

**What it does**
Takes the task, the context bundle, and any clarification answers, then produces a structured implementation plan and a Definition of Done checklist that all downstream agents must satisfy.

**When it runs**
After clarification is resolved. Only invoked for medium and complex tasks — simple tasks go directly to the Coder.

**What it produces**

**Implementation Plan**
- Ordered list of subtasks with assigned agent type for each
- Estimated files to be created or modified
- External dependencies or APIs required
- Identified risks or unknowns

**Definition of Done**
A structured checklist that downstream agents use to verify completeness. Typical items include:

- UI implemented and matches design references
- Navigation wired correctly
- API integrated and error states handled
- Form validation implemented
- Unit tests written and passing
- Accessibility requirements considered
- Edge cases identified and handled
- No hardcoded values or credentials

This checklist is passed to the Reviewer Agent as the acceptance standard against which the implementation is evaluated.

**Input**
- Task description
- Context bundle from Context Builder
- Clarification answers if applicable
- Repo structure

**Output**
- Ordered subtask plan
- Definition of Done checklist
- Risk flags

**Model used**
Most powerful available — deep reasoning is required here. Quality of the plan directly determines quality of everything downstream.

---

## Step 6 — Coder Agent

**What it does**
The primary implementation agent. Takes the plan, context bundle, and Definition of Done, then writes production-ready code. Returns structured output that maps directly to GitHub actions.

**When it runs**
After planning for complex tasks, or directly after context and guardrails for simple tasks.

**What it produces**

- Branch name following your naming conventions
- Complete file contents for every file created or modified — never partial snippets
- Commit message
- PR title
- PR description written in plain English for non-technical reviewers
- One-line Slack summary for stakeholders
- Clarification request if something critical is still unclear

**Key behaviors**

- Never writes directly to main — always branches
- Always writes complete file contents, not diffs or snippets
- PR description is always written for a non-technical audience
- If the Definition of Done cannot be fully satisfied, it flags which items are incomplete rather than silently skipping them
- Uses context bundle to match existing patterns, component names, and conventions

**Input**
- Task description
- Implementation plan from Planner
- Definition of Done checklist
- Context bundle — relevant files, conventions, design system, previous PR patterns

**Output**
- Branch name
- All file paths and complete contents
- PR title and plain English description
- Slack summary
- Incomplete DoD items flagged if any

**Model used**
Strong mid-tier — needs to be good at code but speed matters here. Powerful model reserved for planning.

---

## Step 7 — Tester Agent

**What it does**
Writes comprehensive unit and integration tests for everything the Coder produces. Tests are committed to the same branch before the PR is created.

**When it runs**
Immediately after the Coder completes. Runs before verification and review.

**What it covers**

- Happy path for all new functions and components
- Edge cases and boundary conditions
- Error handling and failure states
- Input validation
- Integration points with APIs or external services

**What it flags**
If certain areas cannot be tested without additional context — mocked dependencies, external services, database state — the Tester flags these explicitly rather than skipping them silently.

**Input**
- All files produced by the Coder Agent
- Definition of Done checklist — specifically the test requirements
- Context bundle — existing test patterns and frameworks in the repo

**Output**
- Complete test files ready to commit
- Coverage summary
- Explicit list of anything that could not be tested and why

**Model used**
Mid-tier — needs to understand testing patterns but not the most expensive model.

---

## Step 8 — Execution Verifier

**What it does**
After code and tests are written, the Execution Verifier runs the actual build, executes the tests, and runs lint checks in an isolated sandbox. This ensures the output is not just syntactically plausible — it actually works.

**When it runs**
After the Tester Agent completes. Before the Reviewer sees anything.

**What it runs**

- Build process — confirms the project compiles or bundles without errors
- Full test suite — confirms all tests pass including newly written ones
- Lint and formatting checks — confirms code meets style requirements
- Type checks if the project uses TypeScript or typed Python

**Failure behavior**
If any check fails, the Verifier does not just report the failure — it triggers a fix iteration. The failure details are passed back to the Coder Agent with the specific errors. The Coder attempts a fix and the verification loop runs again. This continues for a defined number of iterations before escalating to a human.

**Escalation**
If failures persist after the maximum retry count, the task enters the Failure Handling pathway — execution pauses, the user is notified with a plain English summary of what failed and why, and partial progress is preserved.

**Input**
- All files from Coder and Tester Agents
- Isolated sandbox environment — E2B or equivalent
- Build and test commands from repo configuration

**Output**
- Pass confirmation, or
- Specific failure details triggering a fix loop, or
- Escalation to Failure Handling pathway

**Model used**
Lightweight — this is primarily execution and error parsing, not generation.

---

## Step 9 — Reviewer Agent (Critic Pass)

**What it does**
A final automated critic pass that evaluates the complete implementation against the Definition of Done before a PR is created. Catches quality issues, regressions, and missing coverage before any human sees the output.

**When it runs**
After the Execution Verifier confirms the build passes. Final check before GitHub actions are taken.

**What it evaluates**

- Adherence to the Definition of Done checklist item by item
- Code quality patterns — naming, structure, readability, duplication
- Potential regressions — changes that might break existing functionality
- Missing test coverage relative to what the Tester flagged as incomplete
- Risk indicators — hardcoded values, missing error handling, security concerns
- Alignment with conventions identified in the context bundle

**Output**

- Approved — PR creation proceeds
- Changes requested — specific issues sent back to the Coder for revision, triggering another loop
- Plain English verdict for the PR description — one sentence stakeholders can read
- Inline review comments attached to the PR once created

**Revision loop**
If the Reviewer requests changes, the specific issues are passed back to the Coder. The Coder revises, the Verifier runs again, and the Reviewer evaluates again. This loop has a maximum iteration count before escalating to a human.

**Input**
- All files from Coder and Tester Agents
- Definition of Done checklist from Planner
- Context bundle — conventions and previous PR patterns
- Execution Verifier results

**Output**
- Approval or revision request
- Specific inline comments
- Plain English summary for PR and Slack

**Model used**
Strong mid-tier — needs to reason about code quality and completeness.

---

## Step 10 — Doc Agent

**What it does**
Reads uploaded requirements documents — PRDs, Confluence pages, Google Docs, or plain text — and generates a complete structured Jira backlog including epics, stories, story points, and acceptance criteria.

**When it runs**
Invoked independently when a user uploads a document rather than submitting a code task. Replaces the Planner in the document-to-backlog flow.

**What it produces**

- Epics grouped by feature area
- Stories under each epic with clear titles and descriptions
- Acceptance criteria per story
- Story point estimates based on historical Jira velocity if available
- Estimated sprint count for the full backlog
- Risk flags — unknowns, external dependencies, items needing clarification

**Story point calibration**
If past Jira tickets are available, the Doc Agent analyzes historical patterns — average points per story type, team velocity, complexity distribution — and uses this to calibrate estimates rather than guessing generically.

**Human review gate**
The generated backlog is always presented to the user for review and editing before any tickets are created in Jira. Epics and stories can be modified, reordered, or removed. Nothing is created in Jira without explicit approval.

**Input**
- Uploaded document content
- Historical Jira ticket data for estimation calibration (optional)
- Project context

**Output**
- Structured backlog presented for human review
- On approval: epics and stories created in Jira with correct fields, story points, and links

**Model used**
Most powerful available — requires deep reading comprehension and structured reasoning across long documents.

---

## Supporting Agent — Memory Agent (Write-Back)

**What it does**
Runs after every completed task or after reviewer feedback is received. Records what was learned so future tasks benefit from accumulated experience.

**When it runs**
After PR is merged or after human reviewer leaves feedback — not blocking the main pipeline.

**What it records**

- Successful implementation patterns for this repo and task type
- Reviewer comments and what triggered them — fed back to improve future Coder output
- Pitfalls encountered during the task — build failures, wrong assumptions, retry patterns
- Convention updates discovered — new patterns found in the codebase
- Clarification questions that were needed — used to improve future ambiguity detection
- Observations from shadow teammate mode if active during onboarding

**Traceability**
Every memory record is linked to its source — the task ID, the PR, the reviewer comment, or the failure log. Nothing is stored as anonymous tribal knowledge.

**Impact on future tasks**
The Context Builder reads from this memory store when assembling context bundles. Over time the system becomes increasingly calibrated to your specific codebase, team conventions, and reviewer preferences.

---

## Supporting Flow — Failure Handling Pathway

**What it does**
When the system cannot safely complete a task — after maximum retries, unresolvable ambiguity, or guardrail violations — it enters a structured failure pathway rather than producing low-quality output silently.

**Triggers**

- Execution Verifier failures exceed maximum retry count
- Reviewer Agent revision loop exceeds maximum iteration count
- Guardrails Agent blocks the task
- Clarification questions go unanswered beyond a timeout threshold
- Coder Agent detects a situation it cannot safely handle

**What happens**

1. Execution pauses immediately — no partial commits or broken branches
2. A plain English summary of the blocker is composed — what was attempted, what failed, what is needed
3. The user is notified via Slack with the summary and specific questions
4. Partial progress is preserved — any valid work completed so far is saved and can be resumed
5. The task sits in a paused state until human input is provided

**Goal**
No silent failures. No low-quality PRs that waste reviewer time. Either the agent completes the task properly or it stops, explains clearly, and hands off to a human with full context.

---

## Cost Expectations

Costs vary based on context size, number of retry iterations, and model routing decisions. The estimates below reflect a typical well-scoped task with no retries.

| Agent | Model Tier | Cost Driver |
|---|---|---|
| Task Router | Cheapest | Minimal tokens, classification only |
| Context Builder | Mid-tier | Repo file reading, context assembly |
| Guardrails Agent | Cheapest | Rule-based with light reasoning |
| Clarification Agent | Mid-tier | Only runs when ambiguity exists |
| Planner Agent | Most powerful | Deep reasoning — highest per-token cost |
| Coder Agent | Strong mid-tier | Largest output — most tokens generated |
| Tester Agent | Mid-tier | Moderate output volume |
| Execution Verifier | Lightweight | Execution and parsing, minimal generation |
| Reviewer Agent | Strong mid-tier | Reasoning over code and checklist |
| Doc Agent | Most powerful | Long document comprehension |
| Memory Agent | Cheapest | Structured write, minimal reasoning |

**Important caveats**
- Costs increase with context size — larger repos and longer documents cost more to process
- Retry loops multiply costs — a task that requires three verification cycles costs roughly three times the base estimate
- Routing optimization reduces costs significantly over time as simple tasks are correctly identified and skip expensive agents
- POC task costs remain low relative to the developer time they replace — the value comparison is always cost per task versus hourly developer rate

---

## Agent Interaction Summary

```
Task Input
    ↓
Router ──────────────────────────────────── decides pipeline shape
    ↓
Context Builder ─────────────────────────── assembles codebase awareness
    ↓
Guardrails Agent ────────────────────────── validates scope and risk
    ↓                                              ↓ if blocked
Clarification Agent ─────────────────────── resolves ambiguity      → Slack (paused)
    ↓                                              ↓ if unanswered
Planner Agent ───────────────────────────── plan + Definition of Done
    ↓
Coder Agent ─────────────────────────────── implementation
    ↓
Tester Agent ────────────────────────────── tests
    ↓
Execution Verifier ──────────────────────── build + test + lint
    ↓ if fails ←──────────────────────────── fix loop (max retries)
    ↓                                              ↓ if max retries
Reviewer Agent ──────────────────────────── DoD critic pass     → Failure Pathway
    ↓ if changes ←────────────────────────── revision loop      → Slack (paused)
    ↓
GitHub ──────────────────────────────────── branch + commit + PR
    ↓
Jira ────────────────────────────────────── status update + PR link
    ↓
Slack ───────────────────────────────────── plain English notification
    ↓
Memory Agent ────────────────────────────── write-back (async, non-blocking)
    ↓
Human reviews and approves PR
```

---

> Each agent has one job. No agent does more than its defined role. The pipeline is the product.
