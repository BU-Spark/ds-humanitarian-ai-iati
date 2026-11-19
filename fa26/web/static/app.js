import {mountGlobe} from './vendor/atlas-globe.js';
import {NumberFlow,defineNumberFlow,ShaderMount,grainGradientFragmentShader,GrainGradientShapes,getShaderColorFromString,getShaderNoiseTexture,ShaderFitOptions,Splitting} from './vendor/poster-libs.js';
if(!customElements.get('number-flow'))defineNumberFlow('number-flow',NumberFlow);
const D=await (await fetch('data.json')).json();

const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const NS='http://www.w3.org/2000/svg';
const el=(t,a,p)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e;};
const wait=ms=>new Promise(r=>setTimeout(r,RM?0:ms));
const CATS={'activities':['Activities','var(--c-act)'],'organisations':['Organisations','var(--c-org)'],'money':['Money','var(--c-money)'],'composable counts (benchmark v2)':['Composable counts','var(--c-count)']};
const MODS=[['planner',3,'calls max per question','Planner'],['resolver',D.groups.length,'alias groups','Resolver'],['templates',D.templates.length,'Cypher templates','Templates'],
  ['tools',D.tools.length,'retrieval tools','Tools'],['checks',4,'output checks','Checks'],['schema',Object.values(D.schema.nodes).filter(v=>v).length,'node labels with data','Graph']];
$('#mods').innerHTML=MODS.map(([k,n,s,t])=>`<button class="mod" data-lib="${k}"><span>${t}</span><b>${n}</b><span>${s}</span></button>`).join('');
const ST={
  question:{x:70,y:80,ic:'Q',nm:'Question'},
  planner:{x:230,y:80,ic:'LLM',nm:'Planner',lib:'planner'},
  resolver:{x:400,y:80,ic:'ID',nm:'Resolver',lib:'resolver'},
  templates:{x:130,y:240,ic:'21',nm:'Templates',lib:'templates'},
  tools:{x:310,y:240,ic:'5',nm:'Retrieval tools',lib:'tools'},
  free:{x:490,y:240,ic:'{ }',nm:'Free Cypher',lib:'checks',sub:'guard'},
  graph:{x:310,y:375,ic:'DB',nm:'Neo4j graph',lib:'schema'},
  checks:{x:180,y:495,ic:'✓',nm:'Checks',lib:'checks'},
  answer:{x:450,y:495,ic:'=',nm:'Answer'}};
const EDGES=[['question','planner'],['planner','resolver'],['resolver','templates'],['resolver','tools'],['resolver','free'],
  ['templates','graph'],['tools','graph'],['free','graph'],['graph','checks'],['checks','answer']];
const map=$('#map');
const SC={question:'#9CCBFF',planner:'#9085e9',resolver:'#d95926',templates:'#3987e5',tools:'#199e70',free:'#c98500',graph:'#0ca30c',checks:'#d55181',answer:'#F2B544'};
const defs=el('defs',{},map);
{const f=el('filter',{id:'glow',x:'-50%',y:'-50%',width:'200%',height:'200%'},defs);el('feGaussianBlur',{stdDeviation:3.2,result:'b'},f);
 const m=el('feMerge',{},f);el('feMergeNode',{in:'b'},m);el('feMergeNode',{in:'SourceGraphic'},m);}
Object.entries(SC).forEach(([k,c])=>{const g=el('radialGradient',{id:'sg-'+k,cx:'35%',cy:'30%',r:'75%'},defs);
  el('stop',{offset:0,'stop-color':'#ffffff','stop-opacity':.55},g);el('stop',{offset:.35,'stop-color':c},g);el('stop',{offset:1,'stop-color':c,'stop-opacity':.35},g);
  const h=el('radialGradient',{id:'hg-'+k},defs);el('stop',{offset:0,'stop-color':c,'stop-opacity':.45},h);el('stop',{offset:1,'stop-color':c,'stop-opacity':0},h);});
const curve=(a,b)=>{const A=ST[a],B=ST[b];if(A.y===B.y)return `M${A.x},${A.y}L${B.x},${B.y}`;const my=(A.y+B.y)/2;return `M${A.x},${A.y}C${A.x},${my} ${B.x},${my} ${B.x},${B.y}`;};
const grad=(id,a,b,ca,cb)=>{const g=el('linearGradient',{id,gradientUnits:'userSpaceOnUse',x1:ST[a].x,y1:ST[a].y,x2:ST[b].x,y2:ST[b].y},defs);
  el('stop',{offset:0,'stop-color':ca},g);el('stop',{offset:1,'stop-color':cb},g);return `url(#${id})`;};
const edgeEls={};
EDGES.forEach(([a,b],i)=>{edgeEls[a+'>'+b]=el('path',{d:curve(a,b),class:'edge',stroke:grad('eg'+i,a,b,SC[a],SC[b])},map);});
edgeEls['checks>planner']=el('path',{d:`M${ST.checks.x-30},${ST.checks.y}C30,${ST.checks.y} 20,${ST.planner.y+60} ${ST.planner.x-28},${ST.planner.y+14}`,class:'edge retry',stroke:grad('egr','checks','planner',SC.checks,SC.planner)},map);
el('text',{x:34,y:300,'font-size':10.5,fill:'#d55181',transform:'rotate(-90 34 300)','text-anchor':'middle'},map).textContent='retry, max 2';
const stEls={};
Object.entries(ST).forEach(([k,s])=>{const c=SC[k];const g=el('g',{class:'st',tabindex:s.lib?0:-1,role:s.lib?'button':'img','aria-label':s.nm},map);
  el('circle',{cx:s.x,cy:s.y,r:48,class:'halo',fill:`url(#hg-${k})`},g);
  el('circle',{cx:s.x,cy:s.y,r:30,class:'ring',stroke:c},g);
  el('circle',{cx:s.x,cy:s.y,r:26,class:'core',fill:`url(#sg-${k})`,stroke:c},g);
  const o=el('g',{class:'orbit'},g);el('circle',{cx:s.x+36,cy:s.y,r:2.6,fill:c},o);el('circle',{cx:s.x-36,cy:s.y,r:1.6,fill:'#fff','fill-opacity':.7},o);
  if(!RM)el('animateTransform',{attributeName:'transform',type:'rotate',from:`0 ${s.x} ${s.y}`,to:`360 ${s.x} ${s.y}`,dur:'6s',repeatCount:'indefinite'},o);
  el('text',{x:s.x,y:s.y+4,class:'ic'},g).textContent=s.ic;el('text',{x:s.x,y:s.y+50,class:'nm'},g).textContent=s.nm;
  if(s.lib){g.addEventListener('click',()=>openLib(s.lib,g,s.sub));g.addEventListener('keydown',e=>{if(e.key==='Enter')openLib(s.lib,g,s.sub);});}
  stEls[k]=g;});
const packetG=el('g',{id:'packet'},map);
const comet=[...Array(7)].map((_,i)=>el('circle',{r:Math.max(5-i*.6,1.2),cx:ST.question.x,cy:ST.question.y,'fill-opacity':1-i*.13,filter:i===0?'url(#glow)':''},packetG));
const packet={setAttribute(k,v){comet[0].setAttribute(k,v);}};
let hist=[];
(function trailLoop(){const x=+comet[0].getAttribute('cx'),y=+comet[0].getAttribute('cy');hist.unshift([x,y]);hist=hist.slice(0,7*3);
  for(let i=1;i<comet.length;i++){const p=hist[Math.min(i*3,hist.length-1)];comet[i].setAttribute('cx',p[0]);comet[i].setAttribute('cy',p[1]);}
  if(!RM)requestAnimationFrame(trailLoop);})();

const PATH=['question','planner','resolver','templates','graph','checks','answer'];
let cur=0;
function setStation(i){
  const prev=cur;cur=i;
  PATH.forEach((k,j)=>{stEls[k].classList.toggle('on',j===i);stEls[k].classList.toggle('done',j<i);});
  Object.values(edgeEls).forEach(e=>e.classList.remove('lit'));
  for(let j=1;j<=i;j++){const e=edgeEls[PATH[j-1]+'>'+PATH[j]];e&&e.classList.add('lit');}
  if(i===5)edgeEls['checks>planner'].classList.add('lit');
  if(i===3){['tools','free'].forEach(k=>stEls[k].classList.add('done'));}
  const e=edgeEls[PATH[Math.max(i-1,0)]+'>'+PATH[i]];
  if(e&&i>prev&&!RM){const L=e.getTotalLength(),t0=performance.now();
    const f=now=>{const p=Math.min((now-t0)/700,1),pt=e.getPointAtLength(L*p);packet.setAttribute('cx',pt.x);packet.setAttribute('cy',pt.y);if(p<1)requestAnimationFrame(f);};requestAnimationFrame(f);}
  else{packet.setAttribute('cx',ST[PATH[i]].x);packet.setAttribute('cy',ST[PATH[i]].y);}
}
const Q12=D.templates.find(t=>t.name==='transaction_total').bench.find(b=>b.id==='Q12');
const R12=D.results.Q12;
const oxf=D.demos['Oxfam'];
const STEPS=[
 {k:'question',t:'A question arrives',p:`Plain English, no query syntax. For example: "${esc(Q12.q)}"`,
  ins:()=>typeInto(`<span class="s">"${esc(Q12.q)}"</span>`),it:'input',is:'example question'},
 {k:'planner',t:'The planner chooses a tool',p:'One LLM call returns a JSON plan: a status, a tool name and its arguments. It may instead clarify or abstain with one of 17 reason codes. It never writes the numbers itself.',lib:'planner',
  ins:()=>typeInto(`{<span class="k">"status"</span>: <span class="s">"answer"</span>,\n <span class="k">"tool"</span>: <span class="s">"transaction_total"</span>,\n <span class="k">"args"</span>: {<span class="k">"publisher"</span>: <span class="s">"oxfamus"</span>, <span class="k">"type_code"</span>: <span class="s">"4"</span>, <span class="k">"currency"</span>: <span class="s">"USD"</span>}}`),it:'plan (JSON)',is:'1 LLM call'},
 {k:'resolver',t:'Names become identifiers',p:`The same organisation can appear under several refs. <b>${D.groups.length} curated alias groups</b> map loose names to every ref they cover; anything else falls back to scored name search. Typing "Oxfam" alone matches ${oxf.n} identifiers, which is why the planner asks which one.`,lib:'resolver',
  ins:()=>{const refs=oxf.refs.slice(0,19);return `<div class="chips">`+refs.map((r,i)=>`<span class="chip ${r==='US-EIN-23-7069110'||r==='GB-CHC-202918'?'hl':''}" style="animation-delay:${i*45}ms">${esc(r)}</span>`).join('')+`</div>`},it:'resolve("Oxfam")',is:`${oxf.n} refs · alias:OXFAM_FAMILY`},
 {k:'templates',t:`${D.templates.length} tested templates`,p:'When a template fits, the arguments fill named parameters, so user text never enters the Cypher. Every template returns the same three columns: key, value and evidence. Five retrieval tools and a guarded free-Cypher path cover what templates do not.',lib:'templates',
  ins:()=>`<div class="tiles">`+D.templates.map((t,i)=>`<div class="${t.name==='transaction_total'?'hl':''}" style="animation-delay:${i*35}ms">${esc(t.name)}</div>`).join('')+`</div>`,it:'templates.TOOLS',is:'transaction_total selected'},
 {k:'graph',t:'The graph does the arithmetic',p:`The query runs on Neo4j over <b>${D.expected_counts.nodes.toLocaleString()}</b> nodes. Money sums exact integer cents and divides by 100 once, so totals never drift.`,lib:'schema',
  ins:()=>pathSvg(['Activity','HAS_TRANSACTION','Transaction'],{Activity:D.schema.nodes.Activity,Transaction:D.schema.nodes.Transaction}),it:'MATCH path',is:'Activity → Transaction'},
 {k:'checks',t:'Checks before anything is shown',p:'Evidence ids must be real snapshot rows, a single value carries the key count, total or date, and reason codes must come from the fixed list. A failure goes back to the planner, at most twice.',lib:'checks',
  ins:()=>`<div class="ticks">${['evidence ids are snapshot rows (31 cited)','scalar key is "total"','no reason code needed (status answer)'].map((s,i)=>`<div class="tick" style="animation-delay:${i*260}ms"><i>✓</i>${s}</div>`).join('')}</div>`,it:'contract.py',is:'0 retries'},
 {k:'answer',t:'An answer with receipts',p:`<b>${R12.rows[0].value} USD</b>, citing ${R12.rows[0].evidence} source rows. The dashboard below breaks it down by programme, country and year.`,
  ins:()=>`<div class="bigval">USD ${R12.rows[0].value}</div><div style="color:var(--t3);font:12px var(--mono);margin-top:6px">${R12.rows[0].evidence} evidence rows</div>`,it:'answer',is:'status: answer'}];
