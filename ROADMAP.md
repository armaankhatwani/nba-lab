# NBA Lab roadmap

NBA Lab is a host for basketball modeling experiments that share a point-in-time data layer. It is **not** intended to become a generic franchise-management clone.

## Product rule

Every lab should expose a computation that is difficult to fake with prose alone: simulation, reconstruction, optimization, regularized estimation, or probabilistic inference.

The common state should eventually be:

`season -> game -> possession -> stint -> lineup -> player -> context`

## Live now

### 1. Season Lab

- reconstruct a league at an as-of date;
- simulate the remaining regular season;
- play-in, playoffs, and Finals;
- branch history by reversing one completed game;
- compare paired futures with common random numbers;
- inspect win, seed, playoff, and championship deltas.

### 2. Matchup Lab

- choose two teams and an as-of date;
- freeze the model at that point;
- simulate a single game or best-of-3/5/7;
- inspect series-win, length, and score distributions.

### 3. Timeline Lab

- replay a team's rating and record game by game;
- expose individual wins/losses as checkpoints;
- keep the historical evolution visible rather than collapsing everything into a final-season number.

### 4. Model Lab

- chronological Brier score, log loss, and accuracy;
- calibration curve;
- frozen baseline assumptions;
- explicit promotion gate for more complex models.

## Next priority: Awards Lab

Reuse the existing MVP project as historical research, not as production code.

Rebuild around true point-in-time features:

1. NBA player game logs / season-to-date aggregates.
2. Team record and standings as of each date.
3. Correct award eligibility rules for the relevant season.
4. Rolling historical evaluation with no end-of-season leakage.
5. Persist daily race snapshots.
6. Compare ranking objectives vs calibrated award probabilities.
7. Connect remaining-season simulation so a player's award distribution can change with simulated future performance/team context.

The memorable interaction should be **Replay the Race**: scrub through a season and see when the model's leader changed, then simulate the remaining season from that exact date.

## Next priority: Player Impact

Public event/lineup data is current through 2025-26, while modern raw optical tracking is not broadly public. Build around possessions and stints first.

Sequence:

1. reconstruct possessions and five-man lineups;
2. validate stint boundaries and score margins;
3. ridge RAPM baseline;
4. offensive / defensive split only if it is stable enough;
5. uncertainty / shrinkage;
6. rolling or recency weighting;
7. promotion tests against simpler player/team priors.

This layer unlocks defensible player-aware counterfactuals in Season Lab.

## Then: Lineup Lab

Signature interaction: drag five players onto a court and estimate expected offense, defense, net rating, and uncertainty.

Do not report interaction/chemistry effects unless the sample-size and regularization story is defensible. Unseen lineups are a generalization problem, not a lookup table.

## Then: Game Replay

Use public play-by-play / possession data to reconstruct historical game state.

Signature interaction: choose a game and timestamp/possession, change a lineup or event, then simulate from that state forward.

This should remain a **model counterfactual**, not a causal claim that the edited event would have produced the displayed future.

## Data direction

Preferred public sources:

- NBA Stats / `nba_api` for schedules, player aggregates, lineups, and PlayByPlayV3;
- `pbpstats` where its possession and lineup reconstruction adds value;
- frozen raw snapshots for reproducibility;
- licensed or attribution-friendly mirrors only when they improve reproducibility and provenance.

Raw modern player-tracking data should not be treated as a required dependency because it is not broadly available as a current public feed.

## What not to build

- generic NBA news/chatbot/RAG;
- franchise contracts/draft/free-agency systems merely because agents can build them;
- invented player ratings without validation;
- fake precision around trades or injuries before player impact is modeled;
- deep neural models promoted without beating the frozen baseline;
- a giant stats dashboard whose outputs can be looked up elsewhere.

## Promotion philosophy

A more sophisticated model gets deployed only if it improves a declared held-out metric or unlocks a qualitatively new, validated interaction.

Engineering complexity is not evidence of model quality.
