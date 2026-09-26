from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import random
from math import sqrt
from statistics import NormalDist, pstdev

from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class ReplayEvent:
    game_id: str
    action_number: int
    period: int
    clock_seconds: float
    home_score: int
    away_score: int
    team: str | None
    description: str
    action_type: str
    sub_type: str


@dataclass(frozen=True)
class ReplaySimulation:
    game_id: str
    action_number: int
    trials: int
    home_win_probability: float
    away_win_probability: float
    expected_final_margin: float
    p10_final_margin: float
    p50_final_margin: float
    p90_final_margin: float
    pregame_home_win_probability: float
    pregame_expected_margin: float
    historical_margin_sigma: float
    seconds_remaining: float
    home_score_delta: int
    away_score_delta: int


@dataclass(frozen=True)
class ReplayComparison:
    baseline: ReplaySimulation
    altered: ReplaySimulation
    home_win_probability_delta: float
    expected_final_margin_delta: float


@dataclass(frozen=True)
class ReplayTimelinePoint:
    event_index: int
    action_number: int
    period: int
    clock_seconds: float
    home_score: int
    away_score: int
    team: str | None
    description: str
    action_type: str
    sub_type: str
    home_win_probability: float
    probability_swing: float
    expected_final_margin: float


def total_seconds_remaining(period: int, clock_seconds: float) -> float:
    if period < 1:
        raise ValueError("period must be positive")
    if clock_seconds < 0:
        raise ValueError("clock cannot be negative")
    if period <= 4:
        return (4 - period) * 720.0 + min(clock_seconds, 720.0)
    return min(clock_seconds, 300.0)


def historical_margin_sigma(games: list[Game], as_of: date, fallback: float = 12.0) -> float:
    margins = [
        int(game.home_score) - int(game.away_score)
        for game in games
        if game.is_final and game.game_date < as_of
    ]
    if len(margins) < 20:
        return fallback
    sigma = pstdev(margins)
    return max(6.0, sigma)


def _game_by_id(games: list[Game], game_id: str) -> Game:
    try:
        return next(game for game in games if game.game_id == game_id)
    except StopIteration as exc:
        raise ValueError(f"unknown game id: {game_id}") from exc


def _pregame_state(games: list[Game], game: Game, model: EloModel):
    ratings = model.fit_as_of(games, game.game_date)
    p_home = model.win_probability(ratings[game.home_team], ratings[game.away_team])
    sigma = historical_margin_sigma(games, game.game_date)
    p = min(1 - 1e-6, max(1e-6, p_home))
    expected_margin = sigma * NormalDist().inv_cdf(p)
    return p_home, expected_margin, sigma


def _analytic_state_probability(
    event: ReplayEvent,
    pregame_margin: float,
    sigma: float,
) -> tuple[float, float]:
    current_margin = event.home_score - event.away_score
    seconds = total_seconds_remaining(event.period, event.clock_seconds)
    fraction = seconds / 2880.0
    if seconds <= 0 and current_margin == 0:
        fraction = 300.0 / 2880.0

    expected_final_margin = current_margin + pregame_margin * fraction
    residual_sigma = sigma * sqrt(max(0.0, fraction))
    if residual_sigma <= 0:
        if expected_final_margin > 0:
            probability = 1.0
        elif expected_final_margin < 0:
            probability = 0.0
        else:
            probability = 0.5
    else:
        probability = NormalDist().cdf(expected_final_margin / residual_sigma)
    return probability, expected_final_margin


