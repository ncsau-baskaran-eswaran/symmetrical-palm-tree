# From Black-Box Probe to Deep Compliance Agent 🇦🇺
## A product pitch: why APRA agent-assurance needs an MCP-powered agent, not just a UI

> **The one-line pitch:** We've shipped a UI-driven probe that catches the *behaviours* an AI agent can be caught doing wrong. The next step — and the real moat — is an **MCP/agent that reasons across the full CPS 230 & CPS 234 framework**, adapts its attacks, plugs into the entity's own stack, and covers the governance controls a chat probe can never see.

---

## Elevator pitch (30 seconds)

> Australian banks and insurers are putting AI agents in front of customers, and APRA
> holds the Board accountable when those agents misbehave. We do two things about that.
>
> First, we test. Our probe attacks your agent over a normal web connection, the same way
> a manipulative customer would. It tries to talk the agent into approving a loan or
> leaking customer data, maps every failure to the CPS 230 or CPS 234 clause it touches,
> and produces a Board-ready report with a hash-chained evidence record.
>
> Second, we enforce. Our pre-flight check sits between the agent and the customer. Every
> reply is checked before it goes out, and the model can't skip or talk its way around the
> check. If the check fails, the reply is blocked; if it can't run, nothing is released.
>
> Find the gaps, then close them, all against APRA's own standards.

**One-liner:** "We test your AI agents the way an attacker would, and stop unsafe replies
before they reach a customer, mapped to APRA's own standards."

