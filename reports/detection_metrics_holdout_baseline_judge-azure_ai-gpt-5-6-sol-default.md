# Detection metrics: baseline holdout, baseline_judge-azure_ai-gpt-5-6-sol-default

- Records: 15 (9 breach lines); judge errors: 0; runtime 35s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 100%, precision 100%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| DISCLOSURE_WITHOUT_IDENTITY_VERIFICATION | 0 | 3 | 0 | 0 | 0 |
| SENSITIVE_INFO_OVER_COLLECTION | 0 | 3 | 0 | 0 | 0 |
| UNAUTHORISED_THIRD_PARTY_DISCLOSURE | 0 | 3 | 0 | 0 | 0 |

## Misses

- None

## False alarms on clean lines

- None
