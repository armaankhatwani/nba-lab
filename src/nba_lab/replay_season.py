from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .domain import Game
from .simulator import simulate_remaining_season


@dataclass(frozen=True)
class ReplaySeasonTeamRipple:
    team: str
    expected_wins_delta: float
    playoffs_probability_delta: float
    championship_probability_delta: float


@dataclass(frozen=True)
class ReplaySeasonRipple:
    game_id: str
    home_team: str
    away_team: str
    home_win_probability_delta: float
    trials: int
    teams: tuple[ReplaySeasonTeamRipple, ...]


def _force_result(games: list[Game], game_id: str, winner: str) -> list[Game]:
    result = []
    found = False
    for game in games:
        if game.game_id != game_id:
            result.append(game)
            continue
        found = True
        if winner not in {game.home_team, game.away_team}:
            raise ValueError(f"{winner} is not in game {game_id}")
        if winner == game.home_team:
            home_score, away_score = 1, 0
        else:
            home_score, away_score = 0, 1
        result.append(
            Game(
                game_id=game.game_id,
                game_date=game.game_date,
                home_team=game.home_team,
                away_team=game.away_team,
                home_score=home_score,
                away_score=away_score,
            )
        )
    if not found:
        raise ValueError(f"unknown game id: {game_id}")
    return result


def propagate_replay_to_season(
    games: list[Game],
    game_id: str,
    baseline_home_win_probability: float,
    altered_home_win_probability: float,
    trials: int = 750,
    seed: int = 2026,
) -> ReplaySeasonRipple:
    game = next((g for g in games if g.game_id == game_id), None)
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    if trials < 1:
        raise ValueError("trials must be positive")

    as_of = game.game_date + timedelta(days=1)
    home_history = _force_result(games, game_id, game.home_team)
    away_history = _force_result(games, game_id, game.away_team)

    home_world = simulate_remaining_season(
        home_history, as_of, trials=trials, seed=seed
    )
    away_world = simulate_remaining_season(
        away_history, as_of, trials=trials, seed=seed
    )
    home = {row.team: row for row in home_world.teams}
    away = {row.team: row for row in away_world.teams}

    probability_delta = altered_home_win_probability - baseline_home_win_probability
    rows = []
    for team in sorted(set(home) & set(away)):
        rows.append(
            ReplaySeasonTeamRipple(
                team=team,
                expected_wins_delta=probability_delta
                * (home[team].expected_wins - away[team].expected_wins),
                playoffs_probability_delta=probability_delta
                * (home[team].playoffs_probability - away[team].playoffs_probability),
                championship_probability_delta=probability_delta
                * (
                    home[team].championship_probability
                    - away[team].championship_probability
                ),
            )
        )

    rows.sort(
        key=lambda row: (
            -abs(row.championship_probability_delta),
            -abs(row.playoffs_probability_delta),
            -abs(row.expected_wins_delta),
            row.team,
        )
    )
    return ReplaySeasonRipple(
        game_id=game_id,
        home_team=game.home_team,
        away_team=game.away_team,
        home_win_probability_delta=probability_delta,
        trials=trials,
        teams=tuple(rows),
    )
