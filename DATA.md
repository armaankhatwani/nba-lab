# NBA Lab data contract

NBA Lab uses frozen local snapshots when available and deterministic synthetic fixtures otherwise. The UI must always identify which source mode is active.

## Schedule

Canonical schedule source:

`scheduleLeagueV2`

Typical sync:

```bash
nba-lab-sync --season 2025-26
```

The normalized snapshot is expected at:

`data/scheduleLeagueV2.json`

Only final games are treated as observed results. A snapshot may contain games from the full season, but point-in-time model code ignores final scores that occur after the selected cutoff.

## Player game logs / Awards Lab

Awards Lab can load a frozen normalized player-game snapshot at:

`data/playerGameLogs.json`

If it is absent, the application uses deterministic synthetic star logs for offline testing. Synthetic logs are not NBA history.

The Awards pipeline must preserve:
- game date;
- player identity;
- team;
- minutes;
- box-score inputs used by the research score.

Point-in-time race features may use only rows available by the selected date.

## Player impact / lineup stints

Player Impact can load normalized five-man lineup stints at:

`data/impact_stints.json`

The normalized contract contains:
- player metadata;
- game id;
- possessions;
- point differential;
- exactly five unique home players;
- exactly five unique away players.

The parser rejects duplicate players, cross-team duplicate appearance within one stint, unknown player IDs, and empty snapshots.

The project includes an optional `pbpstats`-based ingestion path for possession/lineup reconstruction. Raw event data should be frozen separately from normalized stints when used for reproducible experiments.

## Game Replay

Replay snapshots are loaded from:

`data/replay/`

The replay source stores historical event/checkpoint state such as:
- game id;
- action number;
- period;
- clock;
- score;
- team;
- action description/type.

If no replay snapshot exists, deterministic synthetic score checkpoints keep the product runnable offline. Those checkpoints are clearly labeled synthetic.

## Synthetic cross-lab fixture

Offline Awards and Player Impact fixtures share several recognizable player identities (including Jalen Brunson, Jayson Tatum, Shai Gilgeous-Alexander, and Nikola Jokic) so Scenario Lab can demonstrate cross-model propagation without external data.

Their generated stats, stint outcomes, and RAPM values are synthetic. The shared names are an interface/testing device, not factual NBA estimates.

## Point-in-time rule

No model feature may use information from after the selected cutoff simply because it exists in a full-season snapshot.

That rule applies to:
- Elo fitting;
- standings / records;
- award features;
- replay pregame state;
- scenario historical branches;
- chronological model evaluation.

Tests contain explicit future-leakage and point-in-time regression checks.

## Local-data philosophy

Large live caches are not committed. Sync/freeze raw inputs locally, normalize them into small explicit contracts, and keep synthetic fixtures as deterministic fallbacks for tests and demos.
