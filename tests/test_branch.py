from datetime import date

import pytest

from nba_lab.branch import compare_game_flip, flip_game
from nba_lab.domain import Game


def games():
    return [
        Game("g1", date(2026, 1, 1), "NYK", "BOS", 111, 109),
        Game("g2", date(2026, 1, 2), "NYK", "BOS", 105, 101),
        Game("g3", date(2026, 1, 3), "NYK", "BOS", 99, 103),
        Game("g4", date(2026, 1, 4), "NYK", "BOS"),
    ]


def test_flip_game_swaps_winner_without_mutating_original():
    changed, original = flip_game(games(), "g1")
    target = next(g for g in changed if g.game_id == "g1")
    assert original.winner == "NYK"
    assert target.winner == "BOS"
    assert original.home_score == 111


def test_game_flip_changes_future_distribution():
    result = compare_game_flip(games(), "g2", date(2026, 1, 4), trials=3000, seed=8)
    delta = {x.team: x for x in result.deltas}
    assert result.original_winner == "NYK"
    assert result.flipped_winner == "BOS"
    assert delta["NYK"].expected_wins_delta < 0
    assert delta["BOS"].expected_wins_delta > 0


def test_cannot_flip_future_game():
    with pytest.raises(ValueError):
        compare_game_flip(games(), "g3", date(2026, 1, 3), trials=100)
