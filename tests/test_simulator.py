from datetime import date

from nba_lab.domain import Game
from nba_lab.elo import EloModel
from nba_lab.simulator import simulate_remaining_season


def sample_games():
    return [
        Game("1", date(2026, 1, 1), "A", "B", 110, 100),
        Game("2", date(2026, 1, 2), "B", "A", 90, 120),
        Game("3", date(2026, 1, 3), "A", "B", 80, 130),
        Game("4", date(2026, 1, 4), "A", "B", 99, 101),
    ]


def test_future_finals_do_not_leak_into_as_of_rating():
    model = EloModel()
    games = sample_games()
    with_future_scores = model.fit_as_of(games, date(2026, 1, 3))
    stripped = [games[0], games[1], Game("3", date(2026, 1, 3), "A", "B"), Game("4", date(2026, 1, 4), "A", "B")]
    without_future_scores = model.fit_as_of(stripped, date(2026, 1, 3))
    assert with_future_scores == without_future_scores


def test_simulation_is_reproducible():
    a = simulate_remaining_season(sample_games(), date(2026, 1, 3), trials=1000, seed=7)
    b = simulate_remaining_season(sample_games(), date(2026, 1, 3), trials=1000, seed=7)
    assert a == b


def test_strength_adjustment_changes_expected_wins():
    base = simulate_remaining_season(sample_games(), date(2026, 1, 3), trials=5000, seed=11)
    altered = simulate_remaining_season(sample_games(), date(2026, 1, 3), trials=5000, seed=11, rating_adjustments={"A": 150})
    b = {x.team: x for x in base.teams}
    a = {x.team: x for x in altered.teams}
    assert a["A"].expected_wins > b["A"].expected_wins


def test_first_seed_probabilities_sum_to_one():
    result = simulate_remaining_season(sample_games(), date(2026, 1, 3), trials=2000, seed=5)
    assert abs(sum(x.first_seed_probability for x in result.teams) - 1.0) < 1e-9
