# Automated Pharmacy Benefit Coding

AI-assisted pharmacy benefit coding for PBM and health-plan benefit operations: an AI pipeline reads plan documents and formularies, extracts cost-sharing rules and drug-level attributes with source citations, maps them to adjudication-platform codes, validates them with test claims, and hands a coder a ready-to-approve plan.

**AI drafts and humans decide.** Nothing loads to the adjudication platform without passing automated checks and a coder's approval.

## Problem

Benefit coders translate each sold pharmacy plan (intake form, SBC, SPD, formulary and clinical program selections) into adjudication-platform parameters by hand. Pharmacy claims adjudicate in seconds at the counter, so a coding error reaches members on day one. The work is slow, concentrated in the fourth-quarter renewal season, and dependent on scarce experts.

## Solution

A six-stage pipeline that turns plan documents into proposed benefit codes, each traceable to its source sentence, with a human approving everything that loads.

Targets for the production release:

- Review time for a standard plan under 20 minutes
- First-pass plan-level field accuracy of 92%+ and drug-level tier accuracy of 98%+
- Every coded value traceable to its source sentence, with a full audit trail
- No increase in coding-related claim reprocessing

## Timeline

| Phase | Duration | Outcome |
| --- | --- | --- |
| Phase 1: Prototype | 4 weeks | Live demo and scorecard; go/no-go decision |
| Phase 2: Production build | 8 weeks after approval | Go-live on the first line of business |
| Total | About 3 months | Kickoff to production launch |

## Status

Planning. No code has been written yet.

## Documentation

| Document | Contents |
| --- | --- |
| [Pharmacy coding process](docs/pharmacy-coding-process.md) | How pharmacy benefit coding is done today: roles, source documents, end-to-end steps, what gets coded, code sets, claim adjudication, test claims, maintenance, common errors |
| [Architecture](docs/architecture.md) | The proposed six-stage coding pipeline, test-claim simulator, and learning loop |
| [Implementation plan](docs/implementation-plan.md) | Business case, 4-week prototype, 8-week production build, compliance, testing, success metrics, risks, rollout, approvals, open decisions |
