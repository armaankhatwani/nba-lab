from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from math import sqrt

from .impact import RapmResult, Stint
from .impact_source import ImpactSnapshot


@dataclass(frozen=True)
class LineupEstimate:
    players: tuple[str, ...]
    additive_rapm: float
    rapm_standard_error: float
    rapm_lower_80: float
    rapm_upper_80: float
    observed_possessions: float
    observed_net_rating: float | None
    blended_net_rating: float
    observed_weight: float
    blended_lower_80: float
    blended_upper_80: float


@dataclass(frozen=True)
class LineupMatchup:
    lineup_a: LineupEstimate
    lineup_b: LineupEstimate
    neutral_margin_per_100: float


def _lineup_observations(stints: tuple[Stint, ...]):
    totals = defaultdict(lambda: [0.0, 0.0])
    for stint in stints:
        home = tuple(sorted(stint.home_players))
        away = tuple(sorted(stint.away_players))
        totals[home][0] += stint.possessions
        totals[home][1] += stint.point_diff
        totals[away][0] += stint.possessions
        totals[away][1] -= stint.point_diff
    return totals


def _estimate_lineup_from_context(
    snapshot: ImpactSnapshot,
    rapm: RapmResult,
    rapm_by_id: dict[str, object],
    observations,
    players: tuple[str, ...],
    prior_possessions: float,
) -> LineupEstimate:
    if len(players) != 5 or len(set(players)) != 5:
        raise ValueError("a lineup must contain exactly five unique players")
    unknown = set(players) - set(snapshot.players)
    if unknown:
        raise ValueError(f"unknown player ids: {sorted(unknown)}")
    if prior_possessions <= 0:
        raise ValueError("prior_possessions must be positive")
    missing = set(players) - set(rapm_by_id)
    if missing:
        raise ValueError(f"players missing RAPM estimates: {sorted(missing)}")

    key = tuple(sorted(players))
    rows = [rapm_by_id[player] for player in key]
    additive = sum(row.impact_per_100 for row in rows)
    covariance_index = {
        player_id: i
        for i, player_id in enumerate(rapm.player_order)
    }
    selected = [covariance_index[player] for player in key]
    variance = sum(
        rapm.player_covariance[i][j]
        for i in selected
        for j in selected
    )
    standard_error = sqrt(max(0.0, variance))
    z80 = 1.2815515655446004
    lower = additive - z80 * standard_error
    upper = additive + z80 * standard_error

    possessions, point_diff = observations.get(key, (0.0, 0.0))
    observed = 100.0 * point_diff / possessions if possessions else None
    weight = possessions / (possessions + prior_possessions) if possessions else 0.0
    blended = additive if observed is None else (1.0 - weight) * additive + weight * observed

    # Diagnostic sensitivity band: only the RAPM prior component varies.
    # Empirical lineup uncertainty is not estimated here.
    blended_lower = blended - (1.0 - weight) * (additive - lower)
    blended_upper = blended + (1.0 - weight) * (upper - additive)

    return LineupEstimate(
        players=key,
        additive_rapm=additive,
        rapm_standard_error=standard_error,
        rapm_lower_80=lower,
        rapm_upper_80=upper,
        observed_possessions=possessions,
        observed_net_rating=observed,
        blended_net_rating=blended,
        observed_weight=weight,
        blended_lower_80=blended_lower,
        blended_upper_80=blended_upper,
    )


def estimate_lineup(
    snapshot: ImpactSnapshot,
    rapm: RapmResult,
    players: tuple[str, ...],
    prior_possessions: float = 300.0,
) -> LineupEstimate:
    rapm_by_id = {player.player_id: player for player in rapm.players}
    observations = _lineup_observations(snapshot.stints)
    return _estimate_lineup_from_context(
        snapshot,
        rapm,
        rapm_by_id,
        observations,
        players,
        prior_possessions,
    )


def optimize_lineups(
    snapshot: ImpactSnapshot,
    rapm: RapmResult,
    candidate_players: tuple[str, ...],
    prior_possessions: float = 300.0,
    top_k: int = 10,
) -> tuple[LineupEstimate, ...]:
    unique = tuple(dict.fromkeys(candidate_players))
    if len(unique) < 5:
        raise ValueError("lineup optimization requires at least five players")
    if len(unique) > 20:
        raise ValueError("lineup optimization is limited to 20 players")
    if top_k < 1:
        raise ValueError("top_k must be positive")

    rapm_by_id = {player.player_id: player for player in rapm.players}
    observations = _lineup_observations(snapshot.stints)
    rows = [
        _estimate_lineup_from_context(
            snapshot,
            rapm,
            rapm_by_id,
            observations,
            tuple(group),
            prior_possessions,
        )
        for group in combinations(unique, 5)
    ]
    rows.sort(
        key=lambda row: (
            -row.blended_net_rating,
            -row.blended_lower_80,
            -row.observed_possessions,
            row.players,
        )
    )
    return tuple(rows[:top_k])


def compare_lineups(
    snapshot: ImpactSnapshot,
    rapm: RapmResult,
    lineup_a: tuple[str, ...],
    lineup_b: tuple[str, ...],
    prior_possessions: float = 300.0,
) -> LineupMatchup:
    a = estimate_lineup(snapshot, rapm, lineup_a, prior_possessions)
    b = estimate_lineup(snapshot, rapm, lineup_b, prior_possessions)
    if set(a.players) & set(b.players):
        raise ValueError("the two lineups cannot share a player")
    return LineupMatchup(
        lineup_a=a,
        lineup_b=b,
        neutral_margin_per_100=a.blended_net_rating - b.blended_net_rating,
    )
