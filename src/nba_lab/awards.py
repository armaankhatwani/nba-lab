from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from math import exp

from .domain import Game


@dataclass(frozen=True)
class PlayerGame:
    game_id: str
    game_date: date
    player_id: str
    player_name: str
    team: str
    minutes: float
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float
    fga: float
    fta: float


@dataclass(frozen=True)
class AwardCandidate:
    player_id: str
    player_name: str
    team: str
    games: int
    team_games: int
    ppg: float
    rpg: float
    apg: float
    spg: float
    bpg: float
    topg: float
    true_shooting: float
    team_win_pct: float
    availability: float
    eligibility_status: str
    race_score: float
    race_share: float
    feature_scores: dict[str, float]


@dataclass(frozen=True)
class AwardRace:
    as_of: date
    award: str
    candidates: tuple[AwardCandidate, ...]


def _observed_team_records(games: list[Game], as_of: date):
    wins = defaultdict(int)
    played = defaultdict(int)
    for game in games:
        if not game.is_final or game.game_date > as_of:
            continue
        played[game.home_team] += 1
        played[game.away_team] += 1
        wins[game.winner] += 1
    return wins, played


def _percentile(values: list[float], value: float, higher_is_better: bool = True) -> float:
    if len(values) <= 1:
        return 0.5
    if higher_is_better:
        below = sum(v < value for v in values)
        tied = sum(v == value for v in values)
    else:
        below = sum(v > value for v in values)
        tied = sum(v == value for v in values)
    return (below + 0.5 * tied) / len(values)


def _eligibility_status(gp: int, team_games: int, total_team_games: int = 82) -> str:
    if gp >= 65:
        return "eligible"
    remaining = max(0, total_team_games - team_games)
    if gp + remaining < 65:
        return "ineligible"
    if team_games == 0:
        return "unknown"
    projected = gp / team_games * total_team_games
    return "on_track" if projected >= 65 else "at_risk"


def build_award_race(
    games: list[Game],
    player_games: list[PlayerGame],
    as_of: date,
    award: str = "MVP",
    min_games: int | None = None,
) -> AwardRace:
    if award != "MVP":
        raise ValueError("only MVP is implemented in the first Awards Lab baseline")

    team_wins, team_played = _observed_team_records(games, as_of)
    grouped: dict[str, list[PlayerGame]] = defaultdict(list)
    for row in player_games:
        if row.game_date <= as_of:
            grouped[row.player_id].append(row)

    raw = []
    for player_id, rows in grouped.items():
        gp = len(rows)
        team = rows[-1].team
        tg = team_played[team]
        threshold = min_games if min_games is not None else max(5, int(tg * 0.35))
        mean_minutes = sum(r.minutes for r in rows) / gp
        if gp < threshold or mean_minutes < 20:
            continue
        pts = sum(r.points for r in rows)
        reb = sum(r.rebounds for r in rows)
        ast = sum(r.assists for r in rows)
        stl = sum(r.steals for r in rows)
        blk = sum(r.blocks for r in rows)
        tov = sum(r.turnovers for r in rows)
        fga = sum(r.fga for r in rows)
        fta = sum(r.fta for r in rows)
        ts_denom = 2 * (fga + 0.44 * fta)
        raw.append({
            "player_id": player_id,
            "player_name": rows[-1].player_name,
            "team": team,
            "games": gp,
            "team_games": tg,
            "ppg": pts / gp,
            "rpg": reb / gp,
            "apg": ast / gp,
            "spg": stl / gp,
            "bpg": blk / gp,
            "topg": tov / gp,
            "true_shooting": pts / ts_denom if ts_denom else 0.0,
            "team_win_pct": team_wins[team] / tg if tg else 0.0,
            "availability": gp / tg if tg else 0.0,
            "eligibility_status": _eligibility_status(gp, tg),
        })

    if not raw:
        return AwardRace(as_of=as_of, award=award, candidates=())

    ppgs=[r["ppg"] for r in raw]; rpgs=[r["rpg"] for r in raw]; apgs=[r["apg"] for r in raw]
    defenses=[r["spg"] + r["bpg"] for r in raw]; tss=[r["true_shooting"] for r in raw]
    wins=[r["team_win_pct"] for r in raw]; avails=[r["availability"] for r in raw]; tovs=[r["topg"] for r in raw]

    scored=[]
    for row in raw:
        features={
            "scoring": _percentile(ppgs,row["ppg"]),
            "rebounding": _percentile(rpgs,row["rpg"]),
            "playmaking": _percentile(apgs,row["apg"]),
            "defense": _percentile(defenses,row["spg"]+row["bpg"]),
            "efficiency": _percentile(tss,row["true_shooting"]),
            "team_success": _percentile(wins,row["team_win_pct"]),
            "availability": _percentile(avails,row["availability"]),
            "ball_security": _percentile(tovs,row["topg"],higher_is_better=False),
        }
        score=100*(
            .34*features["scoring"] + .16*features["playmaking"] + .10*features["rebounding"]
            + .08*features["defense"] + .12*features["efficiency"] + .14*features["team_success"]
            + .04*features["availability"] + .02*features["ball_security"]
        )
        row["race_score"]=score
        row["feature_scores"]=features
        scored.append(row)

    logits=[exp((r["race_score"]-70)/8) for r in scored]
    denom=sum(logits)
    candidates=[]
    for row,logit in zip(scored,logits):
        candidates.append(AwardCandidate(
            **row,
            race_share=logit/denom if denom else 0.0,
        ))
    candidates.sort(key=lambda c:(-c.race_score,c.player_name))
    return AwardRace(as_of=as_of,award=award,candidates=tuple(candidates))
