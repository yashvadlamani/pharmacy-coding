# Implementation Plan: Prototype to Production

An AI-assisted account workspace that helps sales and account management teams work with accounts and their pharmacy plans. It reads an account's plan documents and formularies, extracts the plan design with source citations, checks it against what the adjudication platform can administer, shows what is undecided and what changes for members, and hands the coding team a ready-to-code package once the client confirms.

**AI drafts, sales confirms, coders approve.** Nothing goes to a client without a rep's review, and nothing loads to the adjudication platform without a coder's approval.

| Phase | Duration | Outcome |
| --- | --- | --- |
| Phase 1: Prototype | 4 weeks | Live demo and scorecard; go/no-go decision |
| Phase 2: Production build | 8 weeks after approval | Go-live with a pilot sales team on one line of business |
| Total | About 3 months | Kickoff to production launch |

The pipeline and workspace are described in [architecture.md](architecture.md). The coding process the product feeds is described in [pharmacy-coding-process.md](pharmacy-coding-process.md).

## Contents

- [Business case](#business-case)
- [Users and use cases](#users-and-use-cases)
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

Most pharmacy coding errors start before coding does: a plan design is sold with gaps, contradictions, or features the platform cannot administer, and the problem surfaces weeks later during implementation or on day one at the pharmacy counter. Sales teams have no quick way to read a prospect's current plan, check a requested design against what can be built, or see what a change does to members.

| Pain point | Impact today | What the product changes |
| --- | --- | --- |
| Reading a prospect's plan documents by hand | Days to understand an incumbent design; details missed | Structured plan summary in minutes, every value cited |
| Promising features the platform cannot administer | Custom builds, delays, post-sale disputes | Fit check before the proposal goes out |
| Incomplete or contradictory intake | Repeated clarification rounds during implementation | Open questions listed while the rep is still with the client |
| No view of member impact | Disruption found after go-live | Drug disruption and member cost examples at proposal stage |
| Renewal changes tracked in email | Changes missed or applied to the wrong year | Year-over-year comparison listing only what changed |
| Re-keying from sales documents into coding | Slow handoff, transcription errors | Confirmed plan flows to coding as a structured package |
| No visibility after the sale | Reps chase implementation for status | Status shown on the account |

### Value model

To be filled in with baseline numbers gathered in week 1 of the prototype:

- **Sales time saved** = accounts per year × hours per account spent reading documents and chasing clarifications × share automated
- **Faster implementation** = days from signed sale to complete intake today × reduction
- **Fewer disputes and rework** = post-sale disputes and custom builds per year × cost per event × reduction
- **Error savings** = coding-related claim reprocessing events traced to intake × cost per event × reduction
- **Win rate and retention** = effect of faster, more specific proposals and cleaner renewals, tracked but not assumed

The build is lean, so the main costs are LLM usage, hosting, CRM integration, a drug-compendium license in production, and time from sales and coding staff for validation.

## Users and use cases

| User | What they do in the product |
| --- | --- |
| Sales executive (new business) | Upload a prospect's current plan; get a summary, fit report, and comparison against proposed options |
| Account manager (existing accounts) | Keep each account's plans current; run renewal comparisons; answer client benefit questions |
| Implementation manager | Close open questions, obtain client confirmation, trigger the handoff |
| Benefit coder | Receive the coding package, approve or correct it, load it |
| Sales leadership | See pipeline readiness, open items by account, and custom requests awaiting approval |

Use cases, in priority order for the first release:

1. **Understand a plan.** Turn an account's documents into a cited, plain-language plan summary.
2. **Check fit.** Rate every requested feature as standard, configurable, custom, or not supported.
3. **Close gaps.** Generate the list of client questions from missing decisions and document conflicts.
4. **Compare.** Current against proposed, option against option, this year against next.
5. **Show member impact.** Drug disruption and member cost examples.
6. **Confirm and hand off.** Client-confirmed summary becomes a coding package; status returns to the account.

## Delivery plan

| Phase | When | Focus |
| --- | --- | --- |
| Prototype, week 1 | Weeks 1 to 4 | Data, sample accounts, and setup |
| Prototype, week 2 | | Plan-level and drug-level extraction |
| Prototype, week 3 | | Fit check, comparison, account workspace |
| Prototype, week 4 | | Tune and live demo |
| **Approval gate** | End of week 4 | Demo meets criteria |
| Sprint 1 | Build weeks 1-2 | Secure environment, CRM connection, standard catalog and code library |
| Sprint 2 | Build weeks 3-4 | Full benefit set, fit rules, comparison and disruption, client summary |
| Sprint 3 | Build weeks 5-6 | Client confirmation, handoff to coding, status return, learning loop |
| Sprint 4 | Build weeks 7-8 | Regression, sign-off, UAT, pilot, go-live |
| **Go-live** | | Pilot sales team on one line of business, then hypercare |

The approval gate is the only decision point. If the demo misses its criteria, the scorecard shows what needs work before the build is reconsidered.

## Phase 1: Prototype (weeks 1 to 4)

The prototype shows a rep working eight sample accounts built from 25 real, publicly available pharmacy plans: plan summaries with citations, fit reports, open questions, comparisons, member impact, and a coding handoff package. It ends in a go/no-go demo.

No client documents, standard offering catalog, or platform codes are available yet, so every prototype step runs on public sources. Client data replaces them in Phase 2 without changing the pipeline.

### Scope

- **8 sample accounts holding 25 plans**, each with public documents and published values to score against:
  - 15 Medicare Part D plans (stand-alone and Medicare Advantage), including the same plans in two consecutive years for renewal comparison
  - 10 exchange plans, each with an SBC and a machine-readable formulary
  - Account names and contacts are fictional; the plans are real
- **About 30 plan-level fields per plan:** pharmacy deductible and whether it is integrated with medical, tiers the deductible applies to, OOP maximum, number of tiers, cost share per tier for retail 30-day, retail 90-day, mail, and specialty, coinsurance minimums and maximums, days supply limits by channel, mail-order availability, specialty pharmacy rule
- **Drug-level attributes** for a fixed list of 200 commonly used drugs per formulary: tier, prior authorization, step therapy, quantity limit
- **Workspace views:** account overview, plan summary, fit report, open questions, plan comparison, drug lookup and disruption, member cost examples, handoff package
- Public plan documents only: no member PHI and no client or prospect data, so no BAA is needed until real documents are introduced
- **Out of scope:** CRM integration, pricing and rebate terms, quotes and financial guarantees, claims-based disruption using member data, live platform load, Medicaid, compounds, coordination of benefits

### Public data sources

| Pipeline step | What the prototype needs | Public source |
| --- | --- | --- |
| 1. Ingest | Plan documents | Part D Summary of Benefits and Evidence of Coverage documents on plan websites; exchange SBC PDFs linked from the CMS Exchange Public Use Files |
| 1. Ingest | Formulary documents | Formulary PDFs published by each Part D plan and exchange issuer |
| 1. Ingest | RFPs, intake forms, and riders | Not published: synthetic documents written against a real plan, with seeded gaps and conflicts |
| 1. Ingest | Scanned documents | Real documents degraded into scan-like images |
| 2. Extract | Verified plan-level values | CMS Part D formulary and pharmacy network files (beneficiary cost by tier, days supply, and pharmacy type); CMS Exchange Benefits and Cost Sharing Public Use File |
| 2. Extract | Verified drug-level values | CMS Part D formulary file (tier, PA, ST, QL per drug by RxCUI); exchange issuers' machine-readable formulary files |
| 3. Map and fit | Drug identity | RxNorm from the National Library of Medicine; FDA NDC Directory |
| 3. Map and fit | Standard offerings and codes | A placeholder catalog of standard plan designs and a placeholder code table, both replaced by the firm's own in production |
| 4. Validate | Commonly used drugs for disruption | CMS Medicare Part D Spending by Drug data, to pick the 200-drug list |
| 4. Validate | Drug prices for member cost examples | NADAC from Medicaid.gov, as a stand-in for contracted network pricing |
| 4. Validate | Regulatory checks | CMS-published Part D benefit parameters for the plan year; ACA preventive drug categories |
| 5. Review | Reviewers and baseline time | Not public: internal sales and coding reviewers time themselves doing the work by hand, then with the tool |

Limits of public data, to state openly in the pitch:

- Published values are filed plan designs, not a client's request. Real sales documents (RFPs, emails, incumbent contracts) are messier and are represented only by synthetic examples.
- The standard offering catalog and fit rules are placeholders. Fit ratings in the demo show the mechanism, not the firm's real limits.
- Commercial self-funded plans, the most customized segment, publish nothing.
- Disruption is shown against a fixed drug list. Real disruption analysis uses the account's own claims and belongs in production under a BAA.
- NADAC approximates acquisition cost, not a contracted rate. Member cost examples are illustrative.
- Review-time and "would use it" results come from internal reviewers until the pilot sales team takes part.
- File layouts, plan-year parameters, and document links change yearly and must be confirmed in week 1.

### Prototype stack

- Enterprise LLM with structured JSON output for extraction
- Python service for parsing, OCR, extraction, drug normalization, fit rating, and code mapping
- Placeholder standard offering catalog and code table as lookup tables
- Web account workspace: source document beside the plan summary, with fit, questions, comparison, and impact views
- Rules-based member cost simulator, returning member cost or a reject reason
- Exportable plan summary and coding handoff package

Where practical, components are reused from the medical benefit coding prototype.

### Weekly plan

| Week | Focus | Deliverable |
| --- | --- | --- |
| 1 | Data, accounts, setup | CMS files downloaded and layouts confirmed; 25 plans selected and grouped into 8 sample accounts; golden dataset built from published values; 200-drug list fixed; field list, placeholder catalog, and fit rules agreed with a sales reviewer and a coding reviewer; baseline times measured |
| 2 | Extraction | Plan-level fields extracted with citations and confidence; formulary tables parsed and drugs normalized to RxNorm; first accuracy report against published values; plan summary view |
| 3 | Fit, comparison, workspace | Fit ratings and open-question generation working; plan and year-over-year comparison; drug disruption; member cost simulator running 12 scenarios per plan; account workspace usable |
| 4 | Tune and demo | Misses fixed; synthetic RFP, intake-form, rider, and scanned-copy cases added; handoff package export; final scorecard; reviewers time their work; live demo |

### Member cost and test scenarios in the prototype

Each scenario is shown to sales as a member cost example and written into the handoff package as a test claim.

| # | Scenario | Expected result |
| --- | --- | --- |
| 1 | Generic, retail 30-day | Tier 1 cost share |
| 2 | Preferred brand, retail 30-day | Preferred brand cost share |
| 3 | Non-preferred brand, retail 30-day | Non-preferred cost share within min and max |
| 4 | Maintenance drug, mail 90-day | Mail cost share |
| 5 | Specialty drug | Specialty cost share with 30-day limit |
| 6 | Claim in the deductible phase | Member pays the drug price up to the deductible |
| 7 | Claim after OOP maximum is met | $0 |
| 8 | PA-required drug, no authorization | Not paid: prior authorization required (reject 75) |
| 9 | Quantity above the limit | Not paid: plan limit exceeded (reject 76) |
| 10 | Early refill | Not paid: refill too soon (reject 79) |
| 11 | Drug not on the formulary | Not paid: not covered (reject 70) |
| 12 | Days supply above the channel limit | Not paid: plan limit exceeded (reject 76) |

### Demo script (20 minutes)

1. Open a sample account. The overview shows its plans, effective dates, and open items.
2. Upload a prospect's current plan documents and formulary that the system has never seen, from outside the 25-plan set.
3. The plan summary populates in plain language; click any value to see its highlighted source sentence.
4. Open the fit report: most features are standard, one is custom, one is not supported and shows the nearest alternative.
5. Open questions: a seeded conflict between the intake form and the SBC, and two decisions the documents never state, each phrased as a question for the client.
6. Compare the current plan with a proposed option, then with next year's version; only the differences are listed.
7. Look up three drugs and open the disruption view: which commonly used drugs change tier, gain an edit, or lose coverage.
8. Show member cost examples for both options side by side.
9. Mark the plan confirmed and export the handoff package; show the proposed codes and test claims the coder receives.
10. Close on the scorecard: accuracy, gaps caught, time saved versus today.

### Approval criteria for Phase 2

| Measure | Target |
| --- | --- |
| Plan-level field accuracy, Part D plans | 90%+ |
| Plan-level field accuracy, exchange plans | 85%+ |
| Drug-level tier accuracy on the 200-drug list | 95%+ |
| Drug-level PA, ST, and QL flag accuracy | 90%+ |
| Fields with a valid source citation | 100% |
| Seeded conflicts and missing decisions caught | All |
| Year-over-year changes correctly identified | 95%+ |
| Fit ratings matching the coding reviewer's judgment | 90%+ |
| Time for a rep to produce a reviewed plan summary | Under 20 minutes |
| Sales verdict | Majority would use it on live accounts |
| Coding verdict | Handoff package is usable without re-reading the source documents |

Accuracy is scored against the published CMS and issuer values. Time and verdicts come from internal reviewers during the prototype and are re-measured with the pilot sales team in production.

## Phase 2: Production build (8 weeks)

Phase 2 turns the prototype into a secure, integrated product in four 2-week sprints, ending with go-live for a pilot sales team on one line of business.

| Sprint | Weeks | Focus | Done when |
| --- | --- | --- | --- |
| 1 | 1-2 | Production foundations | Secure environment with SSO, encryption, logging, and CI/CD; accounts and ownership synced from the CRM; access limited to a rep's own accounts; standard offering catalog, code library, and list IDs loaded; drug compendium connected |
| 2 | 3-4 | Full benefit set and sales views | All plan design features covered; fit rules written and signed off by coding and clinical teams; comparison and disruption on real formularies; client-ready plan summary export in the firm's template |
| 3 | 5-6 | Confirmation, handoff, learning loop | Client confirmation recorded; coding package delivered to the coding team's intake queue; coder approval and corrections captured; implementation status returned to the account and CRM; renewal mode against the prior-year configuration |
| 4 | 7-8 | Hardening and launch | Regression suite on a 200-plan golden set; security and compliance sign-off; UAT with sales and coding; pilot on live accounts; go-live and hypercare |

### Sprint detail

**Sprint 1: Production foundations**

- Stand up development, test, and production environments in the approved cloud
- SSO, role-based access, encryption at rest and in transit, access logging
- Connect the CRM: accounts, opportunities, owners, and effective dates
- Restrict each rep to their own accounts; leadership sees roll-ups
- Execute the BAA with the LLM provider; confirm no data is retained for training
- Load the standard offering catalog, the code library, formulary and drug-list IDs, and the clinical program catalog
- Connect the licensed drug compendium and build the crosswalk from RxNorm
- Begin the client golden set: 50 already-coded plans with their original sales documents

**Sprint 2: Full benefit set and sales views**

- Extend extraction to accumulator rules, medical integration, brand penalties, mandatory mail and specialty, preventive and HDHP lists, exclusions, and client-specific drug overrides
- Replace placeholder fit rules with the firm's real rules; each rule has a named owner in coding or clinical
- Approval step for custom requests before a rep can commit to them
- Comparison of incumbent formulary against the firm's formularies
- Client-ready summary and comparison exports in approved templates, labeled draft until confirmed
- Regulatory checks for the launch line of business
- Grow the golden set to 120 plans

**Sprint 3: Confirmation, handoff, learning loop**

- Client confirmation record: what was confirmed, by whom, when, and against which document versions
- Coding package: confirmed fields, proposed codes, source citations, fit notes, and test claims with expected results
- Delivery into the coding team's existing intake queue, with coder approval and peer QA unchanged
- Coder corrections and client answers feed the golden set, prompts, and fit rules
- Implementation status returned to the account workspace and the CRM
- Renewal mode: compare new documents with the prior-year configuration and list only what changed
- Grow the golden set to 200 plans

**Sprint 4: Hardening and launch**

- Regression suite must pass on the 200-plan golden set before any release
- Security, compliance, legal, and model-governance sign-off, including review of client-facing templates
- Sales and coder training and UAT
- Pilot: a small sales team uses it on live accounts alongside their current process for two weeks
- Go-live for the pilot team on the first line of business
- Hypercare: every handoff from the pilot compared with what the coder finally loaded

### Production-ready checklist

- [ ] Runs in the firm's approved cloud with SSO and role-based access
- [ ] Reps see only their own accounts; prospect documents handled under the applicable NDA
- [ ] BAA in place with the LLM provider; no data retained for model training
- [ ] Model and prompt versions pinned; changes go through regression tests
- [ ] Every value stores source passage, confidence, reviewer, and timestamp
- [ ] Client-facing outputs carry a draft label and disclaimer until confirmed, in legally approved templates
- [ ] Custom and not-supported items cannot be committed without recorded approval
- [ ] Fit rules have named owners and a change process
- [ ] Handoff package accepted by the coding team; coder approval still required before load
- [ ] Monitoring and alerts for errors, latency, and accuracy drift
- [ ] Runbook, fallback to the manual process, and support path documented
- [ ] Pilot completed with sales and coding sign-off

> **Timing note:** A kickoff in early October puts the approval gate in early November and go-live in early January. That suits sales, since the tool arrives ahead of the selling season for the following January. It is hard on the coding team, whose peak runs October through December and whose time is needed in sprints 2 to 4 for fit rules and UAT. Either reserve named coder time before kickoff or shift the build to start in January.

## Compliance and security

The prototype avoids member PHI and client data entirely. The production build adds the controls needed for client and prospect documents and for client-facing output.

| Requirement | Prototype | Production |
| --- | --- | --- |
| HIPAA | Public plan documents only, no PHI | Encryption, access logging, minimum necessary access; BAA before any client document or claims data is used |
| Prospect confidentiality | Not applicable | Prospect documents handled under NDA; access limited to the account team; retention rules for lost opportunities |
| Client-facing statements | Outputs labeled illustrative | Approved templates and disclaimers; summaries are not quotes, contracts, or plan documents |
| Pricing and guarantees | Out of scope | Out of scope for this release; no rebate, discount, or guarantee terms generated |
| Commitments on custom items | Shown as a rating | Recorded approval required before a rep commits |
| ACA preventive drugs and cost-sharing limits | Checked where published | Non-compliant designs flagged to the rep before proposal |
| HDHP rules | Not in scope | Flag designs that would break HSA eligibility |
| Medicare Part D | Extracted values checked against the year's CMS benefit parameters | Checks aligned with CMS rules for the launch line of business; outputs are for plan sponsors, not beneficiary marketing |
| Mental health parity (MHPAEA) | Not in scope | Flag for compliance review where pharmacy cost sharing or edits may raise a parity question |
| State law | Not in scope | Rules for situs states of the first line of business, such as insulin cost caps and copay accumulator restrictions |
| AI controls | Citations and confidence per field | Plus pinned versions, regression gates, rep review before client use, coder approval before load |
| Audit and retention | Basic change log | Source, AI output, rep and client confirmation, coder decision, and final code kept together |
| Model risk | Informal review | Documentation aligned with the firm's model governance policy |

Regulatory parameters change every plan year. Each must be confirmed against the current official source by the compliance owner before it is encoded as a check.

## Testing and quality assurance

The product passes only when what the rep shows the client, what the client confirms, and what the coder loads are the same plan.

1. **Golden dataset.** 25 public plans scored against CMS and issuer-published values for the prototype, grown to 200 client plans with their original sales documents and final coded configuration for production. Every change is scored against it.
2. **Field-level accuracy.** Precision and recall per field, not just an overall score.
3. **Drug-level accuracy.** Tier and PA, ST, and QL flags scored per drug on a fixed list, plus full-formulary comparison where a published file exists.
4. **Gap detection.** Seeded conflicts and missing decisions must all be caught; false alarms are counted too, since noisy questions waste client goodwill.
5. **Fit rating accuracy.** Ratings compared with the judgment of experienced coders on the golden set.
6. **Comparison accuracy.** Year-over-year and plan-to-plan differences checked against known changes in the published files.
7. **Member cost scenarios.** Standard scenarios per plan must produce the expected member cost or reject reason.
8. **Handoff fidelity.** For each pilot account, the handoff package is compared with what the coder finally loaded; every difference is classified and fed back.
9. **Pilot.** A small sales team uses the product alongside the current process for two weeks before go-live.
10. **Post-launch audit.** Sample 10% of confirmed plans monthly and track post-sale disputes and claim reprocessing traced to intake.

## Success metrics

Speed counts only if accuracy holds. A faster sale that produces more disputes or claim reprocessing is a failure.

| Metric | Prototype (week 4) | Production launch | 3 months after launch |
| --- | --- | --- | --- |
| Plan-level field accuracy | 88%+ overall | 92%+ | 96% |
| Drug-level tier accuracy | 95%+ on list | 98%+ | 99%+ |
| Time to a reviewed plan summary | Under 20 min | Under 20 min | Under 12 min |
| Gaps and conflicts found before client confirmation | Seeded items caught | 90% | 95% |
| Clarification rounds after handoff | n/a | Baseline | 50% reduction |
| Days from signed sale to complete intake | n/a | Baseline | 40% reduction |
| Custom requests identified before commitment | Measured | 90% | 98% |
| Handoff fields changed by the coder | Measured | Under 10% | Under 5% |
| Post-sale disputes and intake-related reprocessing | n/a | No increase | 30% reduction |
| Adoption by the pilot team | Positive verdict | 80% of new accounts | 95% of new accounts |

Targets are proposals to be confirmed against the baseline measured in prototype week 1.

## Risks and mitigations

The biggest risks are a rep relying on a wrong value in front of a client, and the product being read as a commitment it is not.

| Risk | Mitigation |
| --- | --- |
| AI misreads or invents a benefit value | Source citation on every value, confidence thresholds, rep review before client use, client confirmation, coder approval before load |
| Fit rating says "standard" for something that is not | Fit rules owned by coding and clinical teams; unclear cases default to "ask"; coder corrections update the rules |
| Output treated as a quote or contract | Draft labels and approved disclaimers; pricing excluded; confirmation is a recorded step, not an export |
| Rep commits to a custom item | Approval required and recorded before the item can be marked committed |
| Prospect or client data exposed across accounts | Access limited to the account team; audit logging; NDA and retention rules enforced |
| Sales adoption is low | Pilot team shapes the workspace from prototype week 1; the product removes work reps already dislike; CRM integration avoids double entry |
| Coding team sees it as sales overriding their control | Coder approval and peer QA unchanged; coders own the fit rules; handoff fidelity reported openly |
| Too many low-value questions for the client | False alarms measured; questions ranked; rep chooses which to send |
| Drug names fail to match the compendium | Normalize through RxNorm; unmatched drugs flagged, never guessed |
| CRM integration delayed | Confirm API access in prototype week 1; fall back to account import by file |
| Drug compendium license or crosswalk delayed | Start procurement at the approval gate; RxNorm-only mode covers plan-level work meanwhile |
| Public plans understate commercial complexity | Synthetic RFPs and intake forms in the prototype; client golden set started in sprint 1 |
| Tight timeline slips | Fixed scope: one line of business, one pilot team; platform load and pricing move to later releases |
| LLM provider changes model behavior | Pin model versions; rerun the regression suite before any upgrade |
| Regulatory parameters change at plan-year rollover | Checks are data-driven and versioned by plan year; compliance owner signs off annually |

## Rollout and adoption

The product launches with one pilot sales team on one line of business, proves itself for a month, then expands.

**Sales and account management**

- A pilot group of reps involved from prototype week 1, shaping the workspace and the client-facing summary
- Short, scenario-based training: a new prospect, a renewal, a client question
- Accounts and status live in the CRM they already use
- Clear guidance on what the tool's output is and is not when shown to a client

**Benefit coders and analysts**

- Own the fit rules and the handoff package format
- Keep approval and peer QA exactly as today
- Receive complete, cited intake instead of emails and spreadsheets

**Clinical and formulary teams**

- Own formulary and clinical-program content in the catalog
- See client-specific drug requests listed explicitly at proposal stage

**Sales leadership**

- Dashboard of accounts by readiness, open items, and custom requests awaiting approval

**Expansion after launch**

Add sales teams and lines of business one at a time. Later releases, each gated by the same accuracy targets: claims-based disruption analysis, mid-year amendments, direct load to the adjudication platform, and plan design recommendations.

## Approvals and support needed

To start the prototype:

- [ ] Sponsor approval for the 4-week prototype, with a sales leader as co-sponsor
- [ ] CMS public files downloaded and document links confirmed for the 25 selected plans
- [ ] A few hours a week from two sales or account-management reviewers and one experienced benefit coder
- [ ] Two or three anonymized examples of real sales documents (RFP, intake form) to model the synthetic ones on
- [ ] LLM API access (no BAA needed while only public documents are used)
- [ ] Demo date booked with sales and operations decision makers for the end of week 4

To start the production build (after the demo):

- [ ] Go decision based on the approval criteria
- [ ] Pilot sales team and launch line of business named
- [ ] CRM API access and an integration contact
- [ ] The firm's standard offering catalog, code library, and list IDs
- [ ] Past accounts with original sales documents and final coded configuration, for the golden set
- [ ] Drug compendium license and data feed
- [ ] HIPAA-eligible LLM environment under a BAA
- [ ] Named coder and clinical owners for fit rules, with time reserved through the build
- [ ] Legal and compliance review of client-facing templates booked for build weeks 3 to 4, and security review for weeks 6 to 8

## Open decisions

These assumptions were made to complete the plan and should be confirmed before kickoff.

| Decision | Assumed here | Why it matters |
| --- | --- | --- |
| Primary users | Sales executives and account managers, with coders downstream | Sets the workspace design and the pilot team |
| New business, renewals, or both | Both, with new business first in the demo | Changes which comparison views matter most |
| Is output shown to clients | Yes, as a draft summary in an approved template | Triggers legal review and disclaimers |
| Pricing and quoting | Out of scope | Adding it brings contract, underwriting, and rebate data into scope |
| Platform load | Stays with coders; direct load is a later release | Keeps the 8-week build achievable |
| CRM | Not named | Determines the integration built in sprint 1 |
| Prototype plan mix | 15 Medicare Part D and 10 exchange plans | Part D has the richest public answer key; a commercial-only team may prefer all exchange plans |
| Launch line of business | Not chosen | Sets the regulatory checks and fit rules built first |
| Drug compendium | Medi-Span or First Databank, per the firm | Determines the drug crosswalk built in sprint 1 |
| Build start | Immediately after the approval gate | Collides with the coding team's fourth-quarter peak |

## Glossary

| Term | Meaning |
| --- | --- |
| PBM | Pharmacy benefit manager |
| CRM | Customer relationship management system |
| RFP | Request for proposal |
| NDA | Non-disclosure agreement |
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
