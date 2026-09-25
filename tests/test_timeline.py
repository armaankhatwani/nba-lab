from datetime import date

from nba_lab.domain import Game
from nba_lab.timeline import team_timeline
from nba_lab.diagnostics import calibration_curve, chronological_predictions


def games():
    return [
        Game("1", date(2026, 1, 1), "NYK", "BOS", 110, 100),
        Game("2", date(2026, 1, 2), "BOS", "NYK", 101, 103),
        Game("3", date(2026, 1, 3), "LAL", "GSW", 99, 100),
        Game("4", date(2026, 1, 4), "NYK", "LAL", 95, 105),
    ]


def test_team_timeline_tracks_record_and_rating():
    points = team_timeline(games(), "NYK")
    assert len(points) == 3
    assert (points[-1].wins, points[-1].losses) == (2, 1)
    assert points[0].opponent == "BOS"
    assert points[0].rating > 1500


def test_chronological_predictions_do_not_skip_games():
    rows = chronological_predictions(games())
    assert len(rows) == 4
    assert all(0 < row["p_home"] < 1 for row in rows)


def test_calibration_curve_conserves_observations():
    curve = calibration_curve(games(), bins=5)
    assert sum(x.count for x in curve) == 4
