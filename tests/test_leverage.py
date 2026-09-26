from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.leverage import evaluate_game_leverage, rank_upcoming_games


def test_forcing_each_winner_creates_nonnegative_distribution_shifts():
    games = synthetic_demo_games()
    as_of = date(2026, 1, 15)
    game = next(g for g in games if g.game_date >= as_of)
    row = evaluate_game_leverage(games, game, as_of, trials=150, seed=5)
    assert row.title_distribution_shift >= 0
    assert row.playoff_distribution_shift >= 0
    assert row.max_expected_wins_swing > 0


def test_upcoming_games_are_ranked_and_limited():
    games = synthetic_demo_games()
    rows = rank_upcoming_games(games, date(2026, 1, 15), trials=100, seed=4, limit=5)
    assert len(rows) == 5
    assert rows[0].title_distribution_shift >= rows[-1].title_distribution_shift


def test_game_specific_strength_adjustments_can_change_leverage():
    games = synthetic_demo_games()
    as_of = date(2026, 1, 15)
    game = next(g for g in games if g.game_date >= as_of)
    baseline = evaluate_game_leverage(games, game, as_of, trials=250, seed=12)
    adjusted = evaluate_game_leverage(
        games,
        game,
        as_of,
        trials=250,
        seed=12,
        game_rating_adjustments={
            future.game_id: {game.home_team: 140.0}
            for future in games
            if future.game_date >= as_of
        },
    )
    assert adjusted.title_distribution_shift >= 0
    assert (
        abs(adjusted.title_distribution_shift - baseline.title_distribution_shift) > 1e-9
        or abs(adjusted.playoff_distribution_shift - baseline.playoff_distribution_shift) > 1e-9
    )


def test_leverage_can_exclude_already_forced_games():
    games = synthetic_demo_games()
    as_of = date(2026, 1, 15)
    first = next(g for g in games if g.game_date >= as_of)
    rows = rank_upcoming_games(
        games, as_of, trials=100, seed=18, limit=5,
        excluded_game_ids={first.game_id},
    )
    assert rows
    assert all(row.game_id != first.game_id for row in rows)


def test_leverage_preserves_other_forced_results_inside_candidate_branches(monkeypatch):
    games = synthetic_demo_games()
    as_of = date(2026, 1, 15)
    future = [g for g in games if g.game_date >= as_of]
    fixed, candidate = future[0], future[1]
    calls = []

    class EmptyResult:
        teams = ()

    def fake_simulator(*args, **kwargs):
        calls.append(kwargs)
        return EmptyResult()

    monkeypatch.setattr("nba_lab.leverage.simulate_remaining_season", fake_simulator)
    evaluate_game_leverage(
        games,
        candidate,
        as_of,
        trials=10,
        seed=33,
        forced_winners={fixed.game_id: fixed.away_team},
    )
    assert len(calls) == 2
    assert calls[0]["forced_winners"][fixed.game_id] == fixed.away_team
    assert calls[1]["forced_winners"][fixed.game_id] == fixed.away_team
    assert calls[0]["forced_winners"][candidate.game_id] == candidate.home_team
    assert calls[1]["forced_winners"][candidate.game_id] == candidate.away_team
