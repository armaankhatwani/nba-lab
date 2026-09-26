const $=id=>document.getElementById(id);let meta={},mode='flip',diagnosticsLoaded=false,lastDeltas=[],awardHistory=[],currentAwardRace=null,awardTimer=null,impactData=null,lineupPool=[],lineupA=[],lineupB=[],replayGames=[],replayData=null,replayIndex=0,replayLastResult=null,scenarioPlayers=[],scenarioAbsences=[],scenarioLast=null,scenarioLastRequest=null,selectedImpactPlayerId=null,pendingScenarioFlipGameId=null;
const pct=x=>`${(100*x).toFixed(x<.1?1:0)}%`;const signed=x=>`${x>=0?'+':''}${x.toFixed(2)}`;
async function json(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}
function teamOptions(select,includeAll=false){select.replaceChildren();if(includeAll){const o=document.createElement('option');o.value='';o.textContent='All teams';select.append(o)}Object.keys(meta.team_metadata).sort().forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=`${t} · ${meta.team_metadata[t].name}`;select.append(o)})}
const viewMeta={home:['NBA LAB / OVERVIEW','Basketball, as a system.'],season:['NBA LAB / SEASON LAB','Rewrite the season.'],matchup:['NBA LAB / MATCHUP LAB','Run the matchup.'],timeline:['NBA LAB / TIMELINE LAB','Replay how a team changed.'],model:['NBA LAB / MODEL LAB','Trust the model, then improve it.'],awards:['NBA LAB / AWARDS LAB','Replay the award race.'],impact:['NBA LAB / PLAYER IMPACT','Separate player from context.'],lineup:['NBA LAB / LINEUP LAB','Build the five.'],leverage:['NBA LAB / LEVERAGE LAB','Find the pivotal game.'],game:['NBA LAB / GAME REPLAY','Replay the game.'],scenario:['NBA LAB / SCENARIO LAB','Compose an alternate world.']};
function openView(name){document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===name));$(`view-${name}`).classList.add('active');$('view-kicker').textContent=viewMeta[name][0];$('view-title').textContent=viewMeta[name][1];if(name==='timeline')loadTimeline();if(name==='model')loadDiagnostics();if(name==='matchup'&&!$('matchup-a').value)setupMatchup();if(name==='awards')loadAwards();if(name==='impact')loadImpact();if(name==='lineup')loadLineup();if(name==='game')loadReplay();if(name==='scenario')loadScenario()}
document.querySelectorAll('.nav-item').forEach(b=>b.onclick=()=>openView(b.dataset.view));document.querySelectorAll('[data-open]').forEach(c=>c.onclick=()=>openView(c.dataset.open));
async function loadGames(){const team=$('game-team').value;const q=new URLSearchParams({before:$('asof').value,limit:'50'});if(team)q.set('team',team);const games=await json('/api/games?'+q);$('game').replaceChildren();games.forEach(g=>{const o=document.createElement('option');o.value=g.game_id;o.textContent=`${g.date} · ${g.away_team} ${g.away_score} @ ${g.home_team} ${g.home_score}`;$('game').append(o)});if(!games.length){const o=document.createElement('option');o.textContent='No completed games before this date';$('game').append(o)}}
async function init(){meta=await json('/api/status');const official=meta.source.kind==='official_snapshot';$('source-short').textContent=official?'Official NBA snapshot':'Synthetic fallback';$('source-detail').textContent=`${meta.games} games · ${meta.teams} teams`;$('source-dot').style.background=official?'var(--green)':'var(--orange)';$('date-range').textContent=`${meta.date_min} → ${meta.date_max}`;teamOptions($('team'));teamOptions($('game-team'),true);teamOptions($('timeline-team'));teamOptions($('matchup-a'));teamOptions($('matchup-b'));$('team').value='NYK';$('timeline-team').value='NYK';$('matchup-a').value='NYK';$('matchup-b').value='BOS';await loadGames();try{const b=await json('/api/backtest');$('brier').textContent=b.brier.toFixed(3)}catch(e){$('brier').textContent='—'}const encoded=new URLSearchParams(window.location.search).get('scenario');if(encoded){document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view==='scenario'));$('view-scenario').classList.add('active');$('view-kicker').textContent=viewMeta.scenario[0];$('view-title').textContent=viewMeta.scenario[1];await loadScenario();await restoreScenarioFromUrl()}}
function setMode(value){mode=value;document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));$('flip-controls').hidden=mode!=='flip';$('strength-controls').hidden=mode!=='strength';$('run').childNodes[0].textContent=mode==='flip'?'REWRITE HISTORY ':'SIMULATE BOTH WORLDS '}
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));$('asof').onchange=loadGames;$('game-team').onchange=loadGames;$('delta').oninput=()=>{$('delta-value').textContent=`${Number($('delta').value)>=0?'+':''}${$('delta').value} Elo`};
$('run').onclick=async()=>{const start=performance.now();$('run').disabled=true;try{const common={as_of:$('asof').value,trials:Number($('trials').value),seed:2026};let url,body;if(mode==='flip'){url='/api/flip-game';body={...common,game_id:$('game').value}}else{url='/api/compare';body={...common,team:$('team').value,elo_delta:Number($('delta').value)}}const d=await json(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});renderSeason(d);$('runtime').textContent=`${((performance.now()-start)/1000).toFixed(2)}s`}catch(e){$('focus').innerHTML=`<p>${e.message}</p>`}finally{$('run').disabled=false}};
function renderSeason(d){$('sim-count').textContent=d.baseline.trials.toLocaleString();const deltas=Object.fromEntries(d.deltas.map(x=>[x.team,x]));const base=Object.fromEntries(d.baseline.teams.map(x=>[x.team,x]));const alt=Object.fromEntries(d.altered.teams.map(x=>[x.team,x]));const largest=d.deltas.reduce((a,b)=>Math.abs(b.expected_wins_delta)>Math.abs(a.expected_wins_delta)?b:a,d.deltas[0]);$('ripple').textContent=`${largest.team} ${signed(largest.expected_wins_delta)}`;let chosen;if(d.intervention.kind==='flip_game'){chosen=d.intervention.flipped_winner;$('focus').innerHTML=`<span class="eyebrow">HISTORICAL BRANCH / ${d.intervention.date}</span><h2>${d.intervention.away_team} ${d.intervention.away_score} @ ${d.intervention.home_team} ${d.intervention.home_score}</h2><div class="focus-grid"><div><strong>${d.intervention.original_winner} → ${d.intervention.flipped_winner}</strong><span>game winner</span></div><div><strong>${signed(deltas[d.intervention.flipped_winner].expected_wins_delta)}</strong><span>${d.intervention.flipped_winner} expected wins</span></div><div><strong>${pct(alt[d.intervention.flipped_winner].championship_probability)}</strong><span>${d.intervention.flipped_winner} title odds</span></div><div><strong>${signed(deltas[d.intervention.original_winner].expected_wins_delta)}</strong><span>${d.intervention.original_winner} expected wins</span></div></div><p class="note">One historical result changed. Pre-date information stays fixed; future simulations use paired random draws.</p>`}else{chosen=d.intervention.team;const c=deltas[chosen];$('focus').innerHTML=`<span class="eyebrow">MODEL INTERVENTION / ${chosen}</span><h2>${d.intervention.elo_delta>=0?'+':''}${d.intervention.elo_delta} Elo research adjustment</h2><div class="focus-grid"><div><strong>${signed(c.expected_wins_delta)}</strong><span>expected wins</span></div><div><strong>${signed(c.first_seed_probability_delta*100)} pts</strong><span>No. 1 seed probability</span></div><div><strong>${base[chosen].expected_wins.toFixed(1)} → ${alt[chosen].expected_wins.toFixed(1)}</strong><span>baseline → altered</span></div></div><p class="note">${d.intervention.warning}</p>`}lastDeltas=d.deltas;renderRipple();renderSeasonAwardRipple(d);$('rows').innerHTML=d.baseline.teams.map(x=>{const y=alt[x.team],z=deltas[x.team],cls=x.team===chosen?'selected':'';return `<tr class="${cls}"><td>${x.team}</td><td>${x.current_wins}-${x.current_losses}</td><td>${x.expected_wins.toFixed(1)} → ${y.expected_wins.toFixed(1)}</td><td>${x.p10_wins}–${x.p90_wins}</td><td>${pct(y.first_seed_probability)}</td><td>${pct(y.top6_probability)}</td><td>${pct(y.playin_probability)}</td><td>${pct(y.playoffs_probability)}</td><td>${pct(y.championship_probability)}</td><td class="${z.expected_wins_delta>0?'positive':z.expected_wins_delta<0?'negative':''}">${signed(z.expected_wins_delta)}</td></tr>`}).join('')}
function renderRipple(){if(!lastDeltas.length)return;const metric=$('ripple-metric').value;const sorted=[...lastDeltas].sort((a,b)=>Math.abs(b[metric])-Math.abs(a[metric])).slice(0,14);const max=Math.max(...sorted.map(x=>Math.abs(x[metric])),.001);$('ripple-bars').classList.remove('empty');$('ripple-bars').innerHTML=sorted.map(x=>{const value=x[metric],w=48*Math.abs(value)/max;return `<div class="ripple-item"><div class="ripple-track"><div class="ripple-fill ${value>=0?'pos':'neg'}" style="width:${w}%"><title>${x.team} ${metric.includes('probability')?(value*100).toFixed(2)+' pts':value.toFixed(2)}</title></div></div><label>${x.team}</label></div>`}).join('')}
$('ripple-metric').onchange=renderRipple;

function renderSeasonAwardRipple(d){
  const panel=$('award-ripple-panel');
  if(!d.award_ripple||!d.award_ripple.length){panel.hidden=true;return}
  panel.hidden=false;
  panel.dataset.asof=d.baseline.as_of;
  $('season-award-ripple').innerHTML=d.award_ripple.slice(0,8).map(p=>{
    const up=p.race_score_delta>=0;
    return `<div class="award-ripple-card"><span>${p.team} · ${p.player_name}</span><strong class="${up?'up':'down'}">${signed(p.race_score_delta)} race score</strong><small>rank ${p.before_rank} → ${p.after_rank} · share ${p.race_share_delta>=0?'+':''}${(p.race_share_delta*100).toFixed(2)} pts</small></div>`
  }).join('');
}
$('open-awards-from-season').onclick=()=>{
  const date=$('award-ripple-panel').dataset.asof;
  if(date)$('award-date').value=date;
  openView('awards');
};

