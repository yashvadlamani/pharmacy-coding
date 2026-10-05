# Pipeline

How the first draft of the prototype works, which Azure and public services each step uses, how to run it, and what it produced on the 25 pinned plans.

This is a rough first draft. What it does not do yet is listed under [Not built yet](#not-built-yet).

## Contents

- [What runs](#what-runs)
- [Services used](#services-used)
- [Running it](#running-it)
- [Step by step](#step-by-step)
- [Results on the 25 plans](#results-on-the-25-plans)
- [Not built yet](#not-built-yet)

## What runs

| Step | Module | What it does |
| --- | --- | --- |
| Data collection | [`ingest/download_public_docs.py`](../ingest/download_public_docs.py) | Downloads the public files and uploads them to Blob Storage |
| Drug-level layer | [`formulary.py`](../pharmacy_coding/formulary.py) | Builds one compact formulary per plan formulary from the insurers' machine-readable drug files |
| 1. Ingest | [`ingest.py`](../pharmacy_coding/ingest.py), [`ocr.py`](../pharmacy_coding/ocr.py) | Reads each SBC, classifies it, splits it into sections |
| 2. Extract | [`extract.py`](../pharmacy_coding/extract.py) | Extracts 19 plan-level pharmacy fields, each with a quote, page, and confidence; checks every quote against the document |
| 3. Map and fit check | [`fit.py`](../pharmacy_coding/fit.py) | Assigns a placeholder platform code and a fit rating to each field and to the plan's accumulators and formulary structure |
| 4. Validate | [`validate.py`](../pharmacy_coding/validate.py) | Consistency and reconciliation checks, intake-form conflicts, client questions, member cost examples |
| 5. Review and confirm | [`app.py`](../app.py) | The sales workspace: accounts, plan summaries with sources, drug lookup, plan comparison |
| 6. Handoff | [`app.py`](../app.py) | Coding package per plan, with coder approve or return |
| Scoring | [`evaluate.py`](../pharmacy_coding/evaluate.py) | Accuracy report against the published values |

## Services used

The pipeline is orchestrated by a local Python process. Document reading, extraction, storage, and hosting run on Azure resources in resource group `pharmacy-coding-rg`. Source data is downloaded from public websites. No member, client, or prospect data is sent anywhere.

| Step | Service | Type | Resource / detail | Used for |
| --- | --- | --- | --- | --- |
| Data collection | CMS, insurer websites, NLM RxNav, Medicaid NADAC | External, public | See [data sources](data-sources.md) | Plan documents, answer key, formularies, drug identities, prices |
| Data collection | Azure Blob Storage | Azure | Account `pharmcodingf946de69`, container `prototype-docs`, Standard LRS, Central US, public access off | Stores the downloaded files and manifest |
| 1. Ingest | Azure Document Intelligence | Azure | Resource `pharmcoding-ai` (Azure AI Services, S0, East US 2), `prebuilt-read` model, API `2024-11-30` | Reads the text of every document, digital or scanned |
| 2. Extract | Azure OpenAI | Azure | Resource `pharmcoding-ai`, deployment `extract`, model `gpt-5-mini` version `2025-08-07`, Global Standard, API `2024-10-21` | Structured extraction of the 19 fields with quotes and confidence |
| 3 and 4 | None | Local code | | Fit rules, checks, question generation, and the member cost calculator are rule-based |
| All steps | Azure Blob Storage | Azure | Container `prototype-docs`, `output/` prefix | Pipeline outputs: `ingested/`, `extracted/`, `coded/`, `validated/`, `formulary/`, `reference/`, `index.json` |
| 5 and 6 | Azure App Service | Azure | Web app `pharmcoding-workspace-f946de69` (Linux, Python 3.12, gunicorn) on plan `medbencoding-plan` (B1, Central US) | Hosts the sales workspace |
| 5 and 6 | Azure Table Storage | Azure | Account `pharmcodingf946de69`, tables `answers`, `signoffs`, `audittrail` | Client answers, client and coder sign-offs, audit trail |

Notes:

- **Shared App Service plan.** The web app runs on the App Service plan that already hosts the medical benefit coding review app, in resource group `medical-benefit-coding-rg`, so it adds no fixed monthly charge. Stopping or scaling that plan affects both apps. Everything else is in `pharmacy-coding-rg`.
- **Cost.** Storage and both AI services are pay-per-use with no idle charge. A full 25-plan run read 202 pages through Document Intelligence and used about 100k input and 147k output tokens.
- **Authentication.** The pipeline uses the AI resource key and the storage connection string from the git-ignored `.env`. The web app has only the storage connection string.
- **Access to the workspace.** The whole site is behind one shared password. Only its hash is stored, in the web app setting `WORKSPACE_PASSWORD_HASH`. The name shown against answers and sign-offs is whatever the signed-in visitor types.
- **What leaves the machine.** Step 1 sends each SBC PDF to Document Intelligence; step 2 sends SBC text to Azure OpenAI; outputs, answers, and sign-offs are stored in the storage account. All of it is public plan data or fictional.

## Running it

Requires Python 3.12, `curl`, and the Azure CLI signed in to the subscription. Copy `.env.example` to `.env` and fill it in.

```bash
pip install -r requirements.txt
```

```bash
python ingest/download_public_docs.py --upload
```

```bash
python -m pharmacy_coding formularies
```

```bash
python -m pharmacy_coding run
```

```bash
python -m pharmacy_coding evaluate
```

```bash
python -m pytest
```

To run the workspace locally (it reads the same Blob and Table Storage):

```bash
python -m flask run
```

To deploy it to App Service (add `--configure` on first deployment or after changing a secret):

```bash
python deploy.py
```

`python -m pharmacy_coding run --skip-existing` reuses saved extractions and redoes only the fit check and validation, which costs nothing.

## Step by step

### Drug-level layer

Each insurer publishes a machine-readable drug file listing every formulary drug by RxNorm id with its tier and its prior authorization, step therapy, and quantity limit flags, per plan. `formularies` reduces these to one compact file per formulary id.

Tier labels differ by insurer (`TIER-ONE`, `PREFERRED-GENERIC`, and so on), so each label is mapped to a drug class: $0 preventive, generic, preferred brand, non-preferred brand, or specialty. Numbered tiers follow the usual layouts; named tiers are matched on keywords. Comparisons between formularies use the class, not the tier number.

A drug such as "atorvastatin" is matched on the RxNorm ids of all its strengths and forms, and is represented by its lowest-tier entry.

The build also checks whether the labels are believable. A $0 preventive tier where more than a quarter of the drugs need prior authorization is flagged, and the warning is shown wherever that formulary is used.

### 1. Ingest

Document Intelligence reads every page. The document is classified by marker phrases and, for an SBC, split at the template's headings so that only the relevant sections go to the model.

### 2. Extract

One call per plan returns all 19 fields as strict JSON: deductibles, out-of-pocket limits, retail and mail order cost share by drug class, the specialty per-fill maximum, days supply, and three yes/no rules. Each field carries a status, a verbatim quote, a page number, a confidence, and a note.

Every quote is then checked word by word against the page text. A quote that is not in the document caps the field's confidence at 0.3. Fields below 0.8 are marked for confirmation.

### 3. Map and fit check

Each field gets a placeholder code built from the field and its value (for example `RX-GEN-R30-CP0010` for a $10 generic retail copay) and one of five ratings:

| Rating | Placeholder rule |
| --- | --- |
| Standard | Value is in the standard catalog, or mail order copay is 2, 2.5 or 3 times retail |
| Configurable | A non-standard amount, a separate pharmacy deductible, a specialty per-fill maximum, or drugs counting toward the medical deductible |
| Custom | A copay and coinsurance on the same fill, or a formulary with more than five cost-share tiers |
| Not supported | Coinsurance above 50%, or mail order beyond 90 days |
| Unclear | Not stated in the document, or read with low confidence |

The catalog and rules are placeholders that show the mechanism. They are not any firm's real limits.

### 4. Validate

- **Consistency:** family amounts not below individual, out-of-pocket limit not below the deductible, tier copays in ascending order, ACA out-of-pocket limit (warning).
- **Reconciliation:** every dollar and percent figure must appear in its cited passage.
- **Intake conflicts:** values on the client's intake form are compared with the document. The prototype has a synthetic intake form for two plans, each with one seeded disagreement.
- **Questions for the client:** generated from conflicts (blocking), fields the document does not state, low-confidence fields, custom or unsupported designs, and four standing decisions an SBC never covers.
- **Member cost examples:** eight prescriptions are priced before and after the deductible, using each drug's tier on the plan's formulary and a NADAC unit price. A drug that is not on the formulary returns reject 70; prior authorization and quantity limits are noted with the reject a claim would get.

### 5 and 6. Workspace and handoff

| Page | What it shows |
| --- | --- |
| Accounts | Every account with stage, effective date, open questions, custom items, and status |
| Account | Its plans with role (current, proposed, sold), fit, and links to compare each with the current plan |
| Plan | Plain-language summary with fit rating per line, the source page with the quote highlighted, questions with an answer box, member cost examples, history |
| Drugs | Search the plan's formulary; how it treats the 40 most dispensed drugs |
| Compare | Two plans side by side: plan design differences, drug disruption on commonly dispensed drugs, member cost examples |
| Handoff | The coding package: values, placeholder codes, sources, client answers, test claims; downloadable as JSON |

A plan cannot be marked confirmed while a blocking question is unanswered, and a coder cannot approve a plan the client has not confirmed.

## Results on the 25 plans

Full detail is in the [accuracy report](accuracy-report.md).

| Measure | Result |
| --- | --- |
| Plan-level fields scored against published values | 229 |
| Field accuracy, all plans | 94.9% |
| Field accuracy, simple plans | 99.3% |
| Field accuracy, moderate plans | 88.5% |
| Extracted values with a citation found in the document | 329 of 330 |
| Plans with every scored field correct | 20 of 25 |
| Wrong fields that were flagged for confirmation | 6 of 13 |
| Seeded intake conflicts caught | 2 of 2 |
| Fit ratings across all plans | 319 standard, 26 configurable, 5 custom, 0 not supported, 175 unclear |
| Questions generated | 261: 2 conflicts, 109 not in documents, 49 to confirm, 1 fit, 100 standing |
| Member cost examples priced | 162 of 200; 38 await a mail order cost share the SBC does not state |

Things to know when reading these numbers:

- **The deductible fields were redefined after the first run.** The first version asked for "the deductible that applies to drugs" and scored 40% on those fields, because the published file's "integrated" flag does not mean what an SBC states. Splitting it into the overall deductible and a pharmacy-only deductible gave an unambiguous definition and the figures above.
- **Most remaining misses are the four Anthem plans**, where the SBC and the published filing give different tier values. The extraction matches the document.
- **Only 6 of 13 wrong fields were flagged.** Confidence alone is a weak safety net; an independent check of each value is not built yet.
- **Eight fields are not scored** because nothing is published for them: mail order cost shares, days supply, and the three yes/no rules.
- **Unclear is high** because an SBC rarely states mail order terms or days supply. That is the point of the questions list, but 175 unclear items across 25 plans would be too many to send a client unfiltered.
- **Security Health Plan's drug file looks mislabeled.** Its "$0 preventive" tier holds 976 drugs, 86% needing prior authorization, including specialty biologics. The prototype shows the tiers as published, with a warning. This affects 9 of the 25 plans.
- **No design in the 25 plans is rated not supported**, so that rating is only exercised by the unit tests.

## Not built yet

| Item | In the implementation plan | State |
| --- | --- | --- |
| Medicare Part D plans | 15 of the 25 prototype plans | Not included; all 25 are exchange plans |
| Drug-level extraction from formulary documents | Parse formulary PDFs and score against the published files | Not built; drug data is taken from the published files directly |
| Year-over-year comparison | Renewal view listing only what changed | Not built; comparison works between any two plans |
| Synthetic RFPs, riders, and scanned copies | Prototype week 4 | Only a small synthetic intake form |
| Unseen-document upload in the workspace | Demo step 2 | Not built; documents are processed from the command line |
| Independent check of extracted values (LLM judge) | Validation stage | Not built |
| Regulatory checks beyond the ACA out-of-pocket limit | Validation stage | Not built |
| Review-time measurements and rep or coder verdicts | Approval criteria | Not measured |
| Mail order cost share scoring | Answer key exists in the insurers' plan files | Downloaded, not yet used |
| CRM integration, real catalog and codes, platform load | Production phase | Production phase |
