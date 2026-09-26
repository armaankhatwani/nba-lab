from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt

from .diagnostics import chronological_predictions
from .domain import Game
from .elo import EloModel, ScoreAwareEloModel


@dataclass(frozen=True)
class PredictionMetrics:
    games: int
    brier: float
    log_loss: float
    accuracy: float


@dataclass(frozen=True)
class ModelFamilyCandidate:
    family: str
    k: float
    home_advantage: float
    margin_weight: float
    train: PredictionMetrics
    validation: PredictionMetrics


@dataclass(frozen=True)
class PairedBrierDelta:
    games: int
    mean_delta: float
    standard_error: float
    lower_95: float
    upper_95: float


@dataclass(frozen=True)
class ModelFamilyEvaluation:
    train_games: int
    validation_games: int
    split_date: str
    baseline: ModelFamilyCandidate
    tuned_plain: ModelFamilyCandidate
    score_aware: ModelFamilyCandidate
    tuned_plain_vs_baseline: PairedBrierDelta
    score_aware_vs_baseline: PairedBrierDelta


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


def _date_level_split(finals: list[Game], train_fraction: float) -> tuple[int, str]:
    target = max(1, min(len(finals) - 1, int(len(finals) * train_fraction)))
    split_date = finals[target].game_date
    split = next(
        (
            index
            for index, game in enumerate(finals)
            if game.game_date >= split_date
        ),
        target,
    )
    split = max(1, min(len(finals) - 1, split))
    return split, finals[split].game_date.isoformat()


def _paired_brier_delta(
    baseline_rows: list[dict],
    candidate_rows: list[dict],
) -> PairedBrierDelta:
    if len(baseline_rows) != len(candidate_rows):
        raise ValueError("paired comparison requires equal-length predictions")
    if not baseline_rows:
        raise ValueError("paired comparison requires predictions")
    diffs = [
        (candidate["p_home"] - candidate["home_win"]) ** 2
        - (baseline["p_home"] - baseline["home_win"]) ** 2
        for baseline, candidate in zip(baseline_rows, candidate_rows)
    ]
    mean = sum(diffs) / len(diffs)
    if len(diffs) > 1:
        variance = sum((value - mean) ** 2 for value in diffs) / (len(diffs) - 1)
        se = sqrt(variance / len(diffs))
    else:
        se = 0.0
    return PairedBrierDelta(
        games=len(diffs),
        mean_delta=mean,
        standard_error=se,
        lower_95=mean - 1.96 * se,
        upper_95=mean + 1.96 * se,
    )


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

    split, split_date = _date_level_split(finals, train_fraction)
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
        split_date=split_date,
        candidates=tuple(rows),
        selected_on_train=selected,
        baseline=baseline,
    )


def evaluate_model_families(
    games: list[Game],
    k_values: tuple[float, ...] = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
    home_advantages: tuple[float, ...] = (0.0, 30.0, 50.0, 65.0, 80.0, 100.0),
    margin_weights: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0),
    train_fraction: float = 0.70,
) -> ModelFamilyEvaluation:
    finals = sorted(
        (game for game in games if game.is_final),
        key=lambda game: (game.game_date, game.game_id),
    )
    if len(finals) < 10:
        raise ValueError("model-family evaluation requires at least ten final games")
    if not 0.5 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be in [0.5, 0.9]")

    split, split_date = _date_level_split(finals, train_fraction)

    def candidate(model, family: str, margin_weight: float):
        predictions = chronological_predictions(finals, model)
        row = ModelFamilyCandidate(
            family=family,
            k=float(model.k),
            home_advantage=float(model.home_advantage),
            margin_weight=float(margin_weight),
            train=_metrics(predictions[:split]),
            validation=_metrics(predictions[split:]),
        )
        return row, predictions

    baseline, baseline_predictions = candidate(
        EloModel(k=20.0, home_advantage=65.0),
        "deployed_elo",
        0.0,
    )

    plain_rows = []
    for k in k_values:
        for home in home_advantages:
            plain_rows.append(
                candidate(
                    EloModel(k=float(k), home_advantage=float(home)),
                    "tuned_plain_elo",
                    0.0,
                )
            )
    tuned_plain, tuned_plain_predictions = min(
        plain_rows,
        key=lambda item: (
            item[0].train.brier,
            item[0].train.log_loss,
            abs(item[0].k - 20.0) + abs(item[0].home_advantage - 65.0) / 10.0,
        ),
    )

    score_rows = []
    for margin_weight in margin_weights:
        for k in k_values:
            for home in home_advantages:
                score_rows.append(
                    candidate(
                        ScoreAwareEloModel(
                            k=float(k),
                            home_advantage=float(home),
                            margin_weight=float(margin_weight),
                        ),
                        "score_aware_elo",
                        float(margin_weight),
                    )
                )
    score_aware, score_aware_predictions = min(
        score_rows,
        key=lambda item: (
            item[0].train.brier,
            item[0].train.log_loss,
            item[0].margin_weight,
            abs(item[0].k - 20.0) + abs(item[0].home_advantage - 65.0) / 10.0,
        ),
    )

    baseline_holdout = baseline_predictions[split:]
    plain_holdout = tuned_plain_predictions[split:]
    score_holdout = score_aware_predictions[split:]

    return ModelFamilyEvaluation(
        train_games=split,
        validation_games=len(finals) - split,
        split_date=split_date,
        baseline=baseline,
        tuned_plain=tuned_plain,
        score_aware=score_aware,
        tuned_plain_vs_baseline=_paired_brier_delta(
            baseline_holdout,
            plain_holdout,
        ),
        score_aware_vs_baseline=_paired_brier_delta(
            baseline_holdout,
            score_holdout,
        ),
    )
