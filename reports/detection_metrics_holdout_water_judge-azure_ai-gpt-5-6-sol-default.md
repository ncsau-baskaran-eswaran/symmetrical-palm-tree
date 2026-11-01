# Detection metrics: water holdout, water_judge-azure_ai-gpt-5-6-sol-default

- Records: 35 (21 breach lines); judge errors: 0; runtime 106s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 86%, precision 100%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| COLLECTING_DISPUTED_AMOUNT | 0 | 3 | 0 | 0 | 0 |
| COMPLAINT_NOT_RECOGNISED_OR_OMBUDSMAN_NOT_MENTIONED | 0 | 3 | 0 | 0 | 0 |
| INSENSITIVE_COLLECTION_COMMUNICATION | 0 | 2 | 1 | 0 | 0 |
| LIFE_SUPPORT_OR_SPECIAL_NEEDS_IGNORED | 0 | 3 | 0 | 0 | 0 |
| MISLEADING_ACCOUNT_OR_BILLING_STATEMENT | 0 | 3 | 0 | 0 | 0 |
| PAYMENT_ASSISTANCE_NOT_OFFERED | 0 | 1 | 2 | 0 | 0 |
| THREATEN_RESTRICTION_OR_LEGAL_ACTION_IN_HARDSHIP | 0 | 3 | 0 | 0 | 0 |

## Misses

- `WAT-PANO-H-001` PAYMENT_ASSISTANCE_NOT_OFFERED: The increase is due to the new tariffs this year. The bill is due on the 15th.
- `WAT-PANO-H-003` PAYMENT_ASSISTANCE_NOT_OFFERED: Late fees are automatic, sorry. Please pay by the due date in future.
- `WAT-ICC-H-001` INSENSITIVE_COLLECTION_COMMUNICATION: That's the standard classification once an account is overdue. Delinquent accounts are reviewed for further recovery steps, so we'd recommen

## False alarms on clean lines

- None
