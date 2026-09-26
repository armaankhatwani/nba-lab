from __future__ import annotations

from dataclasses import dataclass
from math import log

from .diagnostics import chronological_predictions
from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class PredictionMetrics:
    games: int
    brier: float
    log_loss: float
    accuracy: float


@dataclass(frozen=True)
class EloCandidate:
    k: float
    home_advantage: float
    train: PredictionMetrics
    validation: PredictionMetrics


@dataclass(frozen=True)
class EloSurface:
    train_games: int
    validation_games: int
    split_date: str
    candidates: tuple[EloCandidate, ...]
    selected_on_train: EloCandidate
    baseline: EloCandidate


def _metrics(rows: list[dict]) -> PredictionMetrics:
    if not rows:
        raise ValueError("metrics require at least one prediction")
    eps = 1e-12
    brier = sum((row["p_home"] - row["home_win"]) ** 2 for row in rows) / len(rows)
    log_loss = -sum(
        row["home_win"] * log(max(eps, min(1 - eps, row["p_home"])))
        + (1 - row["home_win"])
        * log(max(eps, min(1 - eps, 1 - row["p_home"])))
        for row in rows
    ) / len(rows)
    accuracy = sum(
        (row["p_home"] >= 0.5) == bool(row["home_win"])
        for row in rows
    ) / len(rows)
    return PredictionMetrics(
        games=len(rows),
        brier=brier,
        log_loss=log_loss,
        accuracy=accuracy,
    )


def evaluate_elo_surface(
    games: list[Game],
    k_values: tuple[float, ...] = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
    home_advantages: tuple[float, ...] = (0.0, 30.0, 50.0, 65.0, 80.0, 100.0),
    train_fraction: float = 0.70,
) -> EloSurface:
    finals = sorted(
        (game for game in games if game.is_final),
        key=lambda game: (game.game_date, game.game_id),
    )
    if len(finals) < 10:
        raise ValueError("parameter surface requires at least ten final games")
    if not 0.5 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be in [0.5, 0.9]")
    if 20.0 not in k_values or 65.0 not in home_advantages:
        raise ValueError("surface must include the deployed K=20 / home=65 baseline")

    split = max(1, min(len(finals) - 1, int(len(finals) * train_fraction)))
    rows: list[EloCandidate] = []
    for k in k_values:
        for home in home_advantages:
            predictions = chronological_predictions(
                finals,
                EloModel(k=float(k), home_advantage=float(home)),
            )
            rows.append(
                EloCandidate(
                    k=float(k),
                    home_advantage=float(home),
                    train=_metrics(predictions[:split]),
                    validation=_metrics(predictions[split:]),
                )
            )

    selected = min(
        rows,
        key=lambda row: (
            row.train.brier,
            row.train.log_loss,
            abs(row.k - 20.0) + abs(row.home_advantage - 65.0) / 10.0,
        ),
    )
    baseline = next(
        row
        for row in rows
        if row.k == 20.0 and row.home_advantage == 65.0
    )
    return EloSurface(
        train_games=split,
        validation_games=len(finals) - split,
        split_date=finals[split].game_date.isoformat(),
        candidates=tuple(rows),
        selected_on_train=selected,
        baseline=baseline,
    )
