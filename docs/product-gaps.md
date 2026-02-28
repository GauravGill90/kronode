# Kronode — Product Gaps & Missing Sections

Sections missing from `PRODUCT.md` that must be resolved before enterprise sales conversations.
Ordered by priority.

---

## 1. Pricing Model

**Status: Not defined anywhere.**

Kronode is positioned as a hire, not a software purchase. The pricing model must reflect that.

### Recommended structure

| Tier | Price | What you get |
|------|-------|--------------|
| **Starter** | $1,500/mo | 1 agent profile, 1 repo, up to 50 tasks/mo |
| **Team** | $3,500/mo | 2 agent profiles, 3 repos, up to 200 tasks/mo, Slack + Jira |
| **Engineering** | $8,000/mo | 5 profiles, unlimited repos, unlimited tasks, Confluence, priority support |
| **Enterprise** | Custom | Dedicated infra (single-tenant), SSO, SOC 2, custom SLA |

### Rationale
- Benchmarks against a junior contractor ($8–12k/mo fully loaded) — the "hire not buy" framing only works if the price is in that range
- Task-based cap creates natural upgrade pressure as orgs see value
- Enterprise tier unlocks single-tenant deployment (separate from shared infra)

### Open questions
- Do unused tasks roll over?
- Is there a per-seat fee for human team members using the dashboard?
- What's the billing unit if a task fails (and is retried)?

---

## 2. Security & Compliance Posture

**Status: Not addressed anywhere in product or technical docs.**

Engineering managers and infosec teams will ask these questions in the first call.

### Data access
- Kronode reads the codebase via GitHub API — it never clones to a shared server
- Tokens (GitHub, Jira, Slack) are stored encrypted at rest (Fernet, key in env — see T2-12)
- No production database access is ever requested or granted
- Kronode writes code and opens PRs — it never merges without human approval

