# CLAUDE.md — Kronode Project Context

## What Is Kronode

Kronode is a persistent AI teammate that gets assigned engineering tickets during sprint planning, ships code within team-set guardrails, and builds organizational memory that makes every sprint better than the last. It is not a coding agent — it is an orchestration and organizational intelligence layer that wraps external coding agents (Claude Agent SDK, OpenAI Codex) to make their output team-aware.

## Core Identity

Kronode behaves like the best junior-to-mid engineer you've ever worked with. It doesn't try to solve problems beyond its ability — it asks for help. It learns fast from feedback and doesn't repeat the same mistakes. It's self-aware about what it knows and what it doesn't. It picks up the work nobody else wants to do and does it reliably. It gradually earns more responsibility because it's proven it can handle it.

The knowledge — because of the organizational memory — is beyond any individual on the team. No junior engineer has read every PR, every incident report, every review comment in the company's history. Kronode has. It combines the judgment and humility of a good junior with the institutional knowledge of someone who's been at the company for five years.

## Core Principles

1. **Memory is the moat.** Every feature should contribute to Kronode getting smarter over time. The organizational model is not a feature — it is the product's soul.
2. **Transparency before action.** Always show reasoning before executing. Trust is earned through visibility, not just results.
3. **Honest about limitations.** Kronode flags its own uncertainty rather than proceeding with false confidence. Below confidence threshold, it steps back and assists rather than producing bad output.
4. **Workflow native.** The company changes nothing. Kronode adapts to them. It lives in Slack, ticket comments, and PR discussions — not a standalone UI.
5. **Kronode never auto-picks work.** Only works on tickets explicitly assigned to it. The team controls what flows in and what flows out.
6. **Kronode is a sprint participant.** Receives tickets during planning like any other team member. Works at the pace the team sets, never overloads reviewers with unexpected PRs.
7. **Kronode is direct and concise.** Every message reads like a competent engineer wrote it. No filler, no hedging, no corporate tone.
8. **Learns from every review.** Every correction from a code reviewer gets stored and applied to future work in that codebase. Corrections compound — the same feedback should never need to be given twice in the same context.

## Self-Onboarding

Kronode onboards itself by analyzing your PR history, codebase structure, and review culture. No setup questionnaires, no configuration wizards, no documentation requirements. Point it at your repos and it starts learning. The more history available, the faster it ramps. On day one, the base knowledge layer for your stack means Kronode already follows community best practices. By week two, the customer-specific layer kicks in and it starts following your team's patterns.

## North Star Metrics

1. **Time to first merged PR** — proves fast onboarding and immediate value.
2. **PR acceptance rate improvement over time per customer** — proves compounding value and the organizational memory working.

Every feature and decision should be evaluated against whether it improves one of these two numbers.

## One-Line Pitch

"Kronode knows everything about how your team builds software. It starts by helping. Over time, it starts shipping."

## What Kronode Is NOT

- Not a coding agent. The Agent SDK does the coding. Kronode orchestrates it.
- Not autonomous. Never acts without assignment and approval.
- Not a replacement for engineers. Infrastructure that makes engineers more effective.
- Not a dashboard product. The dashboard exists for setup and leadership oversight. The product is the presence in existing tools.
- Not a Copilot/Cursor competitor. Those serve individual developers in IDEs. Kronode serves the team in their workflow.

---

## Architecture

### The Key Insight

Don't build Claude Code. Use Claude Code. Kronode's value is not the coding — it's the context it feeds the coding agent and the knowledge it accumulates over time. Same LLM, dramatically better output because the input is richer.

### Four Layers

**Layer 1 — Event Stream:** Continuous ingestion of tickets, PRs, review comments, Slack messages. Always running, always learning, never acting on its own.

**Layer 2 — Organizational Model:** Structured, queryable, human-readable knowledge base. Services, conventions, people, incidents. This is the moat. Everything exportable.

**Layer 3 — Execution Engine:** Thin wrapper around Claude Agent SDK (primary) or OpenAI Codex (secondary). Replaceable. Behind a clean interface so the underlying agent can be swapped.

**Layer 4 — Feedback Loop:** Every review, merge, rejection feeds back into Layer 2. This is what makes it compound.

### Module Pipeline

```
Ticket Assigned → Ticket Interpreter → Context Assembler → Plan Generator
→ [HUMAN APPROVAL] → Execution Engine (Agent SDK) → PR Manager → Feedback Engine
```

### Modules and Current State

