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
| Multi-turn screening | Done | `prior_turns` on the audit tool; history-aware gates and omission checks |
| Remote server with authentication | Done | `src/http_server.py`: bearer tokens, rate limit, body limit, `/healthz`, refuses to start unauthenticated off loopback |
| Corpus change monitoring | Done | `scripts/check_corpus_freshness.py` (`staleness`, `snapshot`, `diff`, `review-pack`); baseline lock of 44 sources |
| Judge latency budget for the runtime guardrail | Done | `GUARDIAN_JUDGE_WHEN` (default `rule_clean`) and `GUARDIAN_JUDGE_BUDGET_MS` (default 4000) with per-call overrides; guarded mode uses 1500 ms; timeout falls back to rules only; `tests/test_judge_budget.py` |
| Lean default tool surface | Done | Toolsets and sector scoping; default ~3,200 tokens of tool definitions |

Test suite: 286 tests pass in all three CI configurations.

## Engineering follow-ups

| Item | Why it matters |
| :--- | :--- |
| Build and scan `Dockerfile.http` | Not built yet: the Docker daemon was not running during verification |
| Shared rate limiting and stateless HTTP sessions | The rate limit is per process and sessions are stateful; multiple replicas need sticky sessions or `stateless_http` |
| State public holidays | Business-day clocks exclude national holidays only |
| Weekly `diff` job | Suggested in `docs/CORPUS_REVIEW.md`; not yet a scheduled workflow |
| Reduce false "changed" results in `diff` | Whole-page hashing flags navigation or banner changes on source sites |
| Name redaction | Redaction is pattern-based; free-text names and non-AU identifiers are not masked |

## Needs people

| Item | Owner | What is needed |
| :--- | :--- | :--- |
| Expert review of the corpus | Compliance or legal SME | Work through `docs/CORPUS_REVIEW.md`, starting with the ten known open items, and sign the table at the end |
| Detection benchmark on real transcripts | Pilot partner and Guardian team | Anonymised production transcripts, labelled by the partner's compliance team; set per-category accuracy targets |
| Hosted judge evaluation | Guardian team | Benchmark Claude and GPT judges on the holdout and partner data; decide the production judge and its data-residency terms |
| Privacy and CPS 230 assessment | Customer's risk team | Cross-border disclosure (APP 8) if a hosted judge is used; whether Guardian is a material service provider |
| Security review | Independent reviewer | HTTP server, token handling, SSRF guards in the probe tools, dependency scan |
