from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Game:
    game_id: str
    game_date: date
    home_team: str
    away_team: str
    home_score: int | None = None
    away_score: int | None = None

    @property
    def is_final(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def winner(self) -> str | None:
        if not self.is_final:
            return None
        if self.home_score == self.away_score:
            raise ValueError("NBA games cannot finish tied.")
        return self.home_team if self.home_score > self.away_score else self.away_team


@dataclass(frozen=True)
class TeamForecast:
    team: str
    current_wins: int
    current_losses: int
    expected_wins: float
    p10_wins: int
    p90_wins: int
    first_seed_probability: float
    top6_probability: float
    playin_probability: float
    playoffs_probability: float
    championship_probability: float
