/* ── Static JSON data layer ── */
const DATA_BASE='data/';
const _cache={};
async function fetchJSON(path){
  if(_cache[path])return _cache[path];
  const resp=await fetch(DATA_BASE+path);
  if(!resp.ok)throw new Error('Failed to load '+path+': '+resp.status);
  const data=await resp.json();
  _cache[path]=data;
  return data;
}

/* ── loadSection: fetch JSON, show skeleton while loading, error+retry on failure ── */
async function loadSection(elementId,jsonPath,renderFn){
  const el=$(elementId);if(!el)return;
  el.innerHTML='<div class="card">'+skeleton(3)+'</div>';
  try{
    const data=await fetchJSON(jsonPath);
    renderFn(data,el);
  }catch(e){
    console.warn('Failed to load '+jsonPath+':',e);
    el.innerHTML='<div class="card" style="padding:18px;text-align:center">'+
      '<div style="color:var(--status-red);font-size:var(--text-sm);margin-bottom:8px">Could not load data</div>'+
      '<button onclick="loadSection(\''+elementId+'\',\''+jsonPath+'\','+renderFn.name+')" '+
      'style="padding:6px 16px;border:1px solid var(--border-light);border-radius:var(--radius-sm);'+
      'background:var(--bg-subtle);color:var(--text-primary);cursor:pointer;font-size:var(--text-xs)">Retry</button></div>';
  }
}
window.loadSection=loadSection;

/* ── Helpers ── */
function hasVal(v){return v!=null&&v!==''&&v!=='N/A'&&v!=='\u2014'&&v!=='—'&&v!=='n/a'}
function pick(){for(let i=0;i<arguments.length;i++){if(hasVal(arguments[i]))return arguments[i]}return 'N/A'}
function fmtPeriod(dateStr){if(!dateStr)return '';try{const d=new Date(dateStr+'T00:00:00');if(isNaN(d))return dateStr;return d.toLocaleDateString('en-CA',{month:'short',year:'numeric'})}catch(e){return dateStr}}
function indBasis(rec,metaPeriod,freq){const p=pick(metaPeriod,rec&&rec.period);const dt=hasVal(p)?fmtPeriod(p):'';const f=freq||rec&&rec.frequency||'';const fLabel=f?f.charAt(0).toUpperCase()+f.slice(1):'';return dt||(fLabel||'')}
function indSource(rec,fallback){return (rec&&rec.source)||fallback||''}
function fmtNum(v){if(v==null||v==='N/A'||v==='\u2014'||v==='')return v;const s=String(v).replace(/,/g,'');const m=s.match(/^([+\-]?)(\$?)(\d[\d]*\.?\d*)(.*)/);if(!m)return String(v);const sign=m[1],prefix=m[2],num=parseFloat(m[3]),suffix=m[4];if(isNaN(num))return String(v);const rounded=num%1===0&&num>=1000?num.toFixed(0):num.toFixed(1);const parts=rounded.split('.');parts[0]=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',');if(parts[1]==='0'&&num>=1000)return sign+prefix+parts[0]+suffix;return sign+prefix+parts.join('.')+suffix}
// Compute period-over-period change from indicator history array
let _indHistory=null;
function _getHistory(){if(_indHistory)return _indHistory;try{const d=_cache['indicators.json'];_indHistory=(d&&d.history)||[]}catch(e){_indHistory=[]}return _indHistory}
function _parseNum(v){if(v==null)return NaN;const s=String(v).replace(/[,%+$]/g,'').trim();return parseFloat(s)}
// Province code <-> name map for history matching
const _provAlias={bc:'british columbia',ab:'alberta',sk:'saskatchewan',mb:'manitoba',on:'ontario',qc:'quebec',nb:'new brunswick',ns:'nova scotia',pe:'prince edward island',nl:'newfoundland and labrador',yt:'yukon',nt:'northwest territories',nu:'nunavut'};
const _provReverse={};Object.entries(_provAlias).forEach(([k,v])=>{_provReverse[v]=k});
function _matchProv(recProv,target){
  if(!target)return (recProv||'')==='national'||(recProv||'')==='';
  const rp=(recProv||'').toLowerCase(),tp=target.toLowerCase();
  if(rp===tp)return true;
  if(_provAlias[rp]===tp||_provAlias[tp]===rp)return true;
  if(_provReverse[rp]===tp||_provReverse[tp]===rp)return true;
  return false;
}
function computeChange(indName,prov){
  // Check if the indicator record itself has a pre-computed change
  const rec=indicators.find(x=>x.indicator_name===indName&&_matchProv(x.province,prov));
  if(rec&&hasVal(rec.change))return rec.change;
  // Check D.indicatorMeta (briefing-level pre-computed changes)
  if(D&&D.indicatorMeta&&D.indicatorMeta[indName]&&hasVal(D.indicatorMeta[indName].change))return D.indicatorMeta[indName].change;
  const h=_getHistory();
  const match=h.filter(x=>x.indicator_name===indName&&_matchProv(x.province,prov));
  if(!match.length)return '';
  match.sort((a,b)=>(a.period||'').localeCompare(b.period||''));
  // Find two most recent distinct numeric values of similar magnitude
  // (skip mixed-unit data: e.g. CPI index 165 vs CPI YoY% 2.3)
  const seen=new Set();const distinct=[];
  for(let i=match.length-1;i>=0&&distinct.length<2;i--){
    const n=_parseNum(match[i].value);
    if(isNaN(n))continue;
    const k=n.toFixed(4);
    if(seen.has(k))continue;
    // If we have a first value, reject the second if magnitude differs >10x (mixed units)
    if(distinct.length===1){
      const ratio=Math.abs(distinct[0])>0?Math.abs(n)/Math.abs(distinct[0]):999;
      if(ratio>10||ratio<0.1)continue;
    }
    seen.add(k);distinct.push(n);
  }
  if(distinct.length<2)return '';
  const curr=distinct[0],prev=distinct[1],diff=curr-prev;
  // Determine display format from the value itself:
  // Rates and percentages (<100 absolute) → show as pp change
  // Large values (GDP levels, index levels) → show as % change
  const isRate=Math.abs(curr)<100&&Math.abs(prev)<100;
  if(isRate){return (diff>=0?'+':'')+diff.toFixed(1)+'pp'}
  const pct=prev!==0?((diff/Math.abs(prev))*100):0;
  return (pct>=0?'+':'')+pct.toFixed(1)+'%';
}

/* ── State ── */
let D=null,indicators=[],allProjects=[],filteredProjects=[],projectPage=0,selectedProvince='BC',tsCache={},charts={},tabRendered={};
const PAGE_SIZE=25;
let _confirmedOnly=true;
const _MONTHS_SHORT={jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11};
function parseEvtDate(d){if(!d)return null;if(d.includes('-')&&d.length>=8)return new Date(d+'T00:00:00');const parts=d.trim().split(/\s+/);const yr=new Date().getFullYear();if(parts.length>=2){const m=_MONTHS_SHORT[(parts[0]||'').toLowerCase().slice(0,3)];if(m!=null)return new Date(yr,m,parseInt(parts[1])||1)}return null;}
let _lastLoadedProvince=null,_loadSeq=0;
const PROVS=[{code:'BC',name:'British Columbia'},{code:'AB',name:'Alberta'},{code:'SK',name:'Saskatchewan'},{code:'MB',name:'Manitoba'},{code:'ON',name:'Ontario'},{code:'QC',name:'Quebec'},{code:'NB',name:'New Brunswick'},{code:'NS',name:'Nova Scotia'},{code:'PE',name:'Prince Edward Island'},{code:'NL',name:'Newfoundland and Labrador'},{code:'YT',name:'Yukon'},{code:'NT',name:'Northwest Territories'},{code:'NU',name:'Nunavut'}];
const NAME_TO_CODE={};PROVS.forEach(p=>{NAME_TO_CODE[p.name]=p.code;NAME_TO_CODE[p.code]=p.code});NAME_TO_CODE['Newfoundland']='NL';NAME_TO_CODE['PEI']='PE';
const PROV_SLUGS={};PROVS.forEach(p=>{PROV_SLUGS[p.code]=p.name.toLowerCase().replace(/ /g,'_')});
function normProvince(raw){if(!raw)return '';return NAME_TO_CODE[raw.trim()]||raw.substring(0,2).toUpperCase()}
const PROV_THRESHOLDS={'ON':500e6,'QC':250e6,'AB':200e6,'BC':175e6,'SK':45e6,'MB':40e6,'NS':25e6,'NB':20e6,'NL':17e6,'PE':5e6,'YT':3e6,'NT':3e6,'NU':3e6};
function meetsThreshold(p){const v=parseNumericValue(p.value);if(!v)return false;const t=PROV_THRESHOLDS[normProvince(p.province)]||0;return v>=t}
const PROV_IMGS={BC:'https://images.unsplash.com/photo-1503614472-8c93d56e92ce?w=1200&q=80',AB:'https://images.unsplash.com/flagged/photo-1556669546-b1f29875df1c?w=1200&q=80',SK:'https://images.unsplash.com/photo-1753081490091-37ce36d8bbd8?w=1200&q=80',MB:'https://images.unsplash.com/photo-1591658522986-9eb791d2a89a?w=1200&q=80',ON:'https://images.unsplash.com/photo-1517935706615-2717063c2225?w=1200&q=80',QC:'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=1200&q=80',NB:'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1200&q=80',NS:'https://images.unsplash.com/photo-1565465685025-9b00dc77ad52?w=1200&q=80',PE:'https://images.unsplash.com/photo-1756845405231-dce993817876?w=1200&q=80',NL:'https://images.unsplash.com/photo-1483599345082-521b252854ff?w=1200&q=80',YT:'https://images.unsplash.com/photo-1494500764479-0c8f2919a3d8?w=1200&q=80',NT:'https://images.unsplash.com/photo-1579033461380-adb47c3eb938?w=1200&q=80',NU:'https://images.unsplash.com/photo-1589656966895-2f33e7653819?w=1200&q=80'};
const NAICS_CODES=['11','21','22','23','31-33','41','44-45','48-49','51','52','53','54','55','56','61','62','71','72','81','91'];
const NAICS_NAMES={'11':'Agriculture','21':'Mining, Oil & Gas','22':'Utilities','23':'Construction','31-33':'Manufacturing','41':'Wholesale Trade','44-45':'Retail Trade','48-49':'Transportation','51':'Information & Cultural','52':'Finance & Insurance','53':'Real Estate','54':'Professional Services','55':'Management','56':'Administrative & Support','61':'Education','62':'Health Care','71':'Arts & Recreation','72':'Accommodation & Food','81':'Other Services','91':'Public Administration'};
const NAICS_CLS={'11':'s-agriculture','21':'s-mining','22':'s-utilities','23':'s-construction','31-33':'s-manufacturing','41':'s-trade','44-45':'s-trade','48-49':'s-transport','51':'s-info','52':'s-finance','53':'s-realestate','54':'s-professional','55':'s-admin','56':'s-admin','61':'s-education','62':'s-health','71':'s-arts','72':'s-accommodation','81':'s-other','91':'s-public'};
const STATUSES=['Proposed','Under Review','Approved','Under Construction','Paused','Expansion','Operational','Completed','Cancelled'];
/* Project type config */
const PROJ_TYPE_CFG={
greenfield:{label:'New Build',cls:'type-greenfield',cat:'Greenfield'},
redevelopment:{label:'Redevelopment',cls:'type-brownfield',cat:'Brownfield'},
adaptive_reuse:{label:'Adaptive Reuse',cls:'type-brownfield',cat:'Brownfield'},
major_renovation:{label:'Renovation',cls:'type-brownfield',cat:'Brownfield'},
expansion:{label:'Expansion',cls:'type-expansion',cat:'Brownfield'},
retrofit:{label:'Retrofit',cls:'type-brownfield',cat:'Brownfield'},
restoration:{label:'Restoration',cls:'type-restoration',cat:'Brownfield'},
remediation:{label:'Remediation',cls:'type-remediation',cat:'Brownfield'},
conversion:{label:'Conversion',cls:'type-brownfield',cat:'Brownfield'},
modernization:{label:'Modernization',cls:'type-expansion',cat:'Brownfield'},
decommission_replace:{label:'Replacement',cls:'type-replace',cat:'Brownfield'},
};
function typeBadge(pt){const c=PROJ_TYPE_CFG[pt]||PROJ_TYPE_CFG.greenfield;return'<span class="type-badge '+c.cls+'">'+c.label+'</span>'}
function confBadge(conf,evCount){if(conf==null)return'';const pct=Math.round(conf*100);const cls=pct>=70?'conf-high':pct>=40?'conf-mid':'conf-low';return'<span class="'+cls+'" title="'+evCount+' source(s)">'+pct+'%'+(evCount?(' ('+evCount+' src'+(evCount>1?'s':'')+')'):'')+'</span>'}

/* ── Helpers ── */
const $=id=>document.getElementById(id);
const san=h=>DOMPurify.sanitize(h||'',{ADD_ATTR:['target']});
function linkFootnotes(html,sources){if(!html||!sources||!sources.length)return html||'';return html.replace(/<sup>(\d+)<\/sup>/g,(m,n)=>{const idx=parseInt(n,10)-1;const s=sources[idx];if(!s)return m;const url=s.url||s.archive_url||'';const title=(s.title||'Source').replace(/"/g,'&quot;');return url?`<a href="${url}" target="_blank" title="${title}" style="color:var(--accent);text-decoration:none"><sup>${n}</sup></a>`:`<sup title="${title}">${n}</sup>`})}
function fmtDate(iso){if(!iso)return'';try{const d=new Date(iso+'T00:00:00');return d.toLocaleDateString('en-CA',{month:'short',day:'numeric',year:'numeric'})}catch{return iso}}
function relDate(iso){if(!iso)return'';const ms=Date.now()-new Date(iso+'T00:00:00').getTime(),d=Math.floor(ms/864e5);if(d<1)return'Today';if(d<7)return d+'d ago';if(d<30)return Math.floor(d/7)+'w ago';return Math.floor(d/30)+'mo ago'}
function changeCls(arrow){return arrow===1?'change-up':arrow===2?'change-down':'change-flat'}
function changeIcon(arrow){return arrow===1?'↑':arrow===2?'↓':'→'}
function stCls(s){const k=s.toLowerCase().replace(/\s+/g,'-');return'st-'+k}
function statusBadge(s){return`<span class="status-badge ${stCls(s)}">${s}</span>`}
function confMeter(conf){if(conf==null)return'';const n=Math.round(conf*5);const cls=conf>=0.7?'high':'';let h='<span class="conf-meter" title="Confidence: '+(conf*100).toFixed(0)+'%">';for(let i=0;i<5;i++)h+='<span class="conf-meter-dot'+(i<n?' filled'+(cls?' '+cls:''): '')+'"></span>';return h+'</span> '+(conf*100).toFixed(0)+'%'}
function buildTimeline(p){const ann=p.announcement_date||p.firstTracked||'';const start=p.start_date||'';const end=p.completionDate||'';if(!ann&&!start&&!end)return'';const STATUS_COLORS={Proposed:'proposed','Under Review':'proposed',Approved:'approved','Under Construction':'construction','Partially Complete':'construction',Complete:'complete',Cancelled:'proposed','On Hold':'hold'};const now=new Date();const d=s=>{if(!s)return null;const dt=new Date(s+'T00:00:00');return isNaN(dt)?null:dt};const dAnn=d(ann);const dStart=d(start);const dEnd=d(end);const earliest=dAnn||dStart||now;const latest=dEnd||new Date(now.getTime()+365*86400000);const span=Math.max(latest-earliest,86400000);const pct=dt=>dt?Math.max(0,Math.min(100,((dt-earliest)/span)*100)):null;const nowPct=pct(now);let bar='<div style="margin-bottom:10px"><div class="proj-timeline">';const segColor=STATUS_COLORS[p.status]||'proposed';bar+='<div class="proj-timeline-seg '+segColor+'" style="width:100%"></div>';if(nowPct!==null&&nowPct>0&&nowPct<100)bar+='<div class="proj-timeline-marker" style="left:'+nowPct+'%"></div>';bar+='</div><div class="proj-timeline-dates">';bar+='<span>'+(ann?fmtDateShort(ann):(p.firstTracked?'Disc. '+fmtDateShort(p.firstTracked):''))+'</span>';if(start)bar+='<span>Start: '+fmtDateShort(start)+'</span>';if(end)bar+='<span>End: '+fmtDateShort(end)+'</span>';bar+='</div></div>';return bar}
function fmtDateShort(s){if(!s)return'';const parts=s.split('-');if(parts.length<2)return s;const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];return months[parseInt(parts[1])-1]+' '+parts[0]}
function srcLink(url,title){if(!url)return'';return`<a href="${url}" target="_blank" rel="noopener noreferrer" title="${title||'Source'}">\u2197</a>`}
function fmtNumeric(n,d){if(typeof n!=='number'||isNaN(n))return String(n);const dec=d!=null?d:(Math.abs(n)>=100?0:Math.abs(n)>=1?1:2);return n.toLocaleString('en-CA',{minimumFractionDigits:dec,maximumFractionDigits:dec})}
function fmtVal(v){if(!v||v==='N/A'||v==='Not disclosed')return'<span style="color:#556B7A">N/D</span>';return v}
function parseNumericValue(v){if(!v)return 0;const s=String(v).toUpperCase();const m=s.match(/([\d.]+)\s*(B|M|K)?/);if(!m)return 0;let n=parseFloat(m[1])||0;if(m[2]==='B')n*=1e9;else if(m[2]==='M')n*=1e6;else if(m[2]==='K')n*=1e3;return n}
function fmtCurrency(v,p){if(!v||v==='—'||v==='N/A'||v==='Not disclosed'){if(p&&p.cost_unfindable)return'<span style="color:#556B7A;font-style:italic" title="Cost not publicly available after 3 search attempts">N/A</span>';if(p&&p.cost_search_attempts>0)return'<span style="color:#556B7A;font-style:italic" title="Searching for value (attempt '+p.cost_search_attempts+'/3)">Searching\u2026</span>';return'<span style="color:#556B7A">N/D</span>'}let out='';if(typeof v==='string'&&v.match(/\$[\d.]+[BMK]/i))out=v;else{const n=parseNumericValue(v);if(!n)out=String(v);else if(n>=1e9)out='$'+(n/1e9).toFixed(1)+'B';else if(n>=1e6)out='$'+(n/1e6).toFixed(0)+'M';else if(n>=1e3)out='$'+(n/1e3).toFixed(0)+'K';else out='$'+n.toLocaleString()}if(p&&p.value_low_millions&&p.value_high_millions)out+='<span style="color:#556B7A;font-size:10px;margin-left:3px" title="Range: $'+Math.round(p.value_low_millions)+'M\u2013$'+Math.round(p.value_high_millions)+'M">*</span>';if(p&&p.value_notes)out+='<span style="color:#556B7A;font-size:10px;margin-left:2px" title="'+p.value_notes.replace(/"/g,"&quot;")+'">\u2020</span>';return out}
function _normSector(s){if(!s)return'';const _SECTOR_MAP={'oil_gas':'Oil & Gas','power_energy':'Power & Energy','transport_logistics':'Transport & Logistics','commercial_mixed':'Commercial & Mixed Use','tourism_culture':'Tourism & Culture','infrastructure':'Infrastructure','healthcare':'Healthcare','education':'Education','residential':'Residential','manufacturing':'Manufacturing','mining':'Mining','agriculture':'Agriculture','forestry':'Forestry','defence':'Defence','telecom':'Telecommunications','indigenous':'Indigenous','environment':'Environment','government':'Government'};if(_SECTOR_MAP[s])return _SECTOR_MAP[s];return s.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()).substring(0,25)}
function skeleton(n=3){return Array(n).fill('<div class="skeleton sk-line"></div><div class="skeleton sk-line med"></div><div class="skeleton sk-line short"></div>').join('')}

/* ── Tab Switching ── */
function switchTab(tabId){
  document.querySelectorAll('.nav-tab').forEach(t=>{
    const isActive=t.dataset.tab===tabId;
    t.classList.toggle('active',isActive);
    t.setAttribute('aria-selected',isActive?'true':'false');
    t.setAttribute('tabindex',isActive?'0':'-1');
  });
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.id==='tab-'+tabId));
  if(!tabRendered[tabId]){renderTab(tabId);tabRendered[tabId]=true}
}
document.querySelectorAll('.nav-tab').forEach(t=>{
  t.addEventListener('click',()=>switchTab(t.dataset.tab));
  t.addEventListener('keydown',e=>{
    const tabs=[...document.querySelectorAll('.nav-tab')];
    const idx=tabs.indexOf(t);
    let target=-1;
    if(e.key==='ArrowRight'||e.key==='ArrowDown')target=(idx+1)%tabs.length;
    else if(e.key==='ArrowLeft'||e.key==='ArrowUp')target=(idx-1+tabs.length)%tabs.length;
    else if(e.key==='Home')target=0;
    else if(e.key==='End')target=tabs.length-1;
    else if(e.key==='Enter'||e.key===' '){e.preventDefault();switchTab(t.dataset.tab);return}
    if(target>=0){e.preventDefault();tabs[target].focus();switchTab(tabs[target].dataset.tab)}
  });
});

/* ── Data Loading ── */
let currentEdition='latest';
async function loadNewsletter(editionId){
  try{
    if(editionId&&editionId!=='latest'){
      // Try edition-specific file first
      try{D=await fetchJSON('briefing_'+editionId+'.json')}
      catch(e2){console.warn('Edition file not found, falling back to latest:',e2);D=await fetchJSON('briefing_latest.json')}
    }else{
      D=await fetchJSON('briefing_latest.json');
    }
  }
  catch(e){console.error('Newsletter load:',e)}
}
async function loadEditionList(){
  try{
    const archive=await fetchJSON('briefing_archive.json');
    const editions=(archive||[]).map(e=>({id:e.week_of||'',edition:e.headline||'',date:e.generated_at||e.week_of||''}));
    const list=$('editionList');
    list.innerHTML=editions.map(e=>{
      const label=(e.edition||'').replace(/EDITION:\s*/i,'').split('//')[0].trim()||e.id;
      const active=e.id===currentEdition?'font-weight:700;background:#e2e8f0;':'';
      return'<div class="edition-item" data-id="'+e.id+'" style="padding:8px 14px;font-size:var(--text-xs);cursor:pointer;border-bottom:1px solid rgba(0,0,0,0.06);color:#1a2744;'+active+'">'+label+'</div>';
    }).join('');
    list.querySelectorAll('.edition-item').forEach(el=>el.addEventListener('click',()=>switchEdition(el.dataset.id)));
  }catch(e){console.warn('Edition list load:',e)}
}
async function switchEdition(editionId){
  currentEdition=editionId;
  $('editionList').style.display='none';
  $('navMeta').textContent='Loading...';
  tabRendered={};
  Object.values(charts).forEach(c=>{if(c&&c.destroy)c.destroy()});charts={};
  await loadNewsletter(editionId);
  try{await renderTab('tldr');tabRendered.tldr=true}catch(e){console.error('renderTLDR:',e)}
  const edStr=D?(D.edition||D.headline||'').replace(/EDITION:\s*/i,'').split('//')[0].trim():'';
  $('navMeta').textContent=edStr||'Latest Edition';
  const activeTab=document.querySelector('.nav-tab.active');
  if(activeTab&&activeTab.dataset.tab!=='tldr'){renderTab(activeTab.dataset.tab);tabRendered[activeTab.dataset.tab]=true}
  loadEditionList();
}
let _indJsonCache=null;
async function loadIndicators(){
  try{
    const data=await fetchJSON('indicators.json');
    _indJsonCache=data;
    const raw=(data&&data.indicators)||data||[];
    // Normalize: SQLite uses indicator_name, frontend uses name
    indicators=raw.map(ind=>{
      const name=ind.name||ind.indicator_name||'';
      const displayName=name.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
      return Object.assign({},ind,{
        name:displayName,
        indicator_name:ind.indicator_name||name,
        refPer:ind.refPer||ind.period||'',
        category:ind.category||categorizeIndicator(displayName)
      });
    });
    // Deduplicate: keep latest by indicator_name + province
    const seen={};
    indicators=indicators.filter(ind=>{
      const key=(ind.indicator_name||'')+'|'+(ind.province||'');
      if(!key||key==='|')return true;
      if(seen[key])return false;
      seen[key]=true;return true;
    });
  }catch(e){console.error('Indicators load:',e)}
}
async function loadProjects(province){
  const seq=++_loadSeq;
  _lastLoadedProvince=province||null;
  try{
    let data;
    if(province){
      const slug=PROV_SLUGS[province]||province.toLowerCase().replace(/ /g,'_');
      data=await fetchJSON('projects_'+slug+'.json');
    }else{
      data=await fetchJSON('projects_all.json');
    }
    if(seq!==_loadSeq)return; // race guard
    allProjects=Array.isArray(data)?data:[];
    allProjects.sort((a,b)=>(b.lastSeen||'').localeCompare(a.lastSeen||''));
    filteredProjects=[...allProjects];
  }catch(e){
    console.error('Projects load:',e);
    allProjects=[];filteredProjects=[];
  }
}
async function loadTimeseries(docId){
  if(tsCache[docId])return tsCache[docId];
  try{
    const all=await fetchJSON('timeseries.json');
    let raw=all[docId];
    if(raw){
      // Normalize: wrap flat array into {series:[...]} if needed
      const ts=Array.isArray(raw)?{series:raw}:raw;
      tsCache[docId]=ts;return ts;
    }
  }catch(e){console.warn('TS load:',e)}
  return null;
}
async function loadAll(){
  try{
    await Promise.all([loadNewsletter(),loadIndicators()]);
  }catch(e){console.error('loadAll data fetch:',e)}
  try{
    await renderTab('tldr');tabRendered.tldr=true;
  }catch(e){
    console.error('renderTLDR:',e);
    const tp=$('tldrPage');if(tp)tp.innerHTML='<div class="tldr-empty">Error rendering: '+e.message+'</div>';
  }
  const edStr=D?(D.edition||D.headline||'').replace(/EDITION:\s*/i,'').split('//')[0].trim():'';
  $('navMeta').textContent=edStr||((indicators.length)?indicators.length+' indicators loaded':'Data loaded');
  $('footerDate').textContent=D&&D.updated_at?'Last pipeline run: '+fmtDate(D.updated_at):(indicators.length?'Live indicator data loaded':'Awaiting first pipeline run');
  // Header date badge
  const heroDate=$('heroDate');
  if(heroDate){
    const briefingDate=D&&(D.week_of||D.updated_at||D.date);
    if(briefingDate){
      const dt=new Date(briefingDate+'T00:00:00');
      heroDate.textContent='Week of '+dt.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
    }else{
      heroDate.textContent=new Date().toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
    }
  }
  // Header freshness
  const freshEl=$('headerFreshness');
  if(freshEl&&D&&D.updated_at){freshEl.textContent='Data as of '+fmtDate(D.updated_at)}
  loadEditionList();
}
/* Edition dropdown toggle */
$('editionBtn').addEventListener('click',e=>{e.stopPropagation();const list=$('editionList');list.style.display=list.style.display==='none'?'block':'none'});
document.addEventListener('click',()=>{$('editionList').style.display='none'});
$('editionList').addEventListener('click',e=>e.stopPropagation());

/* ── Render Router ── */
async function renderTab(id){
  switch(id){
    case'tldr':await renderTLDR();break;
    case'national':renderNational();addDataVintage();break;
    case'provinces':renderProvinces();break;
    case'industries':renderIndustries();break;
    case'markets':renderMarkets();break;
    case'projects':renderProjectsTab();break;
    case'calendar':renderCalendar();break;
    case'explorer':renderExplorer();break;
  }
}

/* ── Sources Footer Helper ── */
function sourcesFooter(sources,containerId){
  if(!sources||!sources.length)return'';
  let html=`<div class="sources-toggle" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('open')">Sources (${sources.length}) <span class="chevron">▾</span></div>`;
  html+='<div class="sources-list">';
  sources.forEach((s,i)=>{
    const url=s.url||s.archive_url||'';
    const title=s.title||'Source';
    const verified=s.verified_date?` · Verified ${fmtDate(s.verified_date)}`:'';
    const archive=s.archive_url?` <a href="${s.archive_url}" target="_blank">[Archived]</a>`:'';
    html+=`<div>[${i+1}] ${url?`<a href="${url}" target="_blank">${title} \u2197</a>`:title}${archive}${verified}</div>`;
  });
  return html+'</div>';
}

/* ── Lead image helper ── */
function findLeadImage(sources){
  if(!sources||!sources.length)return '';
  for(const s of sources){if(s.image_url)return s.image_url}
  return '';
}
function leadImageHtml(sources,float){
  const img=findLeadImage(sources);
  if(!img)return '';
  const side=float==='right'?'right':'left';
  const margin=side==='right'?'0 0 12px 20px':'0 20px 12px 0';
  return `<img src="${img}" alt="" style="float:${side};max-width:280px;width:40%;border-radius:var(--radius-md);margin:${margin};object-fit:cover;max-height:200px" onerror="this.style.display='none'" loading="lazy">`;
}

/* ══ TL;DR TAB (Prussian Blue Redesign) ══ */
let _editorialMode=false;
async function renderTLDR(){
  _editorialMode=true;
  const page=$('tldrPage');
  if(!page)return;

  if(!D||!D.executive_summary){
    page.innerHTML='<div class="tldr-empty">Weekly briefing pending. '+indicators.length+' indicators loaded from primary sources.</div>';
    return;
  }

  // Headline
  let headline=(D.headline||'').trim();
  if(!headline||/^\d|^[A-Z]{3}\s\d/.test(headline)){
    const tmp=document.createElement('div');tmp.innerHTML=D.executive_summary||'';
    const firstLi=tmp.querySelector('li');
    const rawText=firstLi?firstLi.textContent.trim():(tmp.textContent||'').trim();
    const firstSentence=(rawText.split(/[.!]\s/)[0]||'').replace(/\d+$/,'').trim();
    headline=firstSentence.length>90?firstSentence.substring(0,87).replace(/\s\S*$/,'')+'...':firstSentence;
    if(!headline)headline='Weekly Summary';
  }

  // Date
  const weekOf=D.week_of||'';
  let dateDisplay='';
  if(weekOf){try{const dt=new Date(weekOf+'T00:00:00');dateDisplay=dt.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})+', 5:45 AM ET'}catch(e){dateDisplay=weekOf}}

  // Key Indicators table
  const kiHtml=_tldrBuildIndicatorTable();
  // Markets table
  const mkHtml=_tldrBuildMarketsTable();
  // Briefing narrative
  const briefingHtml=_tldrBuildBriefing();
  // Policy section
  const policyHtml=await _tldrBuildPolicy();
  // Project pipeline
  const projectsHtml=await _tldrBuildProjects();

  // "This Week's Key Data" table (commodities + notable items)
  const weeklyDataHtml=_tldrBuildWeeklyDataTable();

  page.innerHTML=`
    <div class="tldr-headline-band fade-in">
      <h2>${san(headline)}</h2>
      <div class="tldr-headline-meta"><span>${dateDisplay}</span></div>
    </div>

    <details class="tldr-glance">
      <summary>Numbers at a Glance</summary>
      <div class="tldr-glance-body">
        <div class="tldr-toggle-row">
          <span class="tldr-glance-label">Canada \u2014 National</span>
          <div class="tldr-toggle" id="tldrGlanceToggle">
            <button class="active" data-view="indicators">Key Indicators</button>
            <button data-view="markets">Markets</button>
          </div>
        </div>
        <div id="tldrIndicatorsView">${kiHtml}</div>
        <div id="tldrMarketsView" style="display:none">${mkHtml}</div>
        ${weeklyDataHtml}
      </div>
    </details>

    ${briefingHtml}
    ${policyHtml}
    ${projectsHtml}`;

  // Wire up toggle
  const tog=$('tldrGlanceToggle');
  if(tog){tog.querySelectorAll('button').forEach(btn=>{btn.addEventListener('click',()=>{
    tog.querySelectorAll('button').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    const v=btn.dataset.view;
    $('tldrIndicatorsView').style.display=v==='indicators'?'':'none';
    $('tldrMarketsView').style.display=v==='markets'?'':'none';
  })})}
  // Render callout charts async
  setTimeout(function(){_tldrRenderCalloutCharts()},100);
}
function bulletsToParas(html){
  if(!html)return'';
  return html.replace(/<ul[^>]*>/gi,'').replace(/<\/ul>/gi,'').replace(/<li>/gi,'<p>').replace(/<\/li>/gi,'</p>');
}

/* ── TL;DR: Key Indicators table ── */
function _tldrBuildIndicatorTable(){
  const ki=D.key_indicators||[];
  const meta=D.indicatorMeta||{};
  const metaKeys=['bocRate','realGdp','cpi','unemployment','housingStarts','tradeBalance','retailSales','consumerConfidence'];
  const labelMap={'BOC RATE':'bocRate','REAL GDP':'realGdp','CPI':'cpi','UNEMPLOYMENT':'unemployment',
    'HOUSING STARTS':'housingStarts','TRADE BALANCE':'tradeBalance','RETAIL SALES':'retailSales',
    'CONSUMER CONFIDENCE':'consumerConfidence','PARTICIPATION':'participation','EMPLOYMENT CHANGE':'employmentChange',
    'WAGE GROWTH':'wageGrowth','PARTICIPATION RATE':'participation','EMPLOYMENT':'employmentChange'};
  const freqMap={'bocRate':'8x/year','realGdp':'Monthly','cpi':'Monthly','unemployment':'Monthly',
    'housingStarts':'Monthly','tradeBalance':'Monthly','retailSales':'Monthly','consumerConfidence':'Monthly',
    'participation':'Monthly','employmentChange':'Monthly','wageGrowth':'Monthly'};
  if(!ki.length)return'<div class="tldr-empty">Indicator data pending.</div>';
  let rows='';
  ki.forEach(ind=>{
    const key=labelMap[(ind.label||'').toUpperCase()]||'';
    const m=meta[key]||{};
    const freq=freqMap[key]||'';
    const chgText=ind.change||m.change||'';
    let cls='unch';
    if(/^\+|▲|\bup\b|\bgain\b|\brose\b|\bincreas/i.test(chgText))cls='up';
    else if(/^-|▼|\bdown\b|\bfell\b|\bdeclin|\bdrop/i.test(chgText))cls='down';
    else if(/held|unchanged|flat|0bp/i.test(chgText))cls='unch';
    const arrow=cls==='up'?'\u25B2 ':cls==='down'?'\u25BC ':'';
    const src=m.source||(D.indicatorSources&&D.indicatorSources[key])||'';
    rows+=`<tr>
      <td class="ind-t-name">${san(ind.label||'')}${freq?' <span class="tldr-freq-tag">'+freq+'</span>':''}</td>
      <td class="ind-t-val">${san(ind.value||'')}</td>
      <td class="ind-t-chg ${cls}">${arrow}${san(chgText)}</td>
      <td class="ind-t-ref">${san(ind.period||m.period||'')}</td>
      <td class="ind-t-next">\u2014</td>
      <td class="ind-t-src">${san(src)}</td>
    </tr>`;
  });
  return`<table class="tldr-ind-table"><thead><tr>
    <th>Indicator</th><th class="r">Value</th><th class="r">Change (from prior)</th>
    <th>Reference Period</th><th class="r">Next Release</th><th class="r">Source</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

/* ── TL;DR: Markets table ── */
function _tldrBuildMarketsTable(){
  const comms=D.commodities||[];
  const fm=D.financialMarkets||D.financial_markets||{};
  let items=[];
  // Add commodities
  comms.forEach(c=>{
    items.push({name:c.name||c.symbol||'',value:c.price||c.value||'',change:c.change||'',source:c.source||'yfinance'});
  });
  // Add FX if available
  if(fm.fx&&fm.fx.length){fm.fx.forEach(f=>{items.push({name:f.name||'',value:f.value||'',change:f.change||'',source:'yfinance'})})}
  // Add indices
  if(fm.indices&&fm.indices.length){fm.indices.forEach(idx=>{items.push({name:idx.name||'',value:idx.value||'',change:idx.change||'',source:'yfinance'})})}
  if(!items.length)return'<div class="tldr-empty">Markets data pending.</div>';
  let rows='';
  items.forEach(it=>{
    const chg=it.change||'';
    let cls='unch';
    if(/^\+|▲|\bup\b|\bgain/i.test(chg)||(/^[\d.]/.test(chg)&&!chg.startsWith('-')&&!chg.startsWith('0')))cls='up';
    if(/^-|▼|\bdown\b|\bfell\b|\bdrop/i.test(chg))cls='down';
    if(!chg||/flat|unchanged|0\.0/i.test(chg))cls='unch';
    const arrow=cls==='up'?'\u25B2 ':cls==='down'?'\u25BC ':'';
    rows+=`<tr>
      <td class="ind-t-name">${san(it.name)} <span class="tldr-freq-tag">Daily</span></td>
      <td class="ind-t-val">${san(String(it.value))}</td>
      <td class="ind-t-chg ${cls}">${arrow}${san(chg)}</td>
      <td class="ind-t-ref">\u2014</td>
      <td class="ind-t-next">\u2014</td>
      <td class="ind-t-src">${san(it.source)}</td>
    </tr>`;
  });
  return`<table class="tldr-ind-table"><thead><tr>
    <th>Indicator</th><th class="r">Value</th><th class="r">Change</th>
    <th>Reference Period</th><th class="r">Next Release</th><th class="r">Source</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

/* ── TL;DR: "This Week's Key Data" table (second section in Numbers at a Glance) ── */
function _tldrBuildWeeklyDataTable(){
  const comms=D.commodities||[];
  const stats=D.discovery_stats||{};
  let rows='';
  // Add top commodities
  comms.slice(0,4).forEach(function(c){
    const chg=c.change||'';
    let cls='unch';
    if(/^\+|▲|\bup\b|\bgain/i.test(chg))cls='up';
    else if(/^-|▼|\bdown\b|\bfell\b|\bdrop/i.test(chg))cls='down';
    const arrow=cls==='up'?'\u25B2 ':cls==='down'?'\u25BC ':'';
    rows+=`<tr>
      <td class="ind-t-name">${san(c.name||'')} <span class="tldr-freq-tag">Daily</span></td>
      <td class="ind-t-val">${san(String(c.price||c.value||''))}</td>
      <td class="ind-t-chg ${cls}">${arrow}${san(chg)}</td>
      <td class="ind-t-ref">\u2014</td><td class="ind-t-next">\u2014</td>
      <td class="ind-t-src">${san(c.source||'yfinance')}</td>
    </tr>`;
  });
  if(!rows)return'';
  return`<div class="tldr-map-section">
    <div class="tldr-toggle-row"><span class="tldr-glance-label">This Week\u2019s Key Data</span></div>
    <table class="tldr-ind-table"><thead><tr>
      <th>Indicator</th><th class="r">Value</th><th class="r">Change (from prior)</th>
      <th>Reference Period</th><th class="r">Next Release</th><th class="r">Source</th>
    </tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

/* ── TL;DR: Weekly Briefing narrative ── */
function _tldrBuildBriefing(){
  const raw=D.executive_summary||'';
  const sources=D.sources||[];
  let html=bulletsToParas(san(linkFootnotes(raw,sources)));

  // Merge short header paragraphs into the following content paragraph.
  html=html.replace(/<p>\s*<strong>([^<]{3,60})<\/strong>\s*<\/p>\s*<p>/gi,function(m,heading){
    return '<p><span class="tldr-lead-sentence">'+heading.replace(/&amp;/g,'&')+' \u2014</span> ';
  });
  // For remaining content paragraphs without a lead-sentence, auto-wrap first sentence
  html=html.replace(/<p>(?!<span class="tldr-lead-sentence")([^<]{20,}?[.!?])\s/g,function(m,first){return'<p><span class="tldr-lead-sentence">'+first+'</span> '});

  // Build callout boxes with inline charts from D.insightCharts
  const ic=D.insightCharts||D.insight_charts||[];
  const stats=D.discovery_stats||{};
  var callouts=[];

  // First callout: pipeline cross-reference + first insight chart
  var c1Text=(stats.total_projects)?'<strong>Cross-reference:</strong> The database tracks '+(stats.total_projects||0).toLocaleString()+' active projects valued at '+(D.pipeline_value||'$'+((stats.total_value_billions||0).toFixed(1))+'B')+' across Canada.'+(stats.new_this_week?' '+stats.new_this_week+' new projects discovered this week.':''):'';
  if(ic.length>=1){
    var ch=ic[0];
    c1Text=(ch.reasoning?san(ch.reasoning):c1Text);
    callouts.push({text:c1Text,chart:ch});
  }else if(c1Text){
    callouts.push({text:c1Text,chart:null});
  }

  // Second callout: second insight chart
  if(ic.length>=2){
    var ch2=ic[1];
    callouts.push({text:ch2.reasoning?san(ch2.reasoning):'',chart:ch2});
  }

  // Intersperse callouts between paragraphs
  var paras=html.split('</p>').filter(function(p){return p.trim().length>0});
  // Place callout 1 after paragraph 1, callout 2 after paragraph 3
  var positions=[{after:1,idx:0},{after:3,idx:1}];
  var inserted=0;
  positions.forEach(function(pos){
    if(pos.idx>=callouts.length)return;
    var insertAt=pos.after+inserted;
    if(insertAt<paras.length){
      paras.splice(insertAt,0,'</p>'+_tldrCalloutHtml(callouts[pos.idx],pos.idx));
      inserted++;
    }
  });
  html=paras.join('</p>')+'</p>';

  // Sources
  let srcHtml='';
  if(sources.length){
    srcHtml=`<details class="tldr-sources"><summary>Sources (${sources.length})</summary><ol>`;
    sources.forEach(function(s){
      const url=s.url||s.archive_url||'';
      const title=san(s.title||'Source');
      srcHtml+=url?`<li><a href="${url}" target="_blank" rel="noopener">${title}</a></li>`:`<li>${title}</li>`;
    });
    srcHtml+='</ol></details>';
  }
  return`<div class="tldr-section">
    <div class="tldr-section-header">
      <div class="tldr-section-accent"></div>
      <h3>Weekly Briefing</h3>
    </div>
    <div class="tldr-narrative">${html}</div>
    ${srcHtml}
  </div>`;
}

/* Build a callout box with optional inline SVG chart */
function _tldrCalloutHtml(co,idx){
  var h='<div class="tldr-callout">';
  if(co.text)h+=co.text;
  if(co.chart){
    var ch=co.chart;
    var keys=ch.dataKeys||[];
    h+='<div class="tldr-callout-chart" id="tldrCalloutChart_'+idx+'">';
    h+='<div class="tldr-callout-chart-title">'+(ch.title||'')+(ch.subtitle?' \u00B7 '+ch.subtitle:'')+'</div>';
    // Legend
    var colors=['#003153','#7c3aed','#c4320a','#0d7a3f'];
    if(keys.length>1){
      h+='<div class="tldr-chart-legend">';
      keys.forEach(function(k,i){h+='<span class="tldr-chart-legend-item"><span class="tldr-chart-legend-dot" style="background:'+colors[i%colors.length]+'"></span>'+k+'</span>'});
      h+='</div>';
    }
    // Chart placeholder — filled async after render
    h+='<div class="tldr-callout-svg" id="tldrCalloutSvg_'+idx+'"><div style="height:120px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">Loading chart\u2026</div></div>';
    h+='</div>';
  }
  h+='</div>';
  return h;
}

/* Render callout SVG charts async after page paint */
async function _tldrRenderCalloutCharts(){
  var ic=D.insightCharts||D.insight_charts||[];
  var colors=['#003153','#7c3aed','#c4320a','#0d7a3f'];
  for(var idx=0;idx<ic.length&&idx<2;idx++){
    var ch=ic[idx];var keys=ch.dataKeys||[];
    var el=document.getElementById('tldrCalloutSvg_'+idx);
    if(!el||!keys.length)continue;
    // Load all timeseries for this chart
    var allSeries=[];
    for(var ki=0;ki<keys.length;ki++){
      var ts=await loadTimeseries(keys[ki]);
      if(!ts){ts=await loadTimeseries('comm_'+keys[ki])}
      var raw=ts&&(ts.series||ts);
      if(Array.isArray(raw)&&raw.length)allSeries.push({key:keys[ki],data:raw,color:colors[ki%colors.length]});
    }
    if(!allSeries.length){el.innerHTML='<div style="height:120px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">No timeseries data</div>';continue;}
    // Filter to last 12 months
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    allSeries.forEach(function(s){s.data=s.data.filter(function(p){return new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)})});
    // Build multi-line SVG
    el.innerHTML=_svgCalloutChart(allSeries,ch.annotations||[]);
  }
}

function _svgCalloutChart(seriesArr,annotations){
  var W=700,H=120,pL=45,pR=10,pT=10,pB=18;
  // Compute global min/max across all series
  var allVals=[];seriesArr.forEach(function(s){s.data.forEach(function(p){allVals.push(p.value)})});
  if(!allVals.length)return '';
  var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals),rng=mx-mn;
  if(rng===0)rng=Math.abs(mn)*0.1||1;
  mn-=rng*0.08;mx+=rng*0.08;rng=mx-mn;
  var pW=W-pL-pR,pH=H-pT-pB;
  function xPos(date,dates){var i=dates.indexOf(date);return pL+(i/(dates.length-1))*pW}
  function yPos(v){return pT+(1-(v-mn)/rng)*pH}

  var svg='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto;">';
  // Grid
  for(var g=0;g<4;g++){var gy=pT+(g/3)*pH;var gv=mx-(g/3)*rng;svg+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="#e4e2dd" stroke-width="0.5"/>';svg+='<text x="'+(pL-4)+'" y="'+(gy+3)+'" text-anchor="end" fill="#aaa" font-size="7" font-family="DM Sans">'+_svgFmtVal(gv)+'</text>';}
  // X-axis labels
  var refDates=seriesArr[0].data;
  var xLabels=Math.min(4,refDates.length);
  for(var xi=0;xi<xLabels;xi++){var di=Math.round(xi/(xLabels-1)*(refDates.length-1));var dx=pL+(di/(refDates.length-1))*pW;svg+='<text x="'+dx+'" y="'+(H-3)+'" text-anchor="middle" fill="#aaa" font-size="7" font-family="DM Sans">'+_svgFmtDate(refDates[di].date)+'</text>';}

  // Draw each series
  seriesArr.forEach(function(s){
    if(!s.data.length)return;
    var pts=s.data.map(function(p,i){return{x:pL+(i/(s.data.length-1))*pW,y:yPos(p.value)}});
    var poly=pts.map(function(p){return p.x+','+p.y}).join(' ');
    // Area fill for first series only
    if(s===seriesArr[0]){
      var fid='tldrCF_'+(++_svgUid);
      svg+='<defs><linearGradient id="'+fid+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="'+s.color+'" stop-opacity="0.08"/><stop offset="100%" stop-color="'+s.color+'" stop-opacity="0"/></linearGradient></defs>';
      var lp=pts[pts.length-1],fp=pts[0],bot=pT+pH;
      svg+='<polygon fill="url(#'+fid+')" points="'+poly+' '+lp.x+','+bot+' '+fp.x+','+bot+'"/>';
    }
    svg+='<polyline fill="none" stroke="'+s.color+'" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" points="'+poly+'"/>';
    var last=pts[pts.length-1];
    svg+='<circle cx="'+last.x+'" cy="'+last.y+'" r="2.5" fill="'+s.color+'"/>';
  });

  // Annotations (vertical markers)
  annotations.forEach(function(a){
    if(!a.date)return;
    // Find x position from first series dates
    var rd=seriesArr[0].data;
    var closest=0,minDiff=Infinity;
    rd.forEach(function(p,i){var diff=Math.abs(new Date(p.date)-new Date(a.date));if(diff<minDiff){minDiff=diff;closest=i}});
    var ax=pL+(closest/(rd.length-1))*pW;
    svg+='<line x1="'+ax+'" y1="'+pT+'" x2="'+ax+'" y2="'+(pT+pH)+'" stroke="#7a8599" stroke-width="0.5" stroke-dasharray="3,2"/>';
  });

  svg+='</svg>';return svg;
}

/* ── TL;DR: Policy Developments ── */
async function _tldrBuildPolicy(){
  let policyItems=[];
  try{
    const raw=await fetchJSON('policy.json');
    const weeks=raw&&raw.weeks?raw.weeks:[];
    if(weeks.length&&weeks[0].items)policyItems=weeks[0].items;
  }catch(e){}
  // Policy summary narrative (from first week's summary if available)
  let policySummary='';
  try{
    const raw2=await fetchJSON('policy.json');
    const weeks2=raw2&&raw2.weeks?raw2.weeks:[];
    if(weeks2.length&&weeks2[0].summary&&weeks2[0].summary.length>10)policySummary=weeks2[0].summary;
  }catch(e){}

  if(!policyItems.length){
    return`<div class="tldr-section">
      <div class="tldr-section-header">
        <div class="tldr-section-accent"></div>
        <h3>Major Policy Developments</h3>
      </div>
      <div class="tldr-policy-narrative"><p>No federal or provincial policy items tracked this week. The policy monitor scans LEGISinfo, Canada Gazette, and ministry feeds for legislative and regulatory developments affecting capital investment.</p></div>
    </div>`;
  }
  let itemsHtml='';
  policyItems.forEach(p=>{
    const title=san(p.title||p.name||'');
    const body=san(p.description||p.summary||p.body||'');
    const url=p.url||p.source_url||'';
    const linkHtml=url?` <a class="tldr-policy-item-link" href="${url}" target="_blank">View source \u2192</a>`:'';
    itemsHtml+=`<details class="tldr-policy-item" open>
      <summary><span class="tldr-policy-item-title">${title}</span></summary>
      <div class="tldr-policy-item-body">${body}${linkHtml}</div>
    </details>`;
  });
  // Build policy sources list
  let policySrcHtml='';
  const policySources=policyItems.filter(function(p){return p.url||p.source_url}).map(function(p){return{url:p.url||p.source_url,title:p.title||p.name||'Source'}});
  if(policySources.length){
    policySrcHtml=`<details class="tldr-sources"><summary>Sources (${policySources.length})</summary><ol>`;
    policySources.forEach(function(s){policySrcHtml+=`<li><a href="${san(s.url)}" target="_blank" rel="noopener">${san(s.title)}</a></li>`});
    policySrcHtml+='</ol></details>';
  }

  return`<div class="tldr-section">
    <div class="tldr-section-header">
      <div class="tldr-section-accent"></div>
      <h3>Major Policy Developments</h3>
      <span class="tldr-section-sub">${policyItems.length} items</span>
    </div>
    ${policySummary?'<div class="tldr-policy-narrative"><p>'+san(policySummary)+'</p></div>':''}
    <div class="tldr-inner-card tldr-policy-items">${itemsHtml}</div>
    ${policySrcHtml}
  </div>`;
}

/* ── TL;DR: Project Pipeline This Week ── */
async function _tldrBuildProjects(){
  const stats=D.discovery_stats||{};
  const newCount=stats.new_this_week||D.new_projects||0;
  const totalProjects=stats.total_projects||D.project_count||0;

  // Determine week range from briefing date
  const weekOf=D.week_of||'';
  let weekStart='',weekEnd='';
  if(weekOf){
    const dt=new Date(weekOf+'T00:00:00');
    const mon=new Date(dt);mon.setDate(dt.getDate()-dt.getDay()+1);// Monday
    const sun=new Date(mon);sun.setDate(mon.getDate()+6);
    weekStart=mon.toISOString().slice(0,10);
    weekEnd=sun.toISOString().slice(0,10);
  }

  // Load projects and filter for this week's activity
  let newProjects=[],statusChanges=[];
  try{
    const all=await fetchJSON('projects_all.json');
    if(Array.isArray(all)&&weekStart){
      all.forEach(p=>{
        const tracked=(p.firstTracked||'').slice(0,10);
        const updated=(p.lastUpdated||'').slice(0,10);
        const isNew=tracked>=weekStart&&tracked<=weekEnd;
        // Check statusHistory for actual status changes this week
        let hadStatusChange=false;
        const sh=p.statusHistory;
        if(Array.isArray(sh)&&sh.length){
          sh.forEach(entry=>{
            if(entry&&entry.date&&entry.date.slice(0,10)>=weekStart&&entry.date.slice(0,10)<=weekEnd){
              hadStatusChange=true;
            }
          });
        }
        // Categorize: new this week vs status change this week
        if(isNew&&newCount>0){newProjects.push(p)}
        else if(hadStatusChange&&!isNew){statusChanges.push(p)}
        else if(!isNew&&updated>=weekStart&&updated<=weekEnd){statusChanges.push(p)}
      });
      // If new_this_week from pipeline says 0 but we found thousands, it's a bulk import — clear
      if(newCount===0)newProjects=[];
      // Sort both by parsed value descending
      const valSort=(a,b)=>(parseNumericValue(b.value)||0)-(parseNumericValue(a.value)||0);
      newProjects.sort(valSort);
      statusChanges.sort(valSort);
    }
  }catch(e){}

  // Build subtitle
  const subParts=[];
  if(newCount>0)subParts.push(newCount+' new');
  if(statusChanges.length>0)subParts.push(statusChanges.length+' status changes');
  const subText=subParts.length?subParts.join(' \u00B7 '):'No changes this week';

  // Narrative
  let narrativeParts=[];
  if(newCount>0)narrativeParts.push(`The pipeline added ${newCount} new project${newCount!==1?'s':''} this week.`);
  if(statusChanges.length>0)narrativeParts.push(`${statusChanges.length} project${statusChanges.length!==1?'s':''} had status updates.`);
  if(!narrativeParts.length)narrativeParts.push(`No new projects or status changes recorded this week. The pipeline tracks ${totalProjects.toLocaleString()} projects across Canada.`);
  const narrativeHtml=`<div class="tldr-update-narrative"><p>${narrativeParts.join(' ')}</p></div>`;

  // Combine for table: new first, then status changes, cap at 12
  const tableProjects=[...newProjects.slice(0,6),...statusChanges.slice(0,12-Math.min(newProjects.length,6))];

  let tableHtml='';
  if(tableProjects.length){
    let rows='';
    tableProjects.forEach(p=>{
      const statusSlug=(p.status||'proposed').toLowerCase().replace(/\s+/g,'-');
      const isNew=newProjects.includes(p);
      rows+=`<tr>
        <td class="proj-name">${san(p.name||'')}${isNew?' <span class="tldr-freq-tag">NEW</span>':''}</td>
        <td>${san(p.province||'')}</td>
        <td>${_normSector(p.sector||'')}</td>
        <td class="proj-val">${fmtCurrency(p.value,p)}</td>
        <td><span class="tldr-status-badge ${statusSlug}">${san(p.status||'Proposed')}</span></td>
      </tr>`;
    });
    tableHtml=`<div class="tldr-inner-card" style="padding:0;overflow:hidden">
      <table class="tldr-projects-table"><thead><tr>
        <th>Project</th><th>Province</th><th>Sector</th><th>Value</th><th>Status</th>
      </tr></thead><tbody>${rows}</tbody></table>
      <div class="tldr-view-all" onclick="switchTab('projects')">View all ${totalProjects.toLocaleString()} projects \u2192</div>
    </div>`;
  }
  return`<div class="tldr-section">
    <div class="tldr-section-header">
      <div class="tldr-section-accent"></div>
      <h3>Project Pipeline This Week</h3>
      <span class="tldr-section-sub">${subText}</span>
    </div>
    ${narrativeHtml}
    ${tableHtml}
  </div>`;
}

/* ── Provincial indicator lookup for map ── */
function getProvIndicators(){
  const data={};
  const FULL_TO_CODE={'Alberta':'AB','British Columbia':'BC','Manitoba':'MB','New Brunswick':'NB',
    'Newfoundland and Labrador':'NL','Nova Scotia':'NS','Ontario':'ON','Prince Edward Island':'PE',
    'Quebec':'QC','Québec':'QC','Saskatchewan':'SK','Northwest Territories':'NT','Nunavut':'NU','Yukon':'YT'};
  indicators.forEach(ind=>{
    const name=ind.indicator_name;
    if(!['gdp','unemployment','cpi','housingStarts','unemployment_prev','cpi_prev','participationRate','participationRate_prev','employmentRate','employmentRate_prev','wageGrowth'].includes(name))return;
    let prov=ind.province;
    if(FULL_TO_CODE[prov])prov=FULL_TO_CODE[prov];
    else if(NAME_TO_CODE[prov])prov=NAME_TO_CODE[prov];
    else return;
    if(prov.toLowerCase()==='national'||prov.toLowerCase()==='global')return;
    if(!data[prov])data[prov]={};
    const existing=data[prov]['_'+name+'_period']||'';
    if(ind.period>=existing){
      data[prov][name]=ind.value;
      data[prov]['_'+name+'_period']=ind.period;
    }
  });
  return data;
}

/* ── Interactive Canada Map (used by other tabs) ── */
async function renderInteractiveMap(){
  const container=$('tldrMapSection');
  if(!container)return;
  const provData=getProvIndicators();
  // Shared toggle state — controls national panel AND province tooltips
  let _mapMode='indicators'; // 'indicators' or 'thisweek'

  // National stat boxes — grounded with period, freq, source, change
  const ki=(D&&D.key_indicators)||[];
  const m=(D&&D.metrics)||{};
  const im=(D&&D.indicatorMeta)||{};
  function _indVal(name){const i=indicators.find(x=>x.indicator_name===name);return i?i.value:null}
  function _indRec(name){return indicators.find(x=>x.indicator_name===name&&(x.province||'').toLowerCase()==='national')||indicators.find(x=>x.indicator_name===name)||null}
  function _indMeta(name){return (im&&im[name])||{}}
  const findKI=(label)=>{const item=ki.find(k=>k.label===label);return item?{value:item.value,change:item.change}:{value:'N/A',change:''}};
  const _tGdp=_indRec('realGdp'),_tUn=_indRec('unemployment'),_tPart=_indRec('participationRate'),_tEmp=_indRec('employmentRate'),_tWage=_indRec('wageGrowth'),_tBoc=_indRec('overnight_rate');
  function _tc(metaKey,indName){return pick(_indMeta(metaKey).change,computeChange(indName||metaKey,'national'))}

  const statsDefault=[
    {label:'BoC Rate',value:pick(m.bocRate,m.boc_rate,_indVal('overnight_rate')),change:_tc('bocRate','overnight_rate'),period:indBasis(_tBoc,_indMeta('bocRate').period,'scheduled'),freq:'8x/yr',source:indSource(_tBoc,'Bank of Canada')},
    {label:'Real GDP',value:pick(m.realGdp,_indVal('realGdp')),change:pick(_tc('realGdp','realGdp'),m.realGdp||''),period:indBasis(_tGdp,_indMeta('realGdp').period,'quarterly'),freq:'Quarterly',source:indSource(_tGdp,'Statistics Canada')},
    {label:'CPI',value:pick(m.cpi,_indVal('cpi'),_indVal('cpi_national')),change:pick(_tc('cpi','cpi'),m.cpi||''),period:indBasis(_indRec('cpi'),_indMeta('cpi').period,'monthly'),freq:'Monthly',source:indSource(_indRec('cpi'),'Statistics Canada')},
    {label:'Unemployment',value:pick(m.unemployment,_indVal('unemployment'),findKI('UNEMPLOYMENT').value),change:pick(findKI('UNEMPLOYMENT').change,_tc('unemployment','unemployment')),period:indBasis(_tUn,_indMeta('unemployment').period,'monthly'),freq:'Monthly',source:indSource(_tUn,'Statistics Canada')},
    {label:'Participation',value:pick(_tPart&&_tPart.value,m.participation,_indVal('participationRate')),change:computeChange('participationRate','national'),period:indBasis(_tPart,'','monthly'),freq:'Monthly',source:indSource(_tPart,'Statistics Canada')},
    {label:'Employment Rate',value:pick(_tEmp&&_tEmp.value,_indVal('employmentRate')),change:computeChange('employmentRate','national'),period:indBasis(_tEmp,'','monthly'),freq:'Monthly',source:indSource(_tEmp,'Statistics Canada')},
    {label:'Wage Growth',value:pick(m.wageGrowth,_tWage&&_tWage.value,_indVal('wageGrowth')),change:pick(computeChange('wageGrowth','national'),m.wageGrowth||''),period:indBasis(_tWage,'','monthly'),freq:'Monthly',source:indSource(_tWage,'Statistics Canada')},
    {label:'Housing Starts',value:pick(m.housingStarts,_indVal('housingStarts')),change:_tc('housingStarts','housingStarts'),period:indBasis(_indRec('housingStarts'),_indMeta('housingStarts').period,'monthly'),freq:'Monthly',source:indSource(_indRec('housingStarts'),'CMHC')}
  ];
  // "This Week" indicators — the ones that moved or are newsworthy this week
  const statsThisWeek=[];
  ki.forEach(k=>{
    if(k.change&&k.change.trim())statsThisWeek.push({label:k.label,value:k.value,change:k.change});
  });
  // Add MFG sales if present
  const mfg=findKI('MFG SALES');if(mfg.value!=='N/A')statsThisWeek.push({label:'MFG Sales',value:mfg.value,change:mfg.change});
  // Pad to 6 with other key indicators
  if(statsThisWeek.length<6&&_tWage)statsThisWeek.push({label:'Wage Growth',value:_tWage.value,change:''});
  if(statsThisWeek.length<6&&_tPart)statsThisWeek.push({label:'Participation',value:_tPart.value,change:''});

  function buildNatPanel(){
    const isInd=_mapMode==='indicators';
    const activeStats=isInd?statsDefault:statsThisWeek.slice(0,8);
    let html=`<div class="ed-stat-header" style="display:flex;justify-content:space-between;align-items:center">
      <span>Canada &mdash; National</span>
      <span style="display:flex;gap:4px">
        <span class="ed-tt-tab${isInd?' active':''}" id="natToggleInd">Key Indicators</span>
        <span class="ed-tt-tab${!isInd?' active':''}" id="natToggleHL">This Week</span>
      </span>
    </div>`;
    if(isInd){
      // Full grounded table with period, freq, source, change
      html+='<table class="ed-ind-table"><thead><tr><th>Indicator</th><th style="text-align:right">Value</th><th style="text-align:right">Chg</th><th style="text-align:right">Period</th><th style="text-align:right">Freq</th><th style="text-align:right">Source</th></tr></thead><tbody>';
      activeStats.forEach(s=>{
        const chg=s.change||'';
        const cls=chg.startsWith('-')||chg.startsWith('\u2212')?'change-down':chg.startsWith('+')?'change-up':'';
        html+='<tr><td class="ind-label">'+s.label+'</td><td class="ind-value">'+fmtNum(s.value)+'</td><td class="ind-change '+cls+'">'+(chg||'\u2014')+'</td><td class="ind-basis" style="font-size:9px;color:#64748B;text-align:right;white-space:nowrap">'+(s.period||'')+'</td><td style="font-size:8px;color:#94A3B8;text-align:right;white-space:nowrap">'+(s.freq||'')+'</td><td style="font-size:8px;color:#94A3B8;text-align:right;white-space:nowrap">'+(s.source||'')+'</td></tr>';
      });
      html+='</tbody></table>';
    }else{
      // "This Week" mode — compact stat boxes for movers
      html+='<div class="ed-stat-grid">';
      activeStats.forEach(s=>{
        const chgCls=s.change?(s.change.startsWith('-')||s.change.startsWith('\u2212')?'change-down':'change-up'):'';
        html+=`<div class="ed-stat-box"><div class="ed-stat-label">${s.label}</div><div class="ed-stat-value">${fmtNum(s.value)}</div>${s.change?`<div class="ed-stat-change ${chgCls}">${s.change}</div>`:''}`;
        html+='</div>';
      });
      html+='</div>';
    }
    const natPanel=document.getElementById('natStatsPanel');
    if(natPanel){
      natPanel.innerHTML=html;
      const indBtn=document.getElementById('natToggleInd');
      const hlBtn=document.getElementById('natToggleHL');
      if(indBtn)indBtn.onclick=()=>{_mapMode='indicators';buildNatPanel()};
      if(hlBtn)hlBtn.onclick=()=>{_mapMode='thisweek';buildNatPanel()};
    }
  }

  // Map container — floats right at 45%
  container.innerHTML=`<div class="ed-map" style="position:relative">
    <div id="natStatsPanel"></div>
    <div class="ed-map-chart">
      <div class="ec-title" style="margin-top:8px">Provincial GDP Growth</div>
      <div class="ec-sub">Hover for province details</div>
      <div id="canadaMapSvg" style="width:100%"></div>
      <div class="ed-map-legend"><span><span class="swatch" style="background:rgba(37,99,235,0.15)"></span>Lower growth</span><span><span class="swatch" style="background:rgba(37,99,235,0.90)"></span>Higher growth</span></div>
      <div class="ec-source">Statistics Canada, Provincial Accounts</div>
    </div>
  </div>`;
  buildNatPanel();

  // Render D3 map
  setTimeout(async()=>{
    try{
      let topo;
      try{
        const resp=await fetch('data/canada-provinces.topo.json');
        topo=await resp.json();
      }catch(e){
        console.warn('Local TopoJSON failed, falling back:',e);
        const resp=await fetch('https://raw.githubusercontent.com/markmarkoh/datamaps/master/src/js/data/can.topo.json');
        topo=await resp.json();
      }
      const objKey=Object.keys(topo.objects)[0];
      const geojson=topojson.feature(topo,topo.objects[objKey]);
      const mapDiv=document.getElementById('canadaMapSvg');
      if(!mapDiv)return;
      const w=mapDiv.clientWidth||400;const h=Math.max(w*0.7,220);
      mapDiv.style.minHeight=h+'px';

      // Use fitExtent to fill the entire SVG with the map
      const projection=d3.geoConicConformal().rotate([96,-1,0]).center([0,62]).parallels([49,77]);
      const tempPath=d3.geoPath().projection(projection);
      // Fit all features into the available space with small margin
      projection.fitExtent([[8,8],[w-8,h-8]],geojson);
      const path=d3.geoPath().projection(projection);

      // Parse GDP values for choropleth — also add a base tint for territories
      const gdpVals={};
      Object.entries(provData).forEach(([code,d])=>{
        if(d.gdp){
          const v=parseFloat(String(d.gdp).replace(/[+%]/g,''));
          if(!isNaN(v))gdpVals[code]=v;
        }
      });
      const gdpRange=Object.values(gdpVals);
      const minGDP=gdpRange.length?Math.min(...gdpRange):0;
      const maxGDP=gdpRange.length?Math.max(...gdpRange):5;
      const colorScale=d3.scaleLinear().domain([minGDP,maxGDP]).range([0.15,0.90]).clamp(true);

      // Province code from feature properties
      function featureCode(f){
        const p=f.properties||{};
        if(p.postal)return p.postal;
        if(p.iso_3166_2)return p.iso_3166_2.replace('CA-','');
        if(p.name){
          if(NAME_TO_CODE[p.name])return NAME_TO_CODE[p.name];
          // Handle accented names like Québec
          const plain=p.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'');
          if(NAME_TO_CODE[plain])return NAME_TO_CODE[plain];
        }
        const idMap={'CA.BC':'BC','CA.AB':'AB','CA.SK':'SK','CA.MB':'MB','CA.ON':'ON','CA.QC':'QC','CA.NB':'NB','CA.NS':'NS','CA.NF':'NL','CA.PE':'PE','CA.YT':'YT','CA.NT':'NT','CA.NU':'NU'};
        return idMap[f.id]||'';
      }

      const svg=d3.select(mapDiv).append('svg').attr('width',w).attr('height',h).attr('viewBox',`0 0 ${w} ${h}`).attr('preserveAspectRatio','xMidYMid meet');
      svg.append('rect').attr('width',w).attr('height',h).attr('fill','#F8FAFF').attr('rx',8);

      // Tooltip — append to body so it escapes overflow:hidden on .editorial-article
      let tooltip=document.getElementById('edMapTooltipGlobal');
      if(!tooltip){
        tooltip=document.createElement('div');
        tooltip.id='edMapTooltipGlobal';
        tooltip.className='ed-map-tooltip';
        document.body.appendChild(tooltip);
      }

      svg.selectAll('path').data(geojson.features).enter().append('path')
        .attr('d',path)
        .attr('fill',f=>{
          const code=featureCode(f);
          const gdp=gdpVals[code];
          if(gdp===undefined)return'rgba(37,99,235,0.07)';
          return`rgba(37,99,235,${colorScale(gdp).toFixed(2)})`;
        })
        .attr('stroke','#fff').attr('stroke-width',1).attr('stroke-linejoin','round')
        .style('cursor','pointer')
        .on('mouseover',function(event,f){
          d3.select(this).attr('stroke','#1a2744').attr('stroke-width',2);
          const code=featureCode(f);
          const pName=(PROVS.find(p=>p.code===code)||{}).name||code;
          const pd=provData[code]||{};
          let body='';
          if(_mapMode==='indicators'){
            if(pd.gdp)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">GDP Growth (YoY)</span><span class="ed-map-tooltip-value">${pd.gdp}</span></div>`;
            if(pd.unemployment){
              body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Unemployment</span><span class="ed-map-tooltip-value">${pd.unemployment}</span></div>`;
              if(pd.unemployment_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label" style="padding-left:8px">Prior month</span><span class="ed-map-tooltip-value" style="opacity:0.6">${pd.unemployment_prev}</span></div>`;
            }
            if(pd.cpi){
              body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">CPI (YoY)</span><span class="ed-map-tooltip-value">${pd.cpi}</span></div>`;
              if(pd.cpi_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label" style="padding-left:8px">Prior month</span><span class="ed-map-tooltip-value" style="opacity:0.6">${pd.cpi_prev}</span></div>`;
            }
            if(pd.participationRate)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Participation</span><span class="ed-map-tooltip-value">${pd.participationRate}</span></div>`;
            if(pd.employmentRate)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Employment Rate</span><span class="ed-map-tooltip-value">${pd.employmentRate}</span></div>`;
            if(pd.housingStarts)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Housing Starts</span><span class="ed-map-tooltip-value">${pd.housingStarts}</span></div>`;
          }else{
            // This Week — show indicators that changed this week for this province
            if(pd.unemployment&&pd.unemployment_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Unemployment</span><span class="ed-map-tooltip-value">${pd.unemployment} <span style="opacity:0.5">from ${pd.unemployment_prev}</span></span></div>`;
            if(pd.cpi&&pd.cpi_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">CPI (YoY)</span><span class="ed-map-tooltip-value">${pd.cpi} <span style="opacity:0.5">from ${pd.cpi_prev}</span></span></div>`;
            if(pd.participationRate&&pd.participationRate_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Participation</span><span class="ed-map-tooltip-value">${pd.participationRate} <span style="opacity:0.5">from ${pd.participationRate_prev}</span></span></div>`;
            if(pd.employmentRate&&pd.employmentRate_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Emp. Rate</span><span class="ed-map-tooltip-value">${pd.employmentRate} <span style="opacity:0.5">from ${pd.employmentRate_prev}</span></span></div>`;
            if(pd.housingStarts)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Housing Starts</span><span class="ed-map-tooltip-value">${pd.housingStarts}</span></div>`;
          }
          if(!body)body='<div style="color:rgba(255,255,255,0.5)">No data available</div>';
          tooltip.innerHTML=`<div class="ed-map-tooltip-title">${pName}</div>${body}`;
          tooltip.classList.add('visible');
        })
        .on('mousemove',function(event){
          const tw=240,th=tooltip.offsetHeight||150;
          let tx=event.pageX+14,ty=event.pageY-10;
          if(event.clientX+14+tw>window.innerWidth)tx=event.pageX-tw-10;
          if(event.clientY-10+th>window.innerHeight)ty=event.pageY-th-10;
          tooltip.style.left=tx+'px';
          tooltip.style.top=ty+'px';
        })
        .on('mouseout',function(){
          d3.select(this).attr('stroke','#fff').attr('stroke-width',1);
          tooltip.classList.remove('visible');
        });

      // Province labels — code only, skip Maritimes (shown in inset)
      const insetCodes=new Set(['NB','NS','PE']);
      const CENTROIDS={BC:[-124,54],AB:[-115,54],SK:[-106,54],MB:[-98,55],ON:[-85,50],QC:[-72,53],NL:[-60,53],YT:[-136,63],NT:[-120,65],NU:[-98,64.5]};
      Object.keys(gdpVals).forEach(code=>{
        if(insetCodes.has(code))return;
        const c=CENTROIDS[code];if(!c)return;
        const pt=projection(c);if(!pt)return;
        svg.append('text').attr('x',pt[0]).attr('y',pt[1]).attr('text-anchor','middle').attr('font-family','DM Sans').attr('font-size',11).attr('font-weight',700).attr('fill','#0f1b33').text(code);
      });

      // ── Maritime inset (top-right corner) — NB, NS, PE ──
      const maritimeCodes=new Set(['NB','NS','PE']);
      const maritimeFeatures=geojson.features.filter(f=>maritimeCodes.has(featureCode(f)));
      if(maritimeFeatures.length){
        const iw=Math.round(w*0.26);const ih=Math.round(iw*0.8);
        const ix=w-iw-12;const iy=12;
        const ig=svg.append('g').attr('class','maritime-inset');
        ig.append('rect').attr('x',ix).attr('y',iy).attr('width',iw).attr('height',ih).attr('fill','#F0F4FF').attr('stroke','rgba(37,99,235,0.25)').attr('stroke-width',1).attr('rx',6);
        ig.append('text').attr('x',ix+iw/2).attr('y',iy+12).attr('text-anchor','middle').attr('font-family','DM Sans').attr('font-size',8).attr('font-weight',600).attr('fill','#64748B').text('Maritimes');
        // Zoomed projection
        const mGeo={type:'FeatureCollection',features:maritimeFeatures};
        const mProj=d3.geoConicConformal().rotate([65,0,0]).center([0,46.5]).parallels([44,49]);
        mProj.fitExtent([[ix+6,iy+16],[ix+iw-6,iy+ih-6]],mGeo);
        const mPath=d3.geoPath().projection(mProj);
        ig.selectAll('path.mar').data(maritimeFeatures).enter().append('path')
          .attr('class','mar')
          .attr('d',mPath)
          .attr('fill',f=>{
            const code=featureCode(f);const gdp=gdpVals[code];
            if(gdp===undefined)return'rgba(37,99,235,0.07)';
            return`rgba(37,99,235,${colorScale(gdp).toFixed(2)})`;
          })
          .attr('stroke','#fff').attr('stroke-width',0.5).attr('stroke-linejoin','round')
          .style('cursor','pointer')
          .on('mouseover',function(event,f){
            d3.select(this).attr('stroke','#1a2744').attr('stroke-width',1.5);
            const code=featureCode(f);
            const pName=(PROVS.find(p=>p.code===code)||{}).name||code;
            const pd=provData[code]||{};
            let body='';
            if(_mapMode==='indicators'){
              if(pd.gdp)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">GDP Growth (YoY)</span><span class="ed-map-tooltip-value">${pd.gdp}</span></div>`;
              if(pd.unemployment)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Unemployment</span><span class="ed-map-tooltip-value">${pd.unemployment}</span></div>`;
              if(pd.cpi)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">CPI (YoY)</span><span class="ed-map-tooltip-value">${pd.cpi}</span></div>`;
              if(pd.participationRate)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Participation</span><span class="ed-map-tooltip-value">${pd.participationRate}</span></div>`;
              if(pd.employmentRate)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Employment Rate</span><span class="ed-map-tooltip-value">${pd.employmentRate}</span></div>`;
              if(pd.housingStarts)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Housing Starts</span><span class="ed-map-tooltip-value">${pd.housingStarts}</span></div>`;
            }else{
              if(pd.unemployment&&pd.unemployment_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Unemployment</span><span class="ed-map-tooltip-value">${pd.unemployment} <span style="opacity:0.5">from ${pd.unemployment_prev}</span></span></div>`;
              if(pd.cpi&&pd.cpi_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">CPI (YoY)</span><span class="ed-map-tooltip-value">${pd.cpi} <span style="opacity:0.5">from ${pd.cpi_prev}</span></span></div>`;
              if(pd.participationRate&&pd.participationRate_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Participation</span><span class="ed-map-tooltip-value">${pd.participationRate} <span style="opacity:0.5">from ${pd.participationRate_prev}</span></span></div>`;
              if(pd.employmentRate&&pd.employmentRate_prev)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Emp. Rate</span><span class="ed-map-tooltip-value">${pd.employmentRate} <span style="opacity:0.5">from ${pd.employmentRate_prev}</span></span></div>`;
              if(pd.housingStarts)body+=`<div class="ed-map-tooltip-row"><span class="ed-map-tooltip-label">Housing Starts</span><span class="ed-map-tooltip-value">${pd.housingStarts}</span></div>`;
            }
            if(!body)body='<div style="color:rgba(255,255,255,0.5)">No data</div>';
            tooltip.innerHTML=`<div class="ed-map-tooltip-title">${pName}</div>${body}`;
            tooltip.classList.add('visible');
          })
          .on('mousemove',function(event){
            const tw=tooltip.offsetWidth||250;
            tooltip.style.left=(event.pageX-tw-14)+'px';
            tooltip.style.top=(event.pageY-10)+'px';
          })
          .on('mouseout',function(){
            d3.select(this).attr('stroke','#fff').attr('stroke-width',0.5);
            tooltip.classList.remove('visible');
          });
        // Inset labels
        const MAR_CENTROIDS={NB:[-66,47],NS:[-63,44.8],PE:[-63,46.5]};
        maritimeFeatures.forEach(f=>{
          const code=featureCode(f);
          const c=MAR_CENTROIDS[code];if(!c)return;
          const pt=mProj(c);if(!pt)return;
          ig.append('text').attr('x',pt[0]).attr('y',pt[1]).attr('text-anchor','middle').attr('font-family','DM Sans').attr('font-size',9).attr('font-weight',700).attr('fill','#0f1b33').text(code);
        });
      }
    }catch(e){console.warn('Canada map render:',e)}
  },100);
}

/* ── TLDR Word Cloud (theme blues) ── */
function renderTLDRWordCloud(topics,containerId){
  const container=document.getElementById(containerId);
  if(!container||!topics||!topics.length)return;
  const w=container.clientWidth||300,h=Math.min(Math.round(w*0.8),250);
  container.innerHTML='';
  const blues=['#1e40af','#2563EB','#3b82f6','#4B6CB7','#60A5FA','#6B8DD6','#93c5fd'];
  const maxFreq=Math.max(...topics.map(t=>t.frequency||t.count||1));
  const sorted=[...topics].sort((a,b)=>(b.frequency||b.count||1)-(a.frequency||a.count||1));
  const words=sorted.slice(0,35).map((t,i)=>{
    const freq=t.frequency||t.count||1;
    return{text:t.topic||t.word||'',size:12+((freq/maxFreq)*30),freq,colorIdx:Math.min(Math.floor(i/5),blues.length-1)};
  });
  const layout=d3.layout.cloud().size([w,h]).words(words).padding(6).rotate(()=>0).font('DM Sans').fontSize(d=>d.size).on('end',drawn);
  layout.start();
  function drawn(wds){
    const svg=d3.select(container).append('svg').attr('width',w).attr('height',h);
    const g=svg.append('g').attr('transform','translate('+w/2+','+h/2+')');
    g.selectAll('text').data(wds).enter().append('text')
      .style('font-size',d=>d.size+'px').style('font-family','DM Sans')
      .style('font-weight',d=>d.size>35?'700':d.size>25?'600':'500')
      .style('fill',d=>blues[d.colorIdx])
      .style('opacity',d=>0.55+Math.min(d.size/52,0.45))
      .attr('text-anchor','middle').attr('transform',d=>'translate('+d.x+','+d.y+')')
      .text(d=>d.text)
      .append('title').text(d=>d.text+' (frequency: '+d.freq+')');
  }
}

/* ── TLDR Financial Markets section ── */
async function renderTLDRMarkets(){
  const el=$('tldrMarketsSection');
  if(!el)return;
  const fm=(D&&(D.financialMarkets||D.financial_markets||D.markets))||{};
  let indices=fm.indices||[];let fx=fm.fx||[];
  // Build from indicators if needed
  if(!indices.length&&indicators.length){
    const idxMap=[{name:'S&P/TSX',ind:'tsx_composite'},{name:'S&P/TSX',ind:'tsx'},{name:'S&P 500',ind:'sp500'},{name:'Dow Jones',ind:'djia'}];
    idxMap.forEach(m=>{const i=indicators.find(x=>x.indicator_name===m.ind);if(i&&!indices.find(x=>x.name===m.name))indices.push({name:m.name,value:i.value,change:''})});
  }
  if(!fx.length&&indicators.length){
    const fxMap=[{name:'CAD/USD',ind:'cadusd'},{name:'CAD/USD',ind:'cad_usd'}];
    fxMap.forEach(m=>{const i=indicators.find(x=>x.indicator_name===m.ind);if(i&&!fx.find(x=>x.name===m.name))fx.push({name:m.name,value:i.value})});
  }
  // Add key commodities
  const commItems=[];
  const commMap=[{name:'WTI',ind:'wti'},{name:'WTI',ind:'wti_oil'},{name:'Gold',ind:'gold'},{name:'Nat Gas',ind:'natural_gas'}];
  commMap.forEach(m=>{const i=indicators.find(x=>x.indicator_name===m.ind);if(i&&!commItems.find(x=>x.name===m.name))commItems.push({name:m.name,value:i.value,change:''})});

  const all=[...indices.slice(0,2),...fx.slice(0,1),...commItems.slice(0,3)];
  if(!all.length){el.innerHTML='<div style="color:#475569;font-size:var(--text-sm)">Markets data pending.</div>';return}

  // Brief narrative
  const tsx=indices.find(x=>x.name&&x.name.includes('TSX'));
  const cad=fx.find(x=>x.name&&x.name.includes('CAD'));
  const wti=commItems.find(x=>x.name==='WTI');
  let narrative='';
  if(tsx)narrative+=`The S&P/TSX traded at ${tsx.value||'N/A'}${tsx.change?' ('+tsx.change+')':''}. `;
  if(cad)narrative+=`The Canadian dollar traded at ${cad.value||'N/A'} against the U.S. dollar. `;
  if(wti)narrative+=`WTI crude at US$${wti.value||'N/A'}/bbl.`;
  if(narrative)narrative=`<p style="margin-bottom:12px">${narrative}</p>`;

  // Grid
  let gridHtml='<div class="ed-markets-grid">';
  all.forEach(item=>{
    const chg=item.change||item.day||'';
    const isNeg=chg.startsWith('-');
    const cls=isNeg?'change-down':(chg?'change-up':'');
    gridHtml+=`<div class="ed-markets-item"><div class="ed-markets-ticker">${item.name||''}</div><div class="ed-markets-price">${item.value||'N/A'}</div>${chg?`<div class="ed-markets-change ${cls}">${isNeg?'\u2193':'\u2191'} ${chg}</div>`:''}`;
    gridHtml+='</div>';
  });
  gridHtml+='</div>';

  // Commodity movers chart as supporting infographic
  const chartHtml=`<div class="ed-chart-inline" id="tldrCommodityCard" style="float:none;width:100%;margin:16px 0">
    <div class="ec-title">Commodity Movers</div><div class="ec-sub">Biggest weekly price changes</div>
    <div style="height:180px;position:relative"><canvas id="tldrCommodityChart"></canvas></div>
    <div class="ec-source">Yahoo Finance</div>
  </div>`;

  el.innerHTML=narrative+gridHtml+chartHtml;
  // Render commodity chart
  try{await _ensureChartData();_renderCommodityChart('tldrCommodityChart','tldrCommodityCard','tldr')}catch(e){console.warn('Markets chart:',e)}
}

/* ══ NATIONAL TAB (redesigned: subtabs Canada + Global Players) ══ */
let _nationalSubRendered={};
let _activeNationalSub='canada';
const COUNTRY_SUBTABS=[
  {key:'canada',label:'Canada',flag:'\uD83C\uDDE8\uD83C\uDDE6'},
  {key:'us',label:'United States',flag:'\uD83C\uDDFA\uD83C\uDDF8'},
  {key:'china',label:'China',flag:'\uD83C\uDDE8\uD83C\uDDF3'},
  {key:'eu',label:'European Union',flag:'\uD83C\uDDEA\uD83C\uDDFA'},
  {key:'uk',label:'United Kingdom',flag:'\uD83C\uDDEC\uD83C\uDDE7'}
];
const GLOBAL_SRC_MAP={us:'BEA \u00b7 BLS \u00b7 Federal Reserve',china:'NBS \u00b7 PBOC \u00b7 GAC',eu:'Eurostat \u00b7 ECB \u00b7 S&P Global',uk:'ONS \u00b7 BoE \u00b7 LSE'};
const GLOBAL_CHART_CFG={
  us:{tsKey:'idx_sp500',title:'S&P 500 \u2014 12-Month Performance',subtitle:'Monthly close',source:'S&P Dow Jones Indices',color:'#1e40af',fillColor:'rgba(30,64,175,0.12)',refLine:null},
  china:{tsKey:'china_pmi',title:'Manufacturing PMI \u2014 12-Month Trend',subtitle:'Official NBS PMI \u00b7 50 = expansion threshold',source:'National Bureau of Statistics',color:'#b91c1c',fillColor:'rgba(185,28,28,0.10)',refLine:{value:50,label:'Expansion threshold',color:'#7a8599'}},
  eu:{tsKey:'fx_eurusd',title:'EUR/USD Exchange Rate \u2014 12-Month Trend',subtitle:'Daily close \u00b7 ECB reference rate',source:'ECB',color:'#1e40af',fillColor:'rgba(30,64,175,0.12)',refLine:null},
  uk:{tsKey:'idx_ftse100',title:'FTSE 100 \u2014 12-Month Performance',subtitle:'Daily close \u00b7 London Stock Exchange',source:'LSE',color:'#065f46',fillColor:'rgba(6,95,70,0.12)',refLine:null}
};
window.showNationalSubtab=function(key){
  _activeNationalSub=key;
  var tabPanel=document.getElementById('tab-national');
  if(!tabPanel)return;
  tabPanel.querySelectorAll('.country-tab').forEach(function(b){b.classList.toggle('active',b.getAttribute('data-country')===key)});
  tabPanel.querySelectorAll('.subtab-panel').forEach(function(p){p.classList.toggle('active',p.id==='natSub-'+key)});
  if(!_nationalSubRendered[key]){
    _nationalSubRendered[key]=true;
    if(key==='canada'){_renderCanadaSubtab()}else{_renderGlobalSubtab(key)}
  }
};
async function renderNational(){
  _nationalSubRendered={};
  _activeNationalSub='canada';
  var page=$('nationalPage');if(!page)return;
  // Build country subtab row
  var html='<div class="country-tabs">';
  COUNTRY_SUBTABS.forEach(function(t){
    html+='<button class="country-tab'+(t.key==='canada'?' active':'')+'" data-country="'+t.key+'" onclick="showNationalSubtab(\''+t.key+'\')">'+t.label+'</button>';
  });
  html+='</div>';
  // Build subtab panels (one per country, only Canada visible by default)
  COUNTRY_SUBTABS.forEach(function(t){
    html+='<div id="natSub-'+t.key+'" class="subtab-panel'+(t.key==='canada'?' active':'')+'">';
    html+='<div id="natContent-'+t.key+'"></div>';
    html+='</div>';
  });
  page.innerHTML=html;
  // Render Canada immediately (default visible subtab)
  _nationalSubRendered.canada=true;
  await _renderCanadaSubtab();
  // Pre-render global subtabs (lazy chart init on first click)
  _preRenderGlobalSubtabs();
}

/* == Analysis-driven insight system == */
const INSIGHT_THEMES=[
  {id:'housing',keywords:['housing','residential','home','apartment','condo','rent','shelter','cmhc','starts','dwelling'],label:'Housing & Residential',sectors:['residential'],color:'#2563EB'},
  {id:'energy',keywords:['oil','gas','energy','petroleum','pipeline','lng','bitumen','crude','refinery','oilsands','wti','natural gas'],label:'Energy & Resources',sectors:['oil_gas','power_energy'],color:'#F59E0B'},
  {id:'mining',keywords:['mining','mineral','lithium','potash','nickel','copper','gold','ore','smelter'],label:'Mining & Minerals',sectors:['mining'],color:'#8B5CF6'},
  {id:'manufacturing',keywords:['manufactur','factory','plant','industrial','auto','ev battery','assembly'],label:'Manufacturing',sectors:['manufacturing'],color:'#10B981'},
  {id:'transport',keywords:['transport','transit','rail','highway','bridge','port','airport','road','lrt','subway'],label:'Transportation & Infrastructure',sectors:['transport_logistics','infrastructure'],color:'#0EA5E9'},
  {id:'healthcare',keywords:['health','hospital','medical','clinic','pharma','long-term care'],label:'Healthcare',sectors:['healthcare'],color:'#EC4899'},
  {id:'labour',keywords:['unemploy','labour','labor','jobs','employment','hiring','workforce','layoff','vacancy'],label:'Labour Market',sectors:[],color:'#6366F1'},
  {id:'trade',keywords:['trade','export','import','tariff','border','softwood','lumber','canola'],label:'Trade & Exports',sectors:[],color:'#14B8A6'},
  {id:'construction',keywords:['construction','permit','development','tower','build','crane','renovation'],label:'Construction Activity',sectors:['infrastructure','commercial_mixed'],color:'#84CC16'},
  {id:'agriculture',keywords:['agriculture','farm','crop','grain','wheat','canola','livestock','dairy'],label:'Agriculture',sectors:['agriculture'],color:'#D97706'},
  {id:'defence',keywords:['defence','defense','military','naval','shipbuild','frigat'],label:'Defence & Shipbuilding',sectors:['defence'],color:'#64748B'},
  {id:'education',keywords:['university','college','school','campus','research','education'],label:'Education & Research',sectors:['education'],color:'#A855F7'}
];

function extractAnalysisThemes(analysisText,projects){
  const text=(analysisText||'').replace(/<[^>]+>/g,' ').toLowerCase();
  const scored=[];
  INSIGHT_THEMES.forEach(theme=>{
    const matched=theme.keywords.filter(kw=>text.includes(kw));
    if(matched.length>0){
      // Count matching projects for sector themes (case-insensitive)
      let projCount=0,projValue=0;
      if(theme.sectors.length&&projects){
        const sectorSet=new Set(theme.sectors.map(s=>s.toLowerCase()));
        projects.forEach(p=>{
          if(sectorSet.has((p.sector||'').toLowerCase())){projCount++;projValue+=parseNumericValue(p.value)}
        });
      }
      scored.push({...theme,score:matched.length,projCount:projCount,projValue:projValue,_matchedKw:matched});
    }
  });
  return scored.sort((a,b)=>b.score-a.score).slice(0,1);
}

// Build a narrative chart title from timeseries trend + analysis context
function _buildNarrativeTitle(primaryLabel,data,analysisText,themeKeywords){
  if(!data||data.length<2)return primaryLabel;
  const first=data[0],last=data[data.length-1];
  const pctChg=first!==0?((last-first)/Math.abs(first))*100:0;
  const absPct=Math.abs(pctChg);
  // Direction verb
  let verb;
  if(absPct<1)verb='held steady';
  else if(pctChg>0)verb=absPct>10?'rose sharply':absPct>5?'rose notably':'rose';
  else verb=absPct>10?'fell sharply':absPct>5?'fell notably':'declined';
  const pctStr=absPct>=1?(' '+absPct.toFixed(1)+'%'):'';
  let headline=primaryLabel+' '+verb+pctStr+' over the past year';
  // Extract a short context clause from analysis matching theme keywords
  if(analysisText&&themeKeywords&&themeKeywords.length){
    const clean=analysisText.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ');
    const sentences=clean.match(/[^.!?]+[.!?]+/g)||[];
    for(const s of sentences){
      const low=s.toLowerCase();
      const hits=themeKeywords.filter(kw=>low.includes(kw));
      if(hits.length>=2){
        let clause=s.trim();
        // Take first clause if sentence is long
        if(clause.length>80){const parts=clause.split(/,\s*/);if(parts[0].length>15&&parts[0].length<80)clause=parts[0]}
        if(clause.length>80)clause=clause.substring(0,77).replace(/\s+\S*$/,'')+'...';
        // Remove leading connectors
        clause=clause.replace(/^(Meanwhile|However|In addition|Additionally|Furthermore|Moreover|Also),?\s*/i,'').replace(/^\w/,c=>c.toLowerCase());
        headline=primaryLabel+' '+verb+pctStr+' as '+clause;
        break;
      }
    }
  }
  return headline;
}

/* == Agent-driven insight chart system == */
// When agents provide an insightChart spec, render their chosen visualization
// instead of the keyword-based fallback system.

function buildAgentInsightStrip(prefix,chartSpec){
  if(!chartSpec||!chartSpec.dataKeys||!chartSpec.dataKeys.length)return '';
  const id=prefix+'AgentInsight';
  const title=chartSpec.title||'Weekly Insight';
  const subtitle=chartSpec.subtitle||'Agent-selected visualization';
  const reasoning=chartSpec.reasoning||'';
  let html='<div style="margin:0;padding:32px 24px 20px;border-top:3px solid #003153;background:#e8eef4;border-radius:0 0 8px 8px">';
  html+='<div style="text-align:left">';
  html+='<div id="'+prefix+'AgentInsightTitle" style="font-family:DM Sans,sans-serif;font-size:16px;font-weight:700;color:#003153;line-height:1.35;margin-bottom:4px">'+title+'</div>';
  html+='<div id="'+prefix+'AgentInsightSub" style="font-family:DM Sans,sans-serif;font-size:11px;color:#475569;margin-bottom:4px">'+subtitle+'</div>';
  if(reasoning){html+='<div style="font-family:DM Sans,sans-serif;font-size:10px;color:#94A3B8;font-style:italic;margin-bottom:16px">'+reasoning+'</div>'}
  html+='<div style="height:300px;position:relative;padding:12px 16px;background:#fff;border-radius:6px;box-shadow:0 1px 3px rgba(0,49,83,0.08)"><canvas id="'+id+'"></canvas></div>';
  html+='<div style="margin-top:12px;padding-top:8px;border-top:1px solid rgba(0,49,83,0.08);font-family:DM Sans,sans-serif;font-size:9px;color:#94A3B8">Source: The Lagging Indicator</div>';
  html+='</div>';
  html+='</div>';
  return html;
}

async function renderAgentInsightChart(prefix,chartSpec){
  if(!chartSpec||!chartSpec.dataKeys||!chartSpec.dataKeys.length)return;
  const canvasId=prefix+'AgentInsight';
  const canvas=document.getElementById(canvasId);
  if(!canvas)return;
  const key='_agentInsight_'+canvasId;
  if(charts[key]){charts[key].destroy();delete charts[key]}

  const allTs=await fetchJSON('timeseries.json').catch(()=>({}));
  const chartType=chartSpec.chartType||'line';
  const dataKeys=chartSpec.dataKeys;
  const annotations=chartSpec.annotations||[];
  const lineColors=[_ic.accent,_ic.pos,'#F59E0B','#8B5CF6'];
  const datasets=[];
  let allLabels=[];

  dataKeys.forEach((tsKey,idx)=>{
    let raw=allTs[tsKey];
    if(!raw||!raw.length)return;
    const series=Array.isArray(raw)?raw:raw.series||[];
    if(!series.length)return;
    const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    const filtered=series.filter(p=>new Date(p.date)>=cutoff).sort((a,b)=>new Date(a.date)-new Date(b.date));
    if(!filtered.length)return;
    const labels=filtered.map(p=>fmtDate(p.date));
    const data=filtered.map(p=>p.value);
    if(labels.length>allLabels.length)allLabels=labels;
    const c=lineColors[idx%lineColors.length];
    const isPrimary=datasets.length===0;

    if(chartType==='bar'||chartType==='diverging_bar'){
      datasets.push({
        label:tsKey.replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),
        data:data,
        backgroundColor:chartType==='diverging_bar'?data.map(v=>v>=0?_ic.pos:_ic.neg):_ic.hexAlpha(c,0.7),
        borderRadius:4,barPercentage:0.65
      });
    }else{
      datasets.push({
        label:tsKey.replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),
        data:data,
        borderColor:c,
        backgroundColor:isPrimary?_ic.hexAlpha(c,0.05):'transparent',
        borderWidth:isPrimary?2.5:2,
        pointRadius:data.map((_,i)=>i===data.length-1?5:0),
        pointBackgroundColor:c,
        pointBorderColor:_ic.white,
        pointBorderWidth:2,
        fill:isPrimary,
        tension:0.35,
        yAxisID:isPrimary?'y':'y1'
      });
    }
  });

  if(!datasets.length){
    canvas.parentElement.insertAdjacentHTML('beforeend','<div style="text-align:center;color:'+_ic.light+';font-size:var(--text-xs);padding:24px">No historical data available for selected indicators</div>');
    return;
  }

  const isBarType=chartType==='bar'||chartType==='diverging_bar';
  const needDualAxis=!isBarType&&datasets.length>=2;

  // Event annotations from agent
  const evtAnnotations={};
  annotations.forEach((ann,i)=>{
    try{
      const ed=new Date(ann.date);if(isNaN(ed))return;
      const ds=fmtDate(ed);const li=allLabels.indexOf(ds);if(li===-1)return;
      evtAnnotations['agentEvt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(0,49,83,0.25)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(ann.label||'').substring(0,25),position:'start',backgroundColor:'rgba(0,49,83,0.8)',color:_ic.white,font:{family:_ic.font,size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
    }catch(e){}
  });
  const hasAnnotation=Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation');
  const annotationCfg=hasAnnotation&&Object.keys(evtAnnotations).length?{annotation:{annotations:{...evtAnnotations}}}:{};

  // Scales
  const scales=isBarType?{
    x:{border:{display:true,color:_ic.prussian,width:1},grid:{display:false},ticks:{maxTicksLimit:10,font:{family:_ic.font,size:9},color:_ic.prussian,maxRotation:45,minRotation:0}},
    y:{border:{display:true,color:_ic.prussian,width:1},grid:{color:_ic.gridSoft,lineWidth:0.5},ticks:{font:{family:_ic.font,size:10},color:_ic.prussian,callback:v=>fmtNum(v)}}
  }:{
    x:{border:{display:true,color:_ic.prussian,width:1},grid:{display:false},ticks:{maxTicksLimit:8,font:{family:_ic.font,size:10},color:_ic.prussian,padding:10}},
    y:{position:'left',border:{display:true,color:_ic.prussian,width:1},grid:{color:_ic.gridSoft,lineWidth:0.5,drawTicks:false},ticks:{font:{family:_ic.font,size:10},color:_ic.prussian,padding:14,callback:v=>fmtNum(v)}}
  };
  if(needDualAxis){
    scales.y1={position:'right',border:{display:true,color:_ic.prussian,width:1},grid:{display:false},ticks:{font:{family:_ic.font,size:10},color:_ic.prussian,padding:14,callback:v=>fmtNum(v)}};
  }

  // Endpoint label plugin (line charts only)
  const endpointPlugin=isBarType?null:{id:'agentEndpoint_'+prefix,afterDraw(chart){
    datasets.forEach((ds,di)=>{
      const meta=chart.getDatasetMeta(di);const lastPt=meta.data[meta.data.length-1];
      if(!lastPt)return;const lastVal=ds.data[ds.data.length-1];
      const ctx=chart.ctx;ctx.save();ctx.font='600 11px '+_ic.font;ctx.fillStyle=ds.borderColor;
      ctx.textAlign=di===0?'left':'right';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):lastVal,lastPt.x+(di===0?6:-6),lastPt.y-8);ctx.restore();
    });
  }};

  // Legend
  const legendCfg=needDualAxis?{
    display:true,position:'top',align:'start',
    labels:{boxWidth:14,boxHeight:3,padding:18,font:{family:_ic.font,size:11,weight:'500'},color:_ic.prussian,usePointStyle:false,
      generateLabels:function(chart){return chart.data.datasets.map(function(ds,i){const axis=i===0?'left axis':'right axis';return{text:ds.label+' ('+axis+')',fillColor:ds.borderColor||ds.backgroundColor,strokeColor:ds.borderColor||ds.backgroundColor,lineWidth:2,hidden:false,datasetIndex:i}})}}
  }:isBarType&&datasets.length>1?{display:true,position:'top',labels:{boxWidth:10,padding:8,font:{family:_ic.font,size:10},color:_ic.heading}}:{display:false};

  const cType=isBarType?'bar':'line';
  const plugins=[].concat(endpointPlugin?[endpointPlugin]:[]);

  charts[key]=new Chart(canvas,{
    type:cType,
    data:{labels:allLabels,datasets:datasets},
    plugins:plugins,
    options:{
      responsive:true,maintainAspectRatio:false,
      layout:{padding:{top:10,right:needDualAxis?50:20,bottom:6,left:10}},
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:legendCfg,
        tooltip:{backgroundColor:'rgba(0,49,83,0.92)',titleColor:'#fff',titleFont:{family:_ic.font,size:11,weight:'600'},bodyColor:'#CBD5E1',bodyFont:{family:_ic.font,size:11},padding:12,cornerRadius:4,borderColor:'rgba(0,49,83,0.15)',borderWidth:1,displayColors:needDualAxis||datasets.length>1,boxWidth:8,boxHeight:2,callbacks:{label:ctx=>ctx.dataset.label+': '+fmtNum(ctx.raw)}},
        ...annotationCfg
      },
      scales:scales
    }
  });
}

function buildInsightStrip(prefix,themes,provCode){
  if(!themes||!themes.length)return '';
  const t=themes[0];
  const id=prefix+'Insight0';
  const tsEntries=resolveThemeTimeseries(t.id,provCode||null);
  const sub=tsEntries.length?tsEntries.map(s=>s.label).join(', ')+' \u2014 12-month trend':'From this week\u2019s analysis';
  let html='<div style="margin:0;padding:32px 24px 20px;border-top:3px solid #003153;background:#e8eef4;border-radius:0 0 8px 8px">';
  html+='<div style="text-align:left">';
  html+='<div id="'+prefix+'InsightTitle" style="font-family:DM Sans,sans-serif;font-size:16px;font-weight:700;color:#003153;line-height:1.35;margin-bottom:4px">'+t.label+'</div>';
  html+='<div id="'+prefix+'InsightSub" style="font-family:DM Sans,sans-serif;font-size:11px;color:#475569;margin-bottom:20px">'+sub+'</div>';
  html+='<div style="height:300px;position:relative;padding:12px 16px;background:#fff;border-radius:6px;box-shadow:0 1px 3px rgba(0,49,83,0.08)"><canvas id="'+id+'"></canvas></div>';
  html+='<div style="margin-top:12px;padding-top:8px;border-top:1px solid rgba(0,49,83,0.08);font-family:DM Sans,sans-serif;font-size:9px;color:#94A3B8">Source: Signal Dispatch pipeline data</div>';
  html+='</div>';
  html+='</div>';
  return html;
}

// Map themes to the best available chart data
const THEME_DATA_MAP={
  housing:{indicators:['housingStarts','housing_starts_total','building_permits_residential'],commodities:[],chartLabel:'Housing Starts & Permits'},
  energy:{indicators:['wti','brent','natural_gas'],commodities:['wti','brent','natural_gas','wcs','propane'],chartLabel:'Energy Prices'},
  mining:{indicators:['gold','copper','aluminum','nickel'],commodities:['gold','copper','aluminum','nickel','uranium_spot','steel','iron_ore','zinc','lithium','potash'],chartLabel:'Metals & Mining Prices'},
  manufacturing:{indicators:['manufacturing_sales','mfg_sales'],commodities:['steel','aluminum'],chartLabel:'Manufacturing Indicators'},
  transport:{indicators:[],commodities:['tsx_infrastructure'],chartLabel:'Infrastructure Pipeline'},
  healthcare:{indicators:[],commodities:[],chartLabel:'Healthcare Pipeline'},
  labour:{indicators:['unemployment','employmentRate','participationRate','wageGrowth','employment_change'],commodities:[],chartLabel:'Labour Market Indicators'},
  trade:{indicators:['agri_exports','merchandise_exports','tradeBalance'],commodities:[],chartLabel:'Trade Indicators'},
  construction:{indicators:['building_permits','construction_price_index'],commodities:['lumber','steel'],chartLabel:'Construction Indicators'},
  agriculture:{indicators:['agri_exports','wheat','canola'],commodities:['wheat','corn','soybeans','canola','sugar','coffee','cattle'],chartLabel:'Agricultural Commodities'},
  defence:{indicators:[],commodities:[],chartLabel:'Defence Projects'},
  education:{indicators:[],commodities:[],chartLabel:'Education Projects'}
};

// Map themes to timeseries keys for historical line charts (national fallback)
const THEME_TIMESERIES_MAP={
  energy:[{key:'wti',label:'WTI Crude Oil',unit:'USD/bbl'},{key:'natural_gas',label:'Natural Gas',unit:'USD/MMBtu'}],
  mining:[{key:'gold',label:'Gold',unit:'USD/oz'},{key:'copper',label:'Copper',unit:'USD/lb'}],
  agriculture:[{key:'wheat',label:'Wheat',unit:'USD/bu'},{key:'soybeans',label:'Soybeans',unit:'USD/bu'}],
  trade:[{key:'cadusd',label:'CAD/USD',unit:''}],
  housing:[{key:'boc_rate',label:'BoC Rate',unit:'%'}],
  labour:[],
  manufacturing:[{key:'aluminum',label:'Aluminum',unit:'USD/lb'},{key:'copper',label:'Copper',unit:'USD/lb'}],
  construction:[{key:'lumber',label:'Lumber',unit:'USD/MBF'}],
  transport:[],
  healthcare:[],
  defence:[],
  education:[]
};

// Province-specific timeseries overrides — keyed by province code
// Each returns {entries:[...], title:'...'} for province-specific descriptive titles.
const PROV_THEME_TS={
  _common:{
    labour:function(c){return[{key:c+'_unemployment',label:'Unemployment Rate',unit:'%'},{key:c+'_cpi',label:'CPI',unit:'%'}]},
    housing:function(c){return[{key:c+'_unemployment',label:'Unemployment Rate',unit:'%'}]},
    construction:function(c){return[{key:c+'_cpi',label:'CPI',unit:'%'}]}
  },
  ON:{
    trade:function(){return[{key:'ON_on_exports',label:'Exports',unit:'$M'},{key:'ON_on_imports',label:'Imports',unit:'$M'}]},
    manufacturing:function(){return[{key:'ON_on_gdp_goods',label:'Goods GDP',unit:'$M'}]},
    construction:function(){return[{key:'ON_on_real_capital_investment',label:'Capital Investment',unit:'$M'}]},
    housing:function(){return[{key:'ON_on_real_household',label:'Household Spending',unit:'$M'},{key:'ON_unemployment',label:'Unemployment Rate',unit:'%'}]}
  },
  QC:{
    trade:function(){return[{key:'QC_qc_exports',label:'Exports',unit:'$M'},{key:'QC_qc_imports',label:'Imports',unit:'$M'}]},
    manufacturing:function(){return[{key:'QC_qc_manufacturing_sales',label:'Manufacturing Sales',unit:'$M'}]},
    construction:function(){return[{key:'QC_qc_bldg_permits_res',label:'Residential Permits',unit:'$M'},{key:'QC_qc_bldg_permits_nonres',label:'Non-Res Permits',unit:'$M'}]},
    housing:function(){return[{key:'QC_qc_housing_starts',label:'Housing Starts',unit:'units'},{key:'QC_unemployment',label:'Unemployment Rate',unit:'%'}]},
    labour:function(){return[{key:'QC_qc_unemployment_rate',label:'Unemployment Rate',unit:'%'},{key:'QC_qc_employment',label:'Employment',unit:'000s'}]}
  }
};

// Resolve the best timeseries entries for a theme + optional province code
function resolveThemeTimeseries(themeId,provCode){
  if(provCode){
    const provMap=PROV_THEME_TS[provCode];
    if(provMap&&provMap[themeId])return provMap[themeId](provCode);
    const common=PROV_THEME_TS._common;
    if(common&&common[themeId])return common[themeId](provCode);
  }
  return THEME_TIMESERIES_MAP[themeId]||[];
}

/* == Infographic Library — multiple chart types per data strategy == */
// Each renderer returns a Chart instance or null. The system rotates through
// available renderers so adjacent charts in the same strip never repeat a shape.

// Centralized design tokens — matches the dashboard CSS exactly
const _ic={
  // Text hierarchy (from CSS vars and editorial styles)
  prussian:'#003153',heading:'#1a2744',body:'#2d3a52',muted:'#475569',light:'#64748B',faint:'#94A3B8',
  // Accent (from --accent-blue and link color)
  accent:'#2563EB',accentSoft:'#60A5FA',
  // Semantic (chart positive/negative — matches palCat and existing _renderCommodityChart)
  pos:'#10B981',neg:'#EF4444',
  // Grid/border (from existing charts and CSS)
  grid:'rgba(0,0,0,0.04)',gridSoft:'rgba(0,0,0,0.06)',border:'rgba(0,0,0,0.08)',
  // Background
  white:'#fff',
  // Shared font
  font:'DM Sans',
  // palCat from _chartCfg (blue-first editorial palette)
  pal:['#2563EB','#10B981','#F59E0B','#8B5CF6','#EC4899','#EF4444','#0EA5E9','#84CC16','#94A3B8'],
  // Title config factory
  ttl:function(text){return{display:true,text:text,font:{family:'DM Sans',size:11,weight:600},color:'#1a2744'}},
  // Axis tick config factory
  tk:function(sz,wt){return{font:{family:'DM Sans',size:sz||9,weight:wt||400},color:'#475569'}},
  tkLabel:function(sz){return{font:{family:'DM Sans',size:sz||9,weight:500},color:'#1a2744'}},
  // Legend config factory
  leg:function(pos){return{position:pos||'right',labels:{boxWidth:10,padding:6,font:{family:'DM Sans',size:9},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}}},
  // Generate opacity variants of a hex color for fills
  alphas:function(hex,levels){return(levels||['E6','B3','80','59','33']).map(a=>hex+a)},
  // Safe alpha for status colors (converts hex to rgba)
  hexAlpha:function(hex,a){
    const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
    return'rgba('+r+','+g+','+b+','+a+')';
  }
};

const _insightLib={
  // --- Commodity renderers (% change data) ---
  commodity:[
    // 0: Vertical diverging columns
    function(canvas,labels,vals,dm,theme,_cfg){
      return new Chart(canvas,{type:'bar',data:{labels,datasets:[{data:vals,backgroundColor:vals.map(v=>v>=0?_ic.pos:_ic.neg),borderRadius:6,barPercentage:0.7,borderSkipped:false}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel+' \u2014 Weekly Change'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}},annotation:{annotations:{zeroLine:{type:'line',yMin:0,yMax:0,borderColor:_ic.faint,borderWidth:1,borderDash:[3,3]}}}},scales:{y:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted,callback:v=>(v>=0?'+':'')+v+'%'}},x:{grid:{display:false},ticks:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading,maxRotation:45,minRotation:0}}}}});
    },
    // 1: Horizontal bar
    function(canvas,labels,vals,dm,theme,_cfg){
      return new Chart(canvas,{type:'bar',data:{labels,datasets:[{data:vals,backgroundColor:vals.map(v=>v>=0?_ic.pos:_ic.neg),borderRadius:4,barPercentage:0.65}]},
        options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel+' \u2014 Weekly Change'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}}},scales:{x:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted,callback:v=>(v>=0?'+':'')+v+'%'}},y:{grid:{display:false},ticks:_ic.tkLabel(9)}}}});
    },
    // 2: Lollipop (thin stems + dots)
    function(canvas,labels,vals,dm,theme,_cfg){
      return new Chart(canvas,{type:'bar',data:{labels,datasets:[
        {data:vals,backgroundColor:vals.map(v=>v>=0?_ic.pos:_ic.neg),borderRadius:6,barPercentage:0.12,borderSkipped:false,order:2},
        {type:'line',data:vals,pointRadius:6,pointBackgroundColor:vals.map(v=>v>=0?_ic.pos:_ic.neg),pointBorderColor:_ic.white,pointBorderWidth:2,borderWidth:0,showLine:false,order:1}
      ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel+' \u2014 Weekly Change'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}},annotation:{annotations:{zeroLine:{type:'line',yMin:0,yMax:0,borderColor:_ic.faint,borderWidth:1,borderDash:[3,3]}}}},scales:{y:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted,callback:v=>(v>=0?'+':'')+v+'%'}},x:{grid:{display:false},ticks:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading,maxRotation:45,minRotation:0}}}}});
    },
    // 3: Radar (absolute values, green/red dots show direction)
    function(canvas,labels,vals,dm,theme,_cfg){
      const absVals=vals.map(v=>Math.abs(v));
      return new Chart(canvas,{type:'radar',data:{labels,datasets:[{data:absVals,backgroundColor:_ic.hexAlpha(_ic.accent,0.1),borderColor:_ic.accent,borderWidth:2,pointBackgroundColor:vals.map(v=>v>=0?_ic.pos:_ic.neg),pointRadius:5,pointBorderColor:_ic.white,pointBorderWidth:1.5}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel+' \u2014 |Weekly Change|'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>{const orig=vals[ctx.dataIndex];return(orig>=0?'+':'')+orig.toFixed(1)+'%'}}}},scales:{r:{angleLines:{color:_ic.gridSoft},grid:{color:_ic.gridSoft},ticks:{display:false},pointLabels:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading}}}}});
    },
    // 4: Line chart — connected points with green/red segment coloring
    function(canvas,labels,vals,dm,theme,_cfg){
      return new Chart(canvas,{type:'line',data:{labels,datasets:[{data:vals,borderColor:_ic.accent,backgroundColor:_ic.hexAlpha(_ic.accent,0.06),borderWidth:2.5,pointRadius:5,pointBackgroundColor:vals.map(v=>v>=0?_ic.pos:_ic.neg),pointBorderColor:_ic.white,pointBorderWidth:2,fill:true,tension:0.3}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel+' \u2014 Weekly Change'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}},annotation:{annotations:{zeroLine:{type:'line',yMin:0,yMax:0,borderColor:_ic.faint,borderWidth:1,borderDash:[3,3]}}}},scales:{y:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted,callback:v=>(v>=0?'+':'')+v+'%'}},x:{grid:{display:false},ticks:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading,maxRotation:45,minRotation:0}}}}});
    }
  ],

  // --- Indicator renderers (current values) ---
  // All receive (canvas, raw, norm, dm, theme, _cfg) where raw=original values, norm=0-100 scaled
  indicator:[
    // 0: Polar area — uses normalized data so different-scale indicators look proportional
    function(canvas,raw,norm,dm,theme,_cfg){
      const polarColors=_ic.alphas(_ic.accent);
      return new Chart(canvas,{type:'polarArea',data:{labels:norm.map(m=>m.label),datasets:[{data:norm.map(m=>m.value),backgroundColor:polarColors.slice(0,norm.length),borderColor:_ic.white,borderWidth:2}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:_ic.leg('right'),title:_ic.ttl(dm.chartLabel),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+fmtNum(norm[ctx.dataIndex].rawValue)}}},scales:{r:{grid:{color:_ic.gridSoft},ticks:{display:false},pointLabels:{display:false}}}}});
    },
    // 1: Radar — uses normalized data, tooltips show real values
    function(canvas,raw,norm,dm,theme,_cfg){
      return new Chart(canvas,{type:'radar',data:{labels:norm.map(m=>m.label),datasets:[{data:norm.map(m=>m.value),backgroundColor:_ic.hexAlpha(_ic.accent,0.08),borderColor:_ic.accent,borderWidth:2,pointBackgroundColor:_ic.accent,pointRadius:4,pointBorderColor:_ic.white,pointBorderWidth:1.5,fill:true}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+fmtNum(norm[ctx.dataIndex].rawValue)}}},scales:{r:{angleLines:{color:_ic.gridSoft},grid:{color:_ic.gridSoft},ticks:{display:false},pointLabels:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading}}}}});
    },
    // 2: Horizontal bar — uses raw values (same axis, labels show magnitude)
    function(canvas,raw,norm,dm,theme,_cfg){
      return new Chart(canvas,{type:'bar',data:{labels:raw.map(m=>m.label),datasets:[{data:raw.map(m=>m.value),backgroundColor:_ic.hexAlpha(_ic.accent,0.7),borderRadius:4,barPercentage:0.65}]},
        options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel),tooltip:{..._cfg.tt,callbacks:{label:ctx=>fmtNum(ctx.raw)}}},scales:{x:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted}},y:{grid:{display:false},ticks:_ic.tkLabel(9)}}}});
    },
    // 3: Doughnut — uses normalized data so slice sizes are meaningful
    function(canvas,raw,norm,dm,theme,_cfg){
      return new Chart(canvas,{type:'doughnut',data:{labels:norm.map(m=>m.label),datasets:[{data:norm.map(m=>m.value),backgroundColor:_ic.pal.slice(0,norm.length),borderColor:_ic.white,borderWidth:2,hoverOffset:6}]},
        options:{responsive:true,maintainAspectRatio:false,cutout:'55%',plugins:{legend:_ic.leg('right'),title:_ic.ttl(dm.chartLabel),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+fmtNum(norm[ctx.dataIndex].rawValue)}}}}});
    },
    // 4: Line chart — uses raw values, good for showing relative levels across indicators
    function(canvas,raw,norm,dm,theme,_cfg){
      return new Chart(canvas,{type:'line',data:{labels:raw.map(m=>m.label),datasets:[{data:raw.map(m=>m.value),borderColor:_ic.accent,backgroundColor:_ic.hexAlpha(_ic.accent,0.08),borderWidth:2.5,pointBackgroundColor:_ic.accent,pointRadius:5,pointBorderColor:_ic.white,pointBorderWidth:2,fill:true,tension:0.3}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(dm.chartLabel),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+fmtNum(ctx.raw)}}},scales:{y:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted}},x:{grid:{display:false},ticks:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading}}}}});
    }
  ],

  // --- Pipeline renderers (project counts by status) ---
  pipeline:[
    // 0: Doughnut with center text
    function(canvas,labels,data,colors,meta,theme,_cfg,key){
      const centerPlugin={id:'ct_'+key,afterDraw(chart){const{ctx:c,chartArea:{top,bottom,left,right}}=chart;const cx=(left+right)/2,cy=(top+bottom)/2;c.save();c.textAlign='center';c.textBaseline='middle';c.font='600 20px '+_ic.font;c.fillStyle=_ic.heading;c.fillText(meta.total,cx,cy-8);c.font='500 10px '+_ic.font;c.fillStyle=_ic.light;c.fillText('projects',cx,cy+8);if(meta.valStr){c.font='500 9px '+_ic.font;c.fillStyle=_ic.faint;c.fillText(meta.valStr,cx,cy+22)}c.restore()}};
      return new Chart(canvas,{type:'doughnut',data:{labels,datasets:[{data,backgroundColor:colors,borderWidth:2,borderColor:_ic.white,hoverOffset:6}]},
        options:{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{legend:_ic.leg('right'),title:_ic.ttl(theme.label+' Pipeline'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+ctx.raw+' projects'}}}},
        plugins:[centerPlugin]});
    },
    // 1: Horizontal bar
    function(canvas,labels,data,colors,meta,theme,_cfg){
      return new Chart(canvas,{type:'bar',data:{labels,datasets:[{data,backgroundColor:colors,borderRadius:4,barPercentage:0.7}]},
        options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(theme.label+' Pipeline ('+meta.total+(meta.valStr?' \u00b7 '+meta.valStr:'')+')'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.raw+' projects'}}},scales:{x:{grid:{display:false},ticks:{font:{family:_ic.font,size:9},color:_ic.muted,stepSize:1}},y:{grid:{display:false},ticks:_ic.tkLabel(9)}}}});
    },
    // 2: Pie
    function(canvas,labels,data,colors,meta,theme,_cfg){
      return new Chart(canvas,{type:'pie',data:{labels,datasets:[{data,backgroundColor:colors,borderColor:_ic.white,borderWidth:2,hoverOffset:6}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:_ic.leg('right'),title:_ic.ttl(theme.label+' Pipeline ('+meta.total+')'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+ctx.raw+' projects'}}}}});
    },
    // 3: Polar area (status colors at 80% opacity via rgba)
    function(canvas,labels,data,colors,meta,theme,_cfg){
      return new Chart(canvas,{type:'polarArea',data:{labels,datasets:[{data,backgroundColor:colors.map(c=>_ic.hexAlpha(c,0.8)),borderColor:_ic.white,borderWidth:2}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:_ic.leg('right'),title:_ic.ttl(theme.label+' Pipeline ('+meta.total+')'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.label+': '+ctx.raw+' projects'}}},scales:{r:{grid:{color:_ic.gridSoft},ticks:{display:false}}}}});
    },
    // 4: Vertical bar
    function(canvas,labels,data,colors,meta,theme,_cfg){
      return new Chart(canvas,{type:'bar',data:{labels,datasets:[{data,backgroundColor:colors,borderRadius:6,barPercentage:0.7}]},
        options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},title:_ic.ttl(theme.label+' Pipeline ('+meta.total+(meta.valStr?' \u00b7 '+meta.valStr:'')+')'),tooltip:{..._cfg.tt,callbacks:{label:ctx=>ctx.raw+' projects'}}},scales:{y:{grid:{color:_ic.grid},ticks:{font:{family:_ic.font,size:9},color:_ic.muted,stepSize:1}},x:{grid:{display:false},ticks:{font:{family:_ic.font,size:8,weight:500},color:_ic.heading,maxRotation:45,minRotation:0}}}}});
    }
  ]
};

// --- Data-aware renderer selection ---
// Each fitness function returns renderer indices ordered variety-first.
// Radial/circular charts come before bar charts so the picker reaches them.

// Commodity: % change values
// 0=vertical bar, 1=horizontal bar, 2=lollipop, 3=radar, 4=line
function _commFit(count){
  if(count>=5)return [3,4,2,0,1]; // radar, line, lollipop, then bars — max variety
  if(count>=3)return [3,2,4,0,1]; // radar, lollipop, line, then bars
  return [4,2,0,1]; // line, lollipop, then bars for 2 items
}

// Indicator: independent measurements — radar/polar use normalized 0-100 data
// so scale disparity is handled visually; tooltips show real values.
// 0=polar area, 1=radar, 2=horizontal bar, 3=doughnut, 4=line
function _indFit(count){
  if(count>=4)return [0,1,4,3,2]; // polar, radar, line, doughnut, bar
  if(count>=3)return [1,0,4,3,2]; // radar, polar, line, doughnut, bar
  return [4,3,2]; // line, doughnut, bar for 2 items
}

// Normalize indicator values to 0-100 range for radial chart display.
// Returns [{label, value (normalized 0-100), rawValue (original)}]
function _normalizeInd(matched){
  const vals=matched.map(m=>m.value);
  const mx=Math.max(...vals),mn=Math.min(...vals);
  const range=mx-mn||1;
  return matched.map(m=>({label:m.label,value:10+((m.value-mn)/range)*90,rawValue:m.value,prov:m.prov||''}));
}

// Pipeline: status counts are parts of a whole — radial always makes sense
// 0=doughnut, 1=horizontal bar, 2=pie, 3=polar area, 4=vertical bar
function _pipeFit(count){
  if(count>=3)return [0,3,2,4,1]; // doughnut, polar, pie first
  if(count===2)return [0,2,1,4]; // doughnut, pie, then bars
  return [1,4]; // single status — bar only
}

// Cycling picker — walks through the suitable array so each call gets the next type
let _insightCursor={commodity:0,indicator:0,pipeline:0};

function _pickFromFit(suitable,strategyKey){
  const idx=_insightCursor[strategyKey]%suitable.length;
  _insightCursor[strategyKey]++;
  return suitable[idx];
}

async function renderInsightCharts(prefix,themes,projects,provCode,analysisText){
  if(!themes||!themes.length)return;
  const theme=themes[0];
  const canvasId=prefix+'Insight0';
  const canvas=document.getElementById(canvasId);
  if(!canvas)return;
  const key='_insight_'+canvasId;
  if(charts[key]){charts[key].destroy();delete charts[key]}

  const tsEntries=resolveThemeTimeseries(theme.id,provCode||null);
  if(!tsEntries.length){
    canvas.parentElement.insertAdjacentHTML('beforeend','<div style="text-align:center;color:'+_ic.light+';font-size:var(--text-xs);padding:24px">No historical data available for this theme</div>');
    return;
  }

  // Load all timeseries for this theme
  const allTs=await fetchJSON('timeseries.json').catch(()=>({}));
  const datasets=[];
  const lineColors=[_ic.accent,_ic.pos];
  let allLabels=[];
  let primaryData=null,primaryLabel='';

  tsEntries.forEach((entry,idx)=>{
    let raw=allTs[entry.key];
    if(!raw||!raw.length)return;
    const series=Array.isArray(raw)?raw:raw.series||[];
    if(!series.length)return;
    const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    const filtered=series.filter(p=>new Date(p.date)>=cutoff).sort((a,b)=>new Date(a.date)-new Date(b.date));
    if(!filtered.length)return;
    const labels=filtered.map(p=>fmtDate(p.date));
    const data=filtered.map(p=>p.value);
    if(labels.length>allLabels.length)allLabels=labels;
    if(!primaryData){primaryData=data;primaryLabel=entry.label}
    const c=lineColors[idx%lineColors.length];
    const isPrimary=datasets.length===0;
    datasets.push({
      label:entry.label+(entry.unit?' ('+entry.unit+')':''),
      data:data,
      borderColor:c,
      backgroundColor:isPrimary?_ic.hexAlpha(c,0.05):'transparent',
      borderWidth:isPrimary?2.5:2,
      pointRadius:data.map((_,i)=>i===data.length-1?5:0),
      pointBackgroundColor:c,
      pointBorderColor:_ic.white,
      pointBorderWidth:2,
      fill:isPrimary,
      tension:0.35,
      yAxisID:isPrimary?'y':'y1'
    });
  });

  if(!datasets.length){
    canvas.parentElement.insertAdjacentHTML('beforeend','<div style="text-align:center;color:'+_ic.light+';font-size:var(--text-xs);padding:24px">No historical data available for this theme</div>');
    return;
  }

  // Update the title with a narrative description based on actual data trend
  const titleEl=document.getElementById(prefix+'InsightTitle');
  if(titleEl&&primaryData){
    const narrative=_buildNarrativeTitle(primaryLabel,primaryData,analysisText||'',theme._matchedKw||theme.keywords||[]);
    titleEl.textContent=narrative;
  }

  // Economist-style scales: thin left axis border, light horizontal gridlines, no vertical grid
  const needDualAxis=datasets.length>=2;
  const scales={
    x:{
      border:{display:true,color:_ic.prussian,width:1},
      grid:{display:false},
      ticks:{maxTicksLimit:8,font:{family:_ic.font,size:10},color:_ic.prussian,padding:10}
    },
    y:{
      position:'left',
      border:{display:true,color:_ic.prussian,width:1},
      grid:{color:_ic.gridSoft,lineWidth:0.5,drawTicks:false},
      ticks:{font:{family:_ic.font,size:10},color:_ic.prussian,padding:14,callback:v=>fmtNum(v)}
    }
  };
  if(needDualAxis){
    scales.y1={
      position:'right',
      border:{display:true,color:_ic.prussian,width:1},
      grid:{display:false},
      ticks:{font:{family:_ic.font,size:10},color:_ic.prussian,padding:14,callback:v=>fmtNum(v)}
    };
  }

  // Event annotations
  const evtAnnotations={};
  try{
    if(D&&(D.watchlist||D.events)){
      const wl=D.watchlist||D.events||[];
      wl.filter(e=>(e.impact||'').toLowerCase()==='high').forEach((evt,i)=>{
        try{
          const ed=parseEvtDate(evt.date);if(!ed)return;
          const ds=fmtDate(ed);const li=allLabels.indexOf(ds);if(li===-1)return;
          evtAnnotations['evt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(0,49,83,0.25)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(evt.event_name||evt.name||'').substring(0,20),position:'start',backgroundColor:'rgba(0,49,83,0.8)',color:_ic.white,font:{family:_ic.font,size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
        }catch(e2){}
      });
    }
  }catch(e3){}
  const hasAnnotation=typeof window.ChartAnnotation!=='undefined'||Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation');
  const annotationCfg=hasAnnotation&&Object.keys(evtAnnotations).length?{annotation:{annotations:{...evtAnnotations}}}:{};

  // Endpoint label plugin
  const endpointPlugin={id:'insightEndpoint_'+prefix,afterDraw(chart){
    datasets.forEach((ds,di)=>{
      const meta=chart.getDatasetMeta(di);
      const lastPt=meta.data[meta.data.length-1];
      if(!lastPt)return;
      const lastVal=ds.data[ds.data.length-1];
      const ctx=chart.ctx;
      ctx.save();
      ctx.font='600 11px '+_ic.font;
      ctx.fillStyle=ds.borderColor;
      ctx.textAlign=di===0?'left':'right';
      ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):lastVal,lastPt.x+(di===0?6:-6),lastPt.y-8);
      ctx.restore();
    });
  }};

  // Legend config — dual-axis shows (left) / (right) indicators with colored swatches
  const legendCfg=needDualAxis?{
    display:true,position:'top',align:'start',
    labels:{
      boxWidth:14,boxHeight:3,padding:18,
      font:{family:_ic.font,size:11,weight:'500'},
      color:_ic.prussian,
      usePointStyle:false,
      generateLabels:function(chart){
        return chart.data.datasets.map(function(ds,i){
          const axis=i===0?'left axis':'right axis';
          return{text:ds.label+' ('+axis+')',fillColor:ds.borderColor,strokeColor:ds.borderColor,lineWidth:2,fontColor:ds.borderColor,hidden:false,datasetIndex:i};
        });
      }
    }
  }:{display:false};

  charts[key]=new Chart(canvas,{
    type:'line',
    data:{labels:allLabels,datasets:datasets},
    plugins:[endpointPlugin],
    options:{
      responsive:true,
      maintainAspectRatio:false,
      layout:{padding:{top:10,right:50,bottom:6,left:10}},
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:legendCfg,
        tooltip:{
          backgroundColor:'rgba(0,49,83,0.92)',
          titleColor:'#fff',
          titleFont:{family:_ic.font,size:11,weight:'600'},
          bodyColor:'#CBD5E1',
          bodyFont:{family:_ic.font,size:11},
          padding:12,
          cornerRadius:4,
          borderColor:'rgba(0,49,83,0.15)',
          borderWidth:1,
          displayColors:needDualAxis,
          boxWidth:8,boxHeight:2,
          callbacks:{label:ctx=>ctx.dataset.label+': '+fmtNum(ctx.raw)}
        },
        ...annotationCfg
      },
      scales:scales
    }
  });
}

function deriveSubtitle(analysisText){
  if(!analysisText)return '';
  const clean=(analysisText||'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  const m=clean.match(/^(.+?[.!?])\s/);
  if(m&&m[1].length<=120)return m[1];
  if(clean.length<=100)return clean;
  const cut=clean.substring(0,100).replace(/\s+\S*$/,'');
  return cut+(cut.length<clean.length?'...':'');
}

/* ── National: build 6-col indicator table HTML (scoped design) ── */
function _natIndTable(flag,title,indRows,srcLine){
  var html='<div class="indicator-panel">';
  html+='<div class="indicator-panel-header"><div class="indicator-panel-title"><span class="flag">'+flag+'</span> '+title+'</div>';
  if(srcLine)html+='<span style="font-size:11px;color:#7a8599">'+srcLine+'</span>';
  html+='</div>';
  html+='<table class="dash-ind-table"><thead><tr><th>Indicator</th><th>Value</th><th>Change</th><th>Reference Period</th><th>Next Release</th><th>Source</th></tr></thead><tbody>';
  indRows.forEach(function(r){
    var chg=r.change||'';
    var cls='';
    if(chg){
      var s=String(chg);
      if(s.indexOf('\u25B2')!==-1||s.indexOf('\u2191')!==-1||s.startsWith('+'))cls='chg-up';
      else if(s.indexOf('\u25BC')!==-1||s.indexOf('\u2193')!==-1||s.startsWith('-')||s.startsWith('\u2212'))cls='chg-down';
      else cls='chg-flat';
    }else{cls='chg-flat';chg='\u2014'}
    var freqTag=r.freq?'<span class="ind-freq">'+r.freq+'</span>':'';
    html+='<tr><td class="ind-name">'+r.label+freqTag+'</td>';
    html+='<td class="ind-val">'+fmtNum(r.value)+'</td>';
    html+='<td class="'+cls+'">'+chg+'</td>';
    html+='<td class="ind-period">'+(r.period||'')+'</td>';
    html+='<td class="ind-period">'+(r.nextRelease||'')+'</td>';
    html+='<td class="ind-source">'+(r.source||'')+'</td></tr>';
  });
  html+='</tbody></table></div>';
  return html;
}
function _natSourcesSection(sources){
  if(!sources||!sources.length)return '';
  var html='<details class="dash-sources-section"><summary>Sources ('+sources.length+')</summary><ol>';
  sources.forEach(function(s){
    var url=s.url||s.archive_url||'';
    var title=(s.title||'Source');
    if(url)html+='<li><a href="'+url+'" target="_blank" rel="noopener noreferrer">'+title+'</a></li>';
    else html+='<li>'+title+'</li>';
  });
  html+='</ol></details>';
  return html;
}
function _natNarrative(text,sources){
  if(!text)return '';
  var processed=san(linkFootnotes(text,sources||[]));
  return '<div class="dash-narrative">'+processed+'</div>';
}
function _initCanadaInsightChart(canvasId){
  var canvas=document.getElementById(canvasId);if(!canvas)return;
  var key='_natCaChart';if(charts[key]){charts[key].destroy();delete charts[key]}
  fetchJSON('timeseries.json').then(function(allTs){
    var raw=allTs['unemployment_rate']||allTs['unemployment']||null;if(!raw)return;
    var series=Array.isArray(raw)?raw:(raw.series||[]);if(!series.length)return;
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    var filtered=series.filter(function(p){return new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
    if(filtered.length<3)return;
    var labels=filtered.map(function(p){return fmtDate(p.date)});
    var data=filtered.map(function(p){return p.value});
    var refVal=data[data.length-1]||6.7;
    charts[key]=new Chart(canvas,{type:'line',data:{labels:labels,datasets:[
      {label:'Unemployment Rate',data:data,borderColor:'#003153',backgroundColor:'rgba(0,49,83,0.10)',fill:true,tension:0.35,borderWidth:2.5,pointRadius:0,pointHoverRadius:5,pointHoverBackgroundColor:'#003153',pointHoverBorderColor:'#fff',pointHoverBorderWidth:2},
      {label:'Current ('+fmtNum(refVal)+'%)',data:Array(data.length).fill(refVal),borderColor:'#c4320a',borderWidth:1,borderDash:[4,3],pointRadius:0,pointHoverRadius:0,fill:false}
    ]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#00253f',titleFont:{family:'DM Sans',size:11,weight:'600'},bodyFont:{family:'DM Sans',size:12},padding:10,cornerRadius:6,displayColors:false,filter:function(item){return item.datasetIndex===0}}},scales:{x:{grid:{display:false},ticks:{font:{family:'DM Sans',size:11,weight:'500'},color:'#4a5568'},border:{color:'#9aa5b4'}},y:{grid:{display:false},ticks:{font:{family:'DM Sans',size:11,weight:'500'},color:'#4a5568',callback:function(v){return v+'%'}},border:{display:false}}}}});
  }).catch(function(e){console.warn('Canada insight chart:',e)});
}
var _globalChartInited={};
function _initGlobalInsightChart(countryKey,canvasId){
  if(_globalChartInited[countryKey])return;_globalChartInited[countryKey]=true;
  var cfg=GLOBAL_CHART_CFG[countryKey];if(!cfg)return;
  var canvas=document.getElementById(canvasId);if(!canvas)return;
  var chartKey='_natGlobal_'+countryKey;if(charts[chartKey]){charts[chartKey].destroy();delete charts[chartKey]}
  fetchJSON('timeseries.json').then(function(allTs){
    var raw=allTs[cfg.tsKey]||null;if(!raw)return;
    var series=Array.isArray(raw)?raw:(raw.series||[]);if(!series.length)return;
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    var filtered=series.filter(function(p){return new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
    if(filtered.length<3)return;
    var labels=filtered.map(function(p){return fmtDate(p.date)});var data=filtered.map(function(p){return p.value});
    var datasets=[{label:cfg.title.split(' \u2014')[0]||cfg.title,data:data,borderColor:cfg.color,backgroundColor:cfg.fillColor,fill:true,tension:0.35,borderWidth:2.5,pointRadius:0,pointHoverRadius:5,pointHoverBackgroundColor:cfg.color,pointHoverBorderColor:'#fff',pointHoverBorderWidth:2}];
    if(cfg.refLine){datasets.push({label:cfg.refLine.label,data:Array(data.length).fill(cfg.refLine.value),borderColor:cfg.refLine.color,borderWidth:1,borderDash:[4,3],pointRadius:0,pointHoverRadius:0,fill:false})}
    charts[chartKey]=new Chart(canvas,{type:'line',data:{labels:labels,datasets:datasets},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#00253f',titleFont:{family:'DM Sans',size:11,weight:'600'},bodyFont:{family:'DM Sans',size:12},padding:10,cornerRadius:6,displayColors:false,filter:function(item){return item.datasetIndex===0}}},scales:{x:{grid:{display:false},ticks:{font:{family:'DM Sans',size:11,weight:'500'},color:'#4a5568'},border:{color:'#9aa5b4'}},y:{grid:{display:false},ticks:{font:{family:'DM Sans',size:11,weight:'500'},color:'#4a5568'},border:{display:false}}}}});
  }).catch(function(e){console.warn('Global insight chart '+countryKey+':',e)});
}
async function _renderCanadaSubtab(){
  var el=$('natContent-canada');if(!el)return;
  var m=(D&&D.metrics)||{};var im=(D&&D.indicatorMeta)||{};
  function indVal(name){var i=indicators.find(function(x){return x.indicator_name===name});return i?i.value:null}
  function indRec(name,prov){return indicators.find(function(x){return x.indicator_name===name&&(!prov||(x.province||'').toLowerCase()===prov.toLowerCase())})||indicators.find(function(x){return x.indicator_name===name})||null}
  function indMeta(name){return(im&&im[name])||{}}
  function chg(metaKey,indName){return pick(indMeta(metaKey).change,computeChange(indName||metaKey,'national'))}
  var _rBoc=indRec('overnight_rate','national'),_rGdp=indRec('realGdp','national'),_rCpi=indRec('cpi','national'),_rUnemp=indRec('unemployment','national'),_rHs=indRec('housingStarts','national'),_rCad=indRec('cad_usd','national')||indRec('cadusd','national');
  var natPart=indicators.find(function(x){return x.indicator_name==='participationRate'&&(x.province||'').toLowerCase()==='national'});

  var natIndicators=[
    {label:'BoC Rate',value:pick(m.bocRate,m.boc_rate,indVal('overnight_rate')),change:chg('bocRate','overnight_rate'),source:indSource(_rBoc,'Bank of Canada'),period:indBasis(_rBoc,indMeta('bocRate').period,'scheduled'),freq:'8x/yr',nextRelease:''},
    {label:'Real GDP YoY',value:pick(m.realGdp,m.gdp,indVal('realGdp'),indVal('gdp')),change:pick(chg('realGdp','realGdp'),m.realGdp||''),source:indSource(_rGdp,'Statistics Canada'),period:indBasis(_rGdp,indMeta('realGdp').period,'quarterly'),freq:'Quarterly',nextRelease:''},
    {label:'CPI Inflation',value:pick(m.cpi,indVal('cpi'),indVal('cpi_national')),change:pick(chg('cpi','cpi'),m.cpi||''),source:indSource(_rCpi,'Statistics Canada'),period:indBasis(_rCpi,indMeta('cpi').period,'monthly'),freq:'Monthly',nextRelease:''},
    {label:'Unemployment Rate',value:pick(m.unemployment,indVal('unemployment'),indVal('unemployment_national')),change:chg('unemployment','unemployment'),source:indSource(_rUnemp,'Statistics Canada'),period:indBasis(_rUnemp,indMeta('unemployment').period,'monthly'),freq:'Monthly',nextRelease:''},
    {label:'Employment Change',value:pick(m.employmentChange,indVal('employment_change')),change:computeChange('employment_change','national'),source:'StatCan 14-10-0287',period:indBasis(indRec('employment_change','national'),'','monthly'),freq:'Monthly',nextRelease:''},
    {label:'Participation Rate',value:pick(natPart&&natPart.value,m.participation,indVal('participationRate')),change:computeChange('participationRate','national'),source:indSource(natPart,'Statistics Canada'),period:indBasis(natPart,'','monthly'),freq:'Monthly',nextRelease:''},
    {label:'Housing Starts',value:pick(m.housingStarts,m.housing_starts,indVal('housingStarts')),change:chg('housingStarts','housingStarts'),source:indSource(_rHs,'CMHC'),period:indBasis(_rHs,indMeta('housingStarts').period,'monthly'),freq:'Monthly',nextRelease:''},
    {label:'Building Permits',value:pick(indVal('building_permits')),change:computeChange('building_permits','national'),source:'StatCan 34-10-0066',period:indBasis(indRec('building_permits','national'),'','monthly'),freq:'Monthly',nextRelease:''}
  ];
  var natProjects=[];
  try{var d=await fetchJSON('projects_all.json');natProjects=Array.isArray(d)?d:[]}catch(e){}
  var projTotal=natProjects.length||allProjects.length||0;
  var ds=D&&D.discovery_stats||{};
  var newPrj=ds.new_this_week||D&&D.new_projects||0;
  var pipVal=ds.total_value_billions||D&&D.pipeline_value||'';
  var natContent=(D&&D.national&&D.national.analysis)||D&&D.national_analysis||'';
  var natSources=(D&&D.national&&D.national.sources)||[];
  var allSources=natSources.length?natSources:(D&&D.sources||[]);
  var html='';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>National Analysis</h3></div>';
  if(natContent){html+=_natNarrative(natContent,allSources)}else{html+='<div class="dash-narrative"><p style="color:#7a8599">National analysis available after next pipeline run.</p></div>'}
  html+='<div class="insight-chart-wrapper"><div class="insight-chart-title">Unemployment Rate \u2014 12-Month Trend</div><div class="insight-chart-subtitle">Seasonally adjusted</div><div class="chart-wrap"><canvas id="natChartCaUnemployment"></canvas></div><div class="chart-source">Source: Statistics Canada, Table 14-10-0287</div></div>';
  html+=_natSourcesSection(allSources);
  html+='</div>';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Policy Developments</h3><span class="section-meta" id="natPolicyMeta"></span></div><div id="natPolicyNarrative"></div><div id="natPolicyAccordion"></div></div>';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Key Indicators &amp; Sector Signals</h3><span class="section-meta">'+natIndicators.length+' indicators</span></div>';
  html+=_natIndTable('\uD83C\uDDE8\uD83C\uDDE6','Canada \u2014 National',natIndicators,'');
  html+='<div id="natEnrichmentCards" class="two-col"></div></div>';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Project Pipeline \u2014 Canada</h3><span class="section-meta">'+projTotal+' tracked'+(pipVal?' \u00b7 $'+pipVal+'B total value':'')+'</span></div>';
  if(newPrj||natProjects.length){
    var topProjects=natProjects.filter(function(p){return parseNumericValue(p.value)>0}).sort(function(a,b){return parseNumericValue(b.value)-parseNumericValue(a.value)}).slice(0,5);
    if(newPrj){html+='<div class="dash-narrative" style="margin-bottom:16px"><p style="font-size:15px;line-height:1.7"><span class="lead">The pipeline added '+newPrj+' new projects this week.</span></p></div>'}
    if(topProjects.length){
      html+='<div class="inner-card" style="padding:0;overflow:hidden"><table class="dash-projects-table"><thead><tr><th>Project</th><th>Province</th><th>Sector</th><th>Value</th><th>Status</th></tr></thead><tbody>';
      topProjects.forEach(function(p){
        var sectorName=_normSector(p.sector);var stClass='status-proposed';var stLabel=p.status||'Proposed';
        if(stLabel.toLowerCase().indexOf('construction')!==-1)stClass='status-construction';
        else if(stLabel.toLowerCase().indexOf('review')!==-1)stClass='status-review';
        else if(stLabel.toLowerCase().indexOf('pre')!==-1||stLabel.toLowerCase().indexOf('approved')!==-1)stClass='status-pre';
        html+='<tr><td style="font-weight:500">'+((p.name||'').substring(0,55))+'</td><td>'+normProvince(p.province)+'</td><td>'+sectorName+'</td><td style="font-variant-numeric:tabular-nums">'+fmtCurrency(p.value,p)+'</td><td><span class="dash-status-badge '+stClass+'">'+stLabel+'</span></td></tr>';
      });
      html+='</tbody></table><button class="dash-footer-link" onclick="switchTab(\'projects\')">View all '+projTotal+' projects \u2192</button></div>';
    }
  }else{html+='<div style="text-align:center;padding:32px;color:#7a8599;font-size:13px">No projects loaded yet.</div>'}
  html+='</div>';
  el.innerHTML=html;
  _initCanadaInsightChart('natChartCaUnemployment');
  _renderNatPolicySection();
  _renderNatEnrichmentCards(natProjects);
}
async function _renderNatPolicySection(){
  try{
    var result=await _loadPolicyData();var items=result.items||[];var narrative=result.narrative||'';
    var metaEl=$('natPolicyMeta');var narEl=$('natPolicyNarrative');var accEl=$('natPolicyAccordion');
    if(!items.length&&!narrative){if(metaEl)metaEl.textContent='';if(accEl)accEl.innerHTML='<div style="color:#7a8599;font-size:13px;padding:12px 0">No policy developments tracked this week.</div>';return}
    var fedCount=0,provCount=0,regCount=0;
    items.forEach(function(a){var level=a.level||'federal';if(level==='federal')fedCount++;else if(level==='regulatory')regCount++;else provCount++});
    var metaParts=[];metaParts.push(items.length+' item'+(items.length!==1?'s':''));
    if(fedCount)metaParts.push(fedCount+' federal');if(provCount)metaParts.push(provCount+' provincial');if(regCount)metaParts.push(regCount+' regulatory');
    if(metaEl)metaEl.textContent=metaParts.join(' \u00b7 ');
    if(narEl&&narrative){narEl.innerHTML='<div class="dash-narrative" style="margin-bottom:16px"><p style="font-size:15px;line-height:1.7">'+narrative+'</p></div>'}
    if(accEl){
      var html='<div class="inner-card">';
      items.slice(0,8).forEach(function(a,i){
        var title=a.title||a.headline||'Untitled';var summary=a.summary||'';var url=a.url||'#';var srcDesc=a.source_description||a.source||'';
        html+='<details class="policy-item"'+(i<3?' open':'')+'><summary>'+title+'</summary><div class="policy-body">';
        if(summary)html+=summary.substring(0,300)+(summary.length>300?'...':'');
        if(srcDesc)html+=' <em style="font-size:11px;color:#7a8599">('+srcDesc+')</em>';
        if(url&&url!=='#')html+=' <a href="'+url+'" target="_blank" rel="noopener noreferrer" class="policy-link">View source \u2192</a>';
        html+='</div></details>';
      });
      accEl.innerHTML=html+'</div>';
    }
  }catch(e){console.warn('National policy section:',e)}
}
async function _renderNatEnrichmentCards(projects){
  var el=$('natEnrichmentCards');if(!el)return;var m=(D&&D.metrics)||{};
  var comms={};try{var cd=await fetchJSON('commodities.json');if(cd&&cd.indicators)comms=cd.indicators;else if(cd&&typeof cd==='object')comms=cd}catch(e){}
  var html='';
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Labour Market</div>';
  [{label:'Employment Change',key:'employmentChange',alt:'employment_change'},{label:'Full-time',key:'fulltime_change'},{label:'Part-time',key:'parttime_change'},{label:'Private Sector',key:'private_sector_change'},{label:'Public Sector',key:'public_sector_change'}].forEach(function(f){
    var val=pick(m[f.key],f.alt?m[f.alt]:null);if(!hasVal(val))val='\u2014';
    var cls='';if(String(val).startsWith('+')||String(val).startsWith('\u2191'))cls='chg-up';else if(String(val).startsWith('-')||String(val).startsWith('\u2212')||String(val).startsWith('\u2193'))cls='chg-down';
    html+='<div class="enrichment-metric"><span class="label">'+f.label+'</span><span class="value'+(cls?' '+cls:'')+'">'+fmtNum(val)+'</span></div>';
  });
  html+='</div>';
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Consumer Pulse</div>';
  [{label:'CPI (All-items)',key:'cpi'},{label:'Core CPI (Median)',key:'core_cpi_median',alt:'coreCpi'},{label:'Shelter',key:'shelter_cpi'},{label:'Food',key:'food_cpi'},{label:'Energy',key:'energy_cpi'}].forEach(function(f){
    var val=pick(m[f.key],f.alt?m[f.alt]:null);if(!hasVal(val))val='\u2014';
    html+='<div class="enrichment-metric"><span class="label">'+f.label+'</span><span class="value">'+fmtNum(val)+'</span></div>';
  });
  html+='</div>';
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Housing &amp; Construction</div>';
  [{label:'Housing Starts (SAAR)',key:'housingStarts',alt:'housing_starts'},{label:'Building Permits',key:'building_permits'},{label:'Residential Permits',key:'residential_permits'},{label:'Non-Residential Permits',key:'nonresidential_permits'},{label:'Active Residential Projects',computed:function(){return projects.filter(function(p){return(p.sector||'').toLowerCase()==='residential'}).length||'\u2014'}}].forEach(function(f){
    var val=f.computed?f.computed():pick(m[f.key],f.alt?m[f.alt]:null);if(!hasVal(val))val='\u2014';
    html+='<div class="enrichment-metric"><span class="label">'+f.label+'</span><span class="value">'+fmtNum(val)+'</span></div>';
  });
  html+='</div>';
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Trade &amp; Commodities</div>';
  var wtiVal=comms.wti?comms.wti.current:pick(m.wti);var cadVal=pick(m.cadUsd,m.cad_usd);
  [{label:'Merchandise Exports',val:pick(m.merchandise_exports)},{label:'Merchandise Imports',val:pick(m.merchandise_imports)},{label:'Trade Balance',val:pick(m.tradeBalance,m.trade_balance)},{label:'WTI Crude',val:wtiVal},{label:'CAD/USD',val:cadVal}].forEach(function(f){
    html+='<div class="enrichment-metric"><span class="label">'+f.label+'</span><span class="value">'+(hasVal(f.val)?fmtNum(f.val):'\u2014')+'</span></div>';
  });
  html+='</div>';
  var jobData=null;try{jobData=await fetchJSON('jobs.json')}catch(e){}
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Hiring Signals</div>';
  if(jobData&&jobData.spikes&&jobData.spikes.length){
    var spikeTexts=jobData.spikes.slice(0,3).map(function(s){return '<strong>'+(s.sector||s.industry||'')+(s.change?' ('+s.change+')':'')+' </strong>'+(s.cma||s.region||'')});
    html+='<p>'+spikeTexts.length+' hiring spike'+(spikeTexts.length!==1?'s':'')+' detected this week: '+spikeTexts.join(', ')+'.</p>';
  }else{html+='<p>No hiring spikes detected this week.</p>'}
  html+='</div>';
  var procData=null;try{procData=await fetchJSON('procurement.json')}catch(e){}
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Procurement Awards</div>';
  if(procData&&procData.awards&&procData.awards.length){
    var totalVal=procData.awards.reduce(function(s,a){return s+(parseNumericValue(a.value)||0)},0);
    var valStr=totalVal>=1e9?'$'+(totalVal/1e9).toFixed(1)+'B':totalVal>=1e6?'$'+(totalVal/1e6).toFixed(0)+'M':'$'+totalVal.toLocaleString();
    html+='<p>Federal government awarded <strong>'+valStr+'</strong> in infrastructure contracts this week across '+procData.awards.length+' award'+(procData.awards.length!==1?'s':'')+'.</p>';
  }else{html+='<p>No procurement awards tracked this week.</p>'}
  html+='</div>';
  el.innerHTML=html;
}
async function _renderGlobalSubtab(key){
  var el=$('natContent-'+key);if(!el)return;
  var gv=D?D.globalVectors||D.global_vectors||{}:{};var globalArr=D?D.global||[]:[];
  var REGION_MAP={'United States':'us','China':'china','European Union':'eu','United Kingdom':'uk'};
  var FREQ_MAP={gdp:'Quarterly',cpi:'Monthly',rate:'Periodic',unemployment:'Monthly',tradeBalance:'Monthly',productivityGrowth:'Quarterly'};
  var SRC_MAP={us:{gdp:'BEA',cpi:'BLS',rate:'Federal Reserve',unemployment:'BLS',tradeBalance:'Census Bureau',productivityGrowth:'BLS'},china:{gdp:'NBS',cpi:'NBS',rate:'PBOC',unemployment:'NBS',tradeBalance:'GAC',productivityGrowth:'NBS'},eu:{gdp:'Eurostat',cpi:'Eurostat',rate:'ECB',unemployment:'Eurostat',tradeBalance:'Eurostat',productivityGrowth:'S&P Global'},uk:{gdp:'ONS',cpi:'ONS',rate:'BoE',unemployment:'ONS',tradeBalance:'ONS',productivityGrowth:'LSE'}};
  var countryInfo=COUNTRY_SUBTABS.find(function(t){return t.key===key})||{label:key,flag:''};
  var gData=globalArr.find(function(g){return REGION_MAP[g.region]===key})||{};
  var analysis=gData.analysis||gv[key]||'';var gi=gData.indicators||{};var giMeta=gData.indicatorMeta||{};var srcs=SRC_MAP[key]||{};
  if(!analysis&&!hasVal(gi.gdp)&&!hasVal(gi.cpi)&&!hasVal(gi.rate)&&!hasVal(gi.unemployment)){
    el.innerHTML='<div style="text-align:center;padding:48px;color:#7a8599;font-size:14px">'+countryInfo.label+' analysis will be available after the next pipeline run.</div>';return;
  }
  var indRows=[];
  [{key:'gdp',label:'GDP Growth (Real)'},{key:'cpi',label:'CPI Inflation'},{key:'rate',label:'Policy Rate'},{key:'unemployment',label:'Unemployment Rate'},{key:'tradeBalance',label:'Trade Balance'},{key:'productivityGrowth',label:'Productivity Growth'}].forEach(function(x){
    var gm=giMeta[x.key]||{};var per=hasVal(gm.period)?fmtPeriod(gm.period):(FREQ_MAP[x.key]||'');var val=pick(gi[x.key]);
    var chgVal=hasVal(gm.change)?gm.change:'';
    if(!chgVal&&val&&typeof val==='string'&&val.match(/^[+-]?\d/)&&val.indexOf('%')!==-1)chgVal=val;
    indRows.push({label:x.label,value:val,change:chgVal,source:srcs[x.key]||'',period:per,freq:FREQ_MAP[x.key]||'',nextRelease:hasVal(gm.nextRelease)?gm.nextRelease:''});
  });
  var html='';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>'+countryInfo.label+' Analysis</h3></div>';
  if(analysis){html+=_natNarrative(analysis,gData.sources||[])}else{html+='<div class="dash-narrative"><p style="color:#7a8599">Analysis available after next pipeline run.</p></div>'}
  var chartCfg=GLOBAL_CHART_CFG[key];
  if(chartCfg){var chartId='natChart_'+key;html+='<div class="insight-chart-wrapper"><div class="insight-chart-title">'+chartCfg.title+'</div><div class="insight-chart-subtitle">'+chartCfg.subtitle+'</div><div class="chart-wrap"><canvas id="'+chartId+'"></canvas></div><div class="chart-source">Source: '+chartCfg.source+'</div></div>'}
  html+=_natSourcesSection(gData.sources||[]);
  html+='</div>';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Key Indicators</h3><span class="section-meta">'+indRows.filter(function(r){return hasVal(r.value)}).length+' indicators</span></div>';
  html+=_natIndTable(countryInfo.flag,countryInfo.label,indRows,'Source: '+(GLOBAL_SRC_MAP[key]||''));
  html+='</div>';
  el.innerHTML=html;
  if(chartCfg){_initGlobalInsightChart(key,'natChart_'+key)}
}
async function _preRenderGlobalSubtabs(){
  var keys=['us','china','eu','uk'];
  for(var i=0;i<keys.length;i++){if(!_nationalSubRendered[keys[i]]){_nationalSubRendered[keys[i]]=true;await _renderGlobalSubtab(keys[i])}}
}
window.switchNationalSub=function(key){showNationalSubtab(key)};
function renderCanadaSub(){_renderCanadaSubtab()}
function renderGlobalPlayerSub(key){_renderGlobalSubtab(key)}
function renderAllGlobalPlayers(){_preRenderGlobalSubtabs()}
function collapseEmpty(){
  const panel=document.getElementById('tab-tldr');
  if(!panel)return;
  // Only hide the footer if both children are empty
  panel.querySelectorAll('.editorial-footer').forEach(row=>{
    const kids=[...row.children];
    const allEmpty=kids.every(c=>!c.innerHTML.trim());
    row.style.display=allEmpty?'none':'';
  });
}

/* ====== WOVEN CHARTS (rendered into specific containers) ====== */
const _chartCfg={tt:{backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8},fv:v=>v>=1e9?'$'+(v/1e9).toFixed(1)+'B':v>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+fmtNum(v,0),palCat:['#2563EB','#10B981','#F59E0B','#8B5CF6','#EC4899','#EF4444','#0EA5E9','#84CC16','#94A3B8']};
let _chartProjects=null,_chartComms=null;
async function _ensureChartData(){
  if(_chartProjects===null){try{const d=await fetchJSON('projects_all.json');_chartProjects=Array.isArray(d)?d:[]}catch(e){_chartProjects=[]}}
  if(_chartComms===null){try{const cd=await fetchJSON('commodities.json');if(Array.isArray(cd))_chartComms=cd;else if(cd&&cd.indicators&&typeof cd.indicators==='object')_chartComms=Object.entries(cd.indicators).map(([k,v])=>Object.assign({name:v.name||k.replace(/_/g,' ')},v)).filter(c=>c&&c.pct_1w);else _chartComms=Object.values(cd).flat().filter(c=>c&&typeof c==='object'&&c.pct_1w)}catch(e){_chartComms=[]}}
}
function _renderMacroChart(canvasId,cardId,prefix){
  if(!indicators.length)return;
  const macroKeys=[['unemployment','unemployment_rate','unemployment_national'],['cpi','cpi_national'],['realGdp','gdp_monthly'],['housingStarts','housing_starts_total'],['overnight_rate','boc_rate'],['employmentRate','participation_rate']];
  const macroLabels=['Unemployment','CPI','GDP','Housing Starts','BoC Rate','Employment Rate'];
  const found=[];
  macroKeys.forEach((alts,i)=>{
    let ind=null;
    for(const k of alts){ind=indicators.find(x=>x.indicator_name===k&&(!x.province||x.province==='National'||x.province==='national'));if(ind&&ind.value!=null)break}
    if(ind&&ind.value!=null)found.push({label:macroLabels[i],current:parseFloat(ind.value)||0,prev:parseFloat(ind.previous_value)||(parseFloat(ind.value)||0)})
  });
  if(found.length<2)return;
  const canvas=$(canvasId);if(!canvas)return;
  const card=$(cardId);if(card)card.style.display='';
  const key='_mc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart(canvas,{type:'bar',data:{labels:found.map(f=>f.label),datasets:[{label:'Current',data:found.map(f=>f.current),backgroundColor:'#2563EB',borderRadius:4,barPercentage:0.6},{label:'Previous',data:found.map(f=>f.prev),backgroundColor:'#CBD5E1',borderRadius:4,barPercentage:0.6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{boxWidth:10,padding:8,font:{family:'DM Sans',size:10},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>ctx.dataset.label+': '+fmtNum(ctx.raw)}}},scales:{x:{grid:{display:false},ticks:{font:{family:'DM Sans',size:9},color:'#475569'}},y:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'DM Sans',size:9},color:'#475569'}}}}});
}
function _renderCommodityChart(canvasId,cardId,prefix){
  const withPct=(_chartComms||[]).filter(c=>c.pct_1w&&c.pct_1w!=='N/A').map(c=>({name:(c.name||c.indicator_name||'').replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),pct:parseFloat(c.pct_1w)||0})).filter(c=>Math.abs(c.pct)>0.1);
  withPct.sort((a,b)=>Math.abs(b.pct)-Math.abs(a.pct));
  const top=withPct.slice(0,8);if(top.length<3)return;
  const canvas=$(canvasId);if(!canvas)return;
  const card=$(cardId);if(card)card.style.display='';
  const key='_cc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart(canvas,{type:'bar',data:{labels:top.map(c=>c.name),datasets:[{data:top.map(c=>c.pct),backgroundColor:top.map(c=>c.pct>=0?'#10B981':'#EF4444'),borderRadius:4,barPercentage:0.65}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}}},scales:{x:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'DM Sans',size:9},color:'#475569',callback:v=>(v>=0?'+':'')+v+'%'}},y:{grid:{display:false},ticks:{font:{family:'DM Sans',size:9,weight:500},color:'#1a2744'}}}}});
}
function _renderPipelineChart(canvasId,prefix,projPool){
  const projects=projPool||_chartProjects||[];if(!projects.length)return;
  const statusOrder=['Proposed','Under Review','Approved','Under Construction','Partially Complete','Complete','On Hold','Cancelled'];
  const statusColors=['#94A3B8','#60A5FA','#3B82F6','#2563EB','#1D4ED8','#15803D','#F59E0B','#EF4444'];
  const statusCounts={};projects.forEach(p=>{const s=p.status||'Proposed';statusCounts[s]=(statusCounts[s]||0)+1});
  const pL=[],pD=[],pC=[];statusOrder.forEach((s,i)=>{if(statusCounts[s]){pL.push(s);pD.push(statusCounts[s]);pC.push(statusColors[i])}});
  if(!pD.length)return;
  const key='_pl_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart($(canvasId),{type:'bar',data:{labels:pL,datasets:[{data:pD,backgroundColor:pC,borderRadius:6,barPercentage:0.7}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>fmtNum(ctx.raw,0)+' projects'}}},scales:{x:{grid:{display:false},ticks:{font:{family:'DM Sans',size:9},color:'#475569'}},y:{grid:{display:false},ticks:{font:{family:'DM Sans',size:9,weight:500},color:'#1a2744'}}}}});
}
function _renderSectorChart(canvasId,prefix,projPool){
  const projects=projPool||_chartProjects||[];if(!projects.length)return;
  const sectorVal={},sectorCnt={};projects.forEach(p=>{const s=p.sector||'Other';const v=parseNumericValue(p.value);sectorVal[s]=(sectorVal[s]||0)+v;sectorCnt[s]=(sectorCnt[s]||0)+1});
  const sorted=Object.entries(sectorVal).sort((a,b)=>b[1]-a[1]);
  const top8=sorted.slice(0,8);const ov=sorted.slice(8).reduce((s,e)=>s+e[1],0);
  if(ov>0)top8.push(['Other',ov]);if(!top8.length)return;
  const key='_sc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart($(canvasId),{type:'doughnut',data:{labels:top8.map(e=>e[0].replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())),datasets:[{data:top8.map(e=>e[1]),backgroundColor:_chartCfg.palCat.slice(0,top8.length),borderWidth:0,hoverOffset:6}]},options:{responsive:true,maintainAspectRatio:false,cutout:'55%',plugins:{legend:{position:'right',labels:{boxWidth:10,padding:6,font:{family:'DM Sans',size:9},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>ctx.label+': '+_chartCfg.fv(ctx.raw)}}}}});
  // Description under the chart
  const descEl=$(canvasId+'Desc');
  if(descEl){
    const totalVal=top8.reduce((s,e)=>s+e[1],0);
    const totalProj=projects.length;
    const topSector=top8[0]?top8[0][0].replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()):'';
    const topPct=totalVal>0?((top8[0][1]/totalVal)*100).toFixed(0):'0';
    const topCnt=sectorCnt[top8[0]?top8[0][0]:'']||0;
    const secCount=sorted.length;
    descEl.textContent=totalProj+' tracked projects across '+secCount+' sectors totaling '+_chartCfg.fv(totalVal)+'. '+topSector+' leads at '+topPct+'% of pipeline value ('+topCnt+' projects).';
  }
}
async function renderWovenCharts(ctx,projPool){
  await _ensureChartData();
  const p=ctx;
  _renderMacroChart(p+'MacroChart',p+'MacroCard',p);
  _renderCommodityChart(p+'CommodityChart',p+'CommodityCard',p);
  if($(p+'PipelineChart'))_renderPipelineChart(p+'PipelineChart',p,projPool);
  if($(p+'SectorChart'))_renderSectorChart(p+'SectorChart',p,projPool);
}


/* == Indicator Dropdown (reused in Overview + Provinces) == */
function renderIndicatorDropdown(inds,title,idSuffix){
  const id='indDropdown'+(idSuffix||'');const filtId='indFilter'+(idSuffix||'');
  const n=inds.length;
  let html='<div class="indicator-dropdown"><button class="indicator-dropdown-toggle" onclick="this.classList.toggle(\x27open\x27);this.nextElementSibling.classList.toggle(\x27open\x27)">'+title+' <span class="chevron">\u25be</span></button>';
  html+='<div class="indicator-dropdown-body" id="'+id+'"><input class="indicator-filter" id="'+filtId+'" placeholder="Filter indicators..." oninput="filterIndicators(\x27'+id+'\x27,\x27'+filtId+'\x27)">';
  const groups={};
  inds.forEach(ind=>{
    const cat=ind.category||categorizeIndicator(ind.name);
    if(!groups[cat])groups[cat]=[];
    groups[cat].push(ind);
  });
  const groupOrder=['GDP by Industry','Labour Market','Housing','Trade','Monetary & Financial','Other'];
  groupOrder.forEach(g=>{
    const items=groups[g];if(!items||!items.length)return;
    html+='<div class="indicator-group-header">'+g+'</div>';
    items.forEach(ind=>{
      const cls=ind.arrow===1?'change-up':ind.arrow===2?'change-down':'change-flat';
      const chgTxt=ind.change?changeIcon(ind.arrow)+' '+ind.change:'';
      html+='<div class="indicator-row" data-name="'+(ind.name||'').toLowerCase()+'"><div class="indicator-row-name">'+(ind.name||'')+'</div><div class="indicator-row-value">'+(ind.value||'N/A')+'</div><div class="indicator-row-change '+cls+'">'+chgTxt+'</div><div class="indicator-row-period">'+(ind.refPer||'')+'</div><div class="indicator-row-source">'+(ind.tableUrl?'<a href="'+ind.tableUrl+'" target="_blank">\u2197</a>':'')+'</div></div>';
    });
  });
  Object.keys(groups).filter(g=>!groupOrder.includes(g)).forEach(g=>{
    const items=groups[g];if(!items||!items.length)return;
    html+='<div class="indicator-group-header">'+g+'</div>';
    items.forEach(ind=>{
      const cls=ind.arrow===1?'change-up':ind.arrow===2?'change-down':'change-flat';
      html+='<div class="indicator-row" data-name="'+(ind.name||'').toLowerCase()+'"><div class="indicator-row-name">'+(ind.name||'')+'</div><div class="indicator-row-value">'+(ind.value||'N/A')+'</div><div class="indicator-row-change '+cls+'">'+(ind.change?changeIcon(ind.arrow)+' '+ind.change:'')+'</div><div class="indicator-row-period">'+(ind.refPer||'')+'</div><div class="indicator-row-source">'+(ind.tableUrl?'<a href="'+ind.tableUrl+'" target="_blank">\u2197</a>':'')+'</div></div>';
    });
  });
  html+='</div></div>';
  return html;
}
function categorizeIndicator(name){
  const n=(name||'').toLowerCase();
  if(n.includes('gross domestic product')||n.includes('gdp'))return 'GDP by Industry';
  if(n.includes('employ')||n.includes('labour')||n.includes('job')||n.includes('wage'))return 'Labour Market';
  if(n.includes('housing')||n.includes('building permit')||n.includes('new house'))return 'Housing';
  if(n.includes('trade')||n.includes('export')||n.includes('import')||n.includes('merchandise'))return 'Trade';
  if(n.includes('interest')||n.includes('yield')||n.includes('monetary')||n.includes('bank rate')||n.includes('consumer price')||n.includes('cpi')||n.includes('inflation'))return 'Monetary & Financial';
  return 'Other';
}
window.filterIndicators=function(dropId,filtId){
  const val=document.getElementById(filtId).value.toLowerCase();
  document.querySelectorAll('#'+dropId+' .indicator-row').forEach(r=>{
    r.style.display=r.dataset.name.includes(val)?'':'none';
  });
};


/* == Interactive Indicator Explorer == */
const INDICATOR_CATALOG=[
  {group:'Rates',items:[
    {id:'overnight_rate',label:'BoC Overnight Rate',unit:'%',source:'Bank of Canada',url:'https://www.bankofcanada.ca/rates/interest-rates/key-interest-rates/',prov:false},
    {id:'prime_rate',label:'Prime Rate',unit:'%',source:'Bank of Canada',url:'https://www.bankofcanada.ca/rates/interest-rates/',prov:false},
    {id:'goc_5y_yield',label:'5Y GoC Yield',unit:'%',source:'Bank of Canada',url:'https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/',prov:false},
    {id:'goc_10y_yield',label:'10Y GoC Yield',unit:'%',source:'Bank of Canada',url:'https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/',prov:false},
    {id:'goc_2y_yield',label:'2Y GoC Yield',unit:'%',source:'Bank of Canada',url:'https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/',prov:false}
  ]},
  {group:'Prices',items:[
    {id:'cpi',label:'CPI (All Items)',unit:'%',source:'Statistics Canada',statcan:true,prov:true},
    {id:'wti',label:'WTI Crude Oil',unit:'USD/bbl',source:'Yahoo Finance',url:'https://finance.yahoo.com/quote/CL%3DF/',prov:false},
    {id:'gold',label:'Gold',unit:'USD/oz',source:'Yahoo Finance',url:'https://finance.yahoo.com/quote/GC%3DF/',prov:false},
    {id:'cadusd',label:'CAD/USD',unit:'',source:'Bank of Canada',url:'https://www.bankofcanada.ca/rates/exchange/',prov:false}
  ]},
  {group:'Labour',items:[
    {id:'unemployment',label:'Unemployment Rate',unit:'%',source:'Statistics Canada',statcan:true,prov:true}
  ]},
  {group:'Activity',items:[
    {id:'realGdp',label:'Real GDP (Q/Q)',unit:'%',source:'Statistics Canada',statcan:true,prov:false},
    {id:'housingStarts',label:'Housing Starts',unit:'K',source:'CMHC',url:'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research',prov:false}
  ]},
  {group:'Markets',items:[
    {id:'tsx',label:'S&P/TSX Composite',unit:'',source:'Yahoo Finance',url:'https://finance.yahoo.com/quote/%5EGSPTSE/',prov:false},
    {id:'lumber',label:'Lumber',unit:'USD',source:'Yahoo Finance',url:'https://finance.yahoo.com/quote/LBS%3DF/',prov:false}
  ]}
];

let _indExpData={},_indExpSel='overnight_rate',_indExpRange=12,_indExpProv='national';

function renderIndicatorExplorer(){
  // Build selector
  let selHtml='<div class="exp-card fade-in"><div class="exp-card-title">Indicator Explorer</div><div class="exp-card-sub">Chart any indicator with a configurable time window</div><div class="exp-control-row">';
  selHtml+='<select id="indExpSelect" class="exp-select" onchange="onIndExpChange()">';
  INDICATOR_CATALOG.forEach(g=>{
    selHtml+='<optgroup label="'+g.group+'">';
    g.items.forEach(it=>{
      selHtml+='<option value="'+it.id+'"'+(it.id===_indExpSel?' selected':'')+'>'+it.label+'</option>';
    });
    selHtml+='</optgroup>';
  });
  selHtml+='</select>';
  // Province toggle (shown only for provincial indicators)
  const selItem=findIndItem(_indExpSel);
  if(selItem&&selItem.prov){
    selHtml+='<select id="indExpProv" class="exp-select" onchange="onIndExpChange()">';
    selHtml+='<option value="national"'+((_indExpProv==='national')?' selected':'')+'>National</option>';
    PROVS.forEach(p=>{selHtml+='<option value="'+p.code+'"'+(_indExpProv===p.code?' selected':'')+'>'+p.name+'</option>'});
    selHtml+='</select>';
  }
  // Time range buttons
  selHtml+='<div class="exp-range-group">';
  [3,12,36,60].forEach(m=>{
    const lbl=m===3?'3M':m===12?'1Y':m===36?'3Y':'5Y';
    const active=_indExpRange===m?' active':'';
    selHtml+='<button class="exp-range-btn'+active+'" onclick="_indExpRange='+m+';loadIndExpData()">'+lbl+'</button>';
  });
  selHtml+='</div></div>';
  // Callout + chart
  selHtml+='<div id="indExpCallout"></div>';
  selHtml+='<div class="exp-chart-wrap"><canvas id="indExpCanvas"></canvas></div>';
  // Source link
  if(selItem){
    const linkUrl=selItem.statcan?'https://www150.statcan.gc.ca/n1/en/type/data':selItem.url||'#';
    const linkLabel=selItem.statcan?'View on StatsCan \u2197':selItem.source+' \u2197';
    selHtml+='<div class="exp-card-footlink"><a href="'+linkUrl+'" target="_blank" rel="noopener noreferrer">'+linkLabel+'</a></div>';
  }
  selHtml+='</div>';
  $('indicatorExplorer').innerHTML=selHtml;
  loadIndExpData();
}

function findIndItem(id){
  for(const g of INDICATOR_CATALOG)for(const it of g.items)if(it.id===id)return it;
  return null;
}

window.onIndExpChange=function(){
  _indExpSel=$('indExpSelect').value;
  const provSel=$('indExpProv');
  _indExpProv=provSel?provSel.value:'national';
  renderIndicatorExplorer();
};

async function loadIndExpData(){
  const item=findIndItem(_indExpSel);if(!item)return;
  const prov=item.prov?_indExpProv:'national';
  const cacheKey=_indExpSel+'_'+prov;

  if(!_indExpData[cacheKey]){
    try{
      const all=await fetchJSON('indicators.json');
      const history_list=all.history||all.indicators||all;
      const pts=(Array.isArray(history_list)?history_list:[])
        .filter(r=>(r.indicator_name||r.indicator)===_indExpSel&&(r.province||'national')===prov)
        .map(r=>({date:r.period||r.date,value:parseFloat(r.value)||0}))
        .sort((a,b)=>(a.date||'').localeCompare(b.date||''));
      _indExpData[cacheKey]=pts;
    }catch(e){console.error('Indicator history load:',e);_indExpData[cacheKey]=[]}
  }

  const allPts=_indExpData[cacheKey]||[];
  const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-_indExpRange);
  const pts=allPts.filter(p=>new Date(p.date)>=cutoff);

  // Callout
  const callout=$('indExpCallout');
  if(pts.length>=2){
    const latest=pts[pts.length-1];const prev=pts[pts.length-2];
    const diff=latest.value-prev.value;
    const arrow=diff>0?'\u25b2':diff<0?'\u25bc':'\u25cf';
    const cls=diff>0?'up':diff<0?'down':'flat';
    const allVals=allPts.map(p=>p.value);
    const mn=fmtNum(Math.min(...allVals));const mx=fmtNum(Math.max(...allVals));
    callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">'+fmtNum(latest.value)+'</span><span class="exp-callout-chg '+cls+'">'+arrow+' '+(diff>=0?'+':'')+fmtNum(diff)+' vs prev</span><span class="exp-callout-meta">5Y range: '+mn+' \u2013 '+mx+'</span><span class="exp-callout-meta">'+latest.date+'</span></div>';
  }else if(pts.length===1){
    callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">'+fmtNum(pts[0].value)+'</span></div>';
  }else{
    callout.innerHTML='<div class="exp-callout"><span class="exp-callout-empty">No data for this period.</span></div>';
  }

  // Chart
  const canvas=$('indExpCanvas');if(!canvas)return;
  if(charts._indExp)charts._indExp.destroy();
  if(!pts.length)return;
  const labels=pts.map(p=>p.date);
  const data=pts.map(p=>p.value);
  // Compute range band (25th-75th percentile) — filter non-numeric, avoid falsy-zero bug
  const numericData=data.filter(v=>typeof v==='number'&&!isNaN(v));
  const sorted=[...numericData].sort((a,b)=>a-b);
  const bandLow=sorted.length>0?sorted[Math.floor(sorted.length*0.25)]:null;
  const bandHigh=sorted.length>0?sorted[Math.floor(sorted.length*0.75)]:null;
  // Build event flag annotations from watchlist
  const evtAnnotations={};
  try{
    if(D&&(D.watchlist||D.events)){
      const wl=D.watchlist||D.events||[];
      wl.filter(e=>(e.impact||'').toLowerCase()==='high').forEach((evt,i)=>{
        try{
          const ed=parseEvtDate(evt.date);if(!ed)return;
          const ds=fmtDate(ed);const li=labels.indexOf(ds);if(li===-1)return;
          evtAnnotations['evt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(245,158,11,0.5)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(evt.event_name||evt.name||'').substring(0,20),position:'start',backgroundColor:'rgba(245,158,11,0.85)',color:'#fff',font:{family:'DM Sans',size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
        }catch(evtErr){}
      });
    }
  }catch(annErr){console.warn('Event annotations:',annErr)}
  const hasAnnotationPlugin=typeof window.ChartAnnotation!=='undefined'||(typeof Chart!=='undefined'&&Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation'));
  const bandAnnotation=(bandLow!==null&&bandHigh!==null)?{band:{type:'box',yMin:bandLow,yMax:bandHigh,backgroundColor:'rgba(59,130,246,0.06)',borderWidth:0}}:{};
  const annotationCfg=hasAnnotationPlugin?{annotation:{annotations:{...bandAnnotation,...evtAnnotations}}}:{};
  const endpointPlugin={id:'endpointLabel',afterDraw(chart){try{const ds=chart.data.datasets[0];if(!ds||!ds.data||!ds.data.length)return;const lastVal=ds.data[ds.data.length-1];if(lastVal==null)return;const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 11px DM Sans';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):String(lastVal),lastPt.x+6,lastPt.y-4);ctx.restore();}catch(e){}}};
  const chartCfg={type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.08)',borderWidth:2,pointRadius:pts.length>60?0:3,pointBackgroundColor:'#3B82F6',fill:true,tension:0.3}]},plugins:[endpointPlugin],options:{responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:'index'},plugins:{legend:{display:false},...annotationCfg,tooltip:{backgroundColor:'rgba(45,75,130,0.95)',titleColor:'#ffffff',bodyColor:'#93C5FD',borderColor:'rgba(255,255,255,0.12)',borderWidth:1,padding:10,cornerRadius:6,callbacks:{label:function(ctx){
    const val=ctx.parsed.y;const idx=ctx.dataIndex;
    if(idx>0){const prev=data[idx-1];const diff=val-prev;return fmtNum(val)+' ('+(diff>=0?'+':'')+fmtNum(diff)+' vs prev)';}
    return fmtNum(val);
  }}}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'DM Sans',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'DM Sans',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}};
  try{charts._indExp=new Chart(canvas,chartCfg);}catch(chartErr){console.warn('Chart with annotations failed, retrying without:',chartErr);try{chartCfg.options.plugins={legend:{display:false},tooltip:chartCfg.options.plugins.tooltip};chartCfg.plugins=[];charts._indExp=new Chart(canvas,chartCfg);}catch(e2){console.error('Chart creation failed completely:',e2);}}
}


function renderWordCloud(topics){
  const container=document.getElementById('wordCloudSvg');
  if(!container||!topics.length)return;
  const w=container.clientWidth||500,h=280;
  container.innerHTML='';
  const maxFreq=Math.max(...topics.map(t=>t.frequency||t.count||1));
  const words=topics.slice(0,80).map(t=>{
    const freq=t.frequency||t.count||1;
    const score=t.sentiment_score||t.sentiment||0;
    return{text:t.topic||t.word||'',size:12+((freq/maxFreq)*28),score:typeof score==='number'?score:0,freq};
  });
  const layout=d3.layout.cloud().size([w,h]).words(words).padding(6).rotate(()=>0).font('Arial').fontSize(d=>d.size).on('end',drawn);
  layout.start();
  function drawn(wds){
    const svg=d3.select(container).append('svg').attr('width',w).attr('height',h);
    const g=svg.append('g').attr('transform','translate('+w/2+','+h/2+')');
    g.selectAll('text').data(wds).enter().append('text')
      .style('font-size',d=>d.size+'px').style('font-family','DM Sans')
      .style('font-weight',d=>d.size>30?'700':d.size>20?'600':'400')
      .style('fill',d=>d.score>0.05?'#065F46':d.score<-0.05?'#991B1B':'#334155')
      .style('opacity',d=>0.5+Math.min(d.size/40,0.5))
      .style('cursor','pointer')
      .attr('text-anchor','middle').attr('transform',d=>'translate('+d.x+','+d.y+') rotate('+d.rotate+')')
      .text(d=>d.text)
      .append('title').text(d=>d.text+'\nSentiment: '+d.score.toFixed(2)+'\nFrequency: '+d.freq);
  }
}



/* ====== PROVINCES TAB ====== */
const PROV_NAMES={ON:'Ontario',QC:'Quebec',AB:'Alberta',BC:'British Columbia',SK:'Saskatchewan',MB:'Manitoba',NS:'Nova Scotia',NB:'New Brunswick',NL:'Newfoundland & Labrador',PE:'Prince Edward Island',YT:'Yukon',NT:'Northwest Territories',NU:'Nunavut'};
const PROV_SPECIFIC_INDICATORS={
  ON:[{label:'Auto Production (vehicles)',source:'DesRosiers Automotive',freq:'Monthly'},{label:'Toronto Home Price Index',source:'TRREB MLS HPI',freq:'Monthly'},{label:'Financial Services Employment',source:'StatCan 14-10-0022',freq:'Monthly'},{label:'Ring of Fire Mining Permits',source:'Ontario MNDM',freq:'Quarterly'}],
  QC:[{label:'Aerospace Exports',source:'StatCan 12-10-0129',freq:'Monthly'},{label:'Montreal Home Price Index',source:'QPAREB Centris',freq:'Monthly'},{label:'Hydro-Quebec Generation Capacity',source:'HQ',freq:'Quarterly'},{label:'AI/Tech Venture Capital',source:'CVCA',freq:'Quarterly'}],
  AB:[{label:'Oil Sands Production',source:'AER ST-39',freq:'Monthly'},{label:'WCS-WTI Differential',source:'Market',freq:'Daily'},{label:'Drilling Rig Count',source:'CAODC',freq:'Weekly'},{label:'Calgary Office Vacancy Rate',source:'CBRE',freq:'Quarterly'}],
  BC:[{label:'Port of Vancouver TEU Volume',source:'VFPA',freq:'Monthly'},{label:'Vancouver Home Price Index',source:'REBGV MLS HPI',freq:'Monthly'},{label:'Lumber Export Value',source:'StatCan 12-10-0129',freq:'Monthly'},{label:'Film/TV Production Spending',source:'CMPA',freq:'Quarterly'}],
  SK:[{label:'Potash Production Volume',source:'StatCan 16-10-0048',freq:'Monthly'},{label:'Crop Receipts',source:'StatCan 21-10-0019',freq:'Quarterly'},{label:'Uranium Mine Output',source:'CNSC',freq:'Quarterly'},{label:'Oil Production',source:'SK Gov',freq:'Monthly'}],
  MB:[{label:'Agriculture Receipts',source:'StatCan 21-10-0019',freq:'Quarterly'},{label:'Winnipeg CMA Employment',source:'StatCan 14-10-0384',freq:'Monthly'},{label:'Hydro Generation',source:'Manitoba Hydro',freq:'Monthly'},{label:'Manufacturing Sales',source:'StatCan 16-10-0048',freq:'Monthly'}],
  NS:[{label:'Shipbuilding Contracts Value',source:'Irving/PSC',freq:'Quarterly'},{label:'Halifax Home Price Index',source:'NSAR MLS',freq:'Monthly'},{label:'Seafood Export Value',source:'StatCan 12-10-0129',freq:'Monthly'},{label:'Tourism Visitors',source:'NS Tourism',freq:'Monthly'}],
  NB:[{label:'Forestry Output Value',source:'StatCan 16-10-0048',freq:'Monthly'},{label:'Saint John Refinery Throughput',source:'Irving Oil',freq:'Monthly'},{label:'Aquaculture Production',source:'DFO',freq:'Quarterly'},{label:'NB Power Generation',source:'NB Power',freq:'Monthly'}],
  NL:[{label:'Offshore Oil Production',source:'C-NLOPB',freq:'Monthly'},{label:'Muskrat Falls Generation',source:'NL Hydro',freq:'Monthly'},{label:'Mineral Shipments Value',source:'NL Gov',freq:'Quarterly'},{label:'Marine/Fishery Landings',source:'DFO',freq:'Quarterly'}],
  PE:[{label:'Potato Crop Value',source:'StatCan 21-10-0019',freq:'Quarterly'},{label:'Tourism Revenue',source:'PEI Tourism',freq:'Monthly'},{label:'Shellfish Aquaculture Volume',source:'DFO',freq:'Quarterly'},{label:'Population Growth Rate',source:'StatCan 17-10-0009',freq:'Quarterly'}],
  YT:[{label:'Mining Exploration Spending',source:'NRCan',freq:'Quarterly'},{label:'Placer Gold Production',source:'YT Mining',freq:'Quarterly'},{label:'Tourism Visitors',source:'YT Tourism',freq:'Monthly'},{label:'Federal Transfer Revenue',source:'YT Finance',freq:'Annual'}],
  NT:[{label:'Diamond Production Value',source:'GNWT',freq:'Quarterly'},{label:'Mining Exploration Spending',source:'NRCan',freq:'Quarterly'},{label:'Resource Royalties',source:'GNWT Finance',freq:'Quarterly'},{label:'Remediation Site Progress',source:'CIRNAC',freq:'Quarterly'}],
  NU:[{label:'Mining Exploration Spending',source:'NRCan',freq:'Quarterly'},{label:'Inuit Employment Rate',source:'StatCan 14-10-0364',freq:'Monthly'},{label:'Construction Investment',source:'StatCan 34-10-0175',freq:'Quarterly'},{label:'Federal Transfer Revenue',source:'NU Finance',freq:'Annual'}]
};
const PROV_ORDER=['ON','QC','AB','BC','SK','MB','NS','NB','NL','PE'];
const TERR_ORDER=['YT','NT','NU'];

function _provFindData(code){
  if(!D||!D.provinces)return null;
  const name=PROV_NAMES[code];
  const norm=s=>(s||'').toLowerCase().replace(/&/g,'and').replace(/[^a-z]/g,'');
  return D.provinces.find(p=>p.name===name||p.name===code||norm(p.name)===norm(name))||null;
}

function renderProvinces(){
  const container=$('provincesPage');
  if(!container)return;
  // Build sidebar
  let sidebarHtml='<nav class="prov-sidebar"><div class="prov-sidebar-title">Provinces</div>';
  PROV_ORDER.forEach(code=>{
    sidebarHtml+='<input type="radio" name="province" id="prov-'+code+'" value="'+code+'" class="prov-radio"'+(code===selectedProvince?' checked':'')+'>';
    sidebarHtml+='<label for="prov-'+code+'" class="prov-label">'+PROV_NAMES[code]+'</label>';
  });
  sidebarHtml+='<div class="prov-sidebar-title" style="margin-top:12px">Territories</div>';
  TERR_ORDER.forEach(code=>{
    sidebarHtml+='<input type="radio" name="province" id="prov-'+code+'" value="'+code+'" class="prov-radio"'+(code===selectedProvince?' checked':'')+'>';
    sidebarHtml+='<label for="prov-'+code+'" class="prov-label">'+PROV_NAMES[code]+'</label>';
  });
  sidebarHtml+='</nav>';

  container.innerHTML='<div class="prov-page">'+sidebarHtml+'<div class="prov-page-main" id="provMainContent"></div></div>';

  // Wire up radio change events
  container.querySelectorAll('.prov-radio').forEach(radio=>{
    radio.addEventListener('change',function(){
      selectedProvince=this.value;
      _renderProvContent();
    });
  });

  _renderProvContent();
}

async function _renderProvContent(){
  const code=selectedProvince;
  const provName=PROV_NAMES[code]||code;
  const mainEl=$('provMainContent');
  if(!mainEl)return;

  // Load province projects
  if(_lastLoadedProvince!==code){await loadProjects(code)}

  // Get province data from D
  const provData=_provFindData(code)||{};
  const provInd=provData.indicators||{};
  const provMeta=provData.indicatorMeta||{};
  const provPrefix=code.toLowerCase();
  const provSources=provData.sources||[];

  // Helper functions
  function provIndVal(key){
    const nameMap={gdp:'realGdp',unemployment:'unemployment',cpi:'cpi',housingStarts:'housingStarts',participationRate:'participationRate',employmentRate:'employmentRate',populationGrowth:'populationGrowth',buildingPermits:'buildingPermits',wageGrowth:'wageGrowth'};
    const indName=nameMap[key]||key;
    const provMatch=indicators.find(x=>x.indicator_name===provPrefix+'_'+indName);
    if(provMatch)return provMatch.value;
    const byProv=indicators.find(x=>x.indicator_name===indName&&(x.province||'').toLowerCase()===provName.toLowerCase());
    if(byProv)return byProv.value;
    return null;
  }
  function provIndRec(key){
    const nameMap={gdp:'realGdp',unemployment:'unemployment',cpi:'cpi',housingStarts:'housingStarts',participationRate:'participationRate',employmentRate:'employmentRate',populationGrowth:'populationGrowth',buildingPermits:'buildingPermits',wageGrowth:'wageGrowth'};
    const indName=nameMap[key]||key;
    return indicators.find(x=>x.indicator_name===provPrefix+'_'+indName)||indicators.find(x=>x.indicator_name===indName&&(x.province||'').toLowerCase()===provName.toLowerCase())||null;
  }
  function pchg(metaKey,indName,valFallback){
    const mc=(provMeta[metaKey]||{}).change;
    const cc=computeChange(indName||metaKey,provName);
    const vf=valFallback&&/^[+-]?\d/.test(String(valFallback))&&String(valFallback).includes('%')?String(valFallback):'';
    return pick(mc,cc,vf);
  }

  // Projects
  const provProj=allProjects.filter(p=>p.province===provName||p.province===code);
  const projCount=provProj.length;
  const projValue=provProj.reduce((s,p)=>s+parseNumericValue(p.value),0);
  const fmtVal=projValue>=1e9?'$'+(projValue/1e9).toFixed(1)+'B':projValue>=1e6?'$'+(projValue/1e6).toFixed(0)+'M':'N/A';
  const threshold=PROV_THRESHOLDS[code]||0;
  const thresholdStr=threshold>=1e9?'$'+(threshold/1e9).toFixed(0)+'B':threshold>=1e6?'$'+(threshold/1e6).toFixed(0)+'M':'$'+threshold;

  // New this week
  const now=new Date();
  const oneWeekAgo=new Date(now);oneWeekAgo.setDate(now.getDate()-7);
  const oneWeekStr=oneWeekAgo.toISOString().split('T')[0];
  const newThisWeek=provProj.filter(p=>p.firstTracked&&p.firstTracked>=oneWeekStr);

  // 8 universal indicators
  const _prGdp=provIndRec('gdp'),_prUn=provIndRec('unemployment'),_prCpi=provIndRec('cpi'),_prPart=provIndRec('participationRate'),_prEmp=provIndRec('employmentRate'),_prHs=provIndRec('housingStarts'),_prWage=provIndRec('wageGrowth'),_prBp=provIndRec('buildingPermits');
  const universalInds=[
    {label:'GDP Growth (Real)',freq:'Quarterly',value:pick(provInd.gdp,provIndVal('gdp')),change:pchg('gdp','realGdp',provInd.gdp),period:indBasis(_prGdp,(provMeta.gdp||{}).period,'quarterly'),source:'StatCan 36-10-0402'},
    {label:'Unemployment Rate',freq:'Monthly',value:pick(provInd.unemployment,provIndVal('unemployment')),change:pchg('unemployment','unemployment',provInd.unemployment),period:indBasis(_prUn,(provMeta.unemployment||{}).period,'monthly'),source:'StatCan 14-10-0287'},
    {label:'CPI Inflation',freq:'Monthly',value:pick(provInd.cpi,provIndVal('cpi')),change:pchg('cpi','cpi',provInd.cpi),period:indBasis(_prCpi,(provMeta.cpi||{}).period,'monthly'),source:'StatCan 18-10-0004'},
    {label:'Employment Rate',freq:'Monthly',value:pick(provInd.employmentRate,provIndVal('employmentRate')),change:pchg('employmentRate','employmentRate',provInd.employmentRate),period:indBasis(_prEmp,(provMeta.employmentRate||{}).period,'monthly'),source:'StatCan 14-10-0287'},
    {label:'Participation Rate',freq:'Monthly',value:pick(provInd.participationRate,provIndVal('participationRate')),change:pchg('participationRate','participationRate',provInd.participationRate),period:indBasis(_prPart,(provMeta.participationRate||{}).period,'monthly'),source:'StatCan 14-10-0287'},
    {label:'Wage Growth',freq:'Monthly',value:pick(provInd.wageGrowth,provIndVal('wageGrowth')),change:pchg('wageGrowth','wageGrowth',provInd.wageGrowth),period:indBasis(_prWage,'','monthly'),source:'StatCan 14-10-0287'},
    {label:'Housing Starts',freq:'Monthly',value:pick(provInd.housingStarts,provIndVal('housingStarts')),change:pchg('housingStarts','housingStarts'),period:indBasis(_prHs,(provMeta.housingStarts||{}).period,'monthly'),source:'CMHC'},
    {label:'Building Permits',freq:'Monthly',value:pick(provInd.buildingPermits,provIndVal('buildingPermits')),change:pchg('buildingPermits','buildingPermits'),period:indBasis(_prBp,(provMeta.buildingPermits||{}).period,'monthly'),source:'StatCan 34-10-0066'}
  ];

  // Change class helper
  function chgCls(c){
    if(!c||c==='N/A')return 'chg-flat';
    const s=String(c);
    if(s.includes('\u25B2')||s.startsWith('+'))return 'chg-up';
    if(s.includes('\u25BC')||s.startsWith('-')||s.startsWith('\u2212'))return 'chg-down';
    return 'chg-flat';
  }
  function chgText(c){
    if(!c||c==='N/A')return '\u2014 N/A';
    return String(c);
  }

  // Build indicator table rows
  function buildIndRows(inds){
    let rows='';
    inds.forEach(ind=>{
      const cls=chgCls(ind.change);
      rows+='<tr><td class="ind-name">'+san(ind.label)+'</td>';
      rows+='<td class="ind-freq">'+san(ind.freq||'')+'</td>';
      rows+='<td class="ind-val">'+san(ind.value||'N/A')+'</td>';
      rows+='<td class="'+cls+'">'+san(chgText(ind.change))+'</td>';
      rows+='<td class="ind-period">'+san(ind.period||'')+'</td>';
      rows+='<td class="ind-period">'+san(ind.nextRelease||'')+'</td>';
      rows+='<td class="ind-source">'+san(ind.source||'')+'</td></tr>';
    });
    return rows;
  }

  function buildIndTable(rows){
    return '<div class="indicator-panel"><table class="ind-table"><thead><tr>'+
      '<th>Indicator</th><th>Frequency</th><th>Value</th><th>Change</th><th>Reference Period</th><th>Next Release</th><th>Source</th>'+
      '</tr></thead><tbody>'+rows+'</tbody></table></div>';
  }

  // Province-specific indicators
  const specInds=PROV_SPECIFIC_INDICATORS[code]||[];
  const specIndData=specInds.map(si=>{
    const indKey=si.label.toLowerCase().replace(/[^a-z0-9]/g,'_');
    const rec=provIndRec(indKey);
    const fromMeta=(provMeta[indKey]||{});
    return {label:si.label,freq:si.freq,value:pick(fromMeta.value,rec&&rec.value),change:pick(fromMeta.change,rec?computeChange(rec.indicator_name,provName):null),period:pick(fromMeta.period,rec&&rec.period,''),nextRelease:pick(fromMeta.nextRelease,''),source:si.source};
  });

  // ── Build full HTML ──
  let html='';

  // Province Header Card
  html+='<div class="province-header-card"><div>';
  html+='<h2>'+san(provName)+'</h2>';
  html+='<div class="province-sub">Weekly provincial economic analysis &middot; GDP threshold: '+thresholdStr+'</div>';
  html+='</div><div class="province-header-stats">';
  html+='<div class="stat-item"><div class="stat-value">'+projCount+'</div><div class="stat-label">Active Projects</div></div>';
  html+='<div class="stat-item"><div class="stat-value">'+fmtVal+'</div><div class="stat-label">Pipeline Value</div></div>';
  html+='<div class="stat-item"><div class="stat-value">'+newThisWeek.length+'</div><div class="stat-label">New This Week</div></div>';
  html+='</div></div>';

  // Section 1: Provincial Analysis
  const provContent=provData.analysis||'';
  html+='<div class="section-block">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Provincial Analysis</h3></div>';
  if(provContent){
    html+='<div class="narrative">'+san(linkFootnotes(provContent,provSources.length?provSources:(D&&D.sources||[])))+'</div>';
  }else{
    html+='<div class="narrative"><p>No provincial analysis available for '+san(provName)+'.</p></div>';
  }
  // Insight chart container
  html+='<div id="provInsightChartArea"></div>';
  // Sources
  if(provSources.length){
    html+='<details class="sources-section"><summary>Sources ('+provSources.length+')</summary><ol>';
    provSources.forEach(s=>{
      const url=s.url||s.archive_url||'';
      const title=s.title||'Source';
      html+='<li>'+(url?'<a href="'+san(url)+'" target="_blank" rel="noopener noreferrer">'+san(title)+'</a>':san(title))+'</li>';
    });
    html+='</ol></details>';
  }
  html+='</div>';

  // Section 2: Policy Developments
  html+='<div class="section-block" id="provPolicySection">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Policy Developments</h3><span class="section-meta" id="provPolicyMeta"></span></div>';
  html+='<div id="provPolicyContent"></div>';
  html+='</div>';

  // Section 3: Key Indicators
  const indCount=8+specIndData.length;
  const genDate=D&&D.generated_at?D.generated_at.split('T')[0]:'';
  html+='<div class="section-block">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Key Indicators \u2014 '+san(provName)+'</h3>';
  html+='<span class="section-meta">'+indCount+' indicators'+(genDate?' &middot; Updated '+genDate:'')+'</span></div>';
  html+=buildIndTable(buildIndRows(universalInds));
  if(specIndData.length){
    html+='<h4 class="ind-section-label">'+san(provName)+'-Specific Indicators</h4>';
    html+=buildIndTable(buildIndRows(specIndData));
  }
  html+='</div>';

  // Section 4: Sector Signals
  html+='<div class="section-block">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Sector Signals</h3><span class="section-meta">4 sector categories</span></div>';
  html+='<div class="two-col">';

  // Sector Highlights card
  const sectorCounts={};
  const sectorValues={};
  provProj.forEach(p=>{
    const s=_normSector(p.sector)||'Other';
    sectorCounts[s]=(sectorCounts[s]||0)+1;
    sectorValues[s]=(sectorValues[s]||0)+parseNumericValue(p.value);
  });
  const topByCount=Object.entries(sectorCounts).sort((a,b)=>b[1]-a[1]);
  const topByValue=Object.entries(sectorValues).sort((a,b)=>b[1]-a[1]);
  const mostActiveThisWeek={};
  newThisWeek.forEach(p=>{const s=_normSector(p.sector)||'Other';mostActiveThisWeek[s]=(mostActiveThisWeek[s]||0)+1});
  const topActive=Object.entries(mostActiveThisWeek).sort((a,b)=>b[1]-a[1]);

  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Sector Highlights</div>';
  if(topByCount.length){
    html+='<div class="enrichment-metric"><span class="label">Largest Sector (by projects)</span><span class="value">'+san(topByCount[0][0])+' ('+topByCount[0][1]+')</span></div>';
  }
  if(topByValue.length){
    const vStr=topByValue[0][1]>=1e9?'$'+(topByValue[0][1]/1e9).toFixed(0)+'B':topByValue[0][1]>=1e6?'$'+(topByValue[0][1]/1e6).toFixed(0)+'M':'$'+topByValue[0][1].toLocaleString();
    html+='<div class="enrichment-metric"><span class="label">Largest Sector (by value)</span><span class="value">'+san(topByValue[0][0])+' ('+vStr+')</span></div>';
  }
  if(topActive.length){
    html+='<div class="enrichment-metric"><span class="label">Most Active This Week</span><span class="value">'+san(topActive[0][0])+' ('+topActive[0][1]+' new)</span></div>';
  }else{
    html+='<div class="enrichment-metric"><span class="label">Most Active This Week</span><span class="value">\u2014</span></div>';
  }
  html+='</div>';

  // Labour Market card
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Labour Market</div>';
  const labourContent=provData.labourDeepDive||'';
  if(labourContent&&labourContent.length>=20){
    html+='<p>'+san(labourContent.substring(0,300))+(labourContent.length>300?'...':'')+'</p>';
  }else{
    const empVal=pick(provInd.employmentRate,provIndVal('employmentRate'));
    const unVal=pick(provInd.unemployment,provIndVal('unemployment'));
    html+='<div class="enrichment-metric"><span class="label">Unemployment Rate</span><span class="value">'+san(unVal||'N/A')+'</span></div>';
    html+='<div class="enrichment-metric"><span class="label">Employment Rate</span><span class="value">'+san(empVal||'N/A')+'</span></div>';
    const wageVal=pick(provInd.wageGrowth,provIndVal('wageGrowth'));
    html+='<div class="enrichment-metric"><span class="label">Wage Growth</span><span class="value">'+san(wageVal||'N/A')+'</span></div>';
  }
  html+='</div>';

  // Trade & Commodities card
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Trade &amp; Commodities</div>';
  const tradeContent=provData.tradeExposure||'';
  if(tradeContent&&tradeContent.length>=20){
    html+='<p>'+san(tradeContent.substring(0,300))+(tradeContent.length>300?'...':'')+'</p>';
  }else{
    html+='<p>No trade data available for '+san(provName)+'.</p>';
  }
  html+='</div>';

  // Hiring Signals card
  html+='<div class="enrichment-card"><div class="enrichment-card-title"><span class="dot"></span> Hiring Signals</div>';
  const sectorHighlights=provData.sectorHighlights||'';
  if(sectorHighlights&&sectorHighlights.length>=20){
    html+='<p>'+san(sectorHighlights.substring(0,300))+(sectorHighlights.length>300?'...':'')+'</p>';
  }else{
    html+='<p>No hiring signal data available for '+san(provName)+'.</p>';
  }
  html+='</div>';
  html+='</div></div>'; // close two-col and section-block

  // Section 5: Projects Preview
  const fourWeeksAgo=new Date(now);fourWeeksAgo.setDate(now.getDate()-28);
  const fourWeekStr=fourWeeksAgo.toISOString().split('T')[0];
  let displayProj=newThisWeek.length?newThisWeek:provProj.filter(p=>p.firstTracked&&p.firstTracked>=fourWeekStr);
  displayProj.sort((a,b)=>parseNumericValue(b.value)-parseNumericValue(a.value));
  displayProj=displayProj.slice(0,8);

  // Projects narrative
  const projNarrative=provData.marketContext||'';
  html+='<div class="section-block">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Project Pipeline \u2014 '+san(provName)+'</h3>';
  html+='<span class="section-meta">'+projCount+' tracked &middot; '+fmtVal+' total value</span></div>';
  if(projNarrative&&projNarrative.length>=20){
    html+='<div class="narrative" style="margin-bottom:16px"><p style="font-size:15px;line-height:1.7">'+san(projNarrative.substring(0,400))+(projNarrative.length>400?'...':'')+'</p></div>';
  }
  if(displayProj.length){
    html+='<div class="inner-card" style="padding:0;overflow:hidden"><table class="projects-table"><thead><tr>';
    html+='<th>Project</th><th>City</th><th>Sector</th><th>Value</th><th>Status</th>';
    html+='</tr></thead><tbody>';
    displayProj.forEach(p=>{
      const pStatus=p.status||'Proposed';
      const stClass=pStatus.toLowerCase().includes('construct')?'status-construction':pStatus.toLowerCase().includes('pre')?'status-pre':pStatus.toLowerCase().includes('review')?'status-review':'status-proposed';
      html+='<tr><td style="font-weight:500">'+san((p.name||'').substring(0,60))+'</td>';
      html+='<td>'+san(p.city||p.location||'')+'</td>';
      html+='<td>'+san(_normSector(p.sector))+'</td>';
      html+='<td style="font-variant-numeric:tabular-nums">'+fmtCurrency(p.value,p)+'</td>';
      html+='<td><span class="status-badge '+stClass+'">'+san(pStatus)+'</span></td></tr>';
    });
    html+='</tbody></table>';
    html+='<a class="footer-link" href="#" onclick="switchTab(\'projects\');return false">View all '+projCount+' '+san(provName)+' projects \u2192</a></div>';
  }else{
    html+='<div class="inner-card" style="text-align:center;color:#7a8599;font-size:13px;padding:24px">No projects tracked for '+san(provName)+'.</div>';
  }
  html+='</div>';

  // Section 6: Upcoming Events
  const agentWl=provData.watchlistItems||[];
  const wl=D&&(D.watchlist||D.events)?D.watchlist||D.events||[]:[];
  const provEvents=agentWl.length?agentWl:wl.filter(e=>{const desc=(e.description||'')+(e.event_name||'')+(e.name||'');return desc.toLowerCase().includes(provName.toLowerCase())});

  if(provEvents.length){
    html+='<div class="section-block">';
    html+='<div class="section-header"><div class="accent-bar"></div><h3>Upcoming Events \u2014 '+san(provName)+'</h3>';
    html+='<span class="section-meta">Next 2 weeks</span></div>';
    html+='<div class="inner-card">';
    provEvents.forEach(e=>{
      const evDate=e.date||'';
      const evName=e.event_name||e.event||e.name||'';
      const evImpact=(e.impact||'medium').toLowerCase();
      const evInst=e.institution||'';
      const impactClass=evImpact==='high'?'impact-high':evImpact==='low'?'impact-low':'impact-medium';
      html+='<div class="watchlist-item">';
      html+='<span class="impact-dot '+impactClass+'"></span>';
      html+='<span class="watchlist-date">'+san(evDate)+'</span>';
      html+='<span class="watchlist-event">'+san(evName)+'</span>';
      if(evInst)html+='<span class="watchlist-institution">'+san(evInst)+'</span>';
      html+='</div>';
    });
    html+='</div></div>';
  }

  mainEl.innerHTML=html;

  // Post-render: insight charts
  const provChartSpec=provData.insightChart||null;
  const provThemes=extractAnalysisThemes(provContent,provProj);
  const chartArea=$('provInsightChartArea');
  if(chartArea){
    if(provChartSpec&&provChartSpec.dataKeys&&provChartSpec.dataKeys.length){
      chartArea.innerHTML=buildAgentInsightStrip('prov',provChartSpec);
    }else{
      chartArea.innerHTML=buildInsightStrip('prov',provThemes,code);
    }
  }

  await _ensureChartData();
  if(provChartSpec&&provChartSpec.dataKeys&&provChartSpec.dataKeys.length){
    await renderAgentInsightChart('prov',provChartSpec);
  }else{
    await renderInsightCharts('prov',provThemes,provProj,code,provContent);
  }

  // Post-render: policy section
  const policyContentEl=$('provPolicyContent');
  const policyMetaEl=$('provPolicyMeta');
  if(policyContentEl){
    try{
      const{items}=await _loadPolicyData();
      const provItems=items.filter(a=>{
        const itemProv=(a.province||'').toUpperCase();
        const level=a.level||'federal';
        return level==='federal'||itemProv===code.toUpperCase();
      });
      if(provItems.length){
        provItems.sort((a,b)=>{
          const aLocal=(a.province||'').toUpperCase()===code.toUpperCase()?0:1;
          const bLocal=(b.province||'').toUpperCase()===code.toUpperCase()?0:1;
          return aLocal-bLocal;
        });
        const provSpecific=provItems.filter(a=>(a.province||'').toUpperCase()===code.toUpperCase()).length;
        const fedCount=provItems.length-provSpecific;
        if(policyMetaEl){
          policyMetaEl.textContent=(provSpecific?provSpecific+' provincial':'')+(provSpecific&&fedCount?' + ':'')+
            (fedCount?fedCount+' federal':'')+(provItems.length?' developments':'');
        }
        // Render as accordion
        let polHtml='<div class="inner-card">';
        provItems.slice(0,8).forEach(a=>{
          const title=a.title||a.headline||'Untitled';
          const summary=a.summary||'';
          const url=a.url||'#';
          polHtml+='<details class="policy-item"><summary>'+san(title)+'</summary>';
          polHtml+='<div class="policy-body">'+san(summary);
          if(url&&url!=='#')polHtml+='<a href="'+san(url)+'" target="_blank" rel="noopener noreferrer" class="policy-link">View source \u2192</a>';
          polHtml+='</div></details>';
        });
        polHtml+='</div>';
        // Sources
        const polSources=provItems.slice(0,8).filter(a=>a.url).map(a=>({url:a.url,title:a.source_description||a.source||a.title||'Source'}));
        if(polSources.length){
          polHtml+='<details class="sources-section"><summary>Sources ('+polSources.length+')</summary><ol>';
          polSources.forEach(s=>{polHtml+='<li><a href="'+san(s.url)+'" target="_blank" rel="noopener noreferrer">'+san(s.title)+'</a></li>'});
          polHtml+='</ol></details>';
        }
        policyContentEl.innerHTML=polHtml;
      }else{
        if(policyMetaEl)policyMetaEl.textContent='';
        policyContentEl.innerHTML='<div class="inner-card" style="color:#7a8599;font-size:13px">No policy developments tracked for '+san(provName)+' this week.</div>';
      }
    }catch(e){console.warn('Province policy:',e);policyContentEl.innerHTML=''}
  }
}



/* ====== INDUSTRIES TAB ====== */
let _industryView='all';

function renderIndustries(){
  var el=$('industriesPage');if(!el)return;
  var goodsArr=(D&&D.goodsIndustries)||[];
  var servArr=(D&&D.servicesIndustries)||[];
  if(!goodsArr.length)['11','21','22','23','31-33'].forEach(function(code){goodsArr.push({code:code,name:NAICS_NAMES[code]})});
  if(!servArr.length)['41','44-45','48-49','51','52','53','54','55','56','61','62','71','72','81','91'].forEach(function(code){servArr.push({code:code,name:NAICS_NAMES[code]})});
  var allSectors=goodsArr.concat(servArr);

  var html='<div class="ind-page">';

  /* --- Section 1: Industry Overview --- */
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Industry Overview</h3>';
  html+='<span class="section-meta">'+allSectors.length+' NAICS sectors</span></div>';
  var overview=(D&&(D.industryOverview||D.industry_overview||D.industries_overview))||'';
  if(overview){
    html+='<div class="narrative">'+san(overview)+'</div>';
  }else{
    var upCount=allSectors.filter(function(s){return s.mm&&!s.isNegative&&s.mm!=='0.0%'&&s.mm!=='\u2014 0.0%'}).length;
    if(upCount)html+='<div class="narrative"><p><span class="lead-sentence">'+upCount+' of '+allSectors.length+' NAICS sectors recorded positive month-over-month GDP growth.</span></p></div>';
  }
  var totalProj=0,goodsProj=0,servProj=0;
  allSectors.forEach(function(s){totalProj+=parseInt(s.projects)||0});
  goodsArr.forEach(function(s){goodsProj+=parseInt(s.projects)||0});
  servArr.forEach(function(s){servProj+=parseInt(s.projects)||0});
  if(totalProj>0){
    html+='<div class="callout"><strong>Pipeline cross-reference:</strong> The database tracks '+fmtNum(totalProj)+' active projects across all sectors.';
    if(goodsProj||servProj)html+=' Goods-producing: '+fmtNum(goodsProj)+' projects. Services-producing: '+fmtNum(servProj)+' projects.';
    html+='</div>';
  }
  html+='</div>';

  /* --- Section 2: Biggest Movers --- */
  var movers=_indGetMovers(allSectors);
  if(movers.length){
    html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Biggest Movers</h3>';
    html+='<span class="section-meta">Largest month-over-month changes</span></div>';
    movers.forEach(function(s){html+=_indMoverCard(s)});
    html+='</div>';
  }

  /* --- Section 3: All Sectors --- */
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>All Sectors</h3>';
  html+='<span class="section-meta">Click any row to read the analysis</span></div>';
  html+='<div class="controls-row"><div class="view-toggle">';
  html+='<button class="toggle-btn'+(_industryView==='all'?' active':'')+'" onclick="_indToggleView(\'all\')">All</button>';
  html+='<button class="toggle-btn'+(_industryView==='goods'?' active':'')+'" onclick="_indToggleView(\'goods\')">Goods-Producing</button>';
  html+='<button class="toggle-btn'+(_industryView==='services'?' active':'')+'" onclick="_indToggleView(\'services\')">Services-Producing</button>';
  html+='</div></div>';
  var showGoods=_industryView==='all'||_industryView==='goods';
  var showServ=_industryView==='all'||_industryView==='services';
  if(showGoods){html+='<div class="subsection-divider">Goods-Producing Industries</div>';html+=_indSectorTable(goodsArr,'g');}
  if(showServ){html+='<div class="subsection-divider">Services-Producing Industries</div>';html+=_indSectorTable(servArr,'s');}
  html+='</div></div>';
  el.innerHTML=html;
}

function _indGetMovers(sectors){
  var withMM=sectors.filter(function(s){return s.mm&&s.mm!=='\u2014'&&s.mm!=='N/A'});
  var gainers=withMM.filter(function(s){return !s.isNegative&&s.mm!=='0.0%'&&s.mm!=='\u2014 0.0%'}).sort(function(a,b){return _absChg(b.mm)-_absChg(a.mm)}).slice(0,2);
  var decliners=withMM.filter(function(s){return s.isNegative}).sort(function(a,b){return _absChg(b.mm)-_absChg(a.mm)}).slice(0,2);
  return gainers.concat(decliners);
}
function _absChg(mm){if(!mm)return 0;var n=parseFloat(String(mm).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:Math.abs(n)}

function _indMoverCard(s){
  var name=s.name||NAICS_NAMES[s.code]||s.code;
  var isUp=!s.isNegative;var dirCls=isUp?'up':'down';var arrow=isUp?'\u25B2':'\u25BC';
  var h='<div class="mover-card"><div class="mover-card-header"><div class="mover-title">'+name+'</div>';
  h+='<span class="mover-direction '+dirCls+'">'+arrow+' '+(s.mm||'')+' month-over-month</span></div>';
  h+='<div class="mover-metrics">';
  if(s.gdp)h+='<div class="mover-metric"><span class="mover-metric-label">GDP (Monthly)</span><span class="mover-metric-value">'+s.gdp+'</span></div>';
  if(s.yy){var yc=(s.yy.indexOf('-')>=0||s.yy.indexOf('\u2212')>=0)?'chg-down':'chg-up';h+='<div class="mover-metric"><span class="mover-metric-label">Year-over-Year</span><span class="mover-metric-value '+yc+'">'+s.yy+'</span></div>';}
  if(s.projects!=null)h+='<div class="mover-metric"><span class="mover-metric-label">Active Projects</span><span class="mover-metric-value">'+s.projects+'</span></div>';
  if(s.pipelineValue)h+='<div class="mover-metric"><span class="mover-metric-label">Pipeline Value</span><span class="mover-metric-value">'+s.pipelineValue+'</span></div>';
  h+='</div>';
  if(s.analysis){h+='<div class="mover-analysis">'+san(s.analysis);if(s.indicatorSrc)h+='<div class="sources"><span>Sources:</span> '+san(s.indicatorSrc)+'</div>';h+='</div>';}
  h+='</div>';return h;
}

function _indSectorTable(sectors,prefix){
  var h='<div class="sector-table-wrap"><table class="sector-table"><thead><tr>';
  h+='<th>Sector</th><th>GDP</th><th>M/M</th><th>Y/Y</th><th>Projects</th><th>Pipeline Value</th>';
  h+='</tr></thead><tbody>';
  sectors.forEach(function(s,i){
    var name=s.name||NAICS_NAMES[s.code]||s.code;
    var mmCls=s.isNegative?'chg-down':(!s.mm||s.mm==='0.0%'||s.mm==='\u2014 0.0%'?'chg-flat':'chg-up');
    var yyCls='chg-flat';if(s.yy){if(s.yy.indexOf('-')>=0||s.yy.indexOf('\u2212')>=0)yyCls='chg-down';else if(s.yy.indexOf('+')>=0||parseFloat(s.yy)>0)yyCls='chg-up';}
    var mmArr=s.isNegative?'\u25BC ': (s.mm&&s.mm!=='0.0%'&&s.mm!=='\u2014 0.0%'?'\u25B2 ':'');
    var uid=prefix+'_'+i;
    h+='<tr class="sector-row" onclick="_indToggleRow(\''+uid+'\')">';
    h+='<td class="tbl-name"><span class="row-chevron" id="indChev_'+uid+'">\u25B6</span>'+name+'</td>';
    h+='<td class="tbl-gdp">'+(s.gdp||'\u2014')+'</td>';
    h+='<td class="'+mmCls+'">'+mmArr+(s.mm||'\u2014')+'</td>';
    h+='<td class="'+yyCls+'">'+(s.yy||'\u2014')+'</td>';
    h+='<td class="tbl-projects">'+(s.projects!=null?s.projects:'\u2014')+'</td>';
    h+='<td class="tbl-value">'+(s.pipelineValue||'\u2014')+'</td></tr>';
    /* expand row */
    h+='<tr class="expand-row" id="indExp_'+uid+'"><td colspan="6"><div class="expand-content">';
    if(s.statusChanges!=null||s.newThisWeek!=null){
      h+='<div class="expand-metrics">';
      if(s.statusChanges!=null)h+='<div class="expand-metric"><span class="expand-metric-label">Status Changes</span><span class="expand-metric-value">'+s.statusChanges+'</span></div>';
      if(s.newThisWeek!=null)h+='<div class="expand-metric"><span class="expand-metric-label">New This Week</span><span class="expand-metric-value">'+s.newThisWeek+'</span></div>';
      h+='</div>';
    }
    if(s.analysis){h+=san(s.analysis);if(s.indicatorSrc)h+='<div class="sources"><span>Sources:</span> '+san(s.indicatorSrc)+'</div>';}
    else h+='<em style="color:#7a8599">No analysis available.</em>';
    h+='</div></td></tr>';
  });
  h+='</tbody></table></div>';return h;
}

window._indToggleView=function(view){_industryView=view;renderIndustries()};
window._indToggleRow=function(uid){
  var exp=document.getElementById('indExp_'+uid);if(!exp)return;
  var row=exp.previousElementSibling;var open=exp.classList.contains('visible');
  if(open){exp.classList.remove('visible');if(row)row.classList.remove('expanded')}
  else{exp.classList.add('visible');if(row)row.classList.add('expanded')}
};

/* ====== MARKETS TAB (Interactive Charts) ====== */
const _mktTsMap={'S&P/TSX':'tsx_composite','S&P/TSX Composite':'tsx_composite','TSX Composite':'tsx_composite','S&P 500':'sp500','Dow Jones':'djia','NASDAQ':'nasdaq','FTSE 100':'ftse100','DAX':'dax','Nikkei 225':'nikkei225','Hang Seng':'idx_hangseng','Shanghai':'idx_shanghai','CAD/USD':'cadusd','USD/CAD':'cadusd','EUR/USD':'eurusd','GBP/USD':'fx_gbpusd','USD/JPY':'usdjpy','USD/CNY':'usdcny','AUD/USD':'fx_audusd','Crude Oil (WTI)':'wti','Crude Oil (Brent)':'brent','Natural Gas':'natural_gas','Gold':'gold','Silver':'silver','Platinum':'platinum','Palladium':'palladium','Copper':'copper','Aluminum':'aluminum','Nickel':'nickel','Zinc':'zinc','Iron Ore':'iron_ore','Wheat':'wheat','Corn':'corn','Rice':'rice','Soybeans':'soybeans','Coffee':'coffee','Cocoa':'cocoa','Sugar #11':'sugar','Cotton':'cotton','Soybean Oil':'soybean_oil','Soybean Meal':'soybean_meal','Coal (Newcastle)':'coal','Propane':'comm_propane','Lumber':'lumber','Potash (Nutrien)':'potash_nutrien','Uranium (Cameco)':'cameco_uranium','Uranium (Sprott)':'sprott_uranium','Bitcoin':'bitcoin','Ethereum':'ethereum','Dry Bulk Shipping':'dry_bulk_shipping','LNG Asia':'lng_asia','Lead':'lead','Tin':'tin'};
const _mktPal=['#2563EB','#10B981','#F59E0B','#8B5CF6','#EC4899','#EF4444','#0EA5E9','#84CC16','#14B8A6','#D946EF','#F97316','#6366F1'];
let _mktState={};

/* _mktBuildSection kept for backward compat — not called by new layout */

function _pillId(name){return(name||'').replace(/[^a-zA-Z0-9]/g,'_')}

function _mktToggle(pill){
  const name=pill.dataset.name;const key=pill.dataset.key;
  const st=_mktState[key];if(!st)return;
  if(st.active.has(name)){if(st.active.size<=1)return;st.active.delete(name);pill.classList.remove('active')}
  else{st.active.add(name);pill.classList.add('active')}
  // Show/hide stat
  const statEl=document.getElementById('mktStat_'+key+'_'+_pillId(name));
  if(statEl)statEl.style.display=st.active.has(name)?'':'none';
  _mktDrawChart(key);
}

function _mktSetMode(btn){
  const key=btn.dataset.key;const mode=btn.dataset.mode;
  const st=_mktState[key];if(!st)return;
  st.mode=mode;
  btn.parentElement.querySelectorAll('.mkt-mode-btn').forEach(b=>b.classList.toggle('active',b===btn));
  _mktDrawChart(key);
}

function _mktSetRange(btn){
  const key=btn.dataset.key;const range=parseInt(btn.dataset.range);
  const st=_mktState[key];if(!st)return;
  st.range=range;
  btn.parentElement.querySelectorAll('.mkt-mode-btn').forEach(b=>b.classList.toggle('active',b===btn));
  _mktDrawChart(key);
}

function _mktSetFreq(btn){
  const key=btn.dataset.key;const freq=btn.dataset.freq;
  const st=_mktState[key];if(!st)return;
  st.freq=freq;
  btn.parentElement.querySelectorAll('.mkt-mode-btn').forEach(b=>b.classList.toggle('active',b===btn));
  _mktDrawChart(key);
}

async function _mktDrawChart(key){
  const st=_mktState[key];if(!st)return;
  const cid='mktChart_'+key;
  const canvas=document.getElementById(cid);if(!canvas)return;
  if(charts[cid])charts[cid].destroy();
  const activeItems=st.items.filter(it=>st.active.has(it.name));
  if(!activeItems.length)return;
  // Load all timeseries in parallel
  const tsPromises=activeItems.map(it=>loadTimeseries(_mktTsMap[it.name]||it.tsId||''));
  const tsResults=await Promise.all(tsPromises);
  // Date range filter
  const rangeMonths=st.range||12;
  const cutoff=rangeMonths>0?(()=>{const d=new Date();d.setMonth(d.getMonth()-rangeMonths);return d})():new Date('1900-01-01');
  const datasets=[];const allLabels=new Set();
  activeItems.forEach((it,i)=>{
    const ts=tsResults[i];if(!ts)return;
    const raw=ts.series||ts;if(!Array.isArray(raw))return;
    let filtered=raw.filter(p=>new Date(p.date)>=cutoff).sort((a,b)=>new Date(a.date)-new Date(b.date));
    // Frequency filter: resample to weekly or monthly if requested
    if(st.freq==='weekly'&&filtered.length>1){
      const sampled=[];let lastWeek='';
      filtered.forEach(p=>{const d=new Date(p.date);const wk=d.getFullYear()+'-W'+String(Math.ceil(((d-new Date(d.getFullYear(),0,1))/86400000+1)/7)).padStart(2,'0');if(wk!==lastWeek){sampled.push(p);lastWeek=wk}});
      filtered=sampled;
    }else if(st.freq==='monthly'&&filtered.length>1){
      const sampled=[];let lastMon='';
      filtered.forEach(p=>{const mon=p.date.substring(0,7);if(mon!==lastMon){sampled.push(p);lastMon=mon}});
      filtered=sampled;
    }else if(st.freq==='daily'){
      // already daily, no change
    }
    if(!filtered.length)return;
    const color=_mktPal[st.items.indexOf(it)%_mktPal.length];
    let data,labels;
    if(st.mode==='pct'&&filtered.length>1){
      const base=filtered[0].value;
      data=filtered.map(p=>base?((p.value-base)/base*100):0);
      labels=filtered.map(p=>p.date);
    }else{
      data=filtered.map(p=>p.value);
      labels=filtered.map(p=>p.date);
    }
    labels.forEach(l=>allLabels.add(l));
    datasets.push({label:it.name,data:labels.map((l,j)=>({x:l,y:data[j]})),borderColor:color,backgroundColor:color+'15',borderWidth:2,pointRadius:0,pointHoverRadius:4,pointBackgroundColor:color,fill:false,tension:0.3});
  });
  if(!datasets.length){canvas.parentElement.innerHTML='<div style="text-align:center;color:#64748B;padding:40px;font-size:13px">No timeseries data available for selected items</div>';return}
  const sortedLabels=[...allLabels].sort();
  // Determine if we need dual axes (>1 dataset with different scales in price mode)
  let useDualAxis=false;
  if(st.mode==='price'&&datasets.length===2){
    const vals0=datasets[0].data.map(d=>d.y).filter(v=>v!=null);
    const vals1=datasets[1].data.map(d=>d.y).filter(v=>v!=null);
    if(vals0.length&&vals1.length){
      const avg0=vals0.reduce((a,b)=>a+b,0)/vals0.length;
      const avg1=vals1.reduce((a,b)=>a+b,0)/vals1.length;
      if(avg0>0&&avg1>0&&(avg0/avg1>5||avg1/avg0>5))useDualAxis=true;
    }
  }
  // Auto-switch to % mode if 3+ items selected in price mode with wildly different scales
  if(st.mode==='price'&&datasets.length>=3){
    const avgs=datasets.map(ds=>{const vals=ds.data.map(d=>d.y).filter(v=>v!=null);return vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:0});
    const mx=Math.max(...avgs),mn=Math.min(...avgs.filter(v=>v>0));
    if(mn>0&&mx/mn>10){
      // Silently normalize
      datasets.forEach((ds,i)=>{
        const vals=ds.data;if(!vals.length)return;
        const base=vals[0].y;
        if(base)vals.forEach(v=>{v.y=((v.y-base)/base)*100});
      });
      st.mode='pct';
      const modeEl=document.getElementById('mktMode_'+key);
      if(modeEl)modeEl.querySelectorAll('.mkt-mode-btn').forEach(b=>b.classList.toggle('active',b.dataset.mode==='pct'));
    }
  }
  const yAxes={y:{position:'left',grid:{color:'rgba(0,0,0,0.05)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'DM Sans',size:11},color:'#636363',callback:v=>st.mode==='pct'?v.toFixed(1)+'%':fmtNum(v)}}};
  if(useDualAxis){
    datasets[0].yAxisID='y';datasets[1].yAxisID='y1';
    yAxes.y1={position:'right',grid:{display:false},ticks:{font:{family:'DM Sans',size:11},color:datasets[1].borderColor,callback:v=>fmtNum(v)}};
    yAxes.y.ticks.color=datasets[0].borderColor;
  }
  charts[cid]=new Chart(canvas,{type:'line',data:{datasets},options:{
    responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    plugins:{
      legend:{display:datasets.length>1,position:'top',labels:{boxWidth:12,padding:8,font:{family:'DM Sans',size:11},usePointStyle:true,pointStyle:'circle'}},
      tooltip:{backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8,
        callbacks:{label:ctx=>{const v=ctx.parsed.y;return ctx.dataset.label+': '+(st.mode==='pct'?v.toFixed(2)+'%':fmtNum(v))}}}
    },
    scales:{x:{type:'time',time:{unit:rangeMonths<=3?'week':rangeMonths<=12?'month':'quarter',tooltipFormat:'MMM d, yyyy',displayFormats:{week:'MMM d',month:'MMM yyyy',quarter:'QQQ yyyy'}},grid:{display:false},ticks:{font:{family:'DM Sans',size:10},color:'#636363',maxTicksLimit:rangeMonths<=6?10:8}},...yAxes}
  }});
}

/* ── SVG chart utilities (mockup style) ── */
var _svgUid=0;
function _svgTimeseries(series,opts){
  if(!series||!series.length)return '<div style="height:220px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No timeseries data available</div>';
  var W=800,H=opts.height||220,pL=60,pR=20,pT=15,pB=28;
  var color=opts.color||'#003153';var fid='svgF_'+(++_svgUid);
  series=series.slice().sort(function(a,b){return new Date(a.date)-new Date(b.date)});
  var vals=series.map(function(p){return p.value});
  var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals),rng=mx-mn;
  if(rng===0)rng=Math.abs(mn)*0.1||1;
  mn-=rng*0.05;mx+=rng*0.05;rng=mx-mn;
  var pW=W-pL-pR,pH=H-pT-pB;
  var pts=series.map(function(p,i){return{x:pL+(i/(series.length-1))*pW,y:pT+(1-(p.value-mn)/rng)*pH}});
  var s='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;display:block">';
  s+='<defs><linearGradient id="'+fid+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="'+color+'" stop-opacity="0.12"/><stop offset="100%" stop-color="'+color+'" stop-opacity="0.01"/></linearGradient></defs>';
  for(var g=0;g<3;g++){var gy=pT+(g/2)*pH;var gv=mx-(g/2)*rng;s+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="#e8ecf0" stroke-width="1"/>';s+='<text x="'+(pL-6)+'" y="'+(gy+4)+'" fill="#7a8599" font-size="10" font-family="DM Sans" text-anchor="end">'+_svgFmtVal(gv)+'</text>';}
  var poly=pts.map(function(p){return p.x+','+p.y}).join(' ');
  var lp=pts[pts.length-1],fp=pts[0],bot=pT+pH;
  s+='<path d="M'+fp.x+','+fp.y+' '+pts.slice(1).map(function(p){return 'L'+p.x+','+p.y}).join(' ')+' L'+lp.x+','+bot+' L'+fp.x+','+bot+' Z" fill="url(#'+fid+')"/>';
  s+='<polyline points="'+poly+'" fill="none" stroke="'+color+'" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>';
  s+='<circle cx="'+lp.x+'" cy="'+lp.y+'" r="4" fill="'+color+'" stroke="#fff" stroke-width="2"/>';
  var lc=Math.min(4,series.length);
  for(var li=0;li<lc;li++){var idx=Math.round(li/(lc-1)*(series.length-1));var anc=li===0?'start':li===lc-1?'end':'middle';var dl=li===lc-1?'Now':_svgFmtDate(series[idx].date);s+='<text x="'+pts[idx].x+'" y="'+(H-5)+'" fill="#7a8599" font-size="10" font-family="DM Sans" text-anchor="'+anc+'">'+dl+'</text>';}
  s+='</svg>';return s;
}
function _svgFmtVal(v){if(Math.abs(v)>=10000)return(v/1000).toFixed(0)+'k';if(Math.abs(v)>=1000)return v.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',');if(Math.abs(v)>=1)return v.toFixed(2);return v.toFixed(4)}
function _svgFmtDate(d){try{var dt=new Date(d);return dt.toLocaleDateString('en-CA',{month:'short'})}catch(e){return d}}

function _svgYieldCurve(yc,ycPrev){
  if(!yc||!yc.length)return '';
  var W=800,H=180,pL=50,pR=40,pT=20,pB=30;
  var data=yc.map(function(y){return parseFloat(y.yield)||0});
  var allVals=data.slice();if(ycPrev&&ycPrev.length)allVals=allVals.concat(ycPrev);
  var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals),rng=mx-mn;
  if(rng===0)rng=1;mn-=rng*0.15;mx+=rng*0.15;rng=mx-mn;
  var pW=W-pL-pR,pH=H-pT-pB;var n=yc.length;
  var xPts=yc.map(function(y,i){return pL+(i/(n-1))*pW});
  function yPos(v){return pT+(1-(v-mn)/rng)*pH}
  var s='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;display:block">';
  for(var g=0;g<4;g++){var gy=pT+(g/3)*pH;var gv=mx-(g/3)*rng;s+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="#e8ecf0" stroke-width="1"/>';s+='<text x="'+(pL-6)+'" y="'+(gy+4)+'" fill="#7a8599" font-size="10" font-family="DM Sans" text-anchor="end">'+gv.toFixed(1)+'%</text>';}
  if(ycPrev&&ycPrev.length>=n){var prevPoly=xPts.map(function(x,i){return x+','+yPos(ycPrev[i])}).join(' ');s+='<polyline points="'+prevPoly+'" fill="none" stroke="#c4320a" stroke-width="1.5" stroke-dasharray="5,3" stroke-linejoin="round"/>';}
  var curPoly=xPts.map(function(x,i){return x+','+yPos(data[i])}).join(' ');
  s+='<polyline points="'+curPoly+'" fill="none" stroke="#003153" stroke-width="2.5" stroke-linejoin="round"/>';
  xPts.forEach(function(x,i){s+='<circle cx="'+x+'" cy="'+yPos(data[i])+'" r="4" fill="#003153" stroke="#fff" stroke-width="2"/>';});
  yc.forEach(function(y,i){s+='<text x="'+xPts[i]+'" y="'+(H-8)+'" fill="#7a8599" font-size="10" font-family="DM Sans" text-anchor="middle">'+y.term+'</text>'});
  if(ycPrev&&ycPrev.length>=n){s+='<line x1="'+(W-pR-120)+'" y1="10" x2="'+(W-pR-95)+'" y2="10" stroke="#003153" stroke-width="2.5"/><text x="'+(W-pR-90)+'" y="14" fill="#4a5568" font-size="10" font-family="DM Sans">Current</text>';s+='<line x1="'+(W-pR-50)+'" y1="10" x2="'+(W-pR-25)+'" y2="10" stroke="#c4320a" stroke-width="1.5" stroke-dasharray="5,3"/><text x="'+(W-pR-20)+'" y="14" fill="#4a5568" font-size="10" font-family="DM Sans">1 Year Ago</text>';}
  s+='</svg>';return s;
}

async function _mktRenderSvg(key){
  var st=_mktState[key];if(!st)return;
  var chartDiv=document.getElementById('mktSvg_'+key);if(!chartDiv)return;
  var activeName=[].concat(Array.from(st.active))[0];
  var item=st.items.find(function(it){return it.name===activeName});
  if(!item){chartDiv.innerHTML='<div style="height:220px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">Select a series</div>';return;}
  var tsId=_mktTsMap[item.name]||'';
  var ts=await loadTimeseries(tsId);
  if(!ts){chartDiv.innerHTML='<div style="height:220px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No timeseries data for '+item.name+'</div>';return;}
  var raw=ts.series||ts;if(!Array.isArray(raw)){chartDiv.innerHTML='';return;}
  var rangeMonths=st.range||3;
  var cutoff=rangeMonths>0?(function(){var d=new Date();d.setMonth(d.getMonth()-rangeMonths);return d})():new Date('1900-01-01');
  var filtered=raw.filter(function(p){return new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
  if(!filtered.length){chartDiv.innerHTML='<div style="height:220px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No data in selected range</div>';return;}
  chartDiv.innerHTML=_svgTimeseries(filtered,{color:'#003153',height:key==='fx'?180:220});
}

/* Single-select pill handler for SVG charts */
window._mktSelectPill=function(pill){
  var name=pill.dataset.name,key=pill.dataset.key;
  var st=_mktState[key];if(!st)return;
  st.active=new Set([name]);
  pill.parentElement.querySelectorAll('.series-pill,.fx-pill').forEach(function(p){p.classList.toggle('active',p.dataset.name===name)});
  _mktRenderSvg(key);
};
/* SVG-aware range handler */
window._mktSvgSetRange=function(btn){
  var key=btn.dataset.key,range=parseInt(btn.dataset.range);
  var st=_mktState[key];if(!st)return;
  st.range=range;
  btn.parentElement.querySelectorAll('.range-btn').forEach(function(b){b.classList.toggle('active',b===btn)});
  _mktRenderSvg(key);
};

function renderMarkets(){
  var el=$('marketsPage');if(!el)return;
  var fm=(D&&(D.financialMarkets||D.financial_markets||D.markets))||{};
  var html='<div class="mkt-page">';
  html+=_buildMktCommentary(fm);
  html+=_buildMktEquities(fm);
  html+=_buildMktFx(fm);
  html+=_buildMktYields();
  html+=_buildMktCommodities(fm);
  html+='</div>';
  el.innerHTML=html;
  setTimeout(function(){
    if(_mktState.equities)_mktRenderSvg('equities');
    if(_mktState.fx)_mktRenderSvg('fx');
  },50);
}

function _chgCls(v){if(!v)return'flat';if(String(v).indexOf('-')>=0||String(v).indexOf('\u2212')>=0)return'down';if(String(v).indexOf('+')>=0||parseFloat(v)>0)return'up';return'flat'}
function _chgArrow(v){var c=_chgCls(v);return c==='down'?'\u25BC ':c==='up'?'\u25B2 ':''}

function _buildMktCommentary(fm){
  var summary=(fm.summary||fm.commentary||(D&&(D.marketCommentary||D.market_commentary)))||'';
  if(!summary)return '';
  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Market Commentary</h3><span class="section-meta"></span></div>';
  h+='<div class="narrative">'+san(summary)+'</div></div>';
  return h;
}

function _buildMktEquities(fm){
  var indices=fm.indices||[];
  if(!indices.length&&indicators.length){
    [{name:'S&P/TSX',ind:'tsx_composite'},{name:'S&P/TSX',ind:'tsx'},{name:'S&P 500',ind:'sp500'},{name:'Dow Jones',ind:'djia'},{name:'NASDAQ',ind:'nasdaq'},{name:'FTSE 100',ind:'ftse100'},{name:'DAX',ind:'dax'},{name:'Nikkei 225',ind:'nikkei225'}].forEach(function(m){var i=indicators.find(function(x){return x.indicator_name===m.ind});if(i&&!indices.find(function(x){return x.name===m.name}))indices.push({name:m.name,value:i.value,change:'',region:''})});
  }
  if(!indices.length)return '';
  var items=indices.map(function(it){return{name:it.name,value:it.value||'',change:it.change||it.day||'',yy:it.yy||''}});
  var defaults=[items[0].name];
  _mktState.equities={items:items,active:new Set(defaults),mode:'price',range:3,freq:'all'};

  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Equity Indices</h3>';
  h+='<span class="section-meta">'+items.length+' indices</span></div><div class="market-card">';
  h+='<div class="series-row">';
  items.forEach(function(it){
    var act=defaults.indexOf(it.name)>=0;var c=_chgCls(it.change);
    h+='<div class="series-pill'+(act?' active':'')+'" data-name="'+it.name+'" data-key="equities" onclick="_mktSelectPill(this)">';
    h+='<div class="pill-name">'+it.name+'</div><div class="pill-value">'+(it.value||'\u2014')+'</div>';
    if(it.change)h+='<div class="pill-change '+c+'">'+_chgArrow(it.change)+it.change+'</div>';
    h+='</div>';
  });
  h+='</div>';
  h+='<div class="stat-row">';
  var fi=items[0];
  if(fi.yy)h+='<div class="stat-item"><span class="stat-label">Year-over-Year</span><span class="stat-val pill-change '+_chgCls(fi.yy)+'">'+fi.yy+'</span></div>';
  h+='</div>';
  h+='<div class="chart-controls"><div class="range-selector">';
  [{m:1,l:'1M'},{m:3,l:'3M'},{m:6,l:'6M'},{m:12,l:'1Y'},{m:36,l:'3Y'}].forEach(function(r){
    h+='<button class="range-btn'+(r.m===3?' active':'')+'" data-range="'+r.m+'" data-key="equities" onclick="_mktSvgSetRange(this)">'+r.l+'</button>';
  });
  h+='</div></div>';
  h+='<div class="chart-area" id="mktSvg_equities"></div>';
  var eqNarr=(fm.equityNarrative||fm.equity_narrative)||'';
  if(eqNarr)h+='<div class="market-narrative">'+san(eqNarr)+'</div>';
  h+='</div></div>';
  return h;
}

function _buildMktFx(fm){
  var fx=fm.fx||[];
  if(!fx.length&&indicators.length){
    [{name:'CAD/USD',ind:'cad_usd'},{name:'CAD/USD',ind:'cadusd'},{name:'EUR/USD',ind:'eurusd'},{name:'USD/CNY',ind:'usdcny'},{name:'USD/JPY',ind:'usdjpy'}].forEach(function(m){var i=indicators.find(function(x){return x.indicator_name===m.ind});if(i&&!fx.find(function(x){return x.name===m.name}))fx.push({name:m.name,value:i.value})});
  }
  if(!fx.length)return '';
  var items=fx.map(function(it){return{name:it.name,value:it.value||'',change:it.day||it.change||'',yy:it.yy||''}});
  var defaults=[items[0].name];
  _mktState.fx={items:items,active:new Set(defaults),mode:'price',range:3,freq:'all'};

  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Foreign Exchange</h3>';
  h+='<span class="section-meta">'+items.length+' pairs</span></div><div class="market-card">';
  h+='<div class="fx-series-row">';
  items.forEach(function(it){
    var act=defaults.indexOf(it.name)>=0;var c=_chgCls(it.change);
    h+='<div class="fx-pill'+(act?' active':'')+'" data-name="'+it.name+'" data-key="fx" onclick="_mktSelectPill(this)">';
    h+='<div class="pill-name">'+it.name+'</div><div class="pill-value">'+(it.value||'\u2014')+'</div>';
    if(it.change)h+='<div class="pill-change '+c+'">'+_chgArrow(it.change)+it.change+'</div>';
    h+='</div>';
  });
  h+='</div>';
  var bocRate=(fm.bocRate||fm.boc_rate||(D&&D.bocRate))||'';
  h+='<div class="stat-row">';
  if(items[0].yy)h+='<div class="stat-item"><span class="stat-label">Year-over-Year</span><span class="stat-val pill-change '+_chgCls(items[0].yy)+'">'+items[0].yy+'</span></div>';
  if(bocRate)h+='<div class="stat-item"><span class="stat-label">Bank of Canada Rate</span><span class="stat-val">'+bocRate+'</span></div>';
  h+='</div>';
  h+='<div class="chart-controls"><div class="range-selector">';
  [{m:1,l:'1M'},{m:3,l:'3M'},{m:6,l:'6M'},{m:12,l:'1Y'},{m:36,l:'3Y'}].forEach(function(r){
    h+='<button class="range-btn'+(r.m===3?' active':'')+'" data-range="'+r.m+'" data-key="fx" onclick="_mktSvgSetRange(this)">'+r.l+'</button>';
  });
  h+='</div></div>';
  h+='<div class="chart-area" id="mktSvg_fx"></div>';
  var fxNarr=(fm.fxNarrative||fm.fx_narrative)||'';
  if(fxNarr)h+='<div class="market-narrative">'+san(fxNarr)+'</div>';
  h+='</div></div>';
  return h;
}

function _buildMktYields(){
  var yc=(D&&D.yieldCurve)||[];
  if(!yc.length&&indicators.length){
    [{term:'3M',ind:'goc_3m_yield'},{term:'1Y',ind:'goc_1y_yield'},{term:'2Y',ind:'goc_2y_yield'},{term:'5Y',ind:'goc_5y_yield'},{term:'10Y',ind:'goc_10y_yield'},{term:'30Y',ind:'goc_30y_yield'}].forEach(function(t){var i=indicators.find(function(x){return x.indicator_name===t.ind});if(i)yc.push({term:t.term,yield:i.value})});
  }
  if(!yc.length)return '';
  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Government of Canada Yields</h3>';
  h+='<span class="section-meta">Yield curve \u00B7 '+yc.length+' tenors</span></div><div class="market-card">';
  h+='<div class="yield-table-wrap"><table class="yield-table"><thead><tr><th>Tenor</th>';
  yc.forEach(function(y){h+='<th>'+y.term+'</th>'});
  h+='</tr></thead><tbody><tr><td>Current</td>';
  yc.forEach(function(y){h+='<td class="yield-current">'+(y.yield||'\u2014')+'</td>'});
  h+='</tr>';
  var hasPrev=yc.some(function(y){return y.prevYield||y.prev_yield});
  if(hasPrev){
    h+='<tr><td>1 Year Ago</td>';yc.forEach(function(y){h+='<td class="yield-prev">'+(y.prevYield||y.prev_yield||'\u2014')+'</td>'});h+='</tr>';
    h+='<tr><td>Change</td>';yc.forEach(function(y){var cur=parseFloat(y.yield)||0,prev=parseFloat(y.prevYield||y.prev_yield)||0;if(prev){var diff=Math.round((cur-prev)*100);var cls=diff>0?'chg-up':'chg-down';h+='<td class="yield-chg '+cls+'">'+(diff>0?'+':'')+diff+' bps</td>'}else h+='<td>\u2014</td>'});h+='</tr>';
  }
  h+='</tbody></table></div>';
  var y2=yc.find(function(y){return y.term==='2Y'});var y10=yc.find(function(y){return y.term==='10Y'});
  if(y2&&y10){
    var spread=((parseFloat(y10.yield)-parseFloat(y2.yield))*100).toFixed(0);var inv=parseInt(spread)<0;
    var boc=(D&&D.financialMarkets&&D.financialMarkets.bocRate)||(D&&D.bocRate)||'';
    h+='<div class="spread-row"><span class="stat-label">2s10s Spread</span> <span class="spread-badge '+(inv?'inverted':'normal')+'">'+spread+' basis points \u2014 '+(inv?'Inverted':'Normal')+'</span>';
    if(boc)h+='<span style="margin-left:auto;font-size:13px;color:#7a8599">Bank of Canada overnight rate: <strong style="color:#1a1a1a;font-weight:700">'+boc+'</strong></span>';
    h+='</div>';
  }
  var ycSvg=_svgYieldCurve(yc,(D&&D.yieldCurveLastYear)||null);
  if(ycSvg)h+='<div class="chart-area" style="padding-top:8px">'+ycSvg+'</div>';
  var yieldNarr=(D&&D.financialMarkets&&(D.financialMarkets.yieldNarrative||D.financialMarkets.yield_narrative))||'';
  if(yieldNarr)h+='<div class="market-narrative">'+san(yieldNarr)+'</div>';
  h+='</div></div>';return h;
}

function _buildMktCommodities(fm){
  var rawComms=(D&&D.commodities)||fm.commodities||[];
  if(!rawComms.length&&indicators.length){
    [{name:'Crude Oil (WTI)',ind:'wti',cat:'Energy'},{name:'Crude Oil (WTI)',ind:'wti_oil',cat:'Energy'},{name:'Crude Oil (Brent)',ind:'brent',cat:'Energy'},{name:'Natural Gas',ind:'natural_gas',cat:'Energy'},{name:'Gold',ind:'gold',cat:'Precious Metals'},{name:'Silver',ind:'silver',cat:'Precious Metals'},{name:'Copper',ind:'copper',cat:'Base Metals'},{name:'Aluminum',ind:'aluminum',cat:'Base Metals'},{name:'Wheat',ind:'wheat',cat:'Agriculture'},{name:'Lumber',ind:'lumber',cat:'Forest Products'}].forEach(function(m){var i=indicators.find(function(x){return x.indicator_name===m.ind});if(i&&!rawComms.find(function(x){return x.name===m.name}))rawComms.push({name:m.name,val:i.value,change:'',category:m.cat,unit:''})});
  }
  var allComms=[],catSet=new Set();
  if(Array.isArray(rawComms)&&rawComms.length&&rawComms[0].items){
    rawComms.forEach(function(cat){catSet.add(cat.category);(cat.items||[]).forEach(function(c){allComms.push({name:c.name,value:c.val||c.value||c.price||'',change:c.day||'',mm:c.mm||'',yy:c.yy||c.change||'',unit:c.unit||'',category:cat.category,context:c.context||''})})});
  }else if(Array.isArray(rawComms)){
    rawComms.forEach(function(c){var cat=c.category||'Other';catSet.add(cat);allComms.push({name:c.name,value:c.val||c.value||c.price||'',change:c.day||'',mm:c.mm||'',yy:c.yy||c.change||'',unit:c.unit||'',category:cat,context:c.context||''})});
  }
  if(!allComms.length)return '';
  _mktState._commAll=allComms;_mktState._commCat='All';
  var categories=['All'];catSet.forEach(function(c){categories.push(c)});

  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Commodities</h3>';
  h+='<span class="section-meta">Click any row for details \u00B7 '+allComms.length+' commodities</span></div><div class="market-card">';
  h+='<div class="cat-tabs">';
  categories.forEach(function(cat){h+='<div class="cat-tab'+(cat==='All'?' active':'')+'" data-cat="'+cat+'" onclick="_mktSetCatTab(this)">'+cat+'</div>'});
  h+='</div><div id="mktCmdTableWrap">'+_buildCmdTable(allComms,'All')+'</div>';
  var commNarr=(fm.commodityNarrative||fm.commodity_narrative||(D&&D.commodityCommentary))||'';
  if(commNarr)h+='<div class="market-narrative">'+san(commNarr)+'</div>';
  h+='</div></div>';return h;
}

function _buildCmdTable(comms,catFilter){
  if(!comms.length)return '<div style="padding:20px;color:#7a8599;font-size:14px">No commodity data available.</div>';
  var h='<div class="commodity-table-wrap"><table class="commodity-table"><thead><tr>';
  h+='<th>Commodity</th><th>Price</th><th>Weekly</th><th>M/M</th><th>Y/Y</th></tr></thead><tbody>';
  var lastCat='';
  comms.forEach(function(c,i){
    if(c.category&&c.category!==lastCat&&catFilter==='All'){h+='<tr><td colspan="5" class="cmd-group-divider">'+c.category+'</td></tr>';lastCat=c.category;}
    var uid='cmd_'+i;
    h+='<tr class="commodity-row" onclick="_mktToggleCmdRow(\''+uid+'\')">';
    h+='<td class="cmd-name"><span class="row-chevron" id="cmdChev_'+uid+'">\u25B6</span>'+c.name;
    if(c.unit)h+=' <span class="cmd-unit">'+c.unit+'</span>';
    h+='</td><td class="cmd-price">'+(c.value||'\u2014')+'</td>';
    h+='<td class="chg-'+_chgCls(c.change)+'">'+(c.change?_chgArrow(c.change)+c.change:'\u2014')+'</td>';
    h+='<td class="chg-'+_chgCls(c.mm)+'">'+(c.mm||'\u2014')+'</td>';
    h+='<td class="chg-'+_chgCls(c.yy)+'">'+(c.yy||'\u2014')+'</td></tr>';
    h+='<tr class="cmd-expand-row" id="cmdExp_'+uid+'"><td colspan="5"><div class="cmd-expand-content">';
    if(c.context)h+='<div class="cmd-narrative">'+san(c.context)+'</div>';
    else h+='<div class="cmd-narrative" style="color:#7a8599">No additional context available.</div>';
    h+='</div></td></tr>';
  });
  h+='</tbody></table></div>';return h;
}

window._mktToggleCmdRow=function(uid){
  var exp=document.getElementById('cmdExp_'+uid);if(!exp)return;
  var row=exp.previousElementSibling;
  if(exp.classList.contains('visible')){exp.classList.remove('visible');if(row)row.classList.remove('expanded')}
  else{exp.classList.add('visible');if(row)row.classList.add('expanded')}
};
window._mktSetCatTab=function(tab){
  var cat=tab.dataset.cat;_mktState._commCat=cat;
  tab.parentElement.querySelectorAll('.cat-tab').forEach(function(t){t.classList.toggle('active',t===tab)});
  var allComms=_mktState._commAll||[];
  var filtered=cat==='All'?allComms:allComms.filter(function(c){return c.category===cat});
  var wrap=document.getElementById('mktCmdTableWrap');
  if(wrap)wrap.innerHTML=_buildCmdTable(filtered,cat);
};

/* == Chart Helpers == */
function drawYieldChart(yc){
  const canvas=document.getElementById('yieldChart');
  if(!canvas)return;
  if(charts.yield)charts.yield.destroy();
  const labels=yc.map(y=>y.term);
  const data=yc.map(y=>parseFloat(y.yield)||0);
  charts.yield=new Chart(canvas,{type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.08)',borderWidth:2,pointRadius:4,pointBackgroundColor:'#3B82F6',pointBorderColor:'#3B82F6',pointBorderWidth:2,fill:true,tension:0.3}]},plugins:[{id:'yieldEndpoint',afterDraw(chart){const ds=chart.data.datasets[0];const lastVal=ds.data[ds.data.length-1];const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 11px DM Sans';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal,2)+'%':lastVal,lastPt.x+6,lastPt.y-4);ctx.restore();}}],options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(45,75,130,0.95)',titleColor:'#ffffff',bodyColor:'#93C5FD',borderColor:'rgba(0,0,0,0.12)',borderWidth:1,padding:10,cornerRadius:6}},scales:{x:{grid:{display:false},ticks:{font:{family:'DM Sans',size:11},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'DM Sans',size:11},color:'#636363',callback:v=>fmtNum(v,2)+'%'}}}}});
}
function drawLineChart(canvasId,tsData,months){
  const canvas=document.getElementById(canvasId);
  if(!canvas)return;
  if(charts[canvasId])charts[canvasId].destroy();
  if(!tsData||!tsData.series||!tsData.series.length){
    canvas.parentElement.insertAdjacentHTML('beforeend','<div style="text-align:center;color:#556B7A;font-size:var(--text-xs);padding:20px">No timeseries data available</div>');
    return;
  }
  const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-months);
  const filtered=tsData.series.filter(p=>new Date(p.date)>=cutoff).sort((a,b)=>new Date(a.date)-new Date(b.date));
  if(!filtered.length)return;
  const labels=filtered.map(p=>fmtDate(p.date));
  const data=filtered.map(p=>p.value);
  // Build event annotations for line chart
  const lcEvtAnnotations={};
  try{
    if(D&&(D.watchlist||D.events)){
      const wl=D.watchlist||D.events||[];
      wl.filter(e=>(e.impact||'').toLowerCase()==='high').forEach((evt,i)=>{
        try{
          const ed=parseEvtDate(evt.date);if(!ed)return;
          const ds=fmtDate(ed);const li=labels.indexOf(ds);if(li===-1)return;
          lcEvtAnnotations['evt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(245,158,11,0.5)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(evt.event_name||evt.name||'').substring(0,20),position:'start',backgroundColor:'rgba(245,158,11,0.85)',color:'#fff',font:{family:'DM Sans',size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
        }catch(e2){}
      });
    }
  }catch(e3){console.warn('Line chart event annotations:',e3)}
  const lcHasAnnotation=typeof window.ChartAnnotation!=='undefined'||Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation');
  const lcAnnotationCfg=lcHasAnnotation&&Object.keys(lcEvtAnnotations).length?{annotation:{annotations:{...lcEvtAnnotations}}}:{};
  charts[canvasId]=new Chart(canvas,{type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.06)',borderWidth:2,pointRadius:3,pointBackgroundColor:'#3B82F6',fill:true,tension:0.3}]},plugins:[{id:'lineEndpoint',afterDraw(chart){const ds=chart.data.datasets[0];const lastVal=ds.data[ds.data.length-1];const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 10px Outfit';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):lastVal,lastPt.x+4,lastPt.y-4);ctx.restore();}}],options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},...lcAnnotationCfg},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:6,font:{family:'DM Sans',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'DM Sans',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}});
}

function drawSparkline(canvasId,tsData,color){
  const canvas=document.getElementById(canvasId);
  if(!canvas||!tsData||!tsData.series||!tsData.series.length)return;
  if(charts[canvasId])charts[canvasId].destroy();
  const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
  const filtered=tsData.series.filter(p=>new Date(p.date)>=cutoff).sort((a,b)=>new Date(a.date)-new Date(b.date));
  if(filtered.length<2)return;
  const data=filtered.map(p=>p.value);
  const c=color||'#3B82F6';
  const mn=Math.min(...data),mx=Math.max(...data),pad=(mx-mn)*0.15||0.01;
  charts[canvasId]=new Chart(canvas,{type:'line',data:{labels:filtered.map(p=>p.date),datasets:[{data,borderColor:c,backgroundColor:c+'12',borderWidth:1.8,pointRadius:data.map((_,i)=>i===data.length-1?3:0),pointBackgroundColor:c,fill:true,tension:0.4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{enabled:false}},scales:{x:{display:false},y:{display:false,min:mn-pad,max:mx+pad}},elements:{line:{capBezierPoints:true}}}});
}
async function loadAndDrawSparkline(canvasId,docId,change){
  const ts=await loadTimeseries(docId);
  if(!ts)return;
  const c=change&&change.startsWith('-')?'#B91C1C':change&&(change.startsWith('+')||parseFloat(change)>0)?'#15803D':'#3B82F6';
  drawSparkline(canvasId,ts,c);
}

/* ====== PROJECTS TAB ====== */
async function renderProjectsTab(){
  // Load projects on demand if not yet loaded
  if(!allProjects.length){
    const prov=$('filterProvince')?.value||'BC';
    await loadProjects(prov||null);
  }
  // Populate filter dropdowns
  const provSel=$('filterProvince');
  if(provSel.options.length<=1){
    PROVS.forEach(p=>{const o=document.createElement('option');o.value=p.code;o.textContent=p.name;provSel.appendChild(o)});
    // Async: fetch project counts per province for display
    (async()=>{try{const r=await fetch('./data/projects_all.json');if(r.ok){const all=await r.json();const cnt={};all.forEach(p=>{cnt[p.province]=(cnt[p.province]||0)+1});provSel.querySelectorAll('option').forEach(o=>{if(o.value&&cnt[o.value])o.textContent+=` (${cnt[o.value]})`;})}}catch(e){}})();
  }
  const secSel=$('filterSector');
  if(secSel.options.length<=1){
    NAICS_CODES.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c+' '+NAICS_NAMES[c];secSel.appendChild(o)});
  }
  const stSel=$('filterStatus');
  if(stSel.options.length<=1){
    STATUSES.forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=s;stSel.appendChild(o)});
  }
  // Event listeners
  $('projectSearch').oninput=filterProjects;
  $('filterProvince').onchange=filterProjects;
  $('filterSector').onchange=filterProjects;
  $('filterStatus').onchange=filterProjects;
  $('sortProjects').onchange=filterProjects;
  $('loadMoreBtn').onclick=()=>{projectPage++;renderProjectTable()};
  filterProjects();
  // Populate missed project form dropdowns
  const mpProv=$('mpProvince');
  if(mpProv&&mpProv.options.length<=1){PROVS.forEach(p=>{const o=document.createElement('option');o.value=p.name;o.textContent=p.name;mpProv.appendChild(o)})}
  const mpSec=$('mpSector');
  if(mpSec&&mpSec.options.length<=1){NAICS_CODES.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c+' '+NAICS_NAMES[c];mpSec.appendChild(o)})}
}
async function submitMissedProject(){
  const fb=$('missedFormFeedback');
  if(fb){
    fb.style.display='block';
    fb.style.background='#FEF3C7';
    fb.style.color='#92400E';
    fb.textContent='Project submissions are being migrated to a new system. Check back soon!';
  }
}
async function filterProjects(){
  const search=($('projectSearch').value||'').toLowerCase();
  const prov=$('filterProvince').value||null;
  const sector=$('filterSector').value;
  const status=$('filterStatus').value;
  const sort=$('sortProjects').value;
  // If province changed, reload from static JSON
  if(prov!==_lastLoadedProvince){
    await loadProjects(prov);
    filterProjects();
    return;
  }
  filteredProjects=allProjects.filter(p=>{
    if(_confirmedOnly&&!meetsThreshold(p))return false;
    if(search&&!(p.name||'').toLowerCase().includes(search)&&!(p.cma||'').toLowerCase().includes(search)&&!(p.proponent||'').toLowerCase().includes(search))return false;
    if(prov&&normProvince(p.province)!==prov)return false;
    if(sector&&p.naics_code!==sector&&!(NAICS_NAMES[sector]&&(NAICS_NAMES[sector].toLowerCase().includes((p.sector||'').replace(/_/g,' ').toLowerCase())||(p.sector||'').toLowerCase().includes(NAICS_NAMES[sector].toLowerCase().split(',')[0].trim().toLowerCase()))))return false;
    if(status&&p.status!==status)return false;
    return true;
  });
  if(sort==='value_desc')filteredProjects.sort((a,b)=>parseNumericValue(b.value)-parseNumericValue(a.value));
  else if(sort==='updated')filteredProjects.sort((a,b)=>(b.lastSeen||'').localeCompare(a.lastSeen||''));
  else if(sort==='name_asc')filteredProjects.sort((a,b)=>(a.name||'').localeCompare(b.name||''));
  else if(sort==='confidence')filteredProjects.sort((a,b)=>(b.confidence||0)-(a.confidence||0));
  projectPage=0;
  renderProjectSummary();
  renderProjectTable();
}
function renderProjectSummary(){
  const total=filteredProjects.length;
  const totalVal=filteredProjects.reduce((s,p)=>s+parseNumericValue(p.value),0);
  const uc=filteredProjects.filter(p=>(p.status||'').toLowerCase().includes('construction')).length;
  const fv=v=>v>=1e9?'$'+(v/1e9).toFixed(1)+'B':v>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$0';
  const withUrls=filteredProjects.filter(p=>(p.evidence||[]).length>0).length;
  const withGov=filteredProjects.filter(p=>p.has_government_source).length;
  const pctVerified=total>0?Math.round(withUrls/total*100):0;
  let banner='';
  if(total>0)banner='<div class="verify-banner"><span>&#128279;</span><span>'+pctVerified+'% of projects have source links for independent verification.'+(withGov>0?' '+withGov+' backed by government sources.':'')+'</span></div>';
  $('projSummaryStats').innerHTML=banner+
    '<div class="proj-stat-card"><div class="proj-stat-val">'+total+'</div><div class="proj-stat-label">Total Projects</div></div>'+
    '<div class="proj-stat-card"><div class="proj-stat-val">'+fv(totalVal)+'</div><div class="proj-stat-label">Total Value</div></div>'+
    '<div class="proj-stat-card"><div class="proj-stat-val">'+uc+'</div><div class="proj-stat-label">Under Construction</div></div>';
}
function renderProjectTable(){
  const shown=filteredProjects.slice(0,(projectPage+1)*PAGE_SIZE);
  // Summary line
  const pf=$('filterProvince')?.value;
  const countNote=(!pf||pf==='')?'Showing '+shown.length+' of '+filteredProjects.length+' projects. Select a province for complete results. ('+allProjects.length+' most recent loaded)':'Showing '+shown.length+' of '+filteredProjects.length+' '+(PROVS.find(p=>p.code===pf)||{}).name+' projects';
  $('projectResultsSummary').textContent=countNote;
  // Table
  let html='<div class="project-table-wrap"><table class="project-table"><thead><tr><th scope="col">Value</th><th scope="col">Project</th><th scope="col">Type</th><th scope="col">Province</th><th scope="col">Proponent</th><th scope="col">Status</th><th scope="col">Sector</th><th scope="col">Updated</th><th scope="col">Src</th></tr></thead><tbody>';
  shown.forEach((p,i)=>{
    const rowId='proj_'+i;
    const firstEv=(p.evidence||[])[0]||{};
    const srcDead=firstEv.url_dead||false;
    const srcUrl=srcDead?'':((p.sources&&p.sources[0])?p.sources[0].url:'');
    const srcTitle=(p.sources&&p.sources[0])?p.sources[0].title:'';
    const updatedAgo=relDate(p.lastSeen||p.updated_at||'');
    const staleWarn=p.is_stale||(p.lastSeen&&(Date.now()-new Date(p.lastSeen+'T00:00:00').getTime())>2592000000);
    const provCode=normProvince(p.province);
    const naicsShort=NAICS_NAMES[p.naics_code]||_normSector(p.sector)||'';
    const pType=p.project_type||'greenfield';
    const isUnconf=!meetsThreshold(p);
    html+='<tr onclick="window.toggleProjectRow(\''+rowId+'\')"'+(isUnconf&&!_confirmedOnly?' class="unconfirmed-row"':'')+'>';
    html+='<td class="col-value">'+fmtCurrency(p.value,p)+(isUnconf?' <span class="unconfirmed-badge">unconfirmed</span>':'')+'</td>';
    html+='<td class="col-name">'+((p.name||'').substring(0,50))+'</td>';
    html+='<td>'+typeBadge(pType)+'</td>';
    html+='<td class="col-province">'+(provCode||((p.province||'').substring(0,3)))+(p.provinces_additional?'<span style="color:#556B7A;font-size:10px"> +'+p.provinces_additional.split(',').length+'</span>':'')+'</td>';
    html+='<td class="col-proponent">'+(p.proponent||'')+'</td>';
    html+='<td>'+statusBadge(p.status||'Proposed')+'</td>';
    html+='<td style="font-size:var(--text-xs)">'+naicsShort+'</td>';
    html+='<td class="col-updated"'+(staleWarn?' style="color:var(--status-amber)"':'')+'>'+updatedAgo+'</td>';
    html+='<td class="col-source">'+srcLink(srcUrl,srcTitle)+'</td>';
    html+='</tr>';
    // Expansion row
    const colSpan=9;
    html+='<tr id="'+rowId+'" style="display:none"><td colspan="'+colSpan+'"><div class="project-expand">';
    html+='<div style="font-size:var(--text-sm);color:#475569;margin-bottom:12px">'+(p.description||'No description available.')+'</div>';
    // Project timeline bar
    html+=buildTimeline(p);
    // CMA + confidence + quality row
    html+='<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px;font-size:var(--text-xs);color:#475569">';
    if(p.cma)html+='<span>CMA: <b>'+p.cma+'</b></span>';
    const evArr=p.evidence||[];
    const dispConf=p.display_confidence!=null?p.display_confidence:p.confidence;
    if(dispConf!=null)html+='<span>Confidence: '+confMeter(dispConf)+(p.decay_applied?' <span style="font-family:var(--font-mono);color:#556B7A;font-size:10px">(decay: -'+Math.round((p.decay_applied||0)*100)+'%)</span>':'')+'</span>';
    if(p.has_government_source)html+='<span class="gov-badge">GOV</span>';
    html+='<span>'+evArr.length+' source'+(evArr.length!==1?'s':'')+'</span>';
    if(p.has_anomalies)html+='<span style="color:var(--status-amber);font-weight:600" title="'+(p.anomalies||[]).map(a=>a.type+': '+a.detail).join('; ')+'">&#9888; Anomaly detected</span>';
    if(p.needs_review)html+='<span style="font-family:var(--font-mono);color:var(--status-red);font-weight:500">Needs review ('+p.days_since_update+'d stale)</span>';
    const dsSrc=p.discovery_sources||[];
    if(dsSrc.length>1)html+='<span>Found by '+dsSrc.length+' channels</span>';
    if(p.proponent)html+='<span>Proponent: <b>'+p.proponent+'</b></span>';
    html+='</div>';
    // Evidence sources with authority badges
    if(evArr.length){
      const authOrder={government:0,major_news:1,industry:2,regional_news:3,other:4};
      const sorted=[...evArr].sort((a,b)=>(authOrder[a.authority]||4)-(authOrder[b.authority]||4));
      html+='<details class="evidence-list"><summary style="cursor:pointer;font-size:var(--text-xs);color:var(--accent-blue)">'+evArr.length+' source'+(evArr.length>1?'s':'')+' -- click to verify independently</summary><ul style="margin:6px 0 0 0;padding:0;list-style:none">';
      sorted.forEach(e=>{
        html+='<li>';
        const auth=e.authority||'other';
        const badgeCfg={government:['GOV','src-badge-gov'],major_news:['NEWS','src-badge-news'],industry:['IND','src-badge-ind'],regional_news:['REG','src-badge-reg'],other:['SRC','src-badge-other']};
        const bc=badgeCfg[auth]||badgeCfg.other;
        html+='<span class="src-badge '+bc[1]+'">'+bc[0]+'</span> ';
        if(e.url&&!e.url_dead){
          let label=e.name||'';
          if(!label){try{const h=new URL(e.url).hostname;label=h.startsWith('www.')?h.slice(4):h}catch(_){label=e.url}}
          html+='<a href="'+e.url+'" target="_blank" rel="noopener noreferrer" style="word-break:break-all">'+label+'</a>';
        }else if(e.url&&e.url_dead){
          let label=e.name||'';
          if(!label){try{const h=new URL(e.url).hostname;label=h.startsWith('www.')?h.slice(4):h}catch(_){label=e.url}}
          html+='<span style="color:#556B7A;text-decoration:line-through;word-break:break-all">'+label+'</span> <span style="color:var(--status-red);font-size:10px">source unavailable</span>';
        }else{
          html+='<span>'+(e.name||'Unknown source')+'</span>';
        }
        if(e.date)html+=' <span style="color:#556B7A;font-size:10px">('+e.date+')</span>';
        if(e.url_verified===false&&!e.url_dead)html+='<span class="url-broken" title="Link may be broken">link may be unavailable</span>';
        html+='</li>';
      });
      html+='</ul></details>';
    }
    // Status history
    const sh=p.statusHistory||[];
    if(sh.length){
      html+='<div class="project-timeline">';
      sh.forEach(entry=>{
        html+='<div class="timeline-entry"><div class="timeline-date">'+fmtDate(entry.date||'')+'</div><div>'+statusBadge(entry.status||'')+(entry.detail?' <span style="color:#475569;font-size:var(--text-xs)">'+entry.detail+'</span>':'')+'</div>';
        const es=entry.source||{};
        if(es.url)html+='<div style="font-size:var(--text-xs);margin-top:2px">'+srcLink(es.url,es.title)+(es.archive_url?' <a href="'+es.archive_url+'" target="_blank" style="color:#556B7A">[Archived]</a>':'')+'</div>';
        html+='</div>';
      });
      html+='</div>';
    }
    // Suggest edit
    const eid='edit_'+i;
    html+='<div style="margin-top:10px"><button onclick="event.stopPropagation();toggleEditForm(\''+eid+'\')" style="background:none;border:1px solid var(--border);border-radius:5px;padding:4px 10px;font-size:var(--text-xs);color:var(--accent-blue-soft);cursor:pointer">Suggest Edit</button></div>';
    html+='<div id="'+eid+'" class="edit-form" style="display:none" onclick="event.stopPropagation()">';
    html+='<div class="edit-grid">';
    html+='<div><label>Value (e.g. $1.2B)</label><input type="text" id="'+eid+'_val" value="'+(p.value||'').replace(/"/g,'&quot;')+'"></div>';
    html+='<div><label>Status</label><select id="'+eid+'_status"><option value="">--</option>';
    STATUSES.forEach(s=>{html+='<option value="'+s+'"'+((p.status||'')===s?' selected':'')+'>'+s+'</option>'});
    html+='</select></div>';
    html+='<div><label>Proponent</label><input type="text" id="'+eid+'_prop" value="'+(p.proponent||'').replace(/"/g,'&quot;')+'"></div>';
    html+='<div><label>Completion Date</label><input type="date" id="'+eid+'_comp" value="'+(p.completionDate||'')+'"></div>';
    html+='</div>';
    html+='<div><label>Source URL (for verification)</label><input type="url" id="'+eid+'_src" placeholder="https://..."></div>';
    html+='<div><label>Notes</label><textarea id="'+eid+'_notes" rows="2" placeholder="Why is this correction needed?"></textarea></div>';
    html+='<button onclick="submitProjectCorrection(\''+eid+'\',\''+((p._id||'').replace(/'/g,"\\'"))+'\')" style="background:var(--accent);color:#fff;border:none;border-radius:5px;padding:5px 14px;font-size:var(--text-xs);cursor:pointer;margin-top:4px">Submit Correction</button>';
    html+='<div id="'+eid+'_fb" class="edit-feedback"></div>';
    html+='</div>';
    // Metadata
    html+='<div style="margin-top:12px;font-size:var(--text-xs);color:#556B7A">';
    if(p.firstTracked)html+='Tracked since '+fmtDate(p.firstTracked)+' \u00b7 ';
    if(p.lastSeen)html+='Last seen '+fmtDate(p.lastSeen)+' \u00b7 ';
    if(p.discovery_source)html+='<span class="disc-badge">'+p.discovery_source+'</span> ';
    if(p.history_backfilled&&p.history_earliest_date)html+='<span class="disc-badge">History since '+fmtDate(p.history_earliest_date)+'</span>';
    if(staleWarn)html+=' <span style="color:var(--status-amber);font-weight:500">\u26a0 Status unconfirmed since '+fmtDate(p.lastSeen)+'</span>';
    html+='</div></div></td></tr>';
  });
  html+='</tbody></table></div>';
  $('projectTableContainer').innerHTML=html;
  $('loadMoreBtn').style.display=shown.length<filteredProjects.length?'block':'none';
}
window.toggleProjectRow=function(id){
  const row=document.getElementById(id);
  if(row)row.style.display=row.style.display==='none'?'table-row':'none';
};
window.toggleEditForm=function(eid){
  const el=document.getElementById(eid);
  if(el)el.style.display=el.style.display==='none'?'block':'none';
};
window.submitProjectCorrection=function(){
  // Find the feedback element in the correction form
  const fbs=document.querySelectorAll('[id$="_fb"]');
  fbs.forEach(function(fb){
    fb.style.display='block';
    fb.style.background='#FEF3C7';
    fb.style.color='#92400E';
    fb.textContent='Project corrections are being migrated to a new system. Check back soon!';
  });
};
window.exportProjects=function(){
  if(!filteredProjects.length)return;
  const headers=['Name','Province','CMA','Sector','NAICS','Value','Status','Proponent','Type','Description','Discovery Source','First Tracked','Last Updated','Source URL','Confidence'];
  const rows=filteredProjects.map(p=>[
    p.name||'',p.province||'',p.cma||'',p.sector||'',p.naics_code||'',
    p.value||'Not disclosed',p.status||'',p.proponent||'',
    p.project_type||'',p.description||'',p.discovery_source||'',
    p.firstTracked||'',p.lastSeen||'',
    (p.sources&&p.sources[0])?p.sources[0].url:'',
    p.confidence!=null?Math.round(p.confidence*100)+'%':''
  ].map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(','));
  const csv=[headers.join(','),...rows].join('\n');
  const blob=new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='can-macro-projects_'+new Date().toISOString().split('T')[0]+'.csv';
  a.click();URL.revokeObjectURL(a.href);
};


/* ====== CALENDAR TAB ====== */
const CAL_PAGE_SIZE=10;
let _calMonth=null,_calYear=null,_calEvents=[],_calFilter={impact:'',institution:'',scope:'upcoming',search:''},_calWired=false,_calPage=1;
async function renderCalendar(){
  _calEvents=(D&&(D.watchlist||D.events))||[];
  if(!_calEvents.length){try{_calEvents=await fetchJSON('events.json')||[]}catch(_){_calEvents=[]}}
  // Merge US + European institution releases from static bridge file
  try{
    const globalData=await fetchJSON('events_global.json');
    if(globalData&&Array.isArray(globalData.events)){
      const seen=new Set(_calEvents.map(e=>(e.date||'')+'|'+(e.event_name||e.event||e.name||'')));
      globalData.events.forEach(e=>{
        const key=(e.date||'')+'|'+(e.event_name||'');
        if(!seen.has(key)){_calEvents.push(e);seen.add(key)}
      });
    }
  }catch(_){}
  const now=new Date();
  _calMonth=now.getMonth();_calYear=now.getFullYear();
  _calPopulateInstitutionFilter();
  _calRenderHeroStats();
  _calWireFilters();
  renderCalendarGrid();
  renderCalendarEvents();
}
window._calNav=function(dir){
  _calMonth+=dir;
  if(_calMonth>11){_calMonth=0;_calYear++}
  if(_calMonth<0){_calMonth=11;_calYear--}
  renderCalendarGrid();
};
window._calToday=function(){
  const now=new Date();_calMonth=now.getMonth();_calYear=now.getFullYear();
  renderCalendarGrid();
};
function _calPopulateInstitutionFilter(){
  const sel=$('calFilterInstitution');if(!sel)return;
  const cur=sel.value;
  const insts=[...new Set(_calEvents.map(e=>e.institution||e.source||'').filter(Boolean))].sort();
  sel.innerHTML='<option value="">All Sources</option>'+insts.map(i=>'<option value="'+i.replace(/"/g,'&quot;')+'">'+san(i)+'</option>').join('');
  if(cur&&insts.includes(cur))sel.value=cur;
}
function _calWireFilters(){
  if(_calWired)return;_calWired=true;
  ['calSearch','calFilterImpact','calFilterInstitution','calFilterScope'].forEach(id=>{
    const el=$(id);if(!el)return;
    const evt=(id==='calSearch')?'input':'change';
    el.addEventListener(evt,()=>{
      _calFilter.search=($('calSearch')||{}).value||'';
      _calFilter.impact=($('calFilterImpact')||{}).value||'';
      _calFilter.institution=($('calFilterInstitution')||{}).value||'';
      _calFilter.scope=($('calFilterScope')||{}).value||'upcoming';
      _calPage=1;
      renderCalendarEvents();
    });
  });
}
window._calGoPage=function(n){_calPage=n;renderCalendarEvents();const el=$('calendarEvents');if(el&&el.scrollIntoView)el.scrollIntoView({behavior:'smooth',block:'start'})};
function _calRenderHeroStats(){
  const now=new Date();now.setHours(0,0,0,0);
  const in7=new Date(now.getTime()+7*864e5);
  const in14=new Date(now.getTime()+14*864e5);
  const thisWeek=_calEvents.filter(e=>{const d=parseEvtDate(e.date);return d&&d>=now&&d<in7}).length;
  const nextWeek=_calEvents.filter(e=>{const d=parseEvtDate(e.date);return d&&d>=in7&&d<in14}).length;
  const setText=(id,val)=>{const el=$(id);if(el)el.textContent=String(val)};
  setText('calStatThisWeek',thisWeek.toLocaleString('en-CA'));
  setText('calStatNextWeek',nextWeek.toLocaleString('en-CA'));
}
function renderCalendarGrid(){
  const events=_calEvents;
  const now=new Date();
  const realMonth=now.getMonth(),realYear=now.getFullYear(),realDay=now.getDate();
  const year=_calYear,month=_calMonth;
  const firstDay=new Date(year,month,1).getDay();
  const daysInMonth=new Date(year,month+1,0).getDate();
  const monthName=new Date(year,month,1).toLocaleDateString('en-CA',{month:'long',year:'numeric'});

  const MONTHS_SHORT={jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11};
  const eventsByDate={};
  events.forEach(e=>{
    const d=e.date||'';if(!d)return;
    let eDay=0,eMonth=-1,eYear=year;
    if(d.includes('-')&&d.length>=8){
      eYear=parseInt(d.split('-')[0]);eMonth=parseInt(d.split('-')[1])-1;eDay=parseInt(d.split('-')[2]);
    }else{
      const parts=d.trim().split(/\s+/);
      if(parts.length>=2){eMonth=MONTHS_SHORT[(parts[0]||'').toLowerCase().slice(0,3)]??-1;eDay=parseInt(parts[1])||0;}
    }
    if(eYear===year&&eMonth===month&&eDay>0){
      if(!eventsByDate[eDay])eventsByDate[eDay]=[];
      eventsByDate[eDay].push(e);
    }
  });

  let calHtml='<div class="calendar-wrap">';
  calHtml+='<div class="calendar-nav"><div class="calendar-nav-btns"><button class="calendar-nav-btn" onclick="_calNav(-1)">\u2039 Prev</button><button class="calendar-nav-btn" onclick="_calToday()">Today</button><button class="calendar-nav-btn" onclick="_calNav(1)">Next \u203a</button></div>';
  calHtml+='<div class="calendar-nav-title">'+monthName+'</div></div>';
  calHtml+='<div class="calendar-grid">';
  ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(d=>{calHtml+='<div class="calendar-header-cell">'+d+'</div>'});
  for(let i=0;i<firstDay;i++)calHtml+='<div class="calendar-cell other-month"></div>';
  for(let d=1;d<=daysInMonth;d++){
    const isToday=(d===realDay&&month===realMonth&&year===realYear);
    const dayEvents=eventsByDate[d]||[];
    calHtml+='<div class="calendar-cell'+(isToday?' today':'')+'">';
    calHtml+='<div class="calendar-day-number">'+d+'</div>';
    if(dayEvents.length){
      dayEvents.forEach(e=>{
        const impact=(e.impact||'low').toLowerCase();
        calHtml+='<span class="cal-dot '+impact+'"></span>';
      });
      calHtml+='<div class="cal-tooltip">';
      dayEvents.forEach(e=>{
        const impact=(e.impact||'low').toLowerCase();
        const impactLabel=impact.charAt(0).toUpperCase()+impact.slice(1);
        calHtml+='<div class="cal-tooltip-event">';
        calHtml+='<div class="cal-tooltip-name">'+san(e.event_name||e.event||e.name||'')+'</div>';
        const inst=e.institution||e.source||'';
        if(inst)calHtml+='<div class="cal-tooltip-inst">'+san(inst)+'</div>';
        const desc=e.description||'';
        if(desc)calHtml+='<div class="cal-tooltip-desc">'+san(desc)+'</div>';
        calHtml+='<span class="cal-tooltip-impact '+impact+'">'+impactLabel+'</span>';
        calHtml+='</div>';
      });
      calHtml+='</div>';
    }
    calHtml+='</div>';
  }
  const totalCells=firstDay+daysInMonth;
  const remaining=7-(totalCells%7);
  if(remaining<7){for(let i=0;i<remaining;i++)calHtml+='<div class="calendar-cell other-month"></div>'}
  calHtml+='</div></div>';
  $('calendarGrid').innerHTML=calHtml;
}
function _calFilterEvents(){
  const now=new Date();now.setHours(0,0,0,0);
  const weekFromNow=new Date(now.getTime()+7*864e5);
  const monthEnd=new Date(now.getFullYear(),now.getMonth()+1,0,23,59,59);
  const threeMonths=new Date(now.getTime()+90*864e5);
  const q=(_calFilter.search||'').trim().toLowerCase();
  const byImpact=(_calFilter.impact||'').toLowerCase();
  const byInst=_calFilter.institution||'';
  const scope=_calFilter.scope||'upcoming';
  return _calEvents.filter(e=>{
    const d=parseEvtDate(e.date);if(!d)return false;
    if(d<now)return false;
    if(scope==='this_week'&&d>weekFromNow)return false;
    if(scope==='this_month'&&d>monthEnd)return false;
    if(scope==='next_3m'&&d>threeMonths)return false;
    if(byImpact&&(e.impact||'').toLowerCase()!==byImpact)return false;
    if(byInst&&(e.institution||e.source||'')!==byInst)return false;
    if(q){
      const hay=((e.event_name||e.event||e.name||'')+' '+(e.description||'')+' '+(e.institution||e.source||'')).toLowerCase();
      if(!hay.includes(q))return false;
    }
    return true;
  }).sort((a,b)=>parseEvtDate(a.date)-parseEvtDate(b.date));
}
function renderCalendarEvents(){
  const events=_calFilterEvents();
  const total=events.length;
  const totalPages=Math.max(1,Math.ceil(total/CAL_PAGE_SIZE));
  if(_calPage>totalPages)_calPage=totalPages;
  if(_calPage<1)_calPage=1;
  const start=(_calPage-1)*CAL_PAGE_SIZE;
  const pageEvents=events.slice(start,start+CAL_PAGE_SIZE);

  const meta=$('calEventsMeta');
  if(meta){
    if(total===0)meta.textContent='0 events';
    else if(totalPages===1)meta.textContent=total+(total===1?' event':' events');
    else meta.textContent=total+' events \u00b7 page '+_calPage+' of '+totalPages;
  }

  const container=$('calendarEvents');if(!container)return;
  if(!total){
    container.innerHTML='<div class="cal-empty">No events match the current filters.</div>';
    return;
  }
  let html='<div class="cal-events-table-wrap"><table class="cal-events-table"><thead><tr>';
  html+='<th class="cal-col-date">Date</th>';
  html+='<th class="cal-col-name">Event</th>';
  html+='<th class="cal-col-inst">Source</th>';
  html+='<th class="cal-col-impact">Impact</th>';
  html+='<th class="cal-col-source">Link</th>';
  html+='</tr></thead><tbody>';
  pageEvents.forEach(e=>{
    const ed=parseEvtDate(e.date);
    const impact=(e.impact||'low').toLowerCase();
    const impactLabel=impact.charAt(0).toUpperCase()+impact.slice(1);
    html+='<tr>';
    html+='<td class="cal-col-date">';
    if(ed){
      html+='<span class="cal-date-day">'+ed.toLocaleDateString('en-CA',{month:'short',day:'numeric'})+'</span>';
      html+='<span class="cal-date-sub">'+ed.toLocaleDateString('en-CA',{weekday:'short'})+' \u00b7 '+ed.getFullYear()+'</span>';
    }else{
      html+='<span class="cal-date-day">'+san(e.date||'\u2014')+'</span>';
    }
    html+='</td>';
    html+='<td class="cal-col-name">';
    html+='<span class="cal-event-name">'+san(e.event_name||e.event||e.name||'Untitled')+'</span>';
    if(e.description)html+='<span class="cal-event-desc">'+san(e.description)+'</span>';
    html+='</td>';
    html+='<td class="cal-col-inst">'+san(e.institution||e.source||'')+'</td>';
    html+='<td class="cal-col-impact"><span class="impact-pill '+impact+'">'+impactLabel+'</span></td>';
    html+='<td class="cal-col-source">'+srcLink(e.source_url||e.url,e.institution||e.source||'Source')+'</td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';

  if(totalPages>1){
    const prevDisabled=_calPage<=1?'disabled':'';
    const nextDisabled=_calPage>=totalPages?'disabled':'';
    html+='<div class="cal-pagination">';
    html+='<button onclick="_calGoPage('+(_calPage-1)+')" '+prevDisabled+'>\u2039 Prev</button>';
    html+='<span class="cal-page-info">Page '+_calPage+' of '+totalPages+'</span>';
    html+='<button onclick="_calGoPage('+(_calPage+1)+')" '+nextDisabled+'>Next \u203a</button>';
    html+='</div>';
  }

  container.innerHTML=html;
}


/* ====== PHASE 1: COST MONITOR WIDGET ====== */
/* ====== PHASE 2: POLICY SECTION ====== */
// Shared policy data cache — loaded once, reused by national + province renderers
let _policyCache=null;
async function _loadPolicyData(){
  if(_policyCache)return _policyCache;
  try{
    const raw=await fetchJSON('policy.json');
    // Normalize: extract all top_developments across weeks
    let items=[];
    let narrative='';
    if(raw.weeks&&Array.isArray(raw.weeks)){
      raw.weeks.forEach(w=>{
        const devs=w.summary?.top_developments||[];
        devs.forEach(d=>{d._week=w.week_of;if(!d.date)d.date=w.week_of});
        items=items.concat(devs);
        if(!narrative&&w.summary?.narrative)narrative=w.summary.narrative;
      });
    }
    // Legacy fallback: flat articles array
    if(!items.length&&raw.articles)items=raw.articles;
    _policyCache={items,raw,narrative};
    return _policyCache;
  }catch(e){_policyCache={items:[],raw:{},narrative:''};return _policyCache}
}

function _renderPolicyItems(items,maxItems){
  const cats={};
  items.forEach(a=>{(a.categories||[a.category||'other']).forEach(c=>{cats[c]=(cats[c]||0)+1})});
  const catBadges=Object.entries(cats).sort((a,b)=>b[1]-a[1]).map(([c,n])=>'<span style="display:inline-block;background:var(--bg-subtle,#f1f5f9);color:var(--text-secondary,#64748B);padding:2px 8px;border-radius:4px;font-size:10px;margin:2px">'+c.replace(/_/g,' ')+' ('+n+')</span>').join('');
  let listHtml='';
  items.slice(0,maxItems||10).forEach(a=>{
    const provCode=a.province||'';
    const level=a.level||'federal';
    const badge=level==='federal'
      ?'<span style="background:#dbeafe;color:#1d4ed8;padding:1px 6px;border-radius:3px;font-size:.6rem;margin-left:4px;font-weight:600">Federal</span>'
      :(provCode?'<span style="background:#dcfce7;color:#166534;padding:1px 6px;border-radius:3px;font-size:.6rem;margin-left:4px;font-weight:600">'+provCode+'</span>':'');
    const sectors=(a.affected_sectors||[]).slice(0,2).map(s=>s.replace(/_/g,' ')).join(', ');
    const sectorTag=sectors?'<span style="color:#94A3B8;font-size:9px;margin-left:6px">'+sectors+'</span>':'';
    const projCount=a.affected_projects_total||0;
    const projTag=projCount?'<span style="color:#94A3B8;font-size:9px;margin-left:4px">\u00b7 '+projCount+' projects</span>':'';
    const srcDesc=a.source_description||a.source||'';
    const dateStr=a.date?'<span style="color:#94A3B8;font-size:9px;margin-right:6px">'+a.date.split('T')[0]+'</span>':'';
    const summary=a.summary?'<div style="color:#64748B;font-size:10px;margin-top:2px;line-height:1.4">'+a.summary.substring(0,200)+(a.summary.length>200?'...':'')+'</div>':'';
    listHtml+='<div style="padding:8px 0;border-bottom:1px solid var(--border-light,#e2e8f0)">'+
      '<div style="font-size:var(--text-xs,12px)">'+dateStr+'<a href="'+(a.url||'#')+'" target="_blank" rel="noopener noreferrer" style="color:var(--accent-blue,#2563EB);text-decoration:none;font-weight:500">'+(a.title||a.headline||'Untitled')+'</a>'+badge+sectorTag+projTag+'</div>'+
      (srcDesc?'<div style="font-size:9px;color:#94A3B8;margin-top:1px">'+srcDesc+'</div>':'')+
      summary+'</div>';
  });
  return{catBadges,listHtml,count:items.length};
}

async function renderPolicySection(){
  const el=$('policyContent')||$('policySection');if(!el)return;
  try{
    const{items,narrative}=await _loadPolicyData();
    if(!items.length&&!narrative){el.innerHTML='';return}
    const{catBadges,listHtml,count}=_renderPolicyItems(items,10);
    const narrativeHtml=narrative?'<div style="font-size:var(--text-xs);color:var(--text-secondary,#475569);line-height:1.6;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--border-light,#e2e8f0)">'+narrative+'</div>':'';
    el.innerHTML='<details class="card fade-in" open><summary style="cursor:pointer;font-size:var(--text-sm);font-weight:600;color:#475569;padding:14px 18px;user-select:none">Policy Monitor ('+count+' development'+(count!==1?'s':'')+' this week)</summary><div style="padding:0 18px 14px">'+narrativeHtml+'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px">'+catBadges+'</div>'+listHtml+'</div></details>';
  }catch(e){console.warn('Policy section:',e);el.innerHTML=''}
}

async function renderProvincePolicySection(provCode,provName,containerEl){
  if(!containerEl)return;
  try{
    const{items}=await _loadPolicyData();
    // Filter: province-specific items + federal items (federal policy affects all provinces)
    const provItems=items.filter(a=>{
      const itemProv=(a.province||'').toUpperCase();
      const level=a.level||'federal';
      // Include federal items (affect all provinces) + province-specific items
      return level==='federal'||itemProv===provCode.toUpperCase();
    });
    if(!provItems.length){
      containerEl.innerHTML='<div class="prov-enrichment-section" style="margin-top:20px;padding:16px;background:var(--bg-alt,#f8fafc);border-radius:8px;border-left:3px solid var(--accent,#3b82f6)">'+
        '<div style="font-size:var(--text-sm);font-weight:700;color:var(--fg,#1e293b);margin-bottom:8px">Policy Monitor</div>'+
        '<div style="font-size:var(--text-xs);color:#94A3B8">No policy developments tracked for '+provName+' this week.</div></div>';
      return;
    }
    // Sort: province-specific first, then federal
    provItems.sort((a,b)=>{
      const aLocal=(a.province||'').toUpperCase()===provCode.toUpperCase()?0:1;
      const bLocal=(b.province||'').toUpperCase()===provCode.toUpperCase()?0:1;
      return aLocal-bLocal;
    });
    const{catBadges,listHtml,count}=_renderPolicyItems(provItems,8);
    const provSpecific=provItems.filter(a=>(a.province||'').toUpperCase()===provCode.toUpperCase()).length;
    const fedCount=count-provSpecific;
    const subtitle=provSpecific&&fedCount
      ?provSpecific+' provincial + '+fedCount+' federal developments'
      :provSpecific?provSpecific+' provincial developments'
      :fedCount+' federal developments affecting '+provName;
    containerEl.innerHTML='<div class="prov-enrichment-section" style="margin-top:20px;padding:16px;background:var(--bg-alt,#f8fafc);border-radius:8px;border-left:3px solid var(--accent,#3b82f6)">'+
      '<div style="font-size:var(--text-sm);font-weight:700;color:var(--fg,#1e293b);margin-bottom:4px">Policy Monitor</div>'+
      '<div style="font-size:10px;color:#94A3B8;margin-bottom:10px">'+subtitle+'</div>'+
      '<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">'+catBadges+'</div>'+
      listHtml+'</div>';
  }catch(e){console.warn('Province policy:',e);containerEl.innerHTML=''}
}

/* ====== PHASE 3: CANADIAN COMMODITIES ====== */
async function renderCanadianCommodities(){
  const el=$('canadianCommodities');if(!el)return;
  try{
    let data;
    try{data=await fetchJSON('commodities.json')}catch(_){el.innerHTML='';return}
    const indicators=data.indicators||data;
    const keys=Object.keys(indicators).filter(k=>k!=='updated_at'&&typeof indicators[k]==='object');
    if(!keys.length){el.innerHTML='';return}
    let html='<h3 style="font-size:var(--text-sm);font-weight:600;margin:0 0 8px;color:#8ea8cc;text-transform:uppercase;letter-spacing:1px">Canadian Commodity Indicators</h3><div class="market-grid">';
    keys.forEach(k=>{
      const c=indicators[k];
      const chg=c.pct_1w||'';const isNeg=String(chg).startsWith('-');
      const cls=isNeg?'change-down':(chg?'change-up':'change-flat');
      const sectors=(c.affected_sectors||[]).map(s=>'<span style="background:rgba(0,0,0,0.06);color:#475569;padding:1px 5px;border-radius:3px;font-size:.6rem">'+s+'</span>').join(' ');
      const provs=(c.affected_provinces||[]).map(p=>'<span style="background:rgba(0,0,0,0.05);color:#475569;padding:1px 5px;border-radius:3px;font-size:.6rem">'+p+'</span>').join(' ');
      html+=`<div class="market-card" data-cat="energy"><div class="market-card-ticker">${c.name||k.replace(/_/g,' ')}</div><div class="market-card-price">${c.current||'N/A'}</div>`;
      if(chg)html+=`<div class="market-card-change ${cls}">${isNeg?'\u2193':'\u2191'} ${chg} 1W</div>`;
      if(c.pct_1m)html+=`<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:#475569">1M: ${c.pct_1m}</div>`;
      if(sectors)html+=`<div style="display:flex;gap:2px;flex-wrap:wrap;margin-top:4px">${sectors}</div>`;
      if(provs)html+=`<div style="display:flex;gap:2px;flex-wrap:wrap;margin-top:2px">${provs}</div>`;
      html+='</div>';
    });
    html+='</div>';
    el.innerHTML=html;
  }catch(e){console.warn('Canadian commodities:',e);el.innerHTML=''}
}

/* ====== PHASE 4: DATA EXPLORER (V-Code Search) ====== */
const VCODE_INDEX=[
  // ── NATIONAL INDICATORS ──
  {vcode:'V41690973',table:'18-10-0004-01',title:'Consumer Price Index, monthly',keywords:'cpi inflation prices consumer',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V2062815',table:'14-10-0287-01',title:'Unemployment rate, seasonally adjusted',keywords:'unemployment rate labour jobs lfs',category:'Labour Market',freq:'Monthly',geo:'Canada'},
  {vcode:'V2062809',table:'14-10-0287-01',title:'Employment rate, seasonally adjusted',keywords:'employment rate labour jobs lfs',category:'Labour Market',freq:'Monthly',geo:'Canada'},
  {vcode:'V2062803',table:'14-10-0287-01',title:'Participation rate, seasonally adjusted',keywords:'participation rate labour force lfs',category:'Labour Market',freq:'Monthly',geo:'Canada'},
  {vcode:'V62305752',table:'36-10-0104-01',title:'Gross domestic product (GDP), quarterly',keywords:'gdp growth economy quarterly real',category:'GDP',freq:'Quarterly',geo:'Canada'},

  // ── CPI COMPONENTS ──
  {vcode:'V41693271',table:'18-10-0004-01',title:'CPI Energy',keywords:'energy gasoline fuel electricity cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693461',table:'18-10-0004-01',title:'CPI Shelter',keywords:'shelter housing rent mortgage cpi',category:'Housing',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693508',table:'18-10-0004-01',title:'CPI Food',keywords:'food grocery prices cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693242',table:'18-10-0004-01',title:'CPI All-items excluding food and energy (core)',keywords:'core cpi inflation excluding food energy',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693302',table:'18-10-0004-01',title:'CPI Transportation',keywords:'transportation vehicles gas auto insurance cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693380',table:'18-10-0004-01',title:'CPI Clothing and footwear',keywords:'clothing footwear apparel cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693414',table:'18-10-0004-01',title:'CPI Health and personal care',keywords:'health personal care medical cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693432',table:'18-10-0004-01',title:'CPI Recreation, education and reading',keywords:'recreation education reading cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693456',table:'18-10-0004-01',title:'CPI Household operations, furnishings and equipment',keywords:'household operations furnishings equipment cpi',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'V41693468',table:'18-10-0004-01',title:'CPI Alcoholic beverages, tobacco and cannabis',keywords:'alcohol tobacco cannabis beverages cpi',category:'Prices',freq:'Monthly',geo:'Canada'},

  // ── PROVINCIAL CPI ──
  {vcode:'V53620',table:'18-10-0006-01',title:'Consumer Price Index, by province',keywords:'cpi inflation prices provincial',category:'Prices',freq:'Monthly',geo:'Provinces'},
  {vcode:'V41690914',table:'18-10-0004-01',title:'CPI Newfoundland and Labrador',keywords:'cpi inflation newfoundland labrador nl',category:'Prices',freq:'Monthly',geo:'Newfoundland and Labrador'},
  {vcode:'V41690915',table:'18-10-0004-01',title:'CPI Prince Edward Island',keywords:'cpi inflation prince edward island pei',category:'Prices',freq:'Monthly',geo:'Prince Edward Island'},
  {vcode:'V41690916',table:'18-10-0004-01',title:'CPI Nova Scotia',keywords:'cpi inflation nova scotia ns',category:'Prices',freq:'Monthly',geo:'Nova Scotia'},
  {vcode:'V41690917',table:'18-10-0004-01',title:'CPI New Brunswick',keywords:'cpi inflation new brunswick nb',category:'Prices',freq:'Monthly',geo:'New Brunswick'},
  {vcode:'V41690918',table:'18-10-0004-01',title:'CPI Quebec',keywords:'cpi inflation quebec qc',category:'Prices',freq:'Monthly',geo:'Quebec'},
  {vcode:'V41690919',table:'18-10-0004-01',title:'CPI Ontario',keywords:'cpi inflation ontario on',category:'Prices',freq:'Monthly',geo:'Ontario'},
  {vcode:'V41690920',table:'18-10-0004-01',title:'CPI Manitoba',keywords:'cpi inflation manitoba mb',category:'Prices',freq:'Monthly',geo:'Manitoba'},
  {vcode:'V41690921',table:'18-10-0004-01',title:'CPI Saskatchewan',keywords:'cpi inflation saskatchewan sk',category:'Prices',freq:'Monthly',geo:'Saskatchewan'},
  {vcode:'V41690922',table:'18-10-0004-01',title:'CPI Alberta',keywords:'cpi inflation alberta ab',category:'Prices',freq:'Monthly',geo:'Alberta'},
  {vcode:'V41690923',table:'18-10-0004-01',title:'CPI British Columbia',keywords:'cpi inflation british columbia bc',category:'Prices',freq:'Monthly',geo:'British Columbia'},

  // ── PROVINCIAL UNEMPLOYMENT ──
  {vcode:'V2063004',table:'14-10-0287-01',title:'Unemployment rate, Newfoundland and Labrador',keywords:'unemployment rate newfoundland labrador nl lfs',category:'Labour Market',freq:'Monthly',geo:'Newfoundland and Labrador'},
  {vcode:'V2063193',table:'14-10-0287-01',title:'Unemployment rate, Prince Edward Island',keywords:'unemployment rate prince edward island pei lfs',category:'Labour Market',freq:'Monthly',geo:'Prince Edward Island'},
  {vcode:'V2063382',table:'14-10-0287-01',title:'Unemployment rate, Nova Scotia',keywords:'unemployment rate nova scotia ns lfs',category:'Labour Market',freq:'Monthly',geo:'Nova Scotia'},
  {vcode:'V2063571',table:'14-10-0287-01',title:'Unemployment rate, New Brunswick',keywords:'unemployment rate new brunswick nb lfs',category:'Labour Market',freq:'Monthly',geo:'New Brunswick'},
  {vcode:'V2063760',table:'14-10-0287-01',title:'Unemployment rate, Quebec',keywords:'unemployment rate quebec qc lfs',category:'Labour Market',freq:'Monthly',geo:'Quebec'},
  {vcode:'V2063949',table:'14-10-0287-01',title:'Unemployment rate, Ontario',keywords:'unemployment rate ontario on lfs',category:'Labour Market',freq:'Monthly',geo:'Ontario'},
  {vcode:'V2064138',table:'14-10-0287-01',title:'Unemployment rate, Manitoba',keywords:'unemployment rate manitoba mb lfs',category:'Labour Market',freq:'Monthly',geo:'Manitoba'},
  {vcode:'V2064327',table:'14-10-0287-01',title:'Unemployment rate, Saskatchewan',keywords:'unemployment rate saskatchewan sk lfs',category:'Labour Market',freq:'Monthly',geo:'Saskatchewan'},
  {vcode:'V2064516',table:'14-10-0287-01',title:'Unemployment rate, Alberta',keywords:'unemployment rate alberta ab lfs',category:'Labour Market',freq:'Monthly',geo:'Alberta'},
  {vcode:'V2064705',table:'14-10-0287-01',title:'Unemployment rate, British Columbia',keywords:'unemployment rate british columbia bc lfs',category:'Labour Market',freq:'Monthly',geo:'British Columbia'},

  // ── PROVINCIAL EMPLOYMENT RATE ──
  {vcode:'V2062998',table:'14-10-0287-01',title:'Employment rate, Newfoundland and Labrador',keywords:'employment rate newfoundland labrador nl lfs',category:'Labour Market',freq:'Monthly',geo:'Newfoundland and Labrador'},
  {vcode:'V2063187',table:'14-10-0287-01',title:'Employment rate, Prince Edward Island',keywords:'employment rate prince edward island pei lfs',category:'Labour Market',freq:'Monthly',geo:'Prince Edward Island'},
  {vcode:'V2063376',table:'14-10-0287-01',title:'Employment rate, Nova Scotia',keywords:'employment rate nova scotia ns lfs',category:'Labour Market',freq:'Monthly',geo:'Nova Scotia'},
  {vcode:'V2063565',table:'14-10-0287-01',title:'Employment rate, New Brunswick',keywords:'employment rate new brunswick nb lfs',category:'Labour Market',freq:'Monthly',geo:'New Brunswick'},
  {vcode:'V2063754',table:'14-10-0287-01',title:'Employment rate, Quebec',keywords:'employment rate quebec qc lfs',category:'Labour Market',freq:'Monthly',geo:'Quebec'},
  {vcode:'V2063943',table:'14-10-0287-01',title:'Employment rate, Ontario',keywords:'employment rate ontario on lfs',category:'Labour Market',freq:'Monthly',geo:'Ontario'},
  {vcode:'V2064132',table:'14-10-0287-01',title:'Employment rate, Manitoba',keywords:'employment rate manitoba mb lfs',category:'Labour Market',freq:'Monthly',geo:'Manitoba'},
  {vcode:'V2064321',table:'14-10-0287-01',title:'Employment rate, Saskatchewan',keywords:'employment rate saskatchewan sk lfs',category:'Labour Market',freq:'Monthly',geo:'Saskatchewan'},
  {vcode:'V2064510',table:'14-10-0287-01',title:'Employment rate, Alberta',keywords:'employment rate alberta ab lfs',category:'Labour Market',freq:'Monthly',geo:'Alberta'},
  {vcode:'V2064699',table:'14-10-0287-01',title:'Employment rate, British Columbia',keywords:'employment rate british columbia bc lfs',category:'Labour Market',freq:'Monthly',geo:'British Columbia'},

  // ── PROVINCIAL PARTICIPATION RATE ──
  {vcode:'V2062992',table:'14-10-0287-01',title:'Participation rate, Newfoundland and Labrador',keywords:'participation rate newfoundland labrador nl lfs',category:'Labour Market',freq:'Monthly',geo:'Newfoundland and Labrador'},
  {vcode:'V2063181',table:'14-10-0287-01',title:'Participation rate, Prince Edward Island',keywords:'participation rate prince edward island pei lfs',category:'Labour Market',freq:'Monthly',geo:'Prince Edward Island'},
  {vcode:'V2063370',table:'14-10-0287-01',title:'Participation rate, Nova Scotia',keywords:'participation rate nova scotia ns lfs',category:'Labour Market',freq:'Monthly',geo:'Nova Scotia'},
  {vcode:'V2063559',table:'14-10-0287-01',title:'Participation rate, New Brunswick',keywords:'participation rate new brunswick nb lfs',category:'Labour Market',freq:'Monthly',geo:'New Brunswick'},
  {vcode:'V2063748',table:'14-10-0287-01',title:'Participation rate, Quebec',keywords:'participation rate quebec qc lfs',category:'Labour Market',freq:'Monthly',geo:'Quebec'},
  {vcode:'V2063937',table:'14-10-0287-01',title:'Participation rate, Ontario',keywords:'participation rate ontario on lfs',category:'Labour Market',freq:'Monthly',geo:'Ontario'},
  {vcode:'V2064126',table:'14-10-0287-01',title:'Participation rate, Manitoba',keywords:'participation rate manitoba mb lfs',category:'Labour Market',freq:'Monthly',geo:'Manitoba'},
  {vcode:'V2064315',table:'14-10-0287-01',title:'Participation rate, Saskatchewan',keywords:'participation rate saskatchewan sk lfs',category:'Labour Market',freq:'Monthly',geo:'Saskatchewan'},
  {vcode:'V2064504',table:'14-10-0287-01',title:'Participation rate, Alberta',keywords:'participation rate alberta ab lfs',category:'Labour Market',freq:'Monthly',geo:'Alberta'},
  {vcode:'V2064693',table:'14-10-0287-01',title:'Participation rate, British Columbia',keywords:'participation rate british columbia bc lfs',category:'Labour Market',freq:'Monthly',geo:'British Columbia'},

  // ── PROVINCIAL GDP ──
  {vcode:'V62464519',table:'36-10-0402-01',title:'Real GDP, Newfoundland and Labrador',keywords:'gdp growth newfoundland labrador nl',category:'GDP',freq:'Annual',geo:'Newfoundland and Labrador'},
  {vcode:'V62464824',table:'36-10-0402-01',title:'Real GDP, Prince Edward Island',keywords:'gdp growth prince edward island pei',category:'GDP',freq:'Annual',geo:'Prince Edward Island'},
  {vcode:'V62465129',table:'36-10-0402-01',title:'Real GDP, Nova Scotia',keywords:'gdp growth nova scotia ns',category:'GDP',freq:'Annual',geo:'Nova Scotia'},
  {vcode:'V62465434',table:'36-10-0402-01',title:'Real GDP, New Brunswick',keywords:'gdp growth new brunswick nb',category:'GDP',freq:'Annual',geo:'New Brunswick'},
  {vcode:'V62465739',table:'36-10-0402-01',title:'Real GDP, Quebec',keywords:'gdp growth quebec qc',category:'GDP',freq:'Annual',geo:'Quebec'},
  {vcode:'V62466044',table:'36-10-0402-01',title:'Real GDP, Ontario',keywords:'gdp growth ontario on',category:'GDP',freq:'Annual',geo:'Ontario'},
  {vcode:'V62466349',table:'36-10-0402-01',title:'Real GDP, Manitoba',keywords:'gdp growth manitoba mb',category:'GDP',freq:'Annual',geo:'Manitoba'},
  {vcode:'V62466654',table:'36-10-0402-01',title:'Real GDP, Saskatchewan',keywords:'gdp growth saskatchewan sk',category:'GDP',freq:'Annual',geo:'Saskatchewan'},
  {vcode:'V62466959',table:'36-10-0402-01',title:'Real GDP, Alberta',keywords:'gdp growth alberta ab',category:'GDP',freq:'Annual',geo:'Alberta'},
  {vcode:'V62467264',table:'36-10-0402-01',title:'Real GDP, British Columbia',keywords:'gdp growth british columbia bc',category:'GDP',freq:'Annual',geo:'British Columbia'},

  // ── GDP BY INDUSTRY (20 NAICS) ──
  {vcode:'V65201229',table:'36-10-0434-01',title:'GDP Agriculture, forestry, fishing',keywords:'agriculture farming forestry gdp naics 11',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201236',table:'36-10-0434-01',title:'GDP Mining, quarrying, oil and gas',keywords:'mining oil gas extraction gdp naics 21',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201254',table:'36-10-0434-01',title:'GDP Utilities',keywords:'utilities power electricity gdp naics 22',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201258',table:'36-10-0434-01',title:'GDP Construction',keywords:'construction building gdp naics 23',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201263',table:'36-10-0434-01',title:'GDP Manufacturing',keywords:'manufacturing factory production gdp naics 31',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201358',table:'36-10-0434-01',title:'GDP Wholesale trade',keywords:'wholesale trade gdp naics 41',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201368',table:'36-10-0434-01',title:'GDP Retail trade',keywords:'retail shopping consumer gdp naics 44',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201381',table:'36-10-0434-01',title:'GDP Transportation and warehousing',keywords:'transportation logistics transit rail gdp naics 48',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201398',table:'36-10-0434-01',title:'GDP Information and cultural industries',keywords:'information media telecom technology gdp naics 51',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201407',table:'36-10-0434-01',title:'GDP Finance and insurance',keywords:'finance banking insurance gdp naics 52',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201419',table:'36-10-0434-01',title:'GDP Real estate',keywords:'real estate housing rental property gdp naics 53',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201429',table:'36-10-0434-01',title:'GDP Professional, scientific and technical services',keywords:'professional scientific technical consulting gdp naics 54',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201441',table:'36-10-0434-01',title:'GDP Management of companies',keywords:'management companies enterprises headquarters gdp naics 55',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201442',table:'36-10-0434-01',title:'GDP Administrative and support, waste management',keywords:'administrative support waste management remediation gdp naics 56',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201452',table:'36-10-0434-01',title:'GDP Educational services',keywords:'education schools university college gdp naics 61',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201457',table:'36-10-0434-01',title:'GDP Health care and social assistance',keywords:'health care hospital medical gdp naics 62',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201463',table:'36-10-0434-01',title:'GDP Arts, entertainment and recreation',keywords:'arts entertainment recreation tourism gdp naics 71',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201468',table:'36-10-0434-01',title:'GDP Accommodation and food services',keywords:'accommodation hotel food services restaurant gdp naics 72',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201471',table:'36-10-0434-01',title:'GDP Other services (except public administration)',keywords:'other services repair personal laundry gdp naics 81',category:'GDP',freq:'Monthly',geo:'Canada'},
  {vcode:'V65201476',table:'36-10-0434-01',title:'GDP Public administration',keywords:'public administration government military defence gdp naics 91',category:'GDP',freq:'Monthly',geo:'Canada'},

  // ── CONSTRUCTION & HOUSING ──
  {vcode:'V735391',table:'34-10-0066-01',title:'Building permits, by type of structure',keywords:'building permits construction residential commercial',category:'Construction',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'V111382687',table:'34-10-0175-01',title:'Building permits, by type of work',keywords:'construction new renovation addition permits',category:'Construction',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'V52367876',table:'27-10-0273-01',title:'Investment in building construction',keywords:'investment building construction capital spending',category:'Construction',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'V735337',table:'34-10-0035-01',title:'Housing starts',keywords:'housing starts cmhc residential new construction',category:'Housing',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'V1044832260',table:'33-10-0036-01',title:'New housing price index',keywords:'housing prices new house index nhpi',category:'Housing',freq:'Monthly',geo:'Canada, CMAs'},

  // ── BUILDING PERMITS BY CMA (Tier 9 anomaly detection) ──
  {vcode:'V77987',table:'34-10-0066-01',title:'Building permits, Toronto CMA',keywords:'building permits construction toronto ontario',category:'Construction',freq:'Monthly',geo:'Toronto'},
  {vcode:'V77971',table:'34-10-0066-01',title:'Building permits, Montreal CMA',keywords:'building permits construction montreal quebec',category:'Construction',freq:'Monthly',geo:'Montreal'},
  {vcode:'V78009',table:'34-10-0066-01',title:'Building permits, Vancouver CMA',keywords:'building permits construction vancouver bc',category:'Construction',freq:'Monthly',geo:'Vancouver'},
  {vcode:'V77951',table:'34-10-0066-01',title:'Building permits, Calgary CMA',keywords:'building permits construction calgary alberta',category:'Construction',freq:'Monthly',geo:'Calgary'},
  {vcode:'V77953',table:'34-10-0066-01',title:'Building permits, Edmonton CMA',keywords:'building permits construction edmonton alberta',category:'Construction',freq:'Monthly',geo:'Edmonton'},
  {vcode:'V77979',table:'34-10-0066-01',title:'Building permits, Ottawa CMA',keywords:'building permits construction ottawa ontario',category:'Construction',freq:'Monthly',geo:'Ottawa'},
  {vcode:'V77967',table:'34-10-0066-01',title:'Building permits, Winnipeg CMA',keywords:'building permits construction winnipeg manitoba',category:'Construction',freq:'Monthly',geo:'Winnipeg'},
  {vcode:'V77973',table:'34-10-0066-01',title:'Building permits, Quebec City CMA',keywords:'building permits construction quebec city',category:'Construction',freq:'Monthly',geo:'Quebec City'},
  {vcode:'V77981',table:'34-10-0066-01',title:'Building permits, Hamilton CMA',keywords:'building permits construction hamilton ontario',category:'Construction',freq:'Monthly',geo:'Hamilton'},
  {vcode:'V77957',table:'34-10-0066-01',title:'Building permits, Halifax CMA',keywords:'building permits construction halifax nova scotia',category:'Construction',freq:'Monthly',geo:'Halifax'},

  // ── TRADE & COMMERCE ──
  {vcode:'V1',table:'12-10-0011-01',title:'Canadian international merchandise trade',keywords:'trade exports imports merchandise international',category:'Trade',freq:'Monthly',geo:'Canada'},
  {vcode:'V37426',table:'16-10-0048-01',title:'Manufacturing sales',keywords:'manufacturing sales shipments production',category:'Trade',freq:'Monthly',geo:'Canada'},
  {vcode:'V52409870',table:'20-10-0008-01',title:'Retail trade sales',keywords:'retail sales consumer spending',category:'Trade',freq:'Monthly',geo:'Canada, provinces'},

  // ── LABOUR MARKET (additional) ──
  {vcode:'V120424858',table:'14-10-0064-01',title:'Employee wages by industry',keywords:'wages salary earnings income employee',category:'Labour Market',freq:'Monthly',geo:'Canada'},
  {vcode:'V39079',table:'BoC Valet',title:'Bank of Canada overnight rate',keywords:'interest rate overnight policy bank canada boc',category:'Rates',freq:'Daily',geo:'Canada'},
  {vcode:'V80691311',table:'11-10-0240-01',title:'Business insolvencies',keywords:'insolvency bankruptcy business failure',category:'GDP',freq:'Monthly',geo:'Canada, provinces'},

  // ── TABLE REFERENCES (no specific vector — link to full table) ──
  {vcode:'—',table:'17-10-0009-01',title:'Population estimates, quarterly',keywords:'population estimates growth demographic quarterly',category:'Demographics',freq:'Quarterly',geo:'Canada, provinces'},
  {vcode:'—',table:'14-10-0372-01',title:'Job vacancies by industry sector, monthly',keywords:'job vacancies vacancy rate openings hiring industry',category:'Labour Market',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'14-10-0371-01',title:'Job vacancies by province, monthly',keywords:'job vacancies vacancy rate openings provincial',category:'Labour Market',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'—',table:'14-10-0355-01',title:'Employment by industry, monthly',keywords:'employment industry sector jobs naics lfs',category:'Labour Market',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'14-10-0223-01',title:'Average weekly earnings by industry',keywords:'wages weekly earnings salary industry seph',category:'Labour Market',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'—',table:'20-10-0074-01',title:'Wholesale trade sales',keywords:'wholesale trade sales distribution',category:'Trade',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'—',table:'36-10-0018-01',title:'Balance of international payments, current account, SA',keywords:'balance payments current account trade surplus deficit',category:'Trade',freq:'Quarterly',geo:'Canada'},
  {vcode:'—',table:'36-10-0108-01',title:'International investment position',keywords:'international investment foreign assets liabilities',category:'Trade',freq:'Quarterly',geo:'Canada'},
  {vcode:'—',table:'36-10-0480-01',title:'Labour productivity and related measures',keywords:'labour productivity output per hour efficiency',category:'GDP',freq:'Quarterly',geo:'Canada'},
  {vcode:'—',table:'36-10-0222-01',title:'GDP at basic prices, provincial, monthly',keywords:'gdp provincial monthly economic output',category:'GDP',freq:'Monthly',geo:'Provinces'},
  {vcode:'—',table:'25-10-0015-01',title:'Electric power generation by type',keywords:'electricity power generation hydro nuclear wind solar coal',category:'Energy',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'—',table:'25-10-0063-01',title:'Supply and disposition of crude oil and natural gas',keywords:'crude oil natural gas supply production pipeline',category:'Energy',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'21-10-0024-01',title:'Capital and repair expenditures by industry',keywords:'capital expenditures investment capex repair industry',category:'Construction',freq:'Annual',geo:'Canada, provinces'},
  {vcode:'—',table:'18-10-0268-01',title:'Industrial product price index',keywords:'ippi industrial product producer prices manufacturing',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'18-10-0029-01',title:'Raw materials price index',keywords:'rmpi raw materials commodity input prices',category:'Prices',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'10-10-0147-01',title:'International merchandise trade by commodity (HS)',keywords:'merchandise trade commodity exports imports harmonized',category:'Trade',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'33-10-0163-01',title:'MLS home sales and average price',keywords:'mls real estate home sales average price housing market',category:'Housing',freq:'Monthly',geo:'Canada, provinces'},
  {vcode:'—',table:'11-10-0065-01',title:'Household sector credit market summary',keywords:'household debt credit mortgage consumer loans',category:'Rates',freq:'Quarterly',geo:'Canada'},
  {vcode:'—',table:'10-10-0006-01',title:'Canadian international transactions in securities',keywords:'securities transactions portfolio investment foreign bonds equities',category:'Trade',freq:'Monthly',geo:'Canada'},
  {vcode:'—',table:'23-10-0067-01',title:'Non-residential building construction price index',keywords:'construction price index non-residential building cost',category:'Construction',freq:'Quarterly',geo:'Canada, CMAs'},
];

/* Full StatCan table directory (loaded async from JSON) */
let _fullTableDir=[];
let _fullDirLoaded=false;
let _expSearchPage=1;
const EXP_PAGE_SIZE=10;
const FREQ_MAP={M:'Monthly',Q:'Quarterly',A:'Annual',D:'Daily',W:'Weekly',E:'Every 2 months',S:'Semi-annual',O:'Occasional'};

(async function loadTableDirectory(){
  try{
    const resp=await fetch('data/statcan_tables.json');
    if(!resp.ok)return;
    const raw=await resp.json();
    /* Build a Set of table IDs already in curated index */
    const curated=new Set(VCODE_INDEX.map(v=>v.table));
    _fullTableDir=raw.filter(r=>!curated.has(r.t)).map(r=>({
      vcode:'—',table:r.t,title:r.n,keywords:r.k,
      category:r.c,freq:FREQ_MAP[r.f]||r.f,geo:r.g,_dir:true
    }));
    _fullDirLoaded=true;
    if(typeof _expRenderHeroStats==='function')_expRenderHeroStats();
  }catch(e){/* silent — curated index still works */}
})();

/* Synonym map — expands user query words to related terms */
const _SYN={
  jobs:['employment','labour','workforce','hiring','vacancy','vacancies','lfs'],
  job:['employment','labour','workforce','hiring','vacancy','vacancies','lfs'],
  workers:['employment','labour','workforce','lfs'],
  hiring:['employment','job','vacancy','vacancies','labour'],
  wages:['salary','earnings','income','compensation','seph'],
  salary:['wages','earnings','income','compensation'],
  pay:['wages','salary','earnings','income'],
  income:['wages','salary','earnings'],
  houses:['housing','residential','shelter','home','dwelling'],
  homes:['housing','residential','shelter','home','dwelling'],
  house:['housing','residential','shelter','home','dwelling'],
  rent:['rental','shelter','housing','tenant','lease'],
  mortgage:['housing','shelter','home','lending','interest'],
  property:['real estate','housing','residential','commercial'],
  inflation:['cpi','prices','consumer','cost'],
  prices:['cpi','inflation','index','cost'],
  cost:['prices','cpi','inflation','expenditure'],
  oil:['crude','petroleum','wti','energy','extraction'],
  gas:['natural gas','lng','petroleum','energy'],
  energy:['oil','gas','electricity','power','utilities','hydro','nuclear','solar','wind'],
  power:['electricity','energy','utilities','hydro','generation'],
  electricity:['power','energy','utilities','hydro','generation'],
  trade:['exports','imports','merchandise','international','commerce'],
  exports:['trade','merchandise','international','shipments'],
  imports:['trade','merchandise','international'],
  mining:['quarrying','extraction','mineral','ore'],
  construction:['building','permits','infrastructure','capex'],
  building:['construction','permits','residential','commercial'],
  permits:['building','construction','approval','development'],
  manufacturing:['factory','production','industrial','plant','shipments'],
  factory:['manufacturing','production','industrial','plant'],
  gdp:['growth','output','economy','economic','gross domestic'],
  economy:['gdp','growth','output','economic'],
  growth:['gdp','economy','output','expansion'],
  debt:['credit','borrowing','loans','liabilities','deficit'],
  spending:['expenditure','consumption','retail','consumer'],
  population:['demographic','census','migration','immigration'],
  immigration:['migration','immigrant','population','newcomer'],
  health:['healthcare','hospital','medical','nursing'],
  hospital:['health','healthcare','medical','nursing'],
  school:['education','university','college','student'],
  education:['school','university','college','student','training'],
  transport:['transportation','transit','rail','logistics','shipping'],
  transit:['transportation','transport','rail','bus','lrt','subway'],
  farming:['agriculture','crop','livestock','farm'],
  agriculture:['farming','crop','livestock','farm','forestry'],
  tourism:['travel','hotel','accommodation','recreation','visitor'],
  travel:['tourism','hotel','accommodation','visitor'],
  insolvency:['bankruptcy','failure','default'],
  bankruptcy:['insolvency','failure','default'],
  productivity:['efficiency','output','labour'],
  investment:['capital','capex','expenditure','spending'],
  securities:['bonds','equities','stocks','portfolio'],
  stocks:['equities','securities','shares','market'],
  bonds:['securities','fixed income','debt','yield'],
  interest:['rate','overnight','policy','boc','lending','mortgage'],
  rate:['interest','overnight','policy','percentage'],
  lumber:['forestry','wood','timber','sawmill'],
  auto:['automotive','vehicle','car','motor'],
  retail:['shopping','consumer','sales','store'],
  wholesale:['distribution','trade','sales'],
  telecom:['telecommunications','broadband','internet','wireless'],
  tech:['technology','information','digital','innovation'],
  military:['defence','defense','dnd','armed forces'],
  defence:['military','defense','dnd','armed forces'],
};

function _expandQuery(words){
  const expanded=new Set(words);
  words.forEach(w=>{
    const syns=_SYN[w];
    if(syns)syns.forEach(s=>expanded.add(s));
  });
  return Array.from(expanded);
}

function searchVCodes(query){
  if(!query||query.length<2)return[];
  const qRaw=query.toLowerCase().split(/\s+/).filter(w=>w.length>1);
  const q=_expandQuery(qRaw);
  /* Search curated entries (boosted) then full directory */
  const score=(v,boost)=>{
    const text=(v.title+' '+v.keywords+' '+v.category+' '+v.geo).toLowerCase();
    let s=0;
    q.forEach(w=>{
      if(text.includes(w))s+=1;
      if(v.title.toLowerCase().includes(w))s+=2;
      if(v.keywords&&v.keywords.includes(w))s+=1;
    });
    return s>0?s+boost:0;
  };
  const curatedResults=VCODE_INDEX.map(v=>({...v,score:score(v,5)})).filter(v=>v.score>0);
  const dirResults=_fullTableDir.map(v=>({...v,score:score(v,0)})).filter(v=>v.score>0);
  return curatedResults.concat(dirResults).sort((a,b)=>b.score-a.score).slice(0,25);
}

/* Hero stats for the Data Explorer tab — Indicators · V-Codes · StatCan Tables · Updated.
   Called on every renderExplorer() and once more when the async statcan_tables.json load
   completes so the "StatCan Tables" count updates from 0 to the real value. */
function _expRenderHeroStats(){
  const indEl=$('expStatIndicators');
  if(!indEl)return;
  const setText=(id,val)=>{const el=$(id);if(el)el.textContent=String(val)};
  const indCount=(_indJsonCache&&Array.isArray(_indJsonCache.indicators))?_indJsonCache.indicators.length:(Array.isArray(indicators)?indicators.length:0);
  setText('expStatIndicators',indCount.toLocaleString('en-CA'));
  setText('expStatVcodes',VCODE_INDEX.length.toLocaleString('en-CA'));
  // StatCan Tables = the full directory count loaded from statcan_tables.json (curated tables
  // are filtered out before storage, so add them back for the headline count)
  const tablesTotal=_fullDirLoaded?(_fullTableDir.length+VCODE_INDEX.length):0;
  setText('expStatTables',_fullDirLoaded?tablesTotal.toLocaleString('en-CA'):'…');
  // Updated from statcan_latest.updatedAt if available
  let upd='—';
  const sc=_indJsonCache&&_indJsonCache.statcan_latest;
  if(sc&&sc.updatedAt){
    try{
      const d=new Date(sc.updatedAt);
      if(!isNaN(d)){
        upd=d.toLocaleDateString('en-CA',{month:'short',day:'numeric'});
      }else{
        upd=sc.updatedAt;
      }
    }catch(e){upd=sc.updatedAt}
  }
  setText('expStatUpdated',upd);
}

function renderExplorer(){
  const searchEl=$('explorerSearch');
  const catEl=$('explorerCategories');
  const resEl=$('explorerResults');
  if(!searchEl)return;

  _expRenderHeroStats();

  searchEl.innerHTML='<div class="exp-search-row"><input type="text" id="vcodeSearch" class="exp-search-input" placeholder="Search StatCan tables (e.g. unemployment, housing, GDP)..." onkeyup="if(event.key===\'Enter\'){_expSearchPage=1;window._doVcodeSearch()}"><button class="exp-search-btn" onclick="_expSearchPage=1;window._doVcodeSearch()">Search</button></div>';

  const categories=['Labour Market','GDP','Construction','Housing','Prices','Trade','Energy','Manufacturing','Agriculture','Infrastructure','Transportation','Health','Demographics','Tourism'];
  catEl.innerHTML='<div class="exp-cat-row">'+categories.map(c=>'<button class="exp-cat-btn" onclick="_expSearchPage=1;window._doVcodeSearch(\''+c+'\')">'+c+'</button>').join('')+'</div>';

  resEl.innerHTML='<div class="exp-empty">Enter a search term or click a category to find StatCan tables.</div>';
  const metaEl=$('expSearchMeta');if(metaEl)metaEl.textContent='';

  // National indicator section: StatCan key economic indicators + explorer chart
  const cis=$('canadaIndicatorSection');
  if(cis){
    cis.innerHTML='<div class="exp-card"><div class="exp-card-title">Statistics Canada \u2014 Key Economic Indicators</div><div class="exp-card-sub">Official economic indicators published by Statistics Canada (<a href="https://www150.statcan.gc.ca/n1/dai-quo/ssi/homepage/ind-econ-eng.htm" target="_blank" rel="noopener noreferrer">source</a>)</div><div id="canadaIndicatorDropdown"></div><section id="indicatorExplorer"></section></div>';
    const dd=$('canadaIndicatorDropdown');
    if(dd){
      // Use StatCan feed indicators if available, otherwise fall back to raw national indicators
      const scData=_indJsonCache&&_indJsonCache.statcan_latest;
      const scInds=(scData&&scData.indicators)||[];
      if(scInds.length){
        // Categorize StatCan indicators
        const _catMap=(name)=>{
          const n=(name||'').toLowerCase();
          if(n.includes('gdp')||n.includes('capacity'))return 'GDP & Output';
          if(n.includes('employ')||n.includes('labour')||n.includes('wage')||n.includes('earning')||n.includes('insurance benefic'))return 'Labour Market';
          if(n.includes('price index')||n.includes('cpi')||n.includes('food')||n.includes('shelter')||n.includes('transportation'))return 'Prices';
          if(n.includes('housing')||n.includes('building')||n.includes('construction'))return 'Housing & Construction';
          if(n.includes('export')||n.includes('import')||n.includes('trade')||n.includes('inventory')||n.includes('merchandise')||n.includes('unfilled'))return 'Trade & Manufacturing';
          if(n.includes('household')||n.includes('saving')||n.includes('debt')||n.includes('net worth')||n.includes('retail')||n.includes('wholesale'))return 'Household & Retail';
          if(n.includes('tourism')||n.includes('visitor')||n.includes('returning'))return 'Tourism & Travel';
          if(n.includes('farm')||n.includes('canola')||n.includes('wheat')||n.includes('corn')||n.includes('soy'))return 'Agriculture';
          if(n.includes('investment')||n.includes('capital')||n.includes('securities')||n.includes('profit')||n.includes('current account')||n.includes('terms of trade'))return 'Investment & Finance';
          if(n.includes('productivity'))return 'Productivity';
          return 'Other';
        };
        const scFormatted=scInds.map(i=>({
          name:i.name||'',
          indicator_name:(i.name||'').toLowerCase().replace(/[^a-z0-9]/g,'_'),
          value:i.value||'',
          change:i.change||'',
          arrow:i.arrow||0,
          refPer:i.refPer||'',
          category:_catMap(i.name),
          source:'Statistics Canada',
          tableUrl:i.tableUrl||'',
          frequency:i.frequency||''
        }));
        dd.innerHTML=renderIndicatorDropdown(scFormatted,'Statistics Canada Indicators ('+scFormatted.length+')','_canada');
      }else{
        const natInds=indicators.filter(ind=>{
          const p=(ind.province||'').toLowerCase();
          return !p||p==='national'||p==='canada';
        });
        dd.innerHTML=renderIndicatorDropdown(natInds,'All National Indicators ('+natInds.length+')','_canada');
      }
    }
    renderIndicatorExplorer();
  }

  // Provincial Indicator Explorer (like national but with province selector)
  _renderProvExplorer();

  // Ontario Economic Accounts (OEA) section
  _renderOeaSection();

  // Quebec ISQ section
  _renderIsqSection();

  // Provincial indicator dropdown (raw list)
  const pis=$('provIndicatorSection');
  if(pis){
    const prov=PROVS.find(p=>p.code===selectedProvince)||PROVS[0];
    const provInds=indicators.filter(ind=>{
      const p=(ind.province||'').toLowerCase();
      return p===prov.code.toLowerCase()||p===prov.name.toLowerCase();
    });
    pis.innerHTML='<div class="exp-card"><div class="exp-card-title">'+prov.name+' Raw Indicators</div><div class="exp-card-sub">All indicator records for '+prov.name+'</div>'+
      renderIndicatorDropdown(provInds,prov.name+' Indicators ('+provInds.length+')','_prov')+'</div>';
  }
}

/* Provincial Indicator Explorer — like the national one but with province selector */
let _provExpSel='cpi',_provExpProv='ON',_provExpRange=12,_provExpData={};

function _renderProvExplorer(){
  const el=$('provExpSection');if(!el)return;
  const prov=PROVS.find(p=>p.code===_provExpProv)||PROVS[0];
  const provItems=[
    {id:'cpi',label:'CPI (All Items)',unit:'%'},
    {id:'unemployment',label:'Unemployment Rate',unit:'%'},
    {id:'employmentRate',label:'Employment Rate',unit:'%'},
    {id:'participationRate',label:'Participation Rate',unit:'%'},
    {id:'wageGrowth',label:'Wage Growth',unit:'%'},
    {id:'housingStarts',label:'Housing Starts',unit:'units'}
  ];

  let html='<div class="exp-card">';
  html+='<div class="exp-card-title">Provincial Indicator Explorer</div>';
  html+='<div class="exp-card-sub">Compare provincial indicators with interactive charts</div>';

  // Province selector + indicator selector + range buttons
  html+='<div class="exp-control-row">';
  html+='<select id="provExpProvSel" class="exp-select" onchange="_provExpProv=this.value;_provExpData={};_renderProvExplorer()">';
  PROVS.forEach(p=>{html+='<option value="'+p.code+'"'+(p.code===_provExpProv?' selected':'')+'>'+p.name+'</option>'});
  html+='</select>';
  html+='<select id="provExpIndSel" class="exp-select" onchange="_provExpSel=this.value;_loadProvExpData()">';
  provItems.forEach(it=>{html+='<option value="'+it.id+'"'+(it.id===_provExpSel?' selected':'')+'>'+it.label+'</option>'});
  html+='</select>';
  html+='<div class="exp-range-group">';
  [3,12,36,60].forEach(m=>{
    const lbl=m===3?'3M':m===12?'1Y':m===36?'3Y':'5Y';
    const active=_provExpRange===m?' active':'';
    html+='<button class="exp-range-btn'+active+'" onclick="_provExpRange='+m+';_loadProvExpData()">'+lbl+'</button>';
  });
  html+='</div></div>';
  html+='<div id="provExpCallout"></div>';
  html+='<div class="exp-chart-wrap"><canvas id="provExpCanvas"></canvas></div>';
  html+='</div>';
  el.innerHTML=html;
  _loadProvExpData();
}

async function _loadProvExpData(){
  const cacheKey=_provExpSel+'_'+_provExpProv;
  if(!_provExpData[cacheKey]){
    try{
      const all=await fetchJSON('indicators.json');
      const hist=all.history||all.indicators||all;
      const pts=(Array.isArray(hist)?hist:[])
        .filter(r=>(r.indicator_name||r.indicator)===_provExpSel&&(r.province||'')==_provExpProv)
        .map(r=>({date:r.period||r.date,value:parseFloat(r.value)||0}))
        .sort((a,b)=>(a.date||'').localeCompare(b.date||''));
      _provExpData[cacheKey]=pts;
    }catch(e){_provExpData[cacheKey]=[]}
  }
  const allPts=_provExpData[cacheKey]||[];
  const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-_provExpRange);
  const pts=allPts.filter(p=>new Date(p.date)>=cutoff);
  // Callout
  const callout=$('provExpCallout');
  if(callout){
    if(pts.length>=2){
      const latest=pts[pts.length-1];const prev=pts[pts.length-2];
      const diff=latest.value-prev.value;
      const arrow=diff>0?'\u25b2':diff<0?'\u25bc':'\u25cf';
      const cls=diff>0?'up':diff<0?'down':'flat';
      callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">'+fmtNum(latest.value)+'</span><span class="exp-callout-chg '+cls+'">'+arrow+' '+(diff>=0?'+':'')+fmtNum(diff)+' vs prev</span><span class="exp-callout-meta">'+latest.date+'</span></div>';
    }else if(pts.length===1){
      callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">'+fmtNum(pts[0].value)+'</span></div>';
    }else{
      callout.innerHTML='<div class="exp-callout"><span class="exp-callout-empty">No data for '+_provExpProv+' / '+_provExpSel+' in this period.</span></div>';
    }
  }
  // Chart
  const canvas=$('provExpCanvas');if(!canvas)return;
  if(charts._provExp)charts._provExp.destroy();
  if(!pts.length)return;
  charts._provExp=new Chart(canvas,{type:'line',data:{labels:pts.map(p=>p.date),datasets:[{data:pts.map(p=>p.value),borderColor:'#2563EB',backgroundColor:'rgba(37,99,235,0.08)',borderWidth:2,pointRadius:pts.length>40?0:3,pointBackgroundColor:'#2563EB',fill:true,tension:0.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'DM Sans',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.05)',lineWidth:0.5},ticks:{font:{family:'DM Sans',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}});
}

/* Ontario Economic Accounts (OEA) Section */
let _oeaSel='on_real_consumption',_oeaRange=36,_oeaData={};

function _renderOeaSection(){
  const el=$('oeaSection');if(!el)return;
  const oeaItems=[
    {id:'on_real_consumption',label:'Real Consumption'},
    {id:'on_real_household',label:'Household Spending'},
    {id:'on_real_gov_expenditure',label:'Gov Expenditure'},
    {id:'on_real_capital_investment',label:'Capital Investment'},
    {id:'on_exports',label:'Exports'},
    {id:'on_imports',label:'Imports'},
    {id:'on_gdp_goods',label:'GDP Goods-Producing'},
    {id:'on_consumption_pct',label:'Consumption Q/Q %'},
    {id:'on_household_pct',label:'Household Q/Q %'},
    {id:'on_gov_expenditure_pct',label:'Gov Spend Q/Q %'},
    {id:'on_capital_investment_pct',label:'Capital Inv Q/Q %'},
    {id:'on_exports_pct',label:'Exports Q/Q %'},
    {id:'on_imports_pct',label:'Imports Q/Q %'},
    {id:'on_gdp_goods_pct',label:'GDP Goods Q/Q %'}
  ];

  let html='<div class="exp-card">';
  html+='<div class="exp-card-title">Ontario Economic Accounts (OEA)</div>';
  html+='<div class="exp-card-sub">Quarterly provincial accounts from <a href="https://data.ontario.ca/dataset/ontario-economic-accounts" target="_blank" rel="noopener noreferrer">Ontario Data Catalogue</a></div>';
  html+='<div class="exp-control-row">';
  html+='<select id="oeaIndSel" class="exp-select" onchange="_oeaSel=this.value;_loadOeaData()">';
  oeaItems.forEach(it=>{html+='<option value="'+it.id+'"'+(it.id===_oeaSel?' selected':'')+'>'+it.label+'</option>'});
  html+='</select>';
  html+='<div class="exp-range-group">';
  [12,36,60].forEach(m=>{
    const lbl=m===12?'1Y':m===36?'3Y':'5Y';
    const active=_oeaRange===m?' active':'';
    html+='<button class="exp-range-btn'+active+'" onclick="_oeaRange='+m+';_loadOeaData()">'+lbl+'</button>';
  });
  html+='</div></div>';
  // Latest values table
  html+='<div id="oeaLatestTable"></div>';
  html+='<div id="oeaCallout"></div>';
  html+='<div class="exp-chart-wrap"><canvas id="oeaCanvas"></canvas></div>';
  html+='</div>';
  el.innerHTML=html;
  _renderOeaLatestTable(oeaItems);
  _loadOeaData();
}

function _renderOeaLatestTable(oeaItems){
  const tbl=$('oeaLatestTable');if(!tbl)return;
  // Find latest value for each OEA indicator from indicators[]
  const rows=oeaItems.map(it=>{
    const ind=indicators.find(x=>(x.indicator_name||'')==it.id);
    return {label:it.label,value:ind?ind.value:'—',period:ind?(ind.refPer||ind.period||''):'',unit:it.id.includes('_pct')?'%':'$M'};
  }).filter(r=>r.value!=='—'&&r.value!=null);
  if(!rows.length){tbl.innerHTML='';return}
  let html='<div class="exp-stat-grid">';
  rows.forEach(r=>{
    html+='<div class="exp-stat-card">';
    html+='<div class="exp-stat-card-label">'+r.label+'</div>';
    html+='<div class="exp-stat-card-value">'+fmtNum(parseFloat(r.value)||0)+' <small>'+r.unit+'</small></div>';
    if(r.period)html+='<div class="exp-stat-card-period">'+r.period+'</div>';
    html+='</div>';
  });
  html+='</div>';
  tbl.innerHTML=html;
}

async function _loadOeaData(){
  if(!_oeaData[_oeaSel]){
    try{
      const all=await fetchJSON('indicators.json');
      const hist=all.history||[];
      const pts=hist.filter(r=>(r.indicator_name||'')==_oeaSel)
        .map(r=>({date:r.period||r.date,value:parseFloat(r.value)||0}))
        .sort((a,b)=>(a.date||'').localeCompare(b.date||''));
      _oeaData[_oeaSel]=pts;
    }catch(e){_oeaData[_oeaSel]=[]}
  }
  const allPts=_oeaData[_oeaSel]||[];
  const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-_oeaRange);
  const pts=allPts.filter(p=>new Date(p.date)>=cutoff);
  const callout=$('oeaCallout');
  if(callout){
    if(pts.length>=2){
      const latest=pts[pts.length-1];const prev=pts[pts.length-2];
      const diff=latest.value-prev.value;const arrow=diff>0?'\u25b2':diff<0?'\u25bc':'\u25cf';
      const cls=diff>0?'up':diff<0?'down':'flat';
      callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">'+fmtNum(latest.value)+'</span><span class="exp-callout-chg '+cls+'">'+arrow+' '+(diff>=0?'+':'')+fmtNum(diff)+' vs prev</span><span class="exp-callout-meta">'+latest.date+'</span></div>';
    }else{callout.innerHTML='<div class="exp-callout"><span class="exp-callout-empty">No history available.</span></div>'}
  }
  const canvas=$('oeaCanvas');if(!canvas)return;
  if(charts._oea)charts._oea.destroy();
  if(!pts.length)return;
  charts._oea=new Chart(canvas,{type:'line',data:{labels:pts.map(p=>p.date),datasets:[{data:pts.map(p=>p.value),borderColor:'#2563EB',backgroundColor:'rgba(37,99,235,0.08)',borderWidth:2,pointRadius:pts.length>30?0:4,pointBackgroundColor:'#2563EB',fill:true,tension:0.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'DM Sans',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.05)',lineWidth:0.5},ticks:{font:{family:'DM Sans',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}});
}

/* Quebec ISQ Section */
let _isqSel='qc_real_gdp',_isqRange=36,_isqData={};

function _renderIsqSection(){
  const el=$('isqSection');if(!el)return;
  const isqItems=[
    {id:'qc_real_gdp',label:'Real GDP'},
    {id:'qc_nominal_gdp',label:'Nominal GDP'},
    {id:'qc_monthly_gdp',label:'Monthly GDP'},
    {id:'qc_household_consumption',label:'Household Spending'},
    {id:'qc_gov_consumption',label:'Gov Spending'},
    {id:'qc_business_investment',label:'Business Investment'},
    {id:'qc_exports',label:'Exports'},
    {id:'qc_imports',label:'Imports'},
    {id:'qc_intl_exports',label:'Int\'l Exports'},
    {id:'qc_intl_imports',label:'Int\'l Imports'},
    {id:'qc_compensation',label:'Employee Compensation'},
    {id:'qc_household_income',label:'Household Income'},
    {id:'qc_real_gdp_pct',label:'Real GDP Q/Q %'},
    {id:'qc_housing_starts',label:'Housing Starts'},
    {id:'qc_retail_sales',label:'Retail Sales'},
    {id:'qc_manufacturing_sales',label:'Manufacturing Sales'},
    {id:'qc_wholesale_sales',label:'Wholesale Sales'},
    {id:'qc_weekly_earnings',label:'Avg Weekly Earnings'},
    {id:'qc_employment',label:'Employment'},
    {id:'qc_unemployment_rate',label:'Unemployment Rate'},
    {id:'qc_participation_rate',label:'Participation Rate'},
    {id:'qc_cpi',label:'CPI Index'},
    {id:'qc_bldg_permits_res',label:'Building Permits (Res)'},
    {id:'qc_bldg_permits_nonres',label:'Building Permits (Non-Res)'}
  ];

  let html='<div class="exp-card">';
  html+='<div class="exp-card-title">Quebec Economic Accounts (ISQ)</div>';
  html+='<div class="exp-card-sub">Provincial accounts from <a href="https://statistique.quebec.ca/en/document/comptes-economiques-du-quebec-quaterly" target="_blank" rel="noopener noreferrer">Institut de la statistique du Qu\u00e9bec</a></div>';
  html+='<div class="exp-control-row">';
  html+='<select id="isqIndSel" class="exp-select" onchange="_isqSel=this.value;_loadIsqData()">';
  isqItems.forEach(it=>{html+='<option value="'+it.id+'"'+(it.id===_isqSel?' selected':'')+'>'+it.label+'</option>'});
  html+='</select>';
  html+='<div class="exp-range-group">';
  [12,36,60].forEach(m=>{
    const lbl=m===12?'1Y':m===36?'3Y':'5Y';
    const active=_isqRange===m?' active':'';
    html+='<button class="exp-range-btn'+active+'" onclick="_isqRange='+m+';_loadIsqData()">'+lbl+'</button>';
  });
  html+='</div></div>';
  html+='<div id="isqLatestTable"></div>';
  html+='<div id="isqCallout"></div>';
  html+='<div class="exp-chart-wrap"><canvas id="isqCanvas"></canvas></div>';
  html+='</div>';
  el.innerHTML=html;
  _renderIsqLatestTable(isqItems);
  _loadIsqData();
}

function _renderIsqLatestTable(isqItems){
  const tbl=$('isqLatestTable');if(!tbl)return;
  const rows=isqItems.map(it=>{
    const ind=indicators.find(x=>(x.indicator_name||'')==it.id);
    const isPct=it.id.includes('_pct')||it.id.includes('unemployment')||it.id.includes('participation')||it.id.includes('cpi');
    return {label:it.label,value:ind?ind.value:'—',period:ind?(ind.refPer||ind.period||''):'',unit:isPct?'%':(it.id.includes('earnings')?'$':'$M')};
  }).filter(r=>r.value!=='—'&&r.value!=null);
  if(!rows.length){tbl.innerHTML='';return}
  let html='<div class="exp-stat-grid">';
  rows.forEach(r=>{
    html+='<div class="exp-stat-card">';
    html+='<div class="exp-stat-card-label">'+r.label+'</div>';
    html+='<div class="exp-stat-card-value">'+fmtNum(parseFloat(r.value)||0)+' <small>'+r.unit+'</small></div>';
    if(r.period)html+='<div class="exp-stat-card-period">'+r.period+'</div>';
    html+='</div>';
  });
  html+='</div>';
  tbl.innerHTML=html;
}

async function _loadIsqData(){
  if(!_isqData[_isqSel]){
    try{
      const all=await fetchJSON('indicators.json');
      const hist=all.history||[];
      const pts=hist.filter(r=>(r.indicator_name||'')==_isqSel)
        .map(r=>({date:r.period||r.date,value:parseFloat(r.value)||0}))
        .sort((a,b)=>(a.date||'').localeCompare(b.date||''));
      _isqData[_isqSel]=pts;
    }catch(e){_isqData[_isqSel]=[]}
  }
  const allPts=_isqData[_isqSel]||[];
  const cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-_isqRange);
  const pts=allPts.filter(p=>new Date(p.date)>=cutoff);
  const callout=$('isqCallout');
  if(callout){
    if(pts.length>=2){
      const latest=pts[pts.length-1];const prev=pts[pts.length-2];
      const diff=latest.value-prev.value;const arrow=diff>0?'\u25b2':diff<0?'\u25bc':'\u25cf';
      const cls=diff>0?'up':diff<0?'down':'flat';
      callout.innerHTML='<div class="exp-callout"><span class="exp-callout-value">'+fmtNum(latest.value)+'</span><span class="exp-callout-chg '+cls+'">'+arrow+' '+(diff>=0?'+':'')+fmtNum(diff)+' vs prev</span><span class="exp-callout-meta">'+latest.date+'</span></div>';
    }else{callout.innerHTML='<div class="exp-callout"><span class="exp-callout-empty">No history available.</span></div>'}
  }
  const canvas=$('isqCanvas');if(!canvas)return;
  if(charts._isq)charts._isq.destroy();
  if(!pts.length)return;
  charts._isq=new Chart(canvas,{type:'line',data:{labels:pts.map(p=>p.date),datasets:[{data:pts.map(p=>p.value),borderColor:'#2563EB',backgroundColor:'rgba(37,99,235,0.08)',borderWidth:2,pointRadius:pts.length>30?0:4,pointBackgroundColor:'#2563EB',fill:true,tension:0.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'DM Sans',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.05)',lineWidth:0.5},ticks:{font:{family:'DM Sans',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}});
}

/* Full (unsliced) search that bypasses the 25-result cap in searchVCodes so pagination
   can walk the complete match set. Returns results sorted by score desc. */
function _expSearchAll(query){
  if(!query||query.length<2)return[];
  const qRaw=query.toLowerCase().split(/\s+/).filter(w=>w.length>1);
  const q=_expandQuery(qRaw);
  const score=(v,boost)=>{
    const text=(v.title+' '+v.keywords+' '+v.category+' '+v.geo).toLowerCase();
    let s=0;
    q.forEach(w=>{
      if(text.includes(w))s+=1;
      if(v.title.toLowerCase().includes(w))s+=2;
      if(v.keywords&&v.keywords.includes(w))s+=1;
    });
    return s>0?s+boost:0;
  };
  const curatedResults=VCODE_INDEX.map(v=>({...v,score:score(v,5)})).filter(v=>v.score>0);
  const dirResults=_fullTableDir.map(v=>({...v,score:score(v,0)})).filter(v=>v.score>0);
  return curatedResults.concat(dirResults).sort((a,b)=>b.score-a.score);
}

/* Remembered query so pagination clicks can re-run the search against the current term */
let _expLastQuery='';

function _expEscapeHtml(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

window._doVcodeSearch=function(cat){
  const q=cat||($('vcodeSearch')?$('vcodeSearch').value:'');
  if(!q)return;
  if(cat&&$('vcodeSearch'))$('vcodeSearch').value=cat;
  _expLastQuery=q;
  _expRenderVcodeResults();
};

function _expRenderVcodeResults(){
  const resEl=$('explorerResults');
  const metaEl=$('expSearchMeta');
  if(!resEl)return;
  const q=_expLastQuery;
  if(!q){
    resEl.innerHTML='<div class="exp-empty">Enter a search term or click a category to find StatCan tables.</div>';
    if(metaEl)metaEl.textContent='';
    return;
  }
  const results=_expSearchAll(q);
  if(!results.length){
    resEl.innerHTML='<div class="exp-empty">No tables found for "'+_expEscapeHtml(q)+'". Try different keywords.</div>';
    if(metaEl)metaEl.textContent='0 results';
    return;
  }
  const totalPages=Math.max(1,Math.ceil(results.length/EXP_PAGE_SIZE));
  if(_expSearchPage<1)_expSearchPage=1;
  if(_expSearchPage>totalPages)_expSearchPage=totalPages;
  const startIdx=(_expSearchPage-1)*EXP_PAGE_SIZE;
  const pageRows=results.slice(startIdx,startIdx+EXP_PAGE_SIZE);
  let html='<div class="exp-vcode-table-wrap"><table class="exp-vcode-table"><thead><tr><th class="exp-col-vcode">V-Code</th><th class="exp-col-table">Table</th><th>Title</th><th class="exp-col-category">Category</th><th class="exp-col-link">Link</th></tr></thead><tbody>';
  pageRows.forEach(r=>{
    const tableUrl=r.table&&r.table.includes('BoC')?'https://www.bankofcanada.ca/rates/':('https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid='+String(r.table||'').replace(/-/g,''));
    const meta=_expEscapeHtml([r.freq,r.geo].filter(Boolean).join(' \u00b7 '));
    html+='<tr>';
    html+='<td><span class="exp-vcode-code">'+_expEscapeHtml(r.vcode||'\u2014')+'</span></td>';
    html+='<td><span class="exp-vcode-tbl">'+_expEscapeHtml(r.table||'')+'</span></td>';
    html+='<td><span class="exp-vcode-title">'+_expEscapeHtml(r.title||'')+'</span>'+(meta?'<span class="exp-vcode-meta">'+meta+'</span>':'')+'</td>';
    html+='<td><span class="exp-vcode-cat">'+_expEscapeHtml(r.category||'')+'</span></td>';
    html+='<td class="exp-col-link"><a href="'+tableUrl+'" target="_blank" rel="noopener noreferrer" title="View on StatCan">\u2197</a></td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  if(totalPages>1){
    html+='<div class="exp-pagination">';
    html+='<button onclick="window._expGoPage('+(_expSearchPage-1)+')"'+(_expSearchPage===1?' disabled':'')+'>\u2039 Prev</button>';
    html+='<span class="exp-page-info">Page '+_expSearchPage+' of '+totalPages+'</span>';
    html+='<button onclick="window._expGoPage('+(_expSearchPage+1)+')"'+(_expSearchPage===totalPages?' disabled':'')+'>Next \u203a</button>';
    html+='</div>';
  }
  resEl.innerHTML=html;
  if(metaEl){
    metaEl.textContent=totalPages>1
      ?results.length.toLocaleString('en-CA')+' results \u00b7 page '+_expSearchPage+' of '+totalPages
      :results.length.toLocaleString('en-CA')+' result'+(results.length===1?'':'s');
  }
}

window._expGoPage=function(n){
  _expSearchPage=n;
  _expRenderVcodeResults();
  const el=$('explorerResults');
  if(el&&el.scrollIntoView)el.scrollIntoView({behavior:'smooth',block:'start'});
};

/* ====== PROVINCE COMPARISON VIEW ====== */
function renderProvinceComparison(){
  return; // Province comparison moved to sidebar navigation layout
  const el=$('provComparisonView');if(!el||!D)return;
  const provs=D.provinces||[];if(!provs.length)return;
  const codes=['ON','QC','AB','BC','SK','MB','NS','NB','NL','PE','YT','NT','NU'];
  let hdr='<th style="padding:6px 8px;font-size:9px;font-weight:600;color:#64748B;text-align:left;position:sticky;left:0;background:#fff;z-index:1">Indicator</th>';
  codes.forEach(c=>hdr+='<th style="padding:6px 8px;font-size:9px;font-weight:600;color:#64748B;text-align:right">'+c+'</th>');
  const _findProv=(code)=>provs.find(p=>(NAME_TO_CODE[p.name]||'')===code)||{};
  const _val=(p,key)=>{const inds=p.indicators||{};const v=inds[key];return(v&&v!=='N/A')?v:'--';};
  const rows=[
    {label:'Unemployment',key:'unemployment'},
    {label:'CPI',key:'cpi'},
    {label:'GDP',key:'gdp'},
    {label:'Projects',fn:p=>(p.projects||[]).length||'--'},
  ];
  let body='';
  rows.forEach((r,ri)=>{
    const bg=ri%2===0?'':'background:#f9fafb';
    body+='<tr style="'+bg+'">';
    body+='<td style="padding:6px 8px;font-size:11px;font-weight:600;color:#1a2744;white-space:nowrap;position:sticky;left:0;background:'+(bg||'#fff')+';z-index:1">'+r.label+'</td>';
    codes.forEach(c=>{
      const p=_findProv(c);
      const v=r.fn?r.fn(p):_val(p,r.key);
      body+='<td style="padding:6px 8px;font-size:11px;font-family:var(--font-mono);text-align:right;color:#475569">'+v+'</td>';
    });
    body+='</tr>';
  });
  el.innerHTML='<details class="card" style="margin-bottom:0"><summary style="cursor:pointer;padding:12px 16px;font-size:var(--text-sm);font-weight:600;color:#475569;user-select:none">Province Comparison</summary><div style="overflow-x:auto;padding:0 16px 12px"><table style="width:100%;border-collapse:collapse;min-width:700px"><thead><tr style="border-bottom:2px solid #e2e8f0">'+hdr+'</tr></thead><tbody>'+body+'</tbody></table></div></details>';
}

/* ====== DATA VINTAGE BADGES ====== */
function addDataVintage(){
  if(!D)return;
  const gen=D.generated_at||D.updated_at||'';
  if(!gen)return;
  const d=gen.split('T')[0];
  const badge='<span style="display:inline-block;font-size:10px;color:#64748B;background:#f1f5f9;padding:2px 8px;border-radius:4px;margin-left:8px">Data as of '+d+'</span>';
  // Add to national tab
  const natEl=$('natAnalysisSection');
  if(natEl){const existing=natEl.querySelector('.data-vintage');if(!existing){const dv=document.createElement('div');dv.className='data-vintage';dv.style.cssText='text-align:right;padding:4px 0;font-size:10px;color:#94A3B8';dv.innerHTML='Generated: '+gen.replace('T',' ').replace('Z',' UTC');natEl.prepend(dv)}}
}

/* ====== INITIALIZATION ====== */
// Module scripts are deferred — DOM is already ready, run immediately
if($('tldrPage'))$('tldrPage').innerHTML=skeleton(6);
if($('natAnalysisSection'))$('natAnalysisSection').innerHTML='<div class="card">'+skeleton(3)+'</div>';
// Section-level skeleton placeholders while async sections load
if($('costMonitor'))$('costMonitor').innerHTML='<div class="card">'+skeleton(2)+'</div>';
if($('microscopeHistory'))$('microscopeHistory').innerHTML='<div class="card">'+skeleton(2)+'</div>';
$('footerDate').textContent='Loading...';
// No auth required — data is served as static JSON files
loadAll();
