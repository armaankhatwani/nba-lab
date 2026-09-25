# NBA Lab model card

## Purpose

NBA Lab is a point-in-time **model counterfactual** system. It reconstructs the information available before an as-of date, simulates the remaining schedule many times, and compares paired alternate histories.

It is not a claim about what *would actually have happened*. Outputs are conditional on the model and its assumptions.

## Current deployed baseline

The deployed baseline is intentionally simple: team Elo updated only from completed games strictly before the selected as-of date.

- teams begin at 1500;
- home-court advantage is 65 Elo points;
- K-factor is 20;
- future simulated results do **not** recursively update Elo inside a Monte Carlo path;
- all future games use strength frozen at the selected date;
- paired comparisons reuse the same random seed/common random numbers to reduce noise in the delta.

A more complex model is not promoted merely because it is more sophisticated. It must beat this frozen baseline on leakage-safe chronological evaluation.

## Season and postseason simulation

Each trial simulates the remaining regular season, conference ordering, play-in, best-of-seven conference playoffs, and Finals.

Known approximations:

1. Official NBA multi-step regular-season tiebreakers are not implemented yet; exact win ties use randomized resolution.
2. Postseason team strength is frozen at the selected as-of date. There is no injury, fatigue, matchup, rotation, or in-series learning layer yet.
3. Finals home court uses the better simulated regular-season record, with random resolution on a tie.
4. The playoff engine is a forecasting layer, not a roster-management or salary-cap simulator.

## Counterfactuals

### Flip a game

A completed game before the as-of date can be reversed. NBA Lab rebuilds the historical Elo state from that altered record and simulates the future using the same random stream as the real-history branch.

This answers: **"Under this model, how does the forecast distribution change if this result is reversed?"**

It does not establish causality.

### Research strength adjustment

A manual Elo adjustment is an engineering/research control. It is explicitly **not** described as adding/removing a player, making a trade, or changing a rotation.

Real player-aware scenarios are gated on a separately validated player-impact model.

## Promotion gates

Future team/player/lineup/possession models should be evaluated chronologically against this baseline with proper probabilistic metrics such as Brier score and log loss. No same-season future information may enter an as-of feature set.
