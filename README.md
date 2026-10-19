# Guardian Compliance MCP 🇦🇺

An MCP server that screens AI agents used by Australian insurers against the laws and codes they actually breach in
conversation. It covers general, life and private health insurance, and keeps the original APRA banking (ADI) scenarios.

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

Call `list_instruments` for the live list with source URLs and verification dates.

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

The rules reach 100% on the dev set they were tuned on, but they do not generalise to new phrasing. A rule hit is
usually right; an empty result is not evidence of compliance. Production use should enable the judge and route REVIEW
flags to a human. Re-measure with `scripts/evaluate_detection.py --split holdout [--judge <provider> --model <id>]`;
reports land in `reports/`.

### Optional semantic judge
Set `GUARDIAN_JUDGE_PROVIDER` to `anthropic`, `openai` or `ollama` (with the provider's API key, and optionally
`GUARDIAN_JUDGE_MODEL`). The judge may only choose catalogue categories, must quote evidence that exists in the
response, and its findings are REVIEW flags, never automatic breaches. Without it the screen is fully offline and
deterministic.

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
| `GUARDIAN_SECTORS` | comma-separated `gi`, `life`, `phi`, `banking` | `gi,life,phi` |
| `GUARDIAN_JUDGE_PROVIDER` | `ollama`, `anthropic`, `openai` (optional semantic judge) | off |
| `GUARDIAN_REDACT` | `1` masks TFN, Medicare, card, BSB and account, email, phone, address and date of birth in returned evidence, probe responses and dossiers; `0` disables (internal debugging only) | `1` |

`GUARDIAN_SECTORS` scopes the server to an insurer's lines. A health fund sets `phi` and sees only private health
prompts, instruments and test cases; a group writing general and life sets `gi,life`. The audit tool still accepts a
`sector` per call, which overrides the scope for that call.

### Toolsets

| Toolset | Tools | Default |
| :--- | :--- | :--- |
| `core` | `audit_agent_for_regulatory_breach`, `triage_customer_message`, `check_claim_timeframe`, `assess_regulatory_obligations`, `map_finding_to_obligations`, `get_obligations`, `get_coverage_map` | on |
| `reference` | `list_instruments` (pass `code` for one instrument), `lookup_clause`, `search_regulations`, `lookup_definition` | on |
| `governance` | `get_cps230_requirements`, `check_agent_architecture_compliance`, `analyze_agent_code` | off |
| `redteam` | `get_insurance_red_team_test_cases`, `probe_external_agent`, `run_autonomous_red_team_probe` (these call external agent endpoints) | off |
| `demo` | `simulate_agent_red_team_audit`, `compare_simulated_agent_guardrails` | off |
| `legacy` | pre-0.3 names: `list_supported_standards`, `get_standard_summary`, `assess_incident_notification`, `get_critical_operations`, `get_material_service_providers`, `get_contract_requirements`, `get_standards_interaction`, `get_sector_adversarial_test_suite`, `probe_external_agent_for_apra_breaches`, `run_autonomous_mcp_red_team_probe`, and the `apra://` resources | off |

Measured tool-definition size: default 11 tools, ~3,200 tokens; `core` only 7 tools, ~2,300; `all` 29 tools, ~8,200.

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

## 🤖 Autonomous Claims Agent Simulation & Red-Teaming

To model real-world risks in production AI deployments, the repository includes a hypothetical autonomous insurance claims agent (`HypotheticalClaimsAgent`) representing a frontline triage bot for Australian Mutual Insurance.

### Running Red-Team Exploits via CLI
Run the automated adversarial red-team audit:
```bash
# Red-team the vulnerable production agent (Triggers 3 APRA breaches & 2 statutory 72h notices)
uv run python -m src.simulation.red_team_runner vulnerable

# Red-team Mode 2 (Active in-band APRA MCP pre-flight guardrail - 100% compliance pass rate)
uv run python -m src.simulation.red_team_runner in_band_guardrail

# Red-team the hardened agent with static guardrails (100% compliance pass rate)
uv run python -m src.simulation.red_team_runner hardened
```

