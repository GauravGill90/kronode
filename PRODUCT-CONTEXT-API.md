# Kronode Context API — Product Evaluation

_Companion to PRODUCT.md. Explores packaging Kronode's organizational intelligence as a standalone API product. Critical, not promotional._

---

## The Idea in One Sentence

Sell the organizational context that makes AI coding tools better — without being an AI coding tool.

---

## What It Is

An API that any AI coding tool calls before generating code. Returns the team's conventions, known pitfalls, reviewer preferences, past failure patterns, and relevant documentation — ranked by relevance to the specific task.

The insight: every AI coding tool (Cursor, Claude Code, Copilot, Codex, Devin) generates code in a vacuum. They know the language. They don't know the team. Kronode fills that gap.

```
Any AI Tool  +  Kronode Context  =  Team-Aware Output
```

The coding agent is the commodity. The organizational knowledge is the moat.

---

## What Data Exists Today

This isn't theoretical. Kronode already collects, structures, and ranks all of this in production:

### Conventions (structured, scored, attributed)
- **What:** Actionable coding rules extracted from PR history. "Use Handler suffix for API routes." "Use TestContext factory for integration tests."
- **How rich:** Each convention has: category (naming/architecture/testing/style/error_handling/logging), confidence score (0.0–1.0), frequency count, source PRs, source file paths, enforced_by (reviewer names who consistently enforce it), suppression flag.
- **Two layers:** Base layer (community best practices per stack, extracted from open source repos like Cal.com) + customer layer (team-specific, extracted from their own PRs). Customer always wins on conflict. Rejected base conventions stay rejected permanently.
- **Scale:** 25–400+ conventions per org after initial extraction. Grows continuously from PR feedback.

### Pitfalls (file-scoped, reviewer-attributed)
- **What:** Review comments from PRs where changes were requested. Stored with exact file paths, reviewer names, and comment bodies.
- **When loaded:** Only when a new task touches the same files that previously failed review. Not global noise — surgically relevant.

### Reviewer Patterns (per-person preferences)
- **What:** Which reviewers care about what. "Sarah always requests null checks on BLE responses." "John enforces named exports in packages/."
- **Source:** Extracted from review comments + convention enforcement tracking. If a reviewer consistently enforces a convention, that link is recorded.

### Past Failures (classified, compounding)
- **What:** Every time Kronode's coder fails, the failure is classified into 8 categories: wrong_path, missing_import, style_violation, logic_error, missing_test, api_misuse, scope_creep, breaking_change.
- **Why it matters:** If BLE tasks have failed 4 times with OOM errors, the next BLE task gets a warning. The system literally remembers its own mistakes and adjusts.

### Documentation Chunks (embedded, searchable)
- **What:** All markdown/docs from the repo and Confluence, chunked by heading, embedded for semantic search.
- **Query:** Given a task description, returns the 5 most relevant doc sections by cosine similarity.

### File Touch History
- **What:** Which files were modified in previous tasks. Used to boost file selection — if the team's last 5 tasks all touched `src/handlers/`, that directory gets priority in context building.

### Coding Standards (org-level, free-text)
- **What:** Team's explicit coding standards, injected into every prompt verbatim.

### Confidence Assessment
- **What:** Before any code is written, Kronode scores 0.0–1.0 how well-understood the task is, based on: convention coverage, file familiarity, structured requirements, risk flags, reviewer pattern availability.

---

## The API Shape

