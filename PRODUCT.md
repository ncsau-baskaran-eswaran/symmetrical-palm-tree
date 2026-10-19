# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: engineers and AI platform teams at Australian general, life and private health insurers
(and, secondarily, banks/ADIs) who build, deploy or integrate customer-facing AI agents, often from third-party
vendors with no source access. They run the probe against an agent's HTTP chat endpoint before
and after release, read what failed and why, and fix it.

Secondary: risk and compliance staff and the Board, who receive the exported dossier rather
than operating the tool.

## Product Purpose

Agent Compliance Probe attacks an AI agent over a normal HTTP connection the way a manipulative
customer would, maps each failure to the obligations it engages (APRA prudential standards, ASIC conduct law,
the Codes of Practice, privacy and private health law), and produces a
hash-chained evidence record and a Board dossier. A companion runtime guardrail checks every
draft reply against the same Guardian Compliance MCP tools before it is dispatched and withholds it if the check
fails or cannot run. Success: an engineer gets a trustworthy, clause-mapped read of an agent in
under a minute and knows exactly what to fix.

## Positioning

Black-box, zero-SDK testing grounded in the Australian insurance rulebook via the Guardian
Compliance MCP, paired with a fail-closed runtime guardrail that enforces the same checks.
Find the gaps, then close them, against the rules insurers are actually held to.

## Operating Context

- Target: any agent chat endpoint (`POST /v1/chat`, JSON `{"message": ...}`), optional Bearer token.
- Assessment: a bounded Planner, Actor, Evaluator, Evidence loop over four adversarial stages
  (operational limits, authority coercion, data protection, coverage integrity), streamed live
  as NDJSON with real latencies.
- Outputs: risk rating (LOW / HIGH / CRITICAL / UNREACHABLE), resisted %, per-stage probe and
  response, violations with clause and remediation, APRA notification flags, SHA-256 evidence
  chain fingerprint, Markdown Board dossier.
- Demo setup: unguarded agent on :9000, guarded agent on :9001, prober UI on :8080.

## Capabilities and Constraints

- SSRF guard blocks loopback/private targets unless exactly allowlisted.
- Auth tokens are sent only to the target and are not stored or logged.
- A conversational probe can only assess behaviourally observable clauses (about 11 of 63);
  governance and process controls are out of reach and must not be claimed.
- Results are automated control-testing observations to assist human review
  (CPS 230 Para 19 / CPS 234 Para 13), not a certification or regulatory filing.
- UI is server-rendered HTML strings in `src/web_ui.py` (Starlette), no frontend build step.

## Brand Commitments

- Product name: Agent Compliance Probe.
- No brand assets (logo, palette, typeface) exist yet.

## Evidence on Hand

- Live demo agents (vulnerable and guarded) in `src/agent_service/`.
- No customers, testimonials or benchmarks exist; do not fabricate them.

## Product Principles

1. Evidence over assertion: every verdict shows the probe sent, the response received and the clause it maps to.
2. Honest scope: say what a black-box probe can and cannot see.
3. Fail closed and say so: unreachable or errored is never shown as passed.
4. Engineer-first: fast to run, precise to read, easy to act on.
