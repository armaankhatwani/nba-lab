from nba_lab.demo import synthetic_demo_games
from nba_lab.demo_awards import synthetic_player_games
from nba_lab.demo_impact import synthetic_impact_snapshot


def test_offline_awards_and_impact_share_star_identities():
    games = synthetic_demo_games()
    awards = synthetic_player_games(games)
    impact = synthetic_impact_snapshot()

    award_ids = {row.player_id for row in awards}
    shared = award_ids & set(impact.players)

    assert {"demo-brunson", "1628369", "1628983", "203999"} <= shared
    assert impact.players["1628369"].player_name == "Jayson Tatum"
    assert impact.players["203999"].player_name == "Nikola Jokic"
