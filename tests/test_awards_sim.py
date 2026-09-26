from datetime import date, timedelta

from nba_lab.awards import PlayerGame
from nba_lab.awards_sim import simulate_award_futures
from nba_lab.domain import Game


def data():
    start=date(2026,1,1); games=[]; logs=[]
    for i in range(12):
        d=start+timedelta(days=i)
        games.append(Game(str(i),d,"NYK","BOS",110 if i<6 else None,100 if i<6 else None))
        if i<6:
            logs.append(PlayerGame(str(i),d,"a","Alpha","NYK",36,32,8,8,1,1,3,20,8))
            logs.append(PlayerGame(str(i),d,"b","Beta","BOS",36,24,7,5,1,1,3,18,6))
    return games,logs


def test_award_future_distribution_conserves_leader_mass():
    games,logs=data()
    result=simulate_award_futures(games,logs,date(2026,1,6),trials=300,seed=7)
    assert result.candidates
    assert abs(sum(c.leader_probability for c in result.candidates)-1)<1e-9
    assert result.candidates[0].player_name=="Alpha"


def test_award_simulation_is_reproducible():
    games,logs=data()
    a=simulate_award_futures(games,logs,date(2026,1,6),trials=100,seed=9)
    b=simulate_award_futures(games,logs,date(2026,1,6),trials=100,seed=9)
    assert a==b


def test_award_future_can_block_candidate_games():
    games,logs=data()
    baseline=simulate_award_futures(games,logs,date(2026,1,6),trials=300,seed=17)
    future_ids={g.game_id for g in games if g.game_date>date(2026,1,6)}
    altered=simulate_award_futures(
        games,logs,date(2026,1,6),trials=300,seed=17,
        player_unavailable_game_ids={"a": future_ids},
    )
    b={c.player_id:c for c in baseline.candidates}
    a={c.player_id:c for c in altered.candidates}
    assert a["a"].mean_final_score <= b["a"].mean_final_score


def test_award_future_can_override_player_team():
    games,logs=data()
    result=simulate_award_futures(
        games,logs,date(2026,1,6),trials=50,seed=3,
        player_team_overrides={"a":"BOS"},
    )
    row=next(c for c in result.candidates if c.player_id=="a")
    assert row.team=="BOS"
