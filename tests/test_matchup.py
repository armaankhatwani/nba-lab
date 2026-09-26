from datetime import date

import pytest

from nba_lab.domain import Game
from nba_lab.matchup import simulate_matchup


def games():
    return [
        Game("1", date(2026, 1, 1), "NYK", "BOS", 120, 100),
        Game("2", date(2026, 1, 2), "NYK", "BOS", 115, 101),
        Game("3", date(2026, 1, 3), "BOS", "NYK", 98, 112),
        Game("4", date(2026, 1, 4), "BOS", "NYK", 100, 99),
    ]


def test_stronger_team_wins_series_more_often():
    result = simulate_matchup(games(), "NYK", "BOS", date(2026, 1, 5), trials=5000, best_of=7, seed=1)
    assert result.team_a_rating > result.team_b_rating
    assert result.team_a_series_probability > .5
    assert abs(result.team_a_series_probability + result.team_b_series_probability - 1) < 1e-12
    assert 4 <= result.expected_games <= 7


def test_single_game_has_length_one():
    result = simulate_matchup(games(), "NYK", "BOS", date(2026, 1, 5), trials=500, best_of=1, seed=2)
    assert result.expected_games == 1
    assert result.length_distribution == {1: 1.0}


def test_same_team_rejected():
    with pytest.raises(ValueError):
        simulate_matchup(games(), "NYK", "NYK", date(2026, 1, 5))


def test_positive_rating_adjustment_increases_matchup_probability():
    games=synthetic_demo_games()
    baseline=simulate_matchup(
        games,'BOS','NYK',date(2026,1,15),trials=1200,best_of=1,seed=55
    )
    boosted=simulate_matchup(
        games,'BOS','NYK',date(2026,1,15),trials=1200,best_of=1,seed=55,
        rating_adjustments={'BOS':100.0},
    )
    assert boosted.team_a_rating == baseline.team_a_rating + 100.0
    assert boosted.team_a_series_probability > baseline.team_a_series_probability
