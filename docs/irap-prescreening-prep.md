# Kronode — IRAP Pre-Screening Call Prep

## Elevator Pitch (30 seconds)

Kronode is an AI-powered software engineering teammate that integrates into a team's existing workflow — Jira, GitHub, Slack — to autonomously ship code from assigned tickets. Unlike existing AI coding tools, Kronode builds a persistent organizational memory from PR history, code reviews, and team conventions. It gets measurably better at writing code the way *your* team writes code, every sprint.

---

## The Problem

Engineering teams lose institutional knowledge constantly — through attrition, scaling, and context-switching. When a senior engineer leaves, years of "how we do things here" walks out the door. New hires take 3-6 months to ramp. AI coding tools (Copilot, Cursor) help individual developers autocomplete code, but they have zero awareness of team conventions, architectural decisions, or organizational context. Every session starts from scratch.

**The result:** AI-generated code that compiles but doesn't fit — wrong patterns, wrong conventions, wrong assumptions. Engineers spend more time reviewing and fixing AI output than they save.

---

## The Solution

Kronode sits between the ticket system and the coding agent. It doesn't build its own code generation — it wraps best-in-class coding agents (Anthropic's Claude Agent SDK) and enriches their input with deep organizational context.

**Four-layer architecture:**
1. **Event Stream** — Continuously ingests tickets, PRs, review comments, Slack messages
2. **Team Memory** — Structured knowledge base of conventions, reviewer preferences, incident history
3. **Execution Engine** — Thin wrapper around Claude Agent SDK; replaceable by design
4. **Feedback Loop** — Every code review feeds back into the organizational model, making future output better

**Key differentiator:** The organizational memory compounds over time. Kronode on day 1 follows community best practices. By month 3, it follows *your team's* practices. By month 6, it has more institutional knowledge than any individual engineer.

**Second-order value — engineer onboarding:** The same Team Memory that makes Kronode better at writing code also accelerates human engineer onboarding. New hires can query Kronode's knowledge base to understand "how we do things here" — conventions, architectural decisions, why certain patterns exist, who owns what. Instead of spending weeks reading old PRs or interrupting senior engineers, they get answers from a system that has already read every PR, every review comment, and every incident report. Kronode turns tribal knowledge into a queryable, living resource for the entire team.

---

## Technical Innovation & R&D Challenges

### 1. Convention Extraction from Unstructured Sources (Primary R&D)
**Challenge:** Automatically extracting actionable coding conventions from messy, unstructured PR diffs, review comments, and commit histories. This is not keyword matching — it requires understanding intent behind review feedback ("this should use our factory pattern" vs. "nice refactor") and resolving contradictory signals across hundreds of PRs.

**Uncertainty:** How to reliably deduplicate semantically similar conventions, handle convention evolution over time (what was best practice 6 months ago may not be today), and determine confidence thresholds for when an extracted pattern qualifies as a "convention" vs. noise.

**Approach:** Two-layer system — base conventions extracted from high-quality open-source repos (cross-referenced across multiple repos to filter for universal patterns), overlaid with customer-specific conventions from their own PR history. Customer layer always overrides base on conflict.

### 2. Context Assembly for Optimal Code Generation (Primary R&D)
**Challenge:** Given a ticket and a learned organizational model, determining which subset of conventions, architectural context, and historical patterns to inject into the coding agent's prompt — within token limits — to maximize the quality of generated code.

**Uncertainty:** Context window optimization is an open research problem. Too little context = generic code. Too much = the model ignores critical details. The right context depends on the specific task, the specific codebase area, and the team's priorities. No established methods exist for dynamically assembling task-specific context from a structured organizational knowledge base.

### 3. Confidence Calibration & Self-Awareness (Secondary R&D)
**Challenge:** Building a system that reliably knows what it doesn't know. Before generating code, Kronode must assess its knowledge coverage for the specific task and codebase area, and either proceed, flag uncertainties, or step back entirely.

**Uncertainty:** LLM confidence calibration is an active area of AI research. Mapping model uncertainty to actionable thresholds (execute / flag / defer to human) in a production software engineering context has no established methodology.

### 4. Feedback Loop Quality (Secondary R&D)
**Challenge:** Turning code review outcomes (approval, requested changes, rejection) into structured updates to the organizational model. A reviewer saying "we don't do it this way" needs to be classified, attributed to the right convention, and the convention updated — all automatically.

**Uncertainty:** Review comments are highly contextual, often implicit, and sometimes contradictory between reviewers. Determining which feedback represents a team convention vs. personal preference vs. one-off situational guidance is an unsolved classification problem.

---

## Current State of Development

