from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

import numpy as np


@dataclass(frozen=True)
class Stint:
    game_id: str
    possessions: float
    point_diff: float
    home_players: tuple[str, ...]
    away_players: tuple[str, ...]
    game_date: date | None = None


@dataclass(frozen=True)
class PlayerImpact:
    player_id: str
    impact_per_100: float
    possessions: float
    rank: int
    standard_error: float
    lower_80: float
    upper_80: float


@dataclass(frozen=True)
class RapmResult:
    alpha: float
    home_court_per_100: float
    weighted_rmse: float
    players: tuple[PlayerImpact, ...]
    player_order: tuple[str, ...]
    player_covariance: tuple[tuple[float, ...], ...]


def _matrix(stints: list[Stint], players: list[str]):
    index={player:i for i,player in enumerate(players)}
    x=np.zeros((len(stints),len(players)+1),dtype=float)
    y=np.zeros(len(stints),dtype=float)
    w=np.zeros(len(stints),dtype=float)
    for row,stint in enumerate(stints):
        if stint.possessions<=0:
            raise ValueError("stint possessions must be positive")
        for player in stint.home_players:
            x[row,index[player]]=1.0
        for player in stint.away_players:
            x[row,index[player]]=-1.0
        x[row,-1]=1.0
        y[row]=100.0*stint.point_diff/stint.possessions
        w[row]=stint.possessions
    return x,y,w


def _fit_arrays(x,y,w,alpha:float):
    sw=np.sqrt(w)[:,None]
    xw=x*sw
    yw=y*np.sqrt(w)
    penalty=np.eye(x.shape[1])*alpha
    penalty[-1,-1]=0.0
    gram=xw.T@xw
    lhs=gram+penalty
    rhs=xw.T@yw
    beta=np.linalg.solve(lhs,rhs)
    predictions=x@beta
    residual=predictions-y
    rmse=sqrt(float(np.average(residual**2,weights=w)))

    # Approximate model-based sampling uncertainty for the ridge estimate.
    # Treat possession weights as repeated homoskedastic observations; this is
    # intentionally diagnostic rather than a formal causal/confidence interval.
    lhs_inv=np.linalg.inv(lhs)
    effective_df=float(np.trace(lhs_inv@gram))
    residual_df=max(1.0,float(np.sum(w))-effective_df)
    sigma2=float(np.sum(w*(residual**2))/residual_df)
    covariance=sigma2*(lhs_inv@gram@lhs_inv)
    standard_errors=np.sqrt(np.maximum(0.0,np.diag(covariance)))
    return beta,rmse,standard_errors,covariance


def fit_rapm(stints:list[Stint],alpha:float=1000.0)->RapmResult:
    if not stints:
        raise ValueError("RAPM requires at least one stint")
    if alpha<=0:
        raise ValueError("alpha must be positive")
    players=sorted({p for s in stints for p in (*s.home_players,*s.away_players)})
    x,y,w=_matrix(stints,players)
    beta,rmse,standard_errors,covariance=_fit_arrays(x,y,w,alpha)
    possessions={p:0.0 for p in players}
    for stint in stints:
        for player in (*stint.home_players,*stint.away_players):
            possessions[player]+=stint.possessions
    ordered=sorted(zip(players,beta[:-1]),key=lambda item:(-item[1],item[0]))
    beta_index={player:i for i,player in enumerate(players)}
    z80=1.2815515655446004
    impacts=tuple(PlayerImpact(
        player_id=player,
        impact_per_100=float(value),
        possessions=possessions[player],
        rank=rank,
        standard_error=float(standard_errors[beta_index[player]]),
        lower_80=float(value-z80*standard_errors[beta_index[player]]),
        upper_80=float(value+z80*standard_errors[beta_index[player]]),
    ) for rank,(player,value) in enumerate(ordered,1))
    return RapmResult(
        alpha=float(alpha),
        home_court_per_100=float(beta[-1]),
        weighted_rmse=rmse,
        players=impacts,
        player_order=tuple(players),
        player_covariance=tuple(
            tuple(float(value) for value in row)
            for row in covariance[:-1, :-1]
        ),
    )


def tune_alpha(
    stints:list[Stint],
    candidates:tuple[float,...]=(100.0,300.0,1000.0,3000.0),
    folds:int=5,
)->float:
    games=sorted({s.game_id for s in stints})
    if len(games)<2:
        return 1000.0
    folds=max(2,min(folds,len(games)))
    game_fold={game:i%folds for i,game in enumerate(games)}
    players=sorted({p for s in stints for p in (*s.home_players,*s.away_players)})
    all_x,all_y,all_w=_matrix(stints,players)
    scores=[]
    for alpha in candidates:
        fold_losses=[]
        for fold in range(folds):
            train_idx=[i for i,s in enumerate(stints) if game_fold[s.game_id]!=fold]
            test_idx=[i for i,s in enumerate(stints) if game_fold[s.game_id]==fold]
            if not train_idx or not test_idx:
                continue
            beta,_,_,_=_fit_arrays(all_x[train_idx],all_y[train_idx],all_w[train_idx],alpha)
            pred=all_x[test_idx]@beta
            loss=float(np.average((pred-all_y[test_idx])**2,weights=all_w[test_idx]))
            fold_losses.append(loss)
        scores.append((sum(fold_losses)/len(fold_losses),alpha))
    return min(scores)[1]
