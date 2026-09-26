# NBA Lab model card

## Purpose

NBA Lab is a point-in-time **model counterfactual** system. It reconstructs information available at an as-of date, applies explicit interventions, simulates alternate futures, and compares the resulting distributions.

It is not a claim about what *would actually have happened*. Outputs are conditional on the model and its assumptions.

## Team-strength baseline

The deployed season baseline is intentionally simple:

- teams begin at 1500 Elo;
- home-court advantage is 65 Elo points;
- K-factor is 20;
- team strength is frozen at the selected cutoff during a Monte Carlo path;
- future simulated results do not recursively update Elo;
- paired comparisons reuse the same seed/common random stream to reduce Monte Carlo noise.

A more complex model is not promoted merely because it is more sophisticated. It must beat the baseline chronologically or unlock a new validated interaction.

## Season and postseason simulation

Each trial simulates the remaining regular season, conference ordering, play-in, best-of-seven conference playoffs, and Finals.

Known approximations:

1. Official multi-step NBA regular-season tiebreakers are not fully implemented; exact win ties use randomized resolution.
2. Postseason strength is frozen at the selected cutoff.
3. Injuries, fatigue, travel, matchup effects, rotation changes, and in-series learning are not part of the baseline.
4. Finals home court uses the better simulated regular-season record, with random resolution on a tie.

## Counterfactual layers

### Historical game flip

A completed game before the cutoff can be reversed. NBA Lab rebuilds the historical Elo state from the altered result and reuses paired randomness for future comparisons.

### Forced future result

A scheduled game on or after the Scenario cutoff can be assigned a deterministic winner. That result is held fixed in every altered Monte Carlo path while the baseline world remains stochastic.

Forced results are assumptions, not predictions. They propagate through season simulation, player-impact sensitivity, scenario-aware MVP futures, and the leverage context for other upcoming games. A game whose result is already fixed is removed from Scenario-Leverage ranking because its outcome is no longer uncertain.

### Player impact / RAPM

Player Impact fits weighted ridge adjusted plus-minus from normalized five-man lineup stints. It attempts to separate a player's association with point differential from the other nine players on the floor.

RAPM is not a causal player-value truth. Single-season estimates can be noisy and are sensitive to stint quality, regularization, exposure, and lineup connectivity.

### Player absence

Scenario Lab compares the player's RAPM with an explicit replacement RAPM, scales the gap by expected minutes, treats that as an expected per-game margin change, and maps the margin shift into the Elo probability scale. The adjustment applies only to the next stated number of scheduled games.

This does not model a real replacement rotation, role redistribution, fatigue, or strategic adaptation.

### Player-for-player trade

A trade swaps the modeled RAPM contribution of two players across their teams for the remaining schedule at a stated minutes assumption.

The current trade model does **not** include salary, fit, usage, role changes, chemistry, positional constraints, bench effects, or nonlinear lineup interactions. It is a controlled player-impact scenario, not a trade-value oracle.

A player cannot simultaneously be traded and absent in one scenario yet because the timing semantics are not defined.

### Lineup estimates

Lineup Lab combines an additive RAPM prior with observed lineup net rating using possession-weighted shrinkage. An unseen lineup falls back to the prior. It does not invent a chemistry term.

### Game Replay

Game Replay conditions on historical score state, time remaining, pregame team strength, and historical margin variance. It simulates a final-margin distribution and compares edited score states with matched randomness.

This is not yet a possession-level causal model. Current replay output should be interpreted as a game-state baseline.

### Leverage

Leverage Lab forces each possible winner of an upcoming game in paired season simulations and measures how much the league-wide playoff/title distributions move. It measures model sensitivity to the result, not real-world importance in an absolute causal sense.

## Awards model

Awards Lab builds a point-in-time MVP research score from season-to-date player/team information and can bootstrap remaining player-game lines while simulating future team results.

"Leader probability" is the fraction of simulated endings in which the research score finishes first. It is **not** a calibrated probability of how NBA voters will vote.

Scenario-aware award futures can incorporate:
- altered historical results;
- game-specific team-strength adjustments;
- explicit missed games;
- traded-team context for shared player identities.

## Promotion gates

Future team/player/lineup/possession models should be evaluated chronologically with leakage-safe metrics appropriate to the task. Where a component does not have a clean predictive benchmark yet, it must remain labeled as a research assumption rather than being promoted through presentation alone.
