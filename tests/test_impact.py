import pytest

from nba_lab.impact import Stint, fit_rapm, tune_alpha


def synthetic_stints():
    # A is deliberately present in stronger home groups, D in weaker away groups,
    # with lineup rotation so ridge has enough contrast to separate them.
    return [
        Stint("g1",20,8,("A","B","C"),("D","E","F")),
        Stint("g1",15,4,("A","B","G"),("D","E","H")),
        Stint("g2",18,5,("A","C","G"),("D","F","H")),
        Stint("g2",16,-1,("B","C","G"),("D","E","F")),
        Stint("g3",20,6,("A","B","H"),("E","F","G")),
        Stint("g3",14,-3,("B","C","H"),("D","F","G")),
        Stint("g4",18,7,("A","C","E"),("D","F","G")),
        Stint("g4",17,0,("B","C","E"),("D","F","H")),
        Stint("g5",16,5,("A","B","F"),("D","G","H")),
        Stint("g5",19,-2,("B","C","F"),("D","E","H")),
    ]


def test_rapm_ranks_signal_player_above_negative_player():
    result=fit_rapm(synthetic_stints(),alpha=100)
    by={p.player_id:p for p in result.players}
    assert by["A"].impact_per_100>by["D"].impact_per_100
    assert by["A"].rank<by["D"].rank
    assert result.weighted_rmse>=0


def test_rapm_tracks_possession_exposure():
    result=fit_rapm(synthetic_stints(),alpha=300)
    by={p.player_id:p for p in result.players}
    assert by["A"].possessions>0
    assert by["D"].possessions>0


def test_tune_alpha_returns_candidate():
    candidates=(10.0,100.0,1000.0)
    assert tune_alpha(synthetic_stints(),candidates=candidates,folds=3) in candidates


def test_bad_possessions_rejected():
    with pytest.raises(ValueError):
        fit_rapm([Stint("g",0,1,("A",),("B",))])
