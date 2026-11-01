# Guardian Compliance MCP

An MCP server that screens AI agents used by Australian insurers against the laws and codes they actually breach in
conversation. It covers general, life and private health insurance, and keeps the original APRA banking (ADI) scenarios.

Coverage is organised as **industry domain packs** over one shared, cited source library: insurance, banking,
superannuation, energy retail, telecommunications, water, Commonwealth public sector and commercial (see
[Coverage by industry](#coverage-by-industry)). Call `list_domains` to see each domain's
regulators, coverage level, verification dates and known gaps. Why one server rather than one per industry, and how
to add a domain: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/ADDING_A_DOMAIN.md`](docs/ADDING_A_DOMAIN.md).

It answers three questions for an AI platform or compliance team:

1. **What can this agent breach?** `get_obligations` lists the rule categories that apply to an agent's role and
   sector, with the obligations each one tests. `get_coverage_map` shows, clause by clause, what the MCP detects at
   runtime and what still needs human review.
2. **Did this interaction breach anything?** `audit_agent_for_regulatory_breach` screens a transcript turn and
   cites every obligation engaged, across regulators.
3. **What must we report, to whom, by when?** Findings carry dated clocks for APRA, ASIC, OAIC, the Code
   compliance committees and the ACSC.

> **Honest scope.** This is a screen, not a certification. Rules are deterministic and explainable; an optional
> semantic judge raises REVIEW flags for rewordings the rules miss. Measured recall and precision on a blind
> paraphrase corpus are published in [`reports/detection_metrics.md`](reports/detection_metrics.md). Obligations
> are stored as paraphrased summaries with source links and verification dates, not as legal advice.

### Responsibility and use

NCS uses Guardian as a test aid while it builds and tests AI agents in a client's environment. Suggested wording for
a statement of work:

> Guardian output (findings, review flags, citations, scores and reports) is a testing aid provided to the Client's
> risk and compliance team. It is not legal, regulatory or compliance advice and does not certify that an agent
> complies with any law, code or standard. The Client is responsible for validating each finding against the source
> obligation, deciding whether a breach has occurred, remediating its agent, and making any notification to a
> regulator or other party. The Client owns the compliance obligations of its business and of the agents it
> deploys, including accountability under its own risk management framework (for APRA-regulated entities, CPS 230).
> A probe that passes, or a run with no findings, is not evidence that no obligation was breached.

Detection accuracy figures in this repository come from small, single-author test sets and are for internal use;
do not quote them to clients as a performance commitment.

---

## Regulatory coverage

| Family | Instruments | How it is used |
| :--- | :--- | :--- |
| APRA prudential | CPS 230, CPS 234 (clause level); CPS 220, 510, 511, 520, 190, 900, CPG 230/234/235, GPS/LPS 230 (summary level); capital and valuation standards (out of scope) | Operational risk, critical operations, information security, APRA notification clocks |
| ASIC conduct | Insurance Contracts Act 1984 (s13 utmost good faith, s20B, s21, s54, s56, s33H genetic testing ban and more); ASIC Act 2001 (s12BF UCT, s12DA, s12DB, deferred sales model s12DO to s12DS); Corporations Act 2001 (s766G, s912A, s912D/912DAA, s949A, s961B, s992A, Part 7.8A DDO); RG 271, RG 274, RG 78, RG 38 | Claims handling, misrepresentation, advice, hawking, DDO, IDR, breach reporting |
| ACCC | Australian Consumer Law (s18, s21, s23, s29, s34, s50) | Private health insurance conduct (outside the ASIC Act financial product regime) |
| Codes | General Insurance Code of Practice 2020 (Oct 2023 update), Life Insurance Code of Practice (March 2025, CALI), Private Health Insurance Code of Conduct (Oct 2025) | Claims timeframes, vulnerability, family violence, hardship, complaints, sales, Code breach reporting |
| Health | Private Health Insurance Act 2007, Complying Product Rules | Community rating, Medicare restriction, waiting periods, tiers, portability |
| Privacy and cyber | Privacy Act 1988 (APPs, NDB scheme, ADM transparency, statutory tort), SOCI Act 2018, Cyber Security Act 2024 | PII leaks, disclosure without verification, sensitive information, cyber and ransomware reporting |
| Discrimination | DDA 1992 s46, SDA 1984 s41, ADA 2004 s37 | Underwriting statements on protected attributes |
| Accountability and AI | FAR Act 2023, ASIC REP 798, Voluntary AI Safety Standard and later guidance | Governance checklist items (not runtime breaches) |
| Watch list | CDR, Scams Prevention Framework Act 2025, AML/CTF tranche 2 | Mapped as not yet applicable to insurers |
| Superannuation (reference) | SIS Act 1993 (s52 and s52A covenants, s54B), SPS 515, SPS 530, RG 271 super complaint timeframes (RG 271.79, RG 271.80), plus CPS 230 and CPS 234 | Trustee duties, member outcomes, investment governance, complaint timeframes; verified 2026-10-27, no screening rules |

Call `list_instruments` for the live list with source URLs and verification dates.

## Coverage by industry

NCS uses Guardian to red-team the AI agents it builds for clients. Each industry has a red-team pack
(`src/data/redteam/<industry>.json`): breach categories a conversational agent can commit, the verified provisions
each one cites, and adversarial scenarios. Insurance and banking also have the deterministic rules described below.

| Industry | Instruments | Deterministic rule categories | Judge categories | Scenarios |
| :--- | ---: | ---: | ---: | ---: |
| Insurance (general, life, private health) | 44 | 23 | 2 | built-in suite |
| Banking | 8 | 3 | 7 | 14 plus built-in suite |
| Superannuation | 7 | 0 | 7 | 14 |
| Energy retail | 5 | 0 | 10 | 20 |
| Telecommunications | 7 | 0 | 11 | 22 |
| Water | 4 | 0 | 7 | 14 |
| Commonwealth public sector | 4 | 0 | 7 | 14 |
| Commercial (retail and consumer services) | 3 | 0 | 8 | 16 |

### Instruments by industry

Every instrument carries a verification date; CPS 230 and CPS 234 were re-verified on 2026-11-01.

| Industry | Instruments (regulator) |
| :--- | :--- |
| Insurance | **APRA:** CPS 190, 220, 230, 234, 510, 511, 520, 900; CPG 230, 234, 235; GPS 230; LPS 230; capital and valuation standards; AI letter 2026. **ASIC:** ICA 1984, ASIC Act 2001, Corporations Act 2001, RG 38, RG 78, RG 271, RG 274, REP 768, REP 798, genetic testing ban. **APRA and ASIC:** FAR Act 2023. **Codes:** GI Code, Life Code, PHI Code. **Health:** PHI Act 2007, Complying Product Rules. **OAIC:** Privacy Act 1988. **ACCC:** ACL, SPF Act 2025, CDR. **AUSTRAC:** AML/CTF Act 2006. **AHRC:** DDA 1992, SDA 1984, ADA 2004. **Cyber:** SOCI Act 2018, Cyber Security Act 2024. **AI guidance:** VAISS, Guidance for AI Adoption, National AI Plan 2025 |
| Banking | **APRA:** CPS 230, CPS 234. **ASIC:** ASIC Act 2001, NCCP Act, National Credit Code. **AUSTRAC:** AML/CTF Act. **Code:** Banking Code. **OAIC:** Privacy Act 1988 |
| Superannuation | **APRA:** SIS Act 1993, SPS 515, SPS 530, CPS 230, CPS 234. **ASIC:** RG 271 (super complaint timeframes). **OAIC:** Privacy Act 1988 |
| Energy retail | **AER:** NERL. **ESC Vic:** Electricity Industry Act (Vic), Energy Retail Code of Practice. **ACCC:** ACL. **OAIC:** Privacy Act 1988 |
| Telecommunications | **ACMA:** TCP Code, Complaints Standard, Hardship Standard, Identity Determination, Pre-Porting Standard. **ACCC:** ACL. **OAIC:** Privacy Act 1988 |
| Water | **ESC Vic:** Water Industry Act 1994 (Vic), Water Industry Standard (Urban Customer Service). **IPART NSW:** Sydney Water Operating Licence, Sydney Water Customer Contract |
| Commonwealth public sector | **OAIC:** FOI Act 1982, Privacy Act 1988. **ART:** ART Act 2024. **Commonwealth Ombudsman:** automated decision-making guide |
| Commercial | **ACCC:** ACL. **ACMA:** Spam Act 2003. **OAIC:** Privacy Act 1988 |

The Privacy Act is not tagged for water: water corporations are State authorities, outside the Commonwealth APPs.

### Breach categories by industry

| Industry | Deterministic rules | Judge only (REVIEW flags) |
| :--- | :--- | :--- |
| Insurance | Claim denial without authority, claim discouragement, complaint not recognised, missing AFCA referral, hallucinated cover, pricing misrepresentation, hawking, DDO outside target market, disclosure coaching, missing general advice warning, personal advice without authorisation, discriminatory underwriting, genetic test request, vulnerability or hardship ignored, unauthorised critical operation commitment, PII leak, disclosure without ID verification, sensitive information over-collection, system prompt exfiltration; PHI only: community rating breach, Medicare benefit promise, waiting period waiver | Claim timeframe misstatement, unfair claims handling |
| Banking | Unauthorised credit or payment commitment, PII leak, system prompt exfiltration | Hardship request ignored, enforcement threat during hardship, collections harassment, credit commitment without assessment, misleading rates or fees, AML tipping off, vulnerable customer not supported |
| Superannuation | | Complaint mishandled, death benefit objection dismissed, insurance claim discouraged, member interest conflict, plus privacy baseline |
| Energy retail | | Ignoring a life support declaration, threatening or misstating disconnection, hardship assistance not offered, payment plan refused, enrolment without explicit informed consent, misleading price or discount, misstating consent dispute rights, plus privacy baseline |
| Telecommunications | | Hardship not recognised, disconnection threat in hardship, complaint not recognised, complaint timeframe misstated, TIO not disclosed, high-risk transaction without authentication, irresponsible or pressure selling, misleading claims, plus privacy baseline |
| Water | | Payment assistance not offered, restriction or legal action threatened in hardship, life support or special needs ignored, collecting a disputed amount, insensitive collection communication, misleading billing statement, complaint or ombudsman not mentioned |
| Commonwealth public sector | | Eligibility advice presented as a decision, review rights omitted or denied, opaque automated decision, no human or accessible alternative, FOI request mishandled, unnecessary personal information collected, personal information disclosed |
| Commercial | | Consumer guarantee denial, misleading representation, pressure selling or exploitation, reliance on an unfair term, marketing without consent, plus privacy baseline |

The privacy baseline (`src/data/redteam/baseline.json`) adds disclosure without identity verification, sensitive
information over-collection and unauthorised third-party disclosure.

`get_red_team_scenarios(industry)` lists the scenarios; `probe_external_agent(target_url, sector=<industry>)` runs
them against an agent endpoint. Industries without rules depend on the semantic judge: with no judge configured a
reply is `INCONCLUSIVE` / `NOT_SCREENED`, never a pass. Sources were verified from primary text on 2026-10-27 and are
not yet signed off by a compliance SME; per-industry known gaps are in `list_domains`.

## What the screen detects

Rules run by role and sector (`claims_processing_agent` is general insurance, `life_*`/`ip_claims_agent` life,
`phi_*`/`health_*` private health, `lending_agent`/`payments_agent` banking; unknown roles run everything).

| Family | Categories |
| :--- | :--- |
| Claims | Unauthorised approval, payment or excess waiver; denial without authority; claims discouragement; misrepresentation coaching |
| Coverage and pricing | Hallucinated cover or exclusion waivers; price and loyalty promises |
| Advice and distribution | Personal advice without authorisation; missing general advice warning (review); hawking; DDO target market breaches (including caller-supplied TMD exclusions) |
| Complaints and vulnerability | Complaint not recognised; decline without AFCA or Ombudsman details; vulnerability or hardship ignored (review) |
| Privacy and security | Customer data leaks; disclosure without ID verification; sensitive information over-collection; system prompt exfiltration |
| Underwriting | Genetic test requests; discriminatory underwriting statements |
| Private health | Medicare-covered benefit promises; waiting period waivers; community rating breaches |
| Banking | Credit, payment and fee commitments under pressure |

Negations and conditionals ("I can't confirm your claim is approved", "once approved, we will pay") are not
flagged. Omissions that one turn cannot prove raise a **REVIEW** flag instead of a breach.

### Measured detection quality

A separate author wrote a 450-line paraphrase corpus (`tests/corpus/insurance/`) without seeing the rules. Rules were
tuned on `dev` only; `holdout` was never tuned against. Results on holdout (120 breach lines, 75 compliant lines):

| Configuration | Recall | Precision |
| :--- | ---: | ---: |
| Rules only (offline, deterministic) | 32% | 93% |
| Rules plus local judge (Ollama `qwen3:14b`, judge hits are REVIEW flags) | 73% | 80% |
| Rules plus hosted judge (Azure AI Foundry `gpt-5-6-sol`, Australia East, 2026-10-27) | 96% | 91% |

Industry packs, holdout, Azure judge (2026-10-27). Each set was written by one author who had not seen the category
descriptions and has **not** been reviewed by an SME; with 15 to 40 lines per pack, treat these as indicative only.

| Pack | Lines (breach) | Recall | Precision |
| :--- | ---: | ---: | ---: |
| Superannuation | 20 (12) | 100% | 92% |
| Privacy baseline | 15 (9) | 100% | 100% |
| Commercial | 25 (15) | 100% | 94% |
| Banking | 35 (21) | 95% | 100% |
| Energy retail | 35 (21) | 95% | 91% |
| Telecommunications | 40 (24) | 92% | 88% |
| Water | 35 (21) | 86% | 100% |
| Commonwealth public sector | 35 (21) | 100% | 100% |

Misses are mostly terse omissions (a reply that simply never offers payment assistance); the most common false alarm
is `DISCLOSURE_WITHOUT_IDENTITY_VERIFICATION` on account actions taken for the caller. Per-pack reports:
`reports/detection_metrics_holdout_<pack>_judge-azure_ai-gpt-5-6-sol-default.md`.

The rules reach 100% on the dev set they were tuned on, but they do not generalise to new phrasing. A rule hit is
usually right; an empty result is not evidence of compliance. Production use should enable the judge and route REVIEW
flags to a human. Re-measure with `scripts/evaluate_detection.py --split holdout [--judge <provider> --model <id>]`;
reports land in `reports/`.

### Audit results

Every `audit_agent_for_regulatory_breach` result carries, alongside the verdict and findings:

- `provenance`: engine version, `corpus_hash`, `rules_hash`, schema version, judge provider and model, and
  `screened_at`. Each finding has a deterministic `finding_id` and the `rule_version` that produced it, so a recorded
  decision can be tied to the exact rulebook and rule set it was made under.
- `timing_ms`: time spent in rules, judge and total.
- Redacted evidence: customer identifiers in quoted words are masked (`GUARDIAN_REDACT`, on by default). Detection
  always runs on the raw text.
- Multi-turn context: pass `prior_turns` (`[{"role": "customer"|"agent", "text": ...}]`) so earlier complaints,
  hardship disclosures and coercion count when screening the current reply. Complaint and vulnerability rules also
  credit acknowledgements the agent made in earlier turns.

### Optional semantic judge
Set `GUARDIAN_JUDGE_PROVIDER` to `anthropic`, `openai`, `azure_ai` or `ollama` (with the provider's API key, and
optionally `GUARDIAN_JUDGE_MODEL`, or use `provider/model`). NCS's default is Azure AI Foundry in Australia East, so
transcripts stay in an Australian region:

```bash
export GUARDIAN_JUDGE_PROVIDER=azure_ai/gpt-5-6-sol
export AZURE_AI_API_BASE=https://australiaeast.api.cognitive.microsoft.com/models
export AZURE_AI_API_KEY=...   # from the NCS Azure AI Foundry resource
```

 The judge may only choose catalogue categories, must quote evidence that exists in the
response, and its findings are REVIEW flags, never automatic breaches. Without it the screen is fully offline and
deterministic.

Latency controls (a local 14B judge takes about 12 seconds per call):

- `GUARDIAN_JUDGE_WHEN`: `rule_clean` (default) skips the judge when the rules already found a breach, since the
  verdict is FAILED anyway; `always` runs it on every reply; `off` disables it. `context["judge_when"]` overrides per call.
- `GUARDIAN_JUDGE_BUDGET_MS` (default 4000): hard wall-clock budget for one judge call. On expiry the audit falls back
  to rules only and `coverage_scope.judge` reads `timeout after <n> ms (rules only)`. `context["judge_budget_ms"]` overrides per call.
- The runtime guardrail (`guarded` mode in `src/agent_service/brains.py`) passes `judge_when=rule_clean` and
  `judge_budget_ms=1500`. In the live path the rules decide blocking; the judge's job is to raise REVIEW flags for
  human follow-up. For full judge coverage run it asynchronously (a second audit with a larger budget) off the reply path.

---

## MCP tools, resources and prompts

Guardian follows the pattern of large public MCP servers such as GitHub's toolsets and Supabase's feature groups and
project scoping: one server, a lean default surface, and opt-in toolsets. Only enabled toolsets are sent to the
client, so a Claude or Copilot session carries about 3,200 tokens of tool definitions by default instead of about
8,200 with everything on.

### Configuration

| Variable | Values | Default |
| :--- | :--- | :--- |
| `GUARDIAN_TOOLSETS` | comma-separated `core`, `reference`, `governance`, `redteam`, `demo`, `legacy`, or `all` | `core,reference` |
| `GUARDIAN_SECTORS` | comma-separated industries: `gi`, `life`, `phi` (or `insurance` for all three), `banking`, `superannuation`, `energy_retail`, `telecommunications`, `water`, `public_sector`, `commercial` | `gi,life,phi` |
| `GUARDIAN_JUDGE_PROVIDER` | `azure_ai`, `anthropic`, `openai`, `ollama`, optionally as `provider/model` (semantic judge) | off |
| `GUARDIAN_JUDGE_WHEN` | `always`, `rule_clean`, `off`: when the judge runs | `rule_clean` |
| `GUARDIAN_JUDGE_BUDGET_MS` | Hard wall-clock budget per judge call | 4000 |
| `GUARDIAN_REDACT` | `1` masks TFN, Medicare, card, BSB and account, email, phone, address, date of birth and person names in returned evidence, probe responses and dossiers; `0` disables (internal debugging only) | `1` |
| `GUARDIAN_REDACT_NAMES` | `0` turns off person-name masking only (names after cues such as customer or Mr, and common given names followed by a surname, become `[NAME]`); inherits `GUARDIAN_REDACT` | `1` |
| `GUARDIAN_STATE` | `NSW`, `VIC`, `QLD`, `WA`, `SA`, `TAS`, `ACT` or `NT`: state public holidays in business-day deadlines (2025-2027; other years use national holidays and say so in `day_basis`) | national only |

`GUARDIAN_SECTORS` scopes the server to one client's industries. A health fund sets `phi` and sees only private
health prompts, instruments and test cases; a telco sets `telecommunications`; a bank with an insurance arm sets
`banking,gi`. Red-team tools default to the scope, and an audit whose role does not name an industry is screened
against it. A `sector` passed on a call still overrides the scope for that call. See
[`docs/CLIENT_DEPLOYMENT.md`](docs/CLIENT_DEPLOYMENT.md).

### Toolsets

| Toolset | Tools | Default |
| :--- | :--- | :--- |
| `core` | `audit_agent_for_regulatory_breach`, `triage_customer_message`, `check_claim_timeframe`, `assess_regulatory_obligations`, `map_finding_to_obligations`, `get_obligations`, `get_coverage_map` | on |
| `reference` | `list_domains`, `list_instruments` (pass `code` for one instrument, or `domain`), `lookup_clause`, `search_regulations` (`domain` filter), `lookup_definition` | on |
| `governance` | `get_cps230_requirements`, `check_agent_architecture_compliance`, `analyze_agent_code` | off |
| `redteam` | `get_red_team_scenarios`, `get_insurance_red_team_test_cases`, `probe_external_agent`, `run_autonomous_red_team_probe` (these call external agent endpoints) | off |
| `demo` | `simulate_agent_red_team_audit`, `compare_simulated_agent_guardrails` | off |
| `legacy` | pre-0.3 names: `list_supported_standards`, `get_standard_summary`, `assess_incident_notification`, `get_critical_operations`, `get_material_service_providers`, `get_contract_requirements`, `get_standards_interaction`, `get_sector_adversarial_test_suite`, `probe_external_agent_for_apra_breaches`, `run_autonomous_mcp_red_team_probe`, and the `apra://` resources | off |

Measured tool-definition size (before `list_domains` was added): default 11 tools, ~3,200 tokens; `core` only 7 tools, ~2,300; `all` 29 tools, ~8,200. Default is now 12 tools and `all` 30.

Reference answers are traceable: each `search_regulations` and `lookup_clause` result has an `evidence` block
(`source_url`, `pinpoint`, `version`, `verified_on`, `current_status`, `expert_reviewed`, and `statement_kinds`
marking the text as a paraphrase of the source and the notes as editorial summary) plus a not-legal-advice
disclaimer. A search with no match returns `supporting_evidence: false` and says that this does not mean no obligation exists.

### Resources
* `guardian://instruments/{code}`: full paraphrased text of any instrument (for example `guardian://instruments/ICA-1984`).
* `guardian://obligations/{sector}`: what an agent in a sector can breach.
* `guardian://coverage-map`: coverage map as markdown.
* `legacy`: `apra://standards/CPS-230`, `apra://standards/CPS-234`, `apra://notifications/matrix`.

### Prompts
Shown only for the sectors in scope: `review_pds_answer`, `idr_complaint_triage`, `ddo_distribution_review` (general
and life), `life_claim_conduct_review` (life), `phi_member_conversation_audit` (private health). With `redteam`:
`red_team_insurance_agent`. With `governance`: `audit_policy_gap_analysis`, `review_third_party_contract`.

---

## Red-team testing

The opt-in `redteam` toolset tests an agent before release, over its normal chat endpoint and with no SDK or code
access. `probe_external_agent` runs the sector's adversarial scenarios (claims coercion, invented cover, data
exfiltration, hawking, genetic testing, Medicare benefits and more) and returns findings, reporting clocks and a Board
dossier. `run_autonomous_red_team_probe` climbs a four-stage escalation ladder and records a hash-chained evidence
trail. Private and loopback targets are blocked unless explicitly allowlisted.

```bash
GUARDIAN_TOOLSETS=core,reference,redteam uv run python -m src.server
```

`mock://insurance-wild-agent` and `mock://insurance-guarded-agent` are built-in targets for trying the tools without a
live agent. To exercise the runtime guardrail end to end, `run_agent_service.py` starts a demo insurance agent over
HTTP in `vulnerable`, `hardened` or `guarded` mode (see [AGENT_SERVICE.md](AGENT_SERVICE.md)).

---

## Setup & Installation

### Requirements
* Python 3.12+
* [`uv`](https://docs.astral.sh/uv/) package manager

### Installation
```bash
git clone https://github.com/ncsau-innovation/guardian-compliance-mcp.git
cd guardian-compliance-mcp
uv sync
```

### Installing as a package
The project builds as a wheel (`hatchling`), so it runs from any directory without a repo checkout:
```bash
uv build                                   # dist/guardian_compliance_mcp-*.whl
uvx --from /path/to/guardian-compliance-mcp guardian-compliance-mcp
# or: pip install dist/*.whl && guardian-compliance-mcp
```
The registry database is written beside the code when that directory is writable, otherwise to
`~/Library/Caches/guardian-compliance` (macOS) or `$XDG_CACHE_HOME/guardian-compliance` (`~/.cache/...`). Set
`GUARDIAN_DB_PATH` to choose another location.

### Running Tests
```bash
uv run pytest -v
```

---

## Shared NCS instance

The current deployment model is one shared Guardian instance for NCS's own work: development, demos, writing new
scenarios, and testing agents in NCS's environment before they are handed to a client. Per-client instances inside
a client's estate are not set up yet.

### Settings

Keep the settings in a file outside the repository (it holds the judge key), for example `~/.config/guardian/ncs.env`:

```bash
GUARDIAN_TOOLSETS=core,reference,redteam
GUARDIAN_JUDGE_PROVIDER=azure_ai/gpt-5-6-sol
GUARDIAN_JUDGE_WHEN=always
AZURE_AI_API_BASE=https://australiaeast.api.cognitive.microsoft.com/models
AZURE_AI_API_KEY=...            # from the NCS Azure AI Foundry resource
GUARDIAN_STATE=VIC              # state public holidays for business-day deadlines
```

The judge is required: superannuation, energy retail, telecommunications, water, public sector and commercial have
no deterministic rules, so without it every probe in those industries returns `NOT_SCREENED`. Leave
`GUARDIAN_SECTORS` unset so the shared instance serves every industry (a client instance sets it; see
[`docs/CLIENT_DEPLOYMENT.md`](docs/CLIENT_DEPLOYMENT.md)).

### On your own machine (stdio)

```bash
set -a; source ~/.config/guardian/ncs.env; set +a
claude mcp add guardian \
  -e GUARDIAN_TOOLSETS="$GUARDIAN_TOOLSETS" -e GUARDIAN_JUDGE_PROVIDER="$GUARDIAN_JUDGE_PROVIDER" \
  -e GUARDIAN_JUDGE_WHEN="$GUARDIAN_JUDGE_WHEN" -e GUARDIAN_STATE="$GUARDIAN_STATE" \
  -e AZURE_AI_API_BASE="$AZURE_AI_API_BASE" -e AZURE_AI_API_KEY="$AZURE_AI_API_KEY" \
  -- uv --directory /path/to/guardian-compliance-mcp run guardian-compliance-mcp
```

For Claude Desktop, VS Code or Cursor, put the same variables in the `env` block of the configs under
[Connecting to MCP Clients](#connecting-to-mcp-clients).

### One server for the team (HTTP)

```bash
docker build -f Dockerfile.http -t guardian-mcp .
docker run -d --name guardian -p 8765:8765 \
  --env-file ~/.config/guardian/ncs.env \
  -e GUARDIAN_HTTP_TOKEN_FILE=/run/secrets/tokens -v ~/.config/guardian/tokens:/run/secrets/tokens:ro \
  guardian-mcp
```

Give each person or tool its own token (one per line in the tokens file) so access can be revoked individually.
Keep the server on the NCS internal network behind a TLS proxy; see [Remote deployment](#remote-deployment) for the
proxy, rate limit and replica settings.

### Ground rules

1. **Name the industry on every call.** Pass `sector` to `probe_external_agent` and
   `audit_agent_for_regulatory_breach`, and `industry` to `get_red_team_scenarios`. Without it a generic role name
   such as `support_agent` is screened against insurance and banking law.
2. **Probe test agents only.** Point `probe_external_agent` at NCS-hosted test agents or `mock://` targets, never at
   a client's production endpoint.
3. **Judge findings are REVIEW flags.** A person confirms each one before it goes into anything shared outside the
   team (see [Responsibility and use](#responsibility-and-use)).
4. **New scenarios are data.** Add them to `src/data/redteam/<industry>.json` and run `uv run pytest -q`;
   `tests/test_redteam_packs.py` fails if a scenario's category or a cited provision does not resolve.

A typical run: `list_domains`, then `get_red_team_scenarios(industry="telecommunications")`, then
`probe_external_agent(target_url="https://<test-agent>/chat", sector="telecommunications", auth_token=...)`.

---

## Remote deployment

Besides stdio, Guardian can run as one central, access-controlled instance over MCP streamable HTTP (`src/http_server.py`). It serves `/mcp` behind bearer-token auth and an unauthenticated `GET /healthz` (`{"status","tools","corpus_hash"}`).

```bash
export GUARDIAN_HTTP_TOKENS="token-for-claude,token-for-guardrail"   # or GUARDIAN_HTTP_TOKEN_FILE (one per line)
uv run python -m src.http_server        # or the guardian-compliance-mcp-http script, once installed
```

| Variable | Default | Purpose |
|---|---|---|
| `GUARDIAN_HTTP_TOKENS` / `GUARDIAN_HTTP_TOKEN_FILE` | none | Accepted bearer tokens. The server refuses to start without any. |
| `GUARDIAN_HTTP_ALLOW_UNAUTHENTICATED` | unset | `1` allows no tokens, only when bound to loopback (development). |
| `GUARDIAN_HTTP_HOST` / `GUARDIAN_HTTP_PORT` | `127.0.0.1` / `8765` | Bind address. A warning is printed when binding non-loopback, since the server speaks plain HTTP. |
| `GUARDIAN_HTTP_RATE_PER_MIN` | `120` | Per-token token bucket (in memory, per process); excess requests get 429. `0` disables. |
| `GUARDIAN_HTTP_RATE_BACKEND` / `GUARDIAN_HTTP_REDIS_URL` | `memory` / unset | `redis` shares the per-token limit (fixed one-minute window) across replicas. Needs `pip install redis`; the server refuses to start if the package or URL is missing. |
| `GUARDIAN_HTTP_STATELESS` | `0` | `1` serves stateless streamable HTTP with JSON responses: no MCP session ids, so no sticky sessions. |
| `GUARDIAN_HTTP_MAX_BODY_BYTES` | `1048576` | Larger request bodies get 413. |
| `GUARDIAN_HTTP_ALLOWED_HOSTS` | unset | Public Host header names to allow-list (DNS-rebinding protection); when unset the Host check is off and bearer auth is the gate. |

Failed auth returns 401 with `WWW-Authenticate: Bearer`. Tokens are compared in constant time and never logged. Always put a TLS-terminating proxy (nginx, Caddy, a cloud load balancer) in front when exposing beyond localhost. Clients send `Authorization: Bearer <token>` to `https://host/mcp`.

The MCP app needs its session manager started by the ASGI lifespan, so run it with a lifespan-aware server (uvicorn, as `main()` does); in tests use `with TestClient(app):`.

**Running several replicas.** By default sessions live in one process and the limit is per process, so replicas would need sticky sessions. For a stateless fleet:

1. Set `GUARDIAN_HTTP_STATELESS=1` on every replica. Each request is then self-contained (no `Mcp-Session-Id`), so the load balancer can route freely.
2. Share the rate limit: either set `GUARDIAN_HTTP_RATE_BACKEND=redis` with `GUARDIAN_HTTP_REDIS_URL=redis://host:6379/0` (install `redis` in the image; the limiter fails open if Redis is down), or set `GUARDIAN_HTTP_RATE_PER_MIN=0` and rate limit at the proxy (nginx `limit_req`, an ALB/WAF rate rule).
3. Point load balancer health checks at `GET /healthz` (no auth; compare `corpus_hash` across replicas to spot a stale rollout).
4. Terminate TLS at the proxy and keep replicas on a private network, with the same tokens on every replica.

`Dockerfile.http` builds the remote server: `docker build -f Dockerfile.http -t guardian-mcp . && docker run -p 8765:8765 -e GUARDIAN_HTTP_TOKENS=... guardian-mcp`. Behind a TLS-intercepting proxy (for example Zscaler), add `--secret id=extra_ca,src="$SSL_CERT_FILE"` to the build; the CA is used only during the build and is not stored in the image.

---

## Connecting to MCP Clients

### 1. Claude Desktop
Add to `claude_desktop_config.json`, then fully quit and reopen Claude Desktop:

```json
{
  "mcpServers": {
    "guardian-compliance": {
      "command": "/path/to/guardian-compliance-mcp/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/guardian-compliance-mcp",
      "env": {"PYTHONPATH": "/path/to/guardian-compliance-mcp"}
    }
  }
}
```

Or, without a checkout path or virtualenv, using the packaged entrypoint:

```json
{
  "mcpServers": {
    "guardian-compliance": {
      "command": "uvx",
      "args": ["--from", "/path/to/guardian-compliance-mcp", "guardian-compliance-mcp"]
    }
  }
}
```

### 2. VS Code (Copilot agent mode)
The repo ships `.vscode/mcp.json` with a `guardian-compliance` stdio server. Open the folder, start the server from
the MCP view, and pick its tools in agent mode.

### 3. Cursor, Goose and other stdio clients
* **Command**: `/path/to/guardian-compliance-mcp/.venv/bin/python`
* **Arguments**: `["-m", "src.server"]` with the repo as working directory.

### 4. MCP Inspector
```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m src.server
```

---

## Project Structure

```
guardian-compliance-mcp/
├── src/
│   ├── server.py              # FastMCP server (guardian-compliance-mcp)
│   ├── db.py                  # Instrument registry: SQLite + FTS5, rebuilt when the corpus changes
│   ├── data/
│   │   ├── instruments/       # One JSON file per instrument, grouped by regulator (see its README)
│   │   ├── definitions.json   # Statutory definitions
│   │   └── notifications.json # Reporting timetable across regulators
│   ├── rules/
│   │   ├── catalog.py         # Rule catalogue mapped to obligations
│   │   ├── engine.py          # Matching, negation and materiality
│   │   ├── audit.py           # Orchestration, verdicts, reporting clocks
│   │   └── judge.py           # Optional semantic judge (REVIEW flags only)
│   ├── tools/                 # Lookup, search, notifications, coverage, claim timeframes, probes
│   ├── http_server.py         # Authenticated streamable HTTP transport
│   ├── provenance.py          # Corpus and rules hashes, finding ids, timing
│   ├── redaction.py           # PII and name masking for returned results
│   ├── simulation/            # Mock claims agent used by the demo toolset
│   └── agent_service/         # Demo agent service for testing the runtime guardrail
├── scripts/                   # Detection evaluation and corpus freshness checks
├── docs/                      # Production readiness tracker and corpus review pack
├── tests/
│   ├── corpus/insurance/      # Blind paraphrase corpus (dev and holdout)
│   └── test_*.py
└── reports/detection_metrics.md
```

---

## Adding or updating an instrument
1. Add or edit a JSON file under `src/data/instruments/<family>/` following `src/data/instruments/README.md`
   (paraphrase only, with `source_url` and `verified_on`).
2. Restart the server: the registry rebuilds automatically when any corpus file changes.
3. If a rule should cite the new clause, add a `Ref` in `src/rules/catalog.py`; `tests/test_rules_catalog.py`
   fails if any reference does not resolve.

---

## Further reading
- [docs/CLIENT_DEPLOYMENT.md](docs/CLIENT_DEPLOYMENT.md): running Guardian for one client engagement, by industry.
- [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md): what is production ready, what is open, and what needs people.
- [docs/CORPUS_REVIEW.md](docs/CORPUS_REVIEW.md): the expert sign-off pack for the regulatory corpus.
- [reports/detection_metrics.md](reports/detection_metrics.md): measured detection quality on the blind corpus.
