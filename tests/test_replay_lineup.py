from datetime import date

import pytest

from nba_lab.impact import Stint, fit_rapm
from nba_lab.impact_source import ImpactPlayer, ImpactSnapshot
from nba_lab.replay import ReplayEvent
from nba_lab.replay_lineup import build_replay_lineup_intervention


def snapshot():
    players = {}
    for i in range(1, 8):
        players[f"A{i}"] = ImpactPlayer(f"A{i}", f"A{i}", "A")
        players[f"B{i}"] = ImpactPlayer(f"B{i}", f"B{i}", "B")
    stints = (
        Stint(
            "g1", 100, 12,
            ("A1","A2","A3","A4","A5"),
            ("B1","B2","B3","B4","B5"),
            date(2025, 11, 1),
        ),
        Stint(
            "g2", 100, 4,
            ("A1","A2","A3","A4","A6"),
            ("B1","B2","B3","B4","B6"),
            date(2025, 11, 2),
        ),
        Stint(
            "g3", 80, -2,
            ("A2","A3","A4","A5","A6"),
            ("B2","B3","B4","B5","B6"),
            date(2025, 11, 3),
        ),
    )
    return ImpactSnapshot(stints=stints, players=players, source="test", qa={})


def event():
    return ReplayEvent(
        "target", 40, 4, 288, 100, 100, "A", "checkpoint", "test", ""
    )


def test_lineup_swap_scales_net_rating_by_remaining_possessions():
    s = snapshot()
    rapm = fit_rapm(list(s.stints), alpha=100)
    result = build_replay_lineup_intervention(
        s,
        rapm,
        event(),
        "home",
        "A",
        ("A1","A2","A3","A4","A5"),
        ("A1","A2","A3","A4","A6"),
        prior_possessions=100,
    )
    assert abs(result.estimated_remaining_possessions - 10) < 1e-12
    assert abs(
        result.future_margin_adjustment
        - result.lineup_delta_per_100 * 0.1
    ) < 1e-12
    assert result.outgoing_player_id == "A5"
    assert result.incoming_player_id == "A6"


def test_away_lineup_delta_flips_home_margin_sign():
    s = snapshot()
    rapm = fit_rapm(list(s.stints), alpha=100)
    home_oriented = build_replay_lineup_intervention(
        s, rapm, event(), "home", "A",
        ("A1","A2","A3","A4","A5"),
        ("A1","A2","A3","A4","A6"),
        prior_possessions=100,
    )
    away_oriented = build_replay_lineup_intervention(
        s, rapm, event(), "away", "A",
        ("A1","A2","A3","A4","A5"),
        ("A1","A2","A3","A4","A6"),
        prior_possessions=100,
    )
    assert abs(
        home_oriented.future_margin_adjustment
        + away_oriented.future_margin_adjustment
    ) < 1e-12


def test_replay_lineup_requires_exactly_one_swap():
    s = snapshot()
    rapm = fit_rapm(list(s.stints), alpha=100)
    with pytest.raises(ValueError, match="swap exactly one"):
        build_replay_lineup_intervention(
            s, rapm, event(), "home", "A",
            ("A1","A2","A3","A4","A5"),
            ("A1","A2","A3","A6","A7"),
            prior_possessions=100,
        )
