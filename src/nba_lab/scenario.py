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
from .branch import flip_game
from .simulator import SimulationResult, simulate_remaining_season


@dataclass(frozen=True)
class PlayerAbsence:
    player_id: str
    games_missed: int
    minutes_per_game: float = 34.0
    replacement_impact_per_100: float = 0.0


@dataclass(frozen=True)
class TradeIntervention:
    player_a_id: str
    player_b_id: str
    minutes_per_game: float = 34.0


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
class TradeEffect:
    player_a_id: str
    player_a_name: str
    team_a: str
    player_b_id: str
    player_b_name: str
    team_b: str
    player_a_impact_per_100: float
    player_b_impact_per_100: float
    minutes_per_game: float
    team_a_margin_delta_per_game: float
    team_b_margin_delta_per_game: float
    team_a_elo_delta_per_game: float
    team_b_elo_delta_per_game: float
    team_a_affected_games: tuple[str, ...]
    team_b_affected_games: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalFlipEffect:
    game_id: str
    game_date: date
    home_team: str
    away_team: str
    original_winner: str
    flipped_winner: str


@dataclass(frozen=True)
class ScenarioResult:
    as_of: date
    trials: int
    baseline: SimulationResult
    altered: SimulationResult
    deltas: tuple[TeamDelta, ...]
    player_absences: tuple[PlayerAbsenceEffect, ...]
    historical_flips: tuple[HistoricalFlipEffect, ...]
    trades: tuple[TradeEffect, ...]


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



def build_trade_adjustments(
    games: list[Game],
    as_of: date,
    impact_snapshot: ImpactSnapshot,
    rapm: RapmResult,
    trades: list[TradeIntervention],
    possessions_per_game: float = 100.0,
) -> tuple[dict[str, dict[str, float]], tuple[TradeEffect, ...]]:
    impact_by_id = {row.player_id: row for row in rapm.players}
    sigma = historical_margin_sigma(games, as_of)
    adjustments: dict[str, dict[str, float]] = {}
    effects: list[TradeEffect] = []

    for trade in trades:
        if trade.player_a_id == trade.player_b_id:
            raise ValueError("trade players must be different")
        if not 0 < trade.minutes_per_game <= 48:
            raise ValueError("trade minutes_per_game must be in (0, 48]")
        meta_a = impact_snapshot.players.get(trade.player_a_id)
        meta_b = impact_snapshot.players.get(trade.player_b_id)
        impact_a = impact_by_id.get(trade.player_a_id)
        impact_b = impact_by_id.get(trade.player_b_id)
        if meta_a is None or meta_b is None or impact_a is None or impact_b is None:
            raise ValueError("unknown impact player in trade")
        if meta_a.team == meta_b.team:
            raise ValueError("trade players must be on different teams")

        scale = (trade.minutes_per_game / 48.0) * (possessions_per_game / 100.0)
        margin_a = (impact_b.impact_per_100 - impact_a.impact_per_100) * scale
        margin_b = (impact_a.impact_per_100 - impact_b.impact_per_100) * scale
        elo_a = elo_delta_for_margin(margin_a, sigma)
        elo_b = elo_delta_for_margin(margin_b, sigma)
        games_a = _future_team_games(games, as_of, meta_a.team)
        games_b = _future_team_games(games, as_of, meta_b.team)

        for game in games_a:
            adjustments.setdefault(game.game_id, {})
            adjustments[game.game_id][meta_a.team] = adjustments[game.game_id].get(meta_a.team, 0.0) + elo_a
        for game in games_b:
            adjustments.setdefault(game.game_id, {})
            adjustments[game.game_id][meta_b.team] = adjustments[game.game_id].get(meta_b.team, 0.0) + elo_b

        effects.append(TradeEffect(
            player_a_id=trade.player_a_id,
            player_a_name=meta_a.player_name,
            team_a=meta_a.team,
            player_b_id=trade.player_b_id,
            player_b_name=meta_b.player_name,
            team_b=meta_b.team,
            player_a_impact_per_100=impact_a.impact_per_100,
            player_b_impact_per_100=impact_b.impact_per_100,
            minutes_per_game=trade.minutes_per_game,
            team_a_margin_delta_per_game=margin_a,
            team_b_margin_delta_per_game=margin_b,
            team_a_elo_delta_per_game=elo_a,
            team_b_elo_delta_per_game=elo_b,
            team_a_affected_games=tuple(game.game_id for game in games_a),
            team_b_affected_games=tuple(game.game_id for game in games_b),
        ))

    return adjustments, tuple(effects)


def _merge_game_adjustments(
    base: dict[str, dict[str, float]],
    extra: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    merged = {game_id: dict(rows) for game_id, rows in base.items()}
    for game_id, rows in extra.items():
        merged.setdefault(game_id, {})
        for team, value in rows.items():
            merged[game_id][team] = merged[game_id].get(team, 0.0) + value
    return merged


def simulate_scenario(
    games: list[Game],
    as_of: date,
    impact_snapshot: ImpactSnapshot,
    rapm: RapmResult,
    absences: list[PlayerAbsence],
    flipped_game_ids: list[str] | None = None,
    trades: list[TradeIntervention] | None = None,
    trials: int = 5000,
    seed: int = 2026,
) -> ScenarioResult:
    altered_games = list(games)
    flip_effects: list[HistoricalFlipEffect] = []
    for game_id in flipped_game_ids or []:
        altered_games, target = flip_game(altered_games, game_id)
        if target.game_date >= as_of:
            raise ValueError("historical scenario flips must occur before the as-of date")
        flipped = next(game for game in altered_games if game.game_id == game_id)
        flip_effects.append(HistoricalFlipEffect(
            game_id=game_id,
            game_date=target.game_date,
            home_team=target.home_team,
            away_team=target.away_team,
            original_winner=target.winner or "",
            flipped_winner=flipped.winner or "",
        ))

    absence_adjustments, effects = build_player_absence_adjustments(
        altered_games, as_of, impact_snapshot, rapm, absences
    )
    trade_adjustments, trade_effects = build_trade_adjustments(
        altered_games, as_of, impact_snapshot, rapm, trades or []
    )
    adjustments = _merge_game_adjustments(absence_adjustments, trade_adjustments)
    baseline = simulate_remaining_season(
        games, as_of, trials=trials, seed=seed
    )
    altered = simulate_remaining_season(
        altered_games,
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
        historical_flips=tuple(flip_effects),
        trades=trade_effects,
    )
