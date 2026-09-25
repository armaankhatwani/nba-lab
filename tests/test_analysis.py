from datetime import date

from nba_lab.analysis import compare_counterfactual
from nba_lab.backtest import chronological_backtest
from nba_lab.domain import Game


def games():
    return [
        Game("1", date(2026, 1, 1), "A", "B", 110, 100),
        Game("2", date(2026, 1, 2), "B", "A", 90, 120),
        Game("3", date(2026, 1, 3), "A", "B", 100, 95),
        Game("4", date(2026, 1, 4), "B", "A", 105, 101),
        Game("5", date(2026, 1, 5), "A", "B", 102, 98),
    ]


def test_counterfactual_uses_paired_worlds_and_preserves_other_team_delta_sign():
    result = compare_counterfactual(games(), date(2026, 1, 3), {"A": 200}, trials=4000, seed=13)
    delta = {x.team: x for x in result.deltas}
    assert delta["A"].expected_wins_delta > 0
    assert delta["B"].expected_wins_delta < 0


def test_zero_adjustment_has_exact_zero_delta():
    result = compare_counterfactual(games(), date(2026, 1, 3), {}, trials=1000, seed=99)
    assert all(x.expected_wins_delta == 0 for x in result.deltas)
    assert all(x.first_seed_probability_delta == 0 for x in result.deltas)


def test_backtest_metrics_are_bounded():
    result = chronological_backtest(games())
    assert result.games == 5
    assert 0 <= result.brier <= 1
    assert result.log_loss >= 0
    assert 0 <= result.accuracy <= 1
