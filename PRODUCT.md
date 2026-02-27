# Kronode — Product Definition

## Core Vision

Kronode is the first AI teammate that gains tenure inside engineering organizations. It is not a tool humans use — it is a persistent organizational actor that lives inside a company's workflow, executes real engineering work, and compounds in value over time. Every interaction makes it smarter about the specific team it works with.

## The Problem

Every AI developer tool today is stateless. They help individuals work faster but they have no persistent existence inside an organization. They don't remember, they don't learn, they don't grow. When you close the session everything is gone. Companies get no compounding value over time.

## The Core Promise

An AI teammate that gains tenure. The second ticket is better than the first. The tenth is better than the fifth. Over time Kronode becomes the most knowledgeable entity about your codebase — more than any individual engineer who has ever worked there.

## What Kronode Does

**Lives inside your existing workflow** without you changing anything. It reads your tickets, participates in standups, communicates in Slack, writes code, opens PRs, and responds to feedback — exactly like a human teammate would.

**Onboards itself.** Point it at your codebase and within 48 hours it understands your conventions, patterns, and architecture without you having to document anything or answer setup questions.

**Executes tickets end to end.** From reading the ticket to opening the PR with no human involvement required unless the agent explicitly asks for it.

**Communicates before it codes.** Before writing a single line it posts its plan, the files it will touch, its assumptions, and its confidence level. Engineers stay in control without doing the work.

**Participates in standups autonomously.** Every morning it posts what it did yesterday, what it's doing today, and flags any blockers — just like every other team member.

**Monitors the backlog proactively.** It doesn't wait to be assigned. It notices unassigned work and volunteers to take it.

**Never repeats a mistake.** Every correction from a code reviewer gets stored and applied permanently to future work in that codebase.

**Learns individual engineers.** It knows what each reviewer cares about and addresses their concerns before they raise them.

**Builds a verifiable career profile.** Every codebase worked in, every PR merged, every acceptance rate tracked — a quantified performance record no human contractor or AI tool can match.

## What Makes It Different

Devin, Factory, Sweep, and GitHub Copilot Workspace are all stateless task executors. They start fresh every time. They have no memory, no accumulating context, no compounding value. They are faster humans, not organizational actors.

Kronode is the only product built around the idea that an AI developer should gain tenure — that it should become more valuable the longer it works with a team, just like a great human engineer would.

## The Buying Decision

Kronode is not bought as software. It is hired as a teammate. It comes out of headcount budget not software budget. The question a CTO asks is not "should we buy this tool" but "should we hire this agent." That reframe is intentional and fundamental to everything we build.

## Core Product Principles

- **Transparency before action** — always show reasoning before executing. Trust is earned through visibility not just results.
- **Memory is the moat** — every feature should contribute to the agent getting smarter over time.
- **Workflow native** — the company changes nothing, Kronode adapts to them.
- **Proactive not reactive** — a great teammate doesn't wait to be told what to do.
- **Honest about limitations** — the agent flags its own uncertainty rather than proceeding with false confidence.

## Agent Profiles

Kronode is not a single generic agent. When an organisation hires Kronode they select a **developer profile** — a specialist with a defined tech stack, a scoped domain of knowledge, and world-class skills within that domain. The agent's scope is enforced: it will not write mobile code if hired as a backend engineer, just as a human specialist wouldn't.

### Available Profiles

| Profile | Stack | Scope |
|---------|-------|-------|
| **Web Engineer** | React / Next.js / TypeScript / Tailwind / REST | Frontend components, routing, state, API integration |
| **Backend Engineer** | Python / FastAPI / PostgreSQL / Redis / Celery | APIs, data models, background jobs, auth |
| **Mobile Engineer (iOS)** | Swift / SwiftUI / Xcode / Combine | iOS screens, navigation, local storage, API calls |
| **Mobile Engineer (Android)** | Kotlin / Jetpack Compose / Android SDK | Android screens, viewmodels, Room, API calls |
| **Full-Stack Engineer** | Next.js + FastAPI or Rails or Node | End-to-end features across frontend and backend |
| **DevOps Engineer** | Docker / Kubernetes / Terraform / GitHub Actions / AWS | CI/CD pipelines, infra-as-code, deployments, monitoring |
| **Data Engineer** | Python / dbt / Airflow / Snowflake / Spark | Pipelines, transformations, data models, orchestration |

### How Profiles Work

**At hire (onboarding):** The team selects the profile that matches the open role. The profile sets:
- The system prompt injected into every agent in the pipeline — written as if the agent is a world-class specialist in that stack
- The guardrails scope — which directories and file types the agent is allowed to touch
- The context builder priorities — which file extensions and patterns to treat as relevant
- The router's complexity thresholds — what "simple" vs "complex" means for that stack

**Specialisation over time:** Memory records are profile-scoped. A Web Engineer Kronode accumulates React conventions, component patterns, and reviewer preferences specific to frontend work. This specialisation compounds faster than a generic agent would.

**World-class skill injection:** Each profile's system prompt is written to embed the highest standards of that discipline — not just syntax knowledge but engineering judgement. For example:
- Web profile: accessibility, Core Web Vitals, component composition, performance
- Backend profile: idempotency, schema migrations, query optimisation, error handling patterns
- DevOps profile: least-privilege IAM, immutable infra, rollback safety, secret management

**Scope enforcement:** Guardrails Agent reads the active profile and blocks work outside the declared domain. A DevOps agent will decline to modify application code. A Mobile agent will not touch backend services. This matches how real teams work — specialists stay in their lane.

### Multi-Profile Orgs

Larger organisations can hire multiple Kronode agents simultaneously, each with a different profile. They share the same Jira and Slack integration but operate in separate guardrailed domains. A ticket tagged `platform` goes to the DevOps agent; a ticket tagged `web` goes to the Web Engineer.

---

## North Star Metrics

1. **Time to first merged PR** — proves fast onboarding
2. **PR acceptance rate improvement over time per customer** — proves compounding value

These two metrics together prove the core promise.