```
POST /v1/context
Authorization: Bearer kron_xxxxx

{
  "task_description": "Add form validation to HVAC cert exchange flow",
  "files_touched": ["app/hooks/ble/hvacCert/useCertExchange.ts"],  // optional
}

→ 200 OK
{
  "conventions": [
    {
      "rule": "Use Handler suffix for API route files in packages/api/",
      "category": "naming",
      "confidence": 0.92,
      "source": "team",
      "enforced_by": ["sarah", "john"],
      "relevance_score": 8.4
    },
    ...
  ],
  "pitfalls": [
    {
      "description": "BLE tasks have failed 4 times — OOM on large cert payloads",
      "files": ["app/hooks/ble/*"],
      "reviewer": "sarah",
      "pr_url": "https://bitbucket.org/..."
    }
  ],
  "reviewer_patterns": [
    {
      "reviewer": "sarah",
      "preference": "Always add null checks on BLE response objects",
      "enforcement_count": 7
    }
  ],
  "past_failures": [
    {
      "task": "Add unit tests for BLE auth",
      "category": "oom",
      "error": "Command failed with exit code -9",
      "files": ["app/hooks/ble/auth/"]
    }
  ],
  "doc_chunks": [
    {
      "heading": "BLE Certificate Exchange Protocol",
      "content": "The cert exchange uses a 3-step handshake...",
      "source_url": "https://confluence.internal/..."
    }
  ],
  "coding_standards": "Always use TypeScript strict mode...",
  "confidence": {
    "score": 0.55,
    "level": "medium",
    "signals": {
      "conventions_available": true,
      "files_familiar": false,
      "past_failures_in_area": true,
      "reviewer_patterns_known": true
    }
  }
}
```

### IDE-Specific Exports

```
GET /v1/context/cursor-rules     → .cursor/rules file content
GET /v1/context/claude-md        → CLAUDE.md content
GET /v1/context/system-prompt    → plain text for any LLM system prompt
```

These are convenience wrappers — same data, formatted for each tool's native convention.

---

## USP Critique — What's Actually Unique

### Genuinely differentiated

1. **Task-specific ranking, not a static dump.** Every API call returns conventions ranked by relevance to _this specific task_ using 7 signals (keyword overlap, file-path match, semantic similarity, category relevance, source file overlap, frequency, confidence). No competitor does per-task ranking — they all return a flat list.

2. **Reviewer modeling.** No tool tracks which humans enforce which rules. Kronode knows that Sarah cares about null checks and John cares about naming conventions. This lets the AI preemptively address the reviewer who'll actually look at the PR.

3. **Failure memory that compounds.** If a BLE task failed 4 times, the 5th attempt knows. This isn't a feature — it's a feedback loop that improves over time. Static rule files can't do this.

4. **Two-layer convention system with attribution.** Every convention traces back to specific PRs and reviewers. "Use named exports — enforced by Sarah across 12 PRs" is more authoritative than "use named exports" in a config file. Teams trust conventions they can verify.

5. **Pitfalls are file-scoped, not global.** A pitfall only surfaces when you're touching the exact files that caused it. This prevents context pollution — you don't get warnings about authentication when you're working on a UI component.

### Honest reality check — what's NOT unique

1. **Convention extraction from PR history** — Greptile, Qodo, and CodeRabbit all do some version of this. The extraction itself is table stakes.

2. **Injecting rules into AI tools** — `.cursor/rules` and `CLAUDE.md` already exist. Any team can write them manually. The question is whether auto-generation + continuous updating is worth paying for.

3. **Embedding-based search** — Sourcegraph Cody, Continue.dev, and others already do semantic code/doc search. Kronode's doc chunk search isn't a differentiator.

4. **The data model itself** — conventions, categories, confidence scores. This is replicable. Any team with an LLM and GitHub API access could build the extraction pipeline in a few weeks.

---

## Competitive Landscape — Brutally Honest

### Direct competitors to the Context API concept

| Competitor | What they do | Why they're a threat | Where Kronode wins |
|-----------|-------------|---------------------|-------------------|
| **Greptile** | Learns team standards from PR comments. API-first. | Closest to this exact idea. Already has funding, customers, API. | Greptile is review-only. No failure memory, no confidence scoring, no task-specific ranking. |
| **CodeRabbit** | Auto-reviewer that learns from feedback. Creates "learnings." | Popular, growing fast. Learnings are similar to conventions. | CodeRabbit learnings are flat. No per-task ranking, no reviewer attribution, no file-scoped pitfalls. |
| **Qodo (formerly CodiumAI)** | "Organizational learning" from PR history. Testing focus. | Explicitly markets org learning. Well-funded. | Qodo focuses on test generation. Convention system is less structured than Kronode's. |
| **Sourcegraph Cody** | Deep codebase understanding. Context-aware completions. | Enterprise-grade code intelligence. Massive funding. | Cody understands code structure, not team culture. No conventions, no reviewer modeling, no failure memory. |

