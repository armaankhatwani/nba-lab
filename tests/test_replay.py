from datetime import date, timedelta

from nba_lab.domain import Game
from nba_lab.replay import ReplayEvent, compare_replay_intervention, simulate_from_event, total_seconds_remaining


def games():
    start = date(2025, 10, 1)
    rows = []
    for i in range(30):
        d = start + timedelta(days=i)
        rows.append(Game(str(i), d, "NYK", "BOS", 105 + (i % 8), 100 + (i % 5)))
    rows.append(Game("target", date(2025, 11, 15), "NYK", "BOS", 110, 108))
    return rows


def event(period=4, clock=120, home=100, away=100):
    return ReplayEvent("target", 50, period, clock, home, away, "NYK", "checkpoint", "test", "")


def test_total_seconds_remaining_across_regulation():
    assert total_seconds_remaining(1, 720) == 2880
    assert total_seconds_remaining(2, 360) == 1800
    assert total_seconds_remaining(4, 30) == 30


def test_tipoff_probability_tracks_pregame_prior():
    result = simulate_from_event(games(), event(period=1, clock=720, home=0, away=0), trials=8000, seed=1)
    assert abs(result.home_win_probability - result.pregame_home_win_probability) < 0.03


def test_score_intervention_moves_probability_with_common_randomness():
    result = compare_replay_intervention(
        games(), event(period=4, clock=90, home=100, away=100),
        trials=5000, seed=2, home_score_delta=3
    )
    assert result.home_win_probability_delta > 0
    assert abs(result.expected_final_margin_delta - 3) < 1e-9


def test_final_buzzer_non_tie_is_deterministic():
    result = simulate_from_event(games(), event(period=4, clock=0, home=101, away=100), trials=100)
    assert result.home_win_probability == 1


def test_future_margin_adjustment_moves_only_altered_world():
    result = compare_replay_intervention(
        games(),
        event(period=4, clock=180, home=100, away=100),
        trials=4000,
        seed=19,
        future_margin_adjustment=2.5,
    )
    assert result.home_win_probability_delta > 0
    assert abs(result.expected_final_margin_delta - 2.5) < 1e-9
    assert result.baseline.future_margin_adjustment == 0
    assert result.altered.future_margin_adjustment == 2.5
