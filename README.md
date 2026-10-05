# Pharmacy Plan Workspace for Sales

An AI-assisted account workspace that helps sales and account management teams work with accounts and their pharmacy plans. It reads an account's plan documents and formularies, extracts the plan design with source citations, checks it against what the adjudication platform can administer, shows what is undecided and what changes for members, and hands the coding team a ready-to-code package once the client confirms.

**AI drafts, sales confirms, coders approve.** Nothing goes to a client without a rep's review, and nothing loads to the adjudication platform without a coder's approval.

## Problem

Most pharmacy coding errors start before coding does. A plan design is sold with gaps, contradictions, or features the platform cannot administer, and the problem surfaces weeks later during implementation or on day one at the pharmacy counter. Sales teams have no quick way to read a prospect's current plan, check a requested design against what can be built, or see what a change does to members.

## Solution

A workspace organized by account, plan, and plan year, built on a six-stage pipeline. For each plan a rep gets:

- **Plan summary** in plain language, every value traceable to its source sentence
- **Fit report** rating each feature standard, configurable, custom, or not supported
- **Open questions** for the client, generated from missing decisions and document conflicts
- **Plan comparison**: current against proposed, option against option, this year against next
- **Member impact**: drug disruption and member cost examples
- **Handoff and status**: a confirmed plan becomes a coding package, and implementation progress returns to the account

Targets for the production release:

- A reviewed plan summary in under 20 minutes
- First-pass plan-level field accuracy of 92%+ and drug-level tier accuracy of 98%+
- 90% of gaps, conflicts, and custom requests found before the client confirms
- No increase in post-sale disputes or intake-related claim reprocessing

## Timeline

| Phase | Duration | Outcome |
| --- | --- | --- |
| Phase 1: Prototype | 4 weeks | Live demo and scorecard; go/no-go decision |
| Phase 2: Production build | 8 weeks after approval | Go-live with a pilot sales team on one line of business |
| Total | About 3 months | Kickoff to production launch |

## Status

Planning. No code has been written yet.

## Documentation

| Document | Contents |
| --- | --- |
| [Pharmacy coding process](docs/pharmacy-coding-process.md) | The account lifecycle and where sales fits, what sales must capture, standard versus custom designs, and the full coding reference: source documents, what gets coded, code sets, claim adjudication, test claims, maintenance, common errors |
| [Architecture](docs/architecture.md) | The account workspace, fit ratings, the six-stage pipeline, member cost simulator, and learning loop |
| [Implementation plan](docs/implementation-plan.md) | Business case, users and use cases, 4-week prototype, 8-week production build, compliance, testing, success metrics, risks, rollout, approvals, open decisions |
