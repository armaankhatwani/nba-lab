from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import random

from .domain import Game, TeamForecast
from .elo import EloModel
from .teams import conference_for


@dataclass(frozen=True)
class SimulationResult:
    as_of: date
    trials: int
    teams: tuple[TeamForecast, ...]


def _observed_records(games: list[Game], as_of: date):
    wins = defaultdict(int)
    losses = defaultdict(int)
    for game in games:
        if game.game_date >= as_of or not game.is_final:
            continue
        winner = game.winner
        loser = game.away_team if winner == game.home_team else game.home_team
        wins[winner] += 1
        losses[loser] += 1
    return wins, losses


def _seed_groups(teams: list[str], wins: dict[str, int], rng: random.Random):
    """Return seed order by conference with randomized tie resolution.

    This is intentionally not presented as official NBA tiebreaker logic yet.
    Randomized ties keep probability mass honest until head-to-head/division
    tiebreakers are modeled explicitly.
    """
    by_conf: dict[str, list[str]] = defaultdict(list)
    for team in teams:
        by_conf[conference_for(team) or "Unknown"].append(team)
    result: dict[str, list[str]] = {}
    for conference, members in by_conf.items():
        jitter = {team: rng.random() for team in members}
        result[conference] = sorted(members, key=lambda team: (-wins[team], jitter[team]))
    return result


def simulate_remaining_season(
    games: list[Game],
    as_of: date,
    trials: int = 10_000,
    seed: int = 2026,
    rating_adjustments: dict[str, float] | None = None,
    model: EloModel | None = None,
) -> SimulationResult:
    if trials < 1:
        raise ValueError("trials must be positive")
    model = model or EloModel()
    ratings = model.fit_as_of(games, as_of)
    adjustments = rating_adjustments or {}
    ratings = {team: rating + adjustments.get(team, 0.0) for team, rating in ratings.items()}
    teams = sorted(ratings)
    observed_wins, observed_losses = _observed_records(games, as_of)
    future = sorted((g for g in games if g.game_date >= as_of), key=lambda g: (g.game_date, g.game_id))

    rng = random.Random(seed)
    win_samples = {team: [] for team in teams}
    first_seed = defaultdict(float)
    top6 = defaultdict(float)
    playin = defaultdict(float)
    for _ in range(trials):
        wins = {team: observed_wins[team] for team in teams}
        for game in future:
            p_home = model.win_probability(ratings[game.home_team], ratings[game.away_team])
            winner = game.home_team if rng.random() < p_home else game.away_team
            wins[winner] += 1

        orders = _seed_groups(teams, wins, rng)
        for order in orders.values():
            if order:
                first_seed[order[0]] += 1
            for team in order[:6]:
                top6[team] += 1
            for team in order[6:10]:
                playin[team] += 1
        for team in teams:
            win_samples[team].append(wins[team])

    forecasts = []
    for team in teams:
        samples = sorted(win_samples[team])
        lo = samples[int(0.10 * (trials - 1))]
        hi = samples[int(0.90 * (trials - 1))]
        forecasts.append(
            TeamForecast(
                team=team,
                current_wins=observed_wins[team],
                current_losses=observed_losses[team],
                expected_wins=sum(samples) / trials,
                p10_wins=lo,
                p90_wins=hi,
                first_seed_probability=first_seed[team] / trials,
                top6_probability=top6[team] / trials,
                playin_probability=playin[team] / trials,
            )
        )
    forecasts.sort(key=lambda x: (-x.expected_wins, x.team))
    return SimulationResult(as_of=as_of, trials=trials, teams=tuple(forecasts))
