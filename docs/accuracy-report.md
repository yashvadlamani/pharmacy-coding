# Extraction accuracy report

Scored 254 plan-level fields across 25 plans against the values published in the CMS Exchange Public Use Files (plan year 2026). Fields with no published value are not scored: `generic_mail`, `preferred_brand_mail`, `nonpreferred_brand_mail`, `retail_days_supply`, `mail_days_supply`, `mail_order_available`, `specialty_pharmacy_required`, `prior_auth_drugs`.

Drug-level data (tier, prior authorization, step therapy, quantity limit) is taken directly from the insurers' machine-readable formulary files in this draft, so it is not an extraction result and is not scored here.

## Summary

| Measure | Result |
| --- | --- |
| Field accuracy, all plans | 94.9% |
| Field accuracy, simple plans | 99.3% |
| Field accuracy, moderate plans | 88.5% |
| Extracted values with a citation found in the document | 329 of 330 |
| Plans with every scored field correct | 20 of 25 |
| Wrong fields that were flagged for confirmation | 6 of 13 |

## Accuracy by field

| Field | Correct | Accuracy |
| --- | --- | --- |
| overall_deductible_individual | 25 of 25 | 100.0% |
| overall_deductible_family | 25 of 25 | 100.0% |
| rx_deductible_individual | 24 of 25 | 96.0% |
| rx_deductible_family | 24 of 25 | 96.0% |
| oop_max_individual | 25 of 25 | 100.0% |
| oop_max_family | 25 of 25 | 100.0% |
| generic_retail | 24 of 25 | 96.0% |
| preferred_brand_retail | 23 of 25 | 92.0% |
| nonpreferred_brand_retail | 22 of 25 | 88.0% |
| specialty_retail | 20 of 25 | 80.0% |
| specialty_max_per_fill | 4 of 4 | 100.0% |

## Accuracy by plan

| Plan | Complexity | Correct | Accuracy |
| --- | --- | --- | --- |
| 32225MT0070004 | moderate | 10 of 10 | 100.0% |
| 32225MT0070006 | moderate | 10 of 10 | 100.0% |
| 32225MT0140001 | simple | 9 of 10 | 90.0% |
| 32225MT0140002 | simple | 10 of 10 | 100.0% |
| 32225MT0140003 | simple | 10 of 10 | 100.0% |
| 32225MT0160001 | simple | 10 of 10 | 100.0% |
| 32225MT0160002 | simple | 10 of 10 | 100.0% |
| 32225MT0160006 | simple | 10 of 10 | 100.0% |
| 38166WI0140001 | simple | 10 of 10 | 100.0% |
| 38166WI0140004 | simple | 10 of 10 | 100.0% |
| 38166WI0140011 | simple | 10 of 10 | 100.0% |
| 38166WI0140033 | moderate | 10 of 10 | 100.0% |
| 38166WI0140037 | moderate | 10 of 10 | 100.0% |
| 38166WI0140040 | simple | 10 of 10 | 100.0% |
| 38166WI0140044 | simple | 10 of 10 | 100.0% |
| 38166WI0150001 | simple | 10 of 10 | 100.0% |
| 38166WI0150044 | simple | 10 of 10 | 100.0% |
| 46944AL0280001 | simple | 10 of 10 | 100.0% |
| 46944AL0340001 | moderate | 10 of 10 | 100.0% |
| 46944AL0380001 | moderate | 10 of 10 | 100.0% |
| 46944AL0430001 | simple | 10 of 10 | 100.0% |
| 57601NH0350005 | moderate | 6 of 11 | 54.5% |
| 57601NH0350016 | moderate | 10 of 11 | 90.9% |
| 96751NH0160016 | moderate | 7 of 11 | 63.6% |
| 96751NH0160037 | moderate | 9 of 11 | 81.8% |

## Mismatches

| Plan | Field | Published value | Extracted | Confidence | Cited passage |
| --- | --- | --- | --- | --- | --- |
| 32225MT0140001 | specialty_retail | $250 copay | $250 copay + 50% | 1.00 | Specialty drugs $250 copayment/prescription, deductible does not apply, 50% coinsurance |
| 57601NH0350005 | rx_deductible_individual | $0 | $250 | 1.00 | Are there other deductibles for specific services? Yes. $250/person or $500/family for Pre |
| 57601NH0350005 | rx_deductible_family | $0 | $500 | 1.00 | Are there other deductibles for specific services? Yes. $250/person or $500/family for Pre |
| 57601NH0350005 | preferred_brand_retail | $60 copay | $70 copay | 0.70 | Typically Preferred Brand & Non-Preferred Generic Drugs (Tier 2) $70/prescription, Prescri |
| 57601NH0350005 | nonpreferred_brand_retail | 30% | $60 copay | 0.70 | Typically Non-Preferred Brand and Generic drugs (Tier 3) $60/prescription, Prescription Dr |
| 57601NH0350005 | specialty_retail | 40% | 50% | 0.70 | Typically Preferred Specialty (brand and generic) (Tier 4) 50% coinsurance up to $650/pres |
| 57601NH0350016 | specialty_retail | 40% | 50% | 0.80 | Typically Preferred Specialty (brand and generic) (Tier 4) 50% coinsurance up to $650/pres |
| 96751NH0160016 | generic_retail | $20 copay | $12 copay | 0.70 | Typically Lower Cost Generic (Tier 1a) ... $12/prescription, deductible does not apply (re |
| 96751NH0160016 | preferred_brand_retail | $60 copay | $70 copay | 0.95 | Typically Preferred Brand & Non-Preferred Generic Drugs (Tier 2) ... $70/prescription, ded |
| 96751NH0160016 | nonpreferred_brand_retail | 30% | 40% | 0.95 | Typically Non-Preferred Brand and Generic drugs (Tier 3) ... 40% coinsurance up to $500/pr |
| 96751NH0160016 | specialty_retail | 40% | 50% | 0.95 | Typically Preferred Specialty (brand and generic) (Tier 4) ... 50% coinsurance up to $650/ |
| 96751NH0160037 | nonpreferred_brand_retail | 30% | $90 copay | 0.70 | Typically Non-Preferred Brand and Generic drugs (Tier 3) ... $90/prescription (retail only |
| 96751NH0160037 | specialty_retail | 40% | 50% | 0.70 | Typically Preferred Specialty (brand and generic) (Tier 4) ... 50% coinsurance up to $650/ |
