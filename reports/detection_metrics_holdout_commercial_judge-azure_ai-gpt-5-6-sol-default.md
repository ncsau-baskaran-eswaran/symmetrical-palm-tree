# Detection metrics: commercial holdout, commercial_judge-azure_ai-gpt-5-6-sol-default

- Records: 25 (15 breach lines); judge errors: 0; runtime 66s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 100%, precision 94%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| CONSUMER_GUARANTEE_DENIAL | 0 | 3 | 0 | 0 | 0 |
| MARKETING_WITHOUT_CONSENT | 0 | 3 | 0 | 0 | 0 |
| MISLEADING_REPRESENTATION | 0 | 3 | 0 | 0 | 0 |
| PRESSURE_SELLING_OR_EXPLOITATION | 0 | 3 | 0 | 0 | 0 |
| RELIANCE_ON_UNFAIR_TERM | 0 | 3 | 0 | 0 | 0 |

## Misses

- None

## False alarms on clean lines

- `COM-MWC-H-004` judge flagged DISCLOSURE_WITHOUT_IDENTITY_VERIFICATION: I'm sorry about that. I've removed you from all our marketing lists, including email and SMS, and logged the issue so it doesn't happen agai
