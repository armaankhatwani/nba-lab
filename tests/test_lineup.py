from nba_lab.impact import fit_rapm
from nba_lab.impact_source import ImpactPlayer, ImpactSnapshot
from nba_lab.impact import Stint
from nba_lab.lineup import compare_lineups, estimate_lineup


def snapshot():
    players = {
        str(i): ImpactPlayer(str(i), f"P{i}", "A" if i <= 5 else "B")
        for i in range(1, 11)
    }
    stints = (
        Stint("g1", 100, 10, ("1","2","3","4","5"), ("6","7","8","9","10")),
        Stint("g2", 80, 4, ("1","2","3","4","6"), ("5","7","8","9","10")),
        Stint("g3", 90, -3, ("1","2","3","7","8"), ("4","5","6","9","10")),
    )
    return ImpactSnapshot(stints=stints, players=players, source="test", qa={})


def test_observed_lineup_blends_empirical_and_additive_signal():
    s = snapshot()
    rapm = fit_rapm(list(s.stints), alpha=100)
    result = estimate_lineup(s, rapm, ("1","2","3","4","5"), prior_possessions=100)
    assert result.observed_possessions == 100
    assert result.observed_net_rating == 10
    assert 0 < result.observed_weight < 1


def test_unseen_lineup_falls_back_to_additive_rapm():
    s = snapshot()
    rapm = fit_rapm(list(s.stints), alpha=100)
    result = estimate_lineup(s, rapm, ("1","2","3","4","10"))
    assert result.observed_possessions == 0
    assert result.observed_net_rating is None
    assert result.blended_net_rating == result.additive_rapm


def test_lineup_matchup_is_antisymmetric():
    s = snapshot()
    rapm = fit_rapm(list(s.stints), alpha=100)
    a = ("1","2","3","4","5")
    b = ("6","7","8","9","10")
    ab = compare_lineups(s, rapm, a, b)
    ba = compare_lineups(s, rapm, b, a)
    assert abs(ab.neutral_margin_per_100 + ba.neutral_margin_per_100) < 1e-12