function setupMatchup(){if(!$('matchup-a').value)$('matchup-a').value='NYK';if(!$('matchup-b').value)$('matchup-b').value='BOS'}
$('matchup-run').onclick=runMatchup;
async function runMatchup(){const button=$('matchup-run');button.disabled=true;$('matchup-context').hidden=true;try{const body={as_of:$('matchup-date').value,trials:Number($('matchup-trials').value),seed:2026,team_a:$('matchup-a').value,team_b:$('matchup-b').value,best_of:Number($('matchup-bestof').value)};const d=await json('/api/matchup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});renderMatchup(d)}catch(e){$('matchup-result').innerHTML=`<p>${e.message}</p>`}finally{button.disabled=false}}
function renderMatchup(d){const pa=d.team_a_series_probability,pb=d.team_b_series_probability;$('matchup-a-name').textContent=d.team_a;$('matchup-b-name').textContent=d.team_b;$('matchup-a-prob').textContent=pct(pa);$('matchup-b-prob').textContent=pct(pb);$('matchup-a-elo').textContent=`Elo ${d.team_a_rating.toFixed(0)}`;$('matchup-b-elo').textContent=`Elo ${d.team_b_rating.toFixed(0)}`;$('matchup-prob-fill').style.width=`${pa*100}%`;$('matchup-games').textContent=d.best_of===1?'single game':`${d.expected_games.toFixed(2)} expected games`;const lengths=Object.entries(d.length_distribution),maxL=Math.max(...lengths.map(([,v])=>v),.001);$('length-dist').innerHTML=lengths.map(([k,v])=>`<div class="dist-row"><span>${k} games</span><div class="dist-track"><div class="dist-fill" style="width:${100*v/maxL}%"></div></div><strong>${pct(v)}</strong></div>`).join('');const scores=Object.entries(d.score_distribution).sort((a,b)=>b[1]-a[1]).slice(0,8),maxS=Math.max(...scores.map(([,v])=>v),.001);$('score-dist').innerHTML=scores.map(([k,v])=>`<div class="score-row"><span>${k}</span><div class="score-track"><div class="score-fill" style="width:${100*v/maxS}%"></div></div><strong>${pct(v)}</strong></div>`).join('')}
$('timeline-team').onchange=loadTimeline;
async function loadTimeline(){const team=$('timeline-team').value||'NYK';const d=await json(`/api/timeline/${team}`);$('tl-record').textContent=`${d.summary.wins}-${d.summary.losses}`;$('tl-current').textContent=d.summary.current_rating.toFixed(0);$('tl-peak').textContent=d.summary.peak_rating.toFixed(0);$('tl-range').textContent=`${d.summary.low_rating.toFixed(0)} → ${d.summary.peak_rating.toFixed(0)}`;$('tl-title').textContent=`${d.team.name} · Elo trajectory`;drawTimeline(d.points);$('timeline-games').innerHTML=d.points.slice(-16).reverse().map(p=>`<div class="game-chip ${p.win?'win':'loss'}"><span>${p.date} · ${p.home?'vs':'@'} ${p.opponent}</span><strong>${p.win?'W':'L'} ${p.margin>0?'+':''}${p.margin}</strong><span>${p.wins}-${p.losses} · Elo ${p.rating.toFixed(0)}</span></div>`).join('')}
function drawTimeline(points){const el=$('timeline-chart');if(!points.length){el.innerHTML='';return}const W=900,H=250,pad=34;const vals=points.map(p=>p.rating);const min=Math.min(...vals)-15,max=Math.max(...vals)+15;const x=i=>pad+(W-2*pad)*(i/Math.max(1,points.length-1));const y=v=>H-pad-(H-2*pad)*((v-min)/(max-min));const path=points.map((p,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(p.rating).toFixed(1)}`).join(' ');const grids=[min,(min+max)/2,max];el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${grids.map(v=>`<line class="grid" x1="${pad}" y1="${y(v)}" x2="${W-pad}" y2="${y(v)}"/><text x="2" y="${y(v)+3}">${v.toFixed(0)}</text>`).join('')}<path class="line" d="${path}"/>${points.map((p,i)=>`<circle class="point ${p.win?'win':'loss'}" cx="${x(i)}" cy="${y(p.rating)}" r="4"><title>${p.date} · ${p.win?'W':'L'} ${p.margin>0?'+':''}${p.margin} vs ${p.opponent} · Elo ${p.rating}</title></circle>`).join('')}</svg>`}
async function loadDiagnostics(){
  if(diagnosticsLoaded)return;
  const [d,surface]=await Promise.all([json('/api/diagnostics'),json('/api/model/elo-surface')]);
  diagnosticsLoaded=true;
  $('md-brier').textContent=d.metrics.brier.toFixed(3);
  $('md-logloss').textContent=d.metrics.log_loss.toFixed(3);
  $('md-accuracy').textContent=pct(d.metrics.accuracy);
  $('md-games').textContent=d.metrics.games.toLocaleString();
  $('model-name').textContent=d.model.name;
  $('model-base').textContent=d.model.base;
  $('model-k').textContent=d.model.k;
  $('model-home').textContent=`${d.model.home_advantage} Elo`;
  $('promotion-rule').textContent=d.model.promotion_rule;
  drawCalibration(d.calibration);
  drawEloSurface(surface);
}

function drawEloSurface(d){
  const ks=[...new Set(d.candidates.map(function(row){return Number(row.k)}))].sort(function(a,b){return a-b});
  const homes=[...new Set(d.candidates.map(function(row){return Number(row.home_advantage)}))].sort(function(a,b){return a-b});
  const by=new Map(d.candidates.map(function(row){return [row.k+'|'+row.home_advantage,row]}));
  const values=d.candidates.map(function(row){return row.validation.brier});
  const min=Math.min.apply(null,values),max=Math.max.apply(null,values),span=Math.max(1e-9,max-min);
  const selected=d.selected_on_train,baseline=d.baseline,delta=selected.validation.brier-baseline.validation.brier;

  $('elo-surface-status').textContent=d.train_games+' train · '+d.validation_games+' holdout · split '+d.split_date;
  $('elo-split').textContent=d.train_games+' → '+d.validation_games;
  $('elo-base-holdout').textContent=baseline.validation.brier.toFixed(3);
  $('elo-selected').textContent='K'+selected.k.toFixed(0)+' / H'+selected.home_advantage.toFixed(0);
  $('elo-holdout-delta').textContent=(delta>=0?'+':'')+delta.toFixed(4);
  $('elo-holdout-delta').className=delta<0?'positive':delta>0?'negative':'';

  const grid=$('elo-surface-grid');
  grid.style.gridTemplateColumns='70px repeat('+homes.length+',minmax(78px,1fr))';
  const cells=['<div class="elo-grid-cell axis">K ↓ / HOME →</div>'];
  homes.forEach(function(home){cells.push('<div class="elo-grid-cell axis">'+home.toFixed(0)+'</div>')});
  ks.forEach(function(k){
    cells.push('<div class="elo-grid-cell axis">K '+k.toFixed(0)+'</div>');
    homes.forEach(function(home){
      const row=by.get(k+'|'+home);
      const quality=1-(row.validation.brier-min)/span;
      const alpha=(.05+.34*quality).toFixed(3);
      const baselineCell=k===Number(baseline.k)&&home===Number(baseline.home_advantage);
      const selectedCell=k===Number(selected.k)&&home===Number(selected.home_advantage);
      cells.push('<div class="elo-grid-cell value '+(baselineCell?'baseline ':'')+(selectedCell?'selected':'')+'" style="background:rgba(129,214,190,'+alpha+')">'
        +'<strong>'+row.validation.brier.toFixed(3)+'</strong>'
        +'<span>train '+row.train.brier.toFixed(3)+'</span>'
        +'<title>K '+k+' · home '+home+' · train Brier '+row.train.brier.toFixed(4)+' · holdout Brier '+row.validation.brier.toFixed(4)+'</title>'
        +'</div>');
    });
  });
  grid.innerHTML=cells.join('');

  const verdict=$('elo-surface-verdict');
  if(delta<0){
    verdict.innerHTML='<strong>Train-selected candidate improves this holdout by <span class="positive">'+Math.abs(delta).toFixed(4)+' Brier</span>.</strong> That earns a follow-up experiment, not automatic promotion.';
  }else if(delta>0){
    verdict.innerHTML='<strong>The deployed baseline beats the train-selected candidate on this holdout by <span class="positive">'+Math.abs(delta).toFixed(4)+' Brier</span>.</strong> The frozen baseline survives this parameter search.';
  }else{
    verdict.innerHTML='<strong>The train-selected candidate ties the deployed baseline on this holdout.</strong> There is no evidence here to change the deployed parameters.';
  }
}

function drawCalibration(points){const el=$('calibration-chart'),W=600,H=250,pad=34;const x=v=>pad+(W-2*pad)*v,y=v=>H-pad-(H-2*pad)*v;const path=points.map((p,i)=>`${i?'L':'M'}${x(p.mean_prediction)},${y(p.actual_rate)}`).join(' ');el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line class="grid" x1="${pad}" y1="${y(.5)}" x2="${W-pad}" y2="${y(.5)}"/><line class="grid" x1="${x(.5)}" y1="${pad}" x2="${x(.5)}" y2="${H-pad}"/><line class="ideal" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}"/><path class="cal-line" d="${path}"/>${points.map(p=>`<circle class="point win" cx="${x(p.mean_prediction)}" cy="${y(p.actual_rate)}" r="${Math.max(4,Math.min(9,Math.sqrt(p.count)))}"><title>${(p.mean_prediction*100).toFixed(1)}% predicted · ${(p.actual_rate*100).toFixed(1)}% observed · n=${p.count}</title></circle>`).join('')}<text x="${pad}" y="${H-6}">0%</text><text x="${W-pad-18}" y="${H-6}">100%</text><text x="4" y="${pad+3}">100%</text><text x="4" y="${H-pad+3}">0%</text></svg>`}




$('leverage-run').onclick=async()=>{
  const button=$('leverage-run');button.disabled=true;$('lev-status').textContent='branching upcoming games…';
  try{
    const q=new URLSearchParams({
      as_of:$('leverage-date').value,
      trials:$('leverage-trials').value,
      limit:$('leverage-limit').value,
    });
    const d=await json('/api/leverage?'+q);
    const rows=d.games||[];
    if(!rows.length){$('lev-status').textContent='no upcoming games';return}
    const top=rows[0];
    $('lev-top-game').textContent=`${top.away_team} @ ${top.home_team}`;
    $('lev-title-shift').textContent=pct(top.title_distribution_shift);
    $('lev-playoff-shift').textContent=pct(top.playoff_distribution_shift);
    $('lev-team-swing').textContent=top.biggest_title_swing_team?`${top.biggest_title_swing_team} ${top.biggest_title_swing>=0?'+':''}${(top.biggest_title_swing*100).toFixed(1)} pts`:'—';
    const max=Math.max(...rows.map(r=>r.title_distribution_shift),.001);
    $('leverage-rows').innerHTML=rows.map((r,i)=>`<div class="leverage-row">
      <div class="leverage-rank">${String(i+1).padStart(2,'0')}</div>
      <div class="leverage-game"><strong>${r.away_team} @ ${r.home_team}</strong><span>${r.game_date}</span></div>
      <div class="leverage-track"><div class="leverage-fill" style="width:${100*r.title_distribution_shift/max}%"></div></div>
      <div class="leverage-cell"><span>TITLE SHIFT</span><strong>${pct(r.title_distribution_shift)}</strong></div>
      <div class="leverage-cell"><span>PLAYOFF SHIFT</span><strong>${pct(r.playoff_distribution_shift)}</strong></div>
      <div class="leverage-cell leverage-swing"><span>BIGGEST TITLE SWING</span><strong>${r.biggest_title_swing_team||'—'} ${r.biggest_title_swing_team?(r.biggest_title_swing>=0?'+':'')+(r.biggest_title_swing*100).toFixed(1)+' pts':''}</strong></div>
    </div>`).join('');
    $('lev-status').textContent=`${rows.length} games · ${Number(d.trials_per_world).toLocaleString()} trials per branch`;
  }catch(e){
    $('lev-status').textContent=e.message;
  }finally{button.disabled=false}
};


async function loadReplay(){
  if(!replayGames.length){
    const listing=await json('/api/replay/games');
    replayGames=listing.games||[];
    $('replay-source').textContent=listing.source?.kind==='official_snapshot'?'OFFICIAL PBP SNAPSHOTS':'SYNTHETIC REPLAY FALLBACK';
    $('replay-game').replaceChildren();
    replayGames.forEach(game=>{
      const option=document.createElement('option');
      option.value=game.game_id;
      option.textContent=`${game.date} · ${game.away_team} ${game.away_score} @ ${game.home_team} ${game.home_score}`;
      $('replay-game').append(option);
    });
  }
  if(!replayGames.length){
    $('replay-event-description').textContent='No replay snapshots are available.';
    return;
  }
  if(!replayData||replayData.game.game_id!==$('replay-game').value)await loadReplayGame();
}
async function loadReplayGame(){
  const gameId=$('replay-game').value;if(!gameId)return;
  replayData=await json(`/api/replay/${gameId}`);
  const events=replayData.events||[];
  replayIndex=Math.max(0,Math.min(events.length-1,Math.floor(events.length*.72)));
  $('replay-slider').min=0;$('replay-slider').max=Math.max(0,events.length-1);$('replay-slider').value=replayIndex;
  $('replay-away-team').textContent=replayData.game.away_team;$('replay-home-team').textContent=replayData.game.home_team;
  $('replay-edit-home-label').textContent=replayData.game.home_team;$('replay-edit-away-label').textContent=replayData.game.away_team;
  $('replay-home-delta').value=0;$('replay-away-delta').value=0;
  renderReplayEvent();
}
function replayClock(seconds){
  const s=Math.max(0,Math.round(seconds));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
}
function replayPeriod(period){return period<=4?`Q${period}`:`OT${period-4}`}
function clearReplayResults(){
  replayLastResult=null;
  ['replay-base-prob','replay-alt-prob','replay-prob-delta','replay-margin'].forEach(id=>$(id).textContent='—');
  $('replay-run-note').textContent='run a simulation';$('replay-prob-bars').innerHTML='';$('replay-margin-dist').innerHTML='';$('replay-season-panel').hidden=true;$('replay-season-ripple').innerHTML='';$('replay-to-scenario').hidden=true;
}
function renderReplayEvent(){
  if(!replayData?.events?.length)return;
  replayIndex=Math.max(0,Math.min(replayData.events.length-1,replayIndex));
  const event=replayData.events[replayIndex];
  $('replay-slider').value=replayIndex;
  $('replay-away-score').textContent=event.away_score;$('replay-home-score').textContent=event.home_score;
  $('replay-period').textContent=replayPeriod(event.period);$('replay-clock').textContent=replayClock(event.clock_seconds);
  $('replay-event-number').textContent=`event ${event.action_number}`;
  $('replay-event-team').textContent=event.team||'GAME STATE';
  $('replay-event-description').textContent=event.description||'No description';
  $('replay-event-type').textContent=[event.action_type,event.sub_type].filter(Boolean).join(' · ');
  $('replay-slider-label').textContent=`${replayIndex+1} / ${replayData.events.length}`;
  const lo=Math.max(0,replayIndex-3),hi=Math.min(replayData.events.length,replayIndex+4);
  $('replay-nearby-events').innerHTML=replayData.events.slice(lo,hi).map((row,offset)=>{
    const idx=lo+offset;
    return `<div class="replay-nearby-row ${idx===replayIndex?'active':''}" data-replay-index="${idx}">
      <span>${replayPeriod(row.period)} ${replayClock(row.clock_seconds)}</span>
      <span>${row.away_score}-${row.home_score}</span>
      <strong>${row.description||row.action_type||'game event'}</strong>
    </div>`;
  }).join('');
  document.querySelectorAll('[data-replay-index]').forEach(row=>row.onclick=()=>{replayIndex=Number(row.dataset.replayIndex);renderReplayEvent();clearReplayResults()});
}
$('replay-game').onchange=loadReplayGame;
$('replay-slider').oninput=()=>{replayIndex=Number($('replay-slider').value);renderReplayEvent();clearReplayResults()};
document.querySelectorAll('[data-replay-preset]').forEach(button=>button.onclick=()=>{
  const preset=button.dataset.replayPreset;
  $('replay-home-delta').value=preset==='home2'?2:preset==='home3'?3:0;
  $('replay-away-delta').value=preset==='away2'?2:preset==='away3'?3:0;
  clearReplayResults();
});
$('replay-home-delta').oninput=clearReplayResults;$('replay-away-delta').oninput=clearReplayResults;
$('replay-run').onclick=async()=>{
  if(!replayData?.events?.length)return;
  const event=replayData.events[replayIndex],button=$('replay-run');button.disabled=true;
  try{
    const d=await json('/api/replay/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      game_id:replayData.game.game_id,
      action_number:event.action_number,
      trials:Number($('replay-trials').value),
      seed:2026,
      home_score_delta:Number($('replay-home-delta').value||0),
      away_score_delta:Number($('replay-away-delta').value||0)
    })});
    renderReplayResult(d);
  }catch(e){$('replay-run-note').textContent=e.message}finally{button.disabled=false}
};
function renderReplayResult(d){
  replayLastResult=d;
  const b=d.baseline,a=d.altered,delta=d.home_win_probability_delta;
  $('replay-base-prob').textContent=pct(b.home_win_probability);
  $('replay-alt-prob').textContent=pct(a.home_win_probability);
  $('replay-prob-delta').textContent=`${delta>=0?'+':''}${(100*delta).toFixed(1)} pts`;
  $('replay-prob-delta').className=delta>=0?'replay-swing-positive':'replay-swing-negative';
  $('replay-margin').textContent=`${a.expected_final_margin>=0?'+':''}${a.expected_final_margin.toFixed(1)}`;
  $('replay-run-note').textContent=`${a.trials.toLocaleString()} paired futures · pregame home ${pct(a.pregame_home_win_probability)}`;
  $('replay-prob-bars').innerHTML=`
    <div class="prob-compare-row"><span>BASELINE</span><div class="prob-compare-track"><div class="prob-compare-fill base" style="width:${100*b.home_win_probability}%"></div></div><strong>${pct(b.home_win_probability)}</strong></div>
    <div class="prob-compare-row"><span>ALTERED</span><div class="prob-compare-track"><div class="prob-compare-fill alt" style="width:${100*a.home_win_probability}%"></div></div><strong>${pct(a.home_win_probability)}</strong></div>`;
  const values=[a.p10_final_margin,a.p50_final_margin,a.p90_final_margin,0];
  const min=Math.floor(Math.min(...values)-2),max=Math.ceil(Math.max(...values)+2),span=Math.max(1,max-min);
  const pos=v=>100*(v-min)/span;
  $('replay-margin-dist').innerHTML=`
    <div class="margin-axis">
      <div class="margin-range" style="left:${pos(a.p10_final_margin)}%;width:${pos(a.p90_final_margin)-pos(a.p10_final_margin)}%"></div>
      <div class="margin-zero" style="left:${pos(0)}%"></div>
      <div class="margin-median" style="left:${pos(a.p50_final_margin)}%"></div>
    </div>
    <div class="margin-labels"><span>${min}</span><span>home margin</span><span>+${max}</span></div>
    <div class="margin-summary"><div><span>P10</span><strong>${a.p10_final_margin.toFixed(1)}</strong></div><div><span>MEDIAN</span><strong>${a.p50_final_margin.toFixed(1)}</strong></div><div><span>P90</span><strong>${a.p90_final_margin.toFixed(1)}</strong></div></div>`;
  renderReplaySeasonRipple(d.season_ripple);
}
function renderReplaySeasonRipple(ripple){
  if(!ripple?.teams?.length)return;
  $('replay-season-panel').hidden=false;
  if(replayData?.game){
    const game=replayData.game;
    const actualWinner=Number(game.home_score)>Number(game.away_score)?game.home_team:game.away_team;
    const opposite=actualWinner===game.home_team?game.away_team:game.home_team;
    $('replay-to-scenario').textContent='BRANCH: '+opposite+' WINS ↗';
    $('replay-to-scenario').hidden=false;
  }
  $('replay-season-note').textContent=`${ripple.trials.toLocaleString()} paired season branches`;
  $('replay-season-ripple').innerHTML=ripple.teams.slice(0,10).map(row=>{
    const title=row.championship_probability_delta*100,playoffs=row.playoffs_probability_delta*100,wins=row.expected_wins_delta;
    const primary=Math.abs(title)>=.01?title:playoffs;
    const cls=primary>=0?'up':'down';
    return `<div class="replay-season-card"><span>${row.team}</span><strong class="${cls}">${wins>=0?'+':''}${wins.toFixed(3)} wins</strong><small>playoffs ${playoffs>=0?'+':''}${playoffs.toFixed(2)} pts<br>title ${title>=0?'+':''}${title.toFixed(2)} pts</small></div>`;
  }).join('');
}


$('replay-to-scenario').onclick=function(){
  if(!replayData?.game||!replayLastResult)return;
  const game=replayData.game;
  const cutoff=new Date(game.date+'T12:00:00Z');
  cutoff.setUTCDate(cutoff.getUTCDate()+1);
  const cutoffText=cutoff.toISOString().slice(0,10);

  scenarioAbsences=[];
  scenarioLast=null;
  scenarioLastRequest=null;
  $('scenario-date').value=cutoffText;
  $('scenario-trade-enabled').checked=false;
  $('scenario-trade-fields').hidden=true;
  pendingScenarioFlipGameId=game.game_id;
  openView('scenario');
};

async function loadLineup(){
  const alpha=Number($('lineup-alpha').value||1000);
  const params=new URLSearchParams({alpha:String(alpha)});
  if($('lineup-date').value)params.set('as_of',$('lineup-date').value);
  const d=await json('/api/lineup/players?'+params);
  lineupPool=d.players||[];
  const available=new Set(lineupPool.map(function(p){return p.player_id}));
  lineupA=lineupA.filter(function(pid){return available.has(pid)});
  lineupB=lineupB.filter(function(pid){return available.has(pid)});
  $('lineup-source').textContent=d.as_of?('AS OF '+d.as_of):'FULL SNAPSHOT';
  const teams=[...new Set(lineupPool.map(p=>p.team))].sort();
  if($('lineup-team-filter').options.length<=1){
    teams.forEach(team=>{const o=document.createElement('option');o.value=team;o.textContent=team;$('lineup-team-filter').append(o)});
  }
  const optTeam=$('lineup-opt-team');
  const previousTeam=optTeam.value;
  optTeam.replaceChildren();
  teams.forEach(team=>{const o=document.createElement('option');o.value=team;o.textContent=team;optTeam.append(o)});
  if(teams.includes(previousTeam))optTeam.value=previousTeam;
  else if(teams.includes('BOS'))optTeam.value='BOS';
  renderLineupSlots();
  renderLineupPool();
}
function renderLineupSlots(){
  for(const [side,players] of [['a',lineupA],['b',lineupB]]){
    const el=$(`lineup-${side}-slots`);
    el.innerHTML=Array.from({length:5},(_,i)=>{
      const pid=players[i];
      const p=lineupPool.find(x=>x.player_id===pid);
      if(!p)return `<div class="lineup-slot empty"><strong>OPEN SLOT</strong><span>player ${i+1}</span></div>`;
      return `<div class="lineup-slot"><button data-remove-side="${side}" data-remove-player="${pid}">×</button><strong>${p.player_name}</strong><span>${p.team} · ${p.impact_per_100>=0?'+':''}${p.impact_per_100.toFixed(1)}</span></div>`;
    }).join('');
  }
  document.querySelectorAll('[data-remove-player]').forEach(button=>button.onclick=()=>{
    const arr=button.dataset.removeSide==='a'?lineupA:lineupB;
    const idx=arr.indexOf(button.dataset.removePlayer);if(idx>=0)arr.splice(idx,1);
    resetLineupResult();renderLineupSlots();renderLineupPool();
  });
}
function renderLineupPool(){
  const q=($('lineup-search').value||'').toLowerCase().trim();
  const team=$('lineup-team-filter').value;
  const used=new Set([...lineupA,...lineupB]);
  const rows=lineupPool.filter(p=>(!q||p.player_name.toLowerCase().includes(q)||p.team.toLowerCase().includes(q))&&(!team||p.team===team));
  $('lineup-player-pool').innerHTML=rows.map(p=>`<div class="pool-player ${used.has(p.player_id)?'used':''}">
    <div><strong>${p.player_name}</strong><span>${p.team} · RAPM ${p.impact_per_100>=0?'+':''}${p.impact_per_100.toFixed(2)} · ${Math.round(p.possessions).toLocaleString()} poss</span></div>
    <div class="pool-actions"><button data-add-a="${p.player_id}" title="Add to lineup A">A</button><button data-add-b="${p.player_id}" title="Add to lineup B">B</button></div>
  </div>`).join('');
  document.querySelectorAll('[data-add-a]').forEach(b=>b.onclick=()=>addLineupPlayer('a',b.dataset.addA));
  document.querySelectorAll('[data-add-b]').forEach(b=>b.onclick=()=>addLineupPlayer('b',b.dataset.addB));
}
function addLineupPlayer(side,pid){
  if(lineupA.includes(pid)||lineupB.includes(pid))return;
  const arr=side==='a'?lineupA:lineupB;
  if(arr.length>=5)return;
  arr.push(pid);resetLineupResult();renderLineupSlots();renderLineupPool();
}
function resetLineupResult(){
  $('lineup-a-value').textContent='—';$('lineup-b-value').textContent='—';$('lineup-margin').textContent='—';
  $('lineup-margin-note').textContent='select ten unique players';
  $('lineup-a-meta').textContent=lineupA.length===5?'Ready to estimate.':'Choose five players.';
  $('lineup-b-meta').textContent=lineupB.length===5?'Ready to estimate.':'Choose five players.';
}
$('lineup-search').oninput=renderLineupPool;
$('lineup-team-filter').onchange=renderLineupPool;
$('lineup-alpha').onchange=async()=>{await loadLineup();resetLineupResult();resetLineupOptimizer()};
$('lineup-date').onchange=async()=>{await loadLineup();resetLineupResult();resetLineupOptimizer()};
$('lineup-latest').onclick=async()=>{$('lineup-date').value='';await loadLineup();resetLineupResult();resetLineupOptimizer()};
$('lineup-prior').onchange=()=>{resetLineupResult();resetLineupOptimizer()};
$('lineup-swap').onclick=()=>{const copy=[...lineupA];lineupA=[...lineupB];lineupB=copy;resetLineupResult();renderLineupSlots();renderLineupPool()};
$('lineup-run').onclick=async()=>{
  if(lineupA.length!==5||lineupB.length!==5){$('lineup-margin-note').textContent='both sides need five unique players';return}
  const button=$('lineup-run');button.disabled=true;
  try{
    const d=await json('/api/lineup/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      lineup_a:lineupA,lineup_b:lineupB,alpha:Number($('lineup-alpha').value),prior_possessions:Number($('lineup-prior').value),
      as_of:$('lineup-date').value||null
    })});
    const a=d.lineup_a,b=d.lineup_b,m=d.neutral_margin_per_100;
    $('lineup-a-value').textContent=`${a.blended_net_rating>=0?'+':''}${a.blended_net_rating.toFixed(1)}`;
    $('lineup-b-value').textContent=`${b.blended_net_rating>=0?'+':''}${b.blended_net_rating.toFixed(1)}`;
    $('lineup-margin').textContent=`${m>=0?'+':''}${m.toFixed(1)}`;
    const winner=m>=0?'Lineup A':'Lineup B';
    $('lineup-margin-note').textContent=`${winner} model edge per 100 possessions${d.as_of?' · as of '+d.as_of:''}`;
    const meta=lineup=>lineup.observed_possessions>0
      ? `<span class="lineup-seen">OBSERVED UNIT</span> · ${Math.round(lineup.observed_possessions)} poss · raw ${lineup.observed_net_rating.toFixed(1)} · ${Math.round(100*lineup.observed_weight)}% empirical weight`
      : `<span class="lineup-unseen">UNSEEN UNIT</span> · additive RAPM prior only`;
    $('lineup-a-meta').innerHTML=meta(a);$('lineup-b-meta').innerHTML=meta(b);
  }catch(e){$('lineup-margin-note').textContent=e.message}finally{button.disabled=false}
};


