from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .domain import Game
from .simulator import simulate_remaining_season


@dataclass(frozen=True)
class GameLeverage:
    game_id: str
    game_date: date
    home_team: str
    away_team: str
    title_distribution_shift: float
    playoff_distribution_shift: float
    max_expected_wins_swing: float
    biggest_title_swing_team: str | None
    biggest_title_swing: float


def _team_map(result):
    return {row.team: row for row in result.teams}


def evaluate_game_leverage(
    games: list[Game],
    game: Game,
    as_of: date,
    trials: int = 1000,
    seed: int = 2026,
    rating_adjustments: dict[str, float] | None = None,
    game_rating_adjustments: dict[str, dict[str, float]] | None = None,
    forced_winners: dict[str, str] | None = None,
) -> GameLeverage:
    if game.game_date < as_of:
        raise ValueError("leverage game must be on or after the as-of date")

    existing_forced = dict(forced_winners or {})
    home_forced = {**existing_forced, game.game_id: game.home_team}
    away_forced = {**existing_forced, game.game_id: game.away_team}

    home_world = simulate_remaining_season(
        games,
        as_of,
        trials=trials,
        seed=seed,
        rating_adjustments=rating_adjustments,
        game_rating_adjustments=game_rating_adjustments,
        forced_winners=home_forced,
    )
    away_world = simulate_remaining_season(
        games,
        as_of,
        trials=trials,
        seed=seed,
        rating_adjustments=rating_adjustments,
        game_rating_adjustments=game_rating_adjustments,
        forced_winners=away_forced,
    )
    home = _team_map(home_world)
    away = _team_map(away_world)
    teams = sorted(set(home) & set(away))

    title_deltas = {
        team: home[team].championship_probability - away[team].championship_probability
        for team in teams
    }
    playoff_deltas = {
        team: home[team].playoffs_probability - away[team].playoffs_probability
        for team in teams
    }
    win_deltas = {
        team: home[team].expected_wins - away[team].expected_wins
        for team in teams
    }

    biggest_team = None
    biggest_value = 0.0
    if title_deltas:
        biggest_team = max(title_deltas, key=lambda team: abs(title_deltas[team]))
        biggest_value = title_deltas[biggest_team]

    return GameLeverage(
        game_id=game.game_id,
        game_date=game.game_date,
        home_team=game.home_team,
        away_team=game.away_team,
        title_distribution_shift=0.5 * sum(abs(value) for value in title_deltas.values()),
        playoff_distribution_shift=0.5 * sum(abs(value) for value in playoff_deltas.values()),
        max_expected_wins_swing=max((abs(value) for value in win_deltas.values()), default=0.0),
        biggest_title_swing_team=biggest_team,
        biggest_title_swing=biggest_value,
    )


def rank_upcoming_games(
    games: list[Game],
    as_of: date,
    trials: int = 1000,
    seed: int = 2026,
    limit: int = 12,
    rating_adjustments: dict[str, float] | None = None,
    game_rating_adjustments: dict[str, dict[str, float]] | None = None,
    excluded_game_ids: set[str] | None = None,
    forced_winners: dict[str, str] | None = None,
) -> tuple[GameLeverage, ...]:
    excluded = excluded_game_ids or set()
    upcoming = sorted(
        (
            game
            for game in games
            if game.game_date >= as_of and game.game_id not in excluded
        ),
        key=lambda game: (game.game_date, game.game_id),
    )[: max(1, limit)]
    rows = [
        evaluate_game_leverage(
            games,
            game,
            as_of,
            trials=trials,
            seed=seed,
            rating_adjustments=rating_adjustments,
            game_rating_adjustments=game_rating_adjustments,
            forced_winners=forced_winners,
        )
        for game in upcoming
    ]
    rows.sort(
        key=lambda row: (
            -row.title_distribution_shift,
            -row.playoff_distribution_shift,
            row.game_date,
            row.game_id,
        )
    )
    return tuple(rows)
