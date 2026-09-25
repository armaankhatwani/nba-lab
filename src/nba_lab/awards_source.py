from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .awards import PlayerGame


def _date(value: str):
    text=value[:10]
    for fmt in ("%Y-%m-%d","%b %d, %Y","%m/%d/%Y"):
        try:
            return datetime.strptime(text,fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported player game date: {value}")


def parse_player_game_logs(payload: dict[str, Any]) -> list[PlayerGame]:
    rows = payload.get("PlayerGameLogs") or payload.get("player_game_logs")
    if not isinstance(rows,list):
        raise ValueError("PlayerGameLogs payload is missing rows")
    result=[]
    for row in rows:
        result.append(PlayerGame(
            game_id=str(row["GAME_ID"]),
            game_date=_date(str(row["GAME_DATE"])),
            player_id=str(row["PLAYER_ID"]),
            player_name=str(row["PLAYER_NAME"]),
            team=str(row["TEAM_ABBREVIATION"]),
            minutes=float(row.get("MIN") or 0),
            points=float(row.get("PTS") or 0),
            rebounds=float(row.get("REB") or 0),
            assists=float(row.get("AST") or 0),
            steals=float(row.get("STL") or 0),
            blocks=float(row.get("BLK") or 0),
            turnovers=float(row.get("TOV") or 0),
            fga=float(row.get("FGA") or 0),
            fta=float(row.get("FTA") or 0),
        ))
    result.sort(key=lambda x:(x.game_date,x.game_id,x.player_id))
    return result


def load_player_logs(path: str | Path) -> list[PlayerGame]:
    return parse_player_game_logs(json.loads(Path(path).read_text()))
