from __future__ import annotations

from dataclasses import dataclass

from .impact import RapmResult
from .impact_source import ImpactSnapshot
from .lineup import LineupEstimate, estimate_lineup
from .replay import ReplayEvent, total_seconds_remaining


@dataclass(frozen=True)
class ReplayLineupIntervention:
    side: str
    team: str
    baseline: LineupEstimate
    altered: LineupEstimate
    lineup_delta_per_100: float
    estimated_remaining_possessions: float
    future_margin_adjustment: float
    outgoing_player_id: str
    incoming_player_id: str


def build_replay_lineup_intervention(
    snapshot: ImpactSnapshot,
    rapm: RapmResult,
    event: ReplayEvent,
    side: str,
    team: str,
    baseline_players: tuple[str, ...],
    altered_players: tuple[str, ...],
    prior_possessions: float = 300.0,
    possessions_per_48: float = 100.0,
) -> ReplayLineupIntervention:
    if side not in {"home", "away"}:
        raise ValueError("lineup side must be home or away")
    if possessions_per_48 <= 0:
        raise ValueError("possessions_per_48 must be positive")
    if len(baseline_players) != 5 or len(set(baseline_players)) != 5:
        raise ValueError("baseline lineup must contain five unique players")
    if len(altered_players) != 5 or len(set(altered_players)) != 5:
        raise ValueError("altered lineup must contain five unique players")

    baseline_set = set(baseline_players)
    altered_set = set(altered_players)
    outgoing = baseline_set - altered_set
    incoming = altered_set - baseline_set
    if len(outgoing) != 1 or len(incoming) != 1 or len(baseline_set & altered_set) != 4:
        raise ValueError("Replay lineup intervention must swap exactly one player")

    for player_id in baseline_set | altered_set:
        meta = snapshot.players.get(player_id)
        if meta is None:
            raise ValueError(f"unknown lineup player: {player_id}")
        if meta.team != team:
            raise ValueError(
                f"lineup player {player_id} belongs to {meta.team}, not {team}"
            )

    baseline = estimate_lineup(
        snapshot,
        rapm,
        tuple(baseline_players),
        prior_possessions=prior_possessions,
    )
    altered = estimate_lineup(
        snapshot,
        rapm,
        tuple(altered_players),
        prior_possessions=prior_possessions,
    )
    lineup_delta = altered.blended_net_rating - baseline.blended_net_rating

    seconds_remaining = total_seconds_remaining(
        event.period,
        event.clock_seconds,
    )
    remaining_possessions = possessions_per_48 * seconds_remaining / 2880.0
    raw_margin_adjustment = lineup_delta * remaining_possessions / 100.0
    home_margin_adjustment = (
        raw_margin_adjustment if side == "home" else -raw_margin_adjustment
    )

    return ReplayLineupIntervention(
        side=side,
        team=team,
        baseline=baseline,
        altered=altered,
        lineup_delta_per_100=lineup_delta,
        estimated_remaining_possessions=remaining_possessions,
        future_margin_adjustment=home_margin_adjustment,
        outgoing_player_id=next(iter(outgoing)),
        incoming_player_id=next(iter(incoming)),
    )
