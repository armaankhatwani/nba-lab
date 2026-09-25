from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .impact import RapmResult, Stint
from .impact_source import ImpactSnapshot


@dataclass(frozen=True)
class LineupEstimate:
    players: tuple[str, ...]
    additive_rapm: float
    observed_possessions: float
    observed_net_rating: float | None
    blended_net_rating: float
    observed_weight: float


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


def estimate_lineup(
    snapshot: ImpactSnapshot,
    rapm: RapmResult,
    players: tuple[str, ...],
    prior_possessions: float = 300.0,
) -> LineupEstimate:
    if len(players) != 5 or len(set(players)) != 5:
        raise ValueError("a lineup must contain exactly five unique players")
    unknown = set(players) - set(snapshot.players)
    if unknown:
        raise ValueError(f"unknown player ids: {sorted(unknown)}")
    if prior_possessions <= 0:
        raise ValueError("prior_possessions must be positive")

    impacts = {player.player_id: player.impact_per_100 for player in rapm.players}
    additive = sum(impacts[player] for player in players)

    observations = _lineup_observations(snapshot.stints)
    key = tuple(sorted(players))
    possessions, point_diff = observations.get(key, (0.0, 0.0))
    observed = 100.0 * point_diff / possessions if possessions else None
    weight = possessions / (possessions + prior_possessions) if possessions else 0.0
    blended = additive if observed is None else (1.0 - weight) * additive + weight * observed

    return LineupEstimate(
        players=key,
        additive_rapm=additive,
        observed_possessions=possessions,
        observed_net_rating=observed,
        blended_net_rating=blended,
        observed_weight=weight,
    )


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
