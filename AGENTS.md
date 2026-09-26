# AGENTS.md

## Project intent

NBA Lab is a basketball simulation and counterfactual research system, not a generic stats dashboard or franchise-management app.

Every major feature should expose computation that cannot be replaced by prose alone: simulation, reconstruction, regularized estimation, optimization, or probabilistic inference.

The current integrating surface is **Scenario Lab**.

## Non-negotiable modeling rules

1. **Preserve point-in-time correctness.**
   - An as-of model may use only information available by that cutoff.
   - Full-season snapshots must never leak later scores, standings, player logs, or replay state into earlier dates.
   - Add or retain regression tests whenever point-in-time logic changes.

2. **Counterfactuals are model worlds, not causal claims.**
   - Use language such as "under this model", "scenario", "association estimate", and "distribution shift".
   - Do not present an edited game, injury, trade, or lineup as proof of what would have happened in reality.

3. **Do not hide assumptions.**
   - Player absences must state replacement RAPM, minutes, and missed games.
   - Trade scenarios must remain explicit about unmodeled fit, role, salary, rotation, chemistry, and nonlinear interactions.
   - Game Replay must remain labeled as a state-based baseline until possession context is actually modeled.

4. **Complexity must earn promotion.**
   - A more complex predictive model should beat a frozen baseline on a declared chronological metric, or unlock a qualitatively new validated interaction.
   - Do not promote a model because it is newer, deeper, or more complicated.

5. **Missing data stays missing.**
   - Do not fabricate NBA observations to fill real-data gaps.
   - Synthetic fixtures are allowed only when clearly labeled and deterministic.

## Scenario Lab contract

The same scenario specification should be reusable across labs.

Current intervention types:
- historical game flip before the cutoff;
- player absence;
- one player-for-player RAPM-backed trade.

Current constraints:
- a player cannot be both traded and absent in the same scenario;
- player-impact uncertainty bands are approximate model-based diagnostics, not formal confidence guarantees.

When extending Scenario Lab:
- prefer adding to the shared scenario builder rather than creating duplicate intervention logic in another module;
- preserve paired randomness where comparisons require low-noise deltas;
- serialize all assumptions needed to reproduce a scenario;
- keep copied/shared scenario links backward-compatible by versioning the spec.

## Testing expectations

Before a feature is considered complete:

- `node --check src/nba_lab/static/app.js`
- `pytest -q`

Add focused regression tests for:
- point-in-time leakage;
- deterministic paired comparisons;
- scenario composition;
- parser/data-contract validation;
- numerical invariants such as antisymmetry or monotonic direction when applicable.

Do not weaken or delete tests merely to make a new implementation pass.

## UI principles

- Keep the scientific/lab visual language.
- Prefer one memorable interaction over many generic controls.
- Surface provenance, assumptions, uncertainty, and source mode.
- Do not turn the app into an NBA news/RAG/chat surface.
- Avoid fake precision; if a number is assumption-sensitive, show that sensitivity.

## Data

Real snapshots are local and generally uncommitted. Deterministic synthetic fixtures keep the full product testable offline.

See:
- `DATA.md`
- `MODEL_CARD.md`
- `ROADMAP.md`

## Safe next directions

High-value work currently includes:
- validating RAPM-to-team-strength translation;
- stronger player-impact uncertainty;
- scenario sensitivity analysis;
- real possession/lineup context for Game Replay;
- broader cross-lab use of the shared Scenario spec;
- reproducible real-data acquisition and QA.

Avoid adding unrelated breadth until one of those becomes clearly blocked.
