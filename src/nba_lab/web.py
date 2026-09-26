from dataclasses import asdict
from datetime import date, timedelta
from functools import lru_cache
from math import comb
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analysis import compare_counterfactual
from .awards import build_award_race
from .awards_sim import simulate_award_futures
from .awards_source import load_player_logs
from .backtest import chronological_backtest
from .branch import compare_game_flip, flip_game
from .demo import synthetic_demo_games
from .demo_awards import synthetic_player_games
from .diagnostics import calibration_curve
from .elo import EloModel
from .matchup import simulate_matchup
from .model_selection import evaluate_elo_surface
from .impact import fit_rapm
from .impact_source import load_impact_snapshot, snapshot_as_of
from .lineup import compare_lineups, optimize_lineups
from .leverage import rank_upcoming_games
from .replay import compare_replay_intervention
from .replay_source import load_replay_directory
from .replay_season import propagate_replay_to_season
from .demo_impact import synthetic_impact_snapshot
from .demo_replay import synthetic_replay_snapshots
from .source import load_snapshot
from .simulator import simulate_remaining_season
from .scenario import PlayerAbsence, TradeIntervention, build_scenario_inputs, simulate_scenario
from .teams import TEAMS
from .timeline import team_timeline

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


def _load_games():
    configured = os.environ.get("NBA_LAB_SNAPSHOT")
    candidates = [Path(configured)] if configured else [Path("data/scheduleLeagueV2.json")]
    for path in candidates:
        if path and path.exists():
            return load_snapshot(path), {"kind": "official_snapshot", "path": str(path)}
    return synthetic_demo_games(), {
        "kind": "synthetic_demo",
        "warning": "Synthetic double round-robin fallback. Run scripts/sync_nba_schedule.py for real NBA data.",
    }


GAMES, SOURCE = _load_games()


def _load_award_logs():
    configured = os.environ.get("NBA_LAB_AWARDS_SNAPSHOT")
    candidates = [Path(configured)] if configured else [Path("data/playerGameLogs.json")]
    for path in candidates:
        if path and path.exists():
            return load_player_logs(path), {"kind": "official_snapshot", "path": str(path)}
    return synthetic_player_games(GAMES), {
        "kind": "synthetic_demo",
        "warning": "Synthetic star logs for offline Awards Lab testing. Run nba-lab-sync-awards for real NBA data.",
    }


AWARD_LOGS, AWARD_SOURCE = _load_award_logs()


def _load_impact():
    configured = os.environ.get("NBA_LAB_IMPACT_SNAPSHOT")
    candidates = [Path(configured)] if configured else [Path("data/impact_stints.json")]
    for path in candidates:
        if path and path.exists():
            return load_impact_snapshot(path), {"kind": "normalized_snapshot", "path": str(path)}
    return synthetic_impact_snapshot(), {
        "kind": "synthetic_demo",
        "warning": "Synthetic RAPM stints for offline testing. Import normalized stint data for real player estimates.",
    }


IMPACT_SNAPSHOT, IMPACT_SOURCE = _load_impact()


def _load_replays():
    configured = os.environ.get("NBA_LAB_REPLAY_DIR")
    directory = Path(configured) if configured else Path("data/replay")
    snapshots = load_replay_directory(directory)
    if snapshots:
        return snapshots, {"kind": "official_snapshot", "path": str(directory)}
    return synthetic_replay_snapshots(GAMES), {
        "kind": "synthetic_demo",
        "warning": "Synthetic replay checkpoints for offline testing. Sync PlayByPlayV3 snapshots for real events.",
    }


REPLAY_SNAPSHOTS, REPLAY_SOURCE = _load_replays()


IMPACT_GAME_DATES = {game.game_id: game.game_date for game in GAMES}


@lru_cache(maxsize=64)
def _impact_snapshot_as_of(as_of: date):
    return snapshot_as_of(
        IMPACT_SNAPSHOT,
        as_of,
        game_dates=IMPACT_GAME_DATES,
        require_resolved_dates=True,
    )


@lru_cache(maxsize=64)
def _impact_result(alpha: float, as_of: date | None = None):
    snapshot = IMPACT_SNAPSHOT if as_of is None else _impact_snapshot_as_of(as_of)
    return fit_rapm(list(snapshot.stints), alpha=alpha)


@lru_cache(maxsize=256)
def _award_race(as_of: date):
    return build_award_race(GAMES, AWARD_LOGS, as_of)


app = FastAPI(title="NBA Lab", version="0.1.0")


class SimRequest(BaseModel):
    as_of: date
    trials: int = Field(default=5000, ge=100, le=50_000)
    seed: int = 2026


class CompareRequest(SimRequest):
    team: str
    elo_delta: float = Field(ge=-300, le=300)


class FlipRequest(SimRequest):
    game_id: str


class MatchupRequest(SimRequest):
    team_a: str
    team_b: str
    best_of: int = 7


class AwardSimRequest(BaseModel):
    as_of: date
    trials: int = Field(default=1000, ge=100, le=5000)
    seed: int = 2026


class LineupCompareRequest(BaseModel):
    lineup_a: list[str]
    lineup_b: list[str]
    alpha: float = Field(default=1000.0, gt=0, le=10000)
    prior_possessions: float = Field(default=300.0, gt=0, le=5000)
    as_of: date | None = None


