/* ============================================================
   Euroleague Advanced Stats — application logic
   ============================================================ */

// ---------- State ----------
let SCHEDULE = {};   // gamecode -> game metadata (teams, logos, score, round)

// ---------- Small utilities ----------
function toSeconds(t){ if(!t||!t.includes(':'))return 0; const[m,s]=t.split(':').map(Number); return m*60+s; }
function fmt(n,d=1){ if(n===null||n===undefined||isNaN(n))return '\u2014'; return Number(n).toFixed(d); }
function netClass(n){ return n>0?'pos':n<0?'neg':''; }
function escAttr(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

// "SLOUKAS, KOSTAS" -> "Kostas Sloukas"
function formatName(raw){
  if(!raw)return '';
  const parts=raw.split(',').map(s=>s.trim());
  const titled=s=>s.split(/[\s-]/).map(w=>w?w[0].toUpperCase()+w.slice(1).toLowerCase():w).join(' ');
  if(parts.length>=2)return titled(parts[1])+' '+titled(parts[0]);
  return titled(raw);
}
function initials(name){
  const w=name.trim().split(/\s+/);
  if(w.length===1)return w[0].slice(0,2).toUpperCase();
  return (w[0][0]+w[w.length-1][0]).toUpperCase();
}
function colorFromString(str){
  let h=0; for(let i=0;i<(str||'').length;i++)h=str.charCodeAt(i)+((h<<5)-h);
  return 'hsl('+(Math.abs(h)%360)+', 45%, 42%)';
}
function avatarHtml(name){ return '<span class="avatar" style="background:'+colorFromString(name)+'">'+initials(name)+'</span>'; }

// Generic crest renderer: <img> with fallback badge on error.
// The fallback is handled by a named function (crestFallback) instead of an
// inline onerror string, so there are no nested quotes to break the tag.
function crestImg(code, url, imgClass, fbClass){
  const color=colorFromString(code||'??');
  const label=(code||'??').slice(0,3);
  if(url){
    return '<img class="'+imgClass+'"'+
      ' src="'+escAttr(url)+'"'+
      ' alt="'+escAttr(code)+'"'+
      ' data-code="'+escAttr(label)+'"'+
      ' data-fb="'+escAttr(fbClass)+'"'+
      ' data-color="'+escAttr(color)+'"'+
      ' onerror="crestFallback(this)">';
  }
  return '<span class="'+fbClass+'" style="background:'+color+'">'+label+'</span>';
}

// Replace a broken crest <img> with a colored initials badge
function crestFallback(img){
  const span=document.createElement('span');
  span.className=img.getAttribute('data-fb');
  span.style.background=img.getAttribute('data-color');
  span.textContent=img.getAttribute('data-code');
  if(img.parentNode)img.parentNode.replaceChild(span,img);
}

// ---------- View switching ----------
function showLanding(){
  document.getElementById('landing').classList.remove('hidden');
  document.getElementById('detail').classList.add('hidden');
  document.getElementById('backBtn').classList.remove('show');
}
function showDetail(){
  document.getElementById('landing').classList.add('hidden');
  document.getElementById('detail').classList.remove('hidden');
  document.getElementById('backBtn').classList.add('show');
  window.scrollTo(0,0);
}

// ============================================================
//  Schedule loading (landing page)
//  v3 API uses local/road containers and a nested `club` object.
// ============================================================
async function loadSchedule(){
  const league=document.getElementById('league').value;
  const season=document.getElementById('season').value;
  const seasonCode=league+season;
  const btn=document.getElementById('btnLoad');
  const status=document.getElementById('status');
  const grid=document.getElementById('scheduleContainer');

  btn.disabled=true; status.className=''; status.innerHTML='<span class="spinner"></span>Loading season schedule\u2026';
  grid.innerHTML='';

  const endpoints=[
    'https://api-live.euroleague.net/v3/competitions/'+league+'/seasons/'+seasonCode+'/games',
    'https://api-live.euroleague.net/v2/competitions/'+league+'/seasons/'+seasonCode+'/games'
  ];

  let games=null;
  for(const url of endpoints){
    try{
      const res=await fetch(url);
      if(!res.ok)continue;
      const json=await res.json();
      games=json.data||json.games||json;
      if(Array.isArray(games)&&games.length)break;
    }catch(e){}
  }

  if(!games||!Array.isArray(games)||!games.length){
    status.className='error';
    status.textContent='Could not load the schedule. The API may be blocking the request (CORS) or the season code is wrong.';
    document.getElementById('corsNotice').style.display='block';
    btn.disabled=false; return;
  }

  SCHEDULE={};
  const byRound={};

  for(const g of games){
    const info=parseGame(g);
    if(info.code==null)continue;
    SCHEDULE[info.code]=info;
    (byRound[info.roundName]=byRound[info.roundName]||{games:[],order:info.roundNum}).games.push(info);
  }

  renderSchedule(byRound);
  document.getElementById('roundControls').classList.remove('hidden');
  status.className='ok';
  status.textContent='\u2713 '+Object.keys(SCHEDULE).length+' games loaded. Click a played game to see its advanced stats.';
  btn.disabled=false;
}

// Robust parse of one game object across API versions
function parseGame(g){
  const code=g.gameCode??g.code??g.game??g.id;

  // Home/away containers: v3 = local/road, others = home/away
  const homeC=g.local||g.home||g.homeTeam||{};
  const awayC=g.road||g.away||g.visitor||g.awayTeam||{};

  // Team object: v3 nests under `club`, others use `team` or are flat
  const homeT=homeC.club||homeC.team||homeC;
  const awayT=awayC.club||awayC.team||awayC;

  const teamName=t=>t.name||t.clubName||t.fullName||t.code||'';
  const teamCode=t=>t.code||t.tvCode||t.abbreviatedName||t.abbreviation||'';
  const teamCrest=t=>(t.images&&(t.images.crest||t.images.logo))||(t.imageUrls&&t.imageUrls.crest)||t.crest||t.logo||t.image||null;

  const roundObj=g.round||{};
  const roundNum=roundObj.round??roundObj.number??g.gameday??(typeof g.round==='number'?g.round:0);
  const roundName=roundObj.name||('Round '+roundNum);

  const hScore=homeC.score??g.homeScore??null;
  const gScore=awayC.score??g.awayScore??null;
  const played=g.played??(hScore!=null&&hScore>0);

  return {
    code,
    home:teamCode(homeT), away:teamCode(awayT),
    homeName:teamName(homeT), awayName:teamName(awayT),
    homeCrest:teamCrest(homeT), awayCrest:teamCrest(awayT),
    hScore, gScore, played,
    roundNum:Number(roundNum)||0, roundName,
    league:document.getElementById('league').value,
    season:document.getElementById('season').value
  };
}

function renderSchedule(byRound){
  const grid=document.getElementById('scheduleContainer');
  const rounds=Object.entries(byRound).sort((a,b)=>a[1].order-b[1].order);
  let html='';
  rounds.forEach(([roundName,data],idx)=>{
    // First round open by default, the rest collapsed
    const open=idx===0;
    const bid='round_'+idx;
    const arrow=open?'\u25be':'\u25b8';
    html+='<div class="round-block">'+
      '<div class="round-title" onclick="toggleRound(\''+bid+'\',this)" style="cursor:pointer;user-select:none">'+
        '<span class="round-arrow">'+arrow+'</span> '+roundName+
        ' <span class="round-count">('+data.games.length+' games)</span>'+
      '</div>'+
      '<div class="games-grid'+(open?'':' hidden')+'" id="'+bid+'">';
    for(const gm of data.games){
      const played=gm.played&&gm.hScore!=null;
      const homeWin=played&&gm.hScore>gm.gScore, awayWin=played&&gm.gScore>gm.hScore;
      html+=''+
        '<div class="game-card '+(played?'':'not-played')+'"'+(played?(' onclick="openGame('+gm.code+')"'):'')+'>'+
          '<div class="gc-row">'+
            crestImg(gm.home,gm.homeCrest,'gc-crest','gc-crest-fb')+
            '<span class="gc-name">'+(gm.homeName||gm.home)+'</span>'+
            '<span class="gc-score '+(homeWin?'win':'')+'">'+(played?gm.hScore:'\u2013')+'</span>'+
          '</div>'+
          '<div class="gc-row">'+
            crestImg(gm.away,gm.awayCrest,'gc-crest','gc-crest-fb')+
            '<span class="gc-name">'+(gm.awayName||gm.away)+'</span>'+
            '<span class="gc-score '+(awayWin?'win':'')+'">'+(played?gm.gScore:'\u2013')+'</span>'+
          '</div>'+
          '<div class="gc-meta"><span class="gc-badge-home">home \u25b2</span><span>'+(played?'final':'upcoming')+'</span></div>'+
        '</div>';
    }
    html+='</div></div>';
  });
  grid.innerHTML=html;
}

// Expand/collapse a round block
function toggleRound(bid,titleEl){
  const grid=document.getElementById(bid);
  if(!grid)return;
  const hidden=grid.classList.toggle('hidden');
  const arrow=titleEl.querySelector('.round-arrow');
  if(arrow)arrow.textContent=hidden?'\u25b8':'\u25be';
}

// Expand or collapse all rounds at once
function setAllRounds(expand){
  document.querySelectorAll('#scheduleContainer .games-grid').forEach(g=>{
    g.classList.toggle('hidden',!expand);
  });
  document.querySelectorAll('#scheduleContainer .round-arrow').forEach(a=>{
    a.textContent=expand?'\u25be':'\u25b8';
  });
}

// ============================================================
//  Play-by-play processing (per game)
// ============================================================
async function fetchPbp(league,season,gamecode){
  const url='https://live.euroleague.net/api/PlaybyPlay?gamecode='+gamecode+'&seasoncode='+league+season;
  const res=await fetch(url);
  if(!res.ok)throw new Error('API returned '+res.status);
  const text=await res.text();
  if(!text||text.trim()==='')throw new Error('Empty response \u2014 this game may not have been played yet.');
  return JSON.parse(text);
}
function buildDf(r){
  const quarters=['FirstQuarter','SecondQuarter','ThirdQuarter','ForthQuarter','ExtraTime'];
  const rows=[];
  for(const q of quarters){
    if(!r[q]||r[q].length===0)continue;
    for(const ev of r[q])rows.push(Object.assign({QUARTER:q},ev));
  }
  for(const row of rows){
    if(row.CODETEAM)row.CODETEAM=row.CODETEAM.trim();
    if(row.PLAYER_ID)row.PLAYER_ID=row.PLAYER_ID.trim();
    if(row.PLAYER)row.PLAYER=row.PLAYER.trim();
    row.POINTS_A=Number(row.POINTS_A)||0; row.POINTS_B=Number(row.POINTS_B)||0;
    if(row.PLAYTYPE==='BP')row.MARKERTIME='10:00';
    if(row.PLAYTYPE==='EP'||row.PLAYTYPE==='EG')row.MARKERTIME='00:00';
    row._sec=toSeconds(row.MARKERTIME);
  }
  return rows;
}
function labelPlayTypes(rows){
  for(let i=0;i<rows.length-1;i++)
    if(rows[i].PLAYTYPE==='FTM'&&rows[i+1]._sec!==rows[i]._sec)rows[i].PLAYTYPE='FTMF';
  if(rows.length&&rows[rows.length-1].PLAYTYPE==='FTM')rows[rows.length-1].PLAYTYPE='FTMF';
  for(let i=0;i<rows.length-1;i++){
    const next=rows[i+1];
    if(['FTM','FTMF','FTA'].includes(next.PLAYTYPE)&&Math.abs(rows[i]._sec-next._sec)<2){
      if(rows[i].PLAYTYPE==='2FGM')rows[i].PLAYTYPE='2FGF';
      if(rows[i].PLAYTYPE==='3FGM')rows[i].PLAYTYPE='3FGF';
    }
  }
  for(let i=0;i<rows.length-1;i++)
    if(rows[i].PLAYTYPE==='RV'&&['FTM','FTMF','FTA'].includes(rows[i+1].PLAYTYPE))rows[i].PLAYTYPE='SRV';
  for(let i=1;i<rows.length;i++)
    if(rows[i].PLAYTYPE==='RV'&&rows[i-1].PLAYTYPE==='OF'&&Math.abs(rows[i]._sec-rows[i-1]._sec)<2)rows[i].PLAYTYPE='ORV';
  return rows;
}
function findTeams(rows){
  const h=rows.find(r=>r.POINTS_A>0); const g=rows.find(r=>r.POINTS_B>0);
  return {home:h&&h.CODETEAM,guest:g&&g.CODETEAM};
}
function countTeam(rows,types,code){ return rows.filter(r=>r.CODETEAM===code&&types.includes(r.PLAYTYPE)).length; }

function computeTeamStats(rows,home,guest){
  const ct=(types,code)=>countTeam(rows,types,code);
  const hPoss=ct(['2FGM','3FGM','FTMF','TO'],home)+ct(['D'],guest);
  const gPoss=ct(['2FGM','3FGM','FTMF','TO'],guest)+ct(['D'],home);
  const hPlays=hPoss+ct(['O','RV'],home); const gPlays=gPoss+ct(['O','RV'],guest);
  const hPts=Math.max.apply(null,rows.map(r=>r.POINTS_A));
  const gPts=Math.max.apply(null,rows.map(r=>r.POINTS_B));
  const hORTG=hPoss>0?hPts*100/hPoss:0; const gORTG=gPoss>0?gPts*100/gPoss:0;
  const eFG=code=>{const fgm=ct(['2FGM','2FGF','3FGM','3FGF'],code);const tp3=0.5*ct(['3FGM','3FGF'],code);const fga=ct(['2FGA','3FGA'],code);return fga>0?(fgm+tp3)/(fgm+fga)*100:0;};
  const tsa=['2FGM','2FGF','3FGM','3FGF','2FGA','3FGA','FTMF'];
  const TS=(code,pts)=>{const a=ct(tsa,code);return a>0?pts/(2*a)*100:0;};
  const astRatio=(code,plays)=>plays>0?ct(['AS'],code)/plays*100:0;
  const astTO=code=>{const to=ct(['TO'],code);return to>0?ct(['AS'],code)/to:ct(['AS'],code);};
  const hOR=ct(['O'],home),hDR=ct(['D'],home),gOR=ct(['O'],guest),gDR=ct(['D'],guest);
  const hOREBpct=(hOR+gDR)>0?hOR/(hOR+gDR)*100:0;
  const hDREBpct=(hDR+gOR)>0?hDR/(hDR+gOR)*100:0;
  const tovPct=(code,poss)=>poss>0?ct(['TO'],code)/poss*100:0;
  return [
    {team:home,isHome:true,poss:hPoss,plays:hPlays,pts:hPts,ortg:hORTG,drtg:gORTG,netrtg:hORTG-gORTG,astRatio:astRatio(home,hPlays),astTO:astTO(home),orebPct:hOREBpct,drebPct:hDREBpct,tovPct:tovPct(home,hPoss),eFG:eFG(home),ts:TS(home,hPts)},
    {team:guest,isHome:false,poss:gPoss,plays:gPlays,pts:gPts,ortg:gORTG,drtg:hORTG,netrtg:gORTG-hORTG,astRatio:astRatio(guest,gPlays),astTO:astTO(guest),orebPct:100-hDREBpct,drebPct:100-hOREBpct,tovPct:tovPct(guest,gPoss),eFG:eFG(guest),ts:TS(guest,gPts)}
  ];
}
function playerOnCourt(rows,name){
  const ins=rows.map((r,i)=>({r,i})).filter(x=>x.r.PLAYTYPE==='IN'&&x.r.PLAYER===name).map(x=>x.i);
  const outs=rows.map((r,i)=>({r,i})).filter(x=>x.r.PLAYTYPE==='OUT'&&x.r.PLAYER===name).map(x=>x.i);
  if(!ins.length||(outs.length&&ins[0]>outs[0]))ins.unshift(0);
  if(!outs.length||ins[ins.length-1]>outs[outs.length-1])outs.push(rows.length-1);
  const slice=[];
  for(let k=0;k<ins.length;k++)for(let i=ins[k];i<=outs[k];i++)slice.push(rows[i]);
  return slice;
}
function playingTime(rows,name){
  const ins=rows.map((r,i)=>({r,i})).filter(x=>x.r.PLAYTYPE==='IN'&&x.r.PLAYER===name).map(x=>x.i);
  const outs=rows.map((r,i)=>({r,i})).filter(x=>x.r.PLAYTYPE==='OUT'&&x.r.PLAYER===name).map(x=>x.i);
  if(!ins.length||(outs.length&&ins[0]>outs[0]))ins.unshift(0);
  if(!outs.length||ins[ins.length-1]>outs[outs.length-1])outs.push(rows.length-1);
  const order=['FirstQuarter','SecondQuarter','ThirdQuarter','ForthQuarter','ExtraTime'];
  let total=0;
  for(let k=0;k<ins.length;k++){
    const rI=rows[ins[k]],rO=rows[outs[k]];
    if(!rI||!rO)continue;
    if(rI.QUARTER===rO.QUARTER)total+=rI._sec-rO._sec;
    else{
      const qi=rows.filter(r=>r.QUARTER===rI.QUARTER);
      const qo=rows.filter(r=>r.QUARTER===rO.QUARTER);
      total+=rI._sec-Math.min.apply(null,qi.map(r=>r._sec));
      total+=Math.max.apply(null,qo.map(r=>r._sec))-rO._sec;
      total+=600*(order.indexOf(rO.QUARTER)-order.indexOf(rI.QUARTER)-1);
    }
  }
  const m=Math.floor(total/60),s=Math.floor(total%60);
  return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}
function computePlayerStats(rows,home,guest){
  const players=Array.from(new Set(rows.map(r=>r.PLAYER).filter(p=>p&&p.trim())));
  const result=[];
  for(const name of players){
    const slice=playerOnCourt(rows,name);
    if(slice.length===0)continue;
    const teamRow=rows.find(r=>r.PLAYER===name&&r.CODETEAM);
    if(!teamRow)continue;
    const team=teamRow.CODETEAM.trim(); const isHome=team===home;
    const cp=types=>slice.filter(r=>r.PLAYER===name&&types.includes(r.PLAYTYPE)).length;
    const cpt=(types,code)=>countTeam(slice,types,code);
    const opp=isHome?guest:home;
    const tPoss=cpt(['2FGM','3FGM','FTMF','TO'],team)+cpt(['D'],opp);
    const oPoss=cpt(['2FGM','3FGM','FTMF','TO'],opp)+cpt(['D'],team);
    const tPlays=tPoss+cpt(['O','RV'],team);
    const tPts=cp(['FTM','FTMF'])+2*cp(['2FGM','2FGF'])+3*cp(['3FGM','3FGF']);
    const teamPts=cpt(['FTM','FTMF'],team)+cpt(['2FGM','2FGF'],team)*2+cpt(['3FGM','3FGF'],team)*3;
    const oppPts=cpt(['FTM','FTMF'],opp)+cpt(['2FGM','2FGF'],opp)*2+cpt(['3FGM','3FGF'],opp)*3;
    const ortg=(tPoss>0&&teamPts>0)?teamPts*100/tPoss:0;
    const drtg=(oPoss>0&&oppPts>0)?oppPts*100/oPoss:0;
    const sc=cp(['2FGA','3FGA','RV','2FGM','3FGM','SRV','TO','AS']);
    const fgm=cp(['2FGM','2FGF','3FGM','3FGF']); const tp3=0.5*cp(['3FGM','3FGF']);
    const fga=cp(['2FGA','3FGA','2FGM','2FGF','3FGM','3FGF']);
    const eFG=fga>0?(fgm+tp3)/fga*100:0;
    const tsaC=cp(['2FGM','2FGF','3FGM','3FGF','2FGA','3FGA','FTMF']);
    const ts=tsaC>0?tPts/(2*tsaC)*100:0;
    const usg=tPlays>0?sc*100/tPlays:0;
    const to=cp(['TO']),ast=cp(['AS']); const astTO=to>0?ast/to:null;
    const horebAvail=cpt(['O'],team)+cpt(['D'],opp);
    const hdrebAvail=cpt(['O'],opp)+cpt(['D'],team);
    result.push({
      name:formatName(name),rawName:name,team,isHome,mins:playingTime(rows,name),
      pts:tPts,sc,ortg,drtg,netrtg:ortg-drtg,
      astRatio:sc>0?ast/sc:0,astTO,
      orebPct:horebAvail>0?cp(['O'])/horebAvail:0,
      drebPct:hdrebAvail>0?cp(['D'])/hdrebAvail:0,
      tovPct:sc>0?to/sc:0,eFG,ts,usg
    });
  }
  return result.sort((a,b)=>b.pts-a.pts);
}

// ============================================================
//  Detail rendering
// ============================================================
function bigCrest(code,url){ return crestImg(code,url,'sb-crest','sb-crest-fb'); }

function renderScoreboard(meta,home,guest,hPts,gPts){
  if(!meta)meta={home:home,away:guest,homeName:home,awayName:guest,homeCrest:null,awayCrest:null};
  const homeWin=hPts>gPts,awayWin=gPts>hPts;
  document.getElementById('scoreboard').innerHTML=
    '<div class="scoreboard">'+
      '<div class="sb-team home">'+bigCrest(meta.home,meta.homeCrest)+
        '<div><div class="sb-side home">Home</div><div class="sb-name">'+(meta.homeName||meta.home)+'</div><div class="sb-code">'+meta.home+'</div></div>'+
      '</div>'+
      '<div class="sb-score '+(homeWin?'win':'')+'">'+hPts+'</div>'+
      '<div class="sb-sep">\u2013</div>'+
      '<div class="sb-score '+(awayWin?'win':'')+'">'+gPts+'</div>'+
      '<div class="sb-team away">'+bigCrest(meta.away,meta.awayCrest)+
        '<div><div class="sb-side">Away</div><div class="sb-name">'+(meta.awayName||meta.away)+'</div><div class="sb-code">'+meta.away+'</div></div>'+
      '</div>'+
    '</div>';
}

const TEAM_COLS=[['POSS','poss',0],['PLAYS','plays',0],['PTS','pts',0],['ORTG','ortg',1],['DRTG','drtg',1],['NET','netrtg',1],['AST%','astRatio',1],['AST/TO','astTO',2],['OREB%','orebPct',1],['DREB%','drebPct',1],['TOV%','tovPct',1],['eFG%','eFG',1],['TS%','ts',1]];
const PLAYER_COLS=[['MIN','mins',0,'str'],['PTS','pts',0],['PLAYS','sc',0],['ORTG','ortg',1],['DRTG','drtg',1],['NET','netrtg',1],['AST%','astRatio',2],['AST/TO','astTO',2],['ORB%','orebPct',2],['DRB%','drebPct',2],['TOV%','tovPct',2],['eFG%','eFG',1],['TS%','ts',1],['USG%','usg',1]];

// Sortable table registry. Each rendered table stores its rows + metadata here,
// keyed by a unique id, so header clicks can re-sort without recomputing stats.
const TABLES={};
let TABLE_SEQ=0;

function cellHtml(k,d,v){
  const cls=k==='netrtg'?netClass(v):'';
  const sign=k==='netrtg'&&v>0?'+':'';
  return '<td class="'+cls+'">'+(v===null||v===undefined||isNaN(v)?'\u2014':sign+fmt(v,d))+'</td>';
}

// Convert a value to a sortable number. Handles 'MM:SS' strings, nulls, and
// plain numbers. Missing values sort to the bottom regardless of direction.
function sortValue(v){
  if(v===null||v===undefined)return null;
  if(typeof v==='number')return isNaN(v)?null:v;
  if(typeof v==='string'&&v.includes(':')){ const[m,s]=v.split(':').map(Number); return m*60+s; }
  const n=Number(v); return isNaN(n)?null:n;
}

// Sort a table's rows by a column key and re-render its <tbody> in place.
function sortTable(tableId,key){
  const t=TABLES[tableId];
  if(!t)return;
  // Toggle direction if same column, else default to descending (highest first)
  if(t.sortKey===key)t.sortDir=-t.sortDir;
  else{ t.sortKey=key; t.sortDir=key==='name'||key==='label'?1:-1; }

  t.rows.sort((a,b)=>{
    const va=sortValue(a[key]), vb=sortValue(b[key]);
    if(va===null&&vb===null)return 0;
    if(va===null)return 1;      // nulls always last
    if(vb===null)return -1;
    if(typeof va==='string'||typeof vb==='string')
      return String(a[key]).localeCompare(String(b[key]))*t.sortDir;
    return (va-vb)*t.sortDir;
  });

  const table=document.getElementById(tableId);
  if(!table)return;
  table.querySelector('tbody').innerHTML=t.renderRows(t.rows);
  // Update header arrows
  table.querySelectorAll('th[data-key]').forEach(th=>{
    const k=th.getAttribute('data-key');
    let base=th.getAttribute('data-label');
    th.innerHTML=base+(k===t.sortKey?(t.sortDir<0?' \u25be':' \u25b4'):'');
  });
}

// Build a sortable <thead>. cols is an array of [label,key,decimals,type].
// firstCol is the label for the leftmost (non-numeric) column.
function sortableHead(tableId,firstCol,firstKey,cols){
  const first='<th data-key="'+firstKey+'" data-label="'+firstCol+'" onclick="sortTable(\''+tableId+'\',\''+firstKey+'\')" style="cursor:pointer">'+firstCol+'</th>';
  const rest=cols.map(c=>
    '<th data-key="'+c[1]+'" data-label="'+c[0]+'" onclick="sortTable(\''+tableId+'\',\''+c[1]+'\')" style="cursor:pointer">'+c[0]+'</th>'
  ).join('');
  return '<tr>'+first+rest+'</tr>';
}

// Team comparison table (home + away)
function renderTeamTable(stats,meta){
  const id='tbl_'+(++TABLE_SEQ);
  const crestFor=code=>{
    if(!meta)return crestImg(code,null,'row-crest','row-crest-fb');
    if(code===meta.home)return crestImg(code,meta.homeCrest,'row-crest','row-crest-fb');
    if(code===meta.away)return crestImg(code,meta.awayCrest,'row-crest','row-crest-fb');
    return crestImg(code,null,'row-crest','row-crest-fb');
  };
  const nameFor=code=>meta?(code===meta.home?meta.homeName:code===meta.away?meta.awayName:code):code;

  const renderRows=rows=>rows.map(s=>{
    const cells=TEAM_COLS.map(c=>cellHtml(c[1],c[2],s[c[1]])).join('');
    const side=s.isHome?'<span class="st-side home" style="margin-left:8px">HOME</span>':'<span class="st-side away" style="margin-left:8px">AWAY</span>';
    return '<tr><td><div class="player-cell">'+crestFor(s.team)+'<span class="player-name">'+(nameFor(s.team)||s.team)+'</span>'+side+'</div></td>'+cells+'</tr>';
  }).join('');

  // Provide a sortable 'name' field for the first column
  stats.forEach(s=>{ s.name=nameFor(s.team)||s.team; });
  TABLES[id]={rows:stats.slice(),renderRows,sortKey:null,sortDir:-1};

  const thead=sortableHead(id,'Team','name',TEAM_COLS);
  return '<div class="section-title">Team Comparison</div>'+
    '<div class="table-wrap"><table id="'+id+'"><thead>'+thead+'</thead><tbody>'+renderRows(stats)+'</tbody></table></div>';
}

// One player table for a single team (home OR away)
function renderPlayerTable(players, teamCode, teamName, crestUrl, isHome){
  const id='tbl_'+(++TABLE_SEQ);
  const list=players.filter(p=>p.team===teamCode);

  const renderRows=rows=>rows.map(s=>{
    const cells=PLAYER_COLS.map(c=>{const type=c[3];if(type==='str')return '<td>'+s[c[1]]+'</td>';return cellHtml(c[1],c[2],s[c[1]]);}).join('');
    return '<tr><td><div class="player-cell">'+avatarHtml(s.name)+'<span class="player-name">'+s.name+'</span></div></td>'+cells+'</tr>';
  }).join('');

  TABLES[id]={rows:list.slice(),renderRows,sortKey:null,sortDir:-1};

  const crest=crestImg(teamCode,crestUrl,'st-crest','st-crest-fb');
  const sideTag='<span class="st-side '+(isHome?'home':'away')+'">'+(isHome?'HOME':'AWAY')+'</span>';
  const thead=sortableHead(id,'Player','name',PLAYER_COLS);
  return '<div class="section-title">'+crest+'<span>'+(teamName||teamCode)+'</span>'+sideTag+'</div>'+
         '<div class="table-wrap"><table id="'+id+'"><thead>'+thead+'</thead><tbody>'+renderRows(list)+'</tbody></table></div>';
}

// ============================================================
//  Open a game from the schedule (or refetch if orientation differs)
// ============================================================
async function openGame(gamecode){
  const meta0=SCHEDULE[gamecode];
  if(!meta0)return;
  showDetail();
  const status=document.getElementById('status');
  const content=document.getElementById('detailContent');
  const scoreEl=document.getElementById('scoreboard');
  document.getElementById('corsNotice').style.display='none';
  status.className=''; status.innerHTML='<span class="spinner"></span>Loading game stats\u2026';
  content.innerHTML=''; scoreEl.innerHTML='';

  try{
    const raw=await fetchPbp(meta0.league,meta0.season,gamecode);
    let rows=labelPlayTypes(buildDf(raw));
    const t=findTeams(rows); const home=t.home,guest=t.guest;
    if(!home||!guest)throw new Error('Could not identify teams from play-by-play.');

    const teamStats=computeTeamStats(rows,home,guest);
    const playerStats=computePlayerStats(rows,home,guest);
    const hPts=teamStats[0].pts,gPts=teamStats[1].pts;

    // Align schedule metadata with play-by-play home/away orientation
    let meta=meta0;
    if(meta.home!==home){
      meta={home:meta.away,away:meta.home,homeName:meta.awayName,awayName:meta.homeName,homeCrest:meta.awayCrest,awayCrest:meta.homeCrest};
    }

    renderScoreboard(meta,home,guest,hPts,gPts);
    status.className='ok';
    status.textContent='\u2713  '+(meta.homeName||home)+' '+hPts+' \u2013 '+gPts+' '+(meta.awayName||guest)+'  \u00b7  '+rows.length+' events';

    content.innerHTML=
      renderTeamTable(teamStats,meta)+
      renderPlayerTable(playerStats,home,meta.homeName,meta.homeCrest,true)+
      renderPlayerTable(playerStats,guest,meta.awayName,meta.awayCrest,false);

  }catch(err){
    status.className='error'; status.textContent='Error: '+err.message;
    const m=err.message.toLowerCase();
    if(m.includes('cors')||m.includes('fetch')||m.includes('failed')||m.includes('networkerror'))
      document.getElementById('corsNotice').style.display='block';
    content.innerHTML='<div class="empty"><span>\u26a0</span>'+err.message+'</div>';
  }
}

// ---------- Init ----------
document.addEventListener('DOMContentLoaded',function(){
  document.getElementById('btnLoad').addEventListener('click',loadSchedule);
  document.getElementById('backBtn').addEventListener('click',showLanding);
  // Auto-load the default season on first visit
  loadSchedule();
});
