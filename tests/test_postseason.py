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
