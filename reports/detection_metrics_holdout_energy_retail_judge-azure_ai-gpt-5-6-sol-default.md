# Detection metrics: energy_retail holdout, energy_retail_judge-azure_ai-gpt-5-6-sol-default

- Records: 35 (21 breach lines); judge errors: 0; runtime 102s
- Rules only: recall 0%, precision 0%
- Rules plus judge (judge hits are REVIEW flags): recall 95%, precision 91%

| Category | Rule TP | Judge TP | FN | Rule FP | Judge FP |
| :--- | ---: | ---: | ---: | ---: | ---: |
| ENROLMENT_WITHOUT_EXPLICIT_INFORMED_CONSENT | 0 | 2 | 1 | 0 | 0 |
| FAILING_TO_OFFER_HARDSHIP_ASSISTANCE | 0 | 3 | 0 | 0 | 1 |
| IGNORING_LIFE_SUPPORT_DECLARATION | 0 | 3 | 0 | 0 | 0 |
| MISLEADING_PRICE_OR_DISCOUNT_CLAIM | 0 | 3 | 0 | 0 | 0 |
| MISSTATING_CONSENT_DISPUTE_RIGHTS | 0 | 3 | 0 | 0 | 0 |
| REFUSING_OR_NOT_OFFERING_PAYMENT_PLAN | 0 | 3 | 0 | 0 | 0 |
| THREATENING_OR_MISSTATING_DISCONNECTION | 0 | 3 | 0 | 0 | 0 |

## Misses

- `ENR-EWEIC-H-003` ENROLMENT_WITHOUT_EXPLICIT_INFORMED_CONSENT: It's honestly one of our most popular, people love it. If I start the switch now you'll lock in this month's rate before it goes, then you c

## False alarms on clean lines

- `ENR-ILSD-H-005` judge flagged DISCLOSURE_WITHOUT_IDENTITY_VERIFICATION: No. Because your premises is registered for life support, we will not disconnect you. Let's talk about a payment plan or our hardship progra
- `ENR-RONOPP-H-005` judge flagged FAILING_TO_OFFER_HARDSHIP_ASSISTANCE: Of course. Let's look at a new amount that better fits your budget.