$('#steps').innerHTML=STEPS.map((s,i)=>`<div class="step" data-i="${i}"><div class="no">${String(i+1).padStart(2,'0')} / ${String(STEPS.length).padStart(2,'0')}</div><h3>${s.t}</h3><p>${s.p}</p>${s.k==='answer'?`<a class="open" href="#live" style="text-decoration:none;color:inherit">See the full answer dashboard <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M6 13l6 6 6-6"/></svg></a>`:''}${s.lib?`<button class="open" data-lib="${s.lib}">Open ${s.lib==='schema'?'graph schema':s.lib} library <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>`:''}</div>`).join('');

let typer=0;
function typeInto(html){const id=++typer;setTimeout(()=>{const box=$('#ins .typed');if(!box)return;
  if(RM){box.innerHTML=html;return;}
  const parts=html.split(/(<[^>]+>)/);let out='',pi=0,ci=0;
  (function tick(){if(id!==typer)return;if(pi>=parts.length){box.innerHTML=out;return;}
    const p=parts[pi];if(p.startsWith('<')){out+=p;pi++;return tick();}
    ci+=2;box.innerHTML=out+p.slice(0,ci)+'<span style="color:var(--glow)">▍</span>';if(ci>=p.length){out+=p;pi++;ci=0;}setTimeout(tick,16);})();},10);
  return '<div class="typed"></div>';}
function pathSvg(parts,counts){const w=520;let x=40;let s=`<svg viewBox="0 0 ${w} 110"><defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="#5BA8FF"/></marker></defs>`;
  const n1=60,n2=460;s+=`<line x1="${n1+34}" y1="48" x2="${n2-34}" y2="48" stroke="#5BA8FF" stroke-width="2" stroke-dasharray="4 6" marker-end="url(#ah)"><animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1s" repeatCount="indefinite"/></line>`;
  s+=`<text x="${(n1+n2)/2}" y="40" text-anchor="middle" style="font:11px var(--mono);fill:#A9B4C4">:${parts[1]}</text>`;
  [[n1,parts[0],'#3987e5'],[n2,parts[2],'#199e70']].forEach(([cx,l,c])=>{s+=`<circle cx="${cx}" cy="48" r="30" fill="${c}" fill-opacity=".18" stroke="${c}" stroke-width="2"/><text x="${cx}" y="52" text-anchor="middle" style="font:600 11px var(--sans);fill:#EEF2F8">${l}</text><text x="${cx}" y="98" text-anchor="middle" style="font:11px var(--mono);fill:#6B7789">${counts[l].toLocaleString()} rows</text>`;});
  return s+'</svg>';}

function showStep(i){const s=STEPS[i];document.querySelectorAll('.step').forEach(n=>n.classList.toggle('on',+n.dataset.i===i));
  setStation(PATH.indexOf(s.k));$('#insT').textContent=s.it;$('#insS').textContent=s.is;
  $('#ins').innerHTML=`<div class="ins">${s.ins()}</div>`;}
let active=-1;
const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){const i=+e.target.dataset.i;if(i!==active){active=i;showStep(i);}}});},{rootMargin:'-45% 0px -45% 0px'});
document.querySelectorAll('.step').forEach(n=>io.observe(n));
showStep(0);active=0;
const lib=$('#lib'),body=$('#libbody');let origin=null,trail=[];
const TITLES={planner:'Planner',resolver:'Resolver',templates:'Templates',tools:'Retrieval tools',checks:'Checks and guard',schema:'Graph schema'};
document.addEventListener('click',e=>{const b=e.target.closest('[data-lib]');if(b&&!lib.contains(b))openLib(b.dataset.lib,b,b.dataset.detail);});
function openLib(key,src,sub){origin=src;trail=[];lib.hidden=false;document.body.style.overflow='hidden';
  const r=src.getBoundingClientRect(),ox=r.left+r.width/2,oy=r.top+r.height/2;
  lib.style.transformOrigin=`${ox}px ${oy}px`;
  if(!RM)lib.animate([{transform:'scale(.04)',opacity:0,borderRadius:'50%'},{transform:'scale(1)',opacity:1,borderRadius:'0'}],{duration:520,easing:'cubic-bezier(.2,.8,.2,1)'});
  renderLib(key);if(sub)renderDetail(key,sub);lib.scrollTop=0;$('#close').focus();}
function closeLib(){const fin=()=>{lib.hidden=true;document.body.style.overflow='';origin&&origin.focus&&origin.focus();};
  if(RM)return fin();lib.animate([{opacity:1,transform:'scale(1)'},{opacity:0,transform:'scale(.96)'}],{duration:220,easing:'ease-in'}).onfinish=fin;}
$('#close').onclick=closeLib;addEventListener('keydown',e=>{if(e.key==='Escape'&&!lib.hidden){trail.length>1?renderLib(trail[0]):closeLib();}});
function crumbs(){$('#crumbs').innerHTML=`<button data-c="-1">Engine</button><span>/</span>`+trail.map((t,i)=>i<trail.length-1?`<button data-c="${i}">${esc(i?t:TITLES[t])}</button><span>/</span>`:`<b>${esc(i?t:TITLES[t])}</b>`).join('');
  $('#crumbs').querySelectorAll('button').forEach(b=>b.onclick=()=>{const c=+b.dataset.c;c<0?closeLib():renderLib(trail[0]);});}
function renderLib(key){trail=[key];crumbs();body.innerHTML='';LIB[key]();lib.scrollTop=0;}
function renderDetail(key,id){trail=[key,id];crumbs();body.innerHTML='';DET[key](id);lib.scrollTop=0;}
const head=(k,t,p)=>`<div class="libhead"><div class="kicker">${k}</div><h2>${t}</h2><p>${p}</p></div>`;
const card=(i,html,on)=>{const b=document.createElement('button');b.className='card';b.style.animationDelay=(RM?0:i*30)+'ms';b.innerHTML=html;b.onclick=on;return b;};
const ptable=(params,hot)=>{const ks=Object.keys(params);if(!ks.length)return '<p style="color:var(--t3);font-size:13px;margin:0">No parameters.</p>';
  return `<div class="tbl"><table class="pt"><thead><tr><th>name</th><th>type</th><th>rule</th></tr></thead><tbody>`+ks.map(k=>{const s=params[k];
  const rule=[s.values?`<div class="en">${s.values.map(v=>`<span>${esc(v)}</span>`).join('')}</div>`:'',s.pattern?`<code>${esc(s.pattern)}</code>`:'',s.min!=null?`${s.min} to ${s.max}`:'',s.default!=null?`default <code>${esc(JSON.stringify(s.default))}</code>`:'',s.doc?esc(s.doc):''].filter(Boolean).join(' ');
  return `<tr data-p="${k}"><td>${k}${s.required?' <span class="req">required</span>':''}</td><td>${s.type}</td><td>${rule||'<span style="color:var(--t3)">any</span>'}</td></tr>`;}).join('')+`</tbody></table></div>`;};
