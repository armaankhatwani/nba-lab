from datetime import date

from nba_lab.demo import synthetic_demo_games
from nba_lab.demo_impact import synthetic_impact_snapshot
from nba_lab.impact import fit_rapm
from nba_lab.rest_planner import evaluate_rest_plan
from nba_lab.scenario import PlayerAbsence, build_player_absence_adjustments


def test_rest_planner_reuses_scenario_strength_translation():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    player = max(rapm.players, key=lambda row: row.impact_per_100)

    plan = evaluate_rest_plan(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        player.player_id,
        trials=250,
        seed=31,
        minutes_per_game=36,
        horizon_games=5,
    )
    _, effects = build_player_absence_adjustments(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        [
            PlayerAbsence(
                player.player_id,
                games_missed=1,
                minutes_per_game=36,
            )
        ],
    )

    assert abs(plan.elo_delta_per_game - effects[0].elo_delta_per_game) < 1e-12
    assert plan.elo_delta_per_game < 0
    assert len(plan.games) == 5


def test_resting_positive_impact_player_does_not_increase_expected_wins():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    player = max(rapm.players, key=lambda row: row.impact_per_100)

    plan = evaluate_rest_plan(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        player.player_id,
        trials=500,
        seed=37,
        horizon_games=8,
    )

    assert [row.rank for row in plan.games] == list(range(1, 9))
    assert len({row.game_id for row in plan.games}) == 8
    assert all(row.expected_wins_delta <= 1e-12 for row in plan.games)


def test_rest_planner_exposes_impact_uncertainty_band():
    games = synthetic_demo_games()
    snapshot = synthetic_impact_snapshot()
    rapm = fit_rapm(list(snapshot.stints), alpha=1000)
    player = max(rapm.players, key=lambda row: row.impact_per_100)

    plan = evaluate_rest_plan(
        games,
        date(2026, 1, 15),
        snapshot,
        rapm,
        player.player_id,
        trials=120,
        seed=41,
        horizon_games=3,
    )

    assert plan.player_impact_lower_80 <= plan.player_impact_per_100 <= plan.player_impact_upper_80
    assert plan.elo_delta_low_80 <= plan.elo_delta_per_game <= plan.elo_delta_high_80
