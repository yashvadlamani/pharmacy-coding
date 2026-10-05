# Implementation Plan: Prototype to Production

AI-assisted pharmacy benefit coding for PBM and health-plan benefit operations: an AI pipeline reads plan documents and formularies, extracts cost-sharing rules and drug-level attributes with source citations, maps them to adjudication-platform codes, validates them with test claims, and hands a coder a ready-to-approve plan.

**AI drafts and humans decide.** Nothing loads to the adjudication platform without passing automated checks and a coder's approval.

| Phase | Duration | Outcome |
| --- | --- | --- |
| Phase 1: Prototype | 4 weeks | Live demo and scorecard; go/no-go decision |
| Phase 2: Production build | 8 weeks after approval | Go-live on the first line of business |
| Total | About 3 months | Kickoff to production launch |

The six-stage pipeline is described in [architecture.md](architecture.md). The manual process it assists is described in [pharmacy-coding-process.md](pharmacy-coding-process.md).

## Contents

- [Business case](#business-case)
- [Delivery plan](#delivery-plan)
- [Phase 1: Prototype (weeks 1 to 4)](#phase-1-prototype-weeks-1-to-4)
- [Phase 2: Production build (8 weeks)](#phase-2-production-build-8-weeks)
- [Compliance and security](#compliance-and-security)
- [Testing and quality assurance](#testing-and-quality-assurance)
- [Success metrics](#success-metrics)
- [Risks and mitigations](#risks-and-mitigations)
- [Rollout and adoption](#rollout-and-adoption)
- [Approvals and support needed](#approvals-and-support-needed)
- [Open decisions](#open-decisions)
- [Glossary](#glossary)

## Business case

Pharmacy claims adjudicate in seconds at the counter, so a coding error reaches members on the first day of the plan year. Manual coding is slow, concentrated in the fourth quarter, and dependent on a small number of experienced coders.

| Pain point | Impact today | What the product changes |
| --- | --- | --- |
| Manual re-keying of intake forms and plan documents | Weeks per group, compressed renewal season | AI drafts every field; coder reviews |
| Conflicting source documents | Rework and late client questions | Conflicts listed automatically at intake |
| Fourth-quarter backlog | Overtime, contractors, rushed testing | Same coders handle more groups |
| Coding errors | Wrong copays and rejects at the counter, claim reprocessing, performance-guarantee penalties | Automated reconciliation and test claims before load |
| Hand-written test claims | Thin test coverage under time pressure | Test scenarios and expected results generated from the extracted benefit |
| Sales promises not reflected in the system | Post-sale disputes | Mismatches flagged before go-live |

### Value model

To be filled in with baseline numbers gathered in week 1 of the prototype:

- **Hours saved** = groups per year × hours per group today × share of work automated
- **Error savings** = coding-related claim reprocessing events per year × cost per event × reduction
- **Penalty avoidance** = performance-guarantee amounts at risk for coding accuracy and timeliness
- **Capacity** = additional groups implemented in the renewal season without added staff

The build is lean, so the main costs are LLM usage, hosting, a drug-compendium license in production, and coder review time for validation.

## Delivery plan

| Phase | When | Focus |
| --- | --- | --- |
| Prototype, week 1 | Weeks 1 to 4 | Data and setup |
| Prototype, week 2 | | Plan-level and drug-level extraction |
| Prototype, week 3 | | Mapping, test-claim simulator, review screen |
| Prototype, week 4 | | Tune and live demo |
| **Approval gate** | End of week 4 | Demo meets criteria |
| Sprint 1 | Build weeks 1-2 | Secure environment, CI/CD, client code library, drug compendium |
| Sprint 2 | Build weeks 3-4 | Platform integration, full benefit set, real test claims |
| Sprint 3 | Build weeks 5-6 | Review queue, audit trail, learning loop, intake form |
| Sprint 4 | Build weeks 7-8 | Regression, sign-off, UAT, parallel run, go-live |
| **Go-live** | | First line of business, then hypercare |

The approval gate is the only decision point. If the demo misses its criteria, the scorecard shows which fields need work before the build is reconsidered.

## Phase 1: Prototype (weeks 1 to 4)

The prototype shows AI turning 25 real, publicly available pharmacy plans into proposed benefit codes, with citations, a review screen, and simulated test claims. It ends in a go/no-go demo.

No client documents or platform codes are available yet, so every prototype step runs on public sources. Client data replaces them in Phase 2 without changing the pipeline.

### Scope

- **25 plans** with public documents and published values to score against:
  - 15 Medicare Part D plans (stand-alone and Medicare Advantage), which publish plan documents, formularies, and a detailed CMS data file
  - 10 exchange plans, which publish an SBC and a machine-readable formulary
- **About 30 plan-level fields per plan:** pharmacy deductible and whether it is integrated with medical, tiers the deductible applies to, OOP maximum, number of tiers, cost share per tier for retail 30-day, retail 90-day, mail, and specialty, coinsurance minimums and maximums, days supply limits by channel, mail-order availability, specialty pharmacy rule
- **Drug-level attributes** for a fixed sample of 200 commonly used drugs per formulary: tier, prior authorization, step therapy, quantity limit
- Public plan documents only: no member PHI and no client data, so no BAA is needed until client documents are introduced
- **Out of scope:** live platform integration, client code libraries, network pricing contracts, accumulator feeds with a medical carrier, Medicaid, compounds, coordination of benefits

### Public data sources

| Pipeline step | What the prototype needs | Public source |
| --- | --- | --- |
| 1. Ingest | Plan documents | Part D Summary of Benefits and Evidence of Coverage documents on plan websites; exchange SBC PDFs linked from the CMS Exchange Public Use Files |
| 1. Ingest | Formulary documents | Formulary PDFs published by each Part D plan and exchange issuer |
| 1. Ingest | Intake forms and riders | Not published: synthetic intake forms and riders written against a real plan, including seeded conflicts |
| 1. Ingest | Scanned documents | Real documents degraded into scan-like images |
| 2. Extract | Verified plan-level values | CMS Part D formulary and pharmacy network files (beneficiary cost by tier, days supply, and pharmacy type); CMS Exchange Benefits and Cost Sharing Public Use File |
| 2. Extract | Verified drug-level values | CMS Part D formulary file (tier, PA, ST, QL per drug by RxCUI); exchange issuers' machine-readable formulary files |
| 3. Map | Drug identity | RxNorm from the National Library of Medicine; FDA NDC Directory |
| 3. Map | Target code system | A placeholder code table modeled on common platform parameters; each client replaces it with its own |
| 4. Validate | Reconciliation | Coded values compared with the source documents; mismatches seeded by altering one value in a copy |
| 4. Validate | Drug prices for test claims | NADAC from Medicaid.gov, as a stand-in for contracted network pricing |
| 4. Validate | Regulatory checks | CMS-published Part D benefit parameters for the plan year; ACA preventive drug categories |
| 5. Review | Reviewers and baseline time | Not public: internal reviewers time themselves coding a plan by hand, then with the tool |

Limits of public data, to state openly in the pitch:

- Published values are filed plan designs, not a client's platform codes. The code table is a stand-in each client replaces.
- Commercial self-funded plans, the most customized segment, publish nothing. Their variety is represented only by synthetic intake forms.
- Medi-Span and First Databank identifiers are licensed, so the prototype uses RxNorm and NDC. Production needs the client's compendium.
- NADAC approximates acquisition cost, not a contracted rate. Deductible-phase and coinsurance test results are illustrative.
- Review-time and "would use it daily" results come from internal reviewers until client coders take part.
- File layouts, plan-year parameters, and document links change yearly and must be confirmed in week 1.

### Prototype stack

- Enterprise LLM with structured JSON output for extraction
- Python service for parsing, OCR, extraction, drug normalization, and code mapping
- Code library as a lookup table (field, value, platform code) filled with placeholder codes
- Lightweight web review screen: source document beside proposed fields and codes
- Rules-based test-claim simulator standing in for the adjudication platform, returning member cost or an NCPDP reject code

Where practical, components are reused from the medical benefit coding prototype.

### Weekly plan

| Week | Focus | Deliverable |
| --- | --- | --- |
| 1 | Data and setup | CMS files downloaded and layouts confirmed; 25 plans selected and their documents collected; golden dataset built from published values; 200-drug sample fixed; field list and placeholder code table agreed; manual baseline review time measured |
| 2 | Extraction | Plan-level fields extracted with citations and confidence; formulary tables parsed and drugs normalized to RxNorm; first accuracy report against published values |
| 3 | Mapping, checks, review screen | Fields mapped to placeholder codes; cross-document reconciliation working; test-claim simulator running 12 scenarios per plan; review screen usable |
| 4 | Tune and demo | Misses fixed; synthetic intake-form, rider, and scanned-copy cases added; final scorecard; reviewers time their reviews; live demo |

### Test-claim scenarios in the prototype

| # | Scenario | Expected result |
| --- | --- | --- |
| 1 | Generic, retail 30-day | Tier 1 cost share |
| 2 | Preferred brand, retail 30-day | Preferred brand cost share |
| 3 | Non-preferred brand, retail 30-day | Non-preferred cost share within min and max |
| 4 | Maintenance drug, mail 90-day | Mail cost share |
| 5 | Specialty drug | Specialty cost share with 30-day limit |
| 6 | Claim in the deductible phase | Member pays the drug price up to the deductible |
| 7 | Claim after OOP maximum is met | $0 |
| 8 | PA-required drug, no authorization | Reject 75 |
| 9 | Quantity above the limit | Reject 76 |
| 10 | Early refill | Reject 79 |
| 11 | Drug not on the formulary | Reject 70 |
| 12 | Days supply above the channel limit | Reject 76 |

### Demo script (20 minutes)

1. Upload plan documents and a formulary the system has never seen, from a plan outside the 25-plan set.
2. Plan-level fields populate, each with a confidence score and its highlighted source sentence.
3. Look up three drugs; tier and PA, ST, and QL flags appear with the formulary line they came from.
4. A seeded conflict between the intake form and the SBC is flagged, and low-confidence fields are highlighted.
5. A coder edits one field and approves; the audit trail records the change.
6. Test claims run: four pay with the expected member cost, and three reject with the expected codes.
7. Close on the scorecard: accuracy by field, review time versus today, plans needing no edits.

### Approval criteria for Phase 2

| Measure | Target |
| --- | --- |
| Plan-level field accuracy, Part D plans | 90%+ |
| Plan-level field accuracy, exchange plans | 85%+ |
| Drug-level tier accuracy on the 200-drug sample | 95%+ |
| Drug-level PA, ST, and QL flag accuracy | 90%+ |
| Fields with a valid source citation | 100% |
| Review time per standard plan | Under 20 minutes |
| Seeded mismatches and conflicts caught | All |
| Test claims matching expected result | 95%+ |
| Coder verdict | Majority would use it daily |

Accuracy is scored against the published CMS and issuer values. Review time and coder verdict come from internal reviewers during the prototype and are re-measured with client coders once a client takes part.

## Phase 2: Production build (8 weeks)

Phase 2 turns the prototype into a secure, integrated product in four 2-week sprints, ending with go-live on the first line of business.

| Sprint | Weeks | Focus | Done when |
| --- | --- | --- | --- |
| 1 | 1-2 | Production foundations | Secure environment with SSO, encryption, logging, and CI/CD; prototype refactored into services; client code library and list IDs loaded; drug compendium connected and mapped to RxNorm |
| 2 | 3-4 | Platform integration and full benefit set | Configuration loads to the platform test region by API or load file; test claims submitted to the test region and compared with expected results; accumulators, brand penalties, preventive lists, and channel rules covered; regulatory checks live for the launch line of business |
| 3 | 5-6 | Reviewer workflow and learning loop | Work queue, approvals, peer-QA step, audit trail, and reporting dashboard; reviewer corrections captured to improve accuracy; standard digital intake form; renewal comparison against the prior-year configuration |
| 4 | 7-8 | Hardening and launch | Regression suite on a 200-plan golden set; security and compliance sign-off; coder UAT and two-week parallel run; go-live and hypercare with first-claims monitoring |

### Sprint detail

**Sprint 1: Production foundations**

- Stand up development, test, and production environments in the approved cloud
- SSO, role-based access, encryption at rest and in transit, access logging
- Execute the BAA with the LLM provider; confirm no data is retained for training
- Load the client's code library, formulary and drug-list IDs, and clinical program catalog
- Connect the licensed drug compendium and build the crosswalk from RxNorm to its identifiers
- Begin the client golden set: 50 already-coded plans with verified configuration

**Sprint 2: Platform integration and full benefit set**

- Confirm the load method (API or load file) and build it against the test region
- Submit generated test claims to the test region and capture results
- Extend extraction to accumulator rules, medical integration, brand penalties, mandatory mail and specialty, preventive and HDHP lists, exclusions, and client-specific drug overrides
- Regulatory checks for the launch line of business
- Grow the golden set to 120 plans

**Sprint 3: Reviewer workflow and learning loop**

- Work queue with assignment, status, and due dates tied to effective dates
- Separate coder and peer-QA approvals, matching the existing control
- Audit trail holding source, AI output, reviewer decision, and final code together
- Corrections feed the golden set, prompts, and mapping rules
- Renewal mode: compare new documents with the prior-year configuration and list only what changed
- Standard intake form that removes free-text ambiguity at the source
- Grow the golden set to 200 plans

**Sprint 4: Hardening and launch**

- Regression suite must pass on the 200-plan golden set before any release
- Security, compliance, and model-governance sign-off
- Coder training and UAT
- Two-week parallel run: new groups coded both ways and compared
- Go-live on the first line of business
- Hypercare: first live claims for each launched group compared with expected results

### Production-ready checklist

- [ ] Runs in the firm's approved cloud with SSO and role-based access
- [ ] BAA in place with the LLM provider; no data retained for model training
- [ ] Model and prompt versions pinned; changes go through regression tests
- [ ] Every coded field stores source passage, confidence, reviewer, and timestamp
- [ ] Reconciliation and test claims block bad loads
- [ ] Coder and peer-QA approvals recorded separately
- [ ] Drug compendium updates handled without manual rework
- [ ] Monitoring and alerts for errors, latency, and accuracy drift
- [ ] Runbook, fallback to manual coding, and support process documented
- [ ] Coders trained; two-week parallel run passed before cutover

> **Timing note:** Pharmacy coding peaks from October through December for January 1 effective dates. A kickoff in early October puts the approval gate in early November and go-live in early January, directly on the peak. Options are to launch on off-cycle groups (April 1 or July 1 effective dates) or to hold cutover until February. No plan should be cut over during its own renewal.

## Compliance and security

The prototype avoids member PHI entirely. The production build adds the controls needed to pass HIPAA and model-risk review before go-live.

| Requirement | Prototype | Production |
| --- | --- | --- |
| HIPAA | Public plan documents only, no PHI or client data | Encryption, access logging, minimum necessary access; BAA before any client document is used |
| ACA preventive drugs | $0 preventive tier checked where published | Missing preventive list blocks the load |
| ACA cost-sharing limits | OOP maximum checked against the annual limit | Same, with pharmacy and medical combined |
| HDHP rules | Not in scope | Deductible applies before cost share except for preventive drugs |
| Medicare Part D | Extracted values checked against the year's CMS benefit parameters | Checks aligned with the client's CMS-approved bid and formulary |
| Mental health parity (MHPAEA) | Not in scope | Cost-sharing and utilization-management comparison for the launch line of business |
| State law | Not in scope | Rules for situs states of the first line of business, such as insulin cost caps and copay accumulator restrictions |
| NCPDP standards | Reject codes used in the simulator | Test claims in the platform's supported standard version |
| AI controls | Citations and confidence per field | Plus pinned versions, regression gates, human approval on every plan |
| Audit and retention | Basic change log | Source, AI output, reviewer decision, and final code kept together |
| Model risk | Informal review | Documentation aligned with the firm's model governance policy |

Regulatory parameters change every plan year. Each must be confirmed against the current official source by the compliance owner before it is encoded as a check.

## Testing and quality assurance

A coded plan passes only when test claims pay, or reject, exactly as the plan document says they should.

1. **Golden dataset.** 25 public plans scored against CMS and issuer-published values for the prototype, grown to 200 client-verified plans for production. Every change is scored against it.
2. **Field-level accuracy.** Precision and recall per field (tier cost shares by channel, deductible, OOP maximum, days supply, edits), not just an overall score.
3. **Drug-level accuracy.** Tier and PA, ST, and QL flags scored per drug on a fixed sample, plus full-formulary comparison where a published file exists.
4. **Test claims.** Standard scenarios per plan must produce the expected member cost or reject code: 12 in the prototype simulator, expanded in production and run in the platform test region.
5. **Cross-document reconciliation.** Intake form, SBC, and SPD compared field by field; any conflict stops for a human decision.
6. **Parallel run.** For two weeks before cutover, coders code new groups both ways; outputs are compared.
7. **First-claims review.** After each group goes live, its first paid and rejected claims are compared with expected results.
8. **Post-launch audit.** Sample 10% of approved plans monthly and track claim reprocessing traced to coding.

## Success metrics

Speed gains count only if accuracy holds. A faster process with more claim reprocessing is a failure.

| Metric | Prototype (week 4) | Production launch | 3 months after launch |
| --- | --- | --- | --- |
| Plan-level field accuracy | 88%+ overall | 92%+ | 96% |
| Drug-level tier accuracy | 95%+ on sample | 98%+ | 99%+ |
| Review time per standard plan | Under 20 min | Under 20 min | Under 12 min |
| Plans needing no edits | Measured | 30% | 50% |
| Test claims passing on first run | 95%+ simulated | 90% in test region | 97% |
| Coding-related claim reprocessing | n/a | No increase | 30% reduction |
| Groups per coder | Baseline | 1.5x | 2x |
| Coder adoption on launch line of business | Positive verdict | 80% of new groups | 95% of new groups |

Targets are proposals to be confirmed against the baseline measured in prototype week 1.

## Risks and mitigations

The two biggest risks are a wrong code reaching members at the counter and an 8-week build slipping. Scope is kept tight to protect against both.

| Risk | Mitigation |
| --- | --- |
| AI misreads or invents a benefit value | Source citation per field, confidence thresholds, human approval on every plan, test claims before load |
| Drug names fail to match the compendium | Normalize through RxNorm; unmatched drugs route to manual review, never to a guessed match |
| Adjudication platform has no usable API | Confirm in prototype week 1; fall back to generated load files or a reviewed keying sheet |
| Drug compendium license or crosswalk delayed | Start procurement at the approval gate; RxNorm-only mode covers plan-level coding meanwhile |
| Public plans understate commercial complexity | Synthetic intake forms in the prototype; client golden set started in sprint 1 |
| Tight timeline slips | Fixed scope: one line of business, standard plans; anything else moves to a later release |
| Delays waiting on data, SMEs, or approvals | Secure plan samples, coder time, and security review dates before kickoff |
| Messy source documents (scans, spreadsheets, emails) | OCR quality check; unreadable documents route to manual coding |
| Coder resistance | Coders validate outputs from week 1 and shape the review screen |
| LLM provider changes model behavior | Pin model versions; rerun the regression suite before any upgrade |
| Regulatory parameters change at plan-year rollover | Checks are data-driven and versioned by plan year; compliance owner signs off annually |
| Launch collides with the renewal peak | Go live on off-cycle groups; no cutover during a plan's own renewal |

## Rollout and adoption

The product launches on one line of business, proves itself for a month, then expands.

**Benefit coders and analysts**

- Involved from prototype week 1 as validators of AI output
- Roles shift toward review, exceptions, and QA rather than data entry
- Accuracy dashboards shared openly so trust is earned with data

**Implementation and account management**

- Standard digital intake form replaces free-form emails and spreadsheets
- Document conflicts surfaced at intake, when the client can still answer them
- Setup status visible for each group

**Clinical and formulary teams**

- Client-specific drug overrides listed explicitly instead of buried in free text
- New-drug and formulary-change handling added in a later release

**Expansion after launch**

Add lines of business one at a time, then renewals at scale, custom plan designs, and mid-year amendments, each gated by the same accuracy targets.

## Approvals and support needed

To start the prototype:

- [ ] Sponsor approval for the 4-week prototype
- [ ] CMS public files downloaded and document links confirmed for the 25 selected plans
- [ ] A few hours a week from two reviewers with pharmacy benefit coding experience
- [ ] LLM API access (no BAA needed while only public documents are used)
- [ ] Demo date booked with decision makers for the end of week 4

To start the production build (after the demo):

- [ ] Go decision based on the approval criteria
- [ ] Client plan documents with verified configuration, the client's code library and list IDs, and a HIPAA-eligible LLM environment under a BAA
- [ ] Drug compendium license and data feed
- [ ] Adjudication platform test region access and an integration contact
- [ ] Security and compliance review dates booked for build weeks 6 to 8
- [ ] Launch line of business and go-live window confirmed

## Open decisions

These assumptions were made to complete the plan and should be confirmed before kickoff.

| Decision | Assumed here | Why it matters |
| --- | --- | --- |
| Prototype plan mix | 15 Medicare Part D and 10 exchange plans | Part D has the richest public answer key; a commercial-only client may prefer all exchange plans |
| Launch line of business | Not chosen | Sets the regulatory checks built in sprint 2 |
| Target adjudication platform | Not named | Determines the code library format and load method |
| Drug compendium | Medi-Span or First Databank, per client | Determines the drug crosswalk built in sprint 1 |
| Shared infrastructure with medical benefit coding | Reuse where practical | Reduces build effort and gives coders one review tool |
| Go-live window | Off-cycle groups or February | Avoids the January 1 renewal peak |

## Glossary

| Term | Meaning |
| --- | --- |
| PBM | Pharmacy benefit manager |
| SBC | Summary of Benefits and Coverage |
| SPD | Summary Plan Description |
| EOC | Evidence of Coverage |
| Public Use Files | CMS data files describing plans on the federal exchange and in Medicare Part D |
| NDC | National Drug Code |
| RxNorm / RxCUI | National Library of Medicine drug vocabulary and its concept identifier |
| NADAC | National Average Drug Acquisition Cost |
| NCPDP | National Council for Prescription Drug Programs |
| PA, ST, QL | Prior authorization, step therapy, quantity limit |
| OOP max | Out-of-pocket maximum |
| HDHP | High-deductible health plan |
| LOB | Line of business |
| BAA | Business Associate Agreement |
| PHI | Protected health information |
| MHPAEA | Mental Health Parity and Addiction Equity Act |
| UAT | User acceptance testing |
