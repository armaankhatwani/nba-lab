from dataclasses import dataclass
from datetime import date

from .analysis import TeamDelta, build_team_deltas
from .domain import Game
from .simulator import SimulationResult, simulate_remaining_season


@dataclass(frozen=True)
class GameFlipComparison:
    game_id: str
    original_winner: str
    flipped_winner: str
    baseline: SimulationResult
    altered: SimulationResult
    deltas: tuple[TeamDelta, ...]


def flip_game(games: list[Game], game_id: str) -> tuple[list[Game], Game]:
    altered: list[Game] = []
    target: Game | None = None
    for game in games:
        if game.game_id != game_id:
            altered.append(game)
            continue
        if not game.is_final:
            raise ValueError("only completed games can be flipped")
        target = game
        altered.append(
            Game(
                game_id=game.game_id,
                game_date=game.game_date,
                home_team=game.home_team,
                away_team=game.away_team,
                home_score=game.away_score,
                away_score=game.home_score,
            )
        )
    if target is None:
        raise ValueError(f"unknown game id: {game_id}")
    return altered, target


def compare_game_flip(
    games: list[Game],
    game_id: str,
    as_of: date,
    trials: int = 10_000,
    seed: int = 2026,
) -> GameFlipComparison:
    altered_games, target = flip_game(games, game_id)
    if target.game_date >= as_of:
        raise ValueError("the flipped game must occur before the as-of date")
    baseline = simulate_remaining_season(games, as_of, trials=trials, seed=seed)
    altered = simulate_remaining_season(altered_games, as_of, trials=trials, seed=seed)
    deltas = build_team_deltas(baseline, altered)
    flipped = next(g for g in altered_games if g.game_id == game_id)
    return GameFlipComparison(
        game_id=game_id,
        original_winner=target.winner or "",
        flipped_winner=flipped.winner or "",
        baseline=baseline,
        altered=altered,
        deltas=deltas,
    )
