# Production readiness

Status of Guardian Compliance MCP against the path to production agreed on 2026-10-19. Engineering items are
tracked here with the commit that delivered them; items that need people are listed with what they need.

## Engineering (done on `feat/guardian-production-readiness`)

| Item | Status | Evidence |
| :--- | :--- | :--- |
| Installable package and entry points | Done | `pyproject.toml` build system; wheel installs into a clean venv and serves 44 instruments over stdio and HTTP from outside the repo |
| Database outside the install directory | Done | `src/db.py` `resolve_db_path()`: `GUARDIAN_DB_PATH`, package dir if writable, else per-user cache |
| Continuous integration | Done | `.github/workflows/ci.yml`: tests in default, `GUARDIAN_TOOLSETS=all` and `GUARDIAN_SECTORS=phi`, plus wheel build |
| Finding provenance and audit trail | Done | `src/provenance.py`: corpus hash, rules hash (including reporting triggers), judge model, finding ids, timing |
| Personal information redaction | Done | `src/redaction.py`: checksum-validated TFN, Medicare and card masking, plus BSB/account, email, phone, address, DOB |
| Name redaction | Done | `src/redaction.py` `redact_names()` with `src/data/given_names.txt` (SSA public-domain list plus AU supplement); `GUARDIAN_REDACT_NAMES`. Hand-labelled set: precision 1.00, recall 1.00 (17 names); blind-corpus false positives 0 of 179 capitalised tokens in 200 reply sentences; recall on corpus customer replies about 75% (misses lone first names and ambiguous names such as Mark) |
| Multi-turn screening | Done | `prior_turns` on the audit tool; history-aware gates and omission checks |
| Remote server with authentication | Done | `src/http_server.py`: bearer tokens, rate limit, body limit, `/healthz`, refuses to start unauthenticated off loopback |
| Corpus change monitoring | Done | `scripts/check_corpus_freshness.py` (`staleness`, `snapshot`, `diff`, `review-pack`); baseline lock of 44 sources |
| Container image | Done | `Dockerfile.http` builds (286 MB, non-root uid 10001, HEALTHCHECK on /healthz); refuses to start without tokens (exit 2); 401 without and 200 with a token; optional build-time CA secret for TLS-intercepting proxies, not written to any layer; `pip-audit` reports no known vulnerabilities in its 29 Python packages. Trivy 0.76.0: 0 critical, 0 fixable high; 44 high in Debian 13 base packages (util-linux, ncurses, perl, systemd libs) with no Debian fix yet, none used by the app; CI `image` job builds, smoke-tests and fails on fixable critical/high |
| Shared rate limiting and stateless HTTP sessions | Done | `GUARDIAN_HTTP_STATELESS=1` (FastMCP `stateless_http` + JSON responses) and `GUARDIAN_HTTP_RATE_BACKEND=redis` (lazy `redis`, fixed-window); tests in `tests/test_http_server.py`; recipe in README "Remote deployment" |
| Judge latency budget for the runtime guardrail | Done | `GUARDIAN_JUDGE_WHEN` (default `rule_clean`) and `GUARDIAN_JUDGE_BUDGET_MS` (default 4000) with per-call overrides; guarded mode uses 1500 ms; timeout falls back to rules only; `tests/test_judge_budget.py` |
| Weekly `diff` job and fewer false "changed" results | Done | `.github/workflows/corpus-freshness.yml` (Monday 21:00 UTC, `staleness` then `diff --json`, artifact plus issue on change); `diff` now uses per-source signals (legislation compilation id, PDF hash and length, main-content hash) recorded in `sources.lock.json`; lock regenerated and 44 of 44 sources unchanged on an immediate re-run |
| State public holidays | Done | `state` argument or `GUARDIAN_STATE`; verified 2025-2027 data in `src/data/holidays/au_public_holidays.json` (verified 2026-10-19), national fallback reported in `day_basis`; `tests/test_holidays.py` |
| Lean default tool surface | Done | Toolsets and sector scoping; default ~3,200 tokens of tool definitions |
| Red-team packs for all industries | Done | `src/data/redteam/` (banking, superannuation, energy retail, telecommunications, water, Commonwealth public sector, commercial, privacy baseline: 48 categories, 96 scenarios); citations verified from primary text 2026-10-27 and enforced by `tests/test_redteam_packs.py`; judge provider `azure_ai` (Azure AI Foundry, Australia East); `INCONCLUSIVE` when nothing can screen a reply |
| Industry domain packs and traceable reference answers | Done | `src/data/domains/`, `list_domains`, `domain` filters, `evidence` blocks and disclaimer on search and lookup, `supporting_evidence: false` on empty results, superannuation example domain; `tests/test_domains.py`; see `docs/ARCHITECTURE.md` |
| CPS 230 and CPS 234 verified | Done | Both checked on 2026-11-01 against the Federal Register (F2026L00475, F2018L01745). The 2026 CPS 230 renumbers the standard, so every CPS 230 citation in the corpus, rules, notification clocks, definitions and prompts moved to the new paragraph numbers (72-hour notice para 32, 24-hour notice para 41, critical operations paras 34 and 35, material service providers paras 48 to 50, formal agreements para 53, 20 business day notice para 60(a)) |
| Freshness fetcher egress allow-list | Done | `scripts/check_corpus_freshness.py`: HTTPS only, `.gov.au` plus named code owners and utilities, checked on every redirect hop; `tests/test_corpus_freshness.py` covers metadata IPs, plain HTTP, look-alike hosts, redirects and that every corpus source is allowed |
| Probe scoring and report | Done | Probes are counted as passed, failed, flagged for review (the judge found a possible breach) or not screened; a flagged probe is never a pass, so an agent the judge flags on every probe scores 0%, not 100% "compliant". The report renders judge findings with their citations, labels each probe accordingly, treats superannuation as APRA-regulated and gives non-APRA industries a non-APRA roadmap; scenario filters no longer fall back to the full suite. Found by an external (agy) review on 2026-11-01 |

