import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

CURRENT_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def sync():
    """Freeze an official NBA ScheduleLeagueV2 payload locally."""
    parser = argparse.ArgumentParser(prog="nba-lab-sync")
    parser.add_argument("--season", help="Historical season such as 2025-26. Requires nba_api.")
    parser.add_argument("--output", default="data/scheduleLeagueV2.json")
    args = parser.parse_args()

    if args.season:
        try:
            from nba_api.stats.endpoints import ScheduleLeagueV2
        except ImportError as exc:
            raise SystemExit("Install the data extra first: pip install -e '.[data]'") from exc
        endpoint = ScheduleLeagueV2(league_id="00", season=args.season, timeout=60)
        payload = endpoint.get_normalized_dict()
        content = json.dumps(payload, indent=2).encode()
        source = f"NBA Stats ScheduleLeagueV2 season={args.season}"
    else:
        request = Request(CURRENT_SCHEDULE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=45) as response:
            content = response.read()
        source = "NBA CDN current ScheduleLeagueV2"

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    print(f"Wrote {len(content):,} bytes to {target} from {source}")


def main():
    import uvicorn
    uvicorn.run("nba_lab.web:app", host="127.0.0.1", port=8765, reload=False)


def sync_awards():
    """Freeze official NBA PlayerGameLogs for one season."""
    parser = argparse.ArgumentParser(prog="nba-lab-sync-awards")
    parser.add_argument("--season", required=True, help="Season such as 2025-26")
    parser.add_argument("--output", default="data/playerGameLogs.json")
    args = parser.parse_args()
    try:
        from nba_api.stats.endpoints import PlayerGameLogs
    except ImportError as exc:
        raise SystemExit("Install the data extra first: pip install -e '.[data]'") from exc
    endpoint = PlayerGameLogs(
        season_nullable=args.season,
        season_type_nullable="Regular Season",
        timeout=60,
    )
    payload = endpoint.get_normalized_dict()
    content = json.dumps(payload, indent=2).encode()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    print(f"Wrote {len(content):,} bytes to {target} from NBA PlayerGameLogs season={args.season}")


def sync_impact():
    """Build normalized RAPM observations from pbpstats possessions."""
    parser = argparse.ArgumentParser(prog="nba-lab-sync-impact")
    parser.add_argument("--schedule", default="data/scheduleLeagueV2.json")
    parser.add_argument("--output", default="data/impact_stints.json")
    parser.add_argument("--pbp-dir", default="data/pbpstats")
    parser.add_argument("--source", choices=["file", "web"], default="file")
    parser.add_argument("--max-games", type=int)
    parser.add_argument("--team", action="append", help="Only include games involving this team; repeatable")
    args = parser.parse_args()

    from .impact_sync import build_impact_snapshot

    payload = build_impact_snapshot(
        schedule_path=args.schedule,
        output_path=args.output,
        pbp_dir=args.pbp_dir,
        source=args.source,
        max_games=args.max_games,
        teams=set(args.team or []),
    )
    qa = payload.get("qa", {})
    print(
        f"Wrote {len(payload['stints']):,} impact observations to {args.output}; "
        f"kept {qa.get('possessions_kept', 0):,} / {qa.get('possessions_seen', 0):,} possessions"
    )


def sync_replay():
    """Freeze official NBA PlayByPlayV3 snapshots for selected games."""
    parser = argparse.ArgumentParser(prog="nba-lab-sync-replay")
    parser.add_argument("--game-id", action="append", required=True, help="NBA game id; repeat for multiple games")
    parser.add_argument("--output-dir", default="data/replay")
    args = parser.parse_args()
    try:
        from nba_api.stats.endpoints import PlayByPlayV3
    except ImportError as exc:
        raise SystemExit("Install the data extra first: pip install -e '.[data]'") from exc

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for game_id in args.game_id:
        endpoint = PlayByPlayV3(game_id=game_id, timeout=60)
        payload = endpoint.get_normalized_dict()
        content = json.dumps(payload, indent=2).encode()
        target = output_dir / f"{game_id}.json"
        target.write_bytes(content)
        print(f"Wrote {len(content):,} bytes to {target}")



def sync_bundle():
    """Freeze a reproducible multi-lab season data bundle."""
    parser = argparse.ArgumentParser(prog="nba-lab-sync-bundle")
    parser.add_argument("--season", required=True, help="Season such as 2025-26")
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--replay-count", type=int, default=8)
    parser.add_argument("--replay-team", action="append", help="Limit replay selection to games involving this team; repeatable")
    parser.add_argument("--impact-games", type=int, default=0, help="Build RAPM data from this many selected games; 0 skips")
    parser.add_argument("--impact-source", choices=["file", "web"], default="web")
    parser.add_argument("--impact-team", action="append", help="Limit RAPM ingestion to games involving this team; repeatable")
    args = parser.parse_args()

    from .data_bundle import sync_season_bundle

    manifest = sync_season_bundle(
        season=args.season,
        output_dir=args.output_dir,
        replay_count=args.replay_count,
        replay_teams=set(args.replay_team or []),
        impact_games=args.impact_games,
        impact_source=args.impact_source,
        impact_teams=set(args.impact_team or []),
    )
    replay_ok = sum(row.get("status") == "ok" for row in manifest["replays"])
    replay_failed = sum(row.get("status") == "error" for row in manifest["replays"])
    print(
        f"NBA Lab bundle {args.season}: "
        f"{manifest['schedule']['games']:,} schedule games, "
        f"{replay_ok} replay snapshots ({replay_failed} failed), "
        f"impact={manifest['impact']['status']}"
    )
    print(f"Manifest: {args.output_dir}/nba_lab_bundle_manifest.json")



def doctor():
    """Verify the frozen NBA Lab bundle and print data readiness."""
    parser = argparse.ArgumentParser(prog="nba-lab-doctor")
    parser.add_argument(
        "--manifest",
        default="data/nba_lab_bundle_manifest.json",
    )
    args = parser.parse_args()

    from .data_bundle import verify_bundle_manifest

    report = verify_bundle_manifest(args.manifest)
    if report.get("error"):
        print(f"NBA Lab data check: FAIL — {report['error']}")
        raise SystemExit(1)

    for row in report["artifacts"]:
        marker = "OK" if row["status"] == "ok" else "FAIL"
        print(f"[{marker}] {row['name']}: {row['status']} · {row.get('path')}")
    if report["valid"]:
        print(
            f"NBA Lab data check: PASS · season={report.get('season')} · "
            f"{len(report['artifacts'])} artifacts verified"
        )
        return
    print("NBA Lab data check: FAIL — one or more artifacts did not match the manifest")
    raise SystemExit(1)
