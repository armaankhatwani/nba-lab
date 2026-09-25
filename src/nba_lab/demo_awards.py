from __future__ import annotations

from collections import defaultdict
import random

from .awards import PlayerGame
from .domain import Game


_PROFILES = [
    ("203999","Nikola Jokic","DEN",30.2,12.4,10.1,1.4,.8,3.3,18.8,6.4,35.5),
    ("1628983","Shai Gilgeous-Alexander","OKC",32.1,5.3,6.5,1.7,1.0,2.5,20.6,9.2,34.8),
    ("1629029","Luka Doncic","LAL",29.4,8.7,8.9,1.4,.5,4.0,21.1,8.8,35.9),
    ("203507","Giannis Antetokounmpo","MIL",30.8,11.6,6.2,1.1,1.1,3.5,19.9,11.0,34.2),
    ("1628369","Jayson Tatum","BOS",27.5,8.4,5.4,1.1,.7,2.8,20.0,7.2,36.3),
    ("1630162","Anthony Edwards","MIN",27.8,5.8,4.9,1.3,.6,3.0,21.0,6.8,36.0),
    ("1641705","Victor Wembanyama","SAS",25.9,11.1,4.2,1.2,3.1,3.2,18.9,7.5,33.7),
    ("1630595","Cade Cunningham","DET",26.6,6.1,8.8,1.0,.6,4.1,20.5,6.0,35.1),
]


def synthetic_player_games(games: list[Game], seed: int = 2026) -> list[PlayerGame]:
    """Deterministic synthetic star logs for offline UI/testing only."""
    by_team=defaultdict(list)
    for game in games:
        if game.is_final:
            by_team[game.home_team].append(game)
            by_team[game.away_team].append(game)
    rng=random.Random(seed)
    rows=[]
    for pid,name,team,pts,reb,ast,stl,blk,tov,fga,fta,minutes in _PROFILES:
        for game in sorted(by_team.get(team,[]), key=lambda g:(g.game_date,g.game_id)):
            # Small deterministic noise keeps the replay visually interesting.
            scale=max(.78,min(1.22,rng.gauss(1.0,.08)))
            rows.append(PlayerGame(
                game_id=game.game_id,
                game_date=game.game_date,
                player_id=pid,
                player_name=name,
                team=team,
                minutes=max(24.0,minutes+rng.gauss(0,2)),
                points=max(0,pts*scale+rng.gauss(0,3)),
                rebounds=max(0,reb*scale+rng.gauss(0,1.5)),
                assists=max(0,ast*scale+rng.gauss(0,1.2)),
                steals=max(0,stl+rng.gauss(0,.35)),
                blocks=max(0,blk+rng.gauss(0,.35)),
                turnovers=max(0,tov+rng.gauss(0,.6)),
                fga=max(1,fga*scale+rng.gauss(0,2)),
                fta=max(0,fta*scale+rng.gauss(0,1.4)),
            ))
    return rows
