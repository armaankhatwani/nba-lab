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
