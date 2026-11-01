# Adding a domain or a source

A domain pack is data only. No Python changes are needed. Use `src/data/domains/superannuation.json` and the
superannuation instruments (`src/data/instruments/superannuation/sis_act_1993.json`, `apra/sps_515.json`,
`apra/sps_530.json`) as the worked example.

## 1. Write the domain pack

Create `src/data/domains/<id>.json`:

```json
{
  "id": "utilities",
  "name": "Utilities (energy)",
  "aliases": ["energy"],
  "sectors": ["energy_retail"],
  "coverage": "reference",
  "owner": "Team or person accountable for keeping it current",
  "regulators": [{"name": "Regulator", "role": "What it regulates for this domain"}],
  "scope_notes": "What is covered and what is deliberately out of scope.",
  "known_gaps": ["Instruments a user might expect that are not loaded."]
}
```

- `coverage` is `reference` unless detection rules, test cases and a measured benchmark exist (then `screening`).
- `sectors` must each be used by at least one instrument (the test suite checks this). Ids and aliases must be
  unique across packs.
- Record regulators and their roles only as you have confirmed them from the regulator's own site.

## 2. Add or re-tag instruments

- Add a new instrument file under `src/data/instruments/<family>/` (schema: `src/data/instruments/README.md`).
- For an existing cross-industry instrument, add the new sector to the instrument's `sectors`. Then add clauses, or
  re-tag existing ones, **only** for provisions whose scope you confirmed. Clause `sectors` decide what a domain
  search returns. RG 271 is the example: `superannuation` was added for RG 271.79 and RG 271.80 only.
- Edit existing files minimally so the diff shows only the real change.

## 3. Verify every source before it is served

For each instrument:

1. Fetch the primary source: legislation.gov.au for Acts and legislative instruments, otherwise the regulator's
   site. Use the Federal Register "versions" page to record the latest compilation or registration id and its
   start date.
2. Read every provision you paraphrase from the source text, and take paragraph or section numbers from the source.
3. Paraphrase. Do not copy copyright text (industry codes, Standards Australia). Commonwealth law is CC BY 4.0, but
   paraphrase is still the house rule.
4. Set `source_url` to the `/latest/text` URL, so the drift check sees new compilations. A source outside `.gov.au` must be added to `ALLOWED_HOSTS` in `scripts/check_corpus_freshness.py`, or the freshness check will not fetch it. Set `source_version` to the
   compilation you read, `verified_on` to the date you read it, and `text_kind` to `paraphrase`.
5. In `verification_notes`, record what you checked and everything you did not check (drafts, cross-references,
   commencement). Leave a field empty rather than guess (for example `effective_date`). The `staleness` command
   surfaces these notes.
6. If something cannot be verified, leave it out and list it in the pack's `known_gaps`.

## 4. Freshness lock and review pack

- Run `scripts/check_corpus_freshness.py diff` first. If existing sources show as changed, **do not** run `snapshot`,
  because that would mark those changes as accepted without review. Add only the new URLs to
  `src/data/sources.lock.json` (as was done for the superannuation sources), and raise the changed sources for
  review.
- Run `scripts/check_corpus_freshness.py staleness --domain <id>` and resolve or record each item.
- Run `scripts/check_corpus_freshness.py review-pack` to regenerate `docs/CORPUS_REVIEW.md`, then ask a compliance or
  legal SME to sign off.

## 5. Write the red-team pack

Create `src/data/redteam/<id>.json` (worked example: `superannuation.json`):

```json
{
  "id": "utilities", "name": "...", "sectors": ["energy_retail"],
  "reviewer": "Australian energy retail compliance reviewer",
  "categories": [
    {"id": "UPPER_SNAKE_ID", "description": "One sentence the judge applies to an agent reply.", "severity": "HIGH",
     "family": "hardship", "obligations": [{"code": "NERL", "clause": "50", "why": "..."}]}
  ],
  "scenarios": [
    {"id": "TC-...", "category": "UPPER_SNAKE_ID", "applicable_role": "energy_retail_agent",
     "adversarial_prompt": "...", "expected_safe_behavior": "...", "breach_condition": "..."}
  ]
}
```

- Cite only clauses already in the corpus; the test fails on any citation that does not resolve.
- Add a role keyword in `src/rules/audit.py` `_ROLE_SECTORS` only if it cannot match an existing insurance or banking
  role name; otherwise rely on an explicit `sector`.
- Have someone who has not seen the category descriptions write `tests/corpus/<id>/dev.jsonl` and `holdout.jsonl`,
  then measure: `scripts/evaluate_detection.py --corpus <id> --split holdout --judge azure_ai/gpt-5-6-sol`.

## 6. Test

`uv run pytest -q` (also with `GUARDIAN_TOOLSETS=all` and `GUARDIAN_SECTORS=phi`). `tests/test_domains.py`
checks pack shape, sector backing, counts, evidence blocks and the domain filter. Add a test for at least one
clause lookup in the new domain.
