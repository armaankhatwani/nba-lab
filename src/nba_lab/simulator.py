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

    Official head-to-head/division/conference tiebreakers are not implemented yet.
    """
    by_conf: dict[str, list[str]] = defaultdict(list)
    for team in teams:
        by_conf[conference_for(team) or "Unknown"].append(team)
    result: dict[str, list[str]] = {}
    for conference, members in by_conf.items():
        jitter = {team: rng.random() for team in members}
        result[conference] = sorted(members, key=lambda team: (-wins[team], jitter[team]))
    return result


def _single_game(home: str, away: str, ratings, model: EloModel, rng: random.Random) -> str:
    p_home = model.win_probability(ratings[home], ratings[away])
    return home if rng.random() < p_home else away


def _series(higher: str, lower: str, ratings, model: EloModel, rng: random.Random) -> str:
    pattern = [higher, higher, lower, lower, higher, lower, higher]
    wins = {higher: 0, lower: 0}
    for home in pattern:
        away = lower if home == higher else higher
        winner = _single_game(home, away, ratings, model, rng)
        wins[winner] += 1
        if wins[winner] == 4:
            return winner
    raise RuntimeError("best-of-seven series did not terminate")


def _conference_playoffs(order: list[str], ratings, model: EloModel, rng: random.Random):
    if len(order) < 10:
        return [], None
    top6 = order[:6]
    seven, eight, nine, ten = order[6:10]
    seven_eight_winner = _single_game(seven, eight, ratings, model, rng)
    seven_eight_loser = eight if seven_eight_winner == seven else seven
    nine_ten_winner = _single_game(nine, ten, ratings, model, rng)
    eighth_seed = _single_game(seven_eight_loser, nine_ten_winner, ratings, model, rng)
    seeds = top6 + [seven_eight_winner, eighth_seed]

    qf = [
        _series(seeds[0], seeds[7], ratings, model, rng),
        _series(seeds[3], seeds[4], ratings, model, rng),
        _series(seeds[2], seeds[5], ratings, model, rng),
        _series(seeds[1], seeds[6], ratings, model, rng),
    ]
    sf1 = _series(qf[0], qf[1], ratings, model, rng)
    sf2 = _series(qf[2], qf[3], ratings, model, rng)
    champion = _series(sf1, sf2, ratings, model, rng)
    return seeds, champion


def _simulate_postseason(orders, wins, ratings, model: EloModel, rng: random.Random):
    east_seeds, east = _conference_playoffs(orders.get("East", []), ratings, model, rng)
    west_seeds, west = _conference_playoffs(orders.get("West", []), ratings, model, rng)
    playoff_teams = east_seeds + west_seeds
    if not east or not west:
        return playoff_teams, None
    if wins[east] > wins[west]:
        higher, lower = east, west
    elif wins[west] > wins[east]:
        higher, lower = west, east
    else:
        higher, lower = (east, west) if rng.random() < 0.5 else (west, east)
    return playoff_teams, _series(higher, lower, ratings, model, rng)


def simulate_remaining_season(
    games: list[Game],
    as_of: date,
    trials: int = 10_000,
    seed: int = 2026,
    rating_adjustments: dict[str, float] | None = None,
    forced_winners: dict[str, str] | None = None,
    model: EloModel | None = None,
) -> SimulationResult:
    if trials < 1:
        raise ValueError("trials must be positive")
    model = model or EloModel()
    ratings = model.fit_as_of(games, as_of)
    adjustments = rating_adjustments or {}
    forced = forced_winners or {}
    ratings = {team: rating + adjustments.get(team, 0.0) for team, rating in ratings.items()}
    teams = sorted(ratings)
    observed_wins, observed_losses = _observed_records(games, as_of)
    future = sorted((g for g in games if g.game_date >= as_of), key=lambda g: (g.game_date, g.game_id))

    rng = random.Random(seed)
    win_samples = {team: [] for team in teams}
    first_seed = defaultdict(float)
    top6 = defaultdict(float)
    playin = defaultdict(float)
    playoffs = defaultdict(float)
    championships = defaultdict(float)
    for _ in range(trials):
        wins = {team: observed_wins[team] for team in teams}
        for game in future:
            if game.game_id in forced:
                rng.random()  # preserve paired random stream versus unconstrained worlds
                winner = forced[game.game_id]
                if winner not in {game.home_team, game.away_team}:
                    raise ValueError(f"forced winner {winner} is not in game {game.game_id}")
            else:
                winner = _single_game(game.home_team, game.away_team, ratings, model, rng)
            wins[winner] += 1

        orders = _seed_groups(teams, wins, rng)
        for order in orders.values():
            if order:
                first_seed[order[0]] += 1
            for team in order[:6]:
                top6[team] += 1
            for team in order[6:10]:
                playin[team] += 1

        playoff_teams, champion = _simulate_postseason(orders, wins, ratings, model, rng)
        for team in playoff_teams:
            playoffs[team] += 1
        if champion:
            championships[champion] += 1
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
                playoffs_probability=playoffs[team] / trials,
                championship_probability=championships[team] / trials,
            )
        )
    forecasts.sort(key=lambda x: (-x.expected_wins, x.team))
    return SimulationResult(as_of=as_of, trials=trials, teams=tuple(forecasts))
