from dataclasses import dataclass
from datetime import date
from collections import defaultdict
import random

from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class MatchupResult:
    team_a: str
    team_b: str
    as_of: date
    trials: int
    best_of: int
    team_a_rating: float
    team_b_rating: float
    team_a_series_probability: float
    team_b_series_probability: float
    expected_games: float
    length_distribution: dict[int, float]
    score_distribution: dict[str, float]


def simulate_matchup(
    games: list[Game],
    team_a: str,
    team_b: str,
    as_of: date,
    trials: int = 10_000,
    best_of: int = 7,
    seed: int = 2026,
    rating_adjustments: dict[str, float] | None = None,
    model: EloModel | None = None,
) -> MatchupResult:
    if team_a == team_b:
        raise ValueError("teams must be different")
    if best_of not in {1, 3, 5, 7}:
        raise ValueError("best_of must be 1, 3, 5, or 7")
    if trials < 1:
        raise ValueError("trials must be positive")

    model = model or EloModel()
    ratings = model.fit_as_of(games, as_of)
    adjustments = rating_adjustments or {}
    ratings = {team: rating + adjustments.get(team, 0.0) for team, rating in ratings.items()}
    if team_a not in ratings or team_b not in ratings:
        raise ValueError("both teams must exist in the game history")

    needed = best_of // 2 + 1
    if best_of == 1:
        pattern = [team_a]
    elif best_of == 3:
        pattern = [team_a, team_b, team_a]
    elif best_of == 5:
        pattern = [team_a, team_a, team_b, team_b, team_a]
    else:
        pattern = [team_a, team_a, team_b, team_b, team_a, team_b, team_a]

    rng = random.Random(seed)
    winners = defaultdict(int)
    lengths = defaultdict(int)
    scores = defaultdict(int)
    for _ in range(trials):
        wins = {team_a: 0, team_b: 0}
        played = 0
        for home in pattern:
            away = team_b if home == team_a else team_a
            p_home = model.win_probability(ratings[home], ratings[away])
            winner = home if rng.random() < p_home else away
            wins[winner] += 1
            played += 1
            if wins[winner] == needed:
                winners[winner] += 1
                lengths[played] += 1
                loser = team_b if winner == team_a else team_a
                scores[f"{winner} {wins[winner]}-{wins[loser]}"] += 1
                break

    return MatchupResult(
        team_a=team_a,
        team_b=team_b,
        as_of=as_of,
        trials=trials,
        best_of=best_of,
        team_a_rating=ratings[team_a],
        team_b_rating=ratings[team_b],
        team_a_series_probability=winners[team_a] / trials,
        team_b_series_probability=winners[team_b] / trials,
        expected_games=sum(length * count for length, count in lengths.items()) / trials,
        length_distribution={length: count / trials for length, count in sorted(lengths.items())},
        score_distribution={score: count / trials for score, count in sorted(scores.items())},
    )
