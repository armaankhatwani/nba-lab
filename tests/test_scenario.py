from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.demo_impact import synthetic_impact_snapshot
from nba_lab.impact import fit_rapm
from nba_lab.scenario import (
    PlayerAbsence,
    build_player_absence_adjustments,
    elo_delta_for_margin,
    simulate_scenario,
)


def test_margin_to_elo_conversion_preserves_direction():
    assert elo_delta_for_margin(3.0, 12.0) > 0
    assert elo_delta_for_margin(-3.0, 12.0) < 0
    assert abs(elo_delta_for_margin(0.0, 12.0)) < 1e-12


def test_positive_player_absence_penalizes_only_next_n_games():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    player = max(rapm.players, key=lambda row: row.impact_per_100)
    meta = snapshot.players[player.player_id]
    adjustments, effects = build_player_absence_adjustments(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        [PlayerAbsence(player.player_id, games_missed=5, minutes_per_game=36)],
    )
    effect = effects[0]
    assert effect.team == meta.team
    assert len(effect.affected_game_ids) == 5
    assert effect.elo_delta_per_game < 0
    assert set(adjustments) == set(effect.affected_game_ids)


def test_player_absence_changes_team_distribution_with_paired_worlds():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    player = max(rapm.players, key=lambda row: row.impact_per_100)
    team = snapshot.players[player.player_id].team
    result = simulate_scenario(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        [PlayerAbsence(player.player_id, games_missed=10, minutes_per_game=36)],
        trials=600,
        seed=9,
    )
    delta = {row.team: row for row in result.deltas}[team]
    assert delta.expected_wins_delta < 0
    assert result.player_absences[0].affected_game_ids


def test_historical_flip_and_absence_compose_in_one_world():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    as_of = date(2026, 1, 15)
    prior = next(game for game in reversed(games) if game.game_date < as_of and game.is_final)
    player = max(rapm.players, key=lambda row: row.impact_per_100)
    result = simulate_scenario(
        games,
        as_of,
        snapshot,
        rapm,
        [PlayerAbsence(player.player_id, games_missed=6, minutes_per_game=36)],
        flipped_game_ids=[prior.game_id],
        trials=300,
        seed=11,
    )
    assert len(result.historical_flips) == 1
    assert result.historical_flips[0].original_winner != result.historical_flips[0].flipped_winner
    assert result.player_absences[0].affected_game_ids
