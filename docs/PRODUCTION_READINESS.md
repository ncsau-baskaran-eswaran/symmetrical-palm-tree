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

Test suite: 286 tests pass in all three CI configurations.

## Engineering follow-ups

| Item | Why it matters |
| :--- | :--- |
| Non-AU identifiers and lone names | Names are masked by cue or given-name list; a lone surname or single given name with no cue, and non-AU identifiers, are not masked |
| Unfixed Debian base CVEs | 44 high findings await Debian fixes; re-scan weekly, or move to a minimal base (for example a distroless or Wolfi Python image) once it supports Python 3.12+ with pinned tags |

## Needs people

| Item | Owner | What is needed |
| :--- | :--- | :--- |
| Expert review of the corpus | Compliance or legal SME | Work through `docs/CORPUS_REVIEW.md`, starting with the ten known open items, and sign the table at the end |
| Detection benchmark on real transcripts | Pilot partner and Guardian team | Anonymised production transcripts, labelled by the partner's compliance team; set per-category accuracy targets |
| Hosted judge evaluation | Guardian team | Benchmark Claude and GPT judges on the holdout and partner data; decide the production judge and its data-residency terms |
| Privacy and CPS 230 assessment | Customer's risk team | Cross-border disclosure (APP 8) if a hosted judge is used; whether Guardian is a material service provider |
| Security review | Independent reviewer | HTTP server, token handling, SSRF guards in the probe tools, dependency scan |
