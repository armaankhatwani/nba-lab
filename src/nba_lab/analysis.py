from dataclasses import dataclass
from datetime import date

from .domain import Game
from .simulator import SimulationResult, simulate_remaining_season


@dataclass(frozen=True)
class TeamDelta:
    team: str
    expected_wins_delta: float
    first_seed_probability_delta: float


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
    """Compare baseline and intervention with common random numbers.

    Using the same seed in both worlds sharply reduces Monte Carlo noise in the
    *difference*, which is what a counterfactual UI actually needs to display.
    """
    baseline = simulate_remaining_season(games, as_of, trials=trials, seed=seed)
    altered = simulate_remaining_season(
        games,
        as_of,
        trials=trials,
        seed=seed,
        rating_adjustments=rating_adjustments,
    )
    left = {x.team: x for x in baseline.teams}
    right = {x.team: x for x in altered.teams}
    deltas = tuple(
        TeamDelta(
            team=team,
            expected_wins_delta=right[team].expected_wins - left[team].expected_wins,
            first_seed_probability_delta=(
                right[team].first_seed_probability - left[team].first_seed_probability
            ),
        )
        for team in sorted(left)
    )
    return CounterfactualComparison(baseline=baseline, altered=altered, deltas=deltas)
