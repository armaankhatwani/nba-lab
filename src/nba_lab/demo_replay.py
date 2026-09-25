from __future__ import annotations

from .domain import Game
from .replay import ReplayEvent
from .replay_source import ReplaySnapshot


def _clock_from_elapsed(elapsed: float) -> tuple[int, float]:
    if elapsed >= 2880:
        return 4, 0.0
    period = int(elapsed // 720) + 1
    clock = 720.0 - (elapsed % 720.0)
    return period, clock


def synthetic_replay_snapshots(games: list[Game], limit: int = 12) -> dict[str, ReplaySnapshot]:
    """Create clearly labeled score checkpoints for offline product testing."""
    finals = sorted(
        (game for game in games if game.is_final),
        key=lambda game: (game.game_date, game.game_id),
        reverse=True,
    )[:limit]
    snapshots = {}
    for game in finals:
        events = []
        checkpoints = 24
        last_home = 0
        last_away = 0
        for i in range(checkpoints + 1):
            fraction = i / checkpoints
            home = round(int(game.home_score) * fraction)
            away = round(int(game.away_score) * fraction)
            elapsed = 2880.0 * fraction
            period, clock = _clock_from_elapsed(elapsed)
            if i == 0:
                description = "Synthetic tipoff checkpoint"
                team = None
            elif i == checkpoints:
                description = f"Synthetic final · {game.away_team} {away} @ {game.home_team} {home}"
                team = game.home_team if home > last_home else game.away_team
            else:
                description = (
                    f"Synthetic checkpoint · {game.away_team} {away} @ {game.home_team} {home}"
                )
                team = game.home_team if home - last_home >= away - last_away else game.away_team
            events.append(
                ReplayEvent(
                    game_id=game.game_id,
                    action_number=i,
                    period=period,
                    clock_seconds=clock,
                    home_score=home,
                    away_score=away,
                    team=team,
                    description=description,
                    action_type="synthetic_checkpoint",
                    sub_type="",
                )
            )
            last_home, last_away = home, away
        snapshots[game.game_id] = ReplaySnapshot(
            game_id=game.game_id,
            events=tuple(events),
            source="synthetic_replay_demo",
        )
    return snapshots
