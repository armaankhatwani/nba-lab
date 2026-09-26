from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.world import simulate_one_world


def test_one_world_is_reproducible_and_complete():
    games = synthetic_demo_games()
    a = simulate_one_world(games, date(2026, 1, 15), seed=44)
    b = simulate_one_world(games, date(2026, 1, 15), seed=44)

    assert a == b
    assert len(a.standings) == 30
    assert sum(row.playoff_seed is not None for row in a.standings) == 16
    assert len(a.play_in_games) == 6
    assert len(a.series) == 15
    assert a.east_champion
    assert a.west_champion
    assert a.champion == a.series[-1].winner


def test_one_world_honors_forced_future_result():
    games = synthetic_demo_games()
    as_of = date(2026, 1, 15)
    game = next(row for row in games if row.game_date >= as_of)
    world = simulate_one_world(
        games,
        as_of,
        seed=45,
        forced_winners={game.game_id: game.away_team},
    )
    row = next(item for item in world.remaining_games if item.game_id == game.game_id)
    assert row.forced is True
    assert row.winner == game.away_team


def test_conference_series_preserve_better_seed_home_court():
    world = simulate_one_world(
        synthetic_demo_games(),
        date(2026, 1, 15),
        seed=46,
    )
    conference_series = [row for row in world.series if row.conference in {"East", "West"}]
    assert conference_series
    assert all(
        row.higher_seed is not None
        and row.lower_seed is not None
        and row.higher_seed < row.lower_seed
        for row in conference_series
    )