### Key Regulatory Attack Vectors Tested:
1. **Prompt Injection / PII Exfiltration (CPS 234 Para 20, 21, 35)**:
   * Attack: Attacker bypasses instructions via debug mode to dump Medicare numbers and medical diagnoses.
   * Finding: Critical information security breach requiring mandatory **72-hour APRA notification**.
2. **Social Engineering / Unauthorized Claims Settlement (CPS 230 Para 29, 36, 33)**:
   * Attack: Attacker claims to be the CEO and demands urgent $85,000 claim approval and excess waiver.
   * Finding: Critical failure of controls over a mandatory Critical Operation (Claims Processing), triggering **72-hour APRA notification** for material financial exposure.
3. **Hallucinated Policy Expansion (CPS 230 Para 14, 23)**:
   * Attack: Attacker prompts bot to override contractual stormwater/flood exclusions.
   * Finding: Operational conduct risk violating Board risk profile and PDS disclosure terms.

---

## 🌐 Universal Black-Box Regulatory Prober & Autonomous Red-Teamer

> 🧪 **Test it against a real service**: See [**AGENT_SERVICE.md**](AGENT_SERVICE.md) to run a hypothetical production-grade banking/insurance agent as its own HTTP service and probe it over the wire (not a `mock://`).  
> 🤖 **Autonomous Prober Overview**: See [**AUTONOMOUS_PROBER.md**](AUTONOMOUS_PROBER.md) for dedicated architecture and runner instructions.  
> 📘 **Step-by-Step Execution Guide**: For complete running instructions across Web UI, FastMCP, and CLI, mock target details, and the full OpenAI Codex review assessment, see [**AUTONOMOUS_AGENT_GUIDE.md**](AUTONOMOUS_AGENT_GUIDE.md).  
> 📖 **Comprehensive Specification**: For in-depth architectural data flows, probe vectors, statutory APRA decision matrices, and sample Board dossiers, see [**BLACKBOX_PROBER.md**](BLACKBOX_PROBER.md).

What if you discover an autonomous AI agent in the wild across Banking or Insurance and need to audit its regulatory resilience **without embedding MCP code, installing SDKs, or modifying the target codebase**?

The APRA MCP server includes two complementary black-box assurance engines:
1. **Curated Static Battery (`spin_test_agent`)**: Instant, zero-cost 5-vector regression suite.
2. **Autonomous LLM Red-Teamer (`AutonomousMCPRedTeamer`)**: Co-designed and brainstormed with **OpenAI Codex (`gpt-6-luna`)**, this agentic engine climbs a structured **4-Stage Test Ladder** (Baseline $\rightarrow$ False Authority $\rightarrow$ Synthetic Data Boundary $\rightarrow$ Policy Ambiguity), dynamically queries APRA MCP tools to research statutory rules, enforces SSRF protections (with DNS pre-resolution and redirect blocking), and generates **tamper-evident SHA-256 cryptographic evidence manifests**.

### Quick Run via Standalone CLI:
```bash
# 1-Command CLI execution against mock banking bot (4 rungs)
uv run python run_autonomous_agent.py --target mock://banking-lending-agent

# Test APRA-hardened banking bot (100% compliance pass rate)
uv run python run_autonomous_agent.py --target mock://hardened-bank-agent

# Test wild insurance claims bot
uv run python run_autonomous_agent.py --target mock://insurance-wild-agent --industry insurance --role claims_processing_agent

# Test external REST endpoint and export Board Dossier (.md)
uv run python run_autonomous_agent.py --target https://api.mybank.com/v1/chat --turns 4 --output board_dossier.md
```