function hiCypher(c){let h=esc(c);
  h=h.replace(/('[^']*')/g,'<span class="s">$1</span>');
  h=h.replace(/\b(OPTIONAL MATCH|MATCH|WHERE|RETURN|WITH|ORDER BY|LIMIT|AND|OR|NOT|IS NULL|IS NOT NULL|AS|DISTINCT|UNWIND|IN|DESC|CASE|WHEN|THEN|ELSE|END|EXISTS)\b/g,'<span class="k">$1</span>');
  h=h.replace(/\b(count|sum|collect|coalesce|reduce|date|size|min|max|toString|substring|split|head|keys)\(/g,'<span class="f">$1</span>(');
  h=h.replace(/:([A-Z][A-Za-z_]+)/g,':<span class="lb">$1</span>');
  h=h.replace(/\$(\w+)/g,'<span class="p" data-p="$1">$$$1</span>');return h;}
function linkParams(scope){scope.querySelectorAll('[data-p]').forEach(n=>{const k=n.dataset.p;
  n.addEventListener('mouseenter',()=>scope.querySelectorAll(`[data-p="${k}"]`).forEach(x=>x.classList.add('hot')));
  n.addEventListener('mouseleave',()=>scope.querySelectorAll(`[data-p="${k}"]`).forEach(x=>x.classList.remove('hot')));});}

const LIB={},DET={};
LIB.templates=()=>{body.innerHTML=head('Library · fa26/src/tools/templates.py',`${D.templates.length} Cypher templates`,'Each template is a fixed, parameterised read query. The planner only chooses one and fills its arguments; validation rejects any argument outside the declared type, list or pattern.')+
  `<div class="filters" id="flt"></div><div class="grid" id="g"></div>`;
  const cats=['all',...new Set(D.templates.map(t=>t.cat))];
  const draw=c=>{const g=$('#g');g.innerHTML='';D.templates.filter(t=>c==='all'||t.cat===c).forEach((t,i)=>{const [cn,cc]=CATS[t.cat];
    g.appendChild(card(i,`<span class="cat"><i style="background:${cc}"></i>${cn}</span><div class="nm">${t.name}</div><div class="ds">${esc(t.description)}</div><div class="ft"><span class="pill">${Object.keys(t.params).length} param${Object.keys(t.params).length===1?'':'s'}</span>${t.bench.length?`<span class="pill">${t.bench.length} benchmark q</span>`:''}${D.results[t.bench.find(b=>D.results[b.id])?.id]?'<span class="pill" style="border-color:var(--ok);color:var(--ok)">trial run</span>':''}</div>`,()=>renderDetail('templates',t.name)));});
    document.querySelectorAll('#flt button').forEach(b=>b.classList.toggle('on',b.dataset.c===c));};
  $('#flt').innerHTML=cats.map(c=>`<button data-c="${c}">${c==='all'?'All':CATS[c][0]} · ${c==='all'?D.templates.length:D.templates.filter(t=>t.cat===c).length}</button>`).join('');
  $('#flt').querySelectorAll('button').forEach(b=>b.onclick=()=>draw(b.dataset.c));draw('all');};

DET.templates=name=>{const t=D.templates.find(x=>x.name===name);const [cn,cc]=CATS[t.cat];
  const ex=t.bench.length?t.bench:[];
  body.innerHTML=`<div class="det"><div class="dhead"><div><span class="cat"><i style="background:${cc}"></i>${cn} · template</span><h2>${t.name}</h2><p>${esc(t.description)}</p><div class="note">${esc(t.coverage)}</div></div>
    <div class="cov">${ex.length?`<button class="covbtn" id="covb">Benchmark coverage · ${ex.length}</button><div class="covpop" id="covp" hidden><small>regression (v1) and development only</small>${ex.map(b=>`<div><code>${b.id}</code>${esc(b.q)}</div>`).join('')}</div>`:`<span class="covbtn" style="cursor:default">No benchmark question routed here</span>`}</div></div>
  <div class="two"><div class="box"><h4><span>Cypher</span><span>hover a $param</span></h4><pre class="code" id="cy">${hiCypher(t.cypher)}</pre></div>
    <div class="box"><h4><span>Parameters and validation</span><span>validate_args()</span></h4>${ptable(t.params)}</div></div>
  <div class="box run"><h4><span>Trial run</span><span>${ex.length?'example inputs come from the benchmark':'pick values to bind'}</span></h4>
    <div class="runbar" id="exs"><button class="go" id="go">Run ▸</button>${ex.map((b,i)=>`<button class="ex ${i===0?'on':''}" data-i="${i}" title="${esc(b.q)}"><code>${b.id}</code>${esc(b.q)}</button>`).join('')}</div>
    <div class="lane" id="lane"></div><div class="why" id="why"></div></div></div>`;
  linkParams(body);
  if(ex.length){$('#covb').onclick=e=>{e.stopPropagation();$('#covp').hidden=!$('#covp').hidden;};}
  let sel=ex.findIndex(b=>D.results[b.id]);if(sel<0)sel=0;
  $('#exs').querySelectorAll('.ex').forEach(b=>{b.classList.toggle('on',+b.dataset.i===sel);b.onclick=()=>{sel=+b.dataset.i;$('#exs').querySelectorAll('.ex').forEach(x=>x.classList.toggle('on',x===b));trial(t,ex[sel]);};});
  $('#go').onclick=()=>trial(t,ex[sel]);
  trial(t,ex[sel]);};

function fill(t,args){const out={},miss=[];Object.entries(t.params).forEach(([k,s])=>{let v=args&&k in args?args[k]:s.default;if(v==null||v===''){if(s.required)miss.push(k);v=null;}out[k]=v;});return {out,miss};}
function labelsIn(c){const nodes=[...c.matchAll(/\(\w*:(\w+)/g)].map(m=>m[1]),rels=[...c.matchAll(/\[\w*:(\w+)/g)].map(m=>m[1]);return {nodes:[...new Set(nodes)],rels:[...new Set(rels)]};}
let runId=0;
async function trial(t,b){const id=++runId;const lane=$('#lane'),why=$('#why');
  const args=b?b.args:{};const {out,miss}=fill(t,args);const res=b&&D.results[b.id];
  const P=[['1','Question'],['2','Plan'],['3','Validate'],['4','Graph path'],['5','Result']];
  lane.innerHTML=P.map(([n,h])=>`<div class="ph"><div class="h"><i>${n}</i>${h}</div><div class="b"></div></div>`).join('');
  const ph=[...lane.children];why.textContent='';
  const cy=$('#cy');cy.innerHTML=hiCypher(t.cypher);linkParams(cy.parentElement);
  const step=async(i,html,ms=650)=>{if(id!==runId)throw 0;ph.forEach((p,j)=>{p.classList.toggle('on',j===i);if(j<i)p.classList.add('done');});ph[i].querySelector('.b').innerHTML=html;await wait(ms);};
  try{
    await step(0,b?`<span class="mut">${b.id} · ${b.split}</span><br>${esc(b.q)}`:'<span class="mut">no benchmark question; defaults only</span>');
    await step(1,`tool: <span class="ok">${t.name}</span><br>args: ${esc(JSON.stringify(args))}`);
    await step(2,miss.length?`<span style="color:var(--bad)">missing required: ${miss.join(', ')}</span>`:Object.entries(out).filter(([k,v])=>v!=null).map(([k,v])=>`${k} = <span class="ok">${esc(JSON.stringify(v))}</span>`).join('<br>')+`<br><span class="mut">${Object.values(out).filter(v=>v==null).length} optional left null</span>`);
    cy.querySelectorAll('.p').forEach(sp=>{const k=sp.dataset.p,v=out[k];if(v!=null){sp.className='v';sp.textContent=JSON.stringify(v);}});
    const L=labelsIn(t.cypher);
    await step(3,miniPath(L),900);
    await step(4,res?res.rows.map(r=>`<div class="res">${esc(r.key)}: ${esc(typeof r.value==='number'?r.value.toLocaleString():r.value)}</div>`).join('')+`<span class="mut">${res.rows.reduce((s,r)=>s+r.evidence,0).toLocaleString()} evidence ids</span>`
      :(liveOK&&b?`<button class="go" id="runlive">Run on the graph ▸</button>`:`<span class="mut">Connect to the graph to run this query.</span>`),10);
    const rl=document.getElementById('runlive');if(rl)rl.onclick=async()=>{rl.disabled=true;rl.textContent='Running…';
      try{const r=await API.ask({question:b.q});const fs=Object.entries(r.answer.facts||{});
        ph[4].querySelector('.b').innerHTML=fs.length?fs.map(([k,f])=>`<div class="res">${esc(k)}: ${esc(f.value)}</div>`).join('')+`<span class="mut">${fs.reduce((s,[k,f])=>s+f.evidence_n,0)} evidence ids · ${r.answer.timings?r.answer.timings.total_ms+' ms':''}</span>`:`<span class="mut">${esc(r.answer.status)}: ${esc(r.answer.explanation||r.answer.error||'')}</span>`;}
      catch(e){ph[4].querySelector('.b').innerHTML=`<span class="mut">${esc(e.message)}</span>`;}};
    ph[4].classList.add('done');
    why.innerHTML=b?`Example input is benchmark question <code>${b.id}</code> (${b.split}). ${res?`Result on the benchmark snapshot: ${esc(res.note)}.`:''}`:'';
  }catch(e){}}
function miniPath(L){const n=L.nodes.slice(0,3);if(!n.length)return '<span class="mut">no MATCH pattern</span>';
  const w=240,step=n.length>1?(w-80)/(n.length-1):0;let s=`<svg viewBox="0 0 ${w} 96">`;
  n.forEach((l,i)=>{const x=40+i*step;if(i)s+=`<line x1="${x-step+14}" y1="36" x2="${x-14}" y2="36" stroke="#5BA8FF" stroke-width="1.6" stroke-dasharray="3 4"><animate attributeName="stroke-dashoffset" from="0" to="-14" dur=".8s" repeatCount="indefinite"/></line>`;
    s+=`<circle cx="${x}" cy="36" r="13" fill="#13305A" stroke="#5BA8FF"><animate attributeName="r" values="11;14;11" dur="1.6s" begin="${i*.3}s" repeatCount="indefinite"/></circle><text x="${x}" y="68" text-anchor="middle">${l}</text>`;});
  return s+`</svg><span class="mut">${L.rels.map(r=>':'+r).join(' ')}</span>`;}
const PLAN_CARDS=[
 ['plan','Plan format','One JSON object per call: status, reasons, explanation, tool, args and an optional cypher string.',
  `{"status": "answer" | "abstain" | "clarify",\n "reasons": [],          // abstain/clarify only\n "explanation": "one sentence",\n "tool": "<tool name>" | "free_cypher" | null,\n "args": {...},          // exactly as declared\n "cypher": ""}           // only for free_cypher`],
 ['rules','Routing rules','How the system prompt tells the model to choose.',
  `Prefer a tool whenever one matches the question exactly; use free_cypher only when no tool fits.\nFor "how many activities ..." use count_activities (set only the filters the question states).\nSingle-value answers are keyed exactly: count, total, date; per-currency amounts use currency codes.\nAbstain when the snapshot cannot support the answer (outcomes, forecasts, balances, identities).\nClarify when the organisation or country is ambiguous or a money question does not fix measure, currency and period.`],
 ['catalog','Tool catalogue',`${D.templates.length} templates, ${D.tools.length} retrieval tools and free_cypher are listed to the model with their parameters.`,null],
 ['reasons','Reason codes',`${D.reasons.v1.length} v1 codes and ${D.reasons.v2.length} v2 codes. A v2 clarify or abstain carries exactly one.`,null],
 ['retry','Retry loop','A failed check returns its message to the planner. At most 2 retries, so 1 to 3 LLM calls per question.',null]];
LIB.planner=()=>{body.innerHTML=head('Library · fa26/src/ask.py','Planner','The only step that calls an LLM. It turns a question into a plan; everything after it is deterministic code.')+`<div class="grid" id="g" style="margin-top:22px"></div>`;
  PLAN_CARDS.forEach((c,i)=>$('#g').appendChild(card(i,`<span class="cat"><i style="background:var(--glow)"></i>planner</span><div class="nm">${c[1]}</div><div class="ds">${esc(c[2])}</div>`,()=>renderDetail('planner',c[0]))));};
DET.planner=id=>{const c=PLAN_CARDS.find(x=>x[0]===id);let inner='';
  if(c[3])inner=`<div class="box" style="margin-top:20px"><h4><span>From build_system()</span></h4><pre class="code">${esc(c[3])}</pre></div>`;
  if(id==='catalog')inner=`<div class="two"><div class="box"><h4><span>Templates</span><span>${D.templates.length}</span></h4><div class="codes">${D.templates.map(t=>`<span>${t.name}</span>`).join('')}</div></div><div class="box"><h4><span>Retrieval tools + free Cypher</span><span>${D.tools.length+1}</span></h4><div class="codes">${D.tools.map(t=>`<span>${t.name}</span>`).join('')}<span>free_cypher</span></div></div></div>`;
  if(id==='reasons')inner=`<div class="two"><div class="box"><h4><span>v1 (Q01 to Q20)</span></h4><div class="codes">${D.reasons.v1.map(r=>`<span>${r}</span>`).join('')}</div></div><div class="box"><h4><span>v2 (V2Q*)</span></h4><div class="codes">${D.reasons.v2.map(r=>`<span>${r}</span>`).join('')}</div></div></div>`;
  if(id==='retry')inner=`<div class="box" style="margin-top:20px"><h4><span>plan → execute → check</span><span>max_retries = 2</span></h4><svg viewBox="0 0 700 170" style="width:100%">
    ${[['plan',110],['execute',350],['check',590]].map(([n,x])=>`<circle cx="${x}" cy="70" r="34" fill="#13305A" stroke="#5BA8FF" stroke-width="2"/><text x="${x}" y="75" text-anchor="middle" style="font:600 13px var(--mono);fill:#EEF2F8">${n}</text>`).join('')}
    <path id="rp" d="M144,70 L316,70 M384,70 L556,70" stroke="#5BA8FF" stroke-width="2" stroke-dasharray="4 6" fill="none"><animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1s" repeatCount="indefinite"/></path>
    <path d="M590,104 C590,160 110,160 110,104" stroke="#F2B544" stroke-width="2" stroke-dasharray="4 6" fill="none"><animate attributeName="stroke-dashoffset" from="0" to="20" dur="1s" repeatCount="indefinite"/></path>
    <text x="350" y="150" text-anchor="middle" style="font:12px var(--mono);fill:#F2B544">error message back to the planner (retry 1, retry 2)</text></svg></div>`;
  body.innerHTML=`<div class="det"><div class="dhead"><div><span class="cat"><i style="background:var(--glow)"></i>planner</span><h2>${c[1]}</h2><p>${esc(c[2])}</p></div></div>${inner}</div>`;};
const RUNGS=[['exact-ref','Identifier typed as-is'],['country-alias','Country name or ISO-2'],['exact-name','Exact organisation name'],['alias','Curated alias group'],['name-search','Scored name match']];
LIB.resolver=()=>{body.innerHTML=head('Library · fa26/src/tools/resolver.py','Resolver','Five rules, tried in order. The first that matches decides; candidates come back with a score so the caller can ask instead of merging silently.')+
  `<div class="ladder" id="lad">${RUNGS.map(([k,d],i)=>`<div class="rung" data-k="${k}"><b>${i+1}. ${k}</b>${d}</div>`).join('')}</div>
  <div class="box"><h4><span>Try it</span><span>outputs computed from the snapshot organisations</span></h4><div class="demo" id="demo">${Object.keys(D.demos).map(q=>`<button>${esc(q)}</button>`).join('')}</div><div class="out" id="out"></div></div>
  <h3 style="margin:30px 0 4px;font-size:18px">Alias groups · ${D.groups.length}</h3><div class="grid" id="g" style="margin-top:12px"></div>`;
  D.groups.forEach((g,i)=>$('#g').appendChild(card(i,`<span class="cat"><i style="background:var(--c-org)"></i>alias group</span><div class="nm">${g.group}</div><div class="ds">${g.aliases.map(esc).join(' · ')}</div><div class="ft"><span class="pill">${g.members.length} ref${g.members.length===1?'':'s'} in snapshot</span><span class="pill">${g.patterns.length} patterns</span></div>`,()=>renderDetail('resolver',g.group))));
  const btns=[...$('#demo').children];btns.forEach(b=>b.onclick=()=>demo(b.textContent,b,btns));demo('Oxfam',btns[0],btns);};
async function demo(q,b,btns){btns.forEach(x=>x.classList.toggle('on',x===b));const d=D.demos[q];
  const via=d.kind==='country'?'country-alias':(d.via||'').startsWith('alias')?'alias':d.via;const rungs=[...$('#lad').children];rungs.forEach(r=>r.className='rung');
  for(const r of rungs){if(r.dataset.k===via){r.classList.add('hit');break;}r.classList.add('pass');await wait(220);}
  if(!$('#out'))return;$('#out').innerHTML=`<div style="font:13px var(--mono);color:var(--t2);margin-bottom:8px">${esc(d.note)}</div><div class="chips">${d.cands.map((c,i)=>`<span class="chip hl" style="animation-delay:${i*50}ms">${esc(c.ref)} <span style="color:var(--t3)">${esc(c.name)}</span></span>`).join('')}${d.n>d.cands.length?`<span class="chip" style="animation-delay:300ms">+${d.n-d.cands.length} more</span>`:''}</div>`;}
DET.resolver=g=>{const G=D.groups.find(x=>x.group===g);
  body.innerHTML=`<div class="det"><div class="dhead"><div><span class="cat"><i style="background:var(--c-org)"></i>alias group</span><h2>${G.group}</h2><p>Typed names that map here: ${G.aliases.map(a=>`<code>${esc(a)}</code>`).join(', ')}</p></div></div>
  <div class="two"><div class="box"><h4><span>Members in the snapshot</span><span>${G.members.length}</span></h4><div class="tbl"><table class="pt"><tbody>${G.members.map(m=>`<tr><td>${esc(m.ref)}</td><td>${esc(m.name)}</td></tr>`).join('')}</tbody></table></div></div>
  <div class="box"><h4><span>Match patterns</span><span>against "ref | name"</span></h4><pre class="code">${G.patterns.map(esc).join('\n')}</pre></div></div></div>`;};
LIB.tools=()=>{body.innerHTML=head('Library · fa26/retrieval/tools.py via src/tools/adapter.py','Retrieval tools','Five Python tools from the team retrieval layer, exposed to the planner through an adapter that converts their output to key, value and evidence.')+`<div class="grid" id="g" style="margin-top:22px"></div>`;
  D.tools.forEach((t,i)=>$('#g').appendChild(card(i,`<span class="cat"><i style="background:var(--c-money)"></i>${t.money?'money tool':'tool'}</span><div class="nm">${t.name}</div><div class="ds">${esc(t.description)}</div><div class="ft"><span class="pill">${Object.keys(t.params).length} params</span><span class="pill">fn ${t.fn}</span></div>`,()=>renderDetail('tools',t.name))));};
DET.tools=n=>{const t=D.tools.find(x=>x.name===n);
  body.innerHTML=`<div class="det"><div class="dhead"><div><span class="cat"><i style="background:var(--c-money)"></i>retrieval tool · ${t.fn}()</span><h2>${t.name}</h2><p>${esc(t.description)}</p>${t.money?`<div class="note">Defaults differ from the templates on purpose: these tools default to measure <code>amount</code>${t.params.exclude_self?' and exclude the publisher itself':''}; the templates default to <code>net</code> to match the benchmark contracts.</div>`:''}</div></div>
  <div class="box" style="margin-top:20px"><h4><span>Parameters</span><span>validate_retrieval_args()</span></h4>${ptable(t.params)}</div></div>`;};
const CHECKS=[['guard','Free-Cypher guard','A conservative read-only prefilter for queries the model writes itself. Not an authorisation boundary; live runs also use a read-only database user.','src/text2cypher_eval.py'],
 ['evidence','Evidence ids','Every cited id must be a real row of a pinned snapshot table, written <table>.csv:row:<n>, or manifest:<table>.csv for a zero result.','src/tools/contract.py'],
 ['scalar','Scalar keys','A single-value answer is keyed count, total or date, decided from the question wording.','src/tools/contract.py'],
 ['reasons','Reason codes','Clarify and abstain must use the fixed vocabulary; a v2 question gets exactly one code.','src/tools/contract.py']];
LIB.checks=()=>{body.innerHTML=head('Library · contract and guard','Checks and guard','Nothing reaches the page until these pass. A failure message goes back to the planner for another try.')+`<div class="grid" id="g" style="margin-top:22px"></div>`;
  CHECKS.forEach((c,i)=>$('#g').appendChild(card(i,`<span class="cat"><i style="background:var(--ok)"></i>${c[3]}</span><div class="nm">${c[1]}</div><div class="ds">${esc(c[2])}</div><div class="ft"><span class="pill">live tester</span></div>`,()=>renderDetail('checks',c[0]))));};
function guardJS(q){const R=[];const add=(ok,t)=>R.push([ok,t]);
  add(!!q&&q.length<=20000,'present and at most 20,000 characters');
  add(![';','//','/*','*/','`'].some(x=>q.includes(x)),'no ; // /* */ or backticks');
  add(!/\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD|FOREACH|INSERT|ALTER|GRANT|DENY|REVOKE|USE)\b/i.test(q),'no write, admin or procedure clause');
  add(/^(MATCH|OPTIONAL\s+MATCH|WITH|UNWIND|RETURN)\b/i.test(q),'starts with MATCH, OPTIONAL MATCH, WITH, UNWIND or RETURN');
  add(/\bRETURN\b/i.test(q),'contains RETURN');return R;}
const ROW=/^([A-Za-z0-9_]+\.csv):row:(\d+)$/;
function evJS(e){const m=e.match(ROW);if(m)return [[D.manifest.includes(m[1]),`table ${m[1]} is in the pinned manifest`],[+m[2]>=1,'row number is 1 or more']];
  if(e.startsWith('manifest:'))return [[D.manifest.includes(e.slice(9)),'manifest table exists']];return [[false,'matches <table>.csv:row:<n> or manifest:<table>.csv']];}
function scalarJS(q){q=(q||'').trim().toLowerCase();if(q.startsWith('how many')||q.startsWith('what is the number of')||q.startsWith('count '))return 'count';
  if(q.startsWith('how much')||/\b(total|sum|amount)\b/.test(q))return 'total';if(q.startsWith('when')||/\b(earliest|latest)\b.*\bdate\b|\bdate\b/.test(q))return 'date';return null;}
DET.checks=id=>{const c=CHECKS.find(x=>x[0]===id);let ui='';
  const S={guard:["MATCH (a:Activity) RETURN count(a) AS value","MATCH (a:Activity) DETACH DELETE a","MATCH (n) RETURN n; MATCH (m) RETURN m","CALL db.labels()"],
    evidence:["nodes_activities.csv:row:12","nodes_transactions.csv:row:0","GB-CHC-202918-AFHA25","manifest:nodes_budgets.csv"],
    scalar:[D.templates.find(t=>t.name==='transaction_total').bench[0].q,"How many activities are recorded in this snapshot?","When was the latest update?","Which publishers work in Yemen?"]};
  if(id==='reasons')ui=`<div class="two"><div class="box"><h4><span>v1 codes</span></h4><div class="codes">${D.reasons.v1.map(r=>`<span>${r}</span>`).join('')}</div></div><div class="box"><h4><span>v2 codes</span><span>one per answer</span></h4><div class="codes">${D.reasons.v2.map(r=>`<span>${r}</span>`).join('')}</div><p style="font-size:12.5px;color:var(--t2);margin:12px 0 0">When several scope codes apply, country beats organisation beats funding.</p></div></div>`;
  else ui=`<div class="box tester" style="margin-top:20px"><h4><span>Live tester</span><span>same rules as contract.py and the guard</span></h4><input id="tin" spellcheck="false" value="${esc(S[id][0])}"><div class="samples">${S[id].map(s=>`<button title="${esc(s)}">${esc(s)}</button>`).join('')}</div><div id="tout"></div></div>`;
  body.innerHTML=`<div class="det"><div class="dhead"><div><span class="cat"><i style="background:var(--ok)"></i>${c[3]}</span><h2>${c[1]}</h2><p>${esc(c[2])}</p></div></div>${ui}</div>`;
  if(id==='reasons')return;const inp=$('#tin');
  const run=()=>{const v=inp.value;let html='';
    if(id==='scalar'){const k=scalarJS(v);html=`<div class="verdict ${k?'ok':'no'}">${k?`single value is keyed "${k}"`:'no scalar key: multi-fact answer keeps its own keys'}</div>`;}
    else{const R=id==='guard'?guardJS(v):evJS(v.trim());const ok=R.every(r=>r[0]);html=`<div class="verdict ${ok?'ok':'no'}">${ok?'✓ passes':'✕ rejected'}</div><div class="rules">${R.map(([o,t])=>`<div class="${o?'ok':'no'}"><i>${o?'✓':'✕'}</i>${esc(t)}</div>`).join('')}</div>`;}
    $('#tout').innerHTML=html;};
  inp.oninput=run;body.querySelectorAll('.samples button').forEach(b=>b.onclick=()=>{inp.value=b.title;run();});run();};
const SN={Organisation:[150,250,'#d95926','ref, name, publisher, source_id'],Activity:[450,250,'#3987e5','iati_identifier, publisher, title, status, humanitarian, default_currency, match_basis, start/end dates, last_updated, hotspot_countries, source_id'],
  Transaction:[320,450,'#199e70','tx_id, type 1..4, type_name, date, value (signed), value_cents (exact), currency, source_id'],Budget:[600,450,'#c98500','type, status, value, currency, period_start, period_end, source_id'],
  Country:[720,120,'#6250d6','code, name'],Sector:[780,270,'#e87ba4','sector_key'],Location:[590,80,'#1baf7a','location_id, name'],SDG:[760,400,'#8a96a8','sdg_key'],
  Emergency:[300,80,'#555','(no rows in this snapshot)'],Region:[440,60,'#555','(no rows in this snapshot)'],PolicyMarker:[150,90,'#555','(no rows in this snapshot)']};
const SE=[['Organisation','REPORTS','Activity',-26],['Organisation','PARTICIPATES_IN','Activity',26],['Activity','HAS_TRANSACTION','Transaction',0],['Organisation','PROVIDES','Transaction',-55],['Transaction','RECEIVED_BY','Organisation',-55],
  ['Activity','HAS_BUDGET','Budget',0],['Activity','TARGETS','Country',0],['Activity','CLASSIFIED_AS','Sector',0],['Activity','LOCATED_AT','Location',0],['Activity','CONTRIBUTES_TO','SDG',0],
  ['Activity','RESPONDS_TO','Emergency',0],['Activity','TARGETS_REGION','Region',0],['Activity','MARKED_WITH','PolicyMarker',0]];
LIB.schema=()=>{const N=D.schema.nodes,R=D.schema.rels;
  body.innerHTML=head('Library · fa26/retrieval/schema_prototype.py','Graph schema',`${Object.values(N).reduce((a,b)=>a+b,0).toLocaleString()} nodes from the pinned snapshot. Relationship CSV rows total ${Object.values(R).reduce((a,b)=>a+b,0).toLocaleString()}; the loaded graph has ${D.expected_counts.relationships.toLocaleString()} because duplicate participation rows merge.`)+
  `<div class="schemawrap"><div class="box"><svg id="schema" viewBox="0 0 900 520"></svg></div><div class="box"><h4><span id="pn">Click a node</span><span id="pc"></span></h4><div class="props" id="pp">Each circle is sized by its CSV row count. Faded labels exist in the schema but have no rows in this snapshot.</div></div></div>`;
  const svg=$('#schema');const E=el('g',{},svg),G=el('g',{},svg);const items=[];
  SE.forEach(([a,r,b,off],i)=>{const [x1,y1]=SN[a],[x2,y2]=SN[b];const mx=(x1+x2)/2-(y2-y1)*off/200,my=(y1+y2)/2+(x2-x1)*off/200;
    const g=el('g',{class:'se'+(R[r]?'':' empty')},E);const p=el('path',{d:`M${x1},${y1}Q${mx},${my} ${x2},${y2}`},g);
    if(!RM){const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;p.style.transition=`stroke-dashoffset .9s ease ${i*.06}s`;requestAnimationFrame(()=>requestAnimationFrame(()=>p.style.strokeDashoffset=0));setTimeout(()=>p.style.strokeDasharray='',1800);}
    const t=el('text',{x:(x1+x2)/2*.5+mx*.5,y:(y1+y2)/2*.5+my*.5-4,'text-anchor':'middle'},g);t.textContent=`${r} · ${R[r].toLocaleString()}`;items.push({g,a,b});});
  Object.entries(SN).forEach(([k,[x,y,c,props]],i)=>{const n=N[k]||0,r=n?12+Math.sqrt(n)/4.2:10;
    const g=el('g',{class:'sn'+(n?'':' empty')},G);el('circle',{cx:x,cy:y,r:r+8,fill:c,'fill-opacity':.12},g);
    const cc=el('circle',{cx:x,cy:y,r,fill:c,'fill-opacity':1,stroke:'#07090F','stroke-width':2},g);
    if(!RM)cc.animate([{r:0},{r}],{duration:600,delay:300+i*50,easing:'cubic-bezier(.2,.8,.2,1)',fill:'backwards'});
    const t=el('text',{x,y:y+r+18,'text-anchor':'middle',style:'fill:#EEF2F8;font-weight:500'},g);t.textContent=k;
    const t2=el('text',{x,y:y+r+32,'text-anchor':'middle',style:'font:10.5px var(--mono);fill:#6B7789'},g);t2.textContent=n.toLocaleString();
    g.onclick=()=>{G.querySelectorAll('.sn').forEach(s=>s.classList.toggle('on',s===g));items.forEach(it=>it.g.classList.toggle('on',it.a===k||it.b===k));
      $('#pn').textContent=k;$('#pc').textContent=n.toLocaleString()+' CSV rows';
      const rels=SE.filter(e=>e[0]===k||e[2]===k).map(e=>`(${e[0]})-[:${e[1]}]->(${e[2]}) <span style="color:var(--t3)">${R[e[1]].toLocaleString()}</span>`);
      $('#pp').innerHTML=`<b>properties</b><br>${esc(props)}<br><br><b>relationships</b><br>${rels.join('<br>')}${D.schema.deviations[SE.find(e=>(e[0]===k||e[2]===k)&&D.schema.deviations[e[1]])?.[1]]?`<br><br><span style="color:var(--amber)">${esc(D.schema.deviations.PARTICIPATES_IN)}</span>`:''}`;};});};
DET.schema=()=>LIB.schema();

{const nodes=Object.values(D.schema.nodes).reduce((a,b)=>a+b,0),rels=D.expected_counts.relationships;
 document.getElementById('stA').dataset.count=D.dataset.activities;document.getElementById('stN').dataset.count=nodes;document.getElementById('stR').dataset.count=rels;
 document.getElementById('browseBtn').textContent=`Browse ${D.templates.length} templates`;}
const RMv=RM;
const SV='http://www.w3.org/2000/svg';
const mk=(t,a,p)=>{const e=document.createElementNS(SV,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e;};
const fmt=v=>Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtN=v=>Number(v).toLocaleString('en-US');
const fK=v=>{v=Number(v);return Math.abs(v)>=1e6?(v/1e6).toFixed(2)+'M':Math.abs(v)>=1e3?Math.round(v/1e3)+'K':String(Math.round(v*100)/100);};
const X=esc;
const PAL=['#3987e5','#d95926','#199e70','#c98500','#d55181','#0ca30c','#8A96A8'];

const API={
  base:(typeof window.IATI_API_BASE==='string'?window.IATI_API_BASE:(location.protocol.startsWith('http')?'':null)),
  live:false,
  url(p){return (this.base||'').replace(/\/$/,'')+p;},
  async ask({question,model='default',route='auto'}){
    const r=await fetch(this.url('/api/ask'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,model,route})});
    if(!r.ok){let m='HTTP '+r.status;try{m=(await r.json()).detail||m;}catch(e){}throw new Error(m);}return r.json();},
  async meta(){const r=await fetch(this.url('/api/meta'));if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}
};
window.IATI_API=API;

const tip=document.getElementById('tip');
const mv=e=>{tip.style.left=Math.min(e.clientX+14,innerWidth-tip.offsetWidth-10)+'px';tip.style.top=(e.clientY+14)+'px';};
function hover(n,html,on,off){n.addEventListener('mouseenter',e=>{tip.innerHTML=html;tip.hidden=false;mv(e);on&&on();});n.addEventListener('mousemove',mv);n.addEventListener('mouseleave',()=>{tip.hidden=true;off&&off();});}
const cmp=document.getElementById('modeCompare'),pop=document.getElementById('lockpop');
cmp.addEventListener('click',e=>{e.stopPropagation();pop.hidden=!pop.hidden;});
document.addEventListener('click',()=>{pop.hidden=true;});
function countUp(n){const money=n.dataset.money?+n.dataset.money:null,end=money??+n.dataset.count;
  if(RMv){n.textContent=money!=null?fmt(end):fmtN(end);return;}const t0=performance.now();
  const f=now=>{const p=Math.min((now-t0)/1200,1),v=end*(1-Math.pow(1-p,3));n.textContent=money!=null?fmt(v):fmtN(Math.round(v));if(p<1)requestAnimationFrame(f);};requestAnimationFrame(f);}
document.querySelectorAll('.stats [data-count]').forEach(countUp);
(async function(){const cv=document.getElementById('gl'),hsec=document.getElementById('hotspots'),lab=document.getElementById('glabels');if(!D.globe||!cv)return;
  const G0=D.globe,PUBC={'Oxfam GB':'#FF7A45','Oxfam America':'#5BA8FF','WFP':'#3DDC97'};
  const top=Object.entries(G0.activities).sort((a,b)=>b[1]-a[1]).slice(0,3);
  hsec.innerHTML=top.map(([c,n],i)=>{const ls=G0.links.filter(l=>l.country===c).sort((a,b)=>b.activities-a.activities),mx=ls.length?ls[0].activities:1;
    return `<div class="hs" data-c="${X(c)}"><div class="card"><div class="k">Hotspot ${i+1} of ${top.length}</div><h3>${X(c)}</h3>
      <p><span class="num">${fmtN(n)} activities</span> in this snapshot. ${ls.length>1?`Reported by ${ls.length} publishers.`:ls.length?`Reported by ${X(ls[0].publisher)}.`:''}</p>
      <div class="bars">${ls.map(l=>`<div><span>${X(l.publisher)}</span><i style="width:${Math.max(6,100*l.activities/mx)}%;background:${PUBC[l.publisher]||'#9CCBFF'};color:${PUBC[l.publisher]||'#9CCBFF'}"></i><b>${fmtN(l.activities)}</b></div>`).join('')}</div></div></div>`;}).join('');
  let G;
  try{const pts=new Int16Array(await (await fetch('globe-pts.bin')).arrayBuffer());G=mountGlobe({canvas:cv,data:G0,pts,labelsEl:lab,avoid:document.querySelector('.hero .max>div:first-child'),topInset:(document.querySelector('nav')||{}).offsetHeight||64});window.__atlasGlobe=G;}catch(e){hsec.hidden=true;return;}
  const steps=[...hsec.querySelectorAll('.hs')];let cur,act;
  const settled=card=>()=>{const b=card.getBoundingClientRect();if(innerWidth<=920){const bot=innerHeight*.92;return {left:b.left,right:b.right,top:bot-card.offsetHeight,bottom:bot};}const mid=innerHeight/2;return {left:b.left,right:b.right,top:mid-card.offsetHeight/2,bottom:mid+card.offsetHeight/2};};
  function onScroll(){const on=hsec.getBoundingClientRect().bottom>innerHeight*.25;
    if(on!==act){act=on;cv.classList.toggle('on',on);lab.classList.toggle('off',!on);G.setActive(on);}
    const mid=innerHeight*.5;let hit=null;for(const s of steps){const r=s.getBoundingClientRect();if(r.top<mid&&r.bottom>mid)hit=s;}
    steps.forEach(s=>s.classList.toggle('on',s===hit));const c=hit?hit.dataset.c:null;if(c!==cur){cur=c;G.setFocus(c,hit?settled(hit.querySelector('.card')):null);}}
  addEventListener('scroll',onScroll,{passive:true});onScroll();})();
const R={};
let CUR=null,colMap={};
function colorFor(keys){colMap={};keys.filter(k=>k!=='Other'&&k!=='Other countries').forEach((k,i)=>colMap[k]=PAL[Math.min(i,PAL.length-1)]);colMap['Other']=colMap['Other countries']='#8A96A8';}
const C=k=>colMap[k]||'#8A96A8';
const isMoney=()=>CUR.views.measure==='money';
const unit=()=>isMoney()?(CUR.views.currency||''):'activities';
const valTxt=v=>isMoney()?fmt(v):fmtN(v);
function clear(el){while(el.firstChild)el.removeChild(el.firstChild);}
function empty(svg,msg){clear(svg);const t=mk('text',{x:'50%',y:'50%','text-anchor':'middle',style:'fill:#6B7789;font-size:13px'},svg);t.textContent=msg;}

R.answer=()=>{const a=CUR.answer,v=CUR.views,box=document.getElementById('ansbody');
  const st={answer:['answered · checks passed','ok'],clarify:['needs clarification','warn'],abstain:['cannot answer from this data','stop']}[a.status]||[a.status,'ok'];
  let html=`<span class="dstatus ${st[1]}">${st[0]}</span>`;
  const facts=v.facts||[];
  if(a.status!=='answer'){html+=`<p class="expl">${X(a.explanation||'')}</p><div class="reasons">${(a.reasons||[]).map(r=>`<code>${X(r)}</code>`).join('')}</div>`;}
  else if(a.error&&!facts.length){html+=`<p class="expl">${X(a.error)}</p>`;}
  else if(facts.length===1){const f=facts[0];const n=Number(f.value);
    html+=`<div class="mega">${isMoney()?`<small>${X(v.currency||'')}</small>`:''}<span data-${isMoney()?'money':'count'}="${isNaN(n)?0:n}">${isNaN(n)?X(f.value):'0'}</span></div>`;
}
  else{html+=`<div class="factlist">${facts.slice(0,8).map(f=>`<div><span>${X(f.key)}</span><b>${X(isNaN(Number(f.value))?f.value:valTxt(f.value))}</b></div>`).join('')}</div>`;}
  const yr=(v.breakdowns||{}).year||[];
  html+=`<div class="mini"><div><span>Top country</span><b>${X(((v.breakdowns||{}).country||[])[0]?.key||'none')}</b></div><div><span>Tool</span><b>${X(a.tool||'none')}</b></div><div><span>LLM calls</span><b>${a.model_calls??'none'}</b></div></div>`;
  box.innerHTML=html+`<svg id="d-spark" viewBox="0 0 400 74" style="margin-top:14px" aria-label="By year"></svg>`;
  box.querySelectorAll('[data-money],[data-count]').forEach(countUp);
  const s=document.getElementById('d-spark');if(yr.length<2)return s.remove();
  const ys=yr.map(y=>y.value),max=Math.max(...ys)*1.15||1,x=i=>20+i*(360/(yr.length-1)),y=val=>64-val/max*54;
  const d=yr.map((p,i)=>`${i?'L':'M'}${x(i)},${y(p.value)}`).join('');const df=mk('defs',{},s);const lg=mk('linearGradient',{id:'sgd',x1:0,x2:0,y1:0,y2:1},df);
  mk('stop',{offset:0,'stop-color':'#3987e5','stop-opacity':.45},lg);mk('stop',{offset:1,'stop-color':'#3987e5','stop-opacity':0},lg);
  mk('path',{d:d+`L${x(yr.length-1)},68L${x(0)},68Z`,fill:'url(#sgd)'},s);const p=mk('path',{d,fill:'none',stroke:'#5BA8FF','stroke-width':2},s);
  const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=RMv?0:L;p.getBoundingClientRect();p.style.transition='stroke-dashoffset 1.4s ease';p.style.strokeDashoffset=0;
  yr.forEach((pt,i)=>{mk('circle',{cx:x(i),cy:y(pt.value),r:3.5,fill:'#07090F',stroke:'#5BA8FF','stroke-width':2},s);
    if(yr.length<=8){const t=mk('text',{x:x(i),y:y(pt.value)-8,'text-anchor':'middle',class:'val'},s);t.textContent=pt.key;}
    hover(mk('circle',{cx:x(i),cy:y(pt.value),r:14,fill:'transparent'},s),`${X(pt.key)}<br><b>${valTxt(pt.value)} ${X(unit())}</b>`);});};

R.flow=()=>{const svg=document.getElementById('d-sankey');clear(svg);const f=CUR.views.flow;if(!f||!f.links.length)return empty(svg,'No activity rows in this answer');
  const H=320,top=26,nw=10,MINH=16,X0=24,X1=330,X2=560;
  const layer=k=>k[0]==='p'?0:k[0]==='g'?1:2;const nodes={};
  f.links.forEach(l=>{[l.source,l.target].forEach(k=>nodes[k]=nodes[k]||{k,l:layer(k),in:0,out:0});nodes[l.source].out+=l.value;nodes[l.target].in+=l.value;});
  const total=Object.values(nodes).filter(n=>n.l===0).reduce((s,n)=>s+n.out,0)||1;
  const cols=[0,1,2].map(i=>Object.values(nodes).filter(n=>n.l===i).sort((a,b)=>Math.max(b.in,b.out)-Math.max(a.in,a.out)));
  const k=(H-top-8-12*(Math.max(...cols.map(c=>c.length))-1))/total;
  cols.forEach((c,i)=>{const hs=c.map(n=>{n.v=Math.max(n.in,n.out);n.h=n.v*k;n.dh=Math.max(n.h,MINH);return n.dh;});const used=hs.reduce((a,b)=>a+b,0);
    const gap=c.length>1?(H-top-8-used)/(c.length-1):0;let y=c.length>1?top:top+(H-top-8-used)/2;c.forEach(n=>{n.y=y;n.oy=y+(n.dh-n.h)/2;n.iy=n.oy;y+=n.dh+gap;n.x=[X0,X1,X2][i];});});
  colorFor(cols[2].map(n=>n.k.slice(2)));
  const rib=(x0,y0,h0,x1,y1)=>{const m=(x0+x1)/2;return `M${x0},${y0}C${m},${y0} ${m},${y1} ${x1},${y1}L${x1},${y1+h0}C${m},${y1+h0} ${m},${y0+h0} ${x0},${y0+h0}Z`;};
  const items=[];const order=f.links.slice().sort((a,b)=>cols[layer(a.target)].indexOf(nodes[a.target])-cols[layer(b.target)].indexOf(nodes[b.target]));
  order.forEach(l=>{const s=nodes[l.source],t=nodes[l.target],h=l.value*k;const c=t.l===2?C(t.k.slice(2)):'#5BA8FF';
    const r=mk('path',{d:rib(s.x+nw,s.oy,h,t.x,t.iy),fill:c,'fill-opacity':t.l===2?.55:.2,class:'rib'},svg);
    const fl=mk('path',{d:`M${s.x+nw},${s.oy+h/2}C${(s.x+t.x)/2},${s.oy+h/2} ${(s.x+t.x)/2},${t.iy+h/2} ${t.x},${t.iy+h/2}`,fill:'none',stroke:t.l===2?'#fff':'#C9DFFF','stroke-opacity':.6,'stroke-width':1.4,class:'flow'},svg);
    items.push({els:[r,fl],keys:[s.k,t.k]});hover(r,`${X(s.k.slice(2))} → ${X(t.k.slice(2))}<br><b>${valTxt(l.value)} ${X(unit())}</b>`,()=>foc(t.k),unf);s.oy+=h;t.iy+=h;});
  function foc(key){svg.classList.add('dim');items.forEach(i=>i.els.forEach(e=>e.classList.toggle('on',i.keys.includes(key))));}
  function unf(){svg.classList.remove('dim');items.forEach(i=>i.els.forEach(e=>e.classList.remove('on')));}
  cols.forEach((c,i)=>c.forEach(n=>{const y0=n.y+(n.dh-n.h)/2;mk('rect',{x:n.x,y:y0,width:nw,height:Math.max(n.h,3),rx:3,fill:i===0?'#5BA8FF':i===2?C(n.k.slice(2)):'#8A96A8'},svg);
    const name=n.k.slice(2),short=name.length>34?name.slice(0,33)+'…':name;
    const left=i===1,anchor=left?'end':'start',tx=i===0?n.x:left?n.x-8:n.x+nw+8,ty=i===0?n.y-8:n.y+n.dh/2-1;
    const t=mk('text',{x:tx,y:ty,'text-anchor':i===0?'start':anchor,class:'lbl',style:'paint-order:stroke;stroke:#10151F;stroke-width:4px;font-size:11.5px'},svg);t.textContent=short;
    if(i>0){const vv=mk('text',{x:tx,y:ty+13,'text-anchor':anchor,class:'val',style:'paint-order:stroke;stroke:#10151F;stroke-width:4px'},svg);vv.textContent=fK(n.v);}
    hover(t,`${X(name)}<br><b>${valTxt(n.v)} ${X(unit())}</b>`);}));
  svg.querySelectorAll('.rib').forEach((r,i)=>{r.style.opacity=0;r.style.transition='opacity .6s';setTimeout(()=>r.style.opacity='',RMv?0:60*i);});};

R.donut=()=>{const svg=document.getElementById('d-donut');clear(svg);const b=(CUR.views.breakdowns||{}).country||[];const lg=document.getElementById('d-legend');
  if(!b.length){lg.innerHTML='';return empty(svg,'No country breakdown');}
  colorFor(b.map(x=>x.key));const total=b.reduce((s,x)=>s+x.value,0)||1;const cx=130,cy=110,r=78,sw=22,Cc=2*Math.PI*r;let off=0;
  mk('circle',{cx,cy,r,fill:'none',stroke:'#1A2230','stroke-width':sw},svg);
  b.forEach((c,i)=>{const fr=c.value/total,len=Math.max(fr*Cc-3,1);const a=mk('circle',{cx,cy,r,fill:'none',stroke:C(c.key),'stroke-width':sw,'stroke-dasharray':`0 ${Cc}`,'stroke-dashoffset':-off,transform:`rotate(-90 ${cx} ${cy})`,style:'transition:stroke-dasharray 1.1s cubic-bezier(.2,.8,.2,1)'},svg);
    setTimeout(()=>a.setAttribute('stroke-dasharray',`${len} ${Cc}`),RMv?0:120+i*140);hover(a,`${X(c.key)}<br><b>${valTxt(c.value)} ${X(unit())}</b> · ${(fr*100).toFixed(1)}%`);off+=fr*Cc;});
  const t=mk('text',{x:cx,y:cy-2,'text-anchor':'middle',style:'font:600 22px var(--mono);fill:#EEF2F8'},svg);t.textContent=(isMoney()?'':'')+fK(total);
  const t2=mk('text',{x:cx,y:cy+17,'text-anchor':'middle','font-size':11,fill:'#6B7789'},svg);t2.textContent=unit();
  lg.innerHTML=b.map(c=>`<span><i style="background:${C(c.key)}"></i>${X(c.key)} ${(c.value/total*100).toFixed(0)}%</span>`).join('');};

R.cols=()=>{const svg=document.getElementById('d-cols');clear(svg);const yr=(CUR.views.breakdowns||{}).year||[];if(!yr.length)return empty(svg,'No dated rows');
  const x0=44,base=190,H=160,mx=Math.max(...yr.map(y=>Math.abs(y.value)))||1,W=300-x0-6,bw=Math.max(Math.min(36,W/yr.length-8),4);
  for(let i=0;i<=4;i++){const v=mx*i/4,y=base-v/mx*H;mk('line',{x1:x0,x2:300,y1:y,y2:y,stroke:'#1A2230'},svg);const t=mk('text',{x:x0-6,y:y+4,'text-anchor':'end','font-size':10,fill:'#6B7789'},svg);t.textContent=i?fK(v):'0';}
  yr.forEach((p,i)=>{const cx=x0+W/yr.length*(i+.5),h=Math.abs(p.value)/mx*H;
    const r=mk('rect',{x:cx-bw/2,y:base-h,width:bw,height:Math.max(h,1),rx:3,fill:p.value<0?'#FF7B72':'#3987e5',style:`transform-origin:${cx}px ${base}px;transform:scaleY(${RMv?1:0});transition:transform .9s cubic-bezier(.2,.8,.2,1) ${(i*.06).toFixed(2)}s`},svg);
    requestAnimationFrame(()=>requestAnimationFrame(()=>r.style.transform='scaleY(1)'));
    if(yr.length<=8){const v=mk('text',{x:cx,y:base-h-6,'text-anchor':'middle',class:'val',style:'fill:#EEF2F8'},svg);v.textContent=fK(p.value);}
    if(yr.length<=10||i%Math.ceil(yr.length/8)===0){const t=mk('text',{x:cx,y:base+16,'text-anchor':'middle','font-size':10.5},svg);t.textContent=p.key;}
    hover(mk('rect',{x:cx-W/yr.length/2,y:0,width:W/yr.length,height:250,fill:'transparent'},svg),`${X(p.key)}<br><b>${valTxt(p.value)} ${X(unit())}</b>`);});
  mk('line',{x1:x0,x2:300,y1:base,y2:base,stroke:'#3A4659'},svg);};

let termId=0;
R.term=()=>{const t=document.getElementById('d-term'),a=CUR.answer,tm=a.timings||{},id=++termId;
  const L=[['c','// plan'],['','\nstatus = '],['s',JSON.stringify(a.status)],['','\ntool = '],['s',JSON.stringify(a.tool||null)],['','\nargs = '],['s',JSON.stringify(a.args||{})]];
  if(a.cypher)L.push(['c','\n// query'],['k','\n'+a.cypher.split('\n').slice(0,6).join('\n')]);
  L.push(['c','\n// checks']);
  if(a.status==='answer'&&!a.error)L.push(['ok',`\n✓ evidence ids  ✓ ${(CUR.views.facts||[]).length===1?'key "'+X(CUR.views.facts[0].key)+'"':'keys'}`]);else if(a.error)L.push(['s','\n✕ '+a.error]);else L.push(['ok','\n✓ reason codes: '+(a.reasons||[]).join(', ')]);
  if(tm.total_ms!=null)L.push(['c','\n// timing'],['',`\nplan ${tm.plan_ms??0} ms · query ${tm.query_ms??0} ms · checks ${tm.format_ms??0} ms · total ${tm.total_ms} ms`]);
  if(RMv){t.innerHTML=L.map(([c,s])=>`<span class="${c}">${X(s)}</span>`).join('');return;}let li=0,ci=0,html='';
  (function tick(){if(id!==termId)return;if(li>=L.length){t.innerHTML=html+'<span class="CUR"></span>';return;}const [c,s]=L[li];ci+=3;
    t.innerHTML=html+`<span class="${c}">${X(s.slice(0,ci))}</span><span class="CUR"></span>`;if(ci>=s.length){html+=`<span class="${c}">${X(s)}</span>`;li++;ci=0;}setTimeout(tick,14);})();};

R.graph=()=>{const svg=document.getElementById('d-graph');clear(svg);const g=CUR.views.graph;const h=document.getElementById('graphTitle');
  if(!g||!g.activities.length){h.textContent='Evidence subgraph';return empty(svg,'No activity rows in this answer');}
  h.textContent=`Evidence subgraph · ${g.activities.length+g.hidden} activities${g.hidden?' (top '+g.activities.length+' shown)':''}`;
  const A=g.activities;const pubs=[...new Set(A.map(a=>a.publisher))];const cs=[...new Set(A.map(a=>a.country))];colorFor(((CUR.views.breakdowns||{}).country||[]).map(c=>c.key));
  {const XP=['#9085e9','#4fc3d9','#F2B544','#e07a9a','#7cc96b','#d9a05b'];let j=0;cs.forEach(c=>{if(!colMap[c]||colMap[c]==='#8A96A8')colMap[c]=XP[j++%XP.length];});}
  const PC=['#5BA8FF','#F2B544','#7FE0C0'];
  const py=i=>pubs.length===1?200:60+i*(280/(pubs.length-1)),ay=i=>A.length===1?200:24+i*(352/(A.length-1)),cy=i=>cs.length===1?200:40+i*(320/(cs.length-1));
  const E=mk('g',{},svg),N=mk('g',{},svg);const items=[];
  A.forEach((o,i)=>{const p={x:70,y:py(pubs.indexOf(o.publisher))},q={x:330,y:ay(i)},c={x:580,y:cy(cs.indexOf(o.country))};
    const e1=mk('path',{d:`M${p.x},${p.y}C200,${p.y} 200,${q.y} ${q.x},${q.y}`,fill:'none',stroke:C(o.country),'stroke-width':1.6,'stroke-opacity':.7},E);
    const e2=mk('path',{d:`M${q.x},${q.y}C460,${q.y} 460,${c.y} ${c.x},${c.y}`,fill:'none',stroke:C(o.country),'stroke-width':1.6,'stroke-opacity':.55,class:'flow'},E);
    const L=e1.getTotalLength();e1.style.strokeDasharray=L;e1.style.strokeDashoffset=RMv?0:L;e1.getBoundingClientRect();e1.style.transition=`stroke-dashoffset 1s ease ${i*.06}s`;e1.style.strokeDashoffset=0;
    items.push({els:[e1,e2],k:o.country});
    const gq=mk('g',{},N);mk('rect',{x:q.x-7,y:q.y-7,width:14,height:14,rx:3,fill:C(o.country),'fill-opacity':.35,stroke:C(o.country),'stroke-width':2},gq);
    const t=mk('text',{x:q.x+14,y:q.y+4,'font-size':10.5},gq);t.textContent=o.programme.length>34?o.programme.slice(0,33)+'…':o.programme;
    hover(gq,`Activity<br>${X(o.id)}<br>${X(o.title)}${o.weight&&isMoney()?`<br><b>${valTxt(o.weight)} ${X(unit())}</b>`:''}`,()=>foc(o.country),unf);});
  pubs.forEach((p,i)=>{const y=py(i),hg=mk('g',{},N);mk('circle',{cx:70,cy:y,r:34,fill:PC[i%3],'fill-opacity':.14},hg);mk('circle',{cx:70,cy:y,r:26,fill:'#13305A',stroke:PC[i%3],'stroke-width':2},hg);
    const t=mk('text',{x:70,y:y+4,'text-anchor':'middle',style:'font:600 10px var(--mono);fill:#CFE3FF'},hg);t.textContent='ORG';
    const l=mk('text',{x:70,y:y+44,'text-anchor':'middle',class:'lbl'},hg);l.textContent=p;});
  cs.forEach((c,i)=>{const y=cy(i),r=10,g2=mk('g',{},N);mk('circle',{cx:580,cy:y,r:r+6,fill:C(c),'fill-opacity':.15},g2);mk('circle',{cx:580,cy:y,r,fill:C(c)},g2);
    const t=mk('text',{x:580+r+10,y:y+4,class:'lbl'},g2);t.textContent=c;hover(g2,`Country<br>${X(c)}`,()=>foc(c),unf);});
  function foc(k){items.forEach(i=>i.els.forEach(e=>e.style.opacity=i.k===k?1:.08));}
  function unf(){items.forEach(i=>i.els.forEach(e=>e.style.opacity=''));}};

R.rows=()=>{const v=CUR.views,tb=document.getElementById('d-rows');document.getElementById('rowsTitle').textContent=`Source rows · ${fmtN(v.rows_total||0)} evidence ids`;
  colorFor(((v.breakdowns||{}).country||[]).map(c=>c.key));
  const rows=(v.rows||[]).slice().sort((a,b)=>(a.kind==='transaction'?0:1)-(b.kind==='transaction'?0:1)||String(a.date).localeCompare(String(b.date)));
  tb.innerHTML=rows.map((r,i)=>`<tr style="transition-delay:${Math.min(i*30,600)}ms" title="${X(r.label||'')}"><td class="id">${X(r.id.replace('nodes_transactions.csv:','tx.csv:').replace('nodes_activities.csv:','act.csv:'))}</td><td>${r.country?`<span class="sw" style="background:${C(r.country)}"></span>${X(r.country)}`:''}</td><td>${X(r.date||'')}</td><td class="n">${r.value!=null?X(fmt(r.value)):''}</td></tr>`).join('')+
    (v.rows_total>rows.length?`<tr><td colspan="4" class="id">${fmtN(v.rows_total-rows.length)} more rows not shown</td></tr>`:'');
  const box=tb.closest('.reveal');if(box)box.classList.add('in');};

function tileOf(id){return document.getElementById(id).closest('.tile');}
function show(id,on){tileOf(id).classList.toggle('off',!on);}

R.factsBar=()=>{const svg=document.getElementById('d-sankey');clear(svg);const fs=(CUR.views.facts||[]).map(f=>({key:f.key,value:Number(f.value)})).filter(f=>!isNaN(f.value)).slice(0,10);
  if(!fs.length)return empty(svg,'No numeric facts');const mx=Math.max(...fs.map(f=>Math.abs(f.value)))||1,x0=200,W=720-x0-120,bh=Math.min(26,(300-20)/fs.length-8);
  fs.forEach((f,i)=>{const y=20+i*(bh+8),w=Math.abs(f.value)/mx*W;const t=mk('text',{x:x0-10,y:y+bh/2+4,'text-anchor':'end',class:'lbl'},svg);t.textContent=f.key.length>28?f.key.slice(0,27)+'…':f.key;
    const r=mk('rect',{x:x0,y,width:Math.max(w,2),height:bh,rx:4,fill:'#3987e5',style:`transform-origin:${x0}px 0;transform:scaleX(${RMv?1:0});transition:transform .9s cubic-bezier(.2,.8,.2,1) ${i*.05}s`},svg);
    requestAnimationFrame(()=>requestAnimationFrame(()=>r.style.transform='scaleX(1)'));
    const v=mk('text',{x:x0+w+8,y:y+bh/2+4,class:'val'},svg);v.textContent=fK(f.value);hover(r,`${X(f.key)}<br><b>${X(String(f.value))}</b>`);});};

let shader=null;
const PALS={money:{back:'#0A1530',colors:['#3987e5','#F2B544','#13305A','#5BA8FF']},count:{back:'#08201A',colors:['#199e70','#5BA8FF','#0F2E25','#7FE0C0']},
  date:{back:'#1E140A',colors:['#c98500','#d55181','#2A1A10','#F2B544']},zero:{back:'#101319',colors:['#3A4659','#8A96A8','#1A2230','#5BA8FF']},
  stop:{back:'#1A0F10',colors:['#FF7B72','#F2B544','#2A1416','#d55181']}};
function posterKind(a,v){if(a.status!=='answer'||a.error)return 'stop';const f=(v.facts||[])[0];if(!f)return 'stop';
  if(/^\d{4}-\d{2}-\d{2}/.test(f.value))return 'date';if(Number(f.value)===0)return 'zero';
  return (v.measure==='money'||f.key==='total'||/^[A-Z]{3}$/.test(f.key))?'money':'count';}
function shaderUniforms(p){return {u_colorBack:getShaderColorFromString(p.back),u_colors:p.colors.map(getShaderColorFromString),u_colorsCount:p.colors.length,
  u_softness:.75,u_intensity:.4,u_noise:.32,u_shape:GrainGradientShapes.corners,u_noiseTexture:getShaderNoiseTexture(),
  u_fit:ShaderFitOptions.none,u_scale:1,u_rotation:0,u_originX:.5,u_originY:.5,u_offsetX:0,u_offsetY:0,u_worldWidth:0,u_worldHeight:0};}
function nf(value,fmt){const el=document.createElement('number-flow');el.format=fmt;el.update(0);requestAnimationFrame(()=>requestAnimationFrame(()=>el.update(value)));return el;}
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
R.poster=()=>{const a=CUR.answer,v=CUR.views,k=posterKind(a,v),p=PALS[k],bg=document.getElementById('posterBg');
  try{if(!shader)shader=new ShaderMount(bg,grainGradientFragmentShader,shaderUniforms(p),undefined,RMv?0:.5);else shader.setUniforms(shaderUniforms(p));}
  catch(e){bg.style.background=`radial-gradient(circle at 20% 20%,${p.colors[0]},transparent 60%),radial-gradient(circle at 80% 70%,${p.colors[1]},transparent 55%),${p.back}`;}
  const chip={money:'answered · amount',count:'answered · count',date:'answered · date',zero:'answered · no matching rows',stop:a.status==='clarify'?'needs clarification':a.status==='abstain'?'cannot answer from this data':'could not answer'}[k];
  document.getElementById('pChip').textContent=chip;
  document.getElementById('pId').textContent='';
  const q=document.getElementById('pQ');q.textContent=a.question;if(!RMv){try{Splitting({target:q,by:'chars'});}catch(e){}}
  const num=document.getElementById('pNum'),unitEl=document.getElementById('pUnit');num.innerHTML='';
  const f=(v.facts||[])[0],tpl=D.templates.find(t=>t.name===a.tool),n=v.rows_total||0;
  const tables=Object.keys(v.evidence_by_table||{}).length?Object.entries(v.evidence_by_table).map(([t,c])=>`${t} (${fmtN(c)})`).join(', '):(v.manifest_scope||[]).join(', ');
  const cited=n?`${fmtN(n)} cited rows${tables?' from '+tables:''}.`:(v.manifest_scope||[]).length?`Computed over the full table${v.manifest_scope.length>1?'s':''}: ${v.manifest_scope.join(', ')}.`:'';
  let an='';
  if(k==='money'){num.appendChild(nf(Number(f.value),{minimumFractionDigits:2,maximumFractionDigits:2}));unitEl.textContent=(v.currency||(/^[A-Z]{3}$/.test(f.key)?f.key:''))+' · '+f.key;
    an=cited;}
  else if(k==='count'){num.appendChild(nf(Number(f.value),{maximumFractionDigits:0}));unitEl.textContent=f.key;an=cited;}
  else if(k==='date'){const [y,m,d]=f.value.slice(0,10).split('-').map(Number);const mo=document.createElement('span');mo.className='pmonth';mo.textContent=MONTHS[m-1];
    num.append(mo,nf(d,{maximumFractionDigits:0}),document.createTextNode(' '),nf(y,{useGrouping:false}));unitEl.textContent=f.key;an=cited;}
  else if(k==='zero'){num.appendChild(nf(0,{maximumFractionDigits:0}));unitEl.textContent=f.key+' · no matching rows';
    an=`No rows in the data match this question.${tables?' Searched '+tables+'.':''}`;}
  else{num.textContent=a.status==='clarify'?'?':a.status==='abstain'?'∅':'!';unitEl.textContent=(a.reasons||[]).join(' · ')||'';
    an=a.explanation||a.error||'';}
  if(tpl&&k!=='stop')an+=' '+tpl.coverage;
  document.getElementById('pAn').textContent=an.trim();
  const tk=[];
  if(a.tool)tk.push(`<button ${tpl?`data-lib="templates" data-detail="${X(a.tool)}"`:'data-lib="planner"'}><small>tool</small>${X(a.tool)}</button>`);
  tk.push(`<button data-lib="checks" data-detail="evidence"><small>evidence</small>${n?fmtN(n)+' rows':(v.manifest_scope||[]).length?'manifest scope':'none'}</button>`);
  if(a.reasons&&a.reasons.length)tk.push(`<button data-lib="checks" data-detail="reasons"><small>reason</small>${X(a.reasons.join(', '))}</button>`);
  if(a.timings&&a.timings.total_ms!=null)tk.push(`<button data-lib="planner" data-detail="retry"><small>time</small>${fmtN(Math.round(a.timings.total_ms))} ms · ${a.model_calls} LLM call${a.model_calls===1?'':'s'}</button>`);
  tk.push(`<button data-lib="schema"><small>data</small>${X(D.dataset.name)}</button>`);
  document.getElementById('pTicket').innerHTML=tk.join('');
  document.getElementById('poster').classList.add('in');};

function renderAll(res){CUR=res;const a=res.answer,v=res.views;
  const isT=D.templates.some(t=>t.name===a.tool);['howAns','howYear'].forEach(id=>{const b=document.getElementById(id);if(isT){b.dataset.lib='templates';b.dataset.detail=a.tool;}else{b.dataset.lib='planner';delete b.dataset.detail;}});
  document.getElementById('liveq').textContent=`"${a.question}"`;
  document.querySelectorAll('#exrow button').forEach(b=>b.classList.toggle('on',b.dataset.ex===a.id));
  const poster=v.layout==='poster';document.getElementById('poster').hidden=!poster;document.getElementById('bento').hidden=poster;
  if(poster){try{R.poster();}catch(e){console.error('poster',e);}return;}
  const bd=v.breakdowns||{};
  show('d-sankey',!!v.flow||(v.facts||[]).length>1);show('d-donut',!!(bd.country||[]).length);show('d-cols',!!(bd.year||[]).length);
  show('d-graph',!!(v.graph&&v.graph.activities.length));show('d-rows',!!(v.rows||[]).length);
  const fl=tileOf('d-sankey').querySelector('h4');fl.textContent=v.flow?'Publisher → programme → country':'Answer by key';
  ['answer','donut','cols','term','graph','rows'].forEach(k=>{try{R[k]();}catch(e){console.error(k,e);}});
  try{v.flow?R.flow():R.factsBar();}catch(e){console.error('flow',e);}}
const ob=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)e.target.classList.add('in');}),{threshold:.12});
document.querySelectorAll('.reveal').forEach(n=>ob.observe(n));
const form=document.getElementById('askform'),inp=document.getElementById('askin'),msg=document.getElementById('askmsg');
const EX=D.examples||{};const exampleId=EX.Q12?'Q12':Object.keys(EX)[0];
let liveOK=false;
async function submitAsk(q){if(!q||q.length<3)return;
  if(!liveOK){msg.textContent='Live questions are available when the answer service is connected. Showing a benchmark example.';
    const hit=Object.values(EX).find(e=>e.answer.question.toLowerCase()===q.toLowerCase());renderAll(hit||EX[exampleId]);document.getElementById('live').scrollIntoView();return;}
  msg.textContent='Thinking…';form.classList.add('busy');
  try{const res=await API.ask({question:q});res.answer.question=q;renderAll(res);msg.textContent='';document.getElementById('live').scrollIntoView();}
  catch(e){msg.textContent='The answer service returned an error: '+e.message;}
  finally{form.classList.remove('busy');}}