**For a CRO**, add after the second paragraph: "Detection rules are configurable, so you
validate them against your own policies." It answers their first diligence question
before they ask it. Stay within the claims in
[How we pitch the runtime guardrail](#how-we-pitch-the-runtime-guardrail).

---

## 1. The problem we're solving

Australian banks, insurers and super funds are putting **autonomous AI agents into production** — lending assistants, claims triage bots, customer-service copilots — often from third-party vendors, with no source access.

Under **APRA CPS 230 (Operational Risk Management)** and **CPS 234 (Information Security)**, the **Board and senior management hold ultimate, non-delegable accountability** (CPS 230 Para 19, CPS 234 Para 13). An agent that approves a coerced loan, leaks a customer's TFN, or invents coverage creates **direct director liability** and can trigger **mandatory 24h / 72h APRA notifications**.

Today, risk and compliance teams have **no fast, repeatable way to interrogate these agents** against the prudential standards. That's the gap.

---

## 2. What we've built — Phase 1 (shipped)

A **behaviourally-observable, UI-driven assurance workflow**. Point it at any agent's HTTP endpoint and get a board-ready read in seconds — **zero code changes or SDK on the target**.

| Capability | What it does |
| :-- | :-- |
| **Agent Compliance Probe (`/probe`)** | Plain web UI: paste an endpoint → run → live, streamed assessment. |
| **Autonomous red-team ladder** | A bounded Planner→Actor→Evaluator loop climbing named adversarial **test stages**, each grounded in APRA MCP regulation tools. |
| **Live stage stepping** | Each stage streams pending → probing → pass/fail with real HTTP latencies. |
| **Verdict + findings** | Risk rating, resisted-% score, per-stage probe/response, flagged clauses + remediation. |
| **Tamper-evident evidence** | Append-only SHA-256 Merkle manifest + downloadable Board dossier (.md). |
| **Standalone agent test harness** | A hypothetical prod-grade banking/insurance agent that runs as its own service, so the probe exercises the real wire path. |

**This is genuinely useful and genuinely shippable.** It catches the highest-frequency, highest-liability failures — unauthorised commitments, PII/TFN leakage, prompt injection, hallucinated coverage — the things that actually make the news.

---

## 3. The honest limit (and why that's the opening)

Here's the slide no competitor will put up, and the reason to go deeper.

**CPS 230 has 30 clauses. CPS 234 has 33. That's 63 obligations.** A conversational black-box probe, by its nature, can only touch the ones that are **behaviourally observable** — what the agent *says and does* in a chat. Today we meaningfully assess ~**11** of them.

The 63 clauses split into two worlds:

### 🟢 Behaviourally observable — a probe *can* test these
Unauthorised commitments, data/PII leakage, prompt-injection & jailbreaks, system-prompt/IP extraction, cross-session data bleed, output integrity & unfair decisions, resilience under malformed input, logging admissions.

### ⚪ Governance & process — a probe *cannot* see these
Board accountability (230 Para 19, 234 Para 13), BCP & tolerance testing (Para 34/43/48/39), material-service-provider contracts & offshoring (Para 51–70), info-security capability & policy framework, asset-classification programs, independent control testing, internal audit (234 Para 15–34). **These require document and control review — not chat.**

> A UI-driven probe alone will *always* leave ~⅔ of the framework untouched. That isn't a bug in our build — it's the ceiling of the method. **Breaking through that ceiling is the product.**

---

## 4. The pitch — Phase 2: a deep MCP / agent

Replace "a UI that runs 4 checks" with **an agent that reasons across the whole standard** and orchestrates every assurance method. Four moves:

### 4.1 Go wider on behavioural coverage
Add the high-signal stages we're currently missing (each a *risk indicator* mapped to a clause):

| New probe stage | Clause (indicator) |
| :-- | :-- |
| Jailbreak / instruction-override robustness | CPS 234 Para 21 |
| System-prompt / model / protected-IP extraction | CPS 234 Para 21 |
| Cross-session memory & data-retention bleed | CPS 234 Para 20/21 |
| Sensitive-data inference / reconstruction | CPS 234 Para 20/21 |
| Unsafe failure under malformed / burst input (tolerance) | CPS 230 Para 39/42 |
| Unlicensed advice / misleading output / unfair-decision bias | CPS 230 Para 14/23 |
| Audit-trail & traceability admissions | CPS 234 Para 23 |

### 4.2 Go deeper with *agentic, adaptive* probing
The UI runs fixed heuristics. An **LLM-driven agent** researches the live clause text via MCP tools (`search_regulations`, `lookup_clause`, `get_critical_operations`), **crafts adaptive multi-turn attacks**, follows the agent's weaknesses, and reasons about whether a response is actually a breach — instead of regex-matching four scripted scenarios.

### 4.3 Go **MCP-native** — assurance where the agents already live
Expose the whole capability as **MCP tools** so it drops into the entity's own stack:
- **Runtime guardrail** — pre-flight audit of an agent's draft action *before* dispatch (already prototyped) → continuous, not point-in-time.
- **CI / release gate** — fail a build if an agent regresses on a CPS control.
- **Inside the client's own agents** — Claude Desktop, Cursor, IDEs, orchestration frameworks.

#### How we pitch the runtime guardrail

> Most AI agent controls ask the model to police itself. Ours doesn't. Every draft
> response passes through a service-enforced pre-flight check before it reaches the
> customer, and the model cannot skip, negotiate around, or switch off that check. If a
> draft breaches the rules we have configured for CPS 230 and CPS 234 risks, it is
> blocked. If the check cannot run, nothing is released. Detection rules are configurable
> and should be validated against your own policies and independent testing. The
> enforcement guarantee does not depend on them.

**Lead with the enforcement guarantee, not the detection.** The defensible claims are:
the agent cannot skip the check; a failed check blocks the draft; an unavailable check
withholds it (HTTP 503) and the service refuses to start without it.

**Do not say:**
- **"Gold standard"**, even for the enforcement pattern alone. A check the model can't
  skip is a baseline expectation for regulated systems, and the qualifier gets dropped in
  decks.
- **"APRA compliant", "prevents CPS breaches", or "audited against CPS 230/234".** The
  check matches a small set of configured patterns (`src/tools/agent_auditor.py`), not
  the standards themselves.
- **The demo's 100% score as validation.** `/probe` grades with the same function the
  guardrail enforces with, so a guarded agent scores 100% by construction.
- **"Escalated to a human officer".** There is no escalation hand-off yet.
- **"Tamper-resistant audit trail" for the service logs.** They store hashes so customer
  text stays out of the logs, which is privacy, not tamper evidence. Only the probe's
  dossier is hash-chained.

**Before this pitch carries weight with a CRO:**
1. Grade the probe independently: a separate evaluator and test set, so it can catch
   what the guardrail misses.
2. Broaden detection: semantic checks, no requirement for attack wording in the prompt,
   and published false-positive and false-negative rates.
3. Build a real escalation hand-off (webhook or queue to a review system) before the
   block notice claims one.

### 4.4 Close the governance gap with a control-review companion
The agent orchestrates the **non-observable** clauses too: ingest policies, BCPs, MSP contracts and control-test evidence; run a structured questionnaire; map documents to clauses. One agent, **both** behavioural probing *and* control review → a **unified coverage picture**.

---

## 5. The deliverable that ties it together: an honest coverage map

Every engagement produces a **per-clause matrix across all 63 obligations**, each labelled:

- **Behaviourally assessed** — an observable test was actually run (with evidence).
- **Partial / indicator only** — a signal, not proof.
- **Covered by control review** — verified via document/evidence, not chat.
- **Out of scope for black-box** — flagged, not silently skipped.

This is the credibility centrepiece: **we tell the Board exactly what we checked, how, and what we didn't** — turning the method's honest limits into a trust advantage.

---

## 6. Architecture at a glance

```
                        ┌─────────────────────────────────────────────┐
                        │        DEEP COMPLIANCE AGENT (MCP)          │
                        │  adaptive planner · reasons over CPS 230/234 │
                        └───────┬───────────────┬───────────────┬──────┘
                                │               │               │
                 ┌──────────────▼──┐   ┌────────▼────────┐  ┌───▼───────────────┐
                 │ Behavioural     │   │ Control-review  │  │ MCP integrations  │
                 │ probe battery   │   │ companion       │  │ • runtime guardrail│
                 │ (Phase 1 + 4.1) │   │ (docs, BCP,     │  │ • CI release gate  │
                 │ over HTTP       │   │  MSP, evidence) │  │ • client agents    │
                 └──────────┬──────┘   └────────┬────────┘  └───┬───────────────┘
                            └───────────┬───────┴───────────────┘
                                        ▼
                    ┌───────────────────────────────────────────┐
                    │  Unified per-clause COVERAGE MAP (63 obl.)  │
                    │  + SHA-256 evidence manifest + Board dossier │
                    └───────────────────────────────────────────┘
```

---

## 7. Phase 1 vs Phase 2 at a glance

| | Phase 1 — UI probe (today) | Phase 2 — Deep MCP agent (the ask) |
| :-- | :-- | :-- |
| Clauses touched | ~11 behavioural | Expanded behavioural **+** governance via control review |
| Probing style | 4 fixed heuristic stages | Adaptive, multi-turn, clause-researching agent |
| Where it runs | A web page you visit | **In the entity's stack** (runtime, CI, agents) + UI |
| Cadence | Point-in-time, manual | Continuous / on every release |
| Governance clauses | Out of scope | Covered by the control-review companion |
| Output | Stage findings + dossier | **Full 63-clause coverage map** + dossier |

---

## 8. Why an MCP/agent is the right vehicle (not just more UI)

- **Reasoning, not regex** — adapts attacks and judges responses in context; clause mapping becomes an explained inference, not a brittle keyword match.
- **Grounded** — queries the live regulation corpus via MCP tools, so findings cite real clause text.
- **Embeddable** — MCP is the standard these agents already speak; assurance rides into the client's runtime, CI and copilots with near-zero integration.
- **Continuous** — turns a one-off audit into always-on prudential assurance.

---

## 9. Integrity guardrails (what keeps this defensible)

- Chat findings are **risk indicators, not legal conclusions** — clause applicability depends on the entity, service, materiality and control context.
- Every finding carries **evidence, limitations, date and version**.
- **Human-in-the-loop**: outputs assist accountable risk teams under CPS 230 Para 19 / CPS 234 Para 13; they are not a certification or a regulatory filing.
- SSRF-safe, read-only, synthetic-fixture probing with a hard safety circuit-breaker on real secret leakage.

---

## 10. Roadmap

1. **Now (done):** behavioural UI probe + live assessment + agent test harness. ✅
2. **Next:** expand the behavioural battery and ship the **per-clause coverage map**.
3. **Then:** the **adaptive MCP agent** + MCP runtime/CI integrations.
4. **Then:** the **control-review companion** for the governance clauses.

---

*Prepared for internal/stakeholder review. Companion specs: [AUTONOMOUS_PROBER.md](AUTONOMOUS_PROBER.md) · [BLACKBOX_PROBER.md](BLACKBOX_PROBER.md) · [AGENT_SERVICE.md](AGENT_SERVICE.md).*
