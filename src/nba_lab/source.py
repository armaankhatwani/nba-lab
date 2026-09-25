from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .domain import Game


def _as_date(value: str) -> date:
    text = value[:10]
    return datetime.strptime(text, "%Y-%m-%d").date()


def parse_schedule_league_v2(payload: dict[str, Any], regular_season_only: bool = True) -> list[Game]:
    """Normalize the NBA scheduleLeagueV2 JSON into NBA Lab games.

    Supports the official CDN shape: leagueSchedule.gameDates[].games[].
    Only status=3 games are treated as final; future/live scores never leak into
    the point-in-time model as finals.
    """
    schedule = payload.get("leagueSchedule", payload)
    dates = schedule.get("gameDates")
    if not isinstance(dates, list):
        raise ValueError("scheduleLeagueV2 payload is missing leagueSchedule.gameDates")

    games: list[Game] = []
    for block in dates:
        for raw in block.get("games", []):
            label = raw.get("gameLabel") or raw.get("gameSubtype") or ""
            game_id = str(raw.get("gameId") or "")
            if regular_season_only and not game_id.startswith("002"):
                continue
            if regular_season_only and label and "preseason" in label.lower():
                continue
            home = raw.get("homeTeam") or {}
            away = raw.get("awayTeam") or {}
            home_team = home.get("teamTricode")
            away_team = away.get("teamTricode")
            if not game_id or not home_team or not away_team:
                continue
            date_value = raw.get("gameDateEst") or raw.get("gameDateTimeEst") or block.get("gameDate")
            if not date_value:
                raise ValueError(f"game {game_id} is missing a date")
            final = int(raw.get("gameStatus") or 0) == 3
            home_score = home.get("score") if final else None
            away_score = away.get("score") if final else None
            games.append(
                Game(
                    game_id=game_id,
                    game_date=_as_date(str(date_value)),
                    home_team=str(home_team),
                    away_team=str(away_team),
                    home_score=int(home_score) if home_score not in (None, "") else None,
                    away_score=int(away_score) if away_score not in (None, "") else None,
                )
            )
    games.sort(key=lambda game: (game.game_date, game.game_id))
    if not games:
        raise ValueError("no regular-season games found in scheduleLeagueV2 payload")
    return games


def load_snapshot(path: str | Path) -> list[Game]:
    return parse_schedule_league_v2(json.loads(Path(path).read_text()))
