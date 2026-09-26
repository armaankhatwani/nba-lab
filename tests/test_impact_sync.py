from types import SimpleNamespace

from datetime import date

from nba_lab.domain import Game
from nba_lab.impact_sync import possession_to_stint, select_impact_games


class Event:
    def __init__(self, lineups, score):
        self.lineup_ids = lineups
        self.score = score


def possession(lineups, score, prev_score=None):
    previous = None if prev_score is None else SimpleNamespace(events=[Event(lineups, prev_score)])
    return SimpleNamespace(
        game_id="g1",
        previous_possession=previous,
        events=[Event(lineups, score)],
    )


def test_possession_to_stint_uses_score_delta_and_lineups():
    lineups = {1: "1-2-3-4-5", 2: "6-7-8-9-10"}
    p = possession(lineups, {1: 12, 2: 10}, {1: 10, 2: 10})
    stint = possession_to_stint(p, 1, 2)
    assert stint is not None
    assert stint.point_diff == 2
    assert stint.home_players == ("1", "2", "3", "4", "5")


def test_mid_possession_lineup_change_is_rejected():
    a = {1: "1-2-3-4-5", 2: "6-7-8-9-10"}
    b = {1: "1-2-3-4-11", 2: "6-7-8-9-10"}
    p = SimpleNamespace(
        game_id="g",
        previous_possession=None,
        events=[Event(a, {1: 0, 2: 0}), Event(b, {1: 1, 2: 0})],
    )
    assert possession_to_stint(p, 1, 2) is None


def test_non_five_player_lineup_is_rejected():
    lineups = {1: "1-2-3-4", 2: "6-7-8-9-10"}
    assert possession_to_stint(possession(lineups, {1: 0, 2: 0}), 1, 2) is None


def test_select_impact_games_filters_final_games_by_team_before_limit():
    games = [
        Game("1", date(2025, 1, 1), "BOS", "NYK", 100, 99),
        Game("2", date(2025, 1, 2), "DEN", "OKC", 110, 108),
        Game("3", date(2025, 1, 3), "NYK", "BOS", 101, 100),
        Game("4", date(2025, 1, 4), "BOS", "DEN", None, None),
    ]
    selected, teams = select_impact_games(games, max_games=1, teams={"bos"})
    assert teams == {"BOS"}
    assert [game.game_id for game in selected] == ["1"]


def test_select_impact_games_rejects_negative_limit():
    import pytest

    with pytest.raises(ValueError, match="non-negative"):
        select_impact_games([], max_games=-1)
