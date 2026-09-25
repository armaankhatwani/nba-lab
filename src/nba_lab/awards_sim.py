from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
import random

from .awards import PlayerGame, build_award_race
from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class AwardFutureCandidate:
    player_id: str
    player_name: str
    team: str
    leader_probability: float
    top3_probability: float
    mean_final_score: float


@dataclass(frozen=True)
class AwardFutureResult:
    as_of: date
    trials: int
    candidates: tuple[AwardFutureCandidate, ...]


def _future_game(game: Game, home_win: bool) -> Game:
    if home_win:
        return Game(game.game_id, game.game_date, game.home_team, game.away_team, 1, 0)
    return Game(game.game_id, game.game_date, game.home_team, game.away_team, 0, 1)


def simulate_award_futures(
    games: list[Game],
    player_games: list[PlayerGame],
    as_of: date,
    trials: int = 1_000,
    seed: int = 2026,
    candidate_limit: int = 10,
    model: EloModel | None = None,
) -> AwardFutureResult:
    if trials < 1:
        raise ValueError("trials must be positive")
    model = model or EloModel()

    current = build_award_race(games, player_games, as_of)
    candidate_ids = {c.player_id for c in current.candidates[:candidate_limit]}
    if not candidate_ids:
        return AwardFutureResult(as_of=as_of, trials=trials, candidates=())

    observed_games = [g for g in games if g.is_final and g.game_date <= as_of]
    future_schedule = sorted((g for g in games if g.game_date > as_of), key=lambda g:(g.game_date,g.game_id))
    final_date = max((g.game_date for g in games), default=as_of)

    observed_logs = [r for r in player_games if r.game_date <= as_of and r.player_id in candidate_ids]
    rows_by_player: dict[str,list[PlayerGame]] = defaultdict(list)
    for row in observed_logs:
        rows_by_player[row.player_id].append(row)

    team_games_so_far = Counter()
    for game in observed_games:
        team_games_so_far[game.home_team] += 1
        team_games_so_far[game.away_team] += 1

    availability={}
    for pid,rows in rows_by_player.items():
        team=rows[-1].team
        availability[pid]=min(1.0,len(rows)/max(1,team_games_so_far[team]))

    ratings=model.fit_as_of(games, as_of + timedelta(days=1))
    rng=random.Random(seed)
    leaders=Counter(); top3=Counter(); score_sums=Counter()
    identity={c.player_id:(c.player_name,c.team) for c in current.candidates if c.player_id in candidate_ids}

    for _ in range(trials):
        sim_games=list(observed_games)
        for game in future_schedule:
            p_home=model.win_probability(ratings[game.home_team],ratings[game.away_team])
            sim_games.append(_future_game(game,rng.random()<p_home))

        sim_logs=list(observed_logs)
        for pid,rows in rows_by_player.items():
            if not rows:
                continue
            team=rows[-1].team
            for game in future_schedule:
                if team not in {game.home_team,game.away_team}:
                    continue
                if rng.random()>availability[pid]:
                    continue
                source=rng.choice(rows)
                sim_logs.append(PlayerGame(
                    game_id=game.game_id,
                    game_date=game.game_date,
                    player_id=source.player_id,
                    player_name=source.player_name,
                    team=team,
                    minutes=source.minutes,
                    points=source.points,
                    rebounds=source.rebounds,
                    assists=source.assists,
                    steals=source.steals,
                    blocks=source.blocks,
                    turnovers=source.turnovers,
                    fga=source.fga,
                    fta=source.fta,
                ))

        race=build_award_race(sim_games,sim_logs,final_date)
        ordered=[c for c in race.candidates if c.player_id in candidate_ids]
        if ordered:
            leaders[ordered[0].player_id]+=1
        for c in ordered[:3]:
            top3[c.player_id]+=1
        for c in ordered:
            score_sums[c.player_id]+=c.race_score

    result=[]
    for pid,(name,team) in identity.items():
        result.append(AwardFutureCandidate(
            player_id=pid,
            player_name=name,
            team=team,
            leader_probability=leaders[pid]/trials,
            top3_probability=top3[pid]/trials,
            mean_final_score=score_sums[pid]/trials,
        ))
    result.sort(key=lambda x:(-x.leader_probability,-x.mean_final_score,x.player_name))
    return AwardFutureResult(as_of=as_of,trials=trials,candidates=tuple(result))
