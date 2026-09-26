from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import random

from .domain import Game
from .elo import EloModel
from .simulator import _observed_records, _seed_groups, _single_game


@dataclass(frozen=True)
class WorldRegularGame:
    game_id: str
    game_date: date
    home_team: str
    away_team: str
    winner: str
    home_win_probability: float
    forced: bool


@dataclass(frozen=True)
class WorldPlayInGame:
    conference: str
    stage: str
    home_team: str
    away_team: str
    winner: str
    home_win_probability: float


@dataclass(frozen=True)
class WorldSeries:
    conference: str
    stage: str
    higher_team: str
    lower_team: str
    higher_seed: int | None
    lower_seed: int | None
    winner: str
    loser: str
    winner_games: int
    loser_games: int
    games_played: int


@dataclass(frozen=True)
class WorldStanding:
    conference: str
    seed: int
    team: str
    wins: int
    losses: int
    playoff_seed: int | None


@dataclass(frozen=True)
class SimulatedWorld:
    as_of: date
    seed: int
    standings: tuple[WorldStanding, ...]
    remaining_games: tuple[WorldRegularGame, ...]
    play_in_games: tuple[WorldPlayInGame, ...]
    series: tuple[WorldSeries, ...]
    east_champion: str | None
    west_champion: str | None
    champion: str | None


def _single_game_detail(
    home: str,
    away: str,
    ratings: dict[str, float],
    model: EloModel,
    rng: random.Random,
) -> tuple[str, float]:
    p_home = model.win_probability(ratings[home], ratings[away])
    winner = home if rng.random() < p_home else away
    return winner, p_home


def _series_detail(
    conference: str,
    stage: str,
    higher: str,
    lower: str,
    higher_seed: int | None,
    lower_seed: int | None,
    ratings: dict[str, float],
    model: EloModel,
    rng: random.Random,
) -> WorldSeries:
    pattern = [higher, higher, lower, lower, higher, lower, higher]
    wins = {higher: 0, lower: 0}
    for home in pattern:
        away = lower if home == higher else higher
        winner, _ = _single_game_detail(home, away, ratings, model, rng)
        wins[winner] += 1
        if wins[winner] == 4:
            loser = lower if winner == higher else higher
            return WorldSeries(
                conference=conference,
                stage=stage,
                higher_team=higher,
                lower_team=lower,
                higher_seed=higher_seed,
                lower_seed=lower_seed,
                winner=winner,
                loser=loser,
                winner_games=4,
                loser_games=wins[loser],
                games_played=sum(wins.values()),
            )
    raise RuntimeError("best-of-seven series did not terminate")


def _series_by_seed_detail(
    conference: str,
    stage: str,
    team_a: str,
    team_b: str,
    seed_by_team: dict[str, int],
    ratings: dict[str, float],
    model: EloModel,
    rng: random.Random,
) -> WorldSeries:
    if seed_by_team[team_a] < seed_by_team[team_b]:
        higher, lower = team_a, team_b
    else:
        higher, lower = team_b, team_a
    return _series_detail(
        conference,
        stage,
        higher,
        lower,
        seed_by_team[higher],
        seed_by_team[lower],
        ratings,
        model,
        rng,
    )


def _conference_world(
    conference: str,
    order: list[str],
    ratings: dict[str, float],
    model: EloModel,
    rng: random.Random,
) -> tuple[
    list[str],
    list[WorldPlayInGame],
    list[WorldSeries],
    str | None,
]:
    if len(order) < 10:
        return [], [], [], None

    top6 = order[:6]
    seven, eight, nine, ten = order[6:10]
    play_in: list[WorldPlayInGame] = []

    winner_78, p_78 = _single_game_detail(seven, eight, ratings, model, rng)
    play_in.append(WorldPlayInGame(
        conference, "7/8 Game", seven, eight, winner_78, p_78
    ))
    loser_78 = eight if winner_78 == seven else seven

    winner_910, p_910 = _single_game_detail(nine, ten, ratings, model, rng)
    play_in.append(WorldPlayInGame(
        conference, "9/10 Game", nine, ten, winner_910, p_910
    ))

    eighth_seed, p_final = _single_game_detail(
        loser_78, winner_910, ratings, model, rng
    )
    play_in.append(WorldPlayInGame(
        conference, "8th Seed Game", loser_78, winner_910, eighth_seed, p_final
    ))

    seeds = top6 + [winner_78, eighth_seed]
    seed_by_team = {team: index + 1 for index, team in enumerate(seeds)}
    series: list[WorldSeries] = []

    round_one_pairs = [
        (seeds[0], seeds[7]),
        (seeds[3], seeds[4]),
        (seeds[2], seeds[5]),
        (seeds[1], seeds[6]),
    ]
    round_one = []
    for higher, lower in round_one_pairs:
        row = _series_detail(
            conference,
            "First Round",
            higher,
            lower,
            seed_by_team[higher],
            seed_by_team[lower],
            ratings,
            model,
            rng,
        )
        series.append(row)
        round_one.append(row.winner)

    semi_one = _series_by_seed_detail(
        conference,
        "Conference Semifinals",
        round_one[0],
        round_one[1],
        seed_by_team,
        ratings,
        model,
        rng,
    )
    semi_two = _series_by_seed_detail(
        conference,
        "Conference Semifinals",
        round_one[2],
        round_one[3],
        seed_by_team,
        ratings,
        model,
        rng,
    )
    series.extend([semi_one, semi_two])

    final = _series_by_seed_detail(
        conference,
        "Conference Finals",
        semi_one.winner,
        semi_two.winner,
        seed_by_team,
        ratings,
        model,
        rng,
    )
    series.append(final)
    return seeds, play_in, series, final.winner


