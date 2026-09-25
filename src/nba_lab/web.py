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
from .demo import synthetic_demo_games
from .source import load_snapshot
from .simulator import simulate_remaining_season
from .teams import TEAMS

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


@app.get("/api/backtest")
def backtest():
    return asdict(chronological_backtest(GAMES))


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
