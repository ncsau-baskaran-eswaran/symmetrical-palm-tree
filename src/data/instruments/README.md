# Regulatory instrument corpus

One JSON file per instrument, grouped by regulator family. `src/db.py` seeds every `*.json` file under this
directory into SQLite, and reseeds automatically whenever any corpus file changes (content hash).

## Licensing rule

- Store obligations as **paraphrases** (`text_kind: "paraphrase"`) with a `source_url`. Do not paste statutory or
  code text verbatim. Commonwealth legislation is CC BY 4.0, but industry codes (ICA, FSC, Private Healthcare
  Australia) are copyright works and must never be reproduced.
- Short defined terms or section headings may be quoted.

## Instrument schema

```json
{
  "code": "ICA 1984",
  "title": "Insurance Contracts Act 1984 (Cth)",
  "short_name": "Insurance Contracts Act",
  "regulator": "ASIC",
  "instrument_type": "act | regulation | prudential_standard | prudential_practice_guide | regulatory_guide | industry_code | report | guidance",
  "legislative_instrument": "C2004A02944",
  "effective_date": "1985-01-01",
  "amended_date": "2025-01-01",
  "status": "In Force | Not yet commenced | Superseded | Announced (not law)",
  "sectors": ["general_insurance", "life_insurance", "private_health_insurance"],
  "entity_types": ["General Insurer"],
  "enforceability": "statutory_civil_penalty | statutory | statutory_prudential_standard | contractual_code | guidance | announced",
  "source_url": "https://www.legislation.gov.au/C2004A02944/latest/text",
  "licence": "CC BY 4.0 (paraphrased)",
  "text_kind": "paraphrase | condensed",
  "verified_on": "2026-10-19",
  "verification_notes": "What was checked, and anything a compliance SME must confirm.",
  "coverage_default": "reference_only | governance_checklist | out_of_scope_not_agent_testable",
  "superseded_standards": [],
  "companion_guidance": [],
  "summary": "Plain-English purpose and scope.",
  "clauses": [
    {
      "id": "ICA-S13",
      "clause_number": "13",
      "section_name": "Part II: The duty of the utmost good faith",
      "heading": "The duty of the utmost good faith",
      "text": "Paraphrased operative obligation.",
      "subclauses": ["Paraphrased sub-obligations"],
      "is_mandatory": true,
      "notification_trigger": null,
      "key_topics": ["claims handling", "utmost good faith"],
      "notes": "Practical meaning for an AI insurance agent; penalties; commencement.",
      "obligation_type": "conduct | disclosure | claims | complaints | privacy | security | reporting | governance | product | pricing | discrimination",
      "agent_relevance": "runtime | code | governance | none",
      "sectors": ["general_insurance", "life_insurance"]
    }
  ]
}
```

`clause_number` is the citation users type into `lookup_clause` (for example `13`, `20B`, `RG 271.38`, `APP 6`,
`Ch 7`). Keep it short and stable: detection rules reference instruments by `(code, clause_number)` and a test
fails if a reference does not resolve.
