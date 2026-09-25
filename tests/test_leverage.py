from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.leverage import evaluate_game_leverage, rank_upcoming_games


def test_forcing_each_winner_creates_nonnegative_distribution_shifts():
    games = synthetic_demo_games()
    as_of = date(2026, 1, 15)
    game = next(g for g in games if g.game_date >= as_of)
    row = evaluate_game_leverage(games, game, as_of, trials=150, seed=5)
    assert row.title_distribution_shift >= 0
    assert row.playoff_distribution_shift >= 0
    assert row.max_expected_wins_swing > 0


def test_upcoming_games_are_ranked_and_limited():
    games = synthetic_demo_games()
    rows = rank_upcoming_games(games, date(2026, 1, 15), trials=100, seed=4, limit=5)
    assert len(rows) == 5
    assert rows[0].title_distribution_shift >= rows[-1].title_distribution_shift