function resetLineupOptimizer(){
  $('lineup-opt-candidates').textContent='—';
  $('lineup-opt-combos').textContent='—';
  $('lineup-opt-best').textContent='—';
  $('lineup-opt-evidence').textContent='—';
  $('lineup-opt-results').classList.add('empty');
  $('lineup-opt-results').innerHTML='<span>Choose a team and enumerate its modeled closing groups.</span>';
}
$('lineup-opt-run').onclick=async()=>{
  const button=$('lineup-opt-run');button.disabled=true;
  const target=$('lineup-opt-results');
  target.classList.add('empty');target.innerHTML='<span>Enumerating five-man combinations…</span>';
  try{
    const q=new URLSearchParams({
      team:$('lineup-opt-team').value,
      alpha:String(Number($('lineup-alpha').value)),
      prior_possessions:String(Number($('lineup-prior').value)),
      top_k:String(Number($('lineup-opt-limit').value))
    });
    if($('lineup-date').value)q.set('as_of',$('lineup-date').value);
    const d=await json('/api/lineup/optimize?'+q);
    $('lineup-opt-candidates').textContent=d.candidate_players;
    $('lineup-opt-combos').textContent=Number(d.combinations_evaluated).toLocaleString();
    const top=d.lineups[0];
    $('lineup-opt-best').textContent=top?(top.blended_net_rating>=0?'+':'')+top.blended_net_rating.toFixed(1):'—';
    $('lineup-opt-evidence').textContent=top?Math.round(top.observed_possessions).toLocaleString():'—';
    if(!d.lineups.length){
      target.classList.add('empty');target.innerHTML='<span>No eligible five-man combinations for this snapshot.</span>';return;
    }
    target.classList.remove('empty');
    target.innerHTML=d.lineups.map(function(row,i){
      const names=row.player_meta.map(function(p){return p.player_name}).join(' · ');
      const weight=Math.round(100*row.observed_weight);
      return '<div class="lineup-opt-row">'
        +'<div class="lineup-opt-rank">'+String(i+1).padStart(2,'0')+'</div>'
        +'<div class="lineup-opt-players"><strong>'+names+'</strong><span>'+d.team+' · '+(row.observed_possessions>0?'observed unit':'unseen combination')+'</span></div>'
        +'<div class="lineup-opt-stat"><span>MODEL NET</span><strong>'+(row.blended_net_rating>=0?'+':'')+row.blended_net_rating.toFixed(1)+'</strong></div>'
        +'<div class="lineup-opt-band">'+(row.blended_lower_80>=0?'+':'')+row.blended_lower_80.toFixed(1)+' → '+(row.blended_upper_80>=0?'+':'')+row.blended_upper_80.toFixed(1)+'</div>'
        +'<div class="lineup-opt-stat"><span>EVIDENCE</span><strong>'+Math.round(row.observed_possessions)+' poss · '+weight+'%</strong></div>'
        +'<button data-load-opt-lineup="'+row.players.join(',')+'">LOAD A ↗</button>'
        +'</div>';
    }).join('');
    document.querySelectorAll('[data-load-opt-lineup]').forEach(function(button){
      button.onclick=function(){
        lineupA=button.dataset.loadOptLineup.split(',');
        lineupB=lineupB.filter(function(pid){return !lineupA.includes(pid)});
        resetLineupResult();renderLineupSlots();renderLineupPool();
        $('lineup-margin-note').textContent='optimized group loaded into Lineup A';
      };
    });
  }catch(e){
    target.classList.add('empty');target.innerHTML='<span>'+e.message+'</span>';
  }finally{button.disabled=false}
};
$('lineup-opt-team').onchange=resetLineupOptimizer;
$('lineup-opt-limit').onchange=resetLineupOptimizer;

