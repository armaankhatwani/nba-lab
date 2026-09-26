from nba_lab.demo import synthetic_demo_games
from nba_lab.model_selection import evaluate_elo_surface, evaluate_model_families


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


def test_parameter_surface_split_respects_whole_dates():
    result = evaluate_elo_surface(synthetic_demo_games(), train_fraction=0.70)
    assert result.train_games > 0
    assert result.validation_games > 0
    assert result.split_date


def test_model_family_selection_uses_training_slice_only():
    result = evaluate_model_families(synthetic_demo_games())
    assert result.baseline.family == "deployed_elo"
    assert result.tuned_plain.family == "tuned_plain_elo"
    assert result.score_aware.family == "score_aware_elo"
    assert result.score_aware.margin_weight > 0
    assert result.tuned_plain.train.brier <= result.baseline.train.brier + 1e-12


def test_model_family_holdout_delta_matches_validation_brier_difference():
    result = evaluate_model_families(synthetic_demo_games())
    expected = result.score_aware.validation.brier - result.baseline.validation.brier
    assert abs(
        result.score_aware_vs_baseline.mean_delta - expected
    ) < 1e-12
    assert result.score_aware_vs_baseline.games == result.validation_games
    assert (
        result.score_aware_vs_baseline.lower_95
        <= result.score_aware_vs_baseline.mean_delta
        <= result.score_aware_vs_baseline.upper_95
    )
