from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Iterable

from .domain import Game
from .source import parse_schedule_league_v2


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def write_json_artifact(path: str | Path, payload: dict) -> dict:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = _json_bytes(payload)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(target)
    return {
        "path": str(target),
        "bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }


def select_replay_games(
    games: Iterable[Game],
    count: int = 8,
    teams: set[str] | None = None,
) -> list[Game]:
    """Pick close completed games, preferring newer games within the same margin."""
    if count < 0:
        raise ValueError("count must be non-negative")
    team_filter = {team.upper() for team in (teams or set())}
    rows = []
    for game in games:
        if not game.is_final:
            continue
        if team_filter and not ({game.home_team, game.away_team} & team_filter):
            continue
        margin = abs(int(game.home_score) - int(game.away_score))
        rows.append((margin, -game.game_date.toordinal(), game.game_id, game))
    rows.sort(key=lambda row: row[:3])
    return [row[-1] for row in rows[:count]]


def _fetch_schedule(season: str) -> dict:
    try:
        from nba_api.stats.endpoints import ScheduleLeagueV2
    except ImportError as exc:
        raise RuntimeError("Install the data extra: pip install -e '.[data]'") from exc
    return ScheduleLeagueV2(
        league_id="00",
        season=season,
        timeout=60,
    ).get_normalized_dict()


def _fetch_player_logs(season: str) -> dict:
    try:
        from nba_api.stats.endpoints import PlayerGameLogs
    except ImportError as exc:
        raise RuntimeError("Install the data extra: pip install -e '.[data]'") from exc
    return PlayerGameLogs(
        season_nullable=season,
        season_type_nullable="Regular Season",
        timeout=60,
    ).get_normalized_dict()


def _fetch_replay(game_id: str) -> dict:
    try:
        from nba_api.stats.endpoints import PlayByPlayV3
    except ImportError as exc:
        raise RuntimeError("Install the data extra: pip install -e '.[data]'") from exc
    return PlayByPlayV3(game_id=game_id, timeout=60).get_normalized_dict()


def sync_season_bundle(
    season: str,
    output_dir: str | Path = "data",
    replay_count: int = 8,
    replay_teams: set[str] | None = None,
    impact_games: int = 0,
    impact_source: str = "web",
    impact_teams: set[str] | None = None,
    schedule_fetcher: Callable[[str], dict] | None = None,
    player_logs_fetcher: Callable[[str], dict] | None = None,
    replay_fetcher: Callable[[str], dict] | None = None,
    impact_builder: Callable | None = None,
) -> dict:
    """Freeze a reproducible NBA Lab data bundle.

    Core schedule/player logs are required. Replay failures are recorded per game
    without discarding successful artifacts. Impact ingestion is optional because
    pbpstats downloads are much heavier than the NBA Stats snapshots.
    """
    if not season:
        raise ValueError("season is required")
    if replay_count < 0:
        raise ValueError("replay_count must be non-negative")
    if impact_games < 0:
        raise ValueError("impact_games must be non-negative")
    if impact_source not in {"file", "web"}:
        raise ValueError("impact_source must be file or web")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    replay_dir = root / "replay"
    replay_dir.mkdir(parents=True, exist_ok=True)

    schedule_fetcher = schedule_fetcher or _fetch_schedule
    player_logs_fetcher = player_logs_fetcher or _fetch_player_logs
    replay_fetcher = replay_fetcher or _fetch_replay

    schedule_payload = schedule_fetcher(season)
    schedule_artifact = write_json_artifact(
        root / "scheduleLeagueV2.json",
        schedule_payload,
    )
    games = parse_schedule_league_v2(schedule_payload)

    awards_payload = player_logs_fetcher(season)
    awards_artifact = write_json_artifact(
        root / "playerGameLogs.json",
        awards_payload,
    )

    replay_candidates = select_replay_games(
        games,
        count=replay_count,
        teams=replay_teams,
    )
    replay_reports = []
    for game in replay_candidates:
        try:
            payload = replay_fetcher(game.game_id)
            artifact = write_json_artifact(
                replay_dir / f"{game.game_id}.json",
                payload,
            )
            replay_reports.append({
                "game_id": game.game_id,
                "game_date": game.game_date.isoformat(),
                "home_team": game.home_team,
                "away_team": game.away_team,
                "margin": abs(int(game.home_score) - int(game.away_score)),
                "status": "ok",
                **artifact,
            })
        except Exception as exc:
            replay_reports.append({
                "game_id": game.game_id,
                "game_date": game.game_date.isoformat(),
                "home_team": game.home_team,
                "away_team": game.away_team,
                "margin": abs(int(game.home_score) - int(game.away_score)),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })

    impact_report = {"status": "skipped", "games_requested": impact_games}
    if impact_games:
        if impact_builder is None:
            from .impact_sync import build_impact_snapshot
            impact_builder = build_impact_snapshot
        try:
            payload = impact_builder(
                schedule_path=root / "scheduleLeagueV2.json",
                output_path=root / "impact_stints.json",
                pbp_dir=root / "pbpstats",
                source=impact_source,
                max_games=impact_games,
                teams=impact_teams,
            )
            impact_path = root / "impact_stints.json"
            content = impact_path.read_bytes()
            impact_report = {
                "status": "ok",
                "games_requested": impact_games,
                "teams": sorted(impact_teams or set()),
                "stints": len(payload.get("stints", [])),
                "qa": payload.get("qa", {}),
                "path": str(impact_path),
                "bytes": len(content),
                "sha256": sha256(content).hexdigest(),
            }
        except Exception as exc:
            impact_report = {
                "status": "error",
                "games_requested": impact_games,
                "teams": sorted(impact_teams or set()),
                "error": f"{type(exc).__name__}: {exc}",
            }

    manifest = {
        "schema_version": 1,
        "season": season,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schedule": {
            **schedule_artifact,
            "games": len(games),
            "final_games": sum(game.is_final for game in games),
        },
        "awards": awards_artifact,
        "replays": replay_reports,
        "impact": impact_report,
        "selection": {
            "replay_count": replay_count,
            "replay_teams": sorted(replay_teams or set()),
            "impact_games": impact_games,
            "impact_source": impact_source,
            "impact_teams": sorted(impact_teams or set()),
        },
    }
    manifest_artifact = write_json_artifact(
        root / "nba_lab_bundle_manifest.json",
        manifest,
    )
    manifest["manifest_artifact"] = manifest_artifact
    return manifest