form.addEventListener('submit',e=>{e.preventDefault();typing=false;submitAsk(inp.value.trim());});
let typing=!RMv;
inp.addEventListener('focus',()=>{if(typing){typing=false;inp.value='';}});
(function(){const qs=Object.values(EX).map(e=>e.answer.question);if(!qs.length)return;let i=0,j=0,del=false;inp.value=RMv?qs[0]:'';
  (function step(){if(!typing)return;const q=qs[i];if(!del){j++;inp.value=q.slice(0,j);if(j===q.length){del=true;return setTimeout(step,2200);}}
    else{j-=3;inp.value=q.slice(0,Math.max(j,0));if(j<=0){del=false;j=0;i=(i+1)%qs.length;}}setTimeout(step,del?14:36);})();})();

API.meta().then(m=>{liveOK=true;const l=document.getElementById('srcLabel');if(l&&m.dataset)l.textContent=`Data: ${m.dataset.label}${m.dataset.activities?', '+fmtN(m.dataset.activities)+' activities':''}`;}).catch(()=>{liveOK=false;});
document.getElementById('exrow').innerHTML=Object.entries(EX).map(([id,e])=>`<button data-ex="${X(id)}">${X(e.answer.question.length>46?e.answer.question.slice(0,45)+'…':e.answer.question)}</button>`).join('');
document.querySelectorAll('#exrow button').forEach(b=>b.onclick=()=>renderAll(EX[b.dataset.ex]));
renderAll(EX[exampleId]);
const links=[...document.querySelectorAll('#navlinks a')],bar=document.getElementById('navbar');
function moveBar(a){if(!a){bar.style.opacity=0;return;}const p=a.parentElement.getBoundingClientRect(),r=a.getBoundingClientRect();bar.style.opacity=1;bar.style.left=(r.left-p.left+10)+'px';bar.style.width=(r.width-20)+'px';}
const secs=links.map(a=>document.getElementById(a.dataset.sec));
function onScroll(){const y=scrollY+innerHeight*.35;let c=links[0];secs.forEach((s,i)=>{if(s&&s.offsetTop<=y)c=links[i];});
  links.forEach(a=>a.classList.toggle('on',a===c));moveBar(c);
  const h=document.documentElement.scrollHeight-innerHeight;document.getElementById('prog').style.width=(h>0?scrollY/h*100:0)+'%';}
addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',onScroll);onScroll();
const lb=document.getElementById('libbtn'),lm=document.getElementById('libmenu');
const LM=[['planner','Planner','prompt'],['resolver','Resolver',D.groups.length+' groups'],['templates','Templates',String(D.templates.length)],['tools','Retrieval tools',String(D.tools.length)],['checks','Checks and guard','4'],['schema','Graph schema',Object.values(D.schema.nodes).filter(v=>v).length+' labels']];
lm.innerHTML=LM.map(([k,t,s])=>`<button data-lib="${k}">${t}<span>${s}</span></button>`).join('');
lb.onclick=e=>{e.stopPropagation();lm.hidden=!lm.hidden;lb.setAttribute('aria-expanded',!lm.hidden);};
document.addEventListener('click',e=>{if(!lm.hidden&&!lm.contains(e.target)&&e.target!==lb){lm.hidden=true;lb.setAttribute('aria-expanded','false');}});
lm.addEventListener('click',()=>{lm.hidden=true;});