| Module | Status | Purpose |
|--------|--------|---------|
| Integration Layer | ✅ Built | Dashboard with Jira, GitHub, Slack connectors |
| Agent Profiles | ✅ Built | Customer creates agents, picks skill sets from library. Composable, not fixed profiles |
| Execution Engine | ✅ Built (basic) | Takes Jira ticket, generates code, opens PR |
| PR Manager | ✅ Partial | Creates branch, opens PR. Needs structured descriptions, reviewer assignment, review comment handling |
| Ticket Interpreter | 🔨 Next | Parses messy tickets into structured task definitions. Posts clarifying questions if needed |
| Context Assembler | 🔨 Next | Queries Org Model, builds rich context injected into Agent SDK prompts |
| Plan Generator | 🔨 Next | Posts human-readable plan to Jira/Slack for approval before coding |
| Organizational Model | 🔨 Next | Convention Registry, Service Topology, People Model, Incident Memory |
| Feedback Engine | Not started | Captures review outcomes, extracts conventions, updates Org Model |

---

## Pre-Coding Pipeline (Current Focus)

Everything that happens between "ticket assigned" and "Agent SDK starts writing code." This is where the organizational intelligence lives and where the product differentiates. Currently Kronode passes Jira tickets more or less directly to the coding agent. The pre-coding pipeline changes that.

Three stages, built in order — each independently valuable:

**Stage 1: Ticket Interpretation.** Raw Jira ticket → structured task definition. Extracts requirements, scope, ambiguities. Posts clarifying questions if unclear. Uses cheap model (Gemini Flash / DeepSeek). Build first — standardizes input for everything downstream.

**Stage 2: Plan Generation.** Structured task → human-readable plan posted for approval. Files, approach, risks, assumptions, confidence. Posted to Jira + Slack, waits for explicit approval. Uses Sonnet-class model. Build second — the trust-building moment where the team sees Kronode's reasoning before it codes.

**Stage 3: Context Assembly.** Queries the Organizational Model and enriches the task with conventions, incident history, reviewer preferences, service topology. Injected into Agent SDK prompt. Build third, alongside convention extraction. As conventions accumulate, plans and PRs get smarter automatically.

### Confidence and Self-Awareness

Before posting a plan, Kronode assesses the ticket against its knowledge coverage:
- **High confidence:** Executes normally.
- **Medium confidence:** Executes but flags uncertainties explicitly.
- **Low confidence:** Does NOT attempt. Recommends a human take it. Offers to assist — share context, review the PR, write tests.

The assist mode is genuinely valuable. Kronode sharing what it knows without writing code is the organizational memory being useful even when execution can't help.

---

## Convention Extraction Pipeline

Runs in parallel with the pre-coding pipeline. Populates the Organizational Model that the Context Assembler queries. The more conventions extracted, the richer the context, the better the plans and PRs.

### Two-Layer Convention System

**Base Knowledge Layer (per profile/stack).** Extracted from high-quality open source repos (Cal.com + 2-3 others for TypeScript). Filtered for universal patterns — conventions that appear across multiple repos, not just one. These become the default starting conventions for any new customer on that stack. It's like a junior engineer who learned best practices before joining the team. Solves the cold start problem — Kronode follows TypeScript best practices from day one.

**Customer-Specific Layer.** Extracted from the customer's own PR history and reinforced through review feedback. Where customer conventions conflict with the base layer, the customer's version always wins. Where the base layer covers something the customer hasn't established a pattern for, the base provides a reasonable default.

### Transparency Between Layers

Kronode must be clear about where a convention came from. "Community best practice" versus "established in your PR #1204 by Sarah" are different levels of authority. If a team explicitly rejects a base convention, that rejection is permanent — never reapply it.

### Extraction Steps
1. Pull last 200+ merged PRs from GitHub. Store diffs, descriptions, review comments, reviewers, files.
2. Extract conventions via LLM: rule, examples, category (naming, error_handling, testing, logging, architecture, style).
3. Deduplicate and score by frequency.
4. For base layer: cross-reference across multiple repos. Only conventions appearing in 2+ repos qualify as universal.
5. For customer layer: present to team for validation — they can edit, delete, add.
6. Inject into execution via Context Assembler. Customer layer overrides base layer.
7. Review comments on Kronode PRs feed back — corrections update customer layer, rejected base conventions get permanently suppressed.

### Training Repo: Cal.com
TypeScript monorepo, Next.js, tRPC, Prisma. Thousands of PRs, active review culture, multiple opinionated contributors. Represents the kind of codebase early customers will have.

### Models for Convention Extraction
- **Prototyping:** Gemini 2.5 Flash free tier (10 RPM, 250 RPD)
- **Production:** DeepSeek V3.2 ($0.28/$0.42 per MTok)
- **Quality benchmark:** Claude Sonnet (run 20 PRs to compare)
- Gemini free tier limits could shrink at any time. Don't build production dependency on it.

---

## Communication Voice

