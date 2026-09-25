from pathlib import Path
from urllib.request import Request, urlopen

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def sync():
    """Freeze the current official NBA scheduleLeagueV2 payload locally."""
    target = Path("data/scheduleLeagueV2.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(SCHEDULE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        payload = response.read()
    target.write_bytes(payload)
    print(f"Wrote {len(payload):,} bytes to {target}")


def main():
    import uvicorn

    uvicorn.run("nba_lab.web:app", host="127.0.0.1", port=8765, reload=False)
