# Data sources

Everything the prototype uses is public. No member data, client data, or prospect data is involved, and the accounts in the workspace are fictional.

All files are downloaded by [`ingest/download_public_docs.py`](../ingest/download_public_docs.py) into `data/` (git-ignored) and uploaded to Azure Blob Storage, account `pharmcodingf946de69`, container `prototype-docs`. `data/manifest.csv` records each file's source URL, size, SHA-256, and download date.

## What is downloaded

| Data | Source | Used for | Location under `data/` |
| --- | --- | --- | --- |
| Plan Attributes and Benefits and Cost Sharing files, plan year 2026 | CMS Exchange Public Use Files (`download.cms.gov/marketplace-puf/2026`) | SBC links for the pinned plans; published deductibles, out-of-pocket limits and drug tier cost sharing (the answer key) | `raw/cms-puf/2026/`, `golden/2026/` |
| Machine Readable URL file | CMS Exchange Public Use Files | Finding each insurer's machine-readable index | `raw/cms-puf/2026/` |
| 25 Summary of Benefits and Coverage PDFs | Insurer websites, linked from the Plan Attributes file | The documents the AI reads | `raw/sbc/2026/<insurer>/` |
| Machine-readable drug files (`drugs.json`) | Each insurer, as registered with CMS | Drug-level formulary per plan: tier, prior authorization, step therapy, quantity limit, keyed by RxNorm id | `raw/formulary/2026/<insurer>/` |
| Machine-readable plan files (`plans.json`) | Each insurer | Kept for reference (tier cost sharing by channel); not yet used | `raw/formulary/2026/<insurer>/` |
| Medicare Part D Spending by Drug, 2024 | CMS (`data.cms.gov`) | Ranking the most dispensed drugs | `raw/part-d-spending/` |
| RxNorm product ids | National Library of Medicine RxNav API (`rxnav.nlm.nih.gov`) | Matching each common drug to every strength and form on a formulary | `reference/top-drugs.json`, `reference/scenario-drugs.json` |
| NADAC unit prices, 2026 | Medicaid (`data.medicaid.gov`) | Drug prices in the member cost examples | `reference/scenario-drugs.json` |

## The 25 plans

Pinned in [`ingest/plans.csv`](../ingest/plans.csv): small-group exchange plans from four insurer groups, the same set used by the medical benefit coding prototype.

| Insurer | State | Plans | Formularies | Drugs per formulary |
| --- | --- | --- | --- | --- |
| Mountain Health CO-OP | MT | 8 | 3 | 4,258 |
| Security Health Plan | WI | 9 | 4 | 5,802 |
| Blue Cross and Blue Shield of Alabama | AL | 4 | 4 | 4,455 to 5,276 |
| Anthem Blue Cross and Blue Shield | NH | 4 | 4 | 3,484 |

A formulary is identified by the `FormularyId` in the Plan Attributes file. Plans from one insurer often share the same drug list under different ids.

## Derived files

| File | What it holds |
| --- | --- |
| `golden/2026/selected-plans.csv` | One row per pinned plan: insurer, plan name, metal level, formulary id, SBC path, drug file |
| `golden/2026/plan-attributes.csv` | Plan Attributes rows for the pinned plans |
| `golden/2026/benefits-and-cost-sharing.csv` | Drug rows of the Benefits and Cost Sharing file for the pinned plans |
| `reference/top-drugs.json` | 184 of the 200 most dispensed Part D drugs that RxNav could resolve, each with its claims count and RxNorm product ids |
| `reference/scenario-drugs.json` | RxNorm ids and a NADAC unit price for each member cost example in [`scenarios.csv`](../pharmacy_coding/scenarios.csv) |

## Synthetic inputs

These are not public data; they are written for the prototype and live in the repository.

| File | Purpose |
| --- | --- |
| [`accounts.csv`](../pharmacy_coding/accounts.csv) | Eight fictional accounts that group the 25 plans as current, proposed, or sold |
| [`intake.csv`](../pharmacy_coding/intake.csv) | A client intake form for two plans, with one value on each that deliberately disagrees with the plan document |
| [`catalog.csv`](../pharmacy_coding/catalog.csv) | Placeholder catalog of standard copays and coinsurance used by the fit check |

## Limits

- **Exchange plans only.** The implementation plan also calls for Medicare Part D plans. Those need plan documents collected one insurer website at a time and are not in this draft.
- **Drug-level data is published, not extracted.** Tiers and edits come straight from the insurers' machine-readable files. Reading formulary PDFs with AI is not built yet.
- **The answer key is the insurer's filing, not the SBC.** Where the two disagree, the accuracy report counts it as a miss even if the extraction matches the document.
- **Part D claim counts stand in for an account's own utilization.** Real disruption analysis would use the account's claims, which is production work under a BAA.
- **NADAC is an average acquisition cost, not a contracted price.** Member cost examples are illustrative.
- **Links and layouts change yearly.** The Anthem drug file URL and the NADAC dataset id are pinned in the download script and will need updating for a new plan year.
