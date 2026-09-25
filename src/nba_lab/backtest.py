from dataclasses import dataclass
from math import log

from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class BacktestResult:
    games: int
    brier: float
    log_loss: float
    accuracy: float


def chronological_backtest(games: list[Game], model: EloModel | None = None) -> BacktestResult:
    """Evaluate strictly chronologically with no future information."""
    model = model or EloModel()
    finals = sorted((g for g in games if g.is_final), key=lambda g: (g.game_date, g.game_id))
    if not finals:
        raise ValueError("backtest requires at least one final game")

    probs: list[float] = []
    actuals: list[float] = []
    for game in finals:
        ratings = model.fit_as_of(finals, game.game_date)
        p = model.win_probability(ratings[game.home_team], ratings[game.away_team])
        y = 1.0 if game.winner == game.home_team else 0.0
        probs.append(p)
        actuals.append(y)

    eps = 1e-12
    brier = sum((p - y) ** 2 for p, y in zip(probs, actuals)) / len(probs)
    log_loss = -sum(
        y * log(max(eps, min(1 - eps, p))) + (1 - y) * log(max(eps, min(1 - eps, 1 - p)))
        for p, y in zip(probs, actuals)
    ) / len(probs)
    accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(probs, actuals)) / len(probs)
    return BacktestResult(games=len(probs), brier=brier, log_loss=log_loss, accuracy=accuracy)
