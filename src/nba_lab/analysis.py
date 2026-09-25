from dataclasses import dataclass
from datetime import date

from .domain import Game
from .simulator import SimulationResult, simulate_remaining_season


@dataclass(frozen=True)
class TeamDelta:
    team: str
    expected_wins_delta: float
    first_seed_probability_delta: float
    top6_probability_delta: float
    playin_probability_delta: float
    playoffs_probability_delta: float
    championship_probability_delta: float


def build_team_deltas(baseline: SimulationResult, altered: SimulationResult) -> tuple[TeamDelta, ...]:
    left = {x.team: x for x in baseline.teams}
    right = {x.team: x for x in altered.teams}
    return tuple(
        TeamDelta(
            team=team,
            expected_wins_delta=right[team].expected_wins - left[team].expected_wins,
            first_seed_probability_delta=right[team].first_seed_probability - left[team].first_seed_probability,
            top6_probability_delta=right[team].top6_probability - left[team].top6_probability,
            playin_probability_delta=right[team].playin_probability - left[team].playin_probability,
            playoffs_probability_delta=right[team].playoffs_probability - left[team].playoffs_probability,
            championship_probability_delta=right[team].championship_probability - left[team].championship_probability,
        )
        for team in sorted(left)
    )


@dataclass(frozen=True)
class CounterfactualComparison:
    baseline: SimulationResult
    altered: SimulationResult
    deltas: tuple[TeamDelta, ...]


def compare_counterfactual(
    games: list[Game],
    as_of: date,
    rating_adjustments: dict[str, float],
    trials: int = 10_000,
    seed: int = 2026,
) -> CounterfactualComparison:
    """Compare baseline and intervention with common random numbers."""
    baseline = simulate_remaining_season(games, as_of, trials=trials, seed=seed)
    altered = simulate_remaining_season(
        games,
        as_of,
        trials=trials,
        seed=seed,
        rating_adjustments=rating_adjustments,
    )
    return CounterfactualComparison(
        baseline=baseline,
        altered=altered,
        deltas=build_team_deltas(baseline, altered),
    )
