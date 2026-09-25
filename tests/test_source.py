import pytest

from nba_lab.source import parse_schedule_league_v2


def cdn_payload():
    return {"leagueSchedule": {"gameDates": [{"gameDate": "2025-10-21", "games": [
        {"gameId": "0022500001", "gameStatus": 3, "gameDateEst": "2025-10-21", "homeTeam": {"teamTricode": "OKC", "score": "125"}, "awayTeam": {"teamTricode": "HOU", "score": "124"}},
        {"gameId": "0022500002", "gameStatus": 1, "gameDateEst": "2025-10-22", "homeTeam": {"teamTricode": "LAL", "score": ""}, "awayTeam": {"teamTricode": "GSW", "score": ""}},
        {"gameId": "0012500001", "gameStatus": 3, "gameLabel": "Preseason", "gameDateEst": "2025-10-10", "homeTeam": {"teamTricode": "NYK", "score": "100"}, "awayTeam": {"teamTricode": "BOS", "score": "99"}},
    ]}]}}


def normalized_payload():
    return {"SeasonGames": [
        {"gameId": "0022500001", "gameStatus": 3, "gameDateEst": "2025-10-21", "homeTeam_teamTricode": "OKC", "awayTeam_teamTricode": "HOU", "homeTeam_score": 125, "awayTeam_score": 124},
        {"gameId": "0022500002", "gameStatus": 1, "gameDateEst": "2025-10-22", "homeTeam_teamTricode": "LAL", "awayTeam_teamTricode": "GSW", "homeTeam_score": 0, "awayTeam_score": 0},
    ]}


@pytest.mark.parametrize("payload", [cdn_payload(), normalized_payload()])
def test_schedule_parser_supports_official_shapes(payload):
    games = parse_schedule_league_v2(payload)
    assert [g.game_id for g in games] == ["0022500001", "0022500002"]
    assert games[0].winner == "OKC"
    assert games[1].home_score is None and not games[1].is_final


def test_bad_payload_fails_loudly():
    with pytest.raises(ValueError):
        parse_schedule_league_v2({})
