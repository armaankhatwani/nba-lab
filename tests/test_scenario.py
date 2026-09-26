from datetime import date, timedelta

import pytest

from nba_lab.demo import synthetic_demo_games
from nba_lab.demo_impact import synthetic_impact_snapshot
from nba_lab.impact import fit_rapm
from nba_lab.scenario import (
    FutureResultIntervention,
    PlayerAbsence,
    TradeIntervention,
    build_scenario_inputs,
    scenario_roster_for_game,
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


def test_trade_adjusts_both_teams_in_opposite_directions():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    ranked = sorted(rapm.players, key=lambda row: row.impact_per_100, reverse=True)
    strong = ranked[0]
    strong_team = snapshot.players[strong.player_id].team
    weak = next(
        row for row in reversed(ranked)
        if snapshot.players[row.player_id].team != strong_team
    )
    weak_team = snapshot.players[weak.player_id].team
    result = simulate_scenario(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        [],
        trades=[TradeIntervention(strong.player_id, weak.player_id, minutes_per_game=36)],
        trials=500,
        seed=14,
    )
    assert len(result.trades) == 1
    deltas = {row.team: row for row in result.deltas}
    assert deltas[strong_team].expected_wins_delta < 0
    assert deltas[weak_team].expected_wins_delta > 0


def test_absence_translation_carries_rapm_uncertainty_band():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    player = max(rapm.players, key=lambda row: row.impact_per_100)
    adjustments, effects = build_player_absence_adjustments(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        [PlayerAbsence(player.player_id, games_missed=4, minutes_per_game=36)],
    )
    effect = effects[0]
    assert effect.impact_lower_80 <= effect.impact_per_100 <= effect.impact_upper_80
    assert effect.margin_delta_low_80 <= effect.margin_delta_per_game <= effect.margin_delta_high_80
    assert effect.elo_delta_low_80 <= effect.elo_delta_per_game <= effect.elo_delta_high_80
    assert adjustments


def test_trade_translation_carries_symmetric_impact_uncertainty():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    ranked = sorted(rapm.players, key=lambda row: row.impact_per_100, reverse=True)
    a = ranked[0]
    team_a = snapshot.players[a.player_id].team
    b = next(row for row in reversed(ranked) if snapshot.players[row.player_id].team != team_a)
    result = simulate_scenario(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        [],
        trades=[TradeIntervention(a.player_id, b.player_id, minutes_per_game=34)],
        trials=100,
        seed=27,
    )
    effect = result.trades[0]
    assert effect.impact_difference_standard_error >= 0
    assert effect.team_a_margin_delta_low_80 <= effect.team_a_margin_delta_per_game <= effect.team_a_margin_delta_high_80
    assert effect.team_b_margin_delta_low_80 <= effect.team_b_margin_delta_per_game <= effect.team_b_margin_delta_high_80



def test_future_result_intervention_forces_same_game_in_every_scenario_path():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    as_of = date(2026, 1, 15)
    game = next(row for row in games if row.game_date >= as_of)
    baseline = simulate_scenario(
        games, as_of, snapshot, rapm, [], trials=500, seed=31
    )
    altered = simulate_scenario(
        games,
        as_of,
        snapshot,
        rapm,
        [],
        future_results=[FutureResultIntervention(game.game_id, game.away_team)],
        trials=500,
        seed=31,
    )
    assert altered.future_results[0].game_id == game.game_id
    assert altered.future_results[0].forced_winner == game.away_team
    deltas = {row.team: row for row in altered.deltas}
    assert any(abs(row.expected_wins_delta) > 0 for row in deltas.values())
    assert baseline.future_results == ()


def test_future_result_rejects_past_game_and_invalid_winner():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    as_of = date(2026, 1, 15)
    past = next(row for row in games if row.game_date < as_of)
    with pytest.raises(ValueError, match="on or after"):
        simulate_scenario(
            games, as_of, snapshot, rapm, [],
            future_results=[FutureResultIntervention(past.game_id, past.home_team)],
            trials=20,
        )
    future = next(row for row in games if row.game_date >= as_of)
    with pytest.raises(ValueError, match="not in game"):
        simulate_scenario(
            games, as_of, snapshot, rapm, [],
            future_results=[FutureResultIntervention(future.game_id, "XXX")],
            trials=20,
        )


def test_trade_strength_persists_into_postseason_after_regular_schedule_ends():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    ranked = sorted(rapm.players, key=lambda row: row.impact_per_100, reverse=True)
    strong = ranked[0]
    strong_team = snapshot.players[strong.player_id].team
    weak = next(
        row for row in reversed(ranked)
        if snapshot.players[row.player_id].team != strong_team
    )
    weak_team = snapshot.players[weak.player_id].team
    as_of = max(game.game_date for game in games) + timedelta(days=1)

    result = simulate_scenario(
        games,
        as_of,
        snapshot,
        rapm,
        [],
        trades=[TradeIntervention(strong.player_id, weak.player_id, minutes_per_game=48)],
        trials=800,
        seed=91,
    )
    deltas = {row.team: row for row in result.deltas}

    # No regular-season games remain, so win totals cannot move.
    assert deltas[strong_team].expected_wins_delta == 0
    assert deltas[weak_team].expected_wins_delta == 0

    # The roster change still survives into the postseason strength model.
    assert result.team_rating_adjustments[strong_team] < 0
    assert result.team_rating_adjustments[weak_team] > 0
    assert (
        abs(deltas[strong_team].championship_probability_delta) > 0
        or abs(deltas[weak_team].championship_probability_delta) > 0
    )


def test_scenario_roster_applies_trade_and_game_specific_absence():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    as_of = date(2026, 1, 15)

    bos = [pid for pid, meta in snapshot.players.items() if meta.team == "BOS"]
    den = [pid for pid, meta in snapshot.players.items() if meta.team == "DEN"]
    future_bos = next(
        game for game in games
        if game.game_date >= as_of and "BOS" in {game.home_team, game.away_team}
    )
    inputs = build_scenario_inputs(
        games,
        as_of,
        snapshot,
        rapm,
        [PlayerAbsence(bos[1], games_missed=1, minutes_per_game=30)],
        trades=[TradeIntervention(bos[0], den[0], minutes_per_game=34)],
    )
    roster = scenario_roster_for_game(snapshot, inputs, "BOS", future_bos.game_id)

    assert bos[0] not in roster.player_ids
    assert den[0] in roster.player_ids
    assert bos[1] not in roster.player_ids
    assert den[0] in roster.traded_in
    assert bos[0] in roster.traded_out
    assert bos[1] in roster.unavailable
