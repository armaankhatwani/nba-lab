from __future__ import annotations

import random

from .impact import Stint
from .impact_source import ImpactPlayer, ImpactSnapshot


_TEAMS=("NYK","BOS","OKC","DEN")


def synthetic_impact_snapshot(seed:int=2026)->ImpactSnapshot:
    """Deterministic synthetic RAPM fixture. Never present as NBA player truth."""
    rng=random.Random(seed)
    players={}
    latent={}
    for t_i,team in enumerate(_TEAMS):
        for i in range(8):
            pid=f"demo-{team}-{i+1}"
            players[pid]=ImpactPlayer(pid,f"Demo {team} Player {i+1}",team)
            # Enough variation to make shrinkage and recovery visible.
            latent[pid]=3.5-0.85*i+0.25*t_i

    stints=[]
    game_no=1
    for home_i,home in enumerate(_TEAMS):
        for away in _TEAMS[home_i+1:]:
            for repeat in range(6):
                game_id=f"impact-demo-{game_no:03d}"
                game_no+=1
                home_pool=[p for p,m in players.items() if m.team==home]
                away_pool=[p for p,m in players.items() if m.team==away]
                for _ in range(18):
                    hp=tuple(sorted(rng.sample(home_pool,5)))
                    ap=tuple(sorted(rng.sample(away_pool,5)))
                    poss=rng.randint(4,14)
                    expected=2.2+sum(latent[p] for p in hp)-sum(latent[p] for p in ap)
                    point_diff=expected*poss/100+rng.gauss(0,0.85*(poss**0.5))
                    stints.append(Stint(
                        game_id=game_id,
                        possessions=float(poss),
                        point_diff=float(point_diff),
                        home_players=hp,
                        away_players=ap,
                    ))
    return ImpactSnapshot(
        stints=tuple(stints),
        players=players,
        source="synthetic_impact_demo",
        qa={"possessions_seen": len(stints), "possessions_kept": len(stints), "possessions_skipped": 0},
    )