Test suite: 387 tests pass in all three CI configurations.

## Engineering follow-ups

| Item | Why it matters |
| :--- | :--- |
| Non-AU identifiers and lone names | Names are masked by cue or given-name list; a lone surname or single given name with no cue, and non-AU identifiers, are not masked |
| National Energy Retail Rules | AEMC returned HTTP 403 to automated requests on 2026-10-27, so NERR rule numbers (payment plans, hardship, Part 7 life support) are not cited; energy coverage in NECF states rests on the NERL. Download the current NERR in a browser and verify before adding cites |
| Version-pinned state sources | Victorian legislation, ESC codes, the Sydney Water contract and the NERL are cited by version-specific PDF URLs, so the drift check cannot see new versions; watch their landing pages or re-verify quarterly |
| Unfixed Debian base CVEs | 44 high findings await Debian fixes; re-scan weekly, or move to a minimal base (for example a distroless or Wolfi Python image) once it supports Python 3.12+ with pinned tags |

## Needs people

| Item | Owner | What is needed |
| :--- | :--- | :--- |
| Review drifted sources (found 2026-10-27) | Compliance or legal SME | `diff` reports 4 changed sources against the 2026-10-19 lock: ICA 1984 new compilation (C2024C00063 to C2026C00473), CPS 230 Federal Register page (re-verified 2026-11-01; refresh the lock entry), RG 78 page and the Guidance for AI Adoption page. Re-verify the affected entries, then refresh the lock with `snapshot` |
| Expert review of the corpus | Compliance or legal SME | Work through `docs/CORPUS_REVIEW.md`, starting with the ten known open items, and sign the table at the end |
| Detection benchmark on real transcripts | Pilot partner and Guardian team | Anonymised production transcripts, labelled by the partner's compliance team; set per-category accuracy targets |
| Judge evaluation | Guardian team | Default judge chosen: `azure_ai/gpt-5-6-sol` (Azure AI Foundry, Australia East). Measure it on every pack holdout (`scripts/evaluate_detection.py --corpus <pack>`) and on partner transcripts before quoting detection rates to clients |
| Privacy and CPS 230 assessment | Customer's risk team | Transcripts go to Microsoft Azure AI Foundry in Australia East when the judge runs: confirm the client accepts Microsoft as a service provider for test transcripts (and APP 8 if any other region is used); whether Guardian is a material service provider |
| Security review | Independent reviewer | HTTP server, token handling, SSRF guards in the probe tools, dependency scan |