1. First person sparingly. "Flagging: this migration has no rollback path" > "I want to flag that..."
2. One sentence when one sentence works.
3. Technical, not corporate.
4. Never apologize for limitations. "This touches auth — I need a human to handle it."
5. Never be sycophantic.
6. Reference specifics. "Using factory pattern per convention C-047 (from Sarah's review on PR #1204)"
7. Admit uncertainty clearly.
8. Questions are one message, all at once.

---

## Competitive Landscape

### Direct Competitors
- **Devin** — Closest. End-to-end ticket-to-PR, Slack/Linear integration. BUT: no organizational memory, no convention learning, no reviewer modeling. Starts fresh each time. $500/mo.
- **Augment Code** — Best on context/memory. Deep codebase understanding, persistent memory. BUT: IDE tool for individual developers, not team workflow.
- **Atlassian Rovo Dev** — Natural access to Jira's full history. Generates code, creates PRs. Watch closely — Atlassian has more organizational data than anyone.

### Adjacent Competitors
- **Greptile** — Learns team standards from PR comments. Review tool only, doesn't write code.
- **Qodo** — Organizational learning from PR history. Review/testing tool, not a coding agent.
- **CodeRabbit** — Trains from review feedback, creates learnings. Review tool only.

### Kronode's Position
Nobody occupies the intersection of: writes code + deep organizational memory + learns from reviews + operates as sprint participant in team workflow.

### Threat
Convergence. Devin adding memory. Augment adding execution. Rovo Dev improving. Window is 12-18 months.

---

## The Moat — Honest Assessment

### What IS defensible
- **Accumulated customer-specific data.** Can't clone 6 months of a team's review patterns, incident history, and convention evolution.
- **Feedback loop quality.** Hundreds of small decisions in convention extraction, contradictory signal handling, stale convention decay.
- **Time-in-seat.** First product a team trusts for 6 months.

### What is NOT defensible
- Convention extraction, review classification, incident cross-referencing, the schema itself — all replicable.

### Strategic implication
Lead with execution. Retain with memory. Move fast, get to customers early, iterate on loop quality obsessively.

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic migrations — managed with **uv**
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Zustand, Axios — managed with **pnpm**
- **Auth:** Clerk (JWT verification on backend)
- **Database:** PostgreSQL (async via asyncpg) with JSONB for Organizational Model
- **Queue:** Celery + Redis for async ticket processing, Celery Beat for scheduled tasks
- **Execution Agent:** Claude Agent SDK (primary), OpenAI Codex (secondary, planned)
- **LLM calls:** Anthropic API — Haiku for routing/classification, Sonnet for planning + code generation. Gemini Flash / DeepSeek for cheap batch work (convention extraction, ticket interpretation)
- **Integrations:** Jira (✅), GitHub (✅), Slack (✅), Confluence (✅)
- **Dashboard:** ✅ Built. Connector UI for Jira, GitHub, Slack, Confluence.
- **Deployment:** Docker Compose (local), production Docker planned
- **Config:** Environment variables (.env files)

---

## Business Context

### Team
Two senior full-stack dev cofounders. No ML/retrieval specialist — gap to fill via advisor (Vector Institute Toronto, Mila Montreal, Cohere alumni network). 0.25-0.5% equity for ongoing advisory.

### Location
Canada. Leverage Canadian funding programs aggressively.

### Funding Strategy (Non-Dilutive First)
1. **IRAP (NRC)** — Apply immediately. $50K-$500K for R&D salary costs. 4-8 week turnaround.
2. **SR&ED** — 35-64% tax credits on R&D spending. Retroactive. Bridge financing available (Venbridge, Easly).
3. **Cloud Credits** — Stack all three: Microsoft for Startups ($150K Azure), Google for Startups ($200K GCP), AWS Activate ($100K). Not mutually exclusive.
4. **Pre-seed** — Raise AFTER dogfood data + 1-2 design partners. Position of strength.

### Target Customers
20-50 person engineering teams using Jira/Linear + GitHub. TypeScript/Node stacks. Teams where organizational knowledge loss is acute: senior engineers recently left, fast scaling, high attrition, repeated incidents.

### Timeline
- ✅ DONE: Dashboard, Jira/GitHub/Slack integrations, Agent Profiles, basic ticket-to-PR pipeline
- NOW: Pre-coding pipeline + Convention Extraction on Cal.com
- Months 2-3: Memory connects to execution. Conventions feed Context Assembler.
- Months 3-5: Self-awareness + feedback loop. Confidence scoring.
- Months 5-7: Design partners on real codebases.
- Months 8-12: Convert to paying, raise seed if desired.

### Pricing
Not headcount. Not SaaS add-on. Likely $2-5K/month per team. Figure out after design partner feedback.

### Dogfooding
Build Kronode with Kronode. Critical path = humans. Lower-stakes tickets = Kronode. Document every failure.

---

## Agents and Skill Library (✅ Built)

Customers create their own agents and assign skill sets from a curated library. This replaces the fixed profile model with a composable one — customers assemble the right combination for their stack.

