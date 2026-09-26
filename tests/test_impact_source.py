from datetime import date

import pytest

from nba_lab.demo_impact import synthetic_impact_snapshot
from nba_lab.impact import fit_rapm
from nba_lab.impact_source import parse_impact_snapshot, snapshot_as_of


def test_normalized_impact_snapshot_parses():
    snapshot=parse_impact_snapshot({
        "source":"test",
        "players":[
            {"player_id":"A","player_name":"Alpha","team":"NYK"},
            {"player_id":"B","player_name":"Beta","team":"BOS"},
        ],
        "stints":[{"game_id":"g","possessions":10,"point_diff":2,"home_players":["A"],"away_players":["B"]}],
    })
    assert snapshot.source=="test"
    assert snapshot.players["A"].player_name=="Alpha"


def test_synthetic_snapshot_fits_rapm():
    snapshot=synthetic_impact_snapshot()
    result=fit_rapm(list(snapshot.stints),alpha=300)
    assert len(result.players)==32
    assert result.players[0].impact_per_100>result.players[-1].impact_per_100
    assert result.weighted_rmse>=0


def test_impact_snapshot_filters_stints_strictly_before_cutoff():
    snapshot=parse_impact_snapshot({
        "source":"dated",
        "players":[
            {"player_id":"A","player_name":"Alpha","team":"NYK"},
            {"player_id":"B","player_name":"Beta","team":"BOS"},
        ],
        "stints":[
            {"game_id":"g1","game_date":"2026-01-01","possessions":10,"point_diff":2,"home_players":["A"],"away_players":["B"]},
            {"game_id":"g2","game_date":"2026-02-01","possessions":12,"point_diff":-1,"home_players":["A"],"away_players":["B"]},
        ],
    })
    filtered=snapshot_as_of(snapshot,date(2026,1,15))
    assert [row.game_id for row in filtered.stints]==["g1"]
    assert filtered.qa["stints_excluded_future"]==1


def test_legacy_impact_snapshot_resolves_dates_through_schedule():
    snapshot=parse_impact_snapshot({
        "source":"legacy",
        "players":[
            {"player_id":"A","player_name":"Alpha","team":"NYK"},
            {"player_id":"B","player_name":"Beta","team":"BOS"},
        ],
        "stints":[
            {"game_id":"g1","possessions":10,"point_diff":2,"home_players":["A"],"away_players":["B"]},
            {"game_id":"g2","possessions":12,"point_diff":-1,"home_players":["A"],"away_players":["B"]},
        ],
    })
    filtered=snapshot_as_of(
        snapshot,
        date(2026,1,15),
        game_dates={"g1":date(2026,1,1),"g2":date(2026,2,1)},
    )
    assert [row.game_id for row in filtered.stints]==["g1"]
    assert filtered.stints[0].game_date==date(2026,1,1)


def test_unresolved_impact_stint_date_is_rejected_for_point_in_time_use():
    snapshot=parse_impact_snapshot({
        "source":"legacy",
        "players":[
            {"player_id":"A","player_name":"Alpha","team":"NYK"},
            {"player_id":"B","player_name":"Beta","team":"BOS"},
        ],
        "stints":[
            {"game_id":"unknown","possessions":10,"point_diff":2,"home_players":["A"],"away_players":["B"]},
        ],
    })
    with pytest.raises(ValueError,match="unresolved game dates"):
        snapshot_as_of(snapshot,date(2026,1,15),game_dates={})
