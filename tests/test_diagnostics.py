from datetime import date

from nba_lab.diagnostics import chronological_predictions
from nba_lab.domain import Game
from nba_lab.elo import EloModel, ScoreAwareEloModel


def test_same_day_games_do_not_leak_into_each_other():
    games = [
        Game("1", date(2026, 1, 1), "A", "B", 120, 90),
        Game("2", date(2026, 1, 1), "A", "C", 100, 99),
    ]
    rows = chronological_predictions(games, EloModel(home_advantage=0))
    assert len(rows) == 2
    assert abs(rows[0]["p_home"] - 0.5) < 1e-12
    assert abs(rows[1]["p_home"] - 0.5) < 1e-12


def test_score_aware_elo_changes_update_size_not_probability_formula():
    game = Game("1", date(2026, 1, 1), "A", "B", 130, 100)
    plain = EloModel(k=20, home_advantage=65)
    score = ScoreAwareEloModel(k=20, home_advantage=65, margin_weight=0.5)

    p_plain = plain.win_probability(1500, 1500)
    p_score = score.win_probability(1500, 1500)
    assert abs(p_plain - p_score) < 1e-12

    plain_delta = plain.rating_delta(game, 1500, 1500, p_plain, 1.0)
    score_delta = score.rating_delta(game, 1500, 1500, p_score, 1.0)
    assert score_delta > plain_delta


def test_zero_margin_weight_reduces_to_plain_elo_updates():
    game = Game("1", date(2026, 1, 1), "A", "B", 130, 100)
    plain = EloModel(k=20, home_advantage=65)
    score = ScoreAwareEloModel(
        k=20,
        home_advantage=65,
        margin_weight=0,
    )
    p = plain.win_probability(1500, 1500)
    assert abs(
        plain.rating_delta(game, 1500, 1500, p, 1.0)
        - score.rating_delta(game, 1500, 1500, p, 1.0)
    ) < 1e-12
