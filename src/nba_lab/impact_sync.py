from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path

from .impact import Stint
from .source import load_snapshot


def possession_to_stint(possession, home_team_id: int, away_team_id: int) -> Stint | None:
    """Convert one pbpstats possession into a substitution-free RAPM row."""
    if not getattr(possession, "events", None):
        return None

    lineup_maps = []
    for event in possession.events:
        try:
            lineups = event.lineup_ids
        except Exception:
            return None
        if home_team_id not in lineups or away_team_id not in lineups:
            return None
        lineup_maps.append((lineups[home_team_id], lineups[away_team_id]))

    if not lineup_maps or len(set(lineup_maps)) != 1:
        return None

    home_lineup = tuple(lineup_maps[0][0].split("-"))
    away_lineup = tuple(lineup_maps[0][1].split("-"))
    if len(home_lineup) != 5 or len(away_lineup) != 5:
        return None
    if len(set(home_lineup)) != 5 or len(set(away_lineup)) != 5:
        return None
    if set(home_lineup) & set(away_lineup):
        return None

    previous = getattr(possession, "previous_possession", None)
    if previous is None:
        start_home = start_away = 0.0
    else:
        start_score = previous.events[-1].score
        start_home = float(start_score.get(home_team_id, 0))
        start_away = float(start_score.get(away_team_id, 0))

    end_score = possession.events[-1].score
    end_home = float(end_score.get(home_team_id, start_home))
    end_away = float(end_score.get(away_team_id, start_away))

    return Stint(
        game_id=str(possession.game_id),
        possessions=1.0,
        point_diff=(end_home - start_home) - (end_away - start_away),
        home_players=home_lineup,
        away_players=away_lineup,
    )


def build_impact_snapshot(
    schedule_path: str | Path,
    output_path: str | Path,
    pbp_dir: str | Path,
    source: str = "file",
    max_games: int | None = None,
):
    """Build NBA Lab's normalized impact snapshot using pbpstats."""
    try:
        from pbpstats.client import Client
    except ImportError as exc:
        raise RuntimeError("Install impact extras: pip install -e '.[impact]'") from exc

    games = [g for g in load_snapshot(schedule_path) if g.is_final]
    if max_games is not None:
        games = games[:max_games]

    settings = {
        "dir": str(pbp_dir),
        "Boxscore": {"source": source, "data_provider": "stats_nba"},
        "Possessions": {"source": source, "data_provider": "data_nba"},
    }
    client = Client(settings)
    players = {}
    stints = []
    qa = defaultdict(int)

    for schedule_game in games:
        qa["games_attempted"] += 1
        try:
            game = client.Game(schedule_game.game_id)
        except Exception:
            qa["games_failed"] += 1
            continue

        tricode_to_id = {}
        for item in game.boxscore.player_items:
            pid = str(item["player_id"])
            tricode = str(item["team_abbreviation"])
            team_id = int(item["team_id"])
            tricode_to_id[tricode] = team_id
            players[pid] = {
                "player_id": pid,
                "player_name": str(item["name"]),
                "team": tricode,
            }

        home_id = tricode_to_id.get(schedule_game.home_team)
        away_id = tricode_to_id.get(schedule_game.away_team)
        if home_id is None or away_id is None:
            qa["games_missing_team_map"] += 1
            continue

        qa["games_loaded"] += 1
        for possession in game.possessions.items:
            qa["possessions_seen"] += 1
            stint = possession_to_stint(possession, home_id, away_id)
            if stint is None:
                qa["possessions_skipped"] += 1
                continue
            qa["possessions_kept"] += 1
            row = asdict(stint)
            row["game_date"] = schedule_game.game_date.isoformat()
            stints.append(row)

    payload = {
        "source": "pbpstats_possessions",
        "players": sorted(players.values(), key=lambda row: (row["team"], row["player_name"])),
        "stints": stints,
        "qa": dict(qa),
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))
    return payload
