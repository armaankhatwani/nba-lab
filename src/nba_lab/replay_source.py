from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .replay import ReplayEvent


@dataclass(frozen=True)
class ReplaySnapshot:
    game_id: str
    events: tuple[ReplayEvent, ...]
    source: str


def parse_clock_seconds(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    iso = re.fullmatch(r"PT(?:(\d+)M)?([0-9.]+)S", text)
    if iso:
        minutes = int(iso.group(1) or 0)
        seconds = float(iso.group(2))
        return minutes * 60 + seconds
    if ":" in text:
        minutes, seconds = text.split(":", 1)
        return int(minutes) * 60 + float(seconds)
    return float(text)


def _get(row: dict[str, Any], *keys, default=None):
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def parse_playbyplay_v3(payload: dict[str, Any]) -> ReplaySnapshot:
    rows = payload.get("PlayByPlay") or payload.get("play_by_play")
    if not isinstance(rows, list) or not rows:
        raise ValueError("PlayByPlay payload is missing rows")

    game_id = str(_get(rows[0], "gameId", "GAME_ID", default=""))
    if not game_id:
        raise ValueError("PlayByPlay rows are missing gameId")

    events = []
    home_score = 0
    away_score = 0
    for raw in rows:
        raw_home = _get(raw, "scoreHome", "SCORE_HOME")
        raw_away = _get(raw, "scoreAway", "SCORE_AWAY")
        if raw_home not in (None, ""):
            home_score = int(float(raw_home))
        if raw_away not in (None, ""):
            away_score = int(float(raw_away))

        events.append(
            ReplayEvent(
                game_id=game_id,
                action_number=int(_get(raw, "actionNumber", "ACTION_NUMBER", default=len(events))),
                period=int(_get(raw, "period", "PERIOD", default=1)),
                clock_seconds=parse_clock_seconds(_get(raw, "clock", "CLOCK", default=0)),
                home_score=home_score,
                away_score=away_score,
                team=(
                    str(_get(raw, "teamTricode", "TEAM_TRICODE"))
                    if _get(raw, "teamTricode", "TEAM_TRICODE") not in (None, "")
                    else None
                ),
                description=str(_get(raw, "description", "DESCRIPTION", default="")),
                action_type=str(_get(raw, "actionType", "ACTION_TYPE", default="")),
                sub_type=str(_get(raw, "subType", "SUB_TYPE", default="")),
            )
        )

    events.sort(key=lambda event: event.action_number)
    return ReplaySnapshot(game_id=game_id, events=tuple(events), source="nba_playbyplay_v3")


def load_replay_snapshot(path: str | Path) -> ReplaySnapshot:
    return parse_playbyplay_v3(json.loads(Path(path).read_text()))


def load_replay_directory(path: str | Path) -> dict[str, ReplaySnapshot]:
    directory = Path(path)
    if not directory.exists():
        return {}
    snapshots = {}
    for file in sorted(directory.glob("*.json")):
        try:
            snapshot = load_replay_snapshot(file)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        snapshots[snapshot.game_id] = snapshot
    return snapshots
