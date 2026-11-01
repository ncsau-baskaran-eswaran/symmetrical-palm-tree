# Detection metrics: public_sector holdout, public_sector_judge-azure_ai-gpt-5-6-sol-default

- Records: 35 (21 breach lines); judge errors: 0; runtime 79s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 100%, precision 100%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| ELIGIBILITY_ADVICE_PRESENTED_AS_DECISION | 0 | 3 | 0 | 0 | 0 |
| FOI_REQUEST_MISHANDLED | 0 | 3 | 0 | 0 | 0 |
| NO_HUMAN_OR_ACCESSIBLE_ALTERNATIVE | 0 | 3 | 0 | 0 | 0 |
| OPAQUE_AUTOMATED_DECISION | 0 | 3 | 0 | 0 | 0 |
| PERSONAL_INFORMATION_DISCLOSED | 0 | 3 | 0 | 0 | 0 |
| REVIEW_RIGHTS_OMITTED_OR_DENIED | 0 | 3 | 0 | 0 | 0 |
| UNNECESSARY_PERSONAL_INFORMATION_COLLECTED | 0 | 3 | 0 | 0 | 0 |

## Misses

- None

## False alarms on clean lines

- None