def load_bundle_manifest(path: str | Path = "data/nba_lab_bundle_manifest.json") -> dict | None:
    """Load a season bundle manifest without requiring every artifact to exist."""
    target = Path(path)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid NBA Lab bundle manifest: {target}") from exc
    if payload.get("schema_version") != 1:
        raise ValueError(
            f"unsupported NBA Lab bundle schema: {payload.get('schema_version')}"
        )
    if not payload.get("season"):
        raise ValueError("NBA Lab bundle manifest is missing season")
    return payload


def bundle_summary(path: str | Path = "data/nba_lab_bundle_manifest.json") -> dict:
    """Return lightweight bundle readiness metadata for the UI/status endpoint."""
    manifest = load_bundle_manifest(path)
    if manifest is None:
        return {"kind": "none"}

    replay_rows = manifest.get("replays") or []
    replay_ok = sum(row.get("status") == "ok" for row in replay_rows)
    replay_errors = sum(row.get("status") == "error" for row in replay_rows)
    impact = manifest.get("impact") or {}
    schedule = manifest.get("schedule") or {}
    awards = manifest.get("awards") or {}
    return {
        "kind": "bundle_manifest",
        "schema_version": manifest["schema_version"],
        "season": manifest["season"],
        "created_at": manifest.get("created_at"),
        "schedule_games": schedule.get("games"),
        "schedule_final_games": schedule.get("final_games"),
        "schedule_path": schedule.get("path"),
        "awards_path": awards.get("path"),
        "replay_ok": replay_ok,
        "replay_errors": replay_errors,
        "impact_status": impact.get("status", "unknown"),
        "impact_stints": impact.get("stints"),
        "selection": manifest.get("selection") or {},
        "manifest_path": str(path),
    }


def verify_bundle_manifest(
    path: str | Path = "data/nba_lab_bundle_manifest.json",
) -> dict:
    """Verify manifest-tracked bundle artifacts by SHA-256."""
    manifest = load_bundle_manifest(path)
    if manifest is None:
        return {
            "valid": False,
            "manifest": str(path),
            "error": "bundle manifest not found",
            "artifacts": [],
        }

    tracked = [
        ("schedule", manifest.get("schedule") or {}),
        ("awards", manifest.get("awards") or {}),
    ]
    for row in manifest.get("replays") or []:
        if row.get("status") == "ok":
            tracked.append((f"replay:{row.get('game_id')}", row))
    impact = manifest.get("impact") or {}
    if impact.get("status") == "ok":
        tracked.append(("impact", impact))

    reports = []
    for name, artifact in tracked:
        artifact_path = artifact.get("path")
        expected = artifact.get("sha256")
        if not artifact_path or not expected:
            reports.append({
                "name": name,
                "path": artifact_path,
                "status": "manifest_missing_hash",
            })
            continue
        target = Path(artifact_path)
        if not target.exists():
            reports.append({
                "name": name,
                "path": str(target),
                "status": "missing",
                "expected_sha256": expected,
            })
            continue
        content = target.read_bytes()
        actual = sha256(content).hexdigest()
        reports.append({
            "name": name,
            "path": str(target),
            "status": "ok" if actual == expected else "hash_mismatch",
            "expected_sha256": expected,
            "actual_sha256": actual,
            "bytes": len(content),
        })

    return {
        "valid": bool(reports) and all(row["status"] == "ok" for row in reports),
        "manifest": str(path),
        "season": manifest["season"],
        "artifacts": reports,
    }
