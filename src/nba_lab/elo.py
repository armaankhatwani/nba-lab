from collections import defaultdict
from math import pow

from .domain import Game


class EloModel:
    def __init__(self, base: float = 1500.0, k: float = 20.0, home_advantage: float = 65.0):
        self.base = base
        self.k = k
        self.home_advantage = home_advantage

    def win_probability(self, home_rating: float, away_rating: float) -> float:
        diff = (home_rating + self.home_advantage) - away_rating
        return 1.0 / (1.0 + pow(10.0, -diff / 400.0))

    def fit_as_of(self, games: list[Game], as_of) -> dict[str, float]:
        ratings = defaultdict(lambda: self.base)
        for game in sorted(games, key=lambda g: (g.game_date, g.game_id)):
            if game.game_date >= as_of or not game.is_final:
                continue
            p_home = self.win_probability(ratings[game.home_team], ratings[game.away_team])
            actual_home = 1.0 if game.winner == game.home_team else 0.0
            delta = self.k * (actual_home - p_home)
            ratings[game.home_team] += delta
            ratings[game.away_team] -= delta
        teams = {g.home_team for g in games} | {g.away_team for g in games}
        return {team: ratings[team] for team in teams}