### Adjacent — could pivot into this space

| Competitor | Risk level | Notes |
|-----------|-----------|-------|
| **Cursor** | High | If Cursor builds native "learn from my PR history" → kills the `.cursor/rules` export use case. They have the distribution. |
| **GitHub Copilot** | High | Copilot already has custom instructions. If GitHub adds "auto-learn from repo history" → massive threat given their data access. |
| **Atlassian Rovo** | Medium | Has all the Jira + Bitbucket data already. If they build convention extraction, they have richer input than anyone. |
| **Anthropic (Claude Code)** | Medium | If Claude Code adds persistent project memory across sessions that learns from reviews, the `CLAUDE.md` export becomes redundant. |

### The uncomfortable truth

The 12–18 month window from PRODUCT.md applies here too. The moat is accumulated customer data (6 months of a team's review patterns can't be cloned), not the technology. If a well-funded competitor builds convention extraction + ranking, the tech differentiator disappears. The retention differentiator (compounded memory) remains.

---

## Sellability Assessment

### Who buys this

**Primary:** 20–100 person engineering teams already using AI coding tools (Cursor, Copilot, Claude Code) who are frustrated that the AI doesn't follow their team's patterns.

**Signal they're ready to buy:** They've manually written `.cursor/rules` or `CLAUDE.md` files and are tired of keeping them updated. They've had PRs from AI tools rejected because the AI didn't know the team's conventions.

**Secondary:** Platform teams at larger orgs (100–500 eng) responsible for developer experience. They want to enforce coding standards across teams without manual policing.

### Why they'd buy

1. **"Our AI keeps making the same mistakes."** The AI doesn't learn from reviews. Kronode does.
2. **"We wrote Cursor rules once and never updated them."** Kronode auto-updates from every merged PR and review comment.
3. **"New engineers take months to learn our patterns."** The Context API gives any AI tool (or human) instant access to institutional knowledge.
4. **"PRs from Devin/Copilot always get rejected."** Kronode context → fewer review rounds → faster merge.

### Why they wouldn't buy

1. **"We can just write rules ourselves."** True for small teams with stable conventions. Falls apart at scale or with high turnover.
2. **"Another SaaS subscription."** Developer tooling fatigue is real. Price has to justify itself in measurable time savings.
3. **"We'd need to give you repo access."** Security-conscious teams will push back. Read-only GitHub access is the minimum — but "read-only access to all our PRs" still triggers procurement review.
4. **"How is this different from CodeRabbit learnings?"** If they already use CodeRabbit, the value delta might be too small to justify a second tool. The answer has to be: task-specific ranking + failure memory + reviewer modeling. If that delta isn't compelling in a demo, the sale dies.

### Price anchor

- Greptile: ~$30/dev/month
- CodeRabbit: $12/dev/month (Pro), $24/dev/month (Enterprise)
- Cursor: $20/dev/month (Pro), $40/dev/month (Business)
- Copilot: $19/dev/month (Business)

Context API should sit at **$10–20/dev/month** — cheaper than the tools it augments. The pitch: "For half the cost of Cursor, make Cursor 2x better at following your team's patterns."

Free tier: 1 repo, 50 conventions, 100 API calls/day. Enough to demo value. Not enough for production use.

---

## Honest Risks

### 1. Distribution problem
AI coding tools have the users. Kronode doesn't. Even if the Context API is technically better, getting teams to add another tool in the workflow is a hard sell. **Mitigation:** IDE-native formats (`.cursor/rules`, `CLAUDE.md`) mean zero workflow change — it's a background sync, not a new tool.

### 2. Feature absorption
Cursor, Copilot, or Claude Code builds convention learning natively. They have the data (they see every keystroke, every accept/reject). **Mitigation:** None, honestly. If a tool with 10M users builds this, a startup can't compete on features. The play is: get there first, accumulate customer-specific data, make switching costly because the memory is valuable.

