"""Fetch and freeze the NBA's official scheduleLeagueV2 payload.

Run on a normal residential/local network if stats.nba.com/CDN blocks your host.
The raw payload is intentionally preserved so future parser changes remain auditable.
"""

from argparse import ArgumentParser
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def main():
    parser = ArgumentParser()
    parser.add_argument("output", nargs="?", default="data/scheduleLeagueV2.json")
    args = parser.parse_args()
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        content = response.read()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(f"wrote {len(content):,} bytes to {path}")


if __name__ == "__main__":
    main()
