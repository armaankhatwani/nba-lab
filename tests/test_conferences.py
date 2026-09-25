from datetime import date

from nba_lab.domain import Game
from nba_lab.simulator import simulate_remaining_season
from nba_lab.teams import conference_for


def test_known_conferences():
    assert conference_for("NYK") == "East"
    assert conference_for("OKC") == "West"


def test_small_conference_probabilities_are_bounded():
    games = [
        Game("1", date(2026, 1, 1), "NYK", "BOS", 110, 100),
        Game("2", date(2026, 1, 2), "LAL", "GSW", 100, 105),
        Game("3", date(2026, 1, 3), "NYK", "BOS"),
        Game("4", date(2026, 1, 3), "LAL", "GSW"),
    ]
    result = simulate_remaining_season(games, date(2026, 1, 3), trials=500, seed=4)
    for team in result.teams:
        assert 0 <= team.first_seed_probability <= 1
        assert 0 <= team.top6_probability <= 1
        assert 0 <= team.playin_probability <= 1
