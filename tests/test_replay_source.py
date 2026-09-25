from nba_lab.replay_source import parse_clock_seconds, parse_playbyplay_v3


def test_clock_parser_supports_v3_iso_and_mmss():
    assert parse_clock_seconds("PT11M32.00S") == 692
    assert parse_clock_seconds("02:15") == 135


def test_playbyplay_parser_carries_score_forward():
    snapshot = parse_playbyplay_v3({"PlayByPlay": [
        {"gameId":"g1","actionNumber":1,"clock":"PT12M00.00S","period":1,"scoreHome":"0","scoreAway":"0","description":"start"},
        {"gameId":"g1","actionNumber":2,"clock":"PT11M30.00S","period":1,"scoreHome":"2","scoreAway":"0","teamTricode":"NYK","description":"make","actionType":"2pt"},
        {"gameId":"g1","actionNumber":3,"clock":"PT11M10.00S","period":1,"scoreHome":"","scoreAway":"","teamTricode":"BOS","description":"miss"},
    ]})
    assert snapshot.game_id == "g1"
    assert snapshot.events[-1].home_score == 2
    assert snapshot.events[-1].away_score == 0
    assert snapshot.events[-1].team == "BOS"
