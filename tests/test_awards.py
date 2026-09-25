from datetime import date, timedelta

from nba_lab.awards import PlayerGame, build_award_race
from nba_lab.awards_source import parse_player_game_logs
from nba_lab.domain import Game


def make_data():
    start=date(2026,1,1); games=[]; logs=[]
    for i in range(20):
        d=start+timedelta(days=i)
        home,away=("NYK","BOS") if i%2==0 else ("BOS","NYK")
        hs,as_=(115,105) if home=="NYK" else (101,112)
        games.append(Game(str(i),d,home,away,hs,as_))
        logs += [
            PlayerGame(str(i),d,"a","Alpha","NYK",36,31,8,7,1.2,.7,3,20,8),
            PlayerGame(str(i),d,"b","Beta","BOS",36,24,10,5,1.0,1.1,2,18,6),
        ]
    return games,logs


def test_award_race_is_point_in_time_and_orders_candidates():
    games,logs=make_data()
    race=build_award_race(games,logs,date(2026,1,10))
    assert len(race.candidates)==2
    assert race.candidates[0].player_name=="Alpha"
    assert race.candidates[0].games==10
    assert abs(sum(x.race_share for x in race.candidates)-1)<1e-9


def test_future_player_games_do_not_leak():
    games,logs=make_data()
    a=build_award_race(games,logs,date(2026,1,5))
    b=build_award_race(games,logs[:10],date(2026,1,5))
    assert a==b


def test_player_game_logs_parser():
    rows=parse_player_game_logs({"PlayerGameLogs":[{
        "GAME_ID":"1","GAME_DATE":"2026-01-01","PLAYER_ID":1,"PLAYER_NAME":"A","TEAM_ABBREVIATION":"NYK",
        "MIN":35,"PTS":30,"REB":8,"AST":7,"STL":1,"BLK":1,"TOV":3,"FGA":20,"FTA":8
    }]})
    assert rows[0].player_name=="A" and rows[0].points==30
