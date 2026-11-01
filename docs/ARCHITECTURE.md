# Architecture: one Guardian MCP, industry domain packs

Guardian is NCS's red-team harness for the AI agents it builds for clients. The regulatory corpus exists so that
every finding cites a verified provision; it is kept as broad and as fresh as the red-team categories need, not as a
general regulatory content service.

Guardian is a single MCP server that covers several Australian industries. Each industry is a **domain pack**
(`src/data/domains/<id>.json`) over one shared library of instruments (`src/data/instruments/`). You turn
capabilities on with toolsets (`GUARDIAN_TOOLSETS`) and narrow the insurance screening scope with `GUARDIAN_SECTORS`.

```
Guardian MCP (one server, one codebase)
 ├─ Core engine         registry and FTS search (src/db.py), lookup and citations (src/tools/lookup.py, search.py),
 │                      provenance, redaction, HTTP auth, freshness monitor (scripts/check_corpus_freshness.py)
 ├─ Source library      one JSON per instrument, tagged with the sectors it binds; shared, never copied per domain
 ├─ Domain packs        coverage metadata per industry (src/data/domains/)
 ├─ Red-team packs      breach categories, cited obligations and scenarios per industry (src/data/redteam/)
 ├─ Detectors           deterministic rules (insurance, banking: src/rules/catalog.py) and a semantic judge
 │                      driven by pack categories (src/rules/judge.py; NCS default azure_ai/gpt-5-6-sol, Australia East)
 └─ Toolsets            reference: list_domains, list_instruments, search_regulations, lookup_clause, lookup_definition
                        core: insurance screening, triage, claim timeframes, reporting clocks
                        governance, redteam, demo, legacy: opt-in
```

## Why one server rather than one per domain

- **Sources overlap.** The Privacy Act, Corporations Act, ASIC Act, CPS 230, CPS 234 and RG 271 bind several
  industries. With one server per industry, each instrument would exist in several copies, and those copies would
  drift apart in verification date and version.
- **One citation and freshness pipeline.** The lock file, the weekly drift check and the expert review pack run
  once over every source.
- **Cross-industry questions.** For example, a super fund that offers insurance or a bank that distributes it. One
  search returns cited answers across domains, instead of leaving the client model to merge separate servers.
- **Client context.** Separate servers would expose near-identical `search` and `lookup` tools. Models choose
  poorly between near-identical tools, and every client has to configure every server.
- **One security surface.** One set of auth, rate limits, redaction and audit trail to review.

Split by **deployment, not codebase**. Run the same image as separate deployments when there is a real boundary: a
tenant's own documents, licensed content only some users may see, per-domain data residency or SLAs, or separate
change control. Do not split by regulator: obligations attach to the entity and its activity, and users ask by
industry and task.

## Red-team packs

Each `src/data/redteam/<id>.json` lists categories (a judge-readable description, a severity, and obligations that
must resolve in the registry; `tests/test_redteam_packs.py` enforces this) and scenarios. `baseline.json` holds
privacy categories shared by superannuation, energy retail, telecommunications and commercial packs. Water uses State
privacy law (not loaded) and public sector has agency-specific privacy categories, so neither uses the baseline.

How a reply is screened (`src/rules/audit.py`):

1. Sectors come from an explicit `sector` (any domain id or alias) or from role keywords.
2. Rules run where they exist (insurance, banking).
3. The judge is offered the rule categories plus every pack category for those sectors, with an industry reviewer
   persona. Insurance keeps the exact prompt its published metrics were measured with.
4. Judge findings are REVIEW flags that cite the pack category's obligations.
5. With no rules and no judge the result is `INCONCLUSIVE` / `NOT_SCREENED`; red-team reports count those
   separately and never as passes.

Every pack needs a labelled evaluation set (`tests/corpus/<pack>/{dev,holdout}.jsonl`) written independently of its
category descriptions, and its measured recall and precision belong in the report given to a client.

## Design rules

1. **Domains describe coverage. Instruments decide applicability.** A domain pack lists regulators, coverage level,
   scope notes and known gaps. It never says an obligation applies; only instrument and clause `sectors` do, and
   they are set only where the source confirms scope.
2. **Every reference answer is traceable.** `search_regulations` and `lookup_clause` results carry `evidence`:
   `source_url`, `pinpoint`, `version`, `verified_on`, `current_status`, `expert_reviewed` and `statement_kinds`
   (`text` is a paraphrase of the source; `notes` is an editorial summary).
3. **No date-only "current" claim.** `verified_on` records when someone last checked the source.
   `current_status` stays "not established" because the server cannot prove that law has not changed since then.
   The drift monitor is what detects change.
4. **Honest empty results.** `supporting_evidence: false` plus a `determination` that says this does not mean no
   obligation exists.
5. **Not legal advice.** Every reference answer includes the disclaimer.
6. **Adding a domain is data only.** See `ADDING_A_DOMAIN.md`.

## Security and operational notes

- The reference corpus is public, read-only data. The reference tools take no customer data and make no outbound
  calls.
- Customer transcripts reach only the screening tools. Redaction (`GUARDIAN_REDACT`) and the HTTP server's bearer
  tokens and rate limits are unchanged.
- `snapshot` and `diff` in the freshness script fetch every corpus `source_url`. Every request, including each
  redirect hop, must be HTTPS to a `.gov.au` host or a named code owner or utility (`ALLOWED_HOSTS` in
  `scripts/check_corpus_freshness.py`); anything else is recorded as unreachable and never fetched. A new source on
  another host needs an `ALLOWED_HOSTS` entry, which makes it visible in code review.
- Per-tenant access control is not implemented. It is required before any feature that ingests customer documents
  or licensed standards.

## Stages

| Stage | Scope |
| :-- | :-- |
| 1 (done) | Red-team packs for all eight industries, industry-neutral judge with Azure AI Foundry provider, INCONCLUSIVE results, `get_red_team_scenarios` |
| 1 (done) | Domain packs, `list_domains`, `domain` filters, evidence blocks, honest empty results, superannuation example domain, domain filter in freshness checks |
| 2 | `source_version` and clause deep links across the existing corpus, filled from lock file compilation ids |
| 3 | Further packs, each with expert sign-off: banking reference, utilities (energy regulators), public sector, commercial businesses |
| 4 | Change tracking from lock history, an obligation finder by entity type and activity, tenant scoping |