def replay_probability_timeline(
    games: list[Game],
    events: tuple[ReplayEvent, ...] | list[ReplayEvent],
    model: EloModel | None = None,
) -> tuple[ReplayTimelinePoint, ...]:
    if not events:
        return ()
    model = model or EloModel()
    ordered = sorted(events, key=lambda row: row.action_number)
    game = _game_by_id(games, ordered[0].game_id)
    if any(row.game_id != game.game_id for row in ordered):
        raise ValueError("replay timeline events must belong to one game")
    _, pregame_margin, sigma = _pregame_state(games, game, model)

    rows = []
    previous_probability = None
    for index, event in enumerate(ordered):
        probability, expected_margin = _analytic_state_probability(
            event,
            pregame_margin,
            sigma,
        )
        swing = (
            0.0
            if previous_probability is None
            else probability - previous_probability
        )
        rows.append(
            ReplayTimelinePoint(
                event_index=index,
                action_number=event.action_number,
                period=event.period,
                clock_seconds=event.clock_seconds,
                home_score=event.home_score,
                away_score=event.away_score,
                team=event.team,
                description=event.description,
                action_type=event.action_type,
                sub_type=event.sub_type,
                home_win_probability=probability,
                probability_swing=swing,
                expected_final_margin=expected_margin,
            )
        )
        previous_probability = probability
    return tuple(rows)


def simulate_from_event(
    games: list[Game],
    event: ReplayEvent,
    trials: int = 10_000,
    seed: int = 2026,
    home_score_delta: int = 0,
    away_score_delta: int = 0,
    model: EloModel | None = None,
) -> ReplaySimulation:
    if trials < 1:
        raise ValueError("trials must be positive")
    model = model or EloModel()
    game = _game_by_id(games, event.game_id)
    p_home, pregame_margin, sigma = _pregame_state(games, game, model)

    current_margin = (
        event.home_score + home_score_delta
        - event.away_score - away_score_delta
    )
    seconds = total_seconds_remaining(event.period, event.clock_seconds)
    fraction = seconds / 2880.0
    if seconds <= 0 and current_margin == 0:
        fraction = 300.0 / 2880.0

    mean_future_margin = pregame_margin * fraction
    residual_sigma = sigma * sqrt(max(0.0, fraction))
    rng = random.Random(seed)

    samples = []
    home_wins = 0
    for _ in range(trials):
        final_margin = current_margin
        if residual_sigma > 0:
            final_margin += rng.gauss(mean_future_margin, residual_sigma)
        if final_margin == 0:
            final_margin = 0.001 if rng.random() < 0.5 else -0.001
        samples.append(final_margin)
        if final_margin > 0:
            home_wins += 1

    samples.sort()
    p10 = samples[int(0.10 * (trials - 1))]
    p50 = samples[int(0.50 * (trials - 1))]
    p90 = samples[int(0.90 * (trials - 1))]
    return ReplaySimulation(
        game_id=event.game_id,
        action_number=event.action_number,
        trials=trials,
        home_win_probability=home_wins / trials,
        away_win_probability=1.0 - home_wins / trials,
        expected_final_margin=sum(samples) / trials,
        p10_final_margin=p10,
        p50_final_margin=p50,
        p90_final_margin=p90,
        pregame_home_win_probability=p_home,
        pregame_expected_margin=pregame_margin,
        historical_margin_sigma=sigma,
        seconds_remaining=seconds,
        home_score_delta=home_score_delta,
        away_score_delta=away_score_delta,
    )


def compare_replay_intervention(
    games: list[Game],
    event: ReplayEvent,
    trials: int = 10_000,
    seed: int = 2026,
    home_score_delta: int = 0,
    away_score_delta: int = 0,
) -> ReplayComparison:
    baseline = simulate_from_event(games, event, trials=trials, seed=seed)
    altered = simulate_from_event(
        games,
        event,
        trials=trials,
        seed=seed,
        home_score_delta=home_score_delta,
        away_score_delta=away_score_delta,
    )
    return ReplayComparison(
        baseline=baseline,
        altered=altered,
        home_win_probability_delta=(
            altered.home_win_probability - baseline.home_win_probability
        ),
        expected_final_margin_delta=(
            altered.expected_final_margin - baseline.expected_final_margin
        ),
    )