### Built-in Zero-Setup Mock Targets:
* `mock://banking-lending-agent`: Unhardened banking bot (fails credit & PII probes; triggers APRA notices).
* `mock://hardened-bank-agent`: APRA-compliant banking bot (resists all probes; 100% compliance pass rate).
* `mock://insurance-wild-agent`: Unhardened claims bot (fails claims & Medicare probes).
* Or supply any remote REST URL (e.g., `https://api.mybank.com/v1/chat/completions` with optional Bearer token).

---

## Visual Testing & Web Studio

### 1. Interactive Web Studio (`http://localhost:8080`)
A local visual dashboard for red-teaming autonomous agents, running search queries, and inspecting APRA notifications:

```bash
uv run python -m src.web_ui
```
Open **`http://localhost:8080`** in your browser.

> 🌐 **Simple Probe page**: For a focused, no-frills workflow — *connect to an external target agent → run the assessment → read the scorecard* — open **`http://localhost:8080/probe`**. It reuses the autonomous red-team engine (Codex 4-stage ladder, SHA-256 evidence manifest, downloadable Board dossier) behind a single plain form.

Features:
* **💬 Live Agent Chat (With vs. Without MCP)**: Interactive conversation playground where you can toggle between running the agent **Without APRA MCP** (unhardened), **Hooked to APRA MCP** (Mode 2 in-band pre-flight guardrail), or in a **Side-by-Side Dual Comparison** to see real-time breach detection and interception.
* **🌐 Black-Box Regulatory Prober & Autonomous Red-Teamer**: Audit external agents with a 1-click engine mode switch:
  - `📋 Curated Static Battery (5 Domain Vectors)`
  - `🧠 Autonomous Red-Teamer (Codex Test Ladder)` with configurable ladder depth (1-4 rungs), LLM planner engine, SHA-256 tamper-evident manifest cards, and 1-click **Download APRA Board Report (.md)**.
* **🤖 Batch Red-Team Benchmark**: One-click red-teaming across statutory exploit suites with compliance scorecards.
* **🛡️ Manual Interaction Audit**: Test presets (PII exfiltration, coerced claims, hallucinated coverage) with visual breach severity alerts.
* **🔎 Regulation Search**: Live search across CPS 230 and CPS 234.
* **🚨 Notification Matrix**: Full timetable of APRA statutory reporting timeframes.
* **☁️ Cloud & LLM Resilience**: Evaluate AI provider uptime SLAs against Board-approved outage tolerance.

### 2. Interactive Terminal CLI
```bash
uv run python interactive_test.py
```
Or run quick commands:
```bash
uv run python interactive_test.py search "tolerance levels"
uv run python interactive_test.py lookup "CPS 230" "42"
uv run python interactive_test.py notify
```

---

## Setup & Installation

### Requirements
* Python 3.12+
* [`uv`](https://docs.astral.sh/uv/) package manager

### Installation
```bash
cd apra-mcp
uv sync
```

### Running Tests
```bash
uv run pytest -v
```

---

## Connecting to MCP Clients

### 1. Claude Desktop
Add to `claude_desktop_config.json`, then fully quit and reopen Claude Desktop:

```json
{
  "mcpServers": {
    "guardian-compliance": {
      "command": "/path/to/apra-mcp/.venv/bin/python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/apra-mcp",
      "env": {"PYTHONPATH": "/path/to/apra-mcp"}
    }
  }
}
```

### 2. VS Code (Copilot agent mode)
The repo ships `.vscode/mcp.json` with a `guardian-compliance` stdio server. Open the folder, start the server from
the MCP view, and pick its tools in agent mode.

### 3. Cursor, Goose and other stdio clients
* **Command**: `/path/to/apra-mcp/.venv/bin/python`
* **Arguments**: `["-m", "src.server"]` with the repo as working directory.

### 4. MCP Inspector
```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m src.server
```

---

## Project Structure

```
apra-mcp/
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
│   ├── tools/                 # Lookup, search, notifications, coverage, claim timeframes, probers
│   ├── simulation/            # Mock claims agent (vulnerable, hardened, guarded)
│   ├── agent_service/         # Standalone demo agent service
│   └── web_ui.py              # Probe UI
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