async function loadImpact(){
  const alpha=Number($('impact-alpha').value||1000);
  const params=new URLSearchParams({alpha:String(alpha),limit:'500'});
  if($('impact-date').value)params.set('as_of',$('impact-date').value);
  const d=await json('/api/impact?'+params);
  impactData=d;
  $('impact-stints').textContent=d.stints.toLocaleString();
  $('impact-games').textContent=d.games.toLocaleString();
  $('impact-home').textContent=d.home_court_per_100.toFixed(2);
  $('impact-rmse').textContent=d.weighted_rmse.toFixed(2);
  const kept=d.qa?.possessions_kept,seen=d.qa?.possessions_seen;
  const qa=(kept!=null&&seen)?` · kept ${kept.toLocaleString()}/${seen.toLocaleString()}`:'';
  $('impact-source').textContent=(d.source?.kind==='normalized_snapshot'?'NORMALIZED REAL STINTS':'SYNTHETIC STINTS')+(d.as_of?' · AS OF '+d.as_of:' · FULL SNAPSHOT')+qa;
  renderImpactRows(d.players);
  drawImpactScatter(d.players);
  if(d.players[0])loadImpactPath(d.players[0].player_id);
}
function renderImpactRows(rows){
  const q=($('impact-search').value||'').trim().toLowerCase();
  const filtered=rows.filter(p=>!q||p.player_name.toLowerCase().includes(q)||p.team.toLowerCase().includes(q));
  $('impact-rows').innerHTML=filtered.map((p,i)=>`<tr data-impact-player="${p.player_id}">
    <td>${p.rank}</td><td>${p.player_name}</td><td>${p.team}</td>
    <td class="${p.impact_per_100>=0?'impact-positive':'impact-negative'}">${p.impact_per_100>=0?'+':''}${p.impact_per_100.toFixed(2)}</td>
    <td class="impact-band">${p.lower_80>=0?'+':''}${p.lower_80.toFixed(2)} → ${p.upper_80>=0?'+':''}${p.upper_80.toFixed(2)}</td>
    <td>${Math.round(p.possessions).toLocaleString()}</td>
  </tr>`).join('');
  document.querySelectorAll('[data-impact-player]').forEach(row=>row.onclick=()=>{document.querySelectorAll('[data-impact-player]').forEach(x=>x.classList.remove('active'));row.classList.add('active');loadImpactPath(row.dataset.impactPlayer)});
}
$('impact-alpha').onchange=loadImpact;
$('impact-date').onchange=loadImpact;
$('impact-latest').onclick=()=>{$('impact-date').value='';loadImpact()};
$('impact-search').oninput=()=>impactData&&renderImpactRows(impactData.players);
async function loadImpactPath(playerId){
  const q=new URLSearchParams();if($('impact-date').value)q.set('as_of',$('impact-date').value);
  const d=await json(`/api/impact/${playerId}/path`+(q.toString()?('?'+q):''));
  selectedImpactPlayerId=playerId;$('impact-detail-name').textContent=`${d.player.player_name} · ${d.player.team}`;$('impact-to-scenario').disabled=false;
  const current=impactData?.players.find(p=>p.player_id===playerId);
  $('impact-detail-meta').textContent=current?`Current α ${impactData.alpha.toFixed(0)} · RAPM ${current.impact_per_100>=0?'+':''}${current.impact_per_100.toFixed(2)} / 100 · approx 80% band ${current.lower_80>=0?'+':''}${current.lower_80.toFixed(2)} to ${current.upper_80>=0?'+':''}${current.upper_80.toFixed(2)} · ${Math.round(current.possessions).toLocaleString()} possessions`:'Regularization path';
  drawImpactPath(d.points);
}
function drawImpactPath(points){
  const el=$('impact-path-chart');if(!points.length){el.innerHTML='';return}
  const W=430,H=220,pad=34;const vals=points.map(p=>p.impact_per_100);const min=Math.min(...vals,0)-.5,max=Math.max(...vals,0)+.5;
  const x=i=>pad+(W-2*pad)*(i/Math.max(1,points.length-1));const y=v=>H-pad-(H-2*pad)*((v-min)/Math.max(.01,max-min));
  const path=points.map((p,i)=>`${i?'L':'M'}${x(i)},${y(p.impact_per_100)}`).join(' ');
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line class="grid" x1="${pad}" y1="${y(0)}" x2="${W-pad}" y2="${y(0)}"/><path class="path-line" d="${path}"/>${points.map((p,i)=>`<circle class="path-dot" cx="${x(i)}" cy="${y(p.impact_per_100)}" r="5"><title>α ${p.alpha} · ${p.impact_per_100.toFixed(2)} · rank ${p.rank}</title></circle><text x="${x(i)-10}" y="${H-8}">${p.alpha}</text>`).join('')}<text x="3" y="${y(max)+4}">${max.toFixed(1)}</text><text x="3" y="${y(min)+4}">${min.toFixed(1)}</text></svg>`;
}
function drawImpactScatter(players){
  const el=$('impact-scatter');if(!players.length){el.innerHTML='';return}
  const W=900,H=300,pad=42;const xs=players.map(p=>p.possessions),ys=players.map(p=>p.impact_per_100);const maxX=Math.max(...xs),minY=Math.min(...ys)-.5,maxY=Math.max(...ys)+.5;
  const x=v=>pad+(W-2*pad)*(v/Math.max(1,maxX));const y=v=>H-pad-(H-2*pad)*((v-minY)/Math.max(.01,maxY-minY));const exposureCut=maxX*.25;
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line class="zero" x1="${pad}" y1="${y(0)}" x2="${W-pad}" y2="${y(0)}"/><line class="grid" x1="${x(exposureCut)}" y1="${pad}" x2="${x(exposureCut)}" y2="${H-pad}"/>${players.map(p=>`<circle class="scatter-point ${p.possessions<exposureCut?'low-sample':''}" cx="${x(p.possessions)}" cy="${y(p.impact_per_100)}" r="5"><title>${p.player_name} · ${p.team} · RAPM ${p.impact_per_100.toFixed(2)} · 80% ${p.lower_80.toFixed(2)} to ${p.upper_80.toFixed(2)} · ${Math.round(p.possessions)} poss</title></circle>`).join('')}<text x="${pad}" y="${H-8}">0 poss</text><text x="${W-pad-50}" y="${H-8}">${Math.round(maxX)} poss</text><text x="3" y="${y(maxY)+3}">${maxY.toFixed(1)}</text><text x="3" y="${y(minY)+3}">${minY.toFixed(1)}</text></svg>`;
}



