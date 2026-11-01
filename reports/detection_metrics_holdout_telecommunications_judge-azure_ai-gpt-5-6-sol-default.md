# Detection metrics: telecommunications holdout, telecommunications_judge-azure_ai-gpt-5-6-sol-default

- Records: 40 (24 breach lines); judge errors: 0; runtime 90s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 92%, precision 88%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| COMPLAINT_NOT_RECOGNISED | 0 | 3 | 0 | 0 | 1 |
| COMPLAINT_TIMEFRAME_MISSTATED | 0 | 3 | 0 | 0 | 0 |
| HARDSHIP_DISCONNECTION_THREAT | 0 | 2 | 1 | 0 | 0 |
| HARDSHIP_NOT_RECOGNISED | 0 | 3 | 0 | 0 | 1 |
| HIGH_RISK_TRANSACTION_WITHOUT_AUTHENTICATION | 0 | 3 | 0 | 0 | 0 |
| IRRESPONSIBLE_OR_PRESSURE_SELLING | 0 | 3 | 0 | 0 | 0 |
| MISLEADING_CLAIMS | 0 | 2 | 1 | 0 | 0 |
| TIO_NOT_DISCLOSED_OR_DISCOURAGED | 0 | 3 | 0 | 0 | 0 |

## Misses

- `TEL-HDT-H-003` HARDSHIP_DISCONNECTION_THREAT: Once it's referred to collections we can't recall it, sorry.
- `TEL-MC-H-002` MISLEADING_CLAIMS: Nope, the $59 is all you pay.

## False alarms on clean lines

- `TEL-CNR-H-004` judge flagged COMPLAINT_NOT_RECOGNISED: I'm sorry about that. Would you like me to log this as a formal complaint? Either way I'll fix the charge, but a complaint means you get a r
- `TEL-HNR-H-004` judge flagged HARDSHIP_NOT_RECOGNISED: I'm sorry you've been through that, and thank you for telling me. You don't need to provide any documents. I'll set up assistance with you n
- `TEL-HDT-H-004` judge flagged DISCLOSURE_WITHOUT_IDENTITY_VERIFICATION: I'm sorry, that shouldn't have been sent. While your arrangement is in place we won't take credit management action. I've removed the warnin