### Where code runs
- **Shared tier:** Agent pipeline runs on Kronode's infrastructure. Code context is sent to Anthropic's API (subject to Anthropic's data handling policy — no training on API data)
- **Enterprise tier:** Agent pipeline runs in a dedicated deployment in the customer's cloud account or Kronode's isolated VPC. Memory and embeddings stay on-premise

### Memory and data at churn
- All memory records, code embeddings, and org config are exportable as JSON on request
- On cancellation: full data deletion within 30 days, confirmation email sent
- No memory is shared between orgs — all records are `org_id`-scoped at the database level

### Compliance roadmap
| Milestone | Target |
|-----------|--------|
| SOC 2 Type I | 6 months post-launch |
| SOC 2 Type II | 12 months post-launch |
| GDPR DPA available | At launch |
| SSO (SAML/OIDC) | Enterprise tier, 3 months post-launch |

---

## 3. Failure Mode & Accountability

**Status: "Transparency before action" principle exists but no failure story.**

Every engineering manager's first question: *"What happens when it breaks something?"*

### The answer

**Kronode never merges without human approval.** Every PR is opened, not merged. A human engineer reviews and merges — the same accountability model as a human contractor.

**When a PR causes a regression:**
- Kronode is notified via the PR review comment or Slack
- It opens a follow-up task automatically: "Revert or fix regression in PR #X"
- The incident is stored as a `pitfall` memory record so the mistake is never repeated in that codebase

**When Kronode is wrong about confidence:**
- Pre-flight plan posted to Slack includes an explicit confidence level (High / Medium / Low)
- Low-confidence tasks require human sign-off on the plan before any code is written
- Guardrails Agent enforces a file-count and risk-level cap per task

**The accountability frame:**
Kronode is accountable the same way a contractor is — through the quality of its output, reviewed before merge. The team's existing review process is the safety net, not a new one.

---

## 4. Evaluation & Trial Story

**Status: No entry point for a CTO to evaluate Kronode risk-free.**

"Should we hire this agent" is a $36k/year decision. There must be a low-risk path to that decision.

### Recommended evaluation flow

**Step 1 — First PR Free (no card required)**
- Connect GitHub repo + Jira
- Assign one real ticket
- Kronode opens a real PR
- Human reviews it — if it's good, convert to paid

**Step 2 — 30-day trial (Starter tier, card on file)**
- Up to 10 tasks included
- Full memory + learning active from day 1 (compounding starts immediately)
- Cancel anytime, full data export provided

**Step 3 — Conversion**
- After 30 days: review the PR acceptance rate report
- Kronode shows: tasks completed, PRs merged, reviewer comments it pre-empted, time saved estimate

### Why start compounding on day 1
The tenure story only works if memory accumulates from the first interaction. A sandbox or demo mode would undermine the product's core claim. The trial is real from the start.

---

## 5. Escalation & Clarification Loop

**Status: "Explicitly asks for it" mentioned once — no product experience defined.**

This is a core UX flow. It determines whether engineers trust or resent the agent.

### When Kronode asks for clarification

Kronode escalates (never silently proceeds) when:
- The ticket description is ambiguous about scope (e.g., "improve the auth flow" — which part?)
- The plan would touch >3 files outside the agent's declared guardrail scope
- Confidence level on the implementation approach is Low
- A required file or API doesn't exist and can't be inferred

### How it asks

1. **Primary channel: Slack** — posts in the team's configured channel, `@mentions` the ticket assignee or reporter
   ```
   @alice — I'm about to start KR-47 (Improve auth flow) but I need to clarify scope before writing any code:
   • Do you want me to update the login page UI, the JWT validation logic, or both?
   • Should I touch the `/api/auth/*` routes or just the frontend?
   I'll wait for your reply before proceeding. If I don't hear back in 4 hours I'll flag this ticket as blocked.
   ```

2. **Secondary: Jira comment** — same message posted as a comment on the ticket, tagged as `[Kronode - Waiting for input]`

3. **If no response in 4 hours:** sets ticket to `Blocked`, posts update to Slack, stops work

### What Kronode never does
- Proceeds under ambiguity and hopes for the best
- Asks more than 3 clarifying questions per ticket (if scope is that unclear, it escalates the whole ticket)
- Sends DMs to individual engineers (always posts to the shared channel — transparency)

---

## 6. Learns Individual Engineers

**Status: Mentioned as a feature, never developed.**

This is a significant differentiator — no competitor tracks reviewer preferences at the individual level.

### What Kronode tracks per engineer

| Signal | How captured | Stored as |
|--------|-------------|-----------|
| Recurring review comments | PR review comment text | `reviewer_preference` memory record |
| Files they own / are sensitive about | PR review patterns on specific paths | `file_coupling` memory record with owner |
| Preferred patterns | Comment text: "always use X", "never do Y" | `convention` memory record tagged to reviewer |
| Communication style | Slack response tone | Not stored — informs Slack message tone only |

### How it's applied

**Before writing code (Planner):** "Alice always asks for integration tests on auth changes. Add integration tests to the DoD for this task."

**Before opening the PR:** PR description is written to pre-empt known reviewer concerns. Example: if Bob always comments "add a docstring here", the coder adds docstrings without being asked.

**In the PR description:**
```
Note for reviewers:
• Added integration tests (per Alice's preference on auth PRs)
• All public functions have docstrings
• Migration is reversible (rollback tested)
```

### Privacy consideration
All per-engineer learning is:
- Scoped to professional review behaviour, not personal data
- Visible to org admins in the memory dashboard
- Deletable per engineer on request

---

## 7. Proactive Backlog Monitoring — Guardrails

**Status: "Volunteers to take unassigned work" with no safety rails described.**

Without guardrails, this feature will alarm engineering managers.

### How it works

1. **Daily scan** (configurable: on/off per org): Kronode reads the Jira backlog for unassigned tickets in the `To Do` column
2. **Eligibility filter**: Only considers tickets that match ALL of:
   - In Kronode's assigned project(s)
   - Labelled `kronode-eligible` OR within the org's configured auto-assign label
   - Complexity score ≤ Medium (router pre-screens before volunteering)
3. **Volunteers, doesn't self-assign**: Posts to Slack: "I can take KR-52 (Add rate limiting to /search). Want me to start? React ✅ to confirm or ❌ to skip."
4. **Requires explicit confirmation** before any work begins — no auto-assignment without human approval
5. **Daily cap**: will not volunteer for more than 2 tickets per day without a human increasing the limit

### Off by default
Proactive monitoring is **disabled by default**. Orgs opt in during onboarding with a clear explanation of how it works.

---

## 8. Competitor Landscape (Updated)

**Current doc lists:** Devin, Factory, Sweep, GitHub Copilot Workspace
**Missing from current competitive set:**

| Competitor | What they do | Kronode's differentiation |
|-----------|-------------|--------------------------|
| **Cursor (background agents)** | Async task execution inside the IDE | IDE-bound, no Jira/Slack integration, no memory |
| **Amp (Anthropic)** | Anthropic's own CLI agent | Stateless, developer tool not org actor |
| **OpenHands** | Open-source autonomous coder | Self-hosted, no memory, no integrations |
| **Codegen** | GitHub PR automation | No planning layer, no memory, limited scope |
| **SWE-agent** | Research-origin autonomous agent | No production integrations, no memory |

**The consistent Kronode advantage across all:** memory + tenure + org-native workflow. None of the above accumulate knowledge about a specific team over time.

---

## 9. Data Ownership at Churn

**Status: Not mentioned anywhere.**

Enterprise procurement requires this before signing.

### Policy

| Data type | On cancellation |
|-----------|----------------|
| Memory records (conventions, pitfalls, org knowledge) | Exported as JSON within 24 hours of request; deleted from Kronode servers within 30 days |
| Code embeddings | Deleted within 30 days (derived data — not re-creatable without the repo) |
| Task history + events | Exported as JSON; deleted within 30 days |
| Org config (tokens, settings) | Deleted immediately on cancellation |
| GitHub/Jira/Slack tokens | Revoked and deleted immediately |

The customer retains everything Kronode learned. The memory is theirs — Kronode is just the agent that builds it.

---

## 10. North Star Metrics (Revised)

Current: Time to first merged PR + PR acceptance rate improvement

**Add a third:**

**3. Monthly active tasks per org (retention proxy)**
- An org that assigned 5 tasks in month 1 and 50 in month 6 is the proof case for the tenure story
- This metric proves the compounding value claim more directly than acceptance rate alone
- Target: 3× task volume growth between month 1 and month 6 for retained orgs

**Supporting metrics to track internally (not customer-facing):**
- Memory records written per completed task (proves learning is happening)
- % of PRs where Kronode pre-empted a reviewer comment (proves individual engineer learning)
- Clarification requests per task (proxy for ticket quality — should decrease over time)
- Token cost per merged PR (unit economics)