class ReplaySimRequest(BaseModel):
    game_id: str
    action_number: int
    trials: int = Field(default=5000, ge=100, le=50000)
    seed: int = 2026
    home_score_delta: int = Field(default=0, ge=-20, le=20)
    away_score_delta: int = Field(default=0, ge=-20, le=20)


class PlayerAbsenceRequest(BaseModel):
    player_id: str
    games_missed: int = Field(ge=1, le=82)
    minutes_per_game: float = Field(default=34.0, gt=0, le=48)
    replacement_impact_per_100: float = Field(default=0.0, ge=-10, le=10)


class TradeRequest(BaseModel):
    player_a_id: str
    player_b_id: str
    minutes_per_game: float = Field(default=34.0, gt=0, le=48)


class PlayerAbsenceScenarioRequest(BaseModel):
    as_of: date
    trials: int = Field(default=5000, ge=100, le=25000)
    seed: int = 2026
    alpha: float = Field(default=1000.0, gt=0, le=10000)
    absences: list[PlayerAbsenceRequest] = Field(default_factory=list)
    flipped_game_ids: list[str] = Field(default_factory=list)
    trades: list[TradeRequest] = Field(default_factory=list)


class ScenarioMatchupRequest(PlayerAbsenceScenarioRequest):
    game_id: str


def _scenario_absences(request: PlayerAbsenceScenarioRequest):
    return [
        PlayerAbsence(
            player_id=row.player_id,
            games_missed=row.games_missed,
            minutes_per_game=row.minutes_per_game,
            replacement_impact_per_100=row.replacement_impact_per_100,
        )
        for row in request.absences
    ]


def _scenario_trades(request: PlayerAbsenceScenarioRequest):
    return [
        TradeIntervention(
            player_a_id=row.player_a_id,
            player_b_id=row.player_b_id,
            minutes_per_game=row.minutes_per_game,
        )
        for row in request.trades
    ]


def _serialize(result):
    return {
        "as_of": result.as_of.isoformat(),
        "trials": result.trials,
        "teams": [asdict(team) for team in result.teams],
    }


@app.get("/api/status")
def status():
    dates = [game.game_date for game in GAMES]
    return {
        "source": SOURCE,
        "games": len(GAMES),
        "teams": len({g.home_team for g in GAMES} | {g.away_team for g in GAMES}),
        "date_min": min(dates).isoformat(),
        "date_max": max(dates).isoformat(),
        "team_metadata": {code: asdict(info) for code, info in TEAMS.items()},
        "awards_source": AWARD_SOURCE,
        "award_logs": len(AWARD_LOGS),
        "impact_source": IMPACT_SOURCE,
        "impact_stints": len(IMPACT_SNAPSHOT.stints),
        "replay_source": REPLAY_SOURCE,
        "replay_games": len(REPLAY_SNAPSHOTS),
    }


