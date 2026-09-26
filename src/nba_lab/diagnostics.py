from dataclasses import dataclass
from collections import defaultdict

from .domain import Game
from .elo import EloModel


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_prediction: float
    actual_rate: float


def chronological_predictions(games: list[Game], model: EloModel | None = None):
    """Generate leakage-safe date-level pregame predictions.

    The normalized game contract guarantees a game date, not a reliable tip-off
    timestamp. Every game on one date is therefore predicted from the same
    entering-day ratings. Results from that date are applied only after all of
    that date's predictions have been recorded.
    """
    model = model or EloModel()
    finals = sorted(
        (g for g in games if g.is_final),
        key=lambda g: (g.game_date, g.game_id),
    )
    ratings = defaultdict(lambda: model.base)
    rows = []

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
            p = model.win_probability(home_rating, away_rating)
            y = 1.0 if game.winner == game.home_team else 0.0
            rows.append({
                "game_id": game.game_id,
                "date": game.game_date.isoformat(),
                "home_team": game.home_team,
                "away_team": game.away_team,
                "p_home": p,
                "home_win": y,
            })
            delta = model.rating_delta(
                game,
                home_rating,
                away_rating,
                p,
                y,
            )
            updates.append((game.home_team, game.away_team, delta))

        for home_team, away_team, delta in updates:
            ratings[home_team] += delta
            ratings[away_team] -= delta

    return rows


def calibration_curve(games: list[Game], bins: int = 10, model: EloModel | None = None) -> list[CalibrationBin]:
    rows = chronological_predictions(games, model)
    buckets = [[] for _ in range(bins)]
    for row in rows:
        idx = min(bins - 1, int(row["p_home"] * bins))
        buckets[idx].append(row)
    result = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        result.append(CalibrationBin(
            lower=i / bins,
            upper=(i + 1) / bins,
            count=len(bucket),
            mean_prediction=sum(x["p_home"] for x in bucket) / len(bucket),
            actual_rate=sum(x["home_win"] for x in bucket) / len(bucket),
        ))
    return result
