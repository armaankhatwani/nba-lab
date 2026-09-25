from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .domain import Game


def _as_date(value: str) -> date:
    text = value[:10]
    return datetime.strptime(text, "%Y-%m-%d").date()


def _parse_cdn(schedule: dict[str, Any], regular_season_only: bool) -> list[Game]:
    dates = schedule.get("gameDates")
    if not isinstance(dates, list):
        return []
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
            games.append(Game(
                game_id=game_id,
                game_date=_as_date(str(date_value)),
                home_team=str(home_team),
                away_team=str(away_team),
                home_score=int(home_score) if home_score not in (None, "") else None,
                away_score=int(away_score) if away_score not in (None, "") else None,
            ))
    return games


def _parse_normalized(rows: list[dict[str, Any]], regular_season_only: bool) -> list[Game]:
    games: list[Game] = []
    for raw in rows:
        game_id = str(raw.get("gameId") or "")
        if regular_season_only and not game_id.startswith("002"):
            continue
        home_team = raw.get("homeTeam_teamTricode")
        away_team = raw.get("awayTeam_teamTricode")
        if not game_id or not home_team or not away_team:
            continue
        date_value = raw.get("gameDateEst") or raw.get("gameDateTimeEst") or raw.get("gameDate")
        if not date_value:
            raise ValueError(f"game {game_id} is missing a date")
        final = int(raw.get("gameStatus") or 0) == 3
        home_score = raw.get("homeTeam_score") if final else None
        away_score = raw.get("awayTeam_score") if final else None
        games.append(Game(
            game_id=game_id,
            game_date=_as_date(str(date_value)),
            home_team=str(home_team),
            away_team=str(away_team),
            home_score=int(home_score) if home_score not in (None, "") else None,
            away_score=int(away_score) if away_score not in (None, "") else None,
        ))
    return games


def parse_schedule_league_v2(payload: dict[str, Any], regular_season_only: bool = True) -> list[Game]:
    """Normalize official ScheduleLeagueV2 payloads into NBA Lab games.

    Supported forms:
    - NBA CDN nested shape: leagueSchedule.gameDates[].games[]
    - nba_api normalized shape: SeasonGames[] with flattened homeTeam_/awayTeam_ keys
    """
    schedule = payload.get("leagueSchedule", payload)
    games = _parse_cdn(schedule, regular_season_only)
    if not games:
        rows = payload.get("SeasonGames") or payload.get("season_games")
        if isinstance(rows, list):
            games = _parse_normalized(rows, regular_season_only)
    games.sort(key=lambda game: (game.game_date, game.game_id))
    if not games:
        raise ValueError("no regular-season games found in ScheduleLeagueV2 payload")
    return games


def load_snapshot(path: str | Path) -> list[Game]:
    return parse_schedule_league_v2(json.loads(Path(path).read_text()))
