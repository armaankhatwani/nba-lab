from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.simulator import simulate_remaining_season


def test_full_league_postseason_probabilities_conserve_title_mass():
    games = synthetic_demo_games()
    result = simulate_remaining_season(games, date(2026, 1, 15), trials=300, seed=17)
    assert abs(sum(x.championship_probability for x in result.teams) - 1.0) < 1e-9
    for team in result.teams:
        assert 0 <= team.playoffs_probability <= 1
        assert 0 <= team.championship_probability <= team.playoffs_probability


def test_each_trial_sends_sixteen_teams_to_playoffs():
    games = synthetic_demo_games()
    result = simulate_remaining_season(games, date(2026, 1, 15), trials=200, seed=18)
    assert abs(sum(x.playoffs_probability for x in result.teams) - 16.0) < 1e-9


def test_later_round_home_court_follows_original_seed_after_upset():
    from nba_lab.simulator import _series_by_seed
    import random

    class HomeAlwaysWins:
        def win_probability(self, home_rating, away_rating):
            return 1.0

    ratings = {"A": 1500, "B": 1500}
    # B is the better original seed even though A is passed first.
    winner = _series_by_seed(
        "A",
        "B",
        {"A": 8, "B": 4},
        ratings,
        HomeAlwaysWins(),
        random.Random(1),
    )
    assert winner == "B"