function encodeScenarioSpec(spec){
  const bytes=new TextEncoder().encode(JSON.stringify(spec));
  let binary='';
  bytes.forEach(function(byte){binary+=String.fromCharCode(byte)});
  return btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
function decodeScenarioSpec(value){
  const padded=value.replace(/-/g,'+').replace(/_/g,'/')+'==='.slice((value.length+3)%4);
  const binary=atob(padded);
  const bytes=Uint8Array.from(binary,function(ch){return ch.charCodeAt(0)});
  return JSON.parse(new TextDecoder().decode(bytes));
}
function scenarioShareSpec(){
  return {
    v:1,
    request:buildScenarioRequest(),
    award_trials:Number($('scenario-award-trials').value||750)
  };
}
function setScenarioShareStatus(message,isError){
  const el=$('scenario-share-status');
  el.textContent=message||'';
  el.classList.toggle('error',!!isError);
}
function clearScenarioResults(){
  scenarioLast=null;
  scenarioLastRequest=null;
  $('scenario-win-swing').textContent='—';
  $('scenario-title-swing').textContent='—';
  $('scenario-sims').textContent='—';
  $('scenario-effects').classList.add('empty');
  $('scenario-effects').innerHTML='<span>Build an intervention to inspect the model translation.</span>';
  $('scenario-bars').classList.add('empty');
  $('scenario-bars').innerHTML='<span>Run the scenario to reveal league-wide effects.</span>';
  $('scenario-rows').innerHTML='';
  $('scenario-award-panel').hidden=true;
  $('scenario-schedule-status').textContent='run a scenario';
  $('scenario-schedule').classList.add('empty');
  $('scenario-schedule').innerHTML='<span>Affected future games will appear here with their combined strength and win-probability shifts.</span>';
  $('scenario-sensitivity-rows').classList.add('empty');
  $('scenario-sensitivity-rows').innerHTML='<span>Run a scenario, then compare lower-signal, point, and upper-signal player-impact worlds.</span>';
  $('scenario-award-future-bars').classList.add('empty');
  $('scenario-award-future-bars').innerHTML='<span>Run an alternate world, then propagate it through the remaining MVP simulation.</span>';
  $('scenario-lineup-results').classList.add('empty');
  $('scenario-lineup-results').innerHTML='<span>Trade or remove a player, then recompute the affected teams\' best modeled five-man groups.</span>';
}
async function applyScenarioShareSpec(spec){
  if(!spec||spec.v!==1||!spec.request)throw Error('Unsupported scenario link format.');
  const request=spec.request;
  if(request.as_of)$('scenario-date').value=request.as_of;
  if(request.trials)$('scenario-trials').value=String(request.trials);
  if(request.alpha)$('scenario-alpha').value=String(request.alpha);
  if(spec.award_trials)$('scenario-award-trials').value=String(spec.award_trials);
  await loadScenarioPlayers();
  await loadScenarioHistory();

  scenarioAbsences=(request.absences||[]).map(function(a){
    const player=scenarioPlayers.find(function(p){return p.player_id===a.player_id});
    return {
      player_id:a.player_id,
      games_missed:Number(a.games_missed||8),
      minutes_per_game:Number(a.minutes_per_game||34),
      replacement_impact_per_100:Number(a.replacement_impact_per_100||0),
      impact_per_100:player?player.impact_per_100:0
    };
  }).filter(function(a){return scenarioPlayers.some(function(p){return p.player_id===a.player_id})});

  const flip=(request.flipped_game_ids||[])[0]||'';
  if([].slice.call($('scenario-flip-game').options).some(function(o){return o.value===flip}))$('scenario-flip-game').value=flip;

  const trade=(request.trades||[])[0];
  $('scenario-trade-enabled').checked=!!trade;
  $('scenario-trade-fields').hidden=!trade;
  renderScenarioTradeOptions();
  if(trade){
    if(scenarioPlayers.some(function(p){return p.player_id===trade.player_a_id}))$('scenario-trade-a').value=trade.player_a_id;
    if(scenarioPlayers.some(function(p){return p.player_id===trade.player_b_id}))$('scenario-trade-b').value=trade.player_b_id;
    $('scenario-trade-minutes').value=String(trade.minutes_per_game||34);
  }
  renderScenarioAbsences();
  clearScenarioResults();
  updateScenarioCountPreview();
}
async function restoreScenarioFromUrl(){
  const encoded=new URLSearchParams(window.location.search).get('scenario');
  if(!encoded)return false;
  try{
    await applyScenarioShareSpec(decodeScenarioSpec(encoded));
    setScenarioShareStatus('Scenario restored from shared link.',false);
    return true;
  }catch(e){
    setScenarioShareStatus('Could not restore scenario: '+e.message,true);
    return false;
  }
}
$('scenario-copy').onclick=async function(){
  try{
    const spec=scenarioShareSpec();
    validateScenarioRequest(spec.request);
    const url=new URL(window.location.href);
    url.searchParams.set('scenario',encodeScenarioSpec(spec));
    url.hash='';
    history.replaceState(null,'',url);
    if(navigator.clipboard&&navigator.clipboard.writeText){
      await navigator.clipboard.writeText(url.toString());
      setScenarioShareStatus('Scenario link copied. Opening it restores this exact world.',false);
    }else{
      setScenarioShareStatus('Scenario encoded in the current URL. Copy it from the address bar.',false);
    }
  }catch(e){
    setScenarioShareStatus(e.message,true);
  }
};
$('scenario-reset').onclick=async function(){
  scenarioAbsences=[];
  $('scenario-trade-enabled').checked=false;
  $('scenario-trade-fields').hidden=true;
  $('scenario-trade-minutes').value='34';
  $('scenario-flip-game').value='';
  $('scenario-date').value='2026-01-15';
  $('scenario-trials').value='5000';
  $('scenario-alpha').value='1000';
  $('scenario-award-trials').value='750';
  await loadScenarioPlayers();
  await loadScenarioHistory();
  renderScenarioAbsences();
  clearScenarioResults();
  const url=new URL(window.location.href);
  url.searchParams.delete('scenario');
  history.replaceState(null,'',url);
  setScenarioShareStatus('Scenario reset.',false);
}

async function loadScenario(){
  await loadScenarioPlayers();
  await loadScenarioHistory();
  if(pendingScenarioFlipGameId){
    const gameId=pendingScenarioFlipGameId;
    const exists=[].slice.call($('scenario-flip-game').options).some(function(option){return option.value===gameId});
    if(exists)$('scenario-flip-game').value=gameId;
    pendingScenarioFlipGameId=null;
    setScenarioShareStatus(exists?'Replay branch loaded. Add more interventions or run the world.':'Replay game is not available before this cutoff.',!exists);
  }
  if(!scenarioAbsences.length&&!$('scenario-flip-game').value&&!$('scenario-trade-enabled').checked){
    addScenarioAbsence(selectedImpactPlayerId||((scenarioPlayers[0]||{}).player_id));
  }
  renderScenarioAbsences();
  updateScenarioCountPreview();
}
async function loadScenarioHistory(){
  const select=$('scenario-flip-game');
  const previous=select.value;
  const rows=await json('/api/games?before='+$('scenario-date').value+'&limit=100');
  select.innerHTML='<option value="">No game flip</option>'+rows.map(function(g){
    return '<option value="'+g.game_id+'">'+g.date+' · '+g.away_team+' '+g.away_score+' @ '+g.home_team+' '+g.home_score+'</option>';
  }).join('');
  if(rows.some(function(g){return g.game_id===previous}))select.value=previous;
}
$('scenario-date').onchange=loadScenarioHistory;
async function loadScenarioPlayers(){
  const alpha=Number($('scenario-alpha').value||1000);
  const d=await json('/api/impact?alpha='+alpha+'&limit=500');
  scenarioPlayers=d.players||[];
  scenarioAbsences=scenarioAbsences.map(function(a){
    const p=scenarioPlayers.find(function(x){return x.player_id===a.player_id});
    return Object.assign({},a,{impact_per_100:p?p.impact_per_100:a.impact_per_100});
  });
  renderScenarioTradeOptions();
}

function renderScenarioTradeOptions(){
  const aSelect=$('scenario-trade-a'),bSelect=$('scenario-trade-b');
  const prevA=aSelect.value,prevB=bSelect.value;
  const options=scenarioPlayers.map(function(p){
    return '<option value="'+p.player_id+'">'+p.player_name+' · '+p.team+' · '+(p.impact_per_100>=0?'+':'')+p.impact_per_100.toFixed(2)+'</option>';
  }).join('');
  aSelect.innerHTML=options;bSelect.innerHTML=options;
  if(scenarioPlayers.some(function(p){return p.player_id===prevA}))aSelect.value=prevA;
  else if(selectedImpactPlayerId&&scenarioPlayers.some(function(p){return p.player_id===selectedImpactPlayerId}))aSelect.value=selectedImpactPlayerId;
  if(scenarioPlayers.some(function(p){return p.player_id===prevB}))bSelect.value=prevB;
  if(!bSelect.value||bSelect.value===aSelect.value||sameScenarioTradeTeam()){
    const a=scenarioPlayers.find(function(p){return p.player_id===aSelect.value});
    const other=scenarioPlayers.find(function(p){return p.player_id!==aSelect.value&&(!a||p.team!==a.team)});
    if(other)bSelect.value=other.player_id;
  }
}
function sameScenarioTradeTeam(){
  const a=scenarioPlayers.find(function(p){return p.player_id===$('scenario-trade-a').value});
  const b=scenarioPlayers.find(function(p){return p.player_id===$('scenario-trade-b').value});
  return !!(a&&b&&a.team===b.team);
}
$('scenario-trade-enabled').onchange=function(){
  $('scenario-trade-fields').hidden=!this.checked;
  updateScenarioCountPreview();
};
$('scenario-trade-a').onchange=function(){
  const value=this.value;
  if(value===$('scenario-trade-b').value||sameScenarioTradeTeam()){
    const a=scenarioPlayers.find(function(p){return p.player_id===value});
    const other=scenarioPlayers.find(function(p){return p.player_id!==value&&(!a||p.team!==a.team)});
    if(other)$('scenario-trade-b').value=other.player_id;
  }
};
$('scenario-trade-b').onchange=function(){
  const value=this.value;
  if(value===$('scenario-trade-a').value||sameScenarioTradeTeam()){
    const b=scenarioPlayers.find(function(p){return p.player_id===value});
    const other=scenarioPlayers.find(function(p){return p.player_id!==value&&(!b||p.team!==b.team)});
    if(other)$('scenario-trade-a').value=other.player_id;
  }
};
function updateScenarioCountPreview(){
  const count=scenarioAbsences.length+($('scenario-flip-game').value?1:0)+($('scenario-trade-enabled').checked?1:0);
  $('scenario-count').textContent=count;
}
$('scenario-flip-game').onchange=updateScenarioCountPreview;

function addScenarioAbsence(playerId){
  if(scenarioAbsences.length>=3)return;
  let available=scenarioPlayers.find(function(p){return p.player_id===playerId&&!scenarioAbsences.some(function(a){return a.player_id===p.player_id})});
  if(!available)available=scenarioPlayers.find(function(p){return !scenarioAbsences.some(function(a){return a.player_id===p.player_id})});
  if(!available)return;
  scenarioAbsences.push({player_id:available.player_id,games_missed:8,minutes_per_game:34,replacement_impact_per_100:0,impact_per_100:available.impact_per_100});
  renderScenarioAbsences();
}
function renderScenarioAbsences(){
  updateScenarioCountPreview();
  $('scenario-add').disabled=scenarioAbsences.length>=3;
  $('scenario-absence-list').innerHTML=scenarioAbsences.map(function(a,i){
    const options=scenarioPlayers.map(function(p){
      return '<option value="'+p.player_id+'" '+(p.player_id===a.player_id?'selected':'')+'>'+p.player_name+' · '+p.team+' · '+(p.impact_per_100>=0?'+':'')+p.impact_per_100.toFixed(2)+'</option>';
    }).join('');
    const player=scenarioPlayers.find(function(p){return p.player_id===a.player_id});
    return '<div class="absence-card" data-absence-index="'+i+'">'
      +'<div class="absence-head"><strong>ABSENCE '+String(i+1).padStart(2,'0')+'</strong><button data-remove-absence="'+i+'">×</button></div>'
      +'<label>Player<select data-absence-field="player_id" data-index="'+i+'">'+options+'</select></label>'
      +'<div class="absence-grid">'
      +'<label>Games missed<input type="number" min="1" max="82" value="'+a.games_missed+'" data-absence-field="games_missed" data-index="'+i+'"></label>'
      +'<label>Minutes / game<input type="number" min="1" max="48" step="1" value="'+a.minutes_per_game+'" data-absence-field="minutes_per_game" data-index="'+i+'"></label>'
      +'</div>'
      +'<label>Replacement RAPM / 100<input type="number" min="-10" max="10" step=".25" value="'+a.replacement_impact_per_100+'" data-absence-field="replacement_impact_per_100" data-index="'+i+'"></label>'
      +'<div class="absence-impact-hint">'+(player?(player.player_name+': RAPM '+(player.impact_per_100>=0?'+':'')+player.impact_per_100.toFixed(2)+' / 100 · '+Math.round(player.possessions).toLocaleString()+' possessions'):'Select a player.')+'</div>'
      +'</div>';
  }).join('');
  document.querySelectorAll('[data-remove-absence]').forEach(function(b){b.onclick=function(){scenarioAbsences.splice(Number(b.dataset.removeAbsence),1);renderScenarioAbsences()}});
  document.querySelectorAll('[data-absence-field]').forEach(function(el){el.onchange=function(){
    const i=Number(el.dataset.index),field=el.dataset.absenceField;
    let value=el.value;if(field!=='player_id')value=Number(value);
    scenarioAbsences[i][field]=value;
    if(field==='player_id'){const p=scenarioPlayers.find(function(x){return x.player_id===value});scenarioAbsences[i].impact_per_100=p?p.impact_per_100:0}
    renderScenarioAbsences();
  }});
}
$('scenario-add').onclick=function(){addScenarioAbsence()};
$('scenario-alpha').onchange=async function(){await loadScenarioPlayers();renderScenarioAbsences()};
$('impact-to-scenario').onclick=function(){
  if(!selectedImpactPlayerId)return;
  if(!scenarioAbsences.some(function(a){return a.player_id===selectedImpactPlayerId})){
    if(scenarioAbsences.length>=3)scenarioAbsences.shift();
    const p=(impactData&&impactData.players||[]).find(function(x){return x.player_id===selectedImpactPlayerId});
    scenarioAbsences.push({player_id:selectedImpactPlayerId,games_missed:8,minutes_per_game:34,replacement_impact_per_100:0,impact_per_100:p?p.impact_per_100:0});
  }
  openView('scenario');
};

function buildScenarioRequest(){
  const tradeEnabled=$('scenario-trade-enabled').checked;
  return {
    as_of:$('scenario-date').value,
    trials:Number($('scenario-trials').value),
    seed:2026,
    alpha:Number($('scenario-alpha').value),
    flipped_game_ids:$('scenario-flip-game').value?[$('scenario-flip-game').value]:[],
    trades:tradeEnabled?[{
      player_a_id:$('scenario-trade-a').value,
      player_b_id:$('scenario-trade-b').value,
      minutes_per_game:Number($('scenario-trade-minutes').value)
    }]:[],
    absences:scenarioAbsences.map(function(a){return {
      player_id:a.player_id,
      games_missed:Number(a.games_missed),
      minutes_per_game:Number(a.minutes_per_game),
      replacement_impact_per_100:Number(a.replacement_impact_per_100)
    }})
  };
}
function validateScenarioRequest(body){
  const ids=body.absences.map(function(a){return a.player_id});
  if(new Set(ids).size!==ids.length)throw Error('Each player can appear only once in a scenario.');
  if(!body.absences.length&&!body.trades.length&&!body.flipped_game_ids.length)throw Error('Add at least one scenario intervention.');
  if(body.trades.length){
    const trade=body.trades[0];
    if(trade.player_a_id===trade.player_b_id)throw Error('Trade players must be different.');
    if(sameScenarioTradeTeam())throw Error('Trade players must come from different teams.');
    if(ids.includes(trade.player_a_id)||ids.includes(trade.player_b_id))throw Error('A traded player cannot also be absent in the same scenario yet.');
  }
}
$('scenario-run').onclick=async function(){
  const button=$('scenario-run');button.disabled=true;
  try{
    const body=buildScenarioRequest();validateScenarioRequest(body);
    const d=await json('/api/scenario/player-absence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    scenarioLast=d;scenarioLastRequest=body;renderScenario(d);
  }catch(e){
    $('scenario-effects').classList.add('empty');$('scenario-effects').innerHTML='<span>'+e.message+'</span>';
  }finally{button.disabled=false}
};

$('scenario-sensitivity-run').onclick=async function(){
  const button=$('scenario-sensitivity-run');button.disabled=true;
  const target=$('scenario-sensitivity-rows');
  target.classList.add('empty');target.innerHTML='<span>Running paired sensitivity worlds…</span>';
  try{
    const body=buildScenarioRequest();validateScenarioRequest(body);
    const trials=Number($('scenario-sensitivity-trials').value);
    const d=await json('/api/scenario/sensitivity?sensitivity_trials='+trials,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    renderScenarioSensitivity(d);
  }catch(e){
    target.classList.add('empty');target.innerHTML='<span>'+e.message+'</span>';
  }finally{button.disabled=false}
};
function renderScenarioSensitivity(d){
  const target=$('scenario-sensitivity-rows');
  const baseline=Object.fromEntries(d.baseline.teams.map(function(x){return [x.team,x]}));
  const point=Object.fromEntries(d.point.teams.map(function(x){return [x.team,x]}));
  const low=Object.fromEntries(d.impact_lower.teams.map(function(x){return [x.team,x]}));
  const high=Object.fromEntries(d.impact_upper.teams.map(function(x){return [x.team,x]}));
  const summaries=(d.team_sensitivity||[]).slice(0,8);
  const teams=summaries.length?summaries.map(function(row){return row.team}):Object.keys(point).slice(0,8);
  const changed=teams.some(function(team){
    return Math.abs(low[team].expected_wins-high[team].expected_wins)>.001
      || Math.abs(low[team].championship_probability-high[team].championship_probability)>.0001;
  });
  if(!changed){
    target.classList.add('empty');
    target.innerHTML='<span>This scenario has no player-impact uncertainty component; the lower, point, and upper worlds are identical.</span>';
    return;
  }
  const summaryBy=Object.fromEntries(summaries.map(function(row){return [row.team,row]}));
  target.classList.remove('empty');
  target.innerHTML=teams.map(function(team){
    const s=summaryBy[team];
    const stable=!s||(s.expected_wins_direction_stable&&s.championship_direction_stable);
    const badge=stable?'STABLE':'FRAGILE';
    const winsRange=s?s.expected_wins_range:null;
    const titleRange=s?s.championship_probability_range:null;
    return '<div class="sensitivity-row">'
      +'<div class="sensitivity-team"><strong>'+team+'</strong><span>signal low → point → high</span><em class="sensitivity-badge '+(stable?'stable':'fragile')+'">'+badge+'</em></div>'
      +'<div class="sensitivity-metric"><span>EXPECTED WINS</span><div class="sensitivity-triplet"><strong class="low">'+low[team].expected_wins.toFixed(1)+'</strong><i>→</i><strong class="point">'+point[team].expected_wins.toFixed(1)+'</strong><i>→</i><strong class="high">'+high[team].expected_wins.toFixed(1)+'</strong></div>'+(winsRange?'<small>Δ range '+signed(winsRange[0])+' to '+signed(winsRange[1])+'</small>':'')+'</div>'
      +'<div class="sensitivity-metric"><span>TITLE ODDS</span><div class="sensitivity-triplet"><strong class="low">'+pct(low[team].championship_probability)+'</strong><i>→</i><strong class="point">'+pct(point[team].championship_probability)+'</strong><i>→</i><strong class="high">'+pct(high[team].championship_probability)+'</strong></div>'+(titleRange?'<small>Δ range '+(titleRange[0]>=0?'+':'')+(100*titleRange[0]).toFixed(2)+' to '+(titleRange[1]>=0?'+':'')+(100*titleRange[1]).toFixed(2)+' pts</small>':'')+'</div>'
      +'</div>';
  }).join('');
}


$('scenario-lineups-run').onclick=async function(){
  const button=$('scenario-lineups-run'),target=$('scenario-lineup-results');
  button.disabled=true;
  target.classList.add('empty');
  target.innerHTML='<span>Rebuilding affected rosters and enumerating closing groups…</span>';
  try{
    const body=buildScenarioRequest();validateScenarioRequest(body);
    if(!body.absences.length&&!body.trades.length)throw Error('This scenario does not change player availability or roster membership.');
    const topK=Number($('scenario-lineup-limit').value);
    const d=await json('/api/scenario/lineups?top_k='+topK,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    renderScenarioLineups(d);
  }catch(e){
    target.classList.add('empty');
    target.innerHTML='<span>'+e.message+'</span>';
  }finally{button.disabled=false}
};
function scenarioLineupFive(row,kind,team,asOf,alpha){
  const names=row.player_meta.map(function(p){return p.player_name}).join(' · ');
  const evidence=row.observed_possessions>0
    ? Math.round(row.observed_possessions)+' observed poss · '+Math.round(100*row.observed_weight)+'% empirical'
    : 'unseen group · RAPM prior only';
  const load=kind==='scenario'
    ? '<button data-scenario-lineup-load="'+row.players.join(',')+'" data-lineup-asof="'+asOf+'" data-lineup-alpha="'+alpha+'">LOAD A ↗</button>'
    : '';
  return '<div class="scenario-lineup-five"><div><strong>'+names+'</strong><small>'+evidence+' · band '+row.blended_lower_80.toFixed(1)+' to '+row.blended_upper_80.toFixed(1)+'</small></div><strong>'+(row.blended_net_rating>=0?'+':'')+row.blended_net_rating.toFixed(1)+'</strong>'+load+'</div>';
}
function renderScenarioLineups(d){
  const target=$('scenario-lineup-results');
  if(!d.teams?.length){target.classList.add('empty');target.innerHTML='<span>No affected rosters could be optimized.</span>';return}
  target.classList.remove('empty');
  target.innerHTML=d.teams.map(function(team){
    const delta=team.top_score_delta;
    const deltaText=delta==null?'—':((delta>=0?'+':'')+delta.toFixed(1));
    const baseline=team.baseline_lineups.slice(0,Math.min(2,team.baseline_lineups.length)).map(function(row){return scenarioLineupFive(row,'baseline',team.team,d.as_of,d.alpha)}).join('');
    const scenario=team.scenario_lineups.slice(0,Math.min(3,team.scenario_lineups.length)).map(function(row){return scenarioLineupFive(row,'scenario',team.team,d.as_of,d.alpha)}).join('');
    return '<div class="scenario-lineup-team">'
      +'<div class="scenario-lineup-team-head"><strong>'+team.team+' closing groups</strong><span>'+team.baseline_candidate_players+' → '+team.scenario_candidate_players+' available players · top score <b class="scenario-lineup-delta '+((delta||0)>=0?'positive':'negative')+'">'+deltaText+'</b></span></div>'
      +'<div class="scenario-lineup-worlds"><div class="scenario-lineup-world"><span>BASELINE ROSTER</span>'+baseline+'</div><div class="scenario-lineup-world"><span>SCENARIO ROSTER</span>'+scenario+'</div></div>'
      +'</div>';
  }).join('');
  document.querySelectorAll('[data-scenario-lineup-load]').forEach(function(button){
    button.onclick=async function(){
      $('lineup-date').value=button.dataset.lineupAsof||'';
      $('lineup-alpha').value=button.dataset.lineupAlpha||'1000';
      openView('lineup');
      await loadLineup();
      const requested=button.dataset.scenarioLineupLoad.split(',');
      const available=new Set(lineupPool.map(function(p){return p.player_id}));
      lineupA=requested.filter(function(pid){return available.has(pid)});
      lineupB=lineupB.filter(function(pid){return !lineupA.includes(pid)});
      resetLineupResult();renderLineupSlots();renderLineupPool();
      $('lineup-margin-note').textContent='Scenario closing group loaded into Lineup A';
    };
  });
}

$('scenario-awards-run').onclick=async function(){
  const button=$('scenario-awards-run');button.disabled=true;
  const target=$('scenario-award-future-bars');
  target.classList.add('empty');target.innerHTML='<span>Simulating award futures in both worlds…</span>';
  try{
    const body=buildScenarioRequest();validateScenarioRequest(body);
    const trials=Number($('scenario-award-trials').value);
    const d=await json('/api/scenario/awards?award_trials='+trials,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    renderScenarioAwardFuture(d);
  }catch(e){
    target.classList.add('empty');target.innerHTML='<span>'+e.message+'</span>';
  }finally{button.disabled=false}
};
function renderScenarioAwardFuture(d){
  const target=$('scenario-award-future-bars');
  const rows=(d.deltas||[]).slice(0,10);
  if(!rows.length){target.classList.add('empty');target.innerHTML='<span>No overlapping award candidates for this scenario.</span>';return}
  const max=Math.max.apply(null,rows.map(function(x){return Math.abs(x.leader_probability_delta)}).concat([.001]));
  target.classList.remove('empty');
  target.innerHTML=rows.map(function(row){
    const delta=row.leader_probability_delta;
    const width=50*Math.abs(delta)/max;
    const teamText=row.baseline_team===row.altered_team?row.altered_team:(row.baseline_team+' → '+row.altered_team);
    return '<div class="scenario-award-future-row">'
      +'<div class="player"><strong>'+row.player_name+'</strong><span>'+teamText+'</span></div>'
      +'<div class="scenario-award-shift-track"><span class="scenario-award-shift-zero"></span><span class="scenario-award-shift-fill '+(delta>=0?'pos':'neg')+'" style="width:'+width+'%"></span></div>'
      +'<strong>'+pct(row.baseline_leader_probability)+' → '+pct(row.altered_leader_probability)+'</strong>'
      +'<small class="'+(delta>=0?'positive':'negative')+'">'+(delta>=0?'+':'')+(100*delta).toFixed(1)+' pts</small>'
      +'</div>';
  }).join('');
}

function renderScenario(d){
  const deltas=d.deltas||[];
  const altered=Object.fromEntries(d.altered.teams.map(function(x){return [x.team,x]}));
  $('scenario-count').textContent=(d.player_absences||[]).length+(d.historical_flips||[]).length+(d.trades||[]).length;$('scenario-sims').textContent=d.trials.toLocaleString();
  const biggestWin=[].concat(deltas).sort(function(a,b){return Math.abs(b.expected_wins_delta)-Math.abs(a.expected_wins_delta)})[0];
  const biggestTitle=[].concat(deltas).sort(function(a,b){return Math.abs(b.championship_probability_delta)-Math.abs(a.championship_probability_delta)})[0];
  $('scenario-win-swing').textContent=biggestWin?(biggestWin.team+' '+signed(biggestWin.expected_wins_delta)):'—';
  $('scenario-title-swing').textContent=biggestTitle?(biggestTitle.team+' '+(biggestTitle.championship_probability_delta>=0?'+':'')+(100*biggestTitle.championship_probability_delta).toFixed(1)+' pts'):'—';
  $('scenario-effects').classList.remove('empty');
  const historyCards=(d.historical_flips||[]).map(function(flip){
    return '<div class="scenario-effect"><span>HISTORICAL BRANCH · '+flip.game_date+'</span><strong>'+flip.original_winner+' → '+flip.flipped_winner+'</strong><small>'+flip.away_team+' @ '+flip.home_team+' · completed result reversed before rebuilding the point-in-time state</small></div>';
  });
  const absenceCards=d.player_absences.map(function(e){
    return '<div class="scenario-effect"><span>'+e.player_name+' · '+e.team+' · '+e.games_missed+' games</span>'
      +'<strong>'+(e.margin_delta_per_game>=0?'+':'')+e.margin_delta_per_game.toFixed(2)+' pts/game → '+(e.elo_delta_per_game>=0?'+':'')+e.elo_delta_per_game.toFixed(0)+' Elo</strong>'
      +'<small>RAPM '+(e.impact_per_100>=0?'+':'')+e.impact_per_100.toFixed(2)+' (80% '+e.impact_lower_80.toFixed(2)+' to '+e.impact_upper_80.toFixed(2)+') → replacement '+(e.replacement_impact_per_100>=0?'+':'')+e.replacement_impact_per_100.toFixed(2)+' · '+e.minutes_per_game.toFixed(0)+' MPG · '+e.affected_game_ids.length+' scheduled games affected<br>margin band '+e.margin_delta_low_80.toFixed(2)+' to '+e.margin_delta_high_80.toFixed(2)+' · Elo band '+e.elo_delta_low_80.toFixed(0)+' to '+e.elo_delta_high_80.toFixed(0)+'</small></div>';
  });
  const tradeCards=(d.trades||[]).map(function(e){
    return '<div class="scenario-effect"><span>TRADE · '+e.team_a+' ⇄ '+e.team_b+'</span>'
      +'<strong>'+e.player_a_name+' ⇄ '+e.player_b_name+'</strong>'
      +'<small>'+e.team_a+': '+(e.team_a_margin_delta_per_game>=0?'+':'')+e.team_a_margin_delta_per_game.toFixed(2)+' pts/game ('+e.team_a_margin_delta_low_80.toFixed(2)+' to '+e.team_a_margin_delta_high_80.toFixed(2)+') · '+(e.team_a_elo_delta_per_game>=0?'+':'')+e.team_a_elo_delta_per_game.toFixed(0)+' Elo · '+e.team_a_affected_games.length+' games<br>'
      +e.team_b+': '+(e.team_b_margin_delta_per_game>=0?'+':'')+e.team_b_margin_delta_per_game.toFixed(2)+' pts/game ('+e.team_b_margin_delta_low_80.toFixed(2)+' to '+e.team_b_margin_delta_high_80.toFixed(2)+') · '+(e.team_b_elo_delta_per_game>=0?'+':'')+e.team_b_elo_delta_per_game.toFixed(0)+' Elo · '+e.team_b_affected_games.length+' games</small></div>';
  });
  $('scenario-effects').innerHTML=historyCards.concat(tradeCards,absenceCards).join('');
  renderScenarioAwardRipple(d);
  renderScenarioSchedule(d);
  renderScenarioBars();
  $('scenario-rows').innerHTML=d.baseline.teams.map(function(x){
    const y=altered[x.team],z=deltas.find(function(v){return v.team===x.team});
    return '<tr><td>'+x.team+'</td><td>'+x.expected_wins.toFixed(1)+' → '+y.expected_wins.toFixed(1)+'</td><td>'+pct(x.playoffs_probability)+' → '+pct(y.playoffs_probability)+'</td><td>'+pct(x.championship_probability)+' → '+pct(y.championship_probability)+'</td>'
      +'<td class="'+(z.expected_wins_delta>=0?'positive':'negative')+'">'+signed(z.expected_wins_delta)+'</td>'
      +'<td class="'+(z.playoffs_probability_delta>=0?'positive':'negative')+'">'+(z.playoffs_probability_delta>=0?'+':'')+(100*z.playoffs_probability_delta).toFixed(1)+' pts</td>'
      +'<td class="'+(z.championship_probability_delta>=0?'positive':'negative')+'">'+(z.championship_probability_delta>=0?'+':'')+(100*z.championship_probability_delta).toFixed(1)+' pts</td></tr>';
  }).join('');
}


function renderScenarioSchedule(d){
  const rows=d.affected_games||[];
  const target=$('scenario-schedule');
  $('scenario-schedule-status').textContent=rows.length?rows.length+' affected games':'no future strength-adjusted games';
  if(!rows.length){
    target.classList.add('empty');
    target.innerHTML='<span>This scenario changes history only; no future game receives a player/trade strength adjustment.</span>';
    return;
  }
  target.classList.remove('empty');
  target.innerHTML=rows.slice(0,16).map(function(g){
    const deltas=[];
    if(Math.abs(g.away_elo_delta)>.01)deltas.push('<span class="scenario-game-delta">'+g.away_team+' '+(g.away_elo_delta>=0?'+':'')+g.away_elo_delta.toFixed(0)+' Elo</span>');
    if(Math.abs(g.home_elo_delta)>.01)deltas.push('<span class="scenario-game-delta">'+g.home_team+' '+(g.home_elo_delta>=0?'+':'')+g.home_elo_delta.toFixed(0)+' Elo</span>');
    const delta=g.home_win_probability_delta;
    return '<div class="scenario-game-row" data-scenario-game="'+g.game_id+'" title="Open this affected game in Matchup Lab">'
      +'<div class="scenario-game-date">'+g.date+'</div>'
      +'<div class="scenario-game-matchup"><strong>'+g.away_team+' @ '+g.home_team+'</strong><span>'+pct(g.baseline_home_win_probability)+' → '+pct(g.altered_home_win_probability)+' home win</span></div>'
      +'<div class="scenario-game-deltas">'+deltas.join('')+'</div>'
      +'<div class="scenario-game-prob"><strong class="'+(delta>=0?'positive':'negative')+'">'+(delta>=0?'+':'')+(100*delta).toFixed(1)+' pts</strong><span>home-win shift</span></div>'
      +'</div>';
  }).join('');
  document.querySelectorAll('[data-scenario-game]').forEach(function(row){
    row.onclick=function(){openScenarioMatchup(row.dataset.scenarioGame)};
  });
}

async function openScenarioMatchup(gameId){
  if(!scenarioLastRequest)return;
  const body=Object.assign({},scenarioLastRequest,{
    game_id:gameId,
    trials:Number($('matchup-trials').value||5000)
  });
  try{
    const d=await json('/api/scenario/matchup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    openView('matchup');
    $('matchup-a').value=d.game.home_team;
    $('matchup-b').value=d.game.away_team;
    $('matchup-date').value=scenarioLastRequest.as_of;
    $('matchup-bestof').value='1';
    renderMatchup(d.scenario);
    const delta=d.home_win_probability_delta;
    const adjustments=Object.entries(d.rating_adjustments||{}).map(function(entry){
      return entry[0]+' '+(entry[1]>=0?'+':'')+entry[1].toFixed(0)+' Elo';
    }).join(' · ');
    $('matchup-context').hidden=false;
    $('matchup-context').innerHTML='<div><strong>SCENARIO MATCHUP · '+d.game.away_team+' @ '+d.game.home_team+' · '+d.game.date+'</strong><span>'+(adjustments||'No direct player/trade adjustment')+' · same altered history, single-game comparison</span></div><div class="scenario-shift">'+pct(d.baseline.team_a_series_probability)+' → '+pct(d.scenario.team_a_series_probability)+' <small>home win</small></div>';
  }catch(e){
    setScenarioShareStatus('Could not open scenario matchup: '+e.message,true);
  }
}

function renderScenarioAwardRipple(d){
  const panel=$('scenario-award-panel');
  if(!d.award_ripple||!d.award_ripple.length){panel.hidden=true;return}
  panel.hidden=false;
  panel.dataset.asof=d.as_of;
  $('scenario-award-ripple').innerHTML=d.award_ripple.slice(0,8).map(function(p){
    const up=p.race_score_delta>=0;
    return '<div class="award-ripple-card"><span>'+p.team+' · '+p.player_name+'</span><strong class="'+(up?'up':'down')+'">'+signed(p.race_score_delta)+' race score</strong><small>share '+(p.race_share_delta>=0?'+':'')+(100*p.race_share_delta).toFixed(2)+' pts</small></div>';
  }).join('');
}
$('scenario-open-awards').onclick=function(){
  const date=$('scenario-award-panel').dataset.asof;
  if(date)$('award-date').value=date;
  openView('awards');
};

function renderScenarioBars(){
  if(!scenarioLast)return;
  const metric=$('scenario-metric').value;
  const rows=[].concat(scenarioLast.deltas).sort(function(a,b){return Math.abs(b[metric])-Math.abs(a[metric])}).slice(0,16);
  const max=Math.max.apply(null,rows.map(function(x){return Math.abs(x[metric])}).concat([.001]));
  $('scenario-bars').classList.remove('empty');
  $('scenario-bars').innerHTML=rows.map(function(x){
    const value=x[metric],h=42*Math.abs(value)/max;
    const title=x.team+' · '+(metric.includes('probability')?(100*value).toFixed(2)+' pts':value.toFixed(2));
    return '<div class="scenario-bar-item"><div class="scenario-bar-track"><div class="scenario-bar-fill '+(value>=0?'pos':'neg')+'" style="height:'+h+'px"><title>'+title+'</title></div></div><label>'+x.team+'</label></div>';
  }).join('');
}
$('scenario-metric').onchange=renderScenarioBars;

async function loadAwards(){
  if(!awardHistory.length){
    const h=await json('/api/awards/history?step_days=7&limit=6');
    awardHistory=h.snapshots||[];
    $('award-source').textContent=h.source?.kind==='official_snapshot'?'OFFICIAL PLAYER LOGS':'SYNTHETIC PLAYER LOGS';
    if(awardHistory.length){
      $('award-slider').min=0;$('award-slider').max=awardHistory.length-1;
      const current=$('award-date').value||awardHistory[Math.floor(awardHistory.length/2)].date;
      let nearest=0,best=Infinity;
      awardHistory.forEach((s,i)=>{const diff=Math.abs(new Date(s.date)-new Date(current));if(diff<best){best=diff;nearest=i}});
      $('award-slider').value=nearest;$('award-date').value=awardHistory[nearest].date;
      drawAwardHistory(awardHistory);
    }
  }
  await loadAwardRace();
}
async function loadAwardRace(){
  const date=$('award-date').value;if(!date)return;
  const d=await json(`/api/awards/race?as_of=${date}&limit=25`);
  currentAwardRace=d;$('award-date-label').textContent=d.as_of;$('award-board-title').textContent=`${d.award} race · ${d.candidates.length} candidates`;
  const top=d.candidates.slice(0,10);
  $('award-board').innerHTML=top.map((p,i)=>`<div class="award-row ${i===0?'active':''}" data-award-player="${p.player_id}">
    <div class="award-rank">${String(i+1).padStart(2,'0')}</div>
    <div class="award-player"><strong>${p.player_name}</strong><span>${p.team} · ${p.games} GP</span><span class="eligibility ${p.eligibility_status}">${p.eligibility_status.replace('_',' ')}</span></div>
    <div class="award-stat"><span>PTS</span><strong>${p.ppg.toFixed(1)}</strong></div>
    <div class="award-stat"><span>REB / AST</span><strong>${p.rpg.toFixed(1)} / ${p.apg.toFixed(1)}</strong></div>
    <div class="award-stat"><span>TEAM WIN%</span><strong>${(100*p.team_win_pct).toFixed(0)}%</strong></div>
    <div class="award-stat award-score"><span>RACE SCORE</span><strong>${p.race_score.toFixed(1)}</strong></div>
  </div>`).join('');
  document.querySelectorAll('[data-award-player]').forEach(row=>row.onclick=()=>{document.querySelectorAll('.award-row').forEach(x=>x.classList.remove('active'));row.classList.add('active');const p=d.candidates.find(x=>x.player_id===row.dataset.awardPlayer);renderAwardDetail(p)});
  if(top[0])renderAwardDetail(top[0]);
}
function renderAwardDetail(p){
  $('award-detail-name').textContent=`${p.player_name} · ${p.team}`;
  $('award-detail-meta').innerHTML=[
    ['Race share',pct(p.race_share)],['PTS / REB / AST',`${p.ppg.toFixed(1)} / ${p.rpg.toFixed(1)} / ${p.apg.toFixed(1)}`],
    ['TS%',pct(p.true_shooting)],['Team win%',pct(p.team_win_pct)],['Availability',pct(p.availability)],['Eligibility',p.eligibility_status.replace('_',' ')]
  ].map(([k,v])=>`<div class="award-mini"><span>${k}</span><strong>${v}</strong></div>`).join('');
  const order=['scoring','playmaking','rebounding','defense','efficiency','team_success','availability','ball_security'];
  $('award-features').innerHTML=order.map(k=>{const v=p.feature_scores[k]||0;return `<div class="feature-row"><span>${k.replace('_',' ')}</span><div class="feature-track"><div class="feature-fill" style="width:${100*v}%"></div></div><strong>${Math.round(100*v)}</strong></div>`}).join('');
}
function drawAwardHistory(snapshots){
  const el=$('award-history-chart');if(!snapshots.length){el.innerHTML='';return}
  const latest=snapshots[snapshots.length-1].candidates.slice(0,6);const players=latest.map(x=>({id:x.player_id,name:x.player_name,team:x.team}));
  const W=900,H=280,pad=38;const x=i=>pad+(W-2*pad)*(i/Math.max(1,snapshots.length-1));const all=[];players.forEach(p=>snapshots.forEach(s=>{const c=s.candidates.find(x=>x.player_id===p.id);if(c)all.push(c.race_score)}));const min=Math.max(0,Math.min(...all)-5),max=Math.min(100,Math.max(...all)+5);const y=v=>H-pad-(H-2*pad)*((v-min)/Math.max(1,max-min));const colors=['#81d6be','#f0b55d','#8eaeff','#de8cff','#f38b7d','#b6cf70'];
  let svg=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  [min,(min+max)/2,max].forEach(v=>svg+=`<line class="grid" x1="${pad}" y1="${y(v)}" x2="${W-pad}" y2="${y(v)}"/><text x="3" y="${y(v)+3}">${v.toFixed(0)}</text>`);
  players.forEach((p,pi)=>{const pts=[];snapshots.forEach((s,i)=>{const a=s.candidates.find(z=>z.player_id===p.id);if(a)pts.push({i,v:a.race_score,date:s.date})});if(pts.length){const path=pts.map((q,j)=>`${j?'L':'M'}${x(q.i)},${y(q.v)}`).join(' ');svg+=`<path class="award-line" stroke="${colors[pi]}" d="${path}"/>`;pts.forEach(q=>svg+=`<circle class="award-dot" fill="${colors[pi]}" cx="${x(q.i)}" cy="${y(q.v)}" r="3"><title>${p.name} · ${q.date} · ${q.v.toFixed(1)}</title></circle>`)}});svg+='</svg>';
  el.innerHTML=svg+`<div class="award-legend">${players.map((p,i)=>`<div class="legend-item"><span class="legend-dot" style="background:${colors[i]}"></span>${p.name}</div>`).join('')}</div>`;
}
$('award-slider').oninput=()=>{if(!awardHistory.length)return;const snap=awardHistory[Number($('award-slider').value)];$('award-date').value=snap.date;$('award-date-label').textContent=snap.date;clearTimeout(awardTimer);awardTimer=setTimeout(loadAwardRace,90)};
$('award-date').onchange=()=>{if(awardHistory.length){let nearest=0,best=Infinity;awardHistory.forEach((s,i)=>{const diff=Math.abs(new Date(s.date)-new Date($('award-date').value));if(diff<best){best=diff;nearest=i}});$('award-slider').value=nearest}loadAwardRace()};


$('award-simulate').onclick=async()=>{
  const button=$('award-simulate');button.disabled=true;$('award-future-note').textContent='simulating alternate endings…';
  try{
    const d=await json('/api/awards/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      as_of:$('award-date').value,trials:Number($('award-sim-trials').value),seed:2026
    })});
    const max=Math.max(...d.candidates.map(x=>x.leader_probability),.001);
    $('award-future-bars').classList.remove('empty');
    $('award-future-bars').innerHTML=d.candidates.slice(0,8).map((p,i)=>`<div class="award-future-row">
      <div class="award-future-player"><strong>${String(i+1).padStart(2,'0')} · ${p.player_name}</strong><span>${p.team} · mean final score ${p.mean_final_score.toFixed(1)}</span></div>
      <div class="award-future-track"><div class="award-future-fill" style="width:${100*p.leader_probability/max}%"></div></div>
      <strong>${pct(p.leader_probability)}</strong><span>top 3 ${pct(p.top3_probability)}</span>
    </div>`).join('');
    $('award-future-note').textContent=`${d.trials.toLocaleString()} simulated season endings`;
  }catch(e){
    $('award-future-bars').classList.add('empty');$('award-future-bars').innerHTML=`<span>${e.message}</span>`;
    $('award-future-note').textContent='simulation failed';
  }finally{button.disabled=false}
};

init();
