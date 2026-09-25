# Data contract

NBA Lab's canonical live/historical discovery input is the NBA `scheduleLeagueV2` feed.

Official feed:

`https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`

The open-source `nba_api` project also documents and wraps `ScheduleLeagueV2` from `stats.nba.com`.

The repository does **not** commit a large live NBA cache. Run:

```bash
nba-lab-sync --season 2025-26
```

or:

```bash
python scripts/sync_nba_schedule.py
```

Historical seasons use nba_api's season-parameterized ScheduleLeagueV2 endpoint; omitting --season uses the current NBA CDN feed. The raw/normalized response is frozen to `data/scheduleLeagueV2.json`, which is ignored by Git. NBA Lab parses game IDs, dates, team tricodes, status, and final scores. Only `gameStatus == 3` is treated as final.

If the official endpoint is unavailable, the application falls back to a clearly labeled deterministic synthetic fixture. Synthetic results must never be presented as NBA history.

## Point-in-time rule

A historical snapshot may contain the final score of a game that had not occurred at the user's selected as-of date. NBA Lab intentionally ignores that result when fitting the as-of model. The test suite contains an explicit future-leakage regression test for this contract.
