from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.replay_season import propagate_replay_to_season


def test_zero_game_probability_change_has_zero_season_ripple():
    games = synthetic_demo_games()
    game = next(g for g in games if g.game_date >= date(2026, 1, 15))
    result = propagate_replay_to_season(
        games, game.game_id, 0.55, 0.55, trials=100, seed=3
    )
    assert all(abs(row.expected_wins_delta) < 1e-12 for row in result.teams)
    assert all(abs(row.championship_probability_delta) < 1e-12 for row in result.teams)


def test_increasing_home_win_probability_helps_home_expected_wins():
    games = synthetic_demo_games()
    game = next(g for g in games if g.game_date >= date(2026, 1, 15))
    result = propagate_replay_to_season(
        games, game.game_id, 0.40, 0.70, trials=300, seed=5
    )
    by_team = {row.team: row for row in result.teams}
    assert by_team[game.home_team].expected_wins_delta > 0
    assert by_team[game.away_team].expected_wins_delta < 0
