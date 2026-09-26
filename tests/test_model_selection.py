from nba_lab.demo import synthetic_demo_games
from nba_lab.model_selection import evaluate_elo_surface


def test_parameter_surface_keeps_validation_separate_from_selection():
    result = evaluate_elo_surface(synthetic_demo_games())
    assert result.train_games > 0
    assert result.validation_games > 0
    assert len(result.candidates) == 36
    assert result.baseline.k == 20
    assert result.baseline.home_advantage == 65
    best_train = min(row.train.brier for row in result.candidates)
    assert abs(result.selected_on_train.train.brier - best_train) < 1e-12


def test_parameter_surface_metrics_are_probabilistic():
    result = evaluate_elo_surface(synthetic_demo_games())
    for row in result.candidates:
        assert 0 <= row.train.brier <= 1
        assert 0 <= row.validation.brier <= 1
        assert row.train.log_loss >= 0
        assert row.validation.log_loss >= 0
        assert 0 <= row.train.accuracy <= 1
        assert 0 <= row.validation.accuracy <= 1
