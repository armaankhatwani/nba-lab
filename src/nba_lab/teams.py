from dataclasses import dataclass


@dataclass(frozen=True)
class TeamInfo:
    tricode: str
    name: str
    conference: str


_TEAMS = [
    TeamInfo("ATL", "Atlanta Hawks", "East"),
    TeamInfo("BOS", "Boston Celtics", "East"),
    TeamInfo("BKN", "Brooklyn Nets", "East"),
    TeamInfo("CHA", "Charlotte Hornets", "East"),
    TeamInfo("CHI", "Chicago Bulls", "East"),
    TeamInfo("CLE", "Cleveland Cavaliers", "East"),
    TeamInfo("DET", "Detroit Pistons", "East"),
    TeamInfo("IND", "Indiana Pacers", "East"),
    TeamInfo("MIA", "Miami Heat", "East"),
    TeamInfo("MIL", "Milwaukee Bucks", "East"),
    TeamInfo("NYK", "New York Knicks", "East"),
    TeamInfo("ORL", "Orlando Magic", "East"),
    TeamInfo("PHI", "Philadelphia 76ers", "East"),
    TeamInfo("TOR", "Toronto Raptors", "East"),
    TeamInfo("WAS", "Washington Wizards", "East"),
    TeamInfo("DAL", "Dallas Mavericks", "West"),
    TeamInfo("DEN", "Denver Nuggets", "West"),
    TeamInfo("GSW", "Golden State Warriors", "West"),
    TeamInfo("HOU", "Houston Rockets", "West"),
    TeamInfo("LAC", "LA Clippers", "West"),
    TeamInfo("LAL", "Los Angeles Lakers", "West"),
    TeamInfo("MEM", "Memphis Grizzlies", "West"),
    TeamInfo("MIN", "Minnesota Timberwolves", "West"),
    TeamInfo("NOP", "New Orleans Pelicans", "West"),
    TeamInfo("OKC", "Oklahoma City Thunder", "West"),
    TeamInfo("PHX", "Phoenix Suns", "West"),
    TeamInfo("POR", "Portland Trail Blazers", "West"),
    TeamInfo("SAC", "Sacramento Kings", "West"),
    TeamInfo("SAS", "San Antonio Spurs", "West"),
    TeamInfo("UTA", "Utah Jazz", "West"),
]

TEAMS = {team.tricode: team for team in _TEAMS}


def conference_for(team: str) -> str | None:
    info = TEAMS.get(team)
    return info.conference if info else None