| Component | Status |
|-----------|--------|
| Dashboard & Onboarding UI | Built |
| Jira, GitHub, Slack, Confluence integrations | Built |
| Agent creation & skill assignment | Built |
| Basic ticket-to-PR pipeline | Built |
| Celery/Redis async task processing | Built |
| Convention extraction pipeline | In progress |
| Pre-coding pipeline (ticket interpretation, plan generation) | In progress |
| Context assembly from organizational model | Next phase |
| Feedback loop from code reviews | Planned |
| Confidence scoring & self-awareness | Planned |

**Tech stack:** Python/FastAPI backend, Next.js frontend, PostgreSQL, Celery/Redis, Anthropic Claude API

---

## Market Opportunity

**Target:** Mid-size engineering teams (20-50 developers) using Jira/Linear + GitHub. TypeScript/Node stacks initially, expanding to Python, Go, mobile.

**Pain point intensity is highest when:**
- Senior engineers recently left (knowledge loss)
- Team is scaling fast (onboarding bottleneck)
- High attrition (repeated ramp-up costs)
- Recurring incidents from convention violations

**Market size:** ~50,000 engineering teams globally in the 20-50 developer range using compatible tooling. At $2-5K/month per team, TAM of $1.2-3B.

**Competitive landscape:**
- **Devin** ($500/mo) — end-to-end coding agent but no organizational memory, starts fresh every session
- **Augment Code** — strong on context/memory but IDE-only, serves individual developers not teams
- **Atlassian Rovo Dev** — natural Jira integration but early stage, limited coding capability

**Kronode's unique position:** No product today combines code generation + persistent organizational memory + team workflow integration + learning from reviews. The window to establish this position is 12-18 months before competitors converge.

---

## Team

Two senior full-stack developer cofounders based in Toronto. Combined experience across enterprise software development, distributed systems, and AI/ML application development. Actively seeking an ML/retrieval advisor (targeting Vector Institute Toronto, Mila Montreal, Cohere alumni networks).

---

## R&D Plan & IRAP Alignment

### Why This Is R&D (Not Routine Development)
The core technical challenges — extracting actionable conventions from unstructured review data, optimizing context assembly within token constraints, and calibrating AI confidence for autonomous action — have no established solutions. These are applied AI research problems that require systematic experimentation, not implementation of known techniques.

### R&D Activities (12-Month Plan)
**Months 1-4:** Convention extraction pipeline R&D
- Experiment with extraction approaches across LLM providers (Claude, Gemini, DeepSeek)
- Develop deduplication and scoring algorithms for convention quality
- Build and validate two-layer convention system on open-source repos
- Establish quality benchmarks against human-curated convention lists

**Months 4-8:** Context assembly and plan generation R&D
- Research optimal context window composition strategies
- Develop dynamic context selection based on task characteristics
- Build and test confidence scoring against human judgment baselines
- Iterate on plan generation quality with design partner feedback

**Months 8-12:** Feedback loop and self-improvement R&D
- Develop review comment classification system
- Research convention evolution and staleness detection
- Build feedback attribution pipeline (review outcome → convention update)
- Measure PR acceptance rate improvement over time as validation metric

### Expected Outcomes
- Novel methodology for extracting team-specific coding conventions from PR history
- Context assembly system that demonstrably improves AI code generation quality
- Validated confidence calibration approach for autonomous software engineering tasks
- Published benchmarks comparing organizational-context-aware vs. context-free code generation

---

## North Star Metrics

1. **Time to first merged PR** — proves onboarding speed and immediate value
2. **PR acceptance rate improvement over time** — proves the organizational memory works and compounds

---

## Funding Ask

R&D salary costs for the two cofounders over 12 months to pursue the technical challenges outlined above. The non-dilutive nature of IRAP funding allows the team to focus on R&D quality without premature pressure to ship a revenue-generating product before the core technical uncertainties are resolved.

---

## Key Talking Points for the Call

1. **This is an R&D project, not a product build.** The core value proposition depends on solving open technical challenges in convention extraction, context optimization, and confidence calibration. Without R&D, we'd be building another generic coding tool.

2. **Canadian AI ecosystem advantage.** Toronto's AI talent density (Vector Institute, U of T, Cohere ecosystem) provides access to advisors and potential hires with relevant expertise in retrieval, embeddings, and LLM optimization.

3. **Capital-efficient approach.** We use existing AI models (Claude, Gemini) rather than training our own. R&D spend goes entirely to applied research on the orchestration and memory layer — not compute for model training.

4. **Clear validation path.** Design partners on real codebases by month 5-7. Measurable improvement in PR acceptance rates proves the R&D thesis.

5. **IP is in the system, not the model.** The organizational memory schema, convention extraction pipeline, and context assembly methodology are proprietary. The underlying LLMs are commodities — our value is what we feed them and what we learn from their output.