### 3. "Good enough" manual rules
Teams that write 20 rules in `.cursor/rules` and call it done. They don't need auto-extraction or ranking — their rules are stable and sufficient. **Mitigation:** Target teams where this breaks down: high turnover, fast-moving codebases, multiple repos, large teams where conventions aren't consistent across people.

### 4. Cold start for new customers
Before conventions are extracted, the API returns very little. The base layer (from Cal.com etc.) helps but may not match the customer's stack. **Mitigation:** First extraction runs on signup (200 PRs → 25–100 conventions in ~10 minutes). But teams with few merged PRs or private review cultures (no written comments) will have thin data.

### 5. Data sensitivity
PR diffs, review comments, and coding patterns are sensitive. Some teams won't send this to a third party. **Mitigation:** SOC 2, on-prem option (eventually), or a self-hosted extraction pipeline that only sends aggregated conventions (not raw code) to the API.

---

## Relationship to the Full Pipeline

The Context API is **Layer 2 of the existing architecture** (Organizational Model) exposed as a standalone product.

```
Layer 1 — Event Stream    →  ingestion (PR history, Jira, Slack, Confluence)
Layer 2 — Org Model       →  ★ THIS IS THE CONTEXT API ★
Layer 3 — Execution        →  coding agent (Track A: full pipeline)
Layer 4 — Feedback Loop   →  review outcomes feed back into Layer 2
```

**Track A** (full pipeline): Ticket → Context → Plan → Code → PR → Review → Learn. For teams that want full autonomy. Kronode does everything.

**Track B** (Context API): Just Layer 2, exposed as an API. For teams that already have a coding tool and just want the organizational intelligence. Kronode provides context, their tool does the coding.

Both tracks share the same memory engine. A Track B customer's conventions improve every time a PR is reviewed, regardless of whether Kronode or Cursor wrote the code. This means Track B still has the compounding feedback loop — the moat still works.

**Upgrade path:** Track B → Track A. "Your conventions are great. Want Kronode to also write the code using them?" Natural upsell once trust is established.

---

## What's Already Built vs. What's New

| Component | Status | Notes |
|-----------|--------|-------|
| Convention extraction from PR history | Built | `convention_pipeline.py` — batch + incremental |
| Convention ranking (7 signals) | Built | `context_builder.py:_rank_conventions()` |
| Pitfall memory | Built | `task_queue.py:_poll_pr_outcomes()` |
| Reviewer pattern tracking | Built | `context_builder.py` + `feedback_extractor.py` |
| Failure classification | Built | 8 categories, LLM-classified on each rejection |
| Doc ingestion + semantic search | Built | `doc_ingestion.py` with embeddings |
| Confidence scoring | Built | `planner_agent.py:_calculate_confidence()` |
| Weekly convention refresh | Built | `refresh_conventions_all_orgs` Celery Beat task |
| **Public context API endpoint** | **Not built** | New: wraps existing ranking + memory queries |
| **API key auth (machine-to-machine)** | **Not built** | New: org-scoped API keys, not Clerk JWT |
| **IDE format exporters** | **Not built** | New: render conventions into .cursor/rules, CLAUDE.md, etc. |
| **Webhook on convention change** | **Not built** | New: notify customer's CI when conventions update |
| **Dashboard: API keys + integration guide** | **Not built** | New: generate/revoke keys, copy-paste snippets |

~85% of the backend already exists. The new work is a thin API layer on top.

---

## One-Line Pitch Options

- "Your AI coding tool doesn't know your team. Kronode does."
- "Every AI coding tool starts from zero. Kronode gives them your team's memory."
- "Convention-aware AI coding — without switching tools."

---

## Decision Framework

Build Track B if:
- You believe the coding agent market will commoditize (evidence: it is)
- You want a lower-friction entry point than "trust our bot with commit access"
- You want to validate whether the organizational intelligence has standalone value

Don't build Track B if:
- You believe the full pipeline's end-to-end experience is the primary differentiator
- You'd rather focus engineering time on making Track A's coding better
- You think the market wants "one tool that does everything" not "a tool that makes other tools better"

The safest path: build Track B alongside Track A. Same memory engine, two surfaces. Track B validates the moat without abandoning the pipeline.
