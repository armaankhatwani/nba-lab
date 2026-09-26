from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .domain import Game
from .elo import EloModel
from .impact import RapmResult
from .impact_source import ImpactSnapshot
from .scenario import PlayerAbsence, build_player_absence_adjustments
from .simulator import simulate_remaining_season


@dataclass(frozen=True)
class RestGame:
    rank: int
    game_id: str
    game_date: date
    team: str
    opponent: str
    home: bool
    baseline_team_win_probability: float
    expected_wins_delta: float
    playoffs_probability_delta: float
    championship_probability_delta: float


@dataclass(frozen=True)
class RestPlan:
    as_of: date
    player_id: str
    player_name: str
    team: str
    trials: int
    minutes_per_game: float
    replacement_impact_per_100: float
    player_impact_per_100: float
    player_impact_lower_80: float
    player_impact_upper_80: float
    elo_delta_per_game: float
    elo_delta_low_80: float
    elo_delta_high_80: float
    games: tuple[RestGame, ...]


def _team_map(result):
    return {row.team: row for row in result.teams}


def evaluate_rest_plan(
    games: list[Game],
    as_of: date,
    impact_snapshot: ImpactSnapshot,
    rapm: RapmResult,
    player_id: str,
    trials: int = 750,
    seed: int = 2026,
    minutes_per_game: float = 34.0,
    replacement_impact_per_100: float = 0.0,
    horizon_games: int = 12,
) -> RestPlan:
    if trials < 1:
        raise ValueError("trials must be positive")
    if horizon_games < 1:
        raise ValueError("horizon_games must be positive")

    meta = impact_snapshot.players.get(player_id)
    impact = next((row for row in rapm.players if row.player_id == player_id), None)
    if meta is None or impact is None:
        raise ValueError(f"unknown impact player: {player_id}")

    # Reuse Scenario Lab's exact player -> margin -> Elo translation. With one
    # missed game, the effect magnitude is independent of which candidate game
    # receives it; only the game-specific placement changes below.
    _, effects = build_player_absence_adjustments(
        games,
        as_of,
        impact_snapshot,
        rapm,
        [
            PlayerAbsence(
                player_id=player_id,
                games_missed=1,
                minutes_per_game=minutes_per_game,
                replacement_impact_per_100=replacement_impact_per_100,
            )
        ],
    )
    if not effects:
        raise ValueError("could not build player absence effect")
    effect = effects[0]

    future_games = sorted(
        (
            game
            for game in games
            if game.game_date >= as_of
            and meta.team in {game.home_team, game.away_team}
        ),
        key=lambda game: (game.game_date, game.game_id),
    )[:horizon_games]
    if not future_games:
        raise ValueError(f"no future games found for {meta.team}")

    baseline = simulate_remaining_season(
        games,
        as_of,
        trials=trials,
        seed=seed,
    )
    baseline_team = _team_map(baseline)[meta.team]

    model = EloModel()
    ratings = model.fit_as_of(games, as_of)
    rows: list[RestGame] = []
    for game in future_games:
        altered = simulate_remaining_season(
            games,
            as_of,
            trials=trials,
            seed=seed,
            game_rating_adjustments={
                game.game_id: {meta.team: effect.elo_delta_per_game}
            },
        )
        altered_team = _team_map(altered)[meta.team]

        p_home = model.win_probability(
            ratings[game.home_team],
            ratings[game.away_team],
        )
        team_win_probability = (
            p_home if game.home_team == meta.team else 1.0 - p_home
        )
        opponent = (
            game.away_team if game.home_team == meta.team else game.home_team
        )

        rows.append(
            RestGame(
                rank=0,
                game_id=game.game_id,
                game_date=game.game_date,
                team=meta.team,
                opponent=opponent,
                home=game.home_team == meta.team,
                baseline_team_win_probability=team_win_probability,
                expected_wins_delta=(
                    altered_team.expected_wins - baseline_team.expected_wins
                ),
                playoffs_probability_delta=(
                    altered_team.playoffs_probability
                    - baseline_team.playoffs_probability
                ),
                championship_probability_delta=(
                    altered_team.championship_probability
                    - baseline_team.championship_probability
                ),
            )
        )

    # "Safest" means the model loses the least championship probability first,
    # then playoff probability, then expected wins. Signed improvements remain
    # visible rather than being clipped away.
    rows.sort(
        key=lambda row: (
            -row.championship_probability_delta,
            -row.playoffs_probability_delta,
            -row.expected_wins_delta,
            row.game_date,
            row.game_id,
        )
    )
    ranked = tuple(
        RestGame(
            rank=index,
            game_id=row.game_id,
            game_date=row.game_date,
            team=row.team,
            opponent=row.opponent,
            home=row.home,
            baseline_team_win_probability=row.baseline_team_win_probability,
            expected_wins_delta=row.expected_wins_delta,
            playoffs_probability_delta=row.playoffs_probability_delta,
            championship_probability_delta=row.championship_probability_delta,
        )
        for index, row in enumerate(rows, 1)
    )

    return RestPlan(
        as_of=as_of,
        player_id=player_id,
        player_name=meta.player_name,
        team=meta.team,
        trials=trials,
        minutes_per_game=minutes_per_game,
        replacement_impact_per_100=replacement_impact_per_100,
        player_impact_per_100=impact.impact_per_100,
        player_impact_lower_80=impact.lower_80,
        player_impact_upper_80=impact.upper_80,
        elo_delta_per_game=effect.elo_delta_per_game,
        elo_delta_low_80=effect.elo_delta_low_80,
        elo_delta_high_80=effect.elo_delta_high_80,
        games=ranked,
    )
