from dataclasses import asdict, dataclass
from collections import defaultdict

from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class TimelinePoint:
    game_id: str
    date: str
    opponent: str
    home: bool
    win: bool
    wins: int
    losses: int
    rating: float
    margin: int


def team_timeline(games: list[Game], team: str, model: EloModel | None = None) -> list[TimelinePoint]:
    model = model or EloModel()
    ratings = defaultdict(lambda: model.base)
    wins = defaultdict(int)
    losses = defaultdict(int)
    points: list[TimelinePoint] = []

    for game in sorted((g for g in games if g.is_final), key=lambda g: (g.game_date, g.game_id)):
        home_rating = ratings[game.home_team]
        away_rating = ratings[game.away_team]
        p_home = model.win_probability(home_rating, away_rating)
        home_win = game.winner == game.home_team
        delta = model.k * ((1.0 if home_win else 0.0) - p_home)
        ratings[game.home_team] += delta
        ratings[game.away_team] -= delta

        winner = game.winner
        loser = game.away_team if winner == game.home_team else game.home_team
        wins[winner] += 1
        losses[loser] += 1

        if team not in {game.home_team, game.away_team}:
            continue
        home = game.home_team == team
        opponent = game.away_team if home else game.home_team
        score_for = game.home_score if home else game.away_score
        score_against = game.away_score if home else game.home_score
        points.append(
            TimelinePoint(
                game_id=game.game_id,
                date=game.game_date.isoformat(),
                opponent=opponent,
                home=home,
                win=winner == team,
                wins=wins[team],
                losses=losses[team],
                rating=round(ratings[team], 2),
                margin=int(score_for - score_against),
            )
        )
    return points
