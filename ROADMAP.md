# NBA Lab roadmap

NBA Lab is a host for basketball modeling experiments that share a point-in-time data layer. It is **not** intended to become a generic franchise-management clone.

## Product rule

Every lab should expose a computation that is difficult to fake with prose alone: simulation, reconstruction, optimization, regularized estimation, or probabilistic inference.

The shared state is converging toward:

`season -> game -> possession -> stint -> lineup -> player -> context -> scenario`

## Live now

### Season Lab
Point-in-time Elo, remaining-season Monte Carlo, play-in/playoffs/Finals, historical game flips, paired deltas.

### Scenario Lab
Composable alternate worlds using:
- historical game flips;
- deterministic upcoming-game result assumptions;
- RAPM-backed player absences;
- RAPM-backed player-for-player trades;
- game-specific strength adjustments;
- league-wide win/playoff/title ripple;
- point-in-time MVP ripple;
- scenario-aware MVP future simulation;
- scenario-aware Leverage re-ranking;
- Leverage → forced-result Scenario branching;
- reproducible share links;
- deterministic one-world rerolls with standings, play-in, playoff bracket, and champion.

### Matchup Lab
Single-game and playoff-series simulation from a frozen as-of state.

### Timeline Lab
Game-by-game rating and record evolution.

### Model Lab
Chronological probabilistic evaluation and calibration for the deployed Elo baseline, held-out parameter selection, and an experimental score-aware Elo family gate.

### Awards Lab
Point-in-time MVP race replay plus simulated remaining-season finishes.

### Player Impact
Ridge RAPM, exposure diagnostics, and regularization paths over normalized lineup stints.

### Lineup Lab
Observed-lineup evidence blended with additive RAPM priors; unseen units fall back to the prior rather than fabricated chemistry.

### Leverage Lab
Upcoming games ranked by the paired season distribution shift produced by each possible winner.

### Game Replay
Historical score-state branching with paired simulations and season-ripple propagation.

## Highest-value next work

### 1. Make player-aware scenarios more defensible

Current RAPM-to-team-strength translation is useful but intentionally simple. Improve it only behind measurable checks:

- bootstrap or resample RAPM to expose uncertainty intervals;
- recency weighting / rolling windows;
- test offensive and defensive splits only if stable;
- validate the RAPM-to-margin-to-Elo translation against held-out games;
- validate persistent trade-strength effects separately for regular season and postseason;
- model replacement minutes from actual rotation context rather than one scalar;
- support trade + absence timing only after the semantics are explicit.

### 2. Move Game Replay toward real possession context

The current replay baseline conditions on score, clock, and pregame strength. The next meaningful upgrade is not cosmetic UI; it is a possession/state model using real play-by-play context:

- possession ownership;
- lineup on floor;
- fouls / bonus;
- timeout state when available;
- possession outcome distributions;
- lineup-aware continuation;
- calibration against held-out historical states.

### 3. Unify scenario state across every lab

Scenario Lab is now the integration surface. Continue moving labs from isolated controls toward one shared scenario specification:

- continue expanding the current Scenario → Matchup and Scenario → game-specific closing-five drilldowns;
- deepen Player Impact / Lineup handoffs with rotation-aware replacement assumptions;
- extend the existing Game Replay → Scenario branch into possession-aware continuation;
- persist/share named scenarios without introducing accounts;
- expose a machine-readable scenario result bundle.

### 4. Replace synthetic fallbacks with reproducible real snapshots where practical

Keep offline fixtures, but improve one-command acquisition and QA for:
- NBA schedule;
- player game logs;
- normalized possession/lineup stints;
- PlayByPlayV3 replay snapshots.

## Research / promotion gates

A more sophisticated model gets deployed only if it either:

1. improves a declared held-out metric under chronological evaluation; or
2. unlocks a qualitatively new interaction whose assumptions are explicit and testable.

Engineering complexity is not evidence of model quality.

## What not to build

- generic NBA news/chatbot/RAG;
- salary-cap / draft / franchise-management systems just because they are large;
- invented player ratings presented as truth;
- opaque deep models without benchmark wins;
- fake precision around trade fit or causal injury effects;
- a giant stats dashboard whose outputs are easier to look up elsewhere.
