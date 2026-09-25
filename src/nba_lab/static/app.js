const $=id=>document.getElementById(id);let meta={},mode='flip',diagnosticsLoaded=false,lastDeltas=[],awardHistory=[],currentAwardRace=null,awardTimer=null,impactData=null,lineupPool=[],lineupA=[],lineupB=[];
const pct=x=>`${(100*x).toFixed(x<.1?1:0)}%`;const signed=x=>`${x>=0?'+':''}${x.toFixed(2)}`;
async function json(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}
function teamOptions(select,includeAll=false){select.replaceChildren();if(includeAll){const o=document.createElement('option');o.value='';o.textContent='All teams';select.append(o)}Object.keys(meta.team_metadata).sort().forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=`${t} · ${meta.team_metadata[t].name}`;select.append(o)})}
const viewMeta={home:['NBA LAB / OVERVIEW','Basketball, as a system.'],season:['NBA LAB / SEASON LAB','Rewrite the season.'],matchup:['NBA LAB / MATCHUP LAB','Run the matchup.'],timeline:['NBA LAB / TIMELINE LAB','Replay how a team changed.'],model:['NBA LAB / MODEL LAB','Trust the model, then improve it.'],awards:['NBA LAB / AWARDS LAB','Replay the award race.'],impact:['NBA LAB / PLAYER IMPACT','Separate player from context.'],lineup:['NBA LAB / LINEUP LAB','Build the five.'],leverage:['NBA LAB / LEVERAGE LAB','Find the pivotal game.'],game:['NBA LAB / GAME REPLAY','Rewrite the possession.']};
function openView(name){document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===name));$(`view-${name}`).classList.add('active');$('view-kicker').textContent=viewMeta[name][0];$('view-title').textContent=viewMeta[name][1];if(name==='timeline')loadTimeline();if(name==='model')loadDiagnostics();if(name==='matchup'&&!$('matchup-a').value)setupMatchup();if(name==='awards')loadAwards();if(name==='impact')loadImpact();if(name==='lineup')loadLineup()}
document.querySelectorAll('.nav-item').forEach(b=>b.onclick=()=>openView(b.dataset.view));document.querySelectorAll('[data-open]').forEach(c=>c.onclick=()=>openView(c.dataset.open));
async function loadGames(){const team=$('game-team').value;const q=new URLSearchParams({before:$('asof').value,limit:'50'});if(team)q.set('team',team);const games=await json('/api/games?'+q);$('game').replaceChildren();games.forEach(g=>{const o=document.createElement('option');o.value=g.game_id;o.textContent=`${g.date} · ${g.away_team} ${g.away_score} @ ${g.home_team} ${g.home_score}`;$('game').append(o)});if(!games.length){const o=document.createElement('option');o.textContent='No completed games before this date';$('game').append(o)}}
async function init(){meta=await json('/api/status');const official=meta.source.kind==='official_snapshot';$('source-short').textContent=official?'Official NBA snapshot':'Synthetic fallback';$('source-detail').textContent=`${meta.games} games · ${meta.teams} teams`;$('source-dot').style.background=official?'var(--green)':'var(--orange)';$('date-range').textContent=`${meta.date_min} → ${meta.date_max}`;teamOptions($('team'));teamOptions($('game-team'),true);teamOptions($('timeline-team'));teamOptions($('matchup-a'));teamOptions($('matchup-b'));$('team').value='NYK';$('timeline-team').value='NYK';$('matchup-a').value='NYK';$('matchup-b').value='BOS';await loadGames();try{const b=await json('/api/backtest');$('brier').textContent=b.brier.toFixed(3)}catch(e){$('brier').textContent='—'}}
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
async function runMatchup(){const button=$('matchup-run');button.disabled=true;try{const body={as_of:$('matchup-date').value,trials:Number($('matchup-trials').value),seed:2026,team_a:$('matchup-a').value,team_b:$('matchup-b').value,best_of:Number($('matchup-bestof').value)};const d=await json('/api/matchup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});renderMatchup(d)}catch(e){$('matchup-result').innerHTML=`<p>${e.message}</p>`}finally{button.disabled=false}}
function renderMatchup(d){const pa=d.team_a_series_probability,pb=d.team_b_series_probability;$('matchup-a-name').textContent=d.team_a;$('matchup-b-name').textContent=d.team_b;$('matchup-a-prob').textContent=pct(pa);$('matchup-b-prob').textContent=pct(pb);$('matchup-a-elo').textContent=`Elo ${d.team_a_rating.toFixed(0)}`;$('matchup-b-elo').textContent=`Elo ${d.team_b_rating.toFixed(0)}`;$('matchup-prob-fill').style.width=`${pa*100}%`;$('matchup-games').textContent=d.best_of===1?'single game':`${d.expected_games.toFixed(2)} expected games`;const lengths=Object.entries(d.length_distribution),maxL=Math.max(...lengths.map(([,v])=>v),.001);$('length-dist').innerHTML=lengths.map(([k,v])=>`<div class="dist-row"><span>${k} games</span><div class="dist-track"><div class="dist-fill" style="width:${100*v/maxL}%"></div></div><strong>${pct(v)}</strong></div>`).join('');const scores=Object.entries(d.score_distribution).sort((a,b)=>b[1]-a[1]).slice(0,8),maxS=Math.max(...scores.map(([,v])=>v),.001);$('score-dist').innerHTML=scores.map(([k,v])=>`<div class="score-row"><span>${k}</span><div class="score-track"><div class="score-fill" style="width:${100*v/maxS}%"></div></div><strong>${pct(v)}</strong></div>`).join('')}
$('timeline-team').onchange=loadTimeline;
async function loadTimeline(){const team=$('timeline-team').value||'NYK';const d=await json(`/api/timeline/${team}`);$('tl-record').textContent=`${d.summary.wins}-${d.summary.losses}`;$('tl-current').textContent=d.summary.current_rating.toFixed(0);$('tl-peak').textContent=d.summary.peak_rating.toFixed(0);$('tl-range').textContent=`${d.summary.low_rating.toFixed(0)} → ${d.summary.peak_rating.toFixed(0)}`;$('tl-title').textContent=`${d.team.name} · Elo trajectory`;drawTimeline(d.points);$('timeline-games').innerHTML=d.points.slice(-16).reverse().map(p=>`<div class="game-chip ${p.win?'win':'loss'}"><span>${p.date} · ${p.home?'vs':'@'} ${p.opponent}</span><strong>${p.win?'W':'L'} ${p.margin>0?'+':''}${p.margin}</strong><span>${p.wins}-${p.losses} · Elo ${p.rating.toFixed(0)}</span></div>`).join('')}
function drawTimeline(points){const el=$('timeline-chart');if(!points.length){el.innerHTML='';return}const W=900,H=250,pad=34;const vals=points.map(p=>p.rating);const min=Math.min(...vals)-15,max=Math.max(...vals)+15;const x=i=>pad+(W-2*pad)*(i/Math.max(1,points.length-1));const y=v=>H-pad-(H-2*pad)*((v-min)/(max-min));const path=points.map((p,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(p.rating).toFixed(1)}`).join(' ');const grids=[min,(min+max)/2,max];el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${grids.map(v=>`<line class="grid" x1="${pad}" y1="${y(v)}" x2="${W-pad}" y2="${y(v)}"/><text x="2" y="${y(v)+3}">${v.toFixed(0)}</text>`).join('')}<path class="line" d="${path}"/>${points.map((p,i)=>`<circle class="point ${p.win?'win':'loss'}" cx="${x(i)}" cy="${y(p.rating)}" r="4"><title>${p.date} · ${p.win?'W':'L'} ${p.margin>0?'+':''}${p.margin} vs ${p.opponent} · Elo ${p.rating}</title></circle>`).join('')}</svg>`}
async function loadDiagnostics(){if(diagnosticsLoaded)return;const d=await json('/api/diagnostics');diagnosticsLoaded=true;$('md-brier').textContent=d.metrics.brier.toFixed(3);$('md-logloss').textContent=d.metrics.log_loss.toFixed(3);$('md-accuracy').textContent=pct(d.metrics.accuracy);$('md-games').textContent=d.metrics.games.toLocaleString();$('model-name').textContent=d.model.name;$('model-base').textContent=d.model.base;$('model-k').textContent=d.model.k;$('model-home').textContent=`${d.model.home_advantage} Elo`;$('promotion-rule').textContent=d.model.promotion_rule;drawCalibration(d.calibration)}
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

async function loadLineup(){
  const alpha=Number($('lineup-alpha').value||1000);
  const d=await json(`/api/lineup/players?alpha=${alpha}`);
  lineupPool=d.players||[];
  const teams=[...new Set(lineupPool.map(p=>p.team))].sort();
  if($('lineup-team-filter').options.length<=1){
    teams.forEach(team=>{const o=document.createElement('option');o.value=team;o.textContent=team;$('lineup-team-filter').append(o)});
  }
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
$('lineup-alpha').onchange=async()=>{await loadLineup();resetLineupResult()};
$('lineup-prior').onchange=resetLineupResult;
$('lineup-swap').onclick=()=>{const copy=[...lineupA];lineupA=[...lineupB];lineupB=copy;resetLineupResult();renderLineupSlots();renderLineupPool()};
$('lineup-run').onclick=async()=>{
  if(lineupA.length!==5||lineupB.length!==5){$('lineup-margin-note').textContent='both sides need five unique players';return}
  const button=$('lineup-run');button.disabled=true;
  try{
    const d=await json('/api/lineup/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      lineup_a:lineupA,lineup_b:lineupB,alpha:Number($('lineup-alpha').value),prior_possessions:Number($('lineup-prior').value)
    })});
    const a=d.lineup_a,b=d.lineup_b,m=d.neutral_margin_per_100;
    $('lineup-a-value').textContent=`${a.blended_net_rating>=0?'+':''}${a.blended_net_rating.toFixed(1)}`;
    $('lineup-b-value').textContent=`${b.blended_net_rating>=0?'+':''}${b.blended_net_rating.toFixed(1)}`;
    $('lineup-margin').textContent=`${m>=0?'+':''}${m.toFixed(1)}`;
    const winner=m>=0?'Lineup A':'Lineup B';
    $('lineup-margin-note').textContent=`${winner} model edge per 100 possessions`;
    const meta=lineup=>lineup.observed_possessions>0
      ? `<span class="lineup-seen">OBSERVED UNIT</span> · ${Math.round(lineup.observed_possessions)} poss · raw ${lineup.observed_net_rating.toFixed(1)} · ${Math.round(100*lineup.observed_weight)}% empirical weight`
      : `<span class="lineup-unseen">UNSEEN UNIT</span> · additive RAPM prior only`;
    $('lineup-a-meta').innerHTML=meta(a);$('lineup-b-meta').innerHTML=meta(b);
  }catch(e){$('lineup-margin-note').textContent=e.message}finally{button.disabled=false}
};

async function loadImpact(){
  const alpha=Number($('impact-alpha').value||1000);
  const d=await json(`/api/impact?alpha=${alpha}&limit=500`);
  impactData=d;
  $('impact-stints').textContent=d.stints.toLocaleString();
  $('impact-games').textContent=d.games.toLocaleString();
  $('impact-home').textContent=d.home_court_per_100.toFixed(2);
  $('impact-rmse').textContent=d.weighted_rmse.toFixed(2);
  const kept=d.qa?.possessions_kept,seen=d.qa?.possessions_seen;
  const qa=(kept!=null&&seen)?` · kept ${kept.toLocaleString()}/${seen.toLocaleString()}`:'';
  $('impact-source').textContent=(d.source?.kind==='normalized_snapshot'?'NORMALIZED REAL STINTS':'SYNTHETIC STINTS')+qa;
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
    <td>${Math.round(p.possessions).toLocaleString()}</td>
  </tr>`).join('');
  document.querySelectorAll('[data-impact-player]').forEach(row=>row.onclick=()=>{document.querySelectorAll('[data-impact-player]').forEach(x=>x.classList.remove('active'));row.classList.add('active');loadImpactPath(row.dataset.impactPlayer)});
}
$('impact-alpha').onchange=loadImpact;
$('impact-search').oninput=()=>impactData&&renderImpactRows(impactData.players);
async function loadImpactPath(playerId){
  const d=await json(`/api/impact/${playerId}/path`);
  $('impact-detail-name').textContent=`${d.player.player_name} · ${d.player.team}`;
  const current=impactData?.players.find(p=>p.player_id===playerId);
  $('impact-detail-meta').textContent=current?`Current α ${impactData.alpha.toFixed(0)} · RAPM ${current.impact_per_100>=0?'+':''}${current.impact_per_100.toFixed(2)} / 100 · ${Math.round(current.possessions).toLocaleString()} possessions`:'Regularization path';
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
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line class="zero" x1="${pad}" y1="${y(0)}" x2="${W-pad}" y2="${y(0)}"/><line class="grid" x1="${x(exposureCut)}" y1="${pad}" x2="${x(exposureCut)}" y2="${H-pad}"/>${players.map(p=>`<circle class="scatter-point ${p.possessions<exposureCut?'low-sample':''}" cx="${x(p.possessions)}" cy="${y(p.impact_per_100)}" r="5"><title>${p.player_name} · ${p.team} · RAPM ${p.impact_per_100.toFixed(2)} · ${Math.round(p.possessions)} poss</title></circle>`).join('')}<text x="${pad}" y="${H-8}">0 poss</text><text x="${W-pad-50}" y="${H-8}">${Math.round(maxX)} poss</text><text x="3" y="${y(maxY)+3}">${maxY.toFixed(1)}</text><text x="3" y="${y(minY)+3}">${minY.toFixed(1)}</text></svg>`;
}

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
