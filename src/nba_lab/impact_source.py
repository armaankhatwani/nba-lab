from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any

from .impact import Stint


@dataclass(frozen=True)
class ImpactPlayer:
    player_id: str
    player_name: str
    team: str


@dataclass(frozen=True)
class ImpactSnapshot:
    stints: tuple[Stint, ...]
    players: dict[str, ImpactPlayer]
    source: str
    qa: dict[str, int]


def parse_impact_snapshot(payload: dict[str, Any]) -> ImpactSnapshot:
    raw_players=payload.get("players")
    raw_stints=payload.get("stints")
    if not isinstance(raw_players,list) or not isinstance(raw_stints,list):
        raise ValueError("impact snapshot requires players[] and stints[]")
    players={}
    for row in raw_players:
        player=ImpactPlayer(
            player_id=str(row["player_id"]),
            player_name=str(row["player_name"]),
            team=str(row["team"]),
        )
        players[player.player_id]=player
    stints=[]
    for row in raw_stints:
        home=tuple(str(x) for x in row["home_players"])
        away=tuple(str(x) for x in row["away_players"])
        if len(home)!=len(set(home)) or len(away)!=len(set(away)):
            raise ValueError("duplicate player within lineup")
        if set(home)&set(away):
            raise ValueError("player cannot appear on both teams in one stint")
        unknown=(set(home)|set(away))-set(players)
        if unknown:
            raise ValueError(f"unknown player ids in stint: {sorted(unknown)}")
        raw_date = row.get("game_date")
        stints.append(Stint(
            game_id=str(row["game_id"]),
            possessions=float(row["possessions"]),
            point_diff=float(row["point_diff"]),
            home_players=home,
            away_players=away,
            game_date=date.fromisoformat(str(raw_date)) if raw_date else None,
        ))
    if not stints:
        raise ValueError("impact snapshot contains no stints")
    return ImpactSnapshot(
        stints=tuple(stints),
        players=players,
        source=str(payload.get("source") or "normalized_stints"),
        qa={str(k): int(v) for k, v in (payload.get("qa") or {}).items()},
    )



def snapshot_as_of(
    snapshot: ImpactSnapshot,
    as_of: date,
    game_dates: dict[str, date] | None = None,
    require_resolved_dates: bool = True,
) -> ImpactSnapshot:
    """Return only stints from games strictly before the selected cutoff.

    Legacy normalized files may omit game_date; callers can resolve those dates
    through the schedule's game_id -> date mapping.
    """
    dates = game_dates or {}
    kept = []
    unresolved = []
    for stint in snapshot.stints:
        resolved = stint.game_date or dates.get(stint.game_id)
        if resolved is None:
            unresolved.append(stint.game_id)
            continue
        if resolved < as_of:
            kept.append(
                Stint(
                    game_id=stint.game_id,
                    possessions=stint.possessions,
                    point_diff=stint.point_diff,
                    home_players=stint.home_players,
                    away_players=stint.away_players,
                    game_date=resolved,
                )
            )

    if unresolved and require_resolved_dates:
        sample = ", ".join(sorted(set(unresolved))[:5])
        raise ValueError(
            "impact snapshot has stints with unresolved game dates"
            + (f": {sample}" if sample else "")
        )
    if not kept:
        raise ValueError("impact snapshot has no stints before the selected as-of date")

    qa = dict(snapshot.qa)
    qa["stints_before_as_of"] = len(kept)
    qa["stints_excluded_future"] = len(snapshot.stints) - len(kept) - len(unresolved)
    qa["stints_unresolved_date"] = len(unresolved)
    return ImpactSnapshot(
        stints=tuple(kept),
        players=snapshot.players,
        source=snapshot.source,
        qa=qa,
    )

def load_impact_snapshot(path: str | Path) -> ImpactSnapshot:
    return parse_impact_snapshot(json.loads(Path(path).read_text()))