### How It Works

1. **Customer creates an agent.** Names it, connects it to their repos, configures integrations.
2. **Customer picks skills from the library.** Browses available skill sets and assigns the ones that match their stack. Example: a team using Next.js + Prisma + Vitest picks "TypeScript Conventions," "React Patterns," "Prisma ORM," and "Testing with Vitest."
3. **Skills become the agent's base knowledge.** The selected skills provide community best practices for that combination of technologies — the base knowledge layer.
4. **Customer-specific layer builds on top.** As Kronode works tickets and receives review feedback, it learns the team's own conventions. Customer conventions override base skills on conflict. Rejected base conventions stay rejected permanently.

### Why Composable Skills Beat Fixed Profiles

- No need for a separate profile for every stack permutation. Customers assemble their own.
- Teams with unusual stacks (e.g., Next.js frontend + Python backend) can mix skills across domains.
- New skills can be added to the library over time without changing existing agents.
- Each skill set is independently maintainable and improvable.

### Skill Library Growth

Each skill set is extracted from high-quality open source repos in that domain (e.g., TypeScript conventions from Cal.com + 2-3 other top TypeScript repos). The library gets richer over time, which makes Kronode useful to more teams, which attracts more customers. This is a compounding growth lever.

### Skill Sets Include

Per skill set:
- **Conventions:** Coding patterns, naming rules, file organization, error handling norms for that technology.
- **Engineering judgment:** Not just syntax — best practices that reflect world-class engineering. Accessibility for React. Idempotency for APIs. Least-privilege for IAM. Query optimization for ORMs.
- **Guardrails:** Scope boundaries — what file types and directories this skill applies to.
- **Context priorities:** Which file extensions and patterns the Context Assembler should treat as relevant when this skill is active.

### Planned Skill Sets

| Skill Set | Source Domain | Covers |
|-----------|-------------|--------|
| TypeScript Conventions | General TS patterns | Types, imports, error handling, async patterns |
| React Patterns | Component architecture | Components, hooks, state, accessibility, performance |
| Next.js | Full-stack React framework | Routing, server components, API routes, data fetching |
| Node.js Backend | Server-side JS | Express/Fastify patterns, middleware, error handling |
| Prisma ORM | Database access | Schema design, migrations, query patterns |
| REST API Design | API patterns | Endpoint structure, validation, error responses |
| Testing (Vitest/Jest) | Test patterns | Test structure, mocking, fixtures, coverage |
| Python Backend | FastAPI/Django | APIs, data models, async patterns |
| DevOps / IaC | Infrastructure | Docker, Kubernetes, Terraform, CI/CD |
| Mobile (Swift) | iOS development | SwiftUI, Combine, navigation |
| Mobile (Kotlin) | Android development | Jetpack Compose, ViewModels, Room |

### Current State
✅ Agent creation and skill assignment is built. Library starts with TypeScript-focused skill sets. Convention extraction pipeline (running on Cal.com) populates the initial skills. Library expands as more repos are analyzed.

---

## Key Product Decisions

1. ❌ Dropped the "hiring" metaphor — sets expectations too high, invites unfair comparison to humans.
2. ❌ No auto-picking tickets — presumptuous, creates surprise review work, undermines team authority.
3. ❌ Not building our own coding agent — use Agent SDK, compete on context not code generation.
4. ❌ No standup ceremony participation — contributes async (Slack, ticket comments), not in live meetings.
5. ❌ No "never repeats a mistake" promise — replaced with "learns from every review." Same spirit, no impossible guarantee.
6. ✅ Sprint participant — assigned work in planning, works within team-set capacity.
7. ✅ Lives in existing tools — Slack, Jira, GitHub. Company changes nothing.
8. ✅ Memory is the moat — foundation of product identity.
9. ✅ Honest about limitations — self-awareness as core feature.
10. ✅ Transparency before action — always posts plan, waits for approval.
11. ✅ Self-onboarding — onboards itself from PR history and codebase.
12. ✅ Exportable knowledge — customer keeps organizational knowledge if they leave.
13. ✅ Pre-coding pipeline is the current build focus.
14. ✅ Convention extraction as first memory feature.
15. ✅ Two-layer convention system — base layer from open source repos solves cold start, customer layer from their own PRs overrides and compounds. Customer always wins on conflicts. Rejected base conventions stay rejected.
15. ✅ TypeScript focus — implicit Full-Stack TypeScript profile.
16. ✅ Composable skill library — customers create agents and pick skills, not fixed profiles. Library grows over time as a compounding growth lever.
17. ✅ Cal.com as training repo for convention extraction.
18. ✅ Cheap models for batch analysis, good models for plan generation.
19. ✅ North star metrics — Time to first merged PR + PR acceptance rate improvement over time.
