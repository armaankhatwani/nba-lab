from __future__ import annotations

from dataclasses import dataclass
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
        stints.append(Stint(
            game_id=str(row["game_id"]),
            possessions=float(row["possessions"]),
            point_diff=float(row["point_diff"]),
            home_players=home,
            away_players=away,
        ))
    if not stints:
        raise ValueError("impact snapshot contains no stints")
    return ImpactSnapshot(
        stints=tuple(stints),
        players=players,
        source=str(payload.get("source") or "normalized_stints"),
        qa={str(k): int(v) for k, v in (payload.get("qa") or {}).items()},
    )


def load_impact_snapshot(path: str | Path) -> ImpactSnapshot:
    return parse_impact_snapshot(json.loads(Path(path).read_text()))