@app.post("/api/simulate")
def simulate(request: SimRequest):
    try:
        return _serialize(
            simulate_remaining_season(GAMES, request.as_of, trials=request.trials, seed=request.seed)
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/compare")
def compare(request: CompareRequest):
    known = {g.home_team for g in GAMES} | {g.away_team for g in GAMES}
    if request.team not in known:
        raise HTTPException(422, f"Unknown team: {request.team}")
    result = compare_counterfactual(
        GAMES,
        request.as_of,
        {request.team: request.elo_delta},
        trials=request.trials,
        seed=request.seed,
    )
    return {
        "baseline": _serialize(result.baseline),
        "altered": _serialize(result.altered),
        "deltas": [asdict(delta) for delta in result.deltas],
        "intervention": {
            "team": request.team,
            "elo_delta": request.elo_delta,
            "label": "research strength adjustment",
            "warning": "This is not a player/trade effect. Player-aware interventions are a future validated layer.",
        },
    }


@app.get("/api/games")
def games(before: date, team: str | None = None, limit: int = 40):
    rows = [
        game
        for game in GAMES
        if game.is_final
        and game.game_date < before
        and (team is None or team in {game.home_team, game.away_team})
    ]
    rows.sort(key=lambda game: (game.game_date, game.game_id), reverse=True)
    return [
        {
            "game_id": game.game_id,
            "date": game.game_date.isoformat(),
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "winner": game.winner,
        }
        for game in rows[: max(1, min(limit, 100))]
    ]


@app.post("/api/flip-game")
def flip_game_result(request: FlipRequest):
    try:
        result = compare_game_flip(
            GAMES, request.game_id, request.as_of, trials=request.trials, seed=request.seed
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    target = next(game for game in GAMES if game.game_id == request.game_id)
    altered_games, _ = flip_game(GAMES, request.game_id)
    award_before = build_award_race(GAMES, AWARD_LOGS, request.as_of)
    award_after = build_award_race(altered_games, AWARD_LOGS, request.as_of)
    award_left = {candidate.player_id: candidate for candidate in award_before.candidates}
    award_right = {candidate.player_id: candidate for candidate in award_after.candidates}
    award_ripple = []
    for player_id in sorted(set(award_left) & set(award_right)):
        left, right = award_left[player_id], award_right[player_id]
        award_ripple.append({
            "player_id": player_id,
            "player_name": left.player_name,
            "team": left.team,
            "race_score_delta": right.race_score - left.race_score,
            "race_share_delta": right.race_share - left.race_share,
            "before_rank": next(i + 1 for i, candidate in enumerate(award_before.candidates) if candidate.player_id == player_id),
            "after_rank": next(i + 1 for i, candidate in enumerate(award_after.candidates) if candidate.player_id == player_id),
        })
    award_ripple.sort(key=lambda row: abs(row["race_score_delta"]), reverse=True)

    return {
        "baseline": _serialize(result.baseline),
        "altered": _serialize(result.altered),
        "deltas": [asdict(delta) for delta in result.deltas],
        "award_ripple": award_ripple[:8],
        "intervention": {
            "kind": "flip_game",
            "game_id": result.game_id,
            "date": target.game_date.isoformat(),
            "home_team": target.home_team,
            "away_team": target.away_team,
            "home_score": target.home_score,
            "away_score": target.away_score,
            "original_winner": result.original_winner,
            "flipped_winner": result.flipped_winner,
            "label": "historical result branch",
        },
    }


@app.get("/api/awards/race")
def awards_race(as_of: date, limit: int = 10):
    race = _award_race(as_of)
    return {
        "as_of": race.as_of.isoformat(),
        "award": race.award,
        "source": AWARD_SOURCE,
        "candidates": [asdict(candidate) for candidate in race.candidates[: max(1, min(limit, 25))]],
    }


@app.post("/api/awards/simulate")
def awards_simulate(request: AwardSimRequest):
    result = simulate_award_futures(
        GAMES,
        AWARD_LOGS,
        request.as_of,
        trials=request.trials,
        seed=request.seed,
    )
    return {
        "as_of": result.as_of.isoformat(),
        "trials": result.trials,
        "source": AWARD_SOURCE,
        "candidates": [asdict(candidate) for candidate in result.candidates],
        "warning": "Leader probability is the share of simulated seasons where this baseline race score finishes first; it is not a calibrated voter probability.",
    }


@app.get("/api/awards/history")
def awards_history(step_days: int = 7, limit: int = 6):
    step_days = max(1, min(step_days, 31))
    limit = max(1, min(limit, 12))
    dates = sorted({row.game_date for row in AWARD_LOGS})
    if not dates:
        return {"source": AWARD_SOURCE, "snapshots": []}
    start, end = dates[0], dates[-1]
    cursor = start
    snapshots = []
    while cursor <= end:
        race = _award_race(cursor)
        snapshots.append({
            "date": cursor.isoformat(),
            "candidates": [
                {
                    "player_id": c.player_id,
                    "player_name": c.player_name,
                    "team": c.team,
                    "race_score": c.race_score,
                    "race_share": c.race_share,
                }
                for c in race.candidates[:limit]
            ],
        })
        cursor += timedelta(days=step_days)
    if snapshots and snapshots[-1]["date"] != end.isoformat():
        race = _award_race(end)
        snapshots.append({
            "date": end.isoformat(),
            "candidates": [
                {
                    "player_id": c.player_id,
                    "player_name": c.player_name,
                    "team": c.team,
                    "race_score": c.race_score,
                    "race_share": c.race_share,
                }
                for c in race.candidates[:limit]
            ],
        })
    return {"source": AWARD_SOURCE, "snapshots": snapshots}


@app.post("/api/matchup")
def matchup(request: MatchupRequest):
    try:
        result = simulate_matchup(
            GAMES,
            request.team_a,
            request.team_b,
            request.as_of,
            trials=request.trials,
            best_of=request.best_of,
            seed=request.seed,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return asdict(result)


@app.get("/api/impact")
def impact(alpha: float = 1000.0, limit: int = 100, as_of: date | None = None):
    if alpha <= 0 or alpha > 10000:
        raise HTTPException(422, "alpha must be in (0, 10000]")
    try:
        snapshot = IMPACT_SNAPSHOT if as_of is None else _impact_snapshot_as_of(as_of)
        result = _impact_result(float(alpha), as_of)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rows = []
    for player in result.players[: max(1, min(limit, 500))]:
        meta = IMPACT_SNAPSHOT.players.get(player.player_id)
        rows.append({
            **asdict(player),
            "player_name": meta.player_name if meta else player.player_id,
            "team": meta.team if meta else "UNK",
        })
    return {
        "source": IMPACT_SOURCE,
        "alpha": result.alpha,
        "home_court_per_100": result.home_court_per_100,
        "weighted_rmse": result.weighted_rmse,
        "as_of": as_of.isoformat() if as_of else None,
        "stints": len(snapshot.stints),
        "games": len({stint.game_id for stint in snapshot.stints}),
        "qa": snapshot.qa,
        "players": rows,
        "warning": "RAPM is a regularized association estimate, not a causal player-value truth.",
    }


@app.get("/api/impact/{player_id}/path")
def impact_path(player_id: str, as_of: date | None = None):
    if player_id not in IMPACT_SNAPSHOT.players:
        raise HTTPException(404, f"Unknown impact player: {player_id}")
    points = []
    for alpha in (100.0, 300.0, 1000.0, 3000.0):
        try:
            result = _impact_result(alpha, as_of)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        row = next((player for player in result.players if player.player_id == player_id), None)
        if row is not None:
            points.append({"alpha": alpha, "impact_per_100": row.impact_per_100, "rank": row.rank})
    meta = IMPACT_SNAPSHOT.players[player_id]
    return {
        "player": asdict(meta),
        "points": points,
        "source": IMPACT_SOURCE,
        "as_of": as_of.isoformat() if as_of else None,
    }


@app.get("/api/lineup/players")
def lineup_players(alpha: float = 1000.0, as_of: date | None = None):
    try:
        result = _impact_result(float(alpha), as_of)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    impact_by_id = {row.player_id: row for row in result.players}
    rows = []
    for player_id, meta in IMPACT_SNAPSHOT.players.items():
        impact = impact_by_id.get(player_id)
        if impact is None:
            continue
        rows.append({
            "player_id": player_id,
            "player_name": meta.player_name,
            "team": meta.team,
            "impact_per_100": impact.impact_per_100,
            "possessions": impact.possessions,
            "rank": impact.rank,
        })
    rows.sort(key=lambda row: (row["team"], row["player_name"]))
    return {
        "source": IMPACT_SOURCE,
        "as_of": as_of.isoformat() if as_of else None,
        "players": rows,
    }


@app.get("/api/lineup/optimize")
def lineup_optimize(
    team: str,
    alpha: float = 1000.0,
    prior_possessions: float = 300.0,
    top_k: int = 8,
    as_of: date | None = None,
):
    if alpha <= 0 or alpha > 10000:
        raise HTTPException(422, "alpha must be in (0, 10000]")
    if prior_possessions <= 0 or prior_possessions > 5000:
        raise HTTPException(422, "prior_possessions must be in (0, 5000]")
    try:
        snapshot = (
            IMPACT_SNAPSHOT
            if as_of is None
            else _impact_snapshot_as_of(as_of)
        )
        rapm = _impact_result(float(alpha), as_of)
        available = {row.player_id for row in rapm.players}
        candidates = tuple(
            player_id
            for player_id, meta in snapshot.players.items()
            if meta.team == team and player_id in available
        )
        rows = optimize_lineups(
            snapshot,
            rapm,
            candidates,
            prior_possessions=prior_possessions,
            top_k=max(1, min(top_k, 25)),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    def serialize(row):
        return {
            **asdict(row),
            "player_meta": [
                asdict(snapshot.players[player_id])
                for player_id in row.players
            ],
        }

    return {
        "source": IMPACT_SOURCE,
        "team": team,
        "as_of": as_of.isoformat() if as_of else None,
        "alpha": alpha,
        "prior_possessions": prior_possessions,
        "candidate_players": len(candidates),
        "combinations_evaluated": (
            0
            if len(candidates) < 5
            else comb(len(candidates), 5)
        ),
        "lineups": [serialize(row) for row in rows],
        "warning": "Optimizer ranks the current snapshot roster under the RAPM-plus-observed-lineup model. It does not model roles, fatigue, matchup fit, or minute feasibility.",
    }


@app.post("/api/lineup/compare")
def lineup_compare(request: LineupCompareRequest):
    try:
        snapshot = (
            IMPACT_SNAPSHOT
            if request.as_of is None
            else _impact_snapshot_as_of(request.as_of)
        )
        result = compare_lineups(
            snapshot,
            _impact_result(float(request.alpha), request.as_of),
            tuple(request.lineup_a),
            tuple(request.lineup_b),
            prior_possessions=request.prior_possessions,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    def serialize_lineup(lineup):
        return {
            **asdict(lineup),
            "player_meta": [asdict(IMPACT_SNAPSHOT.players[player_id]) for player_id in lineup.players],
        }

    return {
        "source": IMPACT_SOURCE,
        "as_of": request.as_of.isoformat() if request.as_of else None,
        "alpha": request.alpha,
        "prior_possessions": request.prior_possessions,
        "lineup_a": serialize_lineup(result.lineup_a),
        "lineup_b": serialize_lineup(result.lineup_b),
        "neutral_margin_per_100": result.neutral_margin_per_100,
        "warning": "Lineup estimates are regularized model expectations, not observed causal effects.",
    }


@app.get("/api/leverage")
def leverage(as_of: date, trials: int = 500, limit: int = 10):
    trials = max(100, min(trials, 5000))
    limit = max(1, min(limit, 20))
    rows = rank_upcoming_games(GAMES, as_of, trials=trials, seed=2026, limit=limit)
    return {
        "as_of": as_of.isoformat(),
        "trials_per_world": trials,
        "games": [asdict(row) for row in rows],
        "definition": "For each game, force each possible winner in paired season simulations and measure the resulting league-wide distribution shift.",
    }


@app.get("/api/replay/games")
def replay_games():
    game_by_id = {game.game_id: game for game in GAMES}
    rows = []
    for game_id, snapshot in REPLAY_SNAPSHOTS.items():
        game = game_by_id.get(game_id)
        if game is None:
            continue
        rows.append({
            "game_id": game_id,
            "date": game.game_date.isoformat(),
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "events": len(snapshot.events),
            "source": snapshot.source,
        })
    rows.sort(key=lambda row: (row["date"], row["game_id"]), reverse=True)
    return {"source": REPLAY_SOURCE, "games": rows}


@app.get("/api/replay/{game_id}")
def replay_events(game_id: str):
    snapshot = REPLAY_SNAPSHOTS.get(game_id)
    if snapshot is None:
        raise HTTPException(404, f"No replay snapshot for game: {game_id}")
    game = next((game for game in GAMES if game.game_id == game_id), None)
    if game is None:
        raise HTTPException(404, f"Unknown scheduled game: {game_id}")
    return {
        "source": REPLAY_SOURCE,
        "game": {
            "game_id": game.game_id,
            "date": game.game_date.isoformat(),
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_score": game.home_score,
            "away_score": game.away_score,
        },
        "events": [asdict(event) for event in snapshot.events],
    }


@app.post("/api/replay/simulate")
def replay_simulate(request: ReplaySimRequest):
    snapshot = REPLAY_SNAPSHOTS.get(request.game_id)
    if snapshot is None:
        raise HTTPException(404, f"No replay snapshot for game: {request.game_id}")
    event = next(
        (event for event in snapshot.events if event.action_number == request.action_number),
        None,
    )
    if event is None:
        raise HTTPException(404, f"Unknown replay action: {request.action_number}")
    try:
        result = compare_replay_intervention(
            GAMES,
            event,
            trials=request.trials,
            seed=request.seed,
            home_score_delta=request.home_score_delta,
            away_score_delta=request.away_score_delta,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    game = next(game for game in GAMES if game.game_id == request.game_id)
    season_ripple = propagate_replay_to_season(
        GAMES,
        request.game_id,
        result.baseline.home_win_probability,
        result.altered.home_win_probability,
        trials=min(1000, request.trials),
        seed=request.seed,
    )
    return {
        "source": REPLAY_SOURCE,
        "game": {
            "game_id": game.game_id,
            "date": game.game_date.isoformat(),
            "home_team": game.home_team,
            "away_team": game.away_team,
        },
        "event": asdict(event),
        "baseline": asdict(result.baseline),
        "altered": asdict(result.altered),
        "home_win_probability_delta": result.home_win_probability_delta,
        "expected_final_margin_delta": result.expected_final_margin_delta,
        "season_ripple": {
            "trials": season_ripple.trials,
            "home_win_probability_delta": season_ripple.home_win_probability_delta,
            "teams": [asdict(row) for row in season_ripple.teams[:10]],
        },
        "warning": "This is a game-state counterfactual baseline, not a possession-level causal model.",
    }


@app.post("/api/scenario/player-absence")
def player_absence_scenario(request: PlayerAbsenceScenarioRequest):
    if not request.absences and not request.flipped_game_ids and not request.trades:
        raise HTTPException(422, "scenario requires at least one intervention")
    try:
        result = simulate_scenario(
            GAMES,
            request.as_of,
            IMPACT_SNAPSHOT,
            _impact_result(float(request.alpha), request.as_of),
            _scenario_absences(request),
            flipped_game_ids=request.flipped_game_ids,
            trades=_scenario_trades(request),
            trials=request.trials,
            seed=request.seed,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    altered_history = list(GAMES)
    for game_id in request.flipped_game_ids:
        altered_history, _ = flip_game(altered_history, game_id)
    award_before = build_award_race(GAMES, AWARD_LOGS, request.as_of)
    award_after = build_award_race(altered_history, AWARD_LOGS, request.as_of)
    left = {row.player_id: row for row in award_before.candidates}
    right = {row.player_id: row for row in award_after.candidates}
    award_ripple = []
    for player_id in sorted(set(left) & set(right)):
        before, after = left[player_id], right[player_id]
        award_ripple.append({
            "player_id": player_id,
            "player_name": before.player_name,
            "team": before.team,
            "race_score_delta": after.race_score - before.race_score,
            "race_share_delta": after.race_share - before.race_share,
        })
    award_ripple.sort(key=lambda row: abs(row["race_score_delta"]), reverse=True)

    model = EloModel()
    ratings = model.fit_as_of(altered_history, request.as_of)
    game_by_id = {game.game_id: game for game in GAMES}
    affected_games = []
    for game_id, adjustments in result.game_rating_adjustments.items():
        game = game_by_id.get(game_id)
        if game is None:
            continue
        home_delta = adjustments.get(game.home_team, 0.0)
        away_delta = adjustments.get(game.away_team, 0.0)
        base_home = model.win_probability(
            ratings[game.home_team],
            ratings[game.away_team],
        )
        altered_home = model.win_probability(
            ratings[game.home_team] + home_delta,
            ratings[game.away_team] + away_delta,
        )
        affected_games.append({
            "game_id": game.game_id,
            "date": game.game_date.isoformat(),
            "home_team": game.home_team,
            "away_team": game.away_team,
            "home_elo_delta": home_delta,
            "away_elo_delta": away_delta,
            "baseline_home_win_probability": base_home,
            "altered_home_win_probability": altered_home,
            "home_win_probability_delta": altered_home - base_home,
        })
    affected_games.sort(key=lambda row: (row["date"], row["game_id"]))

    return {
        "as_of": request.as_of.isoformat(),
        "trials": request.trials,
        "alpha": request.alpha,
        "source": IMPACT_SOURCE,
        "baseline": _serialize(result.baseline),
        "altered": _serialize(result.altered),
        "deltas": [asdict(row) for row in result.deltas],
        "player_absences": [asdict(row) for row in result.player_absences],
        "historical_flips": [asdict(row) for row in result.historical_flips],
        "trades": [asdict(row) for row in result.trades],
        "affected_games": affected_games,
        "award_ripple": award_ripple[:8],
        "warning": "Player absences use RAPM as an association-based strength prior, assume a stated replacement level, and affect only the next scheduled regular-season games. Historical flips rebuild point-in-time team and award context.",
    }


@app.post("/api/scenario/matchup")
def scenario_matchup(request: ScenarioMatchupRequest):
    if not request.absences and not request.flipped_game_ids and not request.trades:
        raise HTTPException(422, "scenario requires at least one intervention")
    game = next((row for row in GAMES if row.game_id == request.game_id), None)
    if game is None:
        raise HTTPException(404, f"Unknown scheduled game: {request.game_id}")
    if game.game_date < request.as_of:
        raise HTTPException(422, "scenario matchup must be on or after the as-of date")
    try:
        inputs = build_scenario_inputs(
            GAMES,
            request.as_of,
            IMPACT_SNAPSHOT,
            _impact_result(float(request.alpha), request.as_of),
            _scenario_absences(request),
            flipped_game_ids=request.flipped_game_ids,
            trades=_scenario_trades(request),
        )
        baseline = simulate_matchup(
            list(inputs.altered_games),
            game.home_team,
            game.away_team,
            request.as_of,
            trials=request.trials,
            best_of=1,
            seed=request.seed,
        )
        adjustments = inputs.game_rating_adjustments.get(game.game_id, {})
        altered = simulate_matchup(
            list(inputs.altered_games),
            game.home_team,
            game.away_team,
            request.as_of,
            trials=request.trials,
            best_of=1,
            seed=request.seed,
            rating_adjustments=adjustments,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    return {
        "game": {
            "game_id": game.game_id,
            "date": game.game_date.isoformat(),
            "home_team": game.home_team,
            "away_team": game.away_team,
        },
        "rating_adjustments": adjustments,
        "baseline": asdict(baseline),
        "scenario": asdict(altered),
        "home_win_probability_delta": (
            altered.team_a_series_probability - baseline.team_a_series_probability
        ),
        "warning": "The scenario adjustment changes the frozen pregame team-strength prior for this scheduled game; it is not a causal player-on/off game prediction.",
    }


@app.post("/api/scenario/sensitivity")
def scenario_sensitivity(request: PlayerAbsenceScenarioRequest, sensitivity_trials: int = 750):
    if not request.absences and not request.flipped_game_ids and not request.trades:
        raise HTTPException(422, "scenario requires at least one intervention")
    sensitivity_trials = max(100, min(sensitivity_trials, 5000))
    try:
        inputs = build_scenario_inputs(
            GAMES,
            request.as_of,
            IMPACT_SNAPSHOT,
            _impact_result(float(request.alpha), request.as_of),
            _scenario_absences(request),
            flipped_game_ids=request.flipped_game_ids,
            trades=_scenario_trades(request),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    altered_games = list(inputs.altered_games)
    baseline = simulate_remaining_season(
        GAMES,
        request.as_of,
        trials=sensitivity_trials,
        seed=request.seed,
    )
    point = simulate_remaining_season(
        altered_games,
        request.as_of,
        trials=sensitivity_trials,
        seed=request.seed,
        game_rating_adjustments=inputs.game_rating_adjustments,
    )
    impact_lower = simulate_remaining_season(
        altered_games,
        request.as_of,
        trials=sensitivity_trials,
        seed=request.seed,
        game_rating_adjustments=inputs.impact_lower_adjustments,
    )
    impact_upper = simulate_remaining_season(
        altered_games,
        request.as_of,
        trials=sensitivity_trials,
        seed=request.seed,
        game_rating_adjustments=inputs.impact_upper_adjustments,
    )
    baseline_by = {row.team: row for row in baseline.teams}
    point_by = {row.team: row for row in point.teams}
    low_by = {row.team: row for row in impact_lower.teams}
    high_by = {row.team: row for row in impact_upper.teams}

    def stable_direction(values: list[float], tolerance: float = 1e-12) -> bool:
        signs = {
            1 if value > tolerance else -1
            for value in values
            if abs(value) > tolerance
        }
        return len(signs) <= 1

    team_sensitivity = []
    for team in sorted(point_by):
        base = baseline_by[team]
        variants = [low_by[team], point_by[team], high_by[team]]
        wins = [row.expected_wins - base.expected_wins for row in variants]
        playoffs = [
            row.playoffs_probability - base.playoffs_probability
            for row in variants
        ]
        titles = [
            row.championship_probability - base.championship_probability
            for row in variants
        ]
        team_sensitivity.append({
            "team": team,
            "expected_wins_deltas": wins,
            "playoffs_probability_deltas": playoffs,
            "championship_probability_deltas": titles,
            "expected_wins_direction_stable": stable_direction(wins),
            "playoffs_direction_stable": stable_direction(playoffs),
            "championship_direction_stable": stable_direction(titles),
            "expected_wins_range": [min(wins), max(wins)],
            "playoffs_probability_range": [min(playoffs), max(playoffs)],
            "championship_probability_range": [min(titles), max(titles)],
        })
    team_sensitivity.sort(
        key=lambda row: (
            abs(row["expected_wins_deltas"][1])
            + 8 * abs(row["championship_probability_deltas"][1])
        ),
        reverse=True,
    )

    return {
        "as_of": request.as_of.isoformat(),
        "trials": sensitivity_trials,
        "baseline": _serialize(baseline),
        "point": _serialize(point),
        "impact_lower": _serialize(impact_lower),
        "impact_upper": _serialize(impact_upper),
        "team_sensitivity": team_sensitivity,
        "definition": "Sensitivity worlds move every player-impact intervention to its approximate lower or upper model-based signal while preserving the same history branch and Monte Carlo seed.",
        "warning": "These are componentwise model-sensitivity worlds, not confidence intervals on season outcomes.",
    }


@app.post("/api/scenario/lineups")
def scenario_lineups(
    request: PlayerAbsenceScenarioRequest,
    top_k: int = 4,
    prior_possessions: float = 300.0,
):
    if not request.absences and not request.trades:
        raise HTTPException(
            422,
            "scenario lineup comparison requires a player absence or trade",
        )
    top_k = max(1, min(top_k, 10))
    if prior_possessions <= 0 or prior_possessions > 5000:
        raise HTTPException(422, "prior_possessions must be in (0, 5000]")
    try:
        snapshot = _impact_snapshot_as_of(request.as_of)
        rapm = _impact_result(float(request.alpha), request.as_of)
        inputs = build_scenario_inputs(
            GAMES,
            request.as_of,
            IMPACT_SNAPSHOT,
            rapm,
            _scenario_absences(request),
            flipped_game_ids=request.flipped_game_ids,
            trades=_scenario_trades(request),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    available = {row.player_id for row in rapm.players}
    baseline_team = {
        player_id: meta.team
        for player_id, meta in snapshot.players.items()
        if player_id in available
    }
    scenario_team = dict(baseline_team)
    affected_teams: set[str] = set()

    for trade in inputs.trades:
        scenario_team[trade.player_a_id] = trade.team_b
        scenario_team[trade.player_b_id] = trade.team_a
        affected_teams.update((trade.team_a, trade.team_b))

    absent_ids = {row.player_id for row in inputs.player_absences}
    for absence in inputs.player_absences:
        affected_teams.add(absence.team)

    def serialize_lineup(row, team_map):
        return {
            **asdict(row),
            "player_meta": [
                {
                    **asdict(snapshot.players[player_id]),
                    "scenario_team": team_map[player_id],
                }
                for player_id in row.players
            ],
        }

    rows = []
    for team in sorted(affected_teams):
        base_candidates = tuple(
            player_id
            for player_id, player_team in baseline_team.items()
            if player_team == team
        )
        scenario_candidates = tuple(
            player_id
            for player_id, player_team in scenario_team.items()
            if player_team == team and player_id not in absent_ids
        )
        try:
            baseline_rows = optimize_lineups(
                snapshot,
                rapm,
                base_candidates,
                prior_possessions=prior_possessions,
                top_k=top_k,
            )
            scenario_rows = optimize_lineups(
                snapshot,
                rapm,
                scenario_candidates,
                prior_possessions=prior_possessions,
                top_k=top_k,
            )
        except ValueError as exc:
            raise HTTPException(
                422,
                f"{team}: {exc}",
            ) from exc

        base_top = baseline_rows[0] if baseline_rows else None
        scenario_top = scenario_rows[0] if scenario_rows else None
        rows.append({
            "team": team,
            "baseline_candidate_players": len(base_candidates),
            "scenario_candidate_players": len(scenario_candidates),
            "baseline_top_score": (
                base_top.blended_net_rating if base_top else None
            ),
            "scenario_top_score": (
                scenario_top.blended_net_rating if scenario_top else None
            ),
            "top_score_delta": (
                scenario_top.blended_net_rating - base_top.blended_net_rating
                if base_top is not None and scenario_top is not None
                else None
            ),
            "baseline_lineups": [
                serialize_lineup(row, baseline_team)
                for row in baseline_rows
            ],
            "scenario_lineups": [
                serialize_lineup(row, scenario_team)
                for row in scenario_rows
            ],
        })

    return {
        "as_of": request.as_of.isoformat(),
        "alpha": request.alpha,
        "prior_possessions": prior_possessions,
        "teams": rows,
        "warning": "Post-trade lineups containing newly acquired players are generally unseen combinations and therefore lean on the additive RAPM prior. The optimizer does not model positional fit, role changes, fatigue, or minute feasibility.",
    }


@app.post("/api/scenario/awards")
def scenario_awards(request: PlayerAbsenceScenarioRequest, award_trials: int = 750):
    if not request.absences and not request.flipped_game_ids and not request.trades:
        raise HTTPException(422, "scenario requires at least one intervention")
    award_trials = max(100, min(award_trials, 5000))
    try:
        inputs = build_scenario_inputs(
            GAMES,
            request.as_of,
            IMPACT_SNAPSHOT,
            _impact_result(float(request.alpha), request.as_of),
            _scenario_absences(request),
            flipped_game_ids=request.flipped_game_ids,
            trades=_scenario_trades(request),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    unavailable = {
        effect.player_id: set(effect.affected_game_ids)
        for effect in inputs.player_absences
    }
    team_overrides = {}
    for trade in inputs.trades:
        team_overrides[trade.player_a_id] = trade.team_b
        team_overrides[trade.player_b_id] = trade.team_a

    baseline = simulate_award_futures(
        GAMES,
        AWARD_LOGS,
        request.as_of,
        trials=award_trials,
        seed=request.seed,
    )
    altered = simulate_award_futures(
        list(inputs.altered_games),
        AWARD_LOGS,
        request.as_of,
        trials=award_trials,
        seed=request.seed,
        game_rating_adjustments=inputs.game_rating_adjustments,
        player_unavailable_game_ids=unavailable,
        player_team_overrides=team_overrides,
    )

    before = {row.player_id: row for row in baseline.candidates}
    after = {row.player_id: row for row in altered.candidates}
    rows = []
    for player_id in sorted(set(before) | set(after)):
        left = before.get(player_id)
        right = after.get(player_id)
        if left is None and right is None:
            continue
        rows.append({
            "player_id": player_id,
            "player_name": (right or left).player_name,
            "baseline_team": left.team if left else None,
            "altered_team": right.team if right else None,
            "baseline_leader_probability": left.leader_probability if left else 0.0,
            "altered_leader_probability": right.leader_probability if right else 0.0,
            "leader_probability_delta": (
                (right.leader_probability if right else 0.0)
                - (left.leader_probability if left else 0.0)
            ),
            "baseline_top3_probability": left.top3_probability if left else 0.0,
            "altered_top3_probability": right.top3_probability if right else 0.0,
            "mean_final_score_delta": (
                (right.mean_final_score if right else 0.0)
                - (left.mean_final_score if left else 0.0)
            ),
        })
    rows.sort(key=lambda row: abs(row["leader_probability_delta"]), reverse=True)
    return {
        "as_of": request.as_of.isoformat(),
        "award_trials": award_trials,
        "baseline": [asdict(row) for row in baseline.candidates],
        "altered": [asdict(row) for row in altered.candidates],
        "deltas": rows,
        "warning": "Award finishing shares are model leaderboard frequencies under bootstrapped player game lines, not calibrated voter probabilities.",
    }


@app.get("/api/timeline/{team}")
def timeline(team: str):
    if team not in TEAMS:
        raise HTTPException(404, f"Unknown team: {team}")
    points = team_timeline(GAMES, team)
    if not points:
        raise HTTPException(404, f"No completed games found for {team}")
    return {
        "team": asdict(TEAMS[team]),
        "points": [asdict(point) for point in points],
        "summary": {
            "games": len(points),
            "wins": points[-1].wins,
            "losses": points[-1].losses,
            "current_rating": points[-1].rating,
            "peak_rating": max(point.rating for point in points),
            "low_rating": min(point.rating for point in points),
            "largest_win": max((point.margin for point in points), default=0),
            "largest_loss": min((point.margin for point in points), default=0),
        },
    }


@app.get("/api/model/elo-surface")
def model_elo_surface():
    result = evaluate_elo_surface(GAMES)
    return {
        "train_games": result.train_games,
        "validation_games": result.validation_games,
        "split_date": result.split_date,
        "selected_on_train": {
            "k": result.selected_on_train.k,
            "home_advantage": result.selected_on_train.home_advantage,
            "train": asdict(result.selected_on_train.train),
            "validation": asdict(result.selected_on_train.validation),
        },
        "baseline": {
            "k": result.baseline.k,
            "home_advantage": result.baseline.home_advantage,
            "train": asdict(result.baseline.train),
            "validation": asdict(result.baseline.validation),
        },
        "candidates": [
            {
                "k": row.k,
                "home_advantage": row.home_advantage,
                "train": asdict(row.train),
                "validation": asdict(row.validation),
            }
            for row in result.candidates
        ],
        "warning": "The grid is selected only on the earlier chronological slice and evaluated on the later holdout. A single holdout improvement is evidence for further testing, not automatic model promotion.",
    }


@app.get("/api/diagnostics")
def diagnostics():
    metrics = asdict(chronological_backtest(GAMES))
    curve = [asdict(bin_) for bin_ in calibration_curve(GAMES, bins=10)]
    return {
        "metrics": metrics,
        "calibration": curve,
        "model": {
            "name": "Frozen Elo baseline",
            "base": 1500,
            "k": 20,
            "home_advantage": 65,
            "promotion_rule": "More complex models must beat this baseline chronologically before promotion.",
        },
    }


@app.get("/api/backtest")
def backtest():
    return asdict(chronological_backtest(GAMES))


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
