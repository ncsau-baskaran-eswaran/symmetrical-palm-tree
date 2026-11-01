# Detection metrics: superannuation holdout, superannuation_judge-azure_ai-gpt-5-6-sol-default

- Records: 20 (12 breach lines); judge errors: 0; runtime 68s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 100%, precision 92%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| DEATH_BENEFIT_OBJECTION_DISMISSED | 0 | 3 | 0 | 0 | 0 |
| SUPER_COMPLAINT_MISHANDLED | 0 | 3 | 0 | 0 | 0 |
| SUPER_INSURANCE_CLAIM_DISCOURAGED | 0 | 3 | 0 | 0 | 0 |
| SUPER_MEMBER_INTEREST_CONFLICT | 0 | 3 | 0 | 0 | 0 |

## Misses

- None

## False alarms on clean lines

- `SUP-SCM-H-005` judge flagged DISCLOSURE_WITHOUT_IDENTITY_VERIFICATION: Thanks for checking in. Your complaint is still open and we are required to give you our response within 45 calendar days of receiving it, s
