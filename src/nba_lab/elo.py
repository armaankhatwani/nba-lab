from collections import defaultdict
from math import log1p, pow

from .domain import Game


class EloModel:
    def __init__(self, base: float = 1500.0, k: float = 20.0, home_advantage: float = 65.0):
        self.base = base
        self.k = k
        self.home_advantage = home_advantage

    def win_probability(self, home_rating: float, away_rating: float) -> float:
        diff = (home_rating + self.home_advantage) - away_rating
        return 1.0 / (1.0 + pow(10.0, -diff / 400.0))

    def update_multiplier(
        self,
        game: Game,
        home_rating: float,
        away_rating: float,
    ) -> float:
        return 1.0

    def rating_delta(
        self,
        game: Game,
        home_rating: float,
        away_rating: float,
        p_home: float,
        actual_home: float,
    ) -> float:
        return (
            self.k
            * self.update_multiplier(game, home_rating, away_rating)
            * (actual_home - p_home)
        )

    def fit_as_of(self, games: list[Game], as_of) -> dict[str, float]:
        """Fit a date-level point-in-time state without same-day ordering effects."""
        ratings = defaultdict(lambda: self.base)
        finals = sorted(
            (
                game
                for game in games
                if game.is_final and game.game_date < as_of
            ),
            key=lambda game: (game.game_date, game.game_id),
        )

        cursor = 0
        while cursor < len(finals):
            day = finals[cursor].game_date
            day_games = []
            while cursor < len(finals) and finals[cursor].game_date == day:
                day_games.append(finals[cursor])
                cursor += 1

            updates = []
            for game in day_games:
                home_rating = ratings[game.home_team]
                away_rating = ratings[game.away_team]
                p_home = self.win_probability(home_rating, away_rating)
                actual_home = 1.0 if game.winner == game.home_team else 0.0
                delta = self.rating_delta(
                    game,
                    home_rating,
                    away_rating,
                    p_home,
                    actual_home,
                )
                updates.append((game.home_team, game.away_team, delta))

            for home_team, away_team, delta in updates:
                ratings[home_team] += delta
                ratings[away_team] -= delta

        teams = {g.home_team for g in games} | {g.away_team for g in games}
        return {team: ratings[team] for team in teams}


class ScoreAwareEloModel(EloModel):
    """Experimental Elo family that lets score margin scale rating updates.

    The probability model remains ordinary Elo. Only the postgame update size
    changes, and the margin-weight parameter must earn promotion on held-out data.
    """

    def __init__(
        self,
        base: float = 1500.0,
        k: float = 20.0,
        home_advantage: float = 65.0,
        margin_weight: float = 0.5,
        margin_cap: float = 50.0,
    ):
        super().__init__(base=base, k=k, home_advantage=home_advantage)
        if margin_weight < 0:
            raise ValueError("margin_weight must be non-negative")
        if margin_cap <= 0:
            raise ValueError("margin_cap must be positive")
        self.margin_weight = margin_weight
        self.margin_cap = margin_cap

    def update_multiplier(
        self,
        game: Game,
        home_rating: float,
        away_rating: float,
    ) -> float:
        if not game.is_final:
            return 1.0
        margin = abs(float(game.home_score) - float(game.away_score))
        capped = min(self.margin_cap, margin)
        normalized = log1p(capped) / log1p(20.0)
        return 1.0 + self.margin_weight * normalized