def simulate_one_world(
    games: list[Game],
    as_of: date,
    seed: int = 2026,
    rating_adjustments: dict[str, float] | None = None,
    game_rating_adjustments: dict[str, dict[str, float]] | None = None,
    forced_winners: dict[str, str] | None = None,
    model: EloModel | None = None,
) -> SimulatedWorld:
    """Sample one concrete regular-season + postseason future.

    Team strength is frozen at the as-of date, matching the aggregate season
    simulator. Persistent rating adjustments survive into the postseason;
    game-specific adjustments affect only their scheduled games.
    """
    model = model or EloModel()
    ratings = model.fit_as_of(games, as_of)
    persistent = rating_adjustments or {}
    ratings = {
        team: rating + persistent.get(team, 0.0)
        for team, rating in ratings.items()
    }
    game_adjustments = game_rating_adjustments or {}
    forced = forced_winners or {}
    teams = sorted(ratings)
    observed_wins, observed_losses = _observed_records(games, as_of)
    wins = {team: observed_wins[team] for team in teams}
    losses = {team: observed_losses[team] for team in teams}
    future = sorted(
        (game for game in games if game.game_date >= as_of),
        key=lambda game: (game.game_date, game.game_id),
    )

    rng = random.Random(seed)
    outcomes: list[WorldRegularGame] = []
    for game in future:
        per_game = game_adjustments.get(game.game_id, {})
        home_rating = ratings[game.home_team] + per_game.get(game.home_team, 0.0)
        away_rating = ratings[game.away_team] + per_game.get(game.away_team, 0.0)
        p_home = model.win_probability(home_rating, away_rating)

        if game.game_id in forced:
            rng.random()  # stay aligned with an unconstrained world for the same seed
            winner = forced[game.game_id]
            if winner not in {game.home_team, game.away_team}:
                raise ValueError(
                    f"forced winner {winner} is not in game {game.game_id}"
                )
            is_forced = True
        else:
            winner = game.home_team if rng.random() < p_home else game.away_team
            is_forced = False

        loser = game.away_team if winner == game.home_team else game.home_team
        wins[winner] += 1
        losses[loser] += 1
        outcomes.append(WorldRegularGame(
            game_id=game.game_id,
            game_date=game.game_date,
            home_team=game.home_team,
            away_team=game.away_team,
            winner=winner,
            home_win_probability=p_home,
            forced=is_forced,
        ))

    orders = _seed_groups(teams, wins, rng)
    east_seeds, east_play_in, east_series, east = _conference_world(
        "East", orders.get("East", []), ratings, model, rng
    )
    west_seeds, west_play_in, west_series, west = _conference_world(
        "West", orders.get("West", []), ratings, model, rng
    )

    playoff_seed = {
        team: index + 1
        for seeds in (east_seeds, west_seeds)
        for index, team in enumerate(seeds)
    }
    standings = tuple(
        WorldStanding(
            conference=conference,
            seed=index + 1,
            team=team,
            wins=wins[team],
            losses=losses[team],
            playoff_seed=playoff_seed.get(team),
        )
        for conference in ("East", "West")
        for index, team in enumerate(orders.get(conference, []))
    )

    series = east_series + west_series
    champion = None
    if east and west:
        if wins[east] > wins[west]:
            higher, lower = east, west
        elif wins[west] > wins[east]:
            higher, lower = west, east
        else:
            higher, lower = (east, west) if rng.random() < 0.5 else (west, east)
        finals = _series_detail(
            "NBA",
            "NBA Finals",
            higher,
            lower,
            playoff_seed.get(higher),
            playoff_seed.get(lower),
            ratings,
            model,
            rng,
        )
        series.append(finals)
        champion = finals.winner

    return SimulatedWorld(
        as_of=as_of,
        seed=seed,
        standings=standings,
        remaining_games=tuple(outcomes),
        play_in_games=tuple(east_play_in + west_play_in),
        series=tuple(series),
        east_champion=east,
        west_champion=west,
        champion=champion,
    )
