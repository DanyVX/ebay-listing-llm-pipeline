# Design

## M0 architecture

- Python package under `src/elp/`; policy metadata in YAML; SQLite-based cost reservations.
- Fixture mode is the only available model. No API integration or cost-producing side effects.
- Rules are declarative metadata in M0, **not an implemented compliance engine**.

## Decision log

| Date | Options | Choice | Why |
|---|---|---|---|
| 2026-10-10 | Paid API initially / offline | Offline fixture first | No secrets, no initial spend, deterministic testing |
| 2026-10-10 | Floats / integer USD micros | Integer USD micros with Decimal conversion | Avoid undercharging due to float rounding |
| 2026-10-10 | Files / SQLite | SQLite transaction-backed ledger | Atomic reservations across threads/processes |
| 2026-10-10 | Hard-code all item-specific limits / metadata lookup | Flag as unknown until marketplace/category lookup | Official guidance says limits vary |
| 2026-10-10 | Update main directly / milestone PR | `m0-foundation-policy-budget` PR | Keeps changes reviewable |

## Future decisions

CSV streaming, provider adapters, grounding thresholds, and caching will be logged when their milestones begin. API and model licenses have not been approved yet.

| 2026-10-10 | pandas memory load / stdlib streaming | csv.reader + read-only openpyxl | 100k+ rows without whole-file memory materialization |
