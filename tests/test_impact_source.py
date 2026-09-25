from nba_lab.demo_impact import synthetic_impact_snapshot
from nba_lab.impact import fit_rapm
from nba_lab.impact_source import parse_impact_snapshot


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
