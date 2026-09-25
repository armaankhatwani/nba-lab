from dataclasses import asdict
from datetime import date
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analysis import compare_counterfactual
from .backtest import chronological_backtest
from .branch import compare_game_flip
from .demo import synthetic_demo_games
from .diagnostics import calibration_curve
from .matchup import simulate_matchup
from .source import load_snapshot
from .simulator import simulate_remaining_season
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
    return {
        "baseline": _serialize(result.baseline),
        "altered": _serialize(result.altered),
        "deltas": [asdict(delta) for delta in result.deltas],
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
