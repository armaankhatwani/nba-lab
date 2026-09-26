from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import log10
from statistics import NormalDist

from .analysis import TeamDelta, build_team_deltas
from .domain import Game
from .impact import RapmResult
from .impact_source import ImpactSnapshot
from .replay import historical_margin_sigma
from .simulator import SimulationResult, simulate_remaining_season


@dataclass(frozen=True)
class PlayerAbsence:
    player_id: str
    games_missed: int
    minutes_per_game: float = 34.0
    replacement_impact_per_100: float = 0.0


@dataclass(frozen=True)
class PlayerAbsenceEffect:
    player_id: str
    player_name: str
    team: str
    impact_per_100: float
    replacement_impact_per_100: float
    minutes_per_game: float
    games_missed: int
    margin_delta_per_game: float
    elo_delta_per_game: float
    affected_game_ids: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioResult:
    as_of: date
    trials: int
    baseline: SimulationResult
    altered: SimulationResult
    deltas: tuple[TeamDelta, ...]
    player_absences: tuple[PlayerAbsenceEffect, ...]


def elo_delta_for_margin(margin_delta: float, margin_sigma: float) -> float:
    if margin_sigma <= 0:
        raise ValueError("margin_sigma must be positive")
    p = NormalDist().cdf(margin_delta / margin_sigma)
    p = min(1 - 1e-6, max(1e-6, p))
    return 400.0 * log10(p / (1.0 - p))


def _future_team_games(games: list[Game], as_of: date, team: str) -> list[Game]:
    return sorted(
        (
            game
            for game in games
            if game.game_date >= as_of and team in {game.home_team, game.away_team}
        ),
        key=lambda game: (game.game_date, game.game_id),
    )


def build_player_absence_adjustments(
    games: list[Game],
    as_of: date,
    impact_snapshot: ImpactSnapshot,
    rapm: RapmResult,
    absences: list[PlayerAbsence],
    possessions_per_game: float = 100.0,
) -> tuple[dict[str, dict[str, float]], tuple[PlayerAbsenceEffect, ...]]:
    if possessions_per_game <= 0:
        raise ValueError("possessions_per_game must be positive")
    impact_by_id = {row.player_id: row for row in rapm.players}
    game_adjustments: dict[str, dict[str, float]] = {}
    effects: list[PlayerAbsenceEffect] = []
    sigma = historical_margin_sigma(games, as_of)

    for absence in absences:
        if absence.games_missed < 1:
            raise ValueError("games_missed must be positive")
        if not 0 < absence.minutes_per_game <= 48:
            raise ValueError("minutes_per_game must be in (0, 48]")
        meta = impact_snapshot.players.get(absence.player_id)
        impact = impact_by_id.get(absence.player_id)
        if meta is None or impact is None:
            raise ValueError(f"unknown impact player: {absence.player_id}")

        margin_delta = (
            (absence.replacement_impact_per_100 - impact.impact_per_100)
            * (absence.minutes_per_game / 48.0)
            * (possessions_per_game / 100.0)
        )
        elo_delta = elo_delta_for_margin(margin_delta, sigma)
        affected = _future_team_games(games, as_of, meta.team)[: absence.games_missed]
        for game in affected:
            game_adjustments.setdefault(game.game_id, {})
            game_adjustments[game.game_id][meta.team] = (
                game_adjustments[game.game_id].get(meta.team, 0.0) + elo_delta
            )
        effects.append(
            PlayerAbsenceEffect(
                player_id=absence.player_id,
                player_name=meta.player_name,
                team=meta.team,
                impact_per_100=impact.impact_per_100,
                replacement_impact_per_100=absence.replacement_impact_per_100,
                minutes_per_game=absence.minutes_per_game,
                games_missed=absence.games_missed,
                margin_delta_per_game=margin_delta,
                elo_delta_per_game=elo_delta,
                affected_game_ids=tuple(game.game_id for game in affected),
            )
        )

    return game_adjustments, tuple(effects)


def simulate_scenario(
    games: list[Game],
    as_of: date,
    impact_snapshot: ImpactSnapshot,
    rapm: RapmResult,
    absences: list[PlayerAbsence],
    trials: int = 5000,
    seed: int = 2026,
) -> ScenarioResult:
    adjustments, effects = build_player_absence_adjustments(
        games, as_of, impact_snapshot, rapm, absences
    )
    baseline = simulate_remaining_season(
        games, as_of, trials=trials, seed=seed
    )
    altered = simulate_remaining_season(
        games,
        as_of,
        trials=trials,
        seed=seed,
        game_rating_adjustments=adjustments,
    )
    return ScenarioResult(
        as_of=as_of,
        trials=trials,
        baseline=baseline,
        altered=altered,
        deltas=build_team_deltas(baseline, altered),
        player_absences=effects,
    )
