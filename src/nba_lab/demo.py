from datetime import date, timedelta
import random

from .domain import Game
from .teams import TEAMS


# Deliberately synthetic fallback. Real runs should use a frozen scheduleLeagueV2
# snapshot from scripts/sync_nba_schedule.py.
def synthetic_demo_games(seed: int = 2026) -> list[Game]:
    teams = sorted(TEAMS)
    rng = random.Random(seed)
    start = date(2025, 10, 21)
    strengths = {team: 1500 + rng.randint(-140, 140) for team in teams}
    games: list[Game] = []
    game_number = 1
    day = 0
    # Double round robin: 870 games, 58 per team. This is not an NBA schedule.
    for cycle in range(2):
        for i, home in enumerate(teams):
            for away in teams[i + 1 :]:
                h, a = (home, away) if cycle == 0 else (away, home)
                game_date = start + timedelta(days=day // 6)
                diff = strengths[h] + 65 - strengths[a]
                home_win = rng.random() < 1 / (1 + 10 ** (-diff / 400))
                margin = rng.randint(1, 18)
                base = rng.randint(98, 121)
                if home_win:
                    hs, as_ = base + margin, base
                else:
                    hs, as_ = base, base + margin
                games.append(Game(f"demo-{game_number:04d}", game_date, h, a, hs, as_))
                game_number += 1
                day += 1
    return games
