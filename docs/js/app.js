/* ── Static JSON data layer ── */
const DATA_BASE='data/';
const _cache={};
async function fetchJSON(path){
  if(_cache[path])return _cache[path];
  // Daily cache-buster so a long-lived tab picks up daily data refreshes
  // without defeating CDN caching entirely (date-granular, local time).
  const _bd=new Date();
  const _bust=''+_bd.getFullYear()+String(_bd.getMonth()+1).padStart(2,'0')+String(_bd.getDate()).padStart(2,'0');
  const resp=await fetch(DATA_BASE+path+(path.includes('?')?'&':'?')+'t='+_bust);
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
// Local-calendar YYYY-MM-DD (toISOString() serializes in UTC and shifts the day for UTC+ viewers)
function _localYMD(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
function fmtPeriod(dateStr){if(!dateStr)return '';try{const d=new Date(dateStr+'T00:00:00');if(isNaN(d))return dateStr;return d.toLocaleDateString('en-CA',{month:'short',year:'numeric'})}catch(e){return dateStr}}
function indBasis(rec,metaPeriod,freq){const p=pick(metaPeriod,rec&&rec.period);const dt=hasVal(p)?fmtPeriod(p):'';const f=freq||rec&&rec.frequency||'';const fLabel=f?f.charAt(0).toUpperCase()+f.slice(1):'';return dt||(fLabel||'')}
function indSource(rec,fallback){return (rec&&rec.source)||fallback||''}
function fmtNum(v){if(v==null)return'\u2014';if(v==='N/A'||v==='\u2014'||v==='')return v;const s=String(v).replace(/,/g,'');const m=s.match(/^([+\-]?)(\$?)(\d[\d]*\.?\d*)(.*)/);if(!m)return String(v);const sign=m[1],prefix=m[2],num=parseFloat(m[3]),suffix=m[4];if(isNaN(num))return String(v);const rounded=num%1===0&&num>=1000?num.toFixed(0):num.toFixed(1);const parts=rounded.split('.');parts[0]=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',');if(parts[1]==='0'&&num>=1000)return sign+prefix+parts[0]+suffix;return sign+prefix+parts.join('.')+suffix}
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
  // Filter out briefing-snapshot artifact periods (real StatCan observations use YYYY-MM-01)
  const clean=match.filter(x=>{
    const p=x.period||'';
    // Keep only real monthly observations (day=01) or quarterly/annual entries
    return /^\d{4}-\d{2}-01$/.test(p)||/^\d{4}-\d{2}$/.test(p)||/^\d{4}$/.test(p);
  });
  const useMatch=clean.length>=2?clean:match;
  useMatch.sort((a,b)=>(a.period||'').localeCompare(b.period||''));
  // Dedupe by month (YYYY-MM) so multiple reads from same month don't confuse sequencing
  const byMonth={};
  for(const rec of useMatch){
    const p=(rec.period||'').substring(0,7);if(!p)continue;
    const n=_parseNum(rec.value);if(isNaN(n))continue;
    byMonth[p]=n;
  }
  const months=Object.keys(byMonth).sort();
  if(months.length<2)return '';
  // Use the two most recent consecutive months
  const curr=byMonth[months[months.length-1]];
  const prev=byMonth[months[months.length-2]];
  // Magnitude guard: reject mixed-unit comparisons
  if(Math.abs(curr)>0&&Math.abs(prev)>0){
    const ratio=Math.abs(curr)/Math.abs(prev);
    if(ratio>10||ratio<0.1)return '';
  }
  const diff=curr-prev;
  // Determine display format from the value itself:
  // Rates and percentages (<100 absolute) → show as pp change
  // Large values (GDP levels, index levels) → show as % change
  const isRate=Math.abs(curr)<100&&Math.abs(prev)<100;
  if(isRate){return (diff>=0?'+':'')+diff.toFixed(1)+'pp'}
  const pct=prev!==0?((diff/Math.abs(prev))*100):0;
  return (pct>=0?'+':'')+pct.toFixed(1)+'%';
}
// StatCan Daily release lookup (indicators.json statcan_latest) — shared by
// the Canada Key Indicators table and the national enrichment cards. The
// Daily feed carries series the WDS pipeline doesn't fetch (CPI components,
// building permits, construction investment, merchandise trade).
function _scDailyRec(re,list){
  list=list||(_indJsonCache&&_indJsonCache.statcan_latest&&_indJsonCache.statcan_latest.indicators)||[];
  for(var i=0;i<list.length;i++){
    var r=list[i];if(!re.test(r.name||''))continue;
    var val=hasVal(r.value)?String(r.value).trim():'';
    var chg=hasVal(r.change)?String(r.change).trim():'';
    if(!val&&!chg)continue;
    var det=String(r.changeDetail||'');
    var basis=/12-month|year-over-year/i.test(det)?' y/y':(/monthly/i.test(det)?' m/m':'');
    // Up-arrow releases publish unsigned changes — sign them so the
    // change column colours correctly
    if(chg&&!/^[+\-−]/.test(chg)&&/^\d/.test(chg)&&String(r.arrow)==='1')chg='+'+chg;
    // CPI-component releases publish only the change — promote it to the
    // value cell with its basis so the cell is never blank
    if(!val){val=(/^[+\-−]/.test(chg)?chg:'+'+chg)+basis;chg=''}
    else if(chg)chg=chg+basis;
    return {value:val,change:chg,period:r.refPer||'',source:'Statistics Canada'};
  }
  return null;
}

/* ── State ── */
let D=null,indicators=[],allProjects=[],filteredProjects=[],projectPage=0,selectedProvince='ON',tsCache={},charts={},tabRendered={};
const PAGE_SIZE=25;
let _confirmedOnly=true;
const _MONTHS_SHORT={jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11};
// Year-less watchlist dates ("June 9") anchor to the briefing week_of's year, not the viewer's clock
function _evtAnchorYear(){const w=(typeof D!=='undefined'&&D&&D.week_of)||'';const y=parseInt(String(w).slice(0,4),10);return(y>2000&&y<2100)?y:new Date().getFullYear()}
function parseEvtDate(d){if(!d)return null;if(d.includes('-')&&d.length>=8)return new Date(d+'T00:00:00');const parts=d.trim().split(/\s+/);const yr=_evtAnchorYear();if(parts.length>=2){const m=_MONTHS_SHORT[(parts[0]||'').toLowerCase().slice(0,3)];if(m!=null)return new Date(yr,m,parseInt(parts[1])||1)}return null;}
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
/* meetsProvThreshold — alias for existing meetsThreshold (line 101) */
var meetsProvThreshold=meetsThreshold;
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
    // Sync currentEdition with the actual loaded briefing so the dropdown highlights correctly
    if(D&&D.week_of)currentEdition=D.week_of;
  }
  catch(e){console.error('Newsletter load:',e)}
}
async function loadEditionList(){
  try{
    const archive=await fetchJSON('briefing_archive.json');
    const editions=(archive||[]).map(e=>({id:e.week_of||'',file:e.file_date||e.week_of||'',edition:e.headline||'',date:e.generated_at||e.week_of||''}));
    const list=$('editionList');
    list.innerHTML=editions.map(e=>{
      const label=(e.edition||'').replace(/EDITION:\s*/i,'').split('//')[0].trim()||e.id;
      const active=e.id===currentEdition?'font-weight:700;background:#e2e8f0;':'';
      return'<div class="edition-item" data-id="'+e.id+'" data-file="'+e.file+'" style="padding:8px 14px;font-size:var(--text-xs);cursor:pointer;border-bottom:1px solid rgba(0,0,0,0.06);color:#1a2744;'+active+'">'+label+'</div>';
    }).join('');
    list.querySelectorAll('.edition-item').forEach(el=>el.addEventListener('click',()=>switchEdition(el.dataset.id,el.dataset.file)));
  }catch(e){console.warn('Edition list load:',e)}
}
async function switchEdition(editionId,fileId){
  currentEdition=editionId;
  $('editionList').style.display='none';
  $('navMeta').textContent='Loading...';
  tabRendered={};
  Object.values(charts).forEach(c=>{if(c&&c.destroy)c.destroy()});charts={};
  // Fetch by the actual dated filename (fileId); editionId (week_of) is kept
  // only for the dropdown's active-highlight. Falls back to editionId for
  // legacy archive entries that predate the file_date field.
  await loadNewsletter(fileId||editionId);
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
        <div id="tldrIndicatorsView">${weeklyDataHtml}${kiHtml}</div>
        <div id="tldrMarketsView" style="display:none">${mkHtml}</div>
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
/* Source name to URL mapping */
const _srcUrls={
  'Bank of Canada':'https://www.bankofcanada.ca/rates/',
  'Statistics Canada':'https://www150.statcan.gc.ca/n1/en/type/data',
  'CMHC':'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research',
  'Conference Board':'https://www.conferenceboard.ca/',
  'yfinance':'https://finance.yahoo.com/',
  'StatCan':'https://www150.statcan.gc.ca/n1/en/type/data',
  'BEA':'https://www.bea.gov/data/gdp/gross-domestic-product',
  'BLS':'https://www.bls.gov/data/',
  'Federal Reserve':'https://www.federalreserve.gov/monetarypolicy.htm',
  'Census Bureau':'https://www.census.gov/economic-indicators/',
  'NBS':'https://www.stats.gov.cn/english/',
  'PBOC':'http://www.pbc.gov.cn/en/',
  'GAC':'http://english.customs.gov.cn/',
  'Eurostat':'https://ec.europa.eu/eurostat/web/main/data/database',
  'ECB':'https://www.ecb.europa.eu/stats/',
  'ONS':'https://www.ons.gov.uk/economy',
  'BoE':'https://www.bankofengland.co.uk/monetary-policy',
  'LSE':'https://www.lse.ac.uk/'
};
function _srcLink(name){
  if(!name)return'';
  // Direct match
  const url=_srcUrls[name];
  if(url)return'<a href="'+url+'" target="_blank" rel="noopener" class="ind-src-link">'+san(name)+'</a>';
  // StatCan table pattern: "StatCan XX-XX-XXXX" or "CMHC/StatCan XX-XX-XXXX"
  const scMatch=String(name).match(/(?:StatCan|Statistics Canada|CMHC\/StatCan)\s+(\d{2})-(\d{2})-(\d{4})/);
  if(scMatch){
    const pid=scMatch[1]+scMatch[2]+scMatch[3]+'01';
    return'<a href="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid='+pid+'" target="_blank" rel="noopener" class="ind-src-link">'+san(name)+'</a>';
  }
  // Partial match for known prefixes
  if(name.startsWith('StatCan'))return'<a href="https://www150.statcan.gc.ca/n1/en/type/data" target="_blank" rel="noopener" class="ind-src-link">'+san(name)+'</a>';
  if(name.startsWith('CMHC'))return'<a href="https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research" target="_blank" rel="noopener" class="ind-src-link">'+san(name)+'</a>';
  return san(name);
}
function _tldrBuildIndicatorTable(){
  const ki=D.key_indicators||[];
  const meta=D.indicatorMeta||{};
  const labelMap={'BOC RATE':'bocRate','REAL GDP':'realGdp','CPI':'cpi','UNEMPLOYMENT':'unemployment',
    'HOUSING STARTS':'housingStarts','TRADE BALANCE':'tradeBalance','MERCHANDISE TRADE':'tradeBalance','RETAIL SALES':'retailSales',
    'CONSUMER CONFIDENCE':'consumerConfidence','PARTICIPATION':'participation','EMPLOYMENT CHANGE':'employmentChange',
    'WAGE GROWTH':'wageGrowth','PARTICIPATION RATE':'participation','EMPLOYMENT':'employmentChange',
    'WTI CRUDE':'wtiCrude','BRENT CRUDE':'brentCrude','CAD/USD':'cadUsd','USD/CAD':'cadUsd','TSX':'tsx',
    'GOC 10Y YIELD':'goc10y'};
  const freqMap={'bocRate':'8x/year','realGdp':'Monthly','cpi':'Monthly','unemployment':'Monthly',
    'housingStarts':'Monthly','tradeBalance':'Monthly','retailSales':'Monthly','consumerConfidence':'Monthly',
    'participation':'Monthly','employmentChange':'Monthly','wageGrowth':'Monthly',
    'wtiCrude':'Daily','brentCrude':'Daily','cadUsd':'Daily','tsx':'Daily','goc10y':'Daily'};
  const srcFallback={'bocRate':'Bank of Canada','realGdp':'Statistics Canada','cpi':'Statistics Canada',
    'unemployment':'Statistics Canada','housingStarts':'CMHC','tradeBalance':'Statistics Canada',
    'retailSales':'Statistics Canada','consumerConfidence':'Conference Board','participation':'Statistics Canada',
    'employmentChange':'Statistics Canada','wageGrowth':'Statistics Canada',
    'wtiCrude':'yfinance','brentCrude':'yfinance','cadUsd':'yfinance','tsx':'yfinance','goc10y':'Bank of Canada'};
  // Tolerant label resolution — exact uppercase match first, then longest startsWith/contains
  // (labels arrive as 'CPI YoY', 'HOUSING STARTS SAAR', 'TSX COMPOSITE', 'GoC 10Y YIELD', etc.)
  function _kiLabelKey(label){
    const up=String(label||'').toUpperCase().replace(/\s+/g,' ').trim();
    if(!up)return'';
    if(labelMap[up])return labelMap[up];
    let best='',bestLen=0;
    for(const k in labelMap){
      if(k.length>bestLen&&(up.startsWith(k)||up.indexOf(k)!==-1)){best=labelMap[k];bestLen=k.length}
    }
    return best;
  }
  if(!ki.length)return'<div class="tldr-empty">Indicator data pending.</div>';
  let rows='';
  ki.forEach(ind=>{
    const key=_kiLabelKey(ind.label);
    const m=meta[key]||{};
    const freq=freqMap[key]||'';
    const chgShort=ind.change||m.change||'';
    const chgContext=ind.changeContext||'';
    let cls='unch';
    if(/^\+|▲|\bup\b|\bgain\b|\brose\b|\bincreas/i.test(chgShort))cls='up';
    else if(/^-|▼|\bdown\b|\bfell\b|\bdeclin|\bdrop/i.test(chgShort))cls='down';
    else if(/held|unchanged|flat|0bp/i.test(chgShort))cls='unch';
    const arrow=cls==='up'?'\u25B2 ':cls==='down'?'\u25BC ':cls==='unch'?'\u2014 ':'';
    const src=m.source||(D.indicatorSources&&D.indicatorSources[key])||srcFallback[key]||'';
    const period=ind.period||m.period||'';
    const ctxParts=[];
    if(chgContext)ctxParts.push(chgContext);
    if(period)ctxParts.push(period);
    const ctxText=ctxParts.join(' \u00B7 ');
    const ctxHtml=ctxText?' <span class="ind-t-name-ctx">'+san(ctxText)+'</span>':'';
    rows+=`<tr>
      <td class="ind-t-name">${san(ind.label||'')}${ctxHtml}</td>
      <td class="ind-t-unit">${san(freq)}</td>
      <td class="ind-t-val">${san(ind.value||'')}</td>
      <td class="ind-t-chg ${cls}">${chgShort?arrow+san(chgShort):''}</td>
      <td class="ind-t-src">${_srcLink(src)}</td>
    </tr>`;
  });
  return`<div class="tldr-mkt-group-label">Key Economic Indicators</div>
  <table class="tldr-ind-table"><thead><tr>
    <th>Indicator</th><th>Frequency</th><th>Value</th><th>Change</th><th>Source</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

/* ── TL;DR: Markets table ── */
/* Parse "US$102.88/bbl" → {num:"102.88", unit:"USD/bbl"} */
function _parseMarketVal(raw){
  if(!raw)return{num:'',unit:''};
  let s=String(raw).replace(/~/g,'').trim();
  // Handle cents first: "607.5¢/bu"
  if(s.includes('\u00A2')||s.includes('¢')){
    const cm=s.match(/^([\d,.]+)[¢\u00A2]\/?(.*)$/);
    if(cm)return{num:cm[1],unit:'USc/'+cm[2]};
  }
  // Detect currency prefix
  let cur='';
  if(s.startsWith('US$')){cur='USD';s=s.slice(3)}
  else if(s.startsWith('C$')){cur='CAD';s=s.slice(2)}
  else if(s.startsWith('$')){cur='USD';s=s.slice(1)}
  // Split number from unit suffix (e.g. "/bbl", "/oz", "/lb", "/MT", "/MBF", "/MMBtu")
  const m=s.match(/^([\d,.]+)\s*\/?(.*)$/);
  if(!m)return{num:s,unit:cur};
  const num=m[1];
  let unit=m[2]||'';
  if(cur&&unit)unit=cur+'/'+unit;
  else if(cur)unit=cur;
  return{num,unit};
}
/* Extract just ±X.X% from messy change strings */
function _normalizeChg(raw){
  if(!raw)return'';
  const s=String(raw);
  // Extract percentage pattern: optional sign, digits, optional decimal, %
  const m=s.match(/([+-]?\d+\.?\d*)%/);
  if(!m)return'';
  let pct=m[1];
  // Ensure sign prefix
  if(!pct.startsWith('+')&&!pct.startsWith('-'))pct='+'+pct;
  return pct+'%';
}
function _tldrBuildMarketsTable(){
  const comms=D.commodities||[];
  const fm=D.financialMarkets||D.financial_markets||{};

  function buildRows(items){
    let rows='';
    items.forEach(it=>{
      const parsed=_parseMarketVal(it.value);
      const unit=it.forceUnit||parsed.unit;
      const chg=_normalizeChg(it.change);
      let cls='unch';
      if(chg.startsWith('+'))cls='up';
      else if(chg.startsWith('-'))cls='down';
      const arrow=cls==='up'?'\u25B2 ':cls==='down'?'\u25BC ':'';
      rows+=`<tr>
        <td class="ind-t-name">${san(it.name)}</td>
        <td class="ind-t-unit">${san(unit)}</td>
        <td class="ind-t-val">${san(parsed.num)}</td>
        <td class="ind-t-chg ${cls}">${chg?arrow+san(chg):''}</td>
        <td class="ind-t-src">${_srcLink(it.source||'')}</td>
      </tr>`;
    });
    return rows;
  }
  const thead=`<thead><tr><th>Indicator</th><th>Unit</th><th>Value</th><th>Change (W/W)</th><th>Source</th></tr></thead>`;

  // Commodities section
  let commItems=[];
  comms.forEach(c=>{
    // 'day' carries the W/W figure in this export; pick() skips ''/'N/A' placeholders
    commItems.push({name:c.name||c.symbol||'',value:c.val||c.price||c.value||'',change:pick(c.day,c.wow,c.change,c.mm),source:c.source||'yfinance'});
  });

  // Currencies section
  const fxUnits={'CAD/USD':'rate','USD/CAD':'rate','EUR/USD':'rate','GBP/USD':'rate','USD/JPY':'rate'};
  let fxItems=[];
  if(fm.fx&&fm.fx.length){fm.fx.forEach(f=>{fxItems.push({name:f.name||'',value:f.value||f.val||'',change:pick(f.day,f.wow,f.change,f.mm),source:'yfinance',forceUnit:fxUnits[f.name]||'rate'})})}

  // Indices section
  let idxItems=[];
  if(fm.indices&&fm.indices.length){fm.indices.forEach(idx=>{idxItems.push({name:idx.name||'',value:idx.value||idx.val||'',change:pick(idx.day,idx.wow,idx.change,idx.mm),source:'yfinance',forceUnit:'pts'})})}

  if(!commItems.length&&!fxItems.length&&!idxItems.length)return'<div class="tldr-empty">Markets data pending.</div>';

  let html='';
  if(commItems.length){
    html+=`<div class="tldr-mkt-group-label">Commodities</div>
    <table class="tldr-ind-table">${thead}<tbody>${buildRows(commItems)}</tbody></table>`;
  }
  if(fxItems.length){
    html+=`<div class="tldr-mkt-group-label">Currencies</div>
    <table class="tldr-ind-table">${thead}<tbody>${buildRows(fxItems)}</tbody></table>`;
  }
  if(idxItems.length){
    html+=`<div class="tldr-mkt-group-label">Indices</div>
    <table class="tldr-ind-table">${thead}<tbody>${buildRows(idxItems)}</tbody></table>`;
  }
  return html;
}

/* ── TL;DR: "This Week's Key Data" table (second section in Numbers at a Glance) ── */
function _tldrBuildWeeklyDataTable(){
  const comms=D.commodities||[];
  const stats=D.discovery_stats||{};
  let rows='';
  // Add top commodities (data uses 'val' and 'mm' fields)
  comms.slice(0,4).forEach(function(c){
    const val=c.val||c.price||c.value||'';
    if(!val)return; // skip rows without values
    const parsed=_parseMarketVal(val);
    const chg=_normalizeChg(pick(c.day,c.wow,c.change,c.mm));
    let cls='unch';
    if(chg.startsWith('+'))cls='up';
    else if(chg.startsWith('-'))cls='down';
    const arrow=cls==='up'?'\u25B2 ':cls==='down'?'\u25BC ':'';
    rows+=`<tr>
      <td class="ind-t-name">${san(c.name||'')}</td>
      <td class="ind-t-unit">${san(parsed.unit)}</td>
      <td class="ind-t-val">${san(parsed.num)}</td>
      <td class="ind-t-chg ${cls}">${chg?arrow+san(chg):''}</td>
      <td class="ind-t-src">${_srcLink(c.source||'yfinance')}</td>
    </tr>`;
  });
  if(!rows)return'';
  return`<div class="tldr-map-section">
    <div class="tldr-toggle-row"><span class="tldr-glance-label">This Week\u2019s Key Data</span></div>
    <table class="tldr-ind-table"><thead><tr>
      <th>Indicator</th><th>Unit</th><th>Value</th><th>Change (W/W)</th><th>Source</th>
    </tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

/* ── Editorial prose (Demo style): bold first-sentence lead-in + em dash, and
   strip the writer's scattered inline <strong> so only the lead-in is bold.
   Tag-aware so it works on live prose that has inline <a> citations / <strong>
   figures in the first sentence (the old [^<] regex bailed on those, leaving most
   paragraphs un-styled with random inline bold). ── */
function _editorialProse(html){
  if(!html) return html;
  return html.replace(/<p>([\s\S]*?)<\/p>/g,function(m,inner){
    var s=inner.trim().replace(/<\/?strong>/gi,'');                  // drop scattered inline bold
    if(/^<span class="(?:tldr-)?lead-sentence"/.test(s)) return '<p>'+s+'</p>'; // data already styled
    // Find the first sentence-ending . ! ? that is not inside a tag and not a
    // decimal. A boundary is a period followed by whitespace, a tag (citation),
    // or end-of-paragraph.
    var depth=0,idx=-1;
    for(var i=0;i<s.length;i++){
      var c=s[i];
      if(c==='<'){depth++;continue;}
      if(c==='>'){if(depth>0)depth--;continue;}
      if(depth>0)continue;
      if(c==='.'||c==='!'||c==='?'){
        var prev=s[i-1]||'',next=s[i+1]||'';
        if(c==='.'&&/[0-9]/.test(prev)&&/[0-9]/.test(next))continue; // decimal e.g. 2.25
        if(next&&!/\s/.test(next)&&next!=='<')continue;              // end = whitespace, tag, or EOL
        idx=i;break;
      }
    }
    if(idx<0) return '<p>'+s+'</p>';
    var lead=s.slice(0,idx).trim();
    if(lead.replace(/<[^>]*>/g,'').trim().length<12) return '<p>'+s+'</p>';
    // Keep citation tags that immediately follow the sentence attached to the lead.
    var after=s.slice(idx+1);
    var mc=after.match(/^\s*(?:<a\b[^>]*>[\s\S]*?<\/a>\s*)+/);
    var cites=mc?mc[0].trim():'';
    var rest=after.slice(mc?mc[0].length:0).replace(/^\s+/,'');
    var out='<span class="lead-sentence">'+lead+'</span>'+(cites?cites:'')+(rest?' — '+rest:'');
    return '<p>'+out+'</p>';
  });
}

/* ── TL;DR: Weekly Briefing narrative ── */
function _tldrBuildBriefing(){
  const raw=D.executive_summary||'';
  const sources=D.sources||[];
  let html=bulletsToParas(san(linkFootnotes(raw,sources)));

  // Merge a standalone bold header paragraph into the following paragraph as a
  // lead-in (Demo style: bold lead-off + em dash + body).
  html=html.replace(/<p>\s*<strong>([^<]{3,60})<\/strong>\s*<\/p>\s*<p>/gi,function(m,heading){
    return '<p><span class="lead-sentence">'+heading.replace(/&amp;/g,'&')+'</span> \u2014 ';
  });
  // Apply the editorial lead-in treatment to every remaining paragraph and strip
  // the writer's scattered inline <strong> so only the lead-in is bold (matches Demo).
  html=_editorialProse(html);

  // Build callout boxes with inline charts from D.insightCharts
  const ic=D.insightCharts||D.insight_charts||[];
  const stats=D.discovery_stats||{};
  var callouts=[];

  // First callout: pipeline cross-reference + first insight chart
  var c1Text=(stats.total_projects)?'<strong>Cross-reference:</strong> The database tracks '+(stats.total_projects||0).toLocaleString()+' active projects valued at '+(D.pipeline_value||'$'+((stats.total_value_billions||0).toFixed(1))+'B')+' across Canada.'+(stats.new_this_week?' '+stats.new_this_week+' new projects discovered this week.':''):'';
  if(ic.length>=1){
    var ch=ic[0];
    // The export carries the validator-enforced text in callout (reasoning is null)
    var c1Spec=ch.callout||ch.reasoning;
    c1Text=(c1Spec?san(c1Spec):c1Text);
    callouts.push({text:c1Text,chart:ch});
  }else if(c1Text){
    callouts.push({text:c1Text,chart:null});
  }

  // Second callout: second insight chart
  if(ic.length>=2){
    var ch2=ic[1];
    var c2Spec=ch2.callout||ch2.reasoning;
    callouts.push({text:c2Spec?san(c2Spec):'',chart:ch2});
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

/* Build a callout box with optional inline SVG chart (header lives inside the SVG) */
function _tldrCalloutHtml(co,idx){
  var h='<div class="tldr-callout">';
  if(co.text)h+=co.text;
  if(co.chart){
    h+='<div class="tldr-callout-chart" id="tldrCalloutChart_'+idx+'">';
    h+='<div class="tldr-callout-svg" id="tldrCalloutSvg_'+idx+'"><div style="height:280px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">Loading chart\u2026</div></div>';
    h+='</div>';
  }
  h+='</div>';
  return h;
}

/* Render callout SVG charts async after page paint */
async function _tldrRenderCalloutCharts(){
  var ic=D.insightCharts||D.insight_charts||[];
  // indicators-sourced specs read indicators.json history \u2014 make sure it is loaded first
  if(ic.some(function(c){return c&&c.dataSource==='indicators'})){
    try{await fetchJSON('indicators.json');if(_indHistory&&!_indHistory.length)_indHistory=null}catch(e){}
  }
  for(var idx=0;idx<ic.length&&idx<2;idx++){
    var ch=ic[idx];var keys=ch.dataKeys||[];
    var el=document.getElementById('tldrCalloutSvg_'+idx);
    if(!el||!keys.length)continue;
    // Resolve series honoring the spec's dataSource (indicators.json history vs timeseries.json)
    var allSeries=[];
    try{allSeries=await _loadChartSpecSeries(ch)}catch(e){allSeries=[]}
    // Filter to last 5 months (tighter window for the editorial chart)
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-5);
    allSeries.forEach(function(s){s.data=s.data.filter(function(p){return new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)})});
    allSeries=allSeries.filter(function(s){return s.data.length>=2});
    if(!allSeries.length){el.innerHTML='<div style="height:280px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">No timeseries data</div>';continue;}
    // Title and subtitle must reflect the actual 5-month window
    var chartTitle=(ch.title||'').replace(/\b\d+([-\s]?[Mm]onth)\b/,'5$1');
    var chartSubtitle=(ch.subtitle||'').replace(/\b\d+[-\s]?month\b/i,'5-month');
    // Pick a sensible source line for the top-level hero. If keys look like crude/brent keep the existing EIA+ICE attribution.
    var src=ch.source;
    if(!src){
      if(ch.dataSource==='indicators')src='Source: Statistics Canada';
      else{
        var ks=keys.map(function(k){return String(k).toLowerCase()}).join(',');
        if(/\bwti\b|\bbrent\b|\bwcs\b/.test(ks))src='Source: EIA, ICE \u00b7 daily spot close';
        else if(/\bgold\b|\bsilver\b|\bcopper\b|\bnickel\b|\bzinc\b|\blithium\b/.test(ks))src='Source: LBMA, LME';
        else if(/\bnatural_gas\b|\bpropane\b|\blng\b/.test(ks))src='Source: EIA, NYMEX';
        else if(/\bwheat\b|\bcanola\b|\bsoybean\b|\bcorn\b|\bpotash\b/.test(ks))src='Source: CBOT, ICE Futures';
        else src='Source: The Lagging Indicator';
      }
    }
    el.innerHTML=_svgCalloutChart(allSeries,ch.annotations||[],chartTitle,chartSubtitle,ch.chartType||'line',src);
  }
}

function _svgCalloutChart(seriesArr,annotations,title,subtitle,chartType,source,opts){
  // Economist-style chart with Prussian blue theme.
  // Types: 'line' (area under curve), 'multi_line' (rebased to 100), 'bar', 'diverging_bar' (auto MoM for level series).
  if(!seriesArr||!seriesArr.length)return '';
  chartType=chartType||'line';
  var isBar=(chartType==='bar'||chartType==='diverging_bar');
  var isMulti=(chartType==='multi_line');
  var isDiv=(chartType==='diverging_bar');

  var W=1100,H=360,PAD_X=0,PAD_TOP=14,PAD_BOT=32;
  var pL=PAD_X,pR=48,pT=96,pB=82;
  var pW=W-pL-pR,pH=H-pT-pB;
  var BRAND='#003153',INK='#0f172a',MUTED='#4a5568',FAINT='#94a3b8',EVENT='#E3120B',GRID='#d9d4c7',POS='#0d7a3f',NEG='#c4320a';
  var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
  function fmtVal(v){return _svgFmtVal(v).replace(/\.00$/,'')}
  function fmtDate(iso){var d=new Date(iso);return MONTHS[d.getUTCMonth()]+' '+d.getUTCDate()+' '+d.getUTCFullYear()}

  // Clone input (avoid mutating caller). Each prepared series keeps key/data/color.
  var prepared=seriesArr.map(function(s){return{key:s.key,data:s.data.slice(),color:s.color}});

  // diverging_bar: if a series looks like a level (same sign, tight range), convert to MoM deltas so the "change" story is visible.
  if(isDiv){
    prepared.forEach(function(s){
      var vals=s.data.map(function(p){return p.value}).filter(function(v){return v!=null});
      if(vals.length<3)return;
      var vmn=Math.min.apply(null,vals),vmx=Math.max.apply(null,vals);
      var sameSign=(vmn>=0)||(vmx<=0);
      var mag=Math.max(Math.abs(vmn),Math.abs(vmx));
      var rangeRatio=mag===0?0:(vmx-vmn)/mag;
      if(sameSign&&rangeRatio<0.6){
        var deltas=[];
        for(var i=1;i<s.data.length;i++){
          if(s.data[i].value==null||s.data[i-1].value==null)continue;
          deltas.push({date:s.data[i].date,value:s.data[i].value-s.data[i-1].value});
        }
        s.data=deltas;
      }
    });
  }

  // multi_line: rebase each series to 100 at first non-null point
  if(isMulti){
    prepared.forEach(function(s){
      var base=null;
      for(var i=0;i<s.data.length;i++){if(s.data[i].value!=null&&s.data[i].value!==0){base=s.data[i].value;break}}
      if(base==null||base===0)return;
      s.data=s.data.map(function(p){return{date:p.date,value:p.value==null?null:(p.value/base)*100}});
    });
  }

  // Align all series to shortest common length
  var n=Math.min.apply(null,prepared.map(function(s){return s.data.length}));
  if(!n||n<2)return '';
  var slices=prepared.map(function(s){return s.data.slice(-n)});
  var primary=slices[0];

  // y-range
  var allVals=[];
  slices.forEach(function(sl){sl.forEach(function(p){if(p.value!=null)allVals.push(p.value)})});
  if(!allVals.length)return '';
  var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals);
  if(isDiv){var absMx=Math.max(Math.abs(mn),Math.abs(mx))||1;mn=-absMx;mx=absMx}
  var rng=mx-mn;if(rng===0)rng=Math.abs(mn)*0.1||1;
  if(isBar){mx+=rng*0.14;rng=mx-mn;if(!isDiv){mn-=rng*0.04;rng=mx-mn}}
  else{
    // Add ~one gridline-step of headroom below the data minimum so the lines don't hug the floor.
    // Exception: if the data minimum is exactly 0, keep 0 as the natural floor (don't go negative).
    // If the data is all-positive and the expansion would cross 0, clamp to 0.
    var dataMin=mn;
    if(dataMin>0){mn=Math.max(0,dataMin-rng*0.25)}
    else if(dataMin<0){mn-=rng*0.25}
    mx+=rng*0.14;rng=mx-mn;
  }

  function xp(i,L){return pL+(i/Math.max(L-1,1))*pW}
  function yp(v){return pT+(1-(v-mn)/rng)*pH}
  var base_y=pT+pH;
  var zero_y=isDiv?yp(0):base_y;

  // Smooth path (Catmull-Rom → Cubic Bezier, tension 0.5)
  function smoothPath(pts){
    if(pts.length<2)return '';
    if(pts.length===2)return 'M'+pts[0][0].toFixed(1)+','+pts[0][1].toFixed(1)+' L'+pts[1][0].toFixed(1)+','+pts[1][1].toFixed(1);
    var d='M'+pts[0][0].toFixed(1)+','+pts[0][1].toFixed(1);
    for(var i=0;i<pts.length-1;i++){
      var p0=i>0?pts[i-1]:pts[i];
      var p1=pts[i],p2=pts[i+1];
      var p3=i+2<pts.length?pts[i+2]:pts[i+1];
      var cp1x=p1[0]+(p2[0]-p0[0])/6,cp1y=p1[1]+(p2[1]-p0[1])/6;
      var cp2x=p2[0]-(p3[0]-p1[0])/6,cp2y=p2[1]-(p3[1]-p1[1])/6;
      d+=' C'+cp1x.toFixed(1)+','+cp1y.toFixed(1)+' '+cp2x.toFixed(1)+','+cp2y.toFixed(1)+' '+p2[0].toFixed(1)+','+p2[1].toFixed(1);
    }
    return d;
  }
  function areaPath(pts,baselineY){
    if(pts.length<2)return '';
    return smoothPath(pts)+' L'+pts[pts.length-1][0].toFixed(1)+','+baselineY.toFixed(1)+' L'+pts[0][0].toFixed(1)+','+baselineY.toFixed(1)+' Z';
  }

  // Screen points per series (null values map to baseline y — bars skip them separately)
  var seriesPts=slices.map(function(slice){return slice.map(function(p,i){return[xp(i,slice.length),yp(p.value==null?mn:p.value)]})});

  // First annotation → flag above plot, dashed drop-line to data point (line/multi_line only)
  var event_x=null,event_y=null,evLabel='',evDate=null;
  if(!isBar&&annotations&&annotations.length&&annotations[0].date){
    var tEv=new Date(annotations[0].date).getTime();
    var bestI=0,bestD=Infinity;
    for(var ii=0;ii<primary.length;ii++){
      var dd=Math.abs(new Date(primary[ii].date).getTime()-tEv);
      if(dd<bestD){bestD=dd;bestI=ii}
    }
    event_x=xp(bestI,primary.length);
    event_y=seriesPts[0][bestI][1];
    evLabel=annotations[0].label||'';
    evDate=annotations[0].date;
  }

  // ---- SVG start ----
  var svg='<svg viewBox="0 0 '+W+' '+H+'" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;font-family:\'Inter\',-apple-system,sans-serif;overflow:visible" role="img" aria-label="'+esc(title||'Chart')+'">';

  // Defs — arrow marker + per-series area gradients (line mode only)
  svg+='<defs>';
  svg+='<marker id="le_arrow_event" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="'+EVENT+'"/></marker>';
  if(!isBar){
    var primaryColor=prepared[0].color||BRAND;
    svg+='<linearGradient id="area_primary" x1="0" y1="0" x2="0" y2="1">';
    svg+='<stop offset="0%" stop-color="'+primaryColor+'" stop-opacity="0.22"/>';
    svg+='<stop offset="100%" stop-color="'+primaryColor+'" stop-opacity="0"/>';
    svg+='</linearGradient>';
    if(prepared.length>=2){
      var secondaryColor=prepared[1].color||BRAND;
      svg+='<linearGradient id="area_secondary" x1="0" y1="0" x2="0" y2="1">';
      svg+='<stop offset="0%" stop-color="'+secondaryColor+'" stop-opacity="0.16"/>';
      svg+='<stop offset="100%" stop-color="'+secondaryColor+'" stop-opacity="0"/>';
      svg+='</linearGradient>';
    }
  }
  svg+='</defs>';

  // Signal49-style: red rule + optional uppercase kicker + Inter bold title + Inter italic deck
  svg+='<rect x="'+PAD_X+'" y="'+PAD_TOP+'" width="48" height="4" fill="#E3120B"/>';
  var _ck=(opts&&opts.kicker)||'';
  var _ttlY=PAD_TOP+34;
  if(_ck){
    svg+='<text x="'+PAD_X+'" y="'+(PAD_TOP+22)+'" font-size="10" font-weight="700" fill="'+INK+'" letter-spacing="1.4">'+esc(_ck.toUpperCase())+'</text>';
    _ttlY=PAD_TOP+46;
  }
  svg+='<text x="'+PAD_X+'" y="'+_ttlY+'" font-size="22" font-weight="700" fill="'+INK+'" letter-spacing="-0.3" font-family="Inter,sans-serif">'+esc(title||'')+'</text>';
  if(subtitle)svg+='<text x="'+PAD_X+'" y="'+(_ttlY+22)+'" font-size="13" font-weight="500" font-style="italic" fill="'+MUTED+'" font-family="Inter,sans-serif">'+esc(subtitle)+'</text>';

  // Horizontal gridlines + right-side y-axis labels
  for(var g=0;g<=4;g++){
    var gy=pT+(g/4)*pH;
    var gv=mx-(g/4)*rng;
    svg+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="'+GRID+'" stroke-width="1"/>';
    svg+='<text x="'+(W-pR+8)+'" y="'+(gy+4)+'" text-anchor="start" font-size="11" font-weight="400" fill="'+MUTED+'" style="font-variant-numeric:tabular-nums">'+fmtVal(gv)+'</text>';
  }

  // Bold chart floor
  svg+='<line x1="'+pL+'" y1="'+base_y+'" x2="'+(W-pR)+'" y2="'+base_y+'" stroke="'+INK+'" stroke-width="1.2"/>';

  // Zero line for diverging_bar (overlays gridlines)
  if(isDiv&&zero_y>pT&&zero_y<base_y){
    svg+='<line x1="'+pL+'" y1="'+zero_y.toFixed(1)+'" x2="'+(W-pR)+'" y2="'+zero_y.toFixed(1)+'" stroke="'+INK+'" stroke-width="1.4"/>';
  }

  // X-axis labels
  var NT=6;if(primary.length<NT)NT=Math.max(2,primary.length);
  for(var xi=0;xi<NT;xi++){
    var di=Math.round((xi/(NT-1))*(primary.length-1));
    var dx=xp(di,primary.length);
    var dObj=new Date(primary[di].date);
    var lbl=MONTHS[dObj.getUTCMonth()];
    if(xi===0||dObj.getUTCMonth()===0)lbl=MONTHS[dObj.getUTCMonth()]+'\u2009'+dObj.getUTCFullYear();
    var xAnc=xi===0?'start':(xi===NT-1?'end':'middle');
    svg+='<text x="'+dx+'" y="'+(base_y+22)+'" text-anchor="'+xAnc+'" font-size="11" font-weight="400" fill="'+MUTED+'">'+lbl+'</text>';
  }

  // Closure flag (line mode only) — flag text sits above plot, dashed line drops from flag to data point
  if(event_x!==null){
    var flagY=pT-8;
    var flagAnchor='middle',flagX=event_x;
    if(event_x<pL+pW*0.22){flagAnchor='start';flagX=event_x+4}
    else if(event_x>pL+pW*0.78){flagAnchor='end';flagX=event_x-4}
    svg+='<text x="'+flagX+'" y="'+flagY+'" text-anchor="'+flagAnchor+'" font-size="11" font-weight="600" fill="'+EVENT+'">'+esc(evLabel)+' \u00b7 '+fmtDate(evDate)+'</text>';
    svg+='<line x1="'+event_x+'" y1="'+(pT-3)+'" x2="'+event_x+'" y2="'+event_y.toFixed(1)+'" stroke="'+EVENT+'" stroke-width="1" stroke-dasharray="2,3" opacity="0.85"/>';
    svg+='<circle cx="'+event_x+'" cy="'+event_y.toFixed(1)+'" r="3" fill="'+EVENT+'"/>';
  }

  // ---- Data rendering ----
  if(isBar){
    // Single-series bar. Bar width = ~70% of x-step, min 2px.
    var sp=seriesPts[0],slice=slices[0];
    var barColor=prepared[0].color||BRAND;
    var barW=sp.length>1?Math.max(2,(sp[1][0]-sp[0][0])*0.7):20;
    for(var bi=0;bi<sp.length;bi++){
      var v=slice[bi].value;if(v==null)continue;
      var y0=isDiv?zero_y:base_y;
      var y1=sp[bi][1];
      var top=Math.min(y0,y1),h=Math.abs(y1-y0);
      var fill=isDiv?(v>=0?POS:NEG):barColor;
      svg+='<rect x="'+(sp[bi][0]-barW/2).toFixed(1)+'" y="'+top.toFixed(1)+'" width="'+barW.toFixed(1)+'" height="'+Math.max(h,0.5).toFixed(1)+'" fill="'+fill+'" rx="1"/>';
    }
  }else{
    // Filled area under each series — secondary first (back), primary on top
    if(seriesPts.length>=2){svg+='<path d="'+areaPath(seriesPts[1],base_y)+'" fill="url(#area_secondary)"/>'}
    svg+='<path d="'+areaPath(seriesPts[0],base_y)+'" fill="url(#area_primary)"/>';
    var drawOrder=seriesPts.length>1?[1,0]:[0];
    drawOrder.forEach(function(sIdx){
      var pts=seriesPts[sIdx];
      var color=prepared[sIdx].color||BRAND;
      var sw=sIdx===0?3:2.4;
      svg+='<path d="'+smoothPath(pts)+'" fill="none" stroke="'+color+'" stroke-width="'+sw+'" stroke-linejoin="round" stroke-linecap="round"/>';
    });
    seriesPts.forEach(function(pts,sIdx){
      var last=pts[pts.length-1];
      var color=prepared[sIdx].color||BRAND;
      var r=sIdx===0?4.5:4;
      svg+='<circle cx="'+last[0]+'" cy="'+last[1]+'" r="'+r+'" fill="'+color+'"/>';
    });
  }

  // Source line (italicized, Economist-style)
  var srcText=source||'Source: The Lagging Indicator';
  svg+='<text x="'+PAD_X+'" y="'+(H-PAD_BOT-2)+'" font-size="10" font-weight="500" font-style="italic" fill="'+MUTED+'">'+esc(srcText)+'</text>';

  svg+='</svg>';return svg;
}

// Resolves a chartSpec ({dataKeys, chartType, window, dataSource, ...}) into a pre-loaded seriesArr
// suitable for _svgCalloutChart. Handles both timeseries.json (loadTimeseries) and indicators.json history.
async function _loadChartSpecSeries(spec,prov){
  var keys=(spec&&spec.dataKeys)||[];
  var colors=['#003153','#7c3aed','#c4320a','#0d7a3f'];
  var dataSource=spec.dataSource||'timeseries';
  // Default window: 12m for timeseries data, 24m for indicator history.
  var defaultWindow=dataSource==='indicators'?24:12;
  var windowMonths=spec.window?_indWindowMonths(spec.window):defaultWindow;
  var out=[];

  if(dataSource==='indicators'){
    for(var ki=0;ki<keys.length;ki++){
      var pts=_indResolveIndicatorsSeries(keys[ki],windowMonths,prov);
      if(!pts||pts.length<2)continue;
      out.push({key:keys[ki],data:pts.map(function(p){return{date:p.label+'-01',value:p.value}}),color:colors[ki%colors.length]});
    }
    return out;
  }

  for(var kj=0;kj<keys.length;kj++){
    var key=keys[kj];
    var ts=null;
    try{ts=await loadTimeseries(key)}catch(e){}
    if(!ts){try{ts=await loadTimeseries('comm_'+key)}catch(e){}}
    var raw=ts&&(ts.series||ts);
    if(!Array.isArray(raw)||!raw.length)continue;
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-windowMonths);
    var filtered=raw.filter(function(p){return p.date&&new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
    if(filtered.length<2)continue;
    out.push({key:key,data:filtered.map(function(p){return{date:p.date,value:parseFloat(p.value)||0}}),color:colors[kj%colors.length]});
  }
  return out;
}

/* ── TL;DR: Policy Developments ── */
async function _tldrBuildPolicy(){
  let policyItems=[];
  let policySummary='';
  try{
    const raw=await fetchJSON('policy.json');
    const weeks=raw&&raw.weeks?raw.weeks:[];
    if(weeks.length){
      const w=weeks[0];
      policyItems=w.items||(w.summary&&w.summary.top_developments)||[];
      if(w.summary&&typeof w.summary.narrative==='string'&&w.summary.narrative.length>10)policySummary=w.summary.narrative;
      else if(typeof w.summary==='string'&&w.summary.length>10)policySummary=w.summary;
    }
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
    const level=(p.level||'').toLowerCase();
    const tagCls=level==='federal'?'federal':level==='regulatory'?'regulatory':'provincial';
    const tagLabel=level?level.charAt(0).toUpperCase()+level.slice(1):'';
    const tagHtml=tagLabel?`<span class="tldr-policy-tag ${tagCls}">${tagLabel}</span>`:'';
    const linkHtml=url?` <a class="tldr-policy-item-link" href="${url}" target="_blank">View source \u2192</a>`:'';
    itemsHtml+=`<details class="tldr-policy-item" open>
      <summary><span class="tldr-policy-item-title">${title}</span>${tagHtml}</summary>
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
      <span class="tldr-section-sub">${(function(){const counts={};policyItems.forEach(p=>{const l=(p.level||'other').toLowerCase();counts[l]=(counts[l]||0)+1});const parts=[policyItems.length+' item'+(policyItems.length!==1?'s':'')];Object.keys(counts).forEach(k=>{parts.push(counts[k]+' '+k)});return parts.join(' \u00B7 ')})()}</span>
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
    weekStart=_localYMD(mon);
    weekEnd=_localYMD(sun);
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

  // Filter out projects without assigned values, then combine: new first, then status changes, cap at 12
  const hasValue=p=>p.value&&p.value!=='N/A'&&p.value!=='Not disclosed'&&p.value!=='—'&&p.value!=='';
  const valuedNew=newProjects.filter(p=>hasValue(p.value)&&meetsProvThreshold(p));
  const valuedChanges=statusChanges.filter(p=>hasValue(p.value)&&meetsProvThreshold(p));
  const tableProjects=[...valuedNew.slice(0,6),...valuedChanges.slice(0,12-Math.min(valuedNew.length,6))];

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
        svg.append('text').attr('x',pt[0]).attr('y',pt[1]).attr('text-anchor','middle').attr('font-family','Inter').attr('font-size',11).attr('font-weight',700).attr('fill','#0f1b33').text(code);
      });

      // ── Maritime inset (top-right corner) — NB, NS, PE ──
      const maritimeCodes=new Set(['NB','NS','PE']);
      const maritimeFeatures=geojson.features.filter(f=>maritimeCodes.has(featureCode(f)));
      if(maritimeFeatures.length){
        const iw=Math.round(w*0.26);const ih=Math.round(iw*0.8);
        const ix=w-iw-12;const iy=12;
        const ig=svg.append('g').attr('class','maritime-inset');
        ig.append('rect').attr('x',ix).attr('y',iy).attr('width',iw).attr('height',ih).attr('fill','#F0F4FF').attr('stroke','rgba(37,99,235,0.25)').attr('stroke-width',1).attr('rx',6);
        ig.append('text').attr('x',ix+iw/2).attr('y',iy+12).attr('text-anchor','middle').attr('font-family','Inter').attr('font-size',8).attr('font-weight',600).attr('fill','#64748B').text('Maritimes');
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
          ig.append('text').attr('x',pt[0]).attr('y',pt[1]).attr('text-anchor','middle').attr('font-family','Inter').attr('font-size',9).attr('font-weight',700).attr('fill','#0f1b33').text(code);
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
  const layout=d3.layout.cloud().size([w,h]).words(words).padding(6).rotate(()=>0).font('Inter').fontSize(d=>d.size).on('end',drawn);
  layout.start();
  function drawn(wds){
    const svg=d3.select(container).append('svg').attr('width',w).attr('height',h);
    const g=svg.append('g').attr('transform','translate('+w/2+','+h/2+')');
    g.selectAll('text').data(wds).enter().append('text')
      .style('font-size',d=>d.size+'px').style('font-family','Inter')
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
  {key:'canada',label:'Canada',flag:''},
  {key:'us',label:'United States',flag:''},
  {key:'china',label:'China',flag:''},
  {key:'eu',label:'European Union',flag:''},
  {key:'uk',label:'United Kingdom',flag:''}
];
const GLOBAL_SRC_MAP={us:'BEA \u00b7 BLS \u00b7 Federal Reserve',china:'NBS \u00b7 PBOC \u00b7 GAC',eu:'Eurostat \u00b7 ECB \u00b7 S&P Global',uk:'ONS \u00b7 BoE \u00b7 LSE'};
const GLOBAL_CHART_CFG={
  us:{tsKeys:['idx_sp500','sp500'],title:'S&P 500 \u2014 12-Month Performance',subtitle:'Monthly close',source:'S&P Dow Jones Indices',color:'#1e40af',fillColor:'rgba(30,64,175,0.12)',refLine:null,valueSuffix:''},
  china:{tsKeys:['china_pmi'],title:'Manufacturing PMI \u2014 12-Month Trend',subtitle:'Official NBS PMI \u00b7 50 = expansion threshold',source:'National Bureau of Statistics',color:'#b91c1c',fillColor:'rgba(185,28,28,0.10)',refLine:{value:50,label:'Expansion threshold',color:'#7a8599'},valueSuffix:''},
  eu:{tsKeys:['eurusd'],title:'EUR/USD Exchange Rate \u2014 12-Month Trend',subtitle:'Daily close \u00b7 ECB reference rate',source:'ECB',color:'#1e40af',fillColor:'rgba(30,64,175,0.12)',refLine:null,valueSuffix:''},
  uk:{tsKeys:['idx_ftse','ftse100'],title:'FTSE 100 \u2014 12-Month Performance',subtitle:'Daily close \u00b7 London Stock Exchange',source:'LSE',color:'#065f46',fillColor:'rgba(6,95,70,0.12)',refLine:null,valueSuffix:''}
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
  return primaryLabel+' '+verb+pctStr+' over the past year';
}

/* == Agent-driven insight chart system == */
// When agents provide an insightChart spec, render their chosen visualization
// instead of the keyword-based fallback system.

// Split text into sentences handling decimals, acronyms, and dollar amounts
function _splitSentences(text){
  if(!text)return [];
  // Protect decimals, acronyms, and numbered refs before splitting
  var protected_=text
    .replace(/(\d)\.(\d)/g,'$1\u2024$2')  // protect decimals (7.6 → 7•6)
    .replace(/\b([A-Z])\.([A-Z])/g,'$1\u2024$2')  // acronyms (U.S.)
    .replace(/\$([\d.]+)/g,function(m,n){return '$'+n.replace(/\./g,'\u2024')});
  var sentences=protected_.match(/[^.!?]+[.!?]+/g)||[];
  return sentences.map(function(s){return s.replace(/\u2024/g,'.').trim()});
}

// Build rich callout text by combining agent reasoning with additional context from all province narrative fields
function _buildProvCalloutText(chartSpec,provData,chartIdx){
  // The validator-enforced spec callout takes precedence over synthesized enrichment (mirrors the industries path)
  if(hasVal(chartSpec.callout))return san(chartSpec.callout);
  var reasoning=chartSpec.reasoning||'';
  // Strip only the most database-specific phrases, keep the news-driven content
  reasoning=reasoning
    .replace(/\s*The province tracks[^.]*(?:in rate-sensitive sectors[^.]*)?\./gi,'')
    .replace(/\s*The database tracks[^.]*\./gi,'')
    .replace(/\s*[^.]*\bmake[s]?\s+[^.]*\ba key secondary indicator[^.]*\./gi,'')
    .trim();
  // Gather all narrative text from the province
  function _clean(t){return(t||'').replace(/<sup[^>]*>[\s\S]*?<\/sup>/gi,'').replace(/<[^>]+>/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ').trim()}
  var allText=[_clean(provData.analysis),_clean(provData.labourDeepDive),_clean(provData.consumerPulse),_clean(provData.sectorHighlights),_clean(provData.tradeExposure),_clean(provData.marketContext)].join(' ');
  var sentences=_splitSentences(allText);
  // Determine topic keywords from the chart title/dataKeys
  var topicKw=((chartSpec.title||'')+' '+(chartSpec.dataKeys||[]).join(' ')).toLowerCase();
  // Domain-specific keyword expansion
  var kwMap={unemploy:['unemploy','employ','labour','labor','worker','job','hiring'],trade:['trade','export','import','tariff','manufactur'],housing:['housing','home','residential','permit','dwelling','starts'],gdp:['gdp','growth','output','economy'],cpi:['cpi','inflation','price'],invest:['invest','capital','expenditure']};
  var topicWords=[];
  for(var k in kwMap){if(topicKw.indexOf(k)!==-1)topicWords=topicWords.concat(kwMap[k])}
  if(!topicWords.length)topicWords=topicKw.match(/[a-z]{4,}/g)||[];
  // Extract numbers already in the reasoning so we can prefer sentences with DIFFERENT numbers
  function _extractNums(t){var m=(t||'').match(/\$?[\d,]+(?:\.\d+)?[%]?/g)||[];return m.map(function(x){return x.replace(/,/g,'')}).filter(function(x){return x.length>1})}
  var reasonNums=_extractNums(reasoning);
  var existingLow=reasoning.toLowerCase();
  var extras=[];
  for(var i=0;i<sentences.length;i++){
    var s=sentences[i].trim();
    if(s.length<40||s.length>280)continue;
    var sLow=s.toLowerCase();
    // Skip duplicates from reasoning (first 30 chars)
    if(sLow.length>30&&existingLow.indexOf(sLow.substring(0,30))!==-1)continue;
    // Skip pure database/pipeline references
    if(/\bthe database\b|\bthe pipeline\b|\btracks\s+\d+\s+projects/i.test(s))continue;
    // Must contain a specific data point
    if(!/\$[\d.]|\d+(?:\.\d+)?%|\d+\s*(?:billion|million|projects|homes|km|jobs|workers|units)/i.test(s))continue;
    // Score by topic keyword matches
    var matchCount=topicWords.filter(function(w){return sLow.indexOf(w)!==-1}).length;
    if(matchCount===0)continue;
    // Count how many NEW numbers this sentence introduces (vs what's in reasoning)
    var sNums=_extractNums(s);
    var newNums=sNums.filter(function(n){return reasonNums.indexOf(n)===-1}).length;
    // Penalize sentences that mostly repeat reasoning's numbers
    var overlapRatio=sNums.length>0?(sNums.length-newNums)/sNums.length:0;
    if(overlapRatio>0.6)continue;
    extras.push({s:s,score:matchCount*3+newNums});
  }
  extras.sort(function(a,b){return b.score-a.score});
  var enriched=reasoning;
  // Add the single best-matching supporting sentence
  if(extras.length&&enriched.length<350){
    enriched+=' '+extras[0].s;
  }
  return enriched||reasoning||(chartSpec.title||'');
}

function buildAgentInsightStrip(prefix,chartSpec,provData){
  if(!chartSpec||!chartSpec.dataKeys||!chartSpec.dataKeys.length)return '';
  var calloutText=_buildProvCalloutText(chartSpec,provData||{},0);
  var html='';
  if(calloutText)html+='<div class="narrative chart-intro"><p>'+calloutText+'</p></div>';
  html+='<div class="tldr-callout">';
  html+='<div class="tldr-callout-chart">';
  html+='<div class="tldr-callout-svg" id="'+prefix+'AgentInsightSvg"><div style="height:280px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">Loading chart\u2026</div></div>';
  html+='</div></div>';
  return html;
}

async function renderAgentInsightChart(prefix,chartSpec,prov){
  if(!chartSpec||!chartSpec.dataKeys||!chartSpec.dataKeys.length)return;
  var el=document.getElementById(prefix+'AgentInsightSvg');
  if(!el)return;
  var series=await _loadChartSpecSeries(chartSpec,prov);
  if(!series.length){
    el.innerHTML='<div style="height:280px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">No historical data available</div>';
    return;
  }
  var title=chartSpec.title||'Weekly Insight';
  var subtitle=(chartSpec.subtitle||'').replace(/\b\d+[-\s]?month\b/i,'12-month');
  var chartType=chartSpec.chartType||'line';
  var source=chartSpec.source||_deriveChartSource(chartSpec.dataKeys);
  el.innerHTML=_svgCalloutChart(series,chartSpec.annotations||[],title,subtitle,chartType,source);
}

// Pick a sensible source attribution from dataKeys when the chart spec doesn't provide one.
function _deriveChartSource(keys){
  var ks=(keys||[]).map(function(k){return String(k).toLowerCase()}).join(',');
  if(/\bwti\b|\bbrent\b|\bwcs\b/.test(ks))return'Source: EIA, ICE \u00b7 daily spot close';
  if(/\bnatural_gas\b|\bpropane\b|\blng\b/.test(ks))return'Source: EIA, NYMEX';
  if(/\bgold\b|\bsilver\b|\bcopper\b|\bnickel\b|\bzinc\b|\blithium\b|\baluminum\b|\biron_ore\b|\bpotash\b/.test(ks))return'Source: LBMA, LME';
  if(/\bwheat\b|\bcanola\b|\bsoybean\b|\bcorn\b|\blumber\b/.test(ks))return'Source: CBOT, ICE Futures';
  if(/\bcadusd\b|\bcad_usd\b|\busdcad\b/.test(ks))return'Source: Bank of Canada';
  if(/\bboc_rate\b|\bovernight\b|\bgoc_\d/.test(ks))return'Source: Bank of Canada';
  if(/^(on|qc|ab|bc|sk|mb|ns|nb|nl|pe|yt|nt|nu)_/i.test((keys||[])[0]||'')||/_unemployment|_cpi|_gdp|_employment|_exports|_imports|_housing|_permits|_manufacturing/.test(ks))return'Source: Statistics Canada';
  return'Source: Statistics Canada, Bank of Canada';
}

function buildInsightStrip(prefix,themes,provCode){
  if(!themes||!themes.length)return '';
  const t=themes[0];
  const id=prefix+'Insight0';
  const tsEntries=resolveThemeTimeseries(t.id,provCode||null);
  const sub=tsEntries.length?tsEntries.map(s=>s.label).join(', ')+' \u2014 12-month trend':'From this week\u2019s analysis';
  // Build callout structure matching TL;DR pattern: text component on top, chart below
  let html='<div class="tldr-callout" style="margin:20px 0">';
  html+='<div id="'+prefix+'InsightCalloutText" style="font-family:\'Inter\',sans-serif;font-size:15px;line-height:1.6;color:#4a5568">'+t.label+'</div>';
  html+='<div class="tldr-callout-chart">';
  html+='<div class="tldr-callout-chart-title" id="'+prefix+'InsightTitle">'+t.label+'</div>';
  html+='<div id="'+prefix+'InsightSub" style="font-family:\'Inter\',sans-serif;font-size:10px;color:#7a8599;margin-bottom:10px">'+sub+'</div>';
  html+='<div style="height:280px;position:relative;padding:12px 16px;background:#fff;border-radius:6px"><canvas id="'+id+'"></canvas></div>';
  html+='<div class="tldr-callout-source">Source: Signal Dispatch pipeline data</div>';
  html+='</div></div>';
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
  font:'Inter',
  // palCat from _chartCfg (blue-first editorial palette)
  pal:['#2563EB','#10B981','#F59E0B','#8B5CF6','#EC4899','#EF4444','#0EA5E9','#84CC16','#94A3B8'],
  // Title config factory
  ttl:function(text){return{display:true,text:text,font:{family:'Inter',size:11,weight:600},color:'#1a2744'}},
  // Axis tick config factory
  tk:function(sz,wt){return{font:{family:'Inter',size:sz||9,weight:wt||400},color:'#475569'}},
  tkLabel:function(sz){return{font:{family:'Inter',size:sz||9,weight:500},color:'#1a2744'}},
  // Legend config factory
  leg:function(pos){return{position:pos||'right',labels:{boxWidth:10,padding:6,font:{family:'Inter',size:9},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}}},
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
    if(filtered.length<2)return; // Need at least 2 points to draw a meaningful line
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
  // Update subtitle to reflect only datasets that actually rendered
  const subEl=document.getElementById(prefix+'InsightSub');
  if(subEl&&datasets.length){
    subEl.textContent=datasets.map(ds=>ds.label).join(', ')+' \u2014 12-month trend';
  }
  // Populate the callout text component with a data-driven summary — news & public data only
  const calloutTextEl=document.getElementById(prefix+'InsightCalloutText');
  if(calloutTextEl&&primaryData&&primaryData.length>=2){
    const first=primaryData[0],last=primaryData[primaryData.length-1];
    const pctChg=first!==0?((last-first)/Math.abs(first))*100:0;
    const verb=Math.abs(pctChg)<1?'held roughly steady':(pctChg>0?(Math.abs(pctChg)>10?'climbed sharply':'rose'):(Math.abs(pctChg)>10?'fell sharply':'declined'));
    const pctStr=Math.abs(pctChg)>=1?(' '+Math.abs(pctChg).toFixed(1)+'%'):'';
    var curStr=typeof last==='number'?(Math.abs(last)<100?last.toFixed(1)+'%':last.toLocaleString()):last;
    var text='<strong>'+primaryLabel+'</strong> '+verb+pctStr+' over the past 12 months, reaching <strong>'+curStr+'</strong> in the latest reading.';
    calloutTextEl.innerHTML=text;
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
function _natIndTable(flag,title,indRows,srcLine,chgHeader){
  var html='<div class="indicator-panel">';
  html+='<div class="indicator-panel-header"><div class="indicator-panel-title">'+(flag?'<span class="flag">'+flag+'</span> ':'')+title+'</div>';
  if(srcLine)html+='<span style="font-size:11px;color:#7a8599">'+srcLine+'</span>';
  html+='</div>';
  var chgCol=chgHeader||'Change';
  html+='<table class="tldr-ind-table"><thead><tr><th>Indicator</th><th>Frequency</th><th>Value</th><th>'+chgCol+'</th><th>Source</th></tr></thead><tbody>';
  indRows.forEach(function(r){
    var chgRaw=r.change||'';
    var chg=_normalizeChg(chgRaw)||chgRaw;
    var cls='';
    if(chg){
      var s=String(chg);
      if(s.indexOf('\u25B2')!==-1||s.startsWith('+'))cls='ind-t-chg up';
      else if(s.indexOf('\u25BC')!==-1||s.startsWith('-')||s.startsWith('\u2212'))cls='ind-t-chg down';
      else if(/held|flat|0bp/i.test(s))cls='ind-t-chg unch';
      else cls='ind-t-chg unch';
    }else{cls='ind-t-chg unch';chg=''}
    var arrow='';
    if(cls.indexOf('up')!==-1)arrow='\u25B2 ';
    else if(cls.indexOf('down')!==-1)arrow='\u25BC ';
    else if(chg)arrow='\u2014 ';
    // Strip existing arrows from chg text to avoid doubles
    chg=chg.replace(/^[\u25B2\u25BC\u2014]\s*/,'');
    // Convert zero changes to "Held"
    if(/^[+\-]?0(\.0+)?(%|pp|bp)?$/i.test(chg.trim())){chg='Held';cls='ind-t-chg unch';arrow='\u2014 '}
    var freq=r.freq||'';
    var period=r.period||'';
    var ctxParts=[];
    if(period)ctxParts.push(period);
    var ctxHtml=ctxParts.length?' <span class="ind-t-name-ctx">'+san(ctxParts.join(' \u00B7 '))+'</span>':'';
    var src=r.source||'';
    html+='<tr><td class="ind-t-name">'+san(r.label)+ctxHtml+'</td>';
    html+='<td class="ind-t-unit">'+san(freq)+'</td>';
    html+='<td class="ind-t-val">'+san(String(r.value))+'</td>';
    html+='<td class="'+cls+'">'+arrow+san(chg)+'</td>';
    html+='<td class="ind-t-src">'+_srcLink(src)+'</td></tr>';
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
async function _initCanadaInsightChart(canvasId){
  var canvas=document.getElementById(canvasId);if(!canvas)return;
  // Replace the parent .insight-chart-wrapper (title+subtitle+chart+source) with a cream tldr-callout containing one SVG chart.
  var wrapper=canvas.closest('.insight-chart-wrapper')||canvas.parentElement;
  if(!wrapper)return;
  try{
    var ts=await loadTimeseries('unemployment_rate');
    var raw=ts&&(ts.series||ts);
    if(!Array.isArray(raw)||!raw.length){wrapper.innerHTML='<div class="tldr-callout"><div class="tldr-callout-chart" style="padding:40px 0;text-align:center;color:#7a8599;font-size:12px">No data</div></div>';return}
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    var filtered=raw.filter(function(p){return p.date&&new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
    if(filtered.length<3){wrapper.innerHTML='<div class="tldr-callout"><div class="tldr-callout-chart" style="padding:40px 0;text-align:center;color:#7a8599;font-size:12px">No data</div></div>';return}
    var series=[{key:'unemployment_rate',data:filtered,color:'#003153'}];
    var svg=_svgCalloutChart(series,[],'Canada Unemployment Rate','Seasonally adjusted \u00b7 12-month trend','line','Source: Statistics Canada, Table 14-10-0287');
    wrapper.outerHTML='<div class="tldr-callout"><div class="tldr-callout-chart"><div class="tldr-callout-svg">'+svg+'</div></div></div>';
  }catch(e){console.warn('Canada insight chart:',e)}
}
var _globalChartInited={};
async function _initGlobalInsightChart(countryKey,canvasId){
  if(_globalChartInited[countryKey])return;_globalChartInited[countryKey]=true;
  var cfg=GLOBAL_CHART_CFG[countryKey];if(!cfg)return;
  var canvas=document.getElementById(canvasId);if(!canvas)return;
  var wrapper=canvas.closest('.insight-chart-wrapper')||canvas.parentElement;
  if(!wrapper)return;
  try{
    var allTs=await fetchJSON('timeseries.json').catch(function(){return{}});
    var raw=null;var keys=cfg.tsKeys||[cfg.tsKey];var pickedKey=keys[0];
    for(var k=0;k<keys.length;k++){
      var candidate=allTs[keys[k]];
      if(candidate){
        var arr=Array.isArray(candidate)?candidate:(candidate.series||[]);
        if(!raw||arr.length>raw.length){raw=arr;pickedKey=keys[k]}
      }
    }
    if(!raw||!raw.length){wrapper.innerHTML='<div class="tldr-callout"><div class="tldr-callout-chart" style="padding:40px 0;text-align:center;color:#7a8599;font-size:12px">No data</div></div>';return}
    var cutoff=new Date();cutoff.setMonth(cutoff.getMonth()-12);
    var filtered=raw.filter(function(p){return p.date&&new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
    if(filtered.length<3){filtered=raw.slice().sort(function(a,b){return new Date(a.date)-new Date(b.date)}).slice(-24)}
    if(filtered.length<3){wrapper.innerHTML='<div class="tldr-callout"><div class="tldr-callout-chart" style="padding:40px 0;text-align:center;color:#7a8599;font-size:12px">No data</div></div>';return}
    var series=[{key:pickedKey,data:filtered,color:cfg.color||'#003153'}];
    var title=(cfg.title||'').split(' \u2014')[0]||cfg.title||'';
    var svg=_svgCalloutChart(series,[],title,cfg.subtitle||'','line','Source: '+(cfg.source||'Market data'));
    wrapper.outerHTML='<div class="tldr-callout"><div class="tldr-callout-chart"><div class="tldr-callout-svg">'+svg+'</div></div></div>';
  }catch(e){console.warn('Global insight chart '+countryKey+':',e)}
}
async function _renderCanadaSubtab(){
  var el=$('natContent-canada');if(!el)return;
  var m=(D&&D.metrics)||{};var im=(D&&D.indicatorMeta)||{};
  function indVal(name){var i=indicators.find(function(x){return x.indicator_name===name});return i?i.value:null}
  function indRec(name,prov){return indicators.find(function(x){return x.indicator_name===name&&(!prov||(x.province||'').toLowerCase()===prov.toLowerCase())})||indicators.find(function(x){return x.indicator_name===name})||null}
  function indMeta(name){return(im&&im[name])||{}}
  function chg(metaKey,indName){return pick(indMeta(metaKey).change,computeChange(indName||metaKey,'national'))}
  var _rBoc=indRec('overnight_rate','national'),_rGdp=indRec('realGdp','national'),_rCpi=indRec('cpi','national'),_rUnemp=indRec('unemployment','national'),_rHs=indRec('housingStarts','national'),_rCad=indRec('cad_usd','national')||indRec('cadusd','national');

  // Build indicator rows from indicatorMeta (pipeline-curated each week) + metrics as value source.
  // Fallback chain per row: metrics -> indicators.json national record ->
  // StatCan Daily feed -> indicatorMeta.prev. Rows resolving nowhere are
  // dropped below — an 'N/A' must never render in the Value column.
  var im=D.indicatorMeta||{};
  function metaRow(label,metaKey,valKeys,freq,fallbackSrc,indNames,daily){
    var meta=im[metaKey]||{};
    var val='',chg=meta.change||'',src=meta.source||fallbackSrc,per=meta.period||'';
    for(var i=0;i<valKeys.length;i++){if(hasVal(m[valKeys[i]])){val=String(m[valKeys[i]]);break}}
    if(!val&&indNames){
      for(var i=0;i<indNames.length;i++){
        var name=indNames[i];
        var r=indicators.find(function(x){return x.indicator_name===name&&_matchProv(x.province,null)&&hasVal(x.value)&&String(x.value)!=='None'});
        if(r){val=String(r.value);chg=chg||((hasVal(r.change)&&String(r.change)!=='None')?String(r.change):'');per=per||r.period||'';src=src||r.source;break}
      }
    }
    if(!val&&daily){var dr=_scDailyRec(daily);if(dr){val=dr.value;chg=chg||dr.change;per=per||dr.period}}
    if(!val&&hasVal(meta.prev))val=String(meta.prev);
    return{label:label,value:val,change:chg||computeChange(metaKey,'national'),
      source:src,period:per,freq:freq};
  }
  var natIndicators=[
    metaRow('BoC Rate','bocRate',['bocRate','boc_rate'],'8x/yr','Bank of Canada',['overnight_rate']),
    metaRow('Real GDP','realGdp',['realGdp','gdp'],'Monthly','Statistics Canada',['realGdp']),
    metaRow('CPI Inflation','cpi',['cpi'],'Monthly','Statistics Canada',['cpi'],/^Consumer Price Index$/i),
    metaRow('Unemployment Rate','unemployment',['unemployment'],'Monthly','Statistics Canada',['unemployment'],/^Unemployment rate$/i),
    metaRow('Employment Change','employmentChange',['employmentChange','employment_change'],'Monthly','Statistics Canada'),
    metaRow('Participation Rate','participation',['participation','participationRate'],'Monthly','Statistics Canada',['participationRate']),
    metaRow('Housing Starts','housingStarts',['housingStarts','housing_starts'],'Monthly','CMHC',['housingStarts','housing_starts_total']),
    metaRow('Building Permits','buildingPermits',['building_permits','buildingPermits'],'Monthly','Statistics Canada',['national_building_permits_total'],/^Building permits$/i)
  ].filter(function(r){return hasVal(r.value)});
  var natProjects=[];
  try{var d=await fetchJSON('projects_all.json');natProjects=Array.isArray(d)?d:[]}catch(e){}
  var projTotal=natProjects.length||allProjects.length||0;
  var ds=D&&D.discovery_stats||{};
  var newPrj=ds.new_this_week||D&&D.new_projects||0;
  var pipVal=ds.total_value_billions||D&&D.pipeline_value||'';
  // pipeline_value may arrive pre-formatted ("$1113.4B") from the finalize
  // alias backfill — strip the wrapper so the template's '$'+pipVal+'B'
  // doesn't render "$$1113.4BB" (red-team 4.4, 2026-06-11)
  if(typeof pipVal==='string'){pipVal=pipVal.replace(/^\$/,'').replace(/B$/i,'')}
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
  html+=_natIndTable('','Canada \u2014 National',natIndicators,'');
  html+='<div id="natEnrichmentCards" class="two-col"></div></div>';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Project Pipeline \u2014 Canada</h3><span class="section-meta">'+projTotal+' tracked'+(pipVal?' \u00b7 $'+pipVal+'B total value':'')+'</span></div>';
  if(newPrj||natProjects.length){
    // Separate new projects from existing, sort each by value, new first
    var weekOf=D&&D.week_of||'';var weekStart='',weekEnd='';
    if(weekOf){var dt=new Date(weekOf+'T00:00:00');var mon=new Date(dt);mon.setDate(dt.getDate()-dt.getDay()+1);var sun=new Date(mon);sun.setDate(mon.getDate()+6);weekStart=_localYMD(mon);weekEnd=_localYMD(sun)}
    var newNatProjects=[];var existingNatProjects=[];
    natProjects.filter(meetsProvThreshold).forEach(function(p){
      var tracked=(p.firstTracked||'').slice(0,10);
      var isNew=weekStart&&tracked>=weekStart&&tracked<=weekEnd;
      if(isNew&&newPrj>0)newNatProjects.push(p);else existingNatProjects.push(p);
    });
    var valSort=function(a,b){return parseNumericValue(b.value)-parseNumericValue(a.value)};
    newNatProjects.sort(valSort);existingNatProjects.sort(valSort);
    var topProjects=[].concat(newNatProjects.slice(0,5),existingNatProjects.slice(0,10-Math.min(newNatProjects.length,5))).slice(0,10);
    if(newPrj){html+='<div class="dash-narrative" style="margin-bottom:16px"><p style="font-size:15px;line-height:1.7"><span class="lead">The pipeline added '+newPrj+' new projects this week.</span></p></div>'}
    if(topProjects.length){
      html+='<div class="inner-card" style="padding:0;overflow:hidden"><table class="dash-projects-table"><thead><tr><th>Project</th><th>Province</th><th>Sector</th><th>Value</th><th>Status</th></tr></thead><tbody>';
      topProjects.forEach(function(p){
        var sectorName=_normSector(p.sector);var stClass='status-proposed';var stLabel=p.status||'Proposed';
        if(stLabel.toLowerCase().indexOf('construction')!==-1)stClass='status-construction';
        else if(stLabel.toLowerCase().indexOf('review')!==-1)stClass='status-review';
        else if(stLabel.toLowerCase().indexOf('pre')!==-1||stLabel.toLowerCase().indexOf('approved')!==-1)stClass='status-pre';
        var isNew=newNatProjects.indexOf(p)!==-1;
        var newTag=isNew?' <span class="tldr-freq-tag" style="background:#003153;color:#fff;margin-left:6px">NEW</span>':'';
        html+='<tr><td style="font-weight:500">'+((p.name||'').substring(0,55))+newTag+'</td><td>'+normProvince(p.province)+'</td><td>'+sectorName+'</td><td style="font-variant-numeric:tabular-nums">'+fmtCurrency(p.value,p)+'</td><td><span class="dash-status-badge '+stClass+'">'+stLabel+'</span></td></tr>';
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
  var indJson=_indJsonCache;if(!indJson){try{indJson=await fetchJSON('indicators.json')}catch(e){indJson=null}}

  // A metrics value must be a short data point. Writers emit the 'N/A'
  // sentinel when a series is missing, and have shipped deferral prose
  // ("See CPI April 2026 detail...") — both used to render as blank or
  // wrapped cells. Reject both so the fallback chain below takes over.
  function mVal(v){
    if(!hasVal(v))return'';
    var s=String(v).trim();
    if(s.length>48)return'';
    if(/\b(see|pending|per statcan|release|detail|dossier|awaiting|tbd)\b/i.test(s))return'';
    if(!/\d/.test(s)&&!/^(little changed|unchanged|flat|held)/i.test(s))return'';
    return s;
  }
  // Freshest national record from the pipeline's indicators.json across
  // candidate series names (SQLite export uses the string 'None' for null)
  function indRec(names){
    var best=null,bestName='';
    for(var i=0;i<names.length;i++){
      for(var j=0;j<indicators.length;j++){
        var x=indicators[j];
        if(x.indicator_name===names[i]&&_matchProv(x.province,null)&&hasVal(x.value)&&String(x.value)!=='None'){
          if(!best||String(x.period||'')>String(best.period||'')){best=x;bestName=names[i]}
        }
      }
    }
    if(!best)return null;
    var chg=(hasVal(best.change)&&String(best.change)!=='None')?String(best.change):(computeChange(bestName,null)||'');
    return {value:String(best.value),change:chg,source:best.source||'',period:best.period||''};
  }
  // StatCan Daily release feed — shared lookup in _scDailyRec; pass the
  // locally fetched list so this works even before loadIndicators() ran
  var scDaily=(indJson&&indJson.statcan_latest&&indJson.statcan_latest.indicators)||[];
  function dailyRec(re){return _scDailyRec(re,scDaily)}

  function enrichTable(title,rows,chgLabel){
    var indRows=[];
    rows.forEach(function(r){
      // Resolution chain: explicit val -> briefing metrics (snake/alt/camel)
      // -> indicators.json national record -> StatCan Daily release feed.
      // A row that resolves nowhere is dropped — never render a blank cell.
      var val=(r.val!==undefined&&hasVal(r.val))?String(r.val):'';
      var src=r.source||'',per='';
      if(!val)val=mVal(m[r.key])||mVal(r.alt&&m[r.alt])||mVal(r.camel&&m[r.camel]);
      var chgKey=r.chgKey||(r.key?r.key+'_chg':'');
      var chg=mVal(chgKey&&m[chgKey])||mVal(r.alt&&m[r.alt+'_chg'])||'';
      if(!val&&r.ind){var ir=indRec(r.ind);if(ir){val=ir.value;chg=chg||ir.change;per=fmtPeriod(ir.period);src=src||ir.source}}
      if(!val&&r.daily){var dr=dailyRec(r.daily);if(dr){val=dr.value;chg=chg||dr.change;per=dr.period;src=src||dr.source}}
      if(!val)return;
      if(!chg&&r.ind){for(var i=0;i<r.ind.length;i++){chg=computeChange(r.ind[i],null)||'';if(chg)break}}
      if(r.fmt)val=r.fmt(val);
      indRows.push({label:r.label,value:val,change:chg,source:src||'Statistics Canada',period:per||r.period||'',freq:r.freq||''});
    });
    if(!indRows.length)return'';
    // Use custom change header label
    return _natIndTable('',title,indRows,'',chgLabel);
  }

  var wtiSpot=comms.wti&&comms.wti.current!=null?comms.wti.current:(mVal(m.wti)||mVal(m.wti_crude));
  function fmtUsd(suffix){return function(v){var n=parseFloat(String(v).replace(/[^\d.\-]/g,''));return isNaN(n)?String(v):'US$'+n.toFixed(2)+suffix}}

  var html='';
  html+=enrichTable('Labour Market',[
    {label:'Employment Change',key:'employmentChange',alt:'employment_change',freq:'Monthly',source:'Statistics Canada'},
    {label:'Employment Level',daily:/^Employment level$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Full-time',key:'fulltime_change',camel:'fulltimeChange',freq:'Monthly',source:'Statistics Canada'},
    {label:'Part-time',key:'parttime_change',camel:'parttimeChange',freq:'Monthly',source:'Statistics Canada'},
    {label:'Private Sector',key:'private_sector_change',camel:'privateSectorChange',freq:'Monthly',source:'Statistics Canada'},
    {label:'Public Sector',key:'public_sector_change',camel:'publicSectorChange',freq:'Monthly',source:'Statistics Canada'},
    {label:'Avg Weekly Earnings',daily:/^Average weekly earnings$/i,freq:'Monthly',source:'Statistics Canada'}
  ],'Change (M/M)');
  html+=enrichTable('Consumer Pulse',[
    {label:'CPI (All-items)',key:'cpi',ind:['cpi'],daily:/^Consumer Price Index$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Core CPI (Median)',key:'core_cpi_median',alt:'coreCpi',camel:'coreCpiMedian',freq:'Monthly',source:'Statistics Canada'},
    {label:'Shelter',key:'shelter_cpi',camel:'shelterCpi',daily:/^Shelter$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Food',key:'food_cpi',camel:'foodCpi',daily:/^Food purchased from stores$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Energy',key:'energy_cpi',camel:'energyCpi',daily:/^(Energy|Gasoline)$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Retail Sales',daily:/^Retail sales$/i,freq:'Monthly',source:'Statistics Canada'}
  ],'Change (M/M)');
  html+=enrichTable('Housing & Construction',[
    {label:'Housing Starts (SAAR)',key:'housingStarts',alt:'housing_starts',ind:['housingStarts','housing_starts_total'],freq:'Monthly',source:'CMHC'},
    {label:'Building Permits',key:'building_permits',camel:'buildingPermits',daily:/^Building permits$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Residential Permits',key:'residential_permits',camel:'residentialPermits',daily:/^Residential building permits/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Non-Residential Permits',key:'nonresidential_permits',camel:'nonresidentialPermits',daily:/^Non-residential building permits/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Building Construction Investment',daily:/^Total investment in building construction$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'New Housing Price Index',ind:['new_housing_price_index'],freq:'Monthly',source:'Statistics Canada'}
  ],'Change (M/M)');
  html+=enrichTable('Trade & Commodities',[
    {label:'Merchandise Exports',key:'merchandise_exports',camel:'merchandiseExports',daily:/^Merchandise exports$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Merchandise Imports',key:'merchandise_imports',camel:'merchandiseImports',daily:/^Merchandise imports$/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'Trade Balance',key:'tradeBalance',alt:'trade_balance',daily:/^Merchandise trade balance/i,freq:'Monthly',source:'Statistics Canada'},
    {label:'WTI Crude',val:wtiSpot||undefined,ind:['wti','wti_oil'],chgKey:'wti_chg',fmt:fmtUsd('/bbl'),freq:'Daily',source:'yfinance'},
    {label:'CAD/USD',key:'cadUsd',alt:'cad_usd',ind:['cadusd'],chgKey:'cadUsd_chg',fmt:fmtUsd(''),freq:'Daily',source:'yfinance'}
  ],'Change (M/M)');

  // Hiring Signals - keep as narrative card
  // jobs.json is a LIST of weekly snapshots [{week_of, data, spikes}] —
  // the old read (jobData.spikes) could never match (red-team 4.2, 2026-06-11)
  var jobData=null;try{jobData=await fetchJSON('jobs.json')}catch(e){}
  var jobSpikes=Array.isArray(jobData)?((jobData[0]||{}).spikes||[]):((jobData||{}).spikes||[]);
  if(jobSpikes.length){
    var spikeTexts=jobSpikes.slice(0,3).map(function(s){return '<strong>'+(s.sector||s.industry||'')+(s.change?' ('+s.change+')':'')+' </strong>'+(s.cma||s.region||s.location||'')});
    html+='<div class="indicator-panel" style="padding:12px 16px"><div class="indicator-panel-header"><div class="indicator-panel-title">Hiring Signals</div></div><p style="font-size:13px;color:#4a5568;margin:8px 0 0">'+spikeTexts.length+' hiring spike'+(spikeTexts.length!==1?'s':'')+' detected: '+spikeTexts.join(', ')+'.</p></div>';
  }

  // Procurement - keep as narrative card
  // procurement.json is a LIST of weekly snapshots [{week_of, contracts}] —
  // the old read (procData.awards) could never match; rows now include QC
  // SEAO + BC tenders, not only federal awards (red-team 4.3, 2026-06-11)
  var procData=null;try{procData=await fetchJSON('procurement.json')}catch(e){}
  var procRows=Array.isArray(procData)?((procData[0]||{}).contracts||[]):((procData||{}).awards||[]);
  if(procRows.length){
    var totalVal=procRows.reduce(function(s,a){return s+(parseNumericValue(a.value)||0)},0);
    var valStr=totalVal>=1e9?'$'+(totalVal/1e9).toFixed(1)+'B':totalVal>=1e6?'$'+(totalVal/1e6).toFixed(0)+'M':'$'+totalVal.toLocaleString();
    html+='<div class="indicator-panel" style="padding:12px 16px"><div class="indicator-panel-header"><div class="indicator-panel-title">Government Procurement</div></div><p style="font-size:13px;color:#4a5568;margin:8px 0 0">Federal and provincial procurement recorded <strong>'+valStr+'</strong> across '+procRows.length+' contract'+(procRows.length!==1?'s':'')+' and tender notices this week.</p></div>';
  }

  el.innerHTML=html;
}
async function _renderGlobalSubtab(key){
  var el=$('natContent-'+key);if(!el)return;
  var gv=D?D.globalVectors||D.global_vectors||{}:{};var globalArr=D?D.global||[]:[];
  var REGION_MAP={'United States':'us','China':'china','China / Asia':'china','European Union':'eu','United Kingdom':'uk'};
  var FREQ_MAP={gdp:'Quarterly',cpi:'Monthly',rate:'Periodic',unemployment:'Monthly',tradeBalance:'Monthly',productivityGrowth:'Quarterly'};
  var SRC_MAP={us:{gdp:'BEA',cpi:'BLS',rate:'Federal Reserve',unemployment:'BLS',tradeBalance:'Census Bureau',productivityGrowth:'BLS'},china:{gdp:'NBS',cpi:'NBS',rate:'PBOC',unemployment:'NBS',tradeBalance:'GAC',productivityGrowth:'NBS'},eu:{gdp:'Eurostat',cpi:'Eurostat',rate:'ECB',unemployment:'Eurostat',tradeBalance:'Eurostat',productivityGrowth:'S&P Global'},uk:{gdp:'ONS',cpi:'ONS',rate:'BoE',unemployment:'ONS',tradeBalance:'ONS',productivityGrowth:'LSE'}};
  var countryInfo=COUNTRY_SUBTABS.find(function(t){return t.key===key})||{label:key,flag:''};
  var gData=globalArr.find(function(g){return REGION_MAP[g.region]===key})||{};
  var analysis=gData.analysis||gv[key]||'';var gi=gData.indicators||{};var giMeta=gData.indicatorMeta||{};var srcs=SRC_MAP[key]||{};
  if(!analysis&&!hasVal(gi.gdp)&&!hasVal(gi.cpi)&&!hasVal(gi.rate)&&!hasVal(gi.unemployment)){
    el.innerHTML='<div style="text-align:center;padding:48px;color:#7a8599;font-size:14px">'+countryInfo.label+' analysis will be available after the next pipeline run.</div>';return;
  }
  var indRows=[];
  [{key:'gdp',label:'GDP Growth (Real)'},{key:'cpi',label:'CPI Inflation'},{key:'rate',label:'Policy Rate'},{key:'unemployment',label:'Unemployment Rate'},{key:'tradeBalance',label:'Trade Balance'}].forEach(function(x){
    var gm=giMeta[x.key]||{};var per=hasVal(gm.period)?fmtPeriod(gm.period):(FREQ_MAP[x.key]||'');var val=pick(gi[x.key]);
    var chgVal=hasVal(gm.change)?gm.change:'';
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
  charts[key]=new Chart(canvas,{type:'bar',data:{labels:found.map(f=>f.label),datasets:[{label:'Current',data:found.map(f=>f.current),backgroundColor:'#2563EB',borderRadius:4,barPercentage:0.6},{label:'Previous',data:found.map(f=>f.prev),backgroundColor:'#CBD5E1',borderRadius:4,barPercentage:0.6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{boxWidth:10,padding:8,font:{family:'Inter',size:10},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>ctx.dataset.label+': '+fmtNum(ctx.raw)}}},scales:{x:{grid:{display:false},ticks:{font:{family:'Inter',size:9},color:'#475569'}},y:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Inter',size:9},color:'#475569'}}}}});
}
function _renderCommodityChart(canvasId,cardId,prefix){
  const withPct=(_chartComms||[]).filter(c=>c.pct_1w&&c.pct_1w!=='N/A').map(c=>({name:(c.name||c.indicator_name||'').replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),pct:parseFloat(c.pct_1w)||0})).filter(c=>Math.abs(c.pct)>0.1);
  withPct.sort((a,b)=>Math.abs(b.pct)-Math.abs(a.pct));
  const top=withPct.slice(0,8);if(top.length<3)return;
  const canvas=$(canvasId);if(!canvas)return;
  const card=$(cardId);if(card)card.style.display='';
  const key='_cc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart(canvas,{type:'bar',data:{labels:top.map(c=>c.name),datasets:[{data:top.map(c=>c.pct),backgroundColor:top.map(c=>c.pct>=0?'#10B981':'#EF4444'),borderRadius:4,barPercentage:0.65}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}}},scales:{x:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Inter',size:9},color:'#475569',callback:v=>(v>=0?'+':'')+v+'%'}},y:{grid:{display:false},ticks:{font:{family:'Inter',size:9,weight:500},color:'#1a2744'}}}}});
}
function _renderPipelineChart(canvasId,prefix,projPool){
  const projects=projPool||_chartProjects||[];if(!projects.length)return;
  const statusOrder=['Proposed','Under Review','Approved','Under Construction','Partially Complete','Complete','On Hold','Cancelled'];
  const statusColors=['#94A3B8','#60A5FA','#3B82F6','#2563EB','#1D4ED8','#15803D','#F59E0B','#EF4444'];
  const statusCounts={};projects.forEach(p=>{const s=p.status||'Proposed';statusCounts[s]=(statusCounts[s]||0)+1});
  const pL=[],pD=[],pC=[];statusOrder.forEach((s,i)=>{if(statusCounts[s]){pL.push(s);pD.push(statusCounts[s]);pC.push(statusColors[i])}});
  if(!pD.length)return;
  const key='_pl_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart($(canvasId),{type:'bar',data:{labels:pL,datasets:[{data:pD,backgroundColor:pC,borderRadius:6,barPercentage:0.7}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>fmtNum(ctx.raw,0)+' projects'}}},scales:{x:{grid:{display:false},ticks:{font:{family:'Inter',size:9},color:'#475569'}},y:{grid:{display:false},ticks:{font:{family:'Inter',size:9,weight:500},color:'#1a2744'}}}}});
}
function _renderSectorChart(canvasId,prefix,projPool){
  const projects=projPool||_chartProjects||[];if(!projects.length)return;
  const sectorVal={},sectorCnt={};projects.forEach(p=>{const s=p.sector||'Other';const v=parseNumericValue(p.value);sectorVal[s]=(sectorVal[s]||0)+v;sectorCnt[s]=(sectorCnt[s]||0)+1});
  const sorted=Object.entries(sectorVal).sort((a,b)=>b[1]-a[1]);
  const top8=sorted.slice(0,8);const ov=sorted.slice(8).reduce((s,e)=>s+e[1],0);
  if(ov>0)top8.push(['Other',ov]);if(!top8.length)return;
  const key='_sc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart($(canvasId),{type:'doughnut',data:{labels:top8.map(e=>e[0].replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())),datasets:[{data:top8.map(e=>e[1]),backgroundColor:_chartCfg.palCat.slice(0,top8.length),borderWidth:0,hoverOffset:6}]},options:{responsive:true,maintainAspectRatio:false,cutout:'55%',plugins:{legend:{position:'right',labels:{boxWidth:10,padding:6,font:{family:'Inter',size:9},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>ctx.label+': '+_chartCfg.fv(ctx.raw)}}}}});
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
  const _rowHtml=(ind)=>{
    const cls=ind.arrow===1?'change-up':ind.arrow===2?'change-down':'change-flat';
    const chgTxt=ind.change?changeIcon(ind.arrow)+' '+ind.change:'';
    const clickAttr=ind.expId?' onclick="_indExpSelectFromList(\''+ind.expId+'\')"':'';
    const extraCls=ind.expId?' clickable':'';
    return '<div class="indicator-row'+extraCls+'" data-name="'+(ind.name||'').toLowerCase()+'"'+clickAttr+'><div class="indicator-row-name">'+(ind.name||'')+'</div><div class="indicator-row-value">'+(ind.value||'N/A')+'</div><div class="indicator-row-change '+cls+'">'+chgTxt+'</div><div class="indicator-row-period">'+(ind.refPer||'')+'</div><div class="indicator-row-source">'+(ind.tableUrl?'<a href="'+ind.tableUrl+'" target="_blank" onclick="event.stopPropagation()">\u2197</a>':'')+'</div></div>';
  };
  const groupOrder=['Key Economic Indicators','GDP by Industry','Labour Market','Housing','Trade','Monetary & Financial','Other'];
  groupOrder.forEach(g=>{
    const items=groups[g];if(!items||!items.length)return;
    html+='<div class="indicator-group-header">'+g+'</div>';
    items.forEach(ind=>{html+=_rowHtml(ind);});
  });
  Object.keys(groups).filter(g=>!groupOrder.includes(g)).forEach(g=>{
    const items=groups[g];if(!items||!items.length)return;
    html+='<div class="indicator-group-header">'+g+'</div>';
    items.forEach(ind=>{html+=_rowHtml(ind);});
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
  {group:'Prices',items:[
    {id:'cpi',label:'Consumer Price Index (All Items)',unit:'%',source:'Statistics Canada',statcan:true,prov:true,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401'}
  ]},
  {group:'Labour Market',items:[
    {id:'unemployment',label:'Unemployment Rate',unit:'%',source:'Statistics Canada',statcan:true,prov:true,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {id:'employmentRate',label:'Employment Rate',unit:'%',source:'Statistics Canada',statcan:true,prov:true,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {id:'participationRate',label:'Participation Rate',unit:'%',source:'Statistics Canada',statcan:true,prov:true,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {id:'employmentChange',label:'Employment Change',unit:'K',source:'Statistics Canada',statcan:true,prov:false,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {id:'wageGrowth',label:'Wage Growth (Y/Y)',unit:'%',source:'Statistics Canada',statcan:true,prov:false,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006401'}
  ]},
  {group:'GDP & Output',items:[
    {id:'realGdp',label:'Real GDP (Q/Q)',unit:'%',source:'Statistics Canada',statcan:true,prov:false,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401'}
  ]},
  {group:'Housing & Construction',items:[
    {id:'housingStarts',label:'Housing Starts',unit:'K',source:'CMHC',statcan:false,prov:true,url:'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research'},
    {id:'buildingPermits',label:'Building Permits',unit:'',source:'Statistics Canada',statcan:true,prov:true,url:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601'}
  ]}
];

let _indExpData={},_indExpSel='cpi',_indExpRange=12,_indExpProv='national',_indExpProvOnly=false;
// Runtime-populated StatCan feed items grouped by category — merged into the explorer's
// single <select> menu so users see both INDICATOR_CATALOG key indicators and the full
// Statistics Canada Key Economic Indicators feed in one place.
let _statcanExplorerGroups=[];

function renderIndicatorExplorer(){
  const selItem=findIndItem(_indExpSel);
  // Dynamic chart header (sits inside the outer Statistics Canada card, beneath the indicator list)
  const title=selItem?selItem.label:'Select an indicator';
  const rangeLabel=_indExpRange===3?'last 3 months':_indExpRange===12?'last year':_indExpRange===36?'last 3 years':'last 5 years';
  const provContext=(selItem&&selItem.prov)?(_indExpProv==='national'?'National':(PROVS.find(p=>p.code===_indExpProv)||{}).name||_indExpProv):'';
  const deck=selItem?((provContext?provContext+' \u00B7 ':'')+rangeLabel):'';
  let selHtml='<div class="exp-explorer-section">';
  selHtml+='<div class="exp-chart-title">'+title+'</div>';
  selHtml+='<div class="exp-chart-deck">'+deck+'</div>';
  selHtml+='<div class="exp-control-row">';
  selHtml+='<select id="indExpSelect" class="exp-select exp-select-wide" onchange="onIndExpChange()">';
  // Key Economic Indicators first (curated). When provincial-only toggle is active, show
  // only items with prov:true (provincial breakdowns available).
  const _filterFn=(it)=>(_indExpProvOnly?it.prov===true:true);
  INDICATOR_CATALOG.forEach(g=>{
    const items=g.items.filter(_filterFn);
    if(!items.length)return;
    selHtml+='<optgroup label="'+g.group+'">';
    items.forEach(it=>{
      selHtml+='<option value="'+it.id+'"'+(it.id===_indExpSel?' selected':'')+'>'+it.label+'</option>';
    });
    selHtml+='</optgroup>';
  });
  // Then the full Statistics Canada Key Economic Indicators feed (~200 items)
  _statcanExplorerGroups.forEach(g=>{
    const items=(g.items||[]).filter(_filterFn);
    if(!items.length)return;
    selHtml+='<optgroup label="'+g.group+'">';
    items.forEach(it=>{
      selHtml+='<option value="'+it.id+'"'+(it.id===_indExpSel?' selected':'')+'>'+it.label+'</option>';
    });
    selHtml+='</optgroup>';
  });
  selHtml+='</select>';
  // Provincial-level toggle — filters the <select> to only indicators that have provincial breakdowns
  selHtml+='<label class="exp-toggle-switch" title="Show only indicators with provincial breakdowns"><input type="checkbox" id="indExpProvOnlyBtn" onchange="window._toggleIndExpProvOnly()"'+(_indExpProvOnly?' checked':'')+'><span class="exp-toggle-slider"></span><span class="exp-toggle-label">Available at provincial level</span></label>';
  // Province toggle (shown only for provincial indicators)
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
    selHtml+='<button class="exp-range-btn'+active+'" onclick="_indExpRange='+m+';renderIndicatorExplorer()">'+lbl+'</button>';
  });
  selHtml+='</div></div>';
  // Callout + chart
  selHtml+='<div id="indExpCallout"></div>';
  selHtml+='<div class="exp-chart-wrap"><canvas id="indExpCanvas"></canvas></div>';
  // Source line (italic, matches SVG editorial chart footer)
  if(selItem){
    const linkUrl=selItem.statcan?'https://www150.statcan.gc.ca/n1/en/type/data':selItem.url||'#';
    const linkLabel=selItem.statcan?'View on StatsCan \u2197':(selItem.source||'Source')+' \u2197';
    const sourceName=selItem.source||(selItem.statcan?'Statistics Canada':'');
    selHtml+='<div class="exp-card-source">Source: '+sourceName+' <a href="'+linkUrl+'" target="_blank" rel="noopener noreferrer">'+linkLabel+'</a></div>';
  }
  selHtml+='</div>';
  $('indicatorExplorer').innerHTML=selHtml;
  loadIndExpData();
}

function findIndItem(id){
  for(const g of INDICATOR_CATALOG)for(const it of g.items)if(it.id===id)return it;
  for(const g of _statcanExplorerGroups)for(const it of g.items)if(it.id===id)return it;
  return null;
}

window.onIndExpChange=function(){
  _indExpSel=$('indExpSelect').value;
  const provSel=$('indExpProv');
  _indExpProv=provSel?provSel.value:'national';
  renderIndicatorExplorer();
};

window._indExpSelectFromList=function(id){
  _indExpSel=id;
  renderIndicatorExplorer();
  const el=document.querySelector('#indicatorExplorer');
  if(el)el.scrollIntoView({behavior:'smooth',block:'start'});
};

window._toggleIndExpProvOnly=function(){
  _indExpProvOnly=!_indExpProvOnly;
  // If the currently selected indicator is no longer visible under the filter, fall back to
  // the first provincial-capable item so the chart doesn't go blank.
  if(_indExpProvOnly){
    const cur=findIndItem(_indExpSel);
    if(!cur||cur.prov!==true){
      let firstProv=null;
      for(const g of INDICATOR_CATALOG){const f=g.items.find(it=>it.prov===true);if(f){firstProv=f;break;}}
      if(!firstProv){
        for(const g of _statcanExplorerGroups){const f=(g.items||[]).find(it=>it.prov===true);if(f){firstProv=f;break;}}
      }
      if(firstProv)_indExpSel=firstProv.id;
    }
  }
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
  // Editorial chart — no event flags, no quartile band (matches editorial/callout no-flag rule)
  const chartCfg={type:'line',data:{labels,datasets:[{data,borderColor:'#003153',backgroundColor:'transparent',borderWidth:2.8,pointRadius:0,pointHoverRadius:5,pointBackgroundColor:'#003153',pointBorderColor:'#ffffff',pointBorderWidth:2,fill:false,tension:0.35}]},options:{responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:'index'},plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f172a',titleColor:'#cbd5e1',bodyColor:'#ffffff',padding:10,cornerRadius:4,titleFont:{family:'Inter',size:10,weight:'400'},bodyFont:{family:'Inter',size:13,weight:'700'},displayColors:false,callbacks:{label:function(ctx){
    const val=ctx.parsed.y;const idx=ctx.dataIndex;
    if(idx>0){const prev=data[idx-1];const diff=val-prev;return fmtNum(val)+'  '+(diff>=0?'+':'')+fmtNum(diff)+' vs prev';}
    return fmtNum(val);
  }}}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'Inter',size:11},color:'#4a5568'}},y:{position:'right',grid:{color:'#e8ecf0',lineWidth:1,drawBorder:false},ticks:{font:{family:'Inter',size:11},color:'#4a5568',callback:v=>fmtNum(v)}}}}};
  try{charts._indExp=new Chart(canvas,chartCfg);}catch(chartErr){console.error('Chart creation failed:',chartErr);}
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
      .style('font-size',d=>d.size+'px').style('font-family','Inter')
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
  const PROV_SHORT={ON:'ON',QC:'QC',AB:'AB',BC:'BC',SK:'SK',MB:'MB',NS:'NS',NB:'NB',NL:'NL',PE:'PE',YT:'YT',NT:'NT',NU:'NU'};
  // Build a vertical listbox rail: Provinces section + Territories section.
  function itemHtml(code){
    var selected=code===selectedProvince?' aria-selected="true"':' aria-selected="false"';
    var tabIndex=code===selectedProvince?'0':'-1';
    return '<li role="option" class="prov-rail-item" data-code="'+code+'"'+selected+' tabindex="'+tabIndex+'">'+
      '<span class="prov-rail-code">'+(PROV_SHORT[code]||code)+'</span>'+
      '<span class="prov-rail-name">'+PROV_NAMES[code]+'</span>'+
      '<span class="prov-rail-metric is-loading" data-metric="'+code+'">\u2014</span>'+
    '</li>';
  }
  var railHtml='<aside class="prov-rail" aria-label="Province selector">';
  railHtml+='<div class="prov-rail-head">Provinces<span class="prov-rail-head-count">'+PROV_ORDER.length+'</span></div>';
  railHtml+='<ul class="prov-rail-list" role="listbox" aria-label="Provinces" tabindex="0">';
  PROV_ORDER.forEach(function(code){railHtml+=itemHtml(code)});
  railHtml+='</ul>';
  railHtml+='<div class="prov-rail-head">Territories<span class="prov-rail-head-count">'+TERR_ORDER.length+'</span></div>';
  railHtml+='<ul class="prov-rail-list" role="listbox" aria-label="Territories" tabindex="0">';
  TERR_ORDER.forEach(function(code){railHtml+=itemHtml(code)});
  railHtml+='</ul>';
  railHtml+='</aside>';

  container.innerHTML='<div class="prov-page">'+railHtml+'<div class="prov-page-main" id="provMainContent"></div></div>';

  // Wire click + keyboard handlers across both lists
  var lists=container.querySelectorAll('.prov-rail-list');
  var allItems=Array.prototype.slice.call(container.querySelectorAll('.prov-rail-item'));
  function selectCode(code){
    if(!code||code===selectedProvince)return;
    selectedProvince=code;
    allItems.forEach(function(it){
      var on=it.getAttribute('data-code')===code;
      it.setAttribute('aria-selected',on?'true':'false');
      it.setAttribute('tabindex',on?'0':'-1');
    });
    _renderProvContent();
  }
  lists.forEach(function(list){
    list.addEventListener('click',function(e){
      var item=e.target.closest('.prov-rail-item');if(!item)return;
      selectCode(item.getAttribute('data-code'));
      item.focus();
    });
  });
  container.addEventListener('keydown',function(e){
    var item=e.target.closest('.prov-rail-item');if(!item)return;
    var idx=allItems.indexOf(item);if(idx<0)return;
    var next=null;
    if(e.key==='ArrowDown'||e.key==='ArrowRight'){next=allItems[Math.min(idx+1,allItems.length-1)];e.preventDefault()}
    else if(e.key==='ArrowUp'||e.key==='ArrowLeft'){next=allItems[Math.max(idx-1,0)];e.preventDefault()}
    else if(e.key==='Home'){next=allItems[0];e.preventDefault()}
    else if(e.key==='End'){next=allItems[allItems.length-1];e.preventDefault()}
    else if(e.key==='Enter'||e.key===' '){selectCode(item.getAttribute('data-code'));e.preventDefault();return}
    if(next){selectCode(next.getAttribute('data-code'));next.focus()}
  });

  _renderProvContent();
  _populateProvRailMetrics(container);
}

// Load projects_all.json once, count by province code, paint the count spans.
async function _populateProvRailMetrics(container){
  try{
    var all=await fetchJSON('projects_all.json');
    if(!Array.isArray(all))return;
    var counts={};
    for(var i=0;i<all.length;i++){
      var pc=(all[i].province||'').toUpperCase();
      if(!pc)continue;
      counts[pc]=(counts[pc]||0)+1;
    }
    container.querySelectorAll('.prov-rail-metric').forEach(function(el){
      var code=el.getAttribute('data-metric');
      var n=counts[code]||0;
      el.textContent=n>=1000?(n/1000).toFixed(1)+'k':String(n);
      el.classList.remove('is-loading');
      el.setAttribute('title',n.toLocaleString()+' tracked projects');
    });
  }catch(e){console.warn('prov rail metrics:',e)}
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
    // Priority 1: Compute from indicatorMeta.prev (briefing-level current vs prev)
    const meta=provMeta[metaKey]||{};
    const curVal=provInd[metaKey];
    if(meta.prev&&curVal){
      const c=parseFloat(String(curVal).replace(/[,%+$]/g,'')),p=parseFloat(String(meta.prev).replace(/[,%+$]/g,''));
      if(!isNaN(c)&&!isNaN(p)&&p!==0){
        const diff=c-p;
        // If value looks like a rate (%, pp), show as pp difference
        if(String(curVal).includes('%')||Math.abs(c)<100){
          return(diff>=0?'+':'')+diff.toFixed(1)+'pp';
        }
        // Otherwise show as % change
        return(diff>=0?'+':'')+((diff/Math.abs(p))*100).toFixed(1)+'%';
      }
    }
    // Priority 2: Compute from indicator_history current vs prior period
    const cc=computeChange(indName||metaKey,provName);
    if(hasVal(cc)&&!/^0(\.0+)?(%|pp|bp)?$/i.test(String(cc).replace(/^[+\-]/,'').trim()))return cc;
    // Priority 3: Use briefing meta.change (agent-written, least trusted — often "0.0pp" placeholder)
    const mc=meta.change;
    if(hasVal(mc)&&!/^[+\-]?0(\.0+)?(%|pp|bp)?$/i.test(String(mc).trim()))return mc;
    // Priority 4: Value fallback if it contains a percent
    const vf=valFallback&&/^[+-]?\d/.test(String(valFallback))&&String(valFallback).includes('%')?String(valFallback):'';
    // Last resort: return meta.change even if it's "0.0pp" (so rate indicators that genuinely didn't move still show)
    return pick(cc,mc,vf);
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

  // Helpers for indicator_history lookups (used in universalInds and enrichment)
  function _provHist(name){return indicators.find(x=>x.indicator_name===name&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code))||indicators.find(x=>x.indicator_name===provPrefix+'_'+name)||null}
  function _provHistVal(name){var r=_provHist(name);return r?r.value:null}
  function _provHistChg(name){
    var cur=_provHist(name),prev=_provHist(name+'_prev');
    if(!cur||!prev||!cur.value||!prev.value)return'';
    var c=parseFloat(String(cur.value).replace(/[,%$]/g,'')),p=parseFloat(String(prev.value).replace(/[,%$]/g,''));
    if(isNaN(c)||isNaN(p)||p===0)return'';
    if(String(cur.value).includes('%'))return(c-p).toFixed(1)+'pp';
    return(((c-p)/Math.abs(p))*100).toFixed(1)+'%';
  }
  function _fmtBig(v){if(!v)return null;var n=parseFloat(String(v).replace(/,/g,''));if(isNaN(n))return String(v);if(n>=1e9)return'$'+(n/1e9).toFixed(1)+'B';if(n>=1e6)return'$'+(n/1e6).toFixed(0)+'M';if(n>=1e3)return String(v).replace(/\B(?=(\d{3})+(?!\d))/g,',');return String(v)}
  // Format values already denominated in millions (StatCan convention)
  function _fmtMillions(v){if(v===null||v===undefined||v==='')return null;var n=parseFloat(String(v).replace(/,/g,''));if(isNaN(n))return String(v);if(Math.abs(n)>=1e6)return'$'+(n/1e6).toFixed(2)+'T';if(Math.abs(n)>=1e3)return'$'+(n/1e3).toFixed(1)+'B';if(Math.abs(n)>=1)return'$'+n.toFixed(0)+'M';return'$'+(n*1e3).toFixed(0)+'K'}
  // Format thousands of persons (employment)
  function _fmtPersons(v){if(!v)return null;var n=parseFloat(String(v).replace(/,/g,''));if(isNaN(n))return String(v);if(n>=1e3)return(n/1e3).toFixed(1)+'M persons';return n.toFixed(0)+'K persons'}
  // Latest period from most recent quarterly data
  var _latestQtr='Q3 2025';
  var _latestMon='Feb 2026';

  // Universal indicators
  const _prGdp=provIndRec('gdp'),_prUn=provIndRec('unemployment'),_prCpi=provIndRec('cpi'),_prPart=provIndRec('participationRate'),_prEmp=provIndRec('employmentRate'),_prHs=provIndRec('housingStarts'),_prWage=provIndRec('wageGrowth'),_prBp=provIndRec('buildingPermits');
  // CPI: use index level from briefing and compute MoM from prev
  var _cpiIdxVal=provInd.cpi||provIndVal('cpi');
  var _cpiMetaObj=provMeta.cpi||{};
  var _cpiPrevIdx=_cpiMetaObj.prev;
  var _cpiLabel='CPI Index',_cpiVal=_cpiIdxVal;
  var _cpiMoMChg='';
  if(_cpiIdxVal&&_cpiPrevIdx){
    var ci=parseFloat(String(_cpiIdxVal).replace(/[,%]/g,'')),cp=parseFloat(String(_cpiPrevIdx).replace(/[,%]/g,''));
    if(!isNaN(ci)&&!isNaN(cp)&&cp>0){
      var mom=((ci-cp)/cp*100);
      _cpiMoMChg=(mom>=0?'+':'')+mom.toFixed(1)+'% M/M';
    }
  }
  // Pull Housing Starts real numeric value from indicator_history
  var _hsHistRec=indicators.find(x=>x.indicator_name==='housingStarts'&&(x.province||'').toLowerCase()===provName.toLowerCase());
  var _hsHistVal=_hsHistRec?_hsHistRec.value:null;
  var _hsHistPrev=indicators.find(x=>x.indicator_name==='housingStarts_prev'&&(x.province||'').toLowerCase()===provName.toLowerCase());
  var _hsHistChg='';
  if(_hsHistVal&&_hsHistPrev&&_hsHistPrev.value){var hn=parseFloat(String(_hsHistVal).replace(/,/g,'')),hp=parseFloat(String(_hsHistPrev.value).replace(/,/g,''));if(hp>0)_hsHistChg=(((hn-hp)/hp)*100).toFixed(1)+'%'}
  var _hsFinalVal=_hsHistVal?String(_hsHistVal).replace(/\B(?=(\d{3})+(?!\d))/g,','):null;
  // Fall back to briefing value only if numeric
  if(!_hsFinalVal){var _hsRaw=pick(provInd.housingStarts,provIndVal('housingStarts'));if(_hsRaw&&!/^(up|down|fell|rose|declined)/i.test(String(_hsRaw)))_hsFinalVal=_hsRaw}
  const universalInds=[
    // ── GDP Group ──
    (function(){
      // Prefer quarterly provincial real GDP QoQ (from OEA Table 3 row 43 or equivalent per-province source)
      var qoqRec=indicators.find(x=>(x.indicator_name===provPrefix+'_real_gdp_pct'||x.indicator_name==='real_gdp_qoq')&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
      if(qoqRec){
        var qPer=qoqRec.period?('Q'+Math.ceil((parseInt(qoqRec.period.substring(5,7)))/3)+' '+qoqRec.period.substring(0,4)):'';
        var qVal=String(qoqRec.value);
        if(!qVal.includes('%'))qVal=(parseFloat(qVal)>=0?'+':'')+qVal+'%';
        var qSrc=code==='ON'?'Ontario Economic Accounts':code==='QC'?'Institut de la statistique du Québec':code==='BC'?'BC Stats Economic Accounts':code==='AB'?'Alberta Economic Accounts':'Provincial Economic Accounts';
        return{label:'Real GDP Growth (QoQ)',freq:'Quarterly',value:qVal,change:'QoQ',period:qPer,source:qSrc};
      }
      return{label:'GDP Growth (Real, YoY)',freq:'Annual',value:pick(provInd.gdp,provIndVal('gdp')),change:'YoY',period:'2024',source:'StatCan 36-10-0402'};
    })(),
    {label:'Provincial GDP',freq:'Annual',value:(function(){var r=indicators.find(x=>x.indicator_name==='gdp'&&(x.province||'').toUpperCase()===code&&parseFloat(String(x.value).replace(/,/g,''))>1000);return r?_fmtMillions(r.value):null})(),change:pick(provInd.gdp,provIndVal('gdp')),period:(function(){var r=indicators.find(x=>x.indicator_name==='gdp_date'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));return r?r.value:'2024'})(),source:'StatCan 36-10-0402'},
    {label:'GDP Goods-Producing',freq:'Quarterly',value:_fmtMillions(_provHistVal(provPrefix+'_gdp_goods')),change:_provHistVal(provPrefix+'_gdp_goods_pct')?'+'+_provHistVal(provPrefix+'_gdp_goods_pct')+'%':'',period:_latestQtr,source:'StatCan 36-10-0402'},
    (function(){var tg=indicators.find(x=>x.indicator_name==='gdp'&&(x.province||'').toUpperCase()===code&&parseFloat(String(x.value).replace(/,/g,''))>1000);var gg=_provHistVal(provPrefix+'_gdp_goods');if(!tg||!gg)return{label:'GDP Services-Producing',freq:'Quarterly',value:null};var sg=parseFloat(String(tg.value).replace(/,/g,''))-parseFloat(String(gg).replace(/,/g,''));var totalPct=pick(provInd.gdp,provIndVal('gdp'));var goodsPct=_provHistVal(provPrefix+'_gdp_goods_pct');var svcChg='';if(totalPct&&goodsPct){var t=parseFloat(String(totalPct).replace(/[+%]/g,'')),g=parseFloat(String(goodsPct).replace(/[+%]/g,''));if(!isNaN(t)&&!isNaN(g)){var gShare=parseFloat(String(gg).replace(/,/g,''))/parseFloat(String(tg.value).replace(/,/g,''));var sShare=1-gShare;var sChg=(t-g*gShare)/sShare;svcChg=(sChg>=0?'+':'')+sChg.toFixed(1)+'%'}}return{label:'GDP Services-Producing',freq:'Quarterly',value:_fmtMillions(String(sg)),change:svcChg,period:_latestQtr,source:'StatCan 36-10-0402'}})(),
    // ── Labour Group ──
    {label:'Unemployment Rate',freq:'Monthly',value:pick(provInd.unemployment,provIndVal('unemployment')),change:pchg('unemployment','unemployment',provInd.unemployment),period:indBasis(_prUn,(provMeta.unemployment||{}).period,'monthly'),source:'StatCan 14-10-0287'},
    {label:'Employment Rate',freq:'Monthly',value:pick(provInd.employmentRate,provIndVal('employmentRate')),change:pchg('employmentRate','employmentRate',provInd.employmentRate),period:indBasis(_prEmp,(provMeta.employmentRate||{}).period,'monthly'),source:'StatCan 14-10-0287'},
    {label:'Participation Rate',freq:'Monthly',value:pick(provInd.participationRate,provIndVal('participationRate')),change:pchg('participationRate','participationRate',provInd.participationRate),period:indBasis(_prPart,(provMeta.participationRate||{}).period,'monthly'),source:'StatCan 14-10-0287'},
    (function(){
      var wRec=indicators.find(x=>x.indicator_name==='avg_hourly_wage'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
      if(!wRec)return{label:'Average Hourly Wage',freq:'Monthly',value:null,change:'',period:'',source:'StatCan 14-10-0063'};
      var wVal='$'+parseFloat(wRec.value).toFixed(2)+'/hr';
      var wChg=wRec.change||'';
      if(!wChg&&wRec.previous_value){var w1=parseFloat(wRec.value),w2=parseFloat(wRec.previous_value);if(w2>0)wChg=(w1>=w2?'+':'')+(((w1-w2)/w2*100).toFixed(1))+'%'}
      var wPer=wRec.period?fmtDate(wRec.period):_latestMon;
      return{label:'Average Hourly Wage',freq:'Monthly',value:wVal,change:wChg,period:wPer,source:'StatCan 14-10-0063'};
    })(),
    // ── Prices Group ──
    {label:'CPI Index',freq:'Monthly',value:_cpiVal,change:_cpiMoMChg,period:indBasis(_prCpi,(provMeta.cpi||{}).period,'monthly'),source:'StatCan 18-10-0004'},
    // ── Housing & Investment Group ──
    {label:'Housing Starts',freq:'Monthly',value:_hsFinalVal,change:pick(_hsHistChg,pchg('housingStarts','housingStarts')),period:indBasis(_prHs,(provMeta.housingStarts||{}).period,'monthly'),source:'CMHC'},
    // Building Permits: sum of residential + non-residential from StatCan 34-10-0292 ($K)
    (function(){
      var resRec=indicators.find(x=>x.indicator_name==='bldg_permits_res'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
      var nonRec=indicators.find(x=>x.indicator_name==='bldg_permits_nonres'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
      if(!resRec&&!nonRec)return{label:'Building Permits',freq:'Monthly',value:pick(provInd.buildingPermits,provIndVal('buildingPermits')),change:pchg('buildingPermits','buildingPermits'),period:indBasis(_prBp,(provMeta.buildingPermits||{}).period,'monthly'),source:'StatCan 34-10-0292'};
      var total=(resRec?parseFloat(resRec.value):0)+(nonRec?parseFloat(nonRec.value):0);
      var prev=(resRec&&resRec.previous_value?parseFloat(resRec.previous_value):0)+(nonRec&&nonRec.previous_value?parseFloat(nonRec.previous_value):0);
      var chg='';
      if(prev>0){var d=((total-prev)/prev*100);chg=(d>=0?'+':'')+d.toFixed(1)+'%'}
      var per=resRec?fmtDate(resRec.period):_latestMon;
      return{label:'Building Permits',freq:'Monthly',value:_fmtMillions(String(total/1000)),change:chg,period:per,source:'StatCan 34-10-0292'};
    })(),
    {label:'Capital Investment',freq:'Quarterly',value:_fmtMillions(_provHistVal(provPrefix+'_real_capital_investment')),change:_provHistVal(provPrefix+'_capital_investment_pct')?'+'+_provHistVal(provPrefix+'_capital_investment_pct')+'%':'',period:_latestQtr,source:'StatCan 36-10-0104'},
    // ── Trade Group ──
    (function(){var te=_provHistVal(provPrefix+'_exports'),ti=_provHistVal(provPrefix+'_imports');if(!te||!ti)return{label:'Trade Balance',freq:'Quarterly',value:null};var teF=parseFloat(String(te).replace(/,/g,'')),tiF=parseFloat(String(ti).replace(/,/g,''));var n=teF-tiF;var exP=_provHistVal(provPrefix+'_exports_pct'),imP=_provHistVal(provPrefix+'_imports_pct');var chg='';if(exP&&imP){var prevExp=teF/(1+parseFloat(exP)/100),prevImp=tiF/(1+parseFloat(imP)/100);var prevBal=prevExp-prevImp;var delta=n-prevBal;chg=(delta>=0?'+':'')+_fmtMillions(String(Math.round(delta)))+' Q/Q'}return{label:'Trade Balance',freq:'Quarterly',value:_fmtMillions(String(Math.round(n))),change:chg,period:_latestQtr,source:'StatCan 12-10-0121'}})()
  ];

  // Reuse _natIndTable for consistent styling across National and Provinces tabs

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

  // Section 1: Provincial Analysis (includes consumer pulse only; sector highlights goes to Sector Signals)
  const provContent=provData.analysis||'';
  const cpNarrative=provData.consumerPulse||'';
  const shNarrative=provData.sectorHighlights||'';
  // Auto-wrap first sentence of each <p> in lead-sentence span with em dash
  function addLeads(htmlStr){
    return _editorialProse(htmlStr);  // Demo-style lead-in + strip scattered inline bold (unified)
  }
  const allSrc=provSources.length?provSources:(D&&D.sources||[]);
  html+='<div class="section-block">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Provincial Analysis</h3></div>';
  if(provContent||cpNarrative){
    let narrativeHtml='';
    if(provContent)narrativeHtml+=san(linkFootnotes(provContent,allSrc));
    if(cpNarrative&&cpNarrative.length>=20)narrativeHtml+=addLeads(linkFootnotes(cpNarrative,allSrc));
    // Note: sectorHighlights is rendered in the Sector Signals section, not here
    html+='<div class="narrative">'+narrativeHtml+'</div>';
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
  const genDate=D&&D.generated_at?D.generated_at.split('T')[0]:'';
  // Filter to only show indicators with actual values
  const filteredInds=universalInds.filter(r=>hasVal(r.value)&&r.value!=='N/A');
  const filteredSpec=specIndData.filter(r=>hasVal(r.value)&&r.value!=='N/A');
  const indCount=filteredInds.length+filteredSpec.length;
  html+='<div class="section-block">';
  html+='<div class="section-header"><div class="accent-bar"></div><h3>Key Indicators \u2014 '+san(provName)+'</h3>';
  html+='<span class="section-meta">'+indCount+' indicators'+(genDate?' &middot; Updated '+genDate:'')+'</span></div>';
  html+=_natIndTable('',san(provName)+' \u2014 Key Indicators',filteredInds,'');
  if(filteredSpec.length){
    html+=_natIndTable('',san(provName)+' \u2014 Sector Indicators',filteredSpec,'');
  }
  // Enrichment tables — 4 panels, province data from indicator_history

  // Enrichment tables — stacked full-width collapsible dropdowns
  function _enrichDropdown(title,rows,chgLabel){
    if(!rows.length)return'';
    var h='<details class="prov-enrich-detail"><summary>'+san(title)+' <span class="prov-enrich-count">'+rows.length+'</span></summary>';
    h+=_natIndTable('','',rows,'',chgLabel);
    h+='</details>';
    return h;
  }

  var labourEnrich=[
    {label:'Unemployment Rate',value:pick(provInd.unemployment,provIndVal('unemployment')),change:pchg('unemployment','unemployment',provInd.unemployment),freq:'Monthly',source:'StatCan 14-10-0287',period:indBasis(_prUn,(provMeta.unemployment||{}).period,'monthly')},
    {label:'Employment Rate',value:pick(provInd.employmentRate,provIndVal('employmentRate')),change:pchg('employmentRate','employmentRate',provInd.employmentRate),freq:'Monthly',source:'StatCan 14-10-0287',period:indBasis(_prEmp,(provMeta.employmentRate||{}).period,'monthly')},
    {label:'Participation Rate',value:pick(provInd.participationRate,provIndVal('participationRate')),change:pchg('participationRate','participationRate',provInd.participationRate),freq:'Monthly',source:'StatCan 14-10-0287',period:indBasis(_prPart,(provMeta.participationRate||{}).period,'monthly')},
    (function(){
      var wRec=indicators.find(x=>x.indicator_name==='avg_hourly_wage'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
      if(!wRec)return{label:'Average Hourly Wage',value:null,change:'',freq:'Monthly',source:'StatCan 14-10-0063',period:''};
      var wVal='$'+parseFloat(wRec.value).toFixed(2)+'/hr';
      var wChg=wRec.change||'';
      if(!wChg&&wRec.previous_value){var w1=parseFloat(wRec.value),w2=parseFloat(wRec.previous_value);if(w2>0)wChg=(w1>=w2?'+':'')+(((w1-w2)/w2*100).toFixed(1))+'%'}
      var wPer=wRec.period?fmtDate(wRec.period):_latestMon;
      return{label:'Average Hourly Wage',value:wVal,change:wChg,freq:'Monthly',source:'StatCan 14-10-0063',period:wPer};
    })()
  ].filter(r=>hasVal(r.value));
  // Household debt-service ratio and savings ratio
  // Try provincial first, then fall back to national (these metrics are typically national-only from StatCan)
  var _dsrRec=indicators.find(x=>(x.indicator_name==='household_debt_service_ratio'||x.indicator_name==='dsr'||x.indicator_name==='household_dsr')&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code))
    ||indicators.find(x=>x.indicator_name==='household_debt_service_ratio'||x.indicator_name==='dsr'||x.indicator_name==='household_dsr');
  var _savRec=indicators.find(x=>(x.indicator_name==='household_savings_ratio'||x.indicator_name==='savings_rate'||x.indicator_name==='household_savings_rate')&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code))
    ||indicators.find(x=>x.indicator_name==='household_savings_ratio'||x.indicator_name==='savings_rate'||x.indicator_name==='household_savings_rate');
  var _hhRaw=_provHistVal(provPrefix+'_real_household'),_hhPct=_provHistVal(provPrefix+'_household_pct');
  var _consRaw=_provHistVal(provPrefix+'_real_consumption'),_consPct=_provHistVal(provPrefix+'_consumption_pct');
  // Household disposable income, DSR, savings rate — Table 36-10-0226 (annual)
  var _hhDispRec=indicators.find(x=>x.indicator_name==='household_disposable_income'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
  var _dsrPer=_dsrRec&&_dsrRec.period?_dsrRec.period.substring(0,4):'2024';
  var _savPer=_savRec&&_savRec.period?_savRec.period.substring(0,4):'2024';
  var _hhDispPer=_hhDispRec&&_hhDispRec.period?_hhDispRec.period.substring(0,4):'2024';
  var cpEnrich=[
    {label:'CPI Index',value:_cpiVal,change:_cpiMoMChg,freq:'Monthly',source:'StatCan 18-10-0004',period:indBasis(_prCpi,(provMeta.cpi||{}).period,'monthly')},
    {label:'Real Household Final Consumption',value:_fmtMillions(_hhRaw),change:_hhPct?(parseFloat(_hhPct)>=0?'+':'')+_hhPct+'%':'',freq:'Quarterly',source:'StatCan 36-10-0222',period:_latestQtr},
    {label:'Total Consumption Expenditure',value:_fmtMillions(_consRaw),change:_consPct?(parseFloat(_consPct)>=0?'+':'')+_consPct+'%':'',freq:'Quarterly',source:'StatCan 36-10-0222',period:_latestQtr},
    {label:'Household Disposable Income',value:_hhDispRec?_fmtMillions(_hhDispRec.value):null,change:_hhDispRec?_hhDispRec.change:'',freq:'Annual',source:'StatCan 36-10-0226',period:_hhDispPer},
    {label:'Debt-Service Ratio',value:_dsrRec?parseFloat(_dsrRec.value).toFixed(2)+'%':null,change:_dsrRec?_dsrRec.change:'',freq:'Annual',source:'StatCan 36-10-0226',period:_dsrPer},
    {label:'Savings Rate',value:_savRec?parseFloat(_savRec.value).toFixed(1)+'%':null,change:_savRec?_savRec.change:'',freq:'Annual',source:'StatCan 36-10-0226',period:_savPer}
  ].filter(r=>hasVal(r.value));
  // Province-level building permits — pulled from indicator_history (StatCan 34-10-0292, $K SAAR)
  var _bpResRec=indicators.find(x=>x.indicator_name==='bldg_permits_res'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
  var _bpNonresRec=indicators.find(x=>x.indicator_name==='bldg_permits_nonres'&&((x.province||'').toLowerCase()===provName.toLowerCase()||(x.province||'').toUpperCase()===code));
  // Convert $K to $M for display
  var _bpResVal=_bpResRec?(parseFloat(_bpResRec.value)/1000).toString():null;
  var _bpNonresVal=_bpNonresRec?(parseFloat(_bpNonresRec.value)/1000).toString():null;
  var _bpResChg=_bpResRec?_bpResRec.change:'';
  var _bpNonresChg=_bpNonresRec?_bpNonresRec.change:'';
  var _bpResPer=_bpResRec?fmtDate(_bpResRec.period):_latestMon;
  var _bpNonresPer=_bpNonresRec?fmtDate(_bpNonresRec.period):_latestMon;
  var _capInvPct=_provHistVal(provPrefix+'_capital_investment_pct');
  var housingEnrich=[
    {label:'Housing Starts',value:_hsFinalVal,change:pick(_hsHistChg,pchg('housingStarts','housingStarts')),freq:'Monthly',source:'CMHC',period:indBasis(_prHs,(provMeta.housingStarts||{}).period,'monthly')},
    {label:'Building Permits (Residential)',value:_fmtMillions(_bpResVal),change:_bpResChg,freq:'Monthly',source:'StatCan 34-10-0292',period:_bpResPer},
    {label:'Building Permits (Non-Residential)',value:_fmtMillions(_bpNonresVal),change:_bpNonresChg,freq:'Monthly',source:'StatCan 34-10-0292',period:_bpNonresPer},
    {label:'Capital Investment',value:_fmtMillions(_provHistVal(provPrefix+'_real_capital_investment')),change:_capInvPct?(parseFloat(_capInvPct)>=0?'+':'')+_capInvPct+'%':'',freq:'Quarterly',source:'StatCan 36-10-0104',period:_latestQtr}
  ].filter(r=>hasVal(r.value));
  var _expPct=_provHistVal(provPrefix+'_exports_pct'),_impPct=_provHistVal(provPrefix+'_imports_pct'),_govPct=_provHistVal(provPrefix+'_gov_expenditure_pct');
  var tradeEnrich=[
    {label:'Merchandise Exports',value:_fmtMillions(_provHistVal(provPrefix+'_exports')),change:_expPct?(parseFloat(_expPct)>=0?'+':'')+_expPct+'%':'',freq:'Quarterly',source:'StatCan 12-10-0121',period:_latestQtr},
    {label:'Merchandise Imports',value:_fmtMillions(_provHistVal(provPrefix+'_imports')),change:_impPct?(parseFloat(_impPct)>=0?'+':'')+_impPct+'%':'',freq:'Quarterly',source:'StatCan 12-10-0121',period:_latestQtr},
    {label:'Government Expenditure',value:_fmtMillions(_provHistVal(provPrefix+'_real_gov_expenditure')),change:_govPct?(parseFloat(_govPct)>=0?'+':'')+_govPct+'%':'',freq:'Quarterly',source:'StatCan 36-10-0222',period:_latestQtr}
  ].filter(r=>hasVal(r.value));

  html+=_enrichDropdown('Labour Market',labourEnrich,'Change (M/M)');
  html+=_enrichDropdown('Consumer Pulse',cpEnrich,'Change');
  html+=_enrichDropdown('Housing & Construction',housingEnrich,'Change');
  html+=_enrichDropdown('Trade & Economy',tradeEnrich,'Change (Q/Q)');

  html+='</div>';

  // Section 4: Sector Signals — news-based narrative from briefing writer (sectorHighlights)
  if(shNarrative&&shNarrative.length>=20){
    var _sectorParaCount=(shNarrative.match(/<p>/g)||[]).length;
    html+='<div class="section-block">';
    html+='<div class="section-header"><div class="accent-bar"></div><h3>Sector Signals</h3>';
    html+='<span class="section-meta">'+_sectorParaCount+' sector update'+(_sectorParaCount===1?'':'s')+'</span></div>';
    html+='<div class="narrative">'+addLeads(linkFootnotes(shNarrative,allSrc))+'</div></div>';
  }

  // Labour Market Detail — render labourDeepDive HTML if present
  var _labourDeep=provData.labourDeepDive||'';
  if(_labourDeep&&_labourDeep.length>=20){
    html+='<div class="section-block">';
    html+='<div class="section-header"><div class="accent-bar"></div><h3>Labour Market Detail</h3></div>';
    html+='<div class="narrative">'+san(linkFootnotes(_labourDeep,allSrc))+'</div></div>';
  }

  // Section 5: Projects Preview
  // Filter by province threshold, new projects first with NEW tag
  const thresholdProj=provProj.filter(meetsThreshold);
  const newFiltered=newThisWeek.filter(meetsThreshold);
  const existingFiltered=thresholdProj.filter(p=>!newFiltered.includes(p));
  newFiltered.sort((a,b)=>parseNumericValue(b.value)-parseNumericValue(a.value));
  existingFiltered.sort((a,b)=>parseNumericValue(b.value)-parseNumericValue(a.value));
  let displayProj=[...newFiltered.slice(0,4),...existingFiltered.slice(0,8-Math.min(newFiltered.length,4))].slice(0,8);

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
    html+='<th>Project</th><th>Sector</th><th>Value</th><th>Status</th>';
    html+='</tr></thead><tbody>';
    displayProj.forEach(p=>{
      const pStatus=p.status||'Proposed';
      const stClass=pStatus.toLowerCase().includes('construct')?'status-construction':pStatus.toLowerCase().includes('pre')?'status-pre':pStatus.toLowerCase().includes('review')?'status-review':'status-proposed';
      const isNewProj=newFiltered.includes(p);
      const newTag=isNewProj?' <span class="tldr-freq-tag" style="background:#003153;color:#fff;margin-left:6px">NEW</span>':'';
      html+='<tr><td style="font-weight:500">'+san((p.name||'').substring(0,60))+newTag+'</td>';
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

  // Post-render: insight charts — render every spec in the insightCharts array.
  var _icArr=(provData.insightCharts||[]).filter(function(s){return s&&s.dataKeys&&s.dataKeys.length});
  if(!_icArr.length&&provData.insightChart&&provData.insightChart.dataKeys&&provData.insightChart.dataKeys.length)_icArr=[provData.insightChart];
  const provThemes=extractAnalysisThemes(provContent,provProj);
  const chartArea=$('provInsightChartArea');
  if(chartArea){
    if(_icArr.length){
      chartArea.innerHTML=_icArr.map(function(s,i){return buildAgentInsightStrip('prov'+i,s,provData)}).join('');
    }else{
      chartArea.innerHTML=buildInsightStrip('prov',provThemes,code);
    }
  }

  await _ensureChartData();
  if(_icArr.length){
    for(var ci=0;ci<_icArr.length;ci++){
      await renderAgentInsightChart('prov'+ci,_icArr[ci],code);
    }
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
      // Dedup by title
      const seenTitles=new Set();
      const dedupedItems=provItems.filter(a=>{const t=(a.title||a.headline||'').toLowerCase().trim();if(seenTitles.has(t))return false;seenTitles.add(t);return true});
      if(dedupedItems.length){
        dedupedItems.sort((a,b)=>{
          const aLocal=(a.province||'').toUpperCase()===code.toUpperCase()?0:1;
          const bLocal=(b.province||'').toUpperCase()===code.toUpperCase()?0:1;
          return aLocal-bLocal;
        });
        const provSpecific=dedupedItems.filter(a=>(a.province||'').toUpperCase()===code.toUpperCase()).length;
        const fedCount=dedupedItems.length-provSpecific;
        if(policyMetaEl){
          policyMetaEl.textContent=(provSpecific?provSpecific+' provincial':'')+(provSpecific&&fedCount?' + ':'')+
            (fedCount?fedCount+' federal':'')+(dedupedItems.length?' developments':'');
        }
        // Render as accordion
        let polHtml='<div class="inner-card">';
        dedupedItems.slice(0,8).forEach(a=>{
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
        const polSources=dedupedItems.slice(0,8).filter(a=>a.url).map(a=>({url:a.url,title:a.source_description||a.source||a.title||'Source'}));
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
let selectedIndustry='11';
const IND_SHORT={'11':'AG','21':'MIN','22':'UTL','23':'CON','31-33':'MFG','41':'WT','44-45':'RT','48-49':'TRN','51':'INF','52':'FIN','53':'RE','54':'PRO','55':'MCE','56':'ADM','61':'EDU','62':'HC','71':'AE','72':'AFS','81':'OSE','91':'PA'};

function renderIndustries(){
  var container=$('industriesPage');if(!container)return;
  var goodsArr=(D&&D.goodsIndustries)||[];
  var servArr=(D&&D.servicesIndustries)||[];
  if(!goodsArr.length)['11','21','22','23','31-33'].forEach(function(code){goodsArr.push({code:code,name:NAICS_NAMES[code]})});
  if(!servArr.length)['41','44-45','48-49','51','52','53','54','55','56','61','62','71','72','81','91'].forEach(function(code){servArr.push({code:code,name:NAICS_NAMES[code]})});

  // Format an m/m GDP delta string into a {text, cls} pair for the rail metric.
  function fmtMm(raw){
    var s=String(raw==null?'':raw).trim();
    if(!s)return{text:'\u2014',cls:'m-flat'};
    var v=parseFloat(s.replace('%',''));
    if(isNaN(v))return{text:'\u2014',cls:'m-flat'};
    var cls=v>0.02?'m-up':(v<-0.02?'m-down':'m-flat');
    var signed=(v>=0?'+':'')+v.toFixed(1)+'%';
    return{text:signed,cls:cls};
  }

  function itemHtml(s){
    var selected=s.code===selectedIndustry?' aria-selected="true"':' aria-selected="false"';
    var tabIndex=s.code===selectedIndustry?'0':'-1';
    var m=fmtMm(s.mm);
    return '<li role="option" class="ind-rail-item" data-code="'+s.code+'"'+selected+' tabindex="'+tabIndex+'">'+
      '<span class="ind-rail-code">'+san(s.code)+'</span>'+
      '<span class="ind-rail-name">'+san(s.name||'')+'</span>'+
      '<span class="ind-rail-metric '+m.cls+'" title="Month-over-month real GDP change">'+m.text+'</span>'+
    '</li>';
  }

  var railHtml='<aside class="ind-rail" aria-label="Industry selector">';
  railHtml+='<div class="ind-rail-head">Goods-producing<span class="ind-rail-head-count">'+goodsArr.length+'</span></div>';
  railHtml+='<ul class="ind-rail-list" role="listbox" aria-label="Goods-producing industries" tabindex="0">';
  goodsArr.forEach(function(s){railHtml+=itemHtml(s)});
  railHtml+='</ul>';
  railHtml+='<div class="ind-rail-head">Services-producing<span class="ind-rail-head-count">'+servArr.length+'</span></div>';
  railHtml+='<ul class="ind-rail-list" role="listbox" aria-label="Services-producing industries" tabindex="0">';
  servArr.forEach(function(s){railHtml+=itemHtml(s)});
  railHtml+='</ul>';
  railHtml+='</aside>';

  container.innerHTML='<div class="ind-page">'+railHtml+'<div class="ind-page-main" id="indMainContent"></div></div>';

  var allItems=Array.prototype.slice.call(container.querySelectorAll('.ind-rail-item'));
  function selectCode(code){
    if(!code||code===selectedIndustry)return;
    selectedIndustry=code;
    allItems.forEach(function(it){
      var on=it.getAttribute('data-code')===code;
      it.setAttribute('aria-selected',on?'true':'false');
      it.setAttribute('tabindex',on?'0':'-1');
    });
    _renderIndContent();
  }
  container.querySelectorAll('.ind-rail-list').forEach(function(list){
    list.addEventListener('click',function(e){
      var item=e.target.closest('.ind-rail-item');if(!item)return;
      selectCode(item.getAttribute('data-code'));
      item.focus();
    });
  });
  container.addEventListener('keydown',function(e){
    var item=e.target.closest('.ind-rail-item');if(!item)return;
    var idx=allItems.indexOf(item);if(idx<0)return;
    var next=null;
    if(e.key==='ArrowDown'||e.key==='ArrowRight'){next=allItems[Math.min(idx+1,allItems.length-1)];e.preventDefault()}
    else if(e.key==='ArrowUp'||e.key==='ArrowLeft'){next=allItems[Math.max(idx-1,0)];e.preventDefault()}
    else if(e.key==='Home'){next=allItems[0];e.preventDefault()}
    else if(e.key==='End'){next=allItems[allItems.length-1];e.preventDefault()}
    else if(e.key==='Enter'||e.key===' '){selectCode(item.getAttribute('data-code'));e.preventDefault();return}
    if(next){selectCode(next.getAttribute('data-code'));next.focus()}
  });

  _renderIndContent();
}

// ==== Industry Key Indicators mapping ====
// Per-NAICS list of the most relevant indicator rows for the Key Indicators table.
// Each entry: {label, key, source:'indicators'|'timeseries', unit, srcLabel, srcUrl}
// Universal rows (Real GDP M/M, Y/Y, Active Projects, Pipeline Value) are added by the renderer.
const STATCAN_GDP_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401';
const STATCAN_LFS_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201';
const STATCAN_BLDINV_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410017501';
const STATCAN_HSTARTS_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410014301';
const STATCAN_NHPI_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810020501';
const STATCAN_CPI_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401';
const STATCAN_HH_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022601';
const STATCAN_EXPORTS_URL='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1210001101';
const BOC_RATE_URL='https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/';
const BOC_BONDS_URL='https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/';
const IND_KEY_INDICATORS={
  '11':[
    // Sector top-line / trade (StatCan)
    {label:'Farm Cash Receipts',key:'farm_cash_receipts',source:'indicators',unit:'$M',freq:'Quarterly',srcLabel:'StatCan 32-10-0046',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210004601'},
    {label:'Agriculture Exports',key:'ag_exports_current',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 12-10-0176',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1210017601'},
    // Labour (StatCan)
    {label:'Agriculture Employment',key:'ag_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410002201'},
    {label:'Avg Hourly Wage, Agriculture',key:'ag_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // Crop commodity prices (timeseries)
    {label:'Wheat',key:'wheat',source:'timeseries',unit:'USD/bu',srcLabel:'CME Group',srcUrl:'https://www.cmegroup.com/markets/agriculture/grains/wheat.html'},
    {label:'Corn',key:'corn',source:'timeseries',unit:'USD/bu',srcLabel:'CME Group',srcUrl:'https://www.cmegroup.com/markets/agriculture/grains/corn.html'},
    {label:'Soybeans',key:'soybeans',source:'timeseries',unit:'USD/bu',srcLabel:'CME Group',srcUrl:'https://www.cmegroup.com/markets/agriculture/grains/soybean.html'},
    {label:'Canola (Saskatchewan)',key:'canola',source:'timeseries',unit:'CAD/tonne',freq:'Monthly',srcLabel:'StatCan 32-10-0077',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3210007701'},
    // Livestock prices (timeseries)
    {label:'Live Cattle',key:'live_cattle',source:'timeseries',unit:'USD/lb',srcLabel:'Yahoo Finance (LE=F)',srcUrl:'https://finance.yahoo.com/quote/LE=F/'},
    {label:'Lean Hogs',key:'lean_hogs',source:'timeseries',unit:'USD/lb',srcLabel:'Yahoo Finance (HE=F)',srcUrl:'https://finance.yahoo.com/quote/HE=F/'},
    // Input costs (StatCan + timeseries)
    {label:'Fertilizer Price Index',key:'fertilizer_price_index',source:'indicators',unit:'index',freq:'Quarterly',srcLabel:'StatCan 18-10-0258',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810025801'},
    {label:'Farm Input Price Index',key:'farm_input_price_index',source:'indicators',unit:'index',freq:'Quarterly',srcLabel:'StatCan 18-10-0258',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810025801'},
    {label:'Potash (Nutrien stock)',key:'potash_nutrien',source:'timeseries',unit:'USD',srcLabel:'Yahoo Finance (NTR)',srcUrl:'https://finance.yahoo.com/quote/NTR/'},
    // Growing conditions (ECCC)
    {label:'2025 Growing Season GDD (Prairie Avg)',key:'ag_gdd_prairie_2025',source:'indicators',unit:'gdd',freq:'Annual',chgLabel:'vs 2024',srcLabel:'Environment and Climate Change Canada',srcUrl:'https://climate.weather.gc.ca/'}
  ],
  '21':[
    // Energy commodities
    {label:'WTI Crude',key:'wti',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (CL=F)',srcUrl:'https://finance.yahoo.com/quote/CL=F/'},
    {label:'Brent Crude',key:'brent',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (BZ=F)',srcUrl:'https://finance.yahoo.com/quote/BZ=F/'},
    {label:'Natural Gas',key:'natural_gas',source:'timeseries',unit:'USD/MMBtu',srcLabel:'Yahoo Finance (NG=F)',srcUrl:'https://finance.yahoo.com/quote/NG=F/'},
    {label:'LNG (Asia JKM)',key:'lng_asia',source:'timeseries',unit:'USD/MMBtu',srcLabel:'S&P Platts JKM',srcUrl:''},
    // Precious metals
    {label:'Gold',key:'gold',source:'timeseries',unit:'USD/oz',srcLabel:'Yahoo Finance (GC=F)',srcUrl:'https://finance.yahoo.com/quote/GC=F/'},
    {label:'Silver',key:'silver',source:'timeseries',unit:'USD/oz',srcLabel:'Yahoo Finance (SI=F)',srcUrl:'https://finance.yahoo.com/quote/SI=F/'},
    // Base & industrial metals
    {label:'Copper',key:'copper',source:'timeseries',unit:'USD/lb',srcLabel:'Yahoo Finance (HG=F)',srcUrl:'https://finance.yahoo.com/quote/HG=F/'},
    {label:'Nickel',key:'nickel',source:'timeseries',unit:'USD/t',srcLabel:'LME / Yahoo Finance',srcUrl:''},
    {label:'Iron Ore',key:'iron_ore',source:'timeseries',unit:'USD/t',srcLabel:'SGX / Platts',srcUrl:''},
    // Nuclear & fertilizer proxies
    {label:'Uranium (Cameco)',key:'uranium',source:'timeseries',unit:'USD',srcLabel:'Yahoo Finance (CCJ)',srcUrl:'https://finance.yahoo.com/quote/CCJ/'},
    {label:'Potash (Nutrien)',key:'potash_nutrien',source:'timeseries',unit:'USD',srcLabel:'Yahoo Finance (NTR)',srcUrl:'https://finance.yahoo.com/quote/NTR/'},
    {label:'Coal',key:'coal',source:'timeseries',unit:'USD/t',srcLabel:'Yahoo Finance',srcUrl:''},
    // Labour
    {label:'Mining & Energy Employment',key:'mining_og_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL}
  ],
  '22':[
    // Fuels for generation
    {label:'Natural Gas',key:'natural_gas',source:'timeseries',unit:'USD/MMBtu',srcLabel:'Yahoo Finance (NG=F)',srcUrl:'https://finance.yahoo.com/quote/NG=F/'},
    {label:'WTI Crude (Fuel)',key:'wti',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (CL=F)',srcUrl:'https://finance.yahoo.com/quote/CL=F/'},
    {label:'Coal',key:'coal',source:'timeseries',unit:'USD/t',srcLabel:'Yahoo Finance',srcUrl:''},
    {label:'LNG (Asia JKM)',key:'lng_asia',source:'timeseries',unit:'USD/MMBtu',srcLabel:'S&P Platts JKM',srcUrl:''},
    {label:'Uranium (Cameco)',key:'uranium',source:'timeseries',unit:'USD',srcLabel:'Yahoo Finance (CCJ)',srcUrl:'https://finance.yahoo.com/quote/CCJ/'},
    // Labour
    {label:'Utilities Employment',key:'utilities_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    // Cost of capital & inflation
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'}
  ],
  '23':[
    // Housing activity
    {label:'Housing Starts (Total)',key:'housing_starts_total',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 34-10-0143',srcUrl:STATCAN_HSTARTS_URL},
    {label:'Housing Starts (Single-Detached)',key:'housing_starts_single',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 34-10-0143',srcUrl:STATCAN_HSTARTS_URL},
    {label:'Housing Starts (Multi-Unit)',key:'housing_starts_multi',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 34-10-0143',srcUrl:STATCAN_HSTARTS_URL},
    // Building investment
    {label:'Residential Building Investment',key:'residential_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    {label:'Non-Residential Building Investment',key:'non_residential_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    {label:'Commercial Building Investment',key:'commercial_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    {label:'Industrial Building Investment',key:'industrial_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    {label:'Institutional Building Investment',key:'institutional_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    // Prices
    {label:'New Housing Price Index',key:'new_housing_price_index',source:'indicators',unit:'index',freq:'Monthly',srcLabel:'StatCan 18-10-0205',srcUrl:STATCAN_NHPI_URL},
    // Permits (national)
    {label:'Residential Building Permits',key:'bldg_permits_res_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0066',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601'},
    {label:'Non-Residential Building Permits',key:'bldg_permits_nonres_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0066',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601'},
    // Labour & rates
    {label:'Construction Employment',key:'construction_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'Prime Rate',key:'prime_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/bank-of-canada-prime-rate/'},
    {label:'Copper (Building Materials)',key:'copper',source:'timeseries',unit:'USD/lb',srcLabel:'Yahoo Finance (HG=F)',srcUrl:'https://finance.yahoo.com/quote/HG=F/'}
  ],
  '31-33':[
    // Sector top-line
    {label:'Manufacturing Sales',key:'manufacturing_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 16-10-0047',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701'},
    {label:'Manufacturing Employment',key:'manufacturing_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'Machinery & Equipment Capex',key:'machinery_capex',source:'indicators',unit:'$M',freq:'Annual',srcLabel:'StatCan 34-10-0035',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410003501'},
    // FX (cross-border manufacturing)
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'},
    // Metal inputs
    {label:'Copper',key:'copper',source:'timeseries',unit:'USD/lb',srcLabel:'Yahoo Finance (HG=F)',srcUrl:'https://finance.yahoo.com/quote/HG=F/'},
    {label:'Aluminum',key:'aluminum',source:'timeseries',unit:'USD/t',srcLabel:'LME',srcUrl:''},
    {label:'Iron Ore',key:'iron_ore',source:'timeseries',unit:'USD/t',srcLabel:'SGX / Platts',srcUrl:''},
    {label:'Nickel',key:'nickel',source:'timeseries',unit:'USD/t',srcLabel:'LME',srcUrl:''},
    {label:'Zinc',key:'zinc',source:'timeseries',unit:'USD/t',srcLabel:'LME',srcUrl:''},
    // Energy inputs
    {label:'Natural Gas',key:'natural_gas',source:'timeseries',unit:'USD/MMBtu',srcLabel:'Yahoo Finance (NG=F)',srcUrl:'https://finance.yahoo.com/quote/NG=F/'},
    {label:'WTI Crude',key:'wti',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (CL=F)',srcUrl:'https://finance.yahoo.com/quote/CL=F/'},
    // Freight & US demand
    {label:'Dry Bulk Shipping',key:'dry_bulk_shipping',source:'timeseries',unit:'index',srcLabel:'Baltic Exchange',srcUrl:''},
    {label:'S&P 500 (US Demand)',key:'sp500',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPC)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPC/'}
  ],
  '41':[
    // Sector top-line
    {label:'Wholesale Sales',key:'wholesale_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 20-10-0074',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010007401'},
    {label:'Wholesale Trade Employment',key:'wholesale_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    // Upstream/downstream linkages
    {label:'Manufacturing Sales',key:'manufacturing_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 16-10-0047',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701'},
    {label:'Retail Sales',key:'retail_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 20-10-0008',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801'},
    // FX & freight
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'},
    {label:'Dry Bulk Shipping',key:'dry_bulk_shipping',source:'timeseries',unit:'index',srcLabel:'Baltic Exchange',srcUrl:''},
    // Prices & rates
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    // Labour
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // Equity proxy
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'}
  ],
  '44-45':[
    // Sector top-line
    {label:'Retail Sales',key:'retail_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 20-10-0008',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801'},
    {label:'Retail Trade Employment',key:'retail_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    // Inflation
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    // Household financials
    {label:'Household Disposable Income',key:'household_disposable_income_national',source:'indicators',unit:'$M',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    {label:'Household Savings Rate',key:'household_savings_rate_national',source:'indicators',unit:'%',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    {label:'Household Debt-Service Ratio',key:'household_debt_service_ratio_national',source:'indicators',unit:'%',freq:'Quarterly',srcLabel:'StatCan 38-10-0238',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3810023801'},
    // Rates
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'Prime Rate',key:'prime_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/bank-of-canada-prime-rate/'},
    // Labour
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // FX
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'}
  ],
  '48-49':[
    // Labour
    {label:'Transportation Employment',key:'transportation_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    // Fuel
    {label:'WTI Crude (Fuel)',key:'wti',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (CL=F)',srcUrl:'https://finance.yahoo.com/quote/CL=F/'},
    {label:'Brent Crude (Fuel)',key:'brent',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (BZ=F)',srcUrl:'https://finance.yahoo.com/quote/BZ=F/'},
    {label:'Natural Gas',key:'natural_gas',source:'timeseries',unit:'USD/MMBtu',srcLabel:'Yahoo Finance (NG=F)',srcUrl:'https://finance.yahoo.com/quote/NG=F/'},
    // Freight / demand proxies
    {label:'Dry Bulk Shipping',key:'dry_bulk_shipping',source:'timeseries',unit:'index',srcLabel:'Baltic Exchange',srcUrl:''},
    {label:'Manufacturing Sales (Freight Demand)',key:'manufacturing_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 16-10-0047',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610004701'},
    {label:'Retail Sales (Freight Demand)',key:'retail_sales_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 20-10-0008',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010000801'},
    // Capital cost
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // FX
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'},
    // Wage
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'}
  ],
  '51':[
    // Labour
    {label:'Information Sector Employment',key:'information_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    // Equity benchmarks (tech valuation)
    {label:'Nasdaq',key:'nasdaq',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^IXIC)',srcUrl:'https://finance.yahoo.com/quote/%5EIXIC/'},
    {label:'S&P 500',key:'sp500',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPC)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPC/'},
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'},
    // Discount rate
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    // FX
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'},
    // Prices & wages
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'}
  ],
  '52':[
    // Policy rate
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'Prime Rate',key:'prime_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/bank-of-canada-prime-rate/'},
    // Yield curve
    {label:'GoC 2-Year Yield',key:'goc_2y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'GoC 5-Year Yield',key:'goc_5y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'Yield Curve (10y\u20132y)',key:'yield_curve_10y2y',source:'timeseries',unit:'pp',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // Credit spreads
    {label:'HY Credit Spread',key:'hy_spread',source:'timeseries',unit:'bps',srcLabel:'FRED / ICE BofA',srcUrl:'https://fred.stlouisfed.org/series/BAMLH0A0HYM2'},
    {label:'IG Credit Spread',key:'ig_spread',source:'timeseries',unit:'bps',srcLabel:'FRED / ICE BofA',srcUrl:'https://fred.stlouisfed.org/series/BAMLC0A0CM'},
    // Equities
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'},
    {label:'S&P 500',key:'sp500',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPC)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPC/'},
    // Labour & FX
    {label:'Finance & Insurance Employment',key:'finance_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'}
  ],
  '53':[
    // Housing flow
    {label:'Housing Starts (Total)',key:'housing_starts_total',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 34-10-0143',srcUrl:STATCAN_HSTARTS_URL},
    {label:'Housing Starts (Single-Detached)',key:'housing_starts_single',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 34-10-0143',srcUrl:STATCAN_HSTARTS_URL},
    {label:'Housing Starts (Multi-Unit)',key:'housing_starts_multi',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 34-10-0143',srcUrl:STATCAN_HSTARTS_URL},
    // Prices
    {label:'New Housing Price Index',key:'new_housing_price_index',source:'indicators',unit:'index',freq:'Monthly',srcLabel:'StatCan 18-10-0205',srcUrl:STATCAN_NHPI_URL},
    // Mortgage rates
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'Prime Rate',key:'prime_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/bank-of-canada-prime-rate/'},
    {label:'GoC 5-Year Yield (5y Mortgage Ref)',key:'goc_5y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // Permits & investment
    {label:'Residential Building Permits',key:'bldg_permits_res_national',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0066',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410006601'},
    {label:'Residential Building Investment',key:'residential_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    // Household
    {label:'Household Debt-Service Ratio',key:'household_debt_service_ratio_national',source:'indicators',unit:'%',freq:'Quarterly',srcLabel:'StatCan 38-10-0238',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3810023801'},
    // Labour & CPI
    {label:'Real Estate Employment',key:'real_estate_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL}
  ],
  '54':[
    // Labour (services-heavy)
    {label:'Professional Services Employment',key:'professional_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    {label:'Job Vacancies',key:'job_vacancies_total',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 14-10-0372',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201'},
    // Equity & rates
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'},
    {label:'S&P 500 (Client Demand)',key:'sp500',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPC)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPC/'},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'}
  ],
  '55':[
    // Note: StatCan 14-10-0022 aggregates NAICS 55 into the "Business, building and other
    // support services" bucket alongside NAICS 56, so no standalone 55 employment series is
    // available at this table's granularity. Employment intentionally omitted to avoid
    // showing the same aggregate value as 56.
    // Equities (parent valuations)
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'},
    {label:'S&P 500',key:'sp500',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPC)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPC/'},
    // Cost of capital
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'Prime Rate',key:'prime_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/bank-of-canada-prime-rate/'},
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // Credit (M&A financing)
    {label:'HY Credit Spread',key:'hy_spread',source:'timeseries',unit:'bps',srcLabel:'FRED / ICE BofA',srcUrl:'https://fred.stlouisfed.org/series/BAMLH0A0HYM2'},
    {label:'IG Credit Spread',key:'ig_spread',source:'timeseries',unit:'bps',srcLabel:'FRED / ICE BofA',srcUrl:'https://fred.stlouisfed.org/series/BAMLC0A0CM'},
    // FX
    {label:'CAD/USD Exchange Rate',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'}
  ],
  '56':[
    // Labour (labour-intensive sector)
    {label:'Admin & Support Employment',key:'admin_waste_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Participation Rate',key:'nat_participation_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    {label:'Job Vacancies',key:'job_vacancies_total',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 14-10-0372',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201'},
    // Prices & rates
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'}
  ],
  '61':[
    // Labour
    {label:'Education Sector Employment',key:'education_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    {label:'Job Vacancies',key:'job_vacancies_total',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 14-10-0372',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201'},
    // Capital (institutional construction)
    {label:'Institutional Building Investment',key:'institutional_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    // Prices & rates
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // Labour market backdrop
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'}
  ],
  '62':[
    // Labour
    {label:'Health Care Employment',key:'healthcare_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    {label:'Job Vacancies',key:'job_vacancies_total',source:'indicators',unit:'units',freq:'Monthly',srcLabel:'StatCan 14-10-0372',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410037201'},
    // Capital (hospital construction)
    {label:'Institutional Building Investment',key:'institutional_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    // Prices & rates
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // Labour market backdrop
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'}
  ],
  '71':[
    // Note: StatCan 14-10-0022 aggregates NAICS 71 into the "Information, culture and
    // recreation" bucket alongside NAICS 51, so no standalone 71 employment series exists
    // at this table's granularity. Employment intentionally omitted to avoid showing the
    // same aggregate value as 51.
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // Household spending power
    {label:'Household Disposable Income',key:'household_disposable_income_national',source:'indicators',unit:'$M',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    {label:'Household Savings Rate',key:'household_savings_rate_national',source:'indicators',unit:'%',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    // FX (inbound tourism)
    {label:'CAD/USD (Tourism FX)',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'},
    // Prices & rates
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    // Labour market backdrop
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'TSX Composite',key:'tsx_composite',source:'timeseries',unit:'points',srcLabel:'Yahoo Finance (^GSPTSE)',srcUrl:'https://finance.yahoo.com/quote/%5EGSPTSE/'}
  ],
  '72':[
    // Labour
    {label:'Accommodation & Food Employment',key:'accommodation_food_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // Household spending power
    {label:'Household Disposable Income',key:'household_disposable_income_national',source:'indicators',unit:'$M',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    {label:'Household Savings Rate',key:'household_savings_rate_national',source:'indicators',unit:'%',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    // FX (tourism)
    {label:'CAD/USD (Tourism FX)',key:'cadusd',source:'timeseries',unit:'rate',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/exchange/'},
    // Prices
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'WTI Crude (Gas Prices)',key:'wti',source:'timeseries',unit:'USD/bbl',srcLabel:'Yahoo Finance (CL=F)',srcUrl:'https://finance.yahoo.com/quote/CL=F/'},
    // Labour market
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'}
  ],
  '81':[
    // Labour
    {label:'Other Services Employment',key:'other_services_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // Household spending power
    {label:'Household Disposable Income',key:'household_disposable_income_national',source:'indicators',unit:'$M',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    {label:'Household Savings Rate',key:'household_savings_rate_national',source:'indicators',unit:'%',freq:'Quarterly',srcLabel:'StatCan 36-10-0112',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201'},
    // Prices & rates
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    // Labour market
    {label:'National Employment Rate',key:'nat_employment_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'},
    {label:'National Participation Rate',key:'nat_participation_rate',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'}
  ],
  '91':[
    // Labour
    {label:'Public Administration Employment',key:'public_admin_employment',source:'indicators',unit:'thousands',freq:'Monthly',srcLabel:'StatCan 14-10-0022',srcUrl:STATCAN_LFS_URL},
    {label:'Avg Hourly Wage (National)',key:'nat_avg_hourly_wage',source:'indicators',unit:'$/hr',freq:'Monthly',srcLabel:'StatCan 14-10-0063',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410006301'},
    // Fiscal cost of funds
    {label:'BoC Overnight Rate',key:'boc_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_RATE_URL},
    {label:'Prime Rate',key:'prime_rate',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:'https://www.bankofcanada.ca/rates/banking-and-financial-statistics/bank-of-canada-prime-rate/'},
    {label:'GoC 2-Year Yield',key:'goc_2y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'GoC 5-Year Yield',key:'goc_5y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'GoC 10-Year Yield',key:'goc_10y_yield',source:'indicators',unit:'%',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    {label:'Yield Curve (10y\u20132y)',key:'yield_curve_10y2y',source:'timeseries',unit:'pp',srcLabel:'Bank of Canada',srcUrl:BOC_BONDS_URL},
    // Prices
    {label:'National CPI',key:'cpi_national',source:'indicators',unit:'index',srcLabel:'StatCan 18-10-0004',srcUrl:STATCAN_CPI_URL},
    // Capital (federal construction)
    {label:'Institutional Building Investment',key:'institutional_building_investment',source:'indicators',unit:'$M',freq:'Monthly',srcLabel:'StatCan 34-10-0175',srcUrl:STATCAN_BLDINV_URL},
    // Labour market
    {label:'National Unemployment',key:'nat_unemployment',source:'indicators',unit:'%',srcLabel:'StatCan 14-10-0287',srcUrl:'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701'}
  ]
};

// Formats a resolved indicator value for the Key Indicators table based on unit hint
function _indFmtKeyValue(val,unit){
  if(val==null||isNaN(val))return'\u2014';
  var u=String(unit||'').toLowerCase();
  if(u==='$m'){
    if(Math.abs(val)>=1000000)return'$'+(val/1000000).toFixed(2)+'T';
    if(Math.abs(val)>=1000)return'$'+(val/1000).toFixed(2)+'B';
    return'$'+Math.round(val).toLocaleString('en-CA')+'M';
  }
  if(u==='thousands')return Math.round(val).toLocaleString('en-CA')+'K';
  if(u==='units')return Math.round(val).toLocaleString('en-CA');
  if(u==='index')return val.toFixed(1);
  if(u==='%'||u==='pp')return val.toFixed(2)+(u==='pp'?'pp':'%');
  // Credit spreads in timeseries.json are stored in percentage points (e.g., 3.42 = 342 bps)
  if(u==='bps')return Math.round(val*100)+' bps';
  if(u==='rate')return val.toFixed(4);
  if(u==='points')return Math.round(val).toLocaleString('en-CA');
  if(u==='usd/bbl')return'$'+val.toFixed(2)+'/bbl';
  if(u==='usd/oz')return'$'+val.toFixed(2)+'/oz';
  if(u==='usd/lb')return'$'+val.toFixed(2)+'/lb';
  if(u==='usd/mmbtu')return'$'+val.toFixed(2)+'/MMBtu';
  if(u==='usd/mbf')return'$'+val.toFixed(2)+'/MBF';
  if(u==='usd/bu')return'$'+val.toFixed(2)+'/bu';
  if(u==='usd/t')return'$'+val.toFixed(2)+'/t';
  if(u==='$/hr')return'$'+val.toFixed(2)+'/hr';
  if(u==='cad/tonne')return'C$'+Math.round(val).toLocaleString('en-CA')+'/t';
  if(u==='gdd')return Math.round(val).toLocaleString('en-CA')+' GDD';
  if(u==='usd')return'$'+val.toFixed(2);
  return typeof val==='number'?fmtNum(val):String(val);
}

// Pretty period label: "Jan 2026" from "2026-01-01", "2024 Q4" rough approximation, etc.
function _indFmtPeriod(period){
  if(!period)return'';
  var m=/^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(String(period));
  if(!m)return String(period);
  var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var mo=parseInt(m[2],10);
  return(MONTHS[mo-1]||m[2])+' '+m[1];
}

// Legacy spec keys \u2192 canonical exported indicator names. The exporter
// (tools/export_dashboard.py _SKIP_INDICATORS) deliberately drops the old
// nat_* / cpi_national naming in favour of indicator + province='national',
// so specs written against the old names must be translated here or their
// rows silently vanish (2026-06-11: participation rate "shows nothing").
// Optional unit override: canonical cpi is a YoY % string, not an index level.
var _IND_KEY_ALIASES={
  nat_unemployment:{name:'unemployment'},
  nat_employment_rate:{name:'employmentRate'},
  nat_participation_rate:{name:'participationRate'},
  cpi_national:{name:'cpi',unit:'%'},
  boc_rate:{name:'overnight_rate'}
};

// Resolves a single IND_KEY_INDICATORS spec into a table row: {label, period, valDisplay, change, chgCls, srcLabel, srcUrl}
// Returns null if data is missing or period is older than 36 months (stale).
function _indResolveKeyRow(spec,tsData){
  var out={label:spec.label,period:'',valDisplay:'\u2014',change:'\u2014',chgCls:'chg-flat',srcLabel:spec.srcLabel||'',srcUrl:spec.srcUrl||''};
  var now=new Date();
  // Staleness cutoff: 18 months. Rows with a latest period older than this are dropped.
  var staleCutoff=new Date(now.getFullYear(),now.getMonth()-18,1);
  if(spec.source==='indicators'){
    var alias=_IND_KEY_ALIASES[spec.key];
    var indName=alias?alias.name:spec.key;
    var indUnit=(alias&&alias.unit)||spec.unit;
    // Prefer the non-provincial / national entry for current value
    var rec=null;
    for(var i=0;i<indicators.length;i++){
      var r=indicators[i];
      if(r.indicator_name!==indName)continue;
      if(r.value==null||r.value==='')continue;
      var prov=(r.province||'').toLowerCase();
      if(prov&&prov!=='national'&&prov!=='canada'&&prov!=='')continue;
      if(!rec||(r.period||'')>(rec.period||''))rec=r;
    }
    if(!rec)return null;
    var per=rec.period||'';
    var perDate=per?new Date(per):null;
    if(perDate&&!isNaN(perDate)&&perDate<staleCutoff)return null;
    var val=parseFloat(rec.value);if(isNaN(val))return null;
    out.period=_indFmtPeriod(per);
    out.valDisplay=_indFmtKeyValue(val,indUnit);
    var chg=computeChange(indName,'national');
    // For wage levels (unit "$/hr"), computeChange misdetects as "rate" because values are <100
    // and returns an absolute-difference "pp" value. Force percent-change mode by recomputing manually.
    if(spec.unit==='$/hr'){
      var _wh=_getHistory();
      var _byM={};
      for(var _i=0;_i<_wh.length;_i++){
        var _r=_wh[_i];
        if(_r.indicator_name!==indName||_r.value==null)continue;
        var _ym=String(_r.period||'').slice(0,7);
        if(!/^\d{4}-\d{2}$/.test(_ym))continue;
        var _v=parseFloat(_r.value);
        if(!isNaN(_v))_byM[_ym]=_v;
      }
      var _months=Object.keys(_byM).sort();
      if(_months.length>=2){
        var _curr=_byM[_months[_months.length-1]];
        var _prev=_byM[_months[_months.length-2]];
        if(_prev!==0){
          var _pct=((_curr-_prev)/Math.abs(_prev))*100;
          chg=(_pct>=0?'+':'')+_pct.toFixed(1)+'%';
        }
      }
    }
    if(chg){
      // Handle "-0.0%" / "+0.0%" edge case — display as flat
      if(/^[+\-\u2212]0\.0(%|pp)$/.test(chg)){
        out.change='\u00B1 0.0'+(chg.indexOf('pp')>=0?'pp':'%');
        out.chgCls='chg-flat';
      }else{
        out.change=chg;
        if(/^-/.test(chg)||/^\u2212/.test(chg))out.chgCls='chg-down';
        else if(/^\+/.test(chg))out.chgCls='chg-up';
      }
      // Apply optional chgLabel suffix for non-standard comparison windows (e.g., "vs 2024" for annual GDD)
      if(spec.chgLabel&&out.change!=='\u2014'){
        out.change=out.change+' '+spec.chgLabel;
      }
    }
    return out;
  }else if(spec.source==='timeseries'){
    if(!tsData)return null;
    var arr=tsData[spec.key];
    if(!arr||!arr.length)return null;
    // Sort ascending by date and pick latest + ~30-day-prior for change
    var sorted=arr.slice().filter(function(p){return p&&p.date&&p.value!=null}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
    if(sorted.length<2)return null;
    var latest=sorted[sorted.length-1];
    var lDate=new Date(latest.date);
    if(lDate<staleCutoff)return null;
    // Find the entry closest to 30 days prior
    var targetMs=lDate.getTime()-30*86400000;
    var prior=sorted[0];
    var bestDiff=Infinity;
    for(var k=0;k<sorted.length-1;k++){
      var d=new Date(sorted[k].date).getTime();
      var diff=Math.abs(d-targetMs);
      if(diff<bestDiff){bestDiff=diff;prior=sorted[k]}
    }
    var lVal=parseFloat(latest.value);
    var pVal=parseFloat(prior.value);
    if(isNaN(lVal)||isNaN(pVal))return null;
    out.period=_indFmtPeriod(latest.date);
    out.valDisplay=_indFmtKeyValue(lVal,spec.unit);
    if(pVal!==0){
      var pct=((lVal-pVal)/Math.abs(pVal))*100;
      var sign=pct>=0?'+':'';
      out.change=sign+pct.toFixed(1)+'% (30d)';
      out.chgCls=pct>=0?'chg-up':'chg-down';
    }
    return out;
  }
  return null;
}

// ==== Industry insight chart infrastructure ====
// Resolves a single dataKey to an array of {label, value} points for the given window.
// dataSource: "indicators" reads indicators.json history; caller handles "timeseries" async.
// prov scopes the history rows (history holds 14 jurisdictions for shared names like
// "unemployment"): explicit arg wins, else a province key prefix (on_exports_pct), else national.
function _indResolveIndicatorsSeries(key,windowMonths,prov){
  var _a=_IND_KEY_ALIASES[key];if(_a)key=_a.name;
  if(prov==null||prov===''){
    var pm=/^(on|qc|ab|bc|sk|mb|ns|nb|nl|pe|yt|nt|nu)_/i.exec(String(key));
    prov=pm?pm[1].toUpperCase():'national';
  }
  var hist=_getHistory()||[];
  var rows=hist.filter(function(r){return r.indicator_name===key&&r.value!=null&&r.period&&_matchProv(r.province,prov)});
  // Graceful fallback: single-jurisdiction series stored under a different province label
  if(!rows.length)rows=hist.filter(function(r){return r.indicator_name===key&&r.value!=null&&r.period});
  // Drop briefing-snapshot artifact periods (real observations are YYYY-MM-01 / YYYY-MM / YYYY) — mirrors computeChange
  var clean=rows.filter(function(r){var p=String(r.period);return /^\d{4}-\d{2}-01$/.test(p)||/^\d{4}-\d{2}$/.test(p)||/^\d{4}$/.test(p)});
  if(clean.length>=2)rows=clean;
  var byMonth={};
  rows.forEach(function(r){
    var ym=String(r.period).slice(0,7);
    if(!/^\d{4}-\d{2}$/.test(ym))return;
    // Prefer later-period duplicates (calendar-month dedupe)
    if(!byMonth[ym]||String(r.period)>=String(byMonth[ym].period))byMonth[ym]=r;
  });
  var ordered=Object.keys(byMonth).sort().map(function(ym){
    var v=parseFloat(byMonth[ym].value);
    return{label:ym,value:isNaN(v)?null:v};
  }).filter(function(p){return p.value!==null});
  return ordered.slice(-windowMonths);
}

// Parses window field like "24m" to an integer months count (max 24)
function _indWindowMonths(w){
  if(!w)return 24;
  var m=/^(\d+)m$/i.exec(String(w));
  return m?Math.min(parseInt(m[1],10),24):24;
}

// Rebases a values array to 100 at the first non-null point (for multi_line normalization)
function _indNormalize(values){
  if(!values||!values.length)return values;
  var base=null;
  for(var i=0;i<values.length;i++){if(values[i]!=null&&values[i]!==0){base=values[i];break}}
  if(base==null)return values;
  return values.map(function(v){return v==null?null:(v/base)*100});
}

// Formats a "YYYY-MM" label as "Mon YY"
function _indFmtMonthLabel(ym){
  if(!ym||ym.length<7)return ym||'';
  var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var yr=ym.slice(2,4);var mo=parseInt(ym.slice(5,7),10);
  return(MONTHS[mo-1]||ym.slice(5,7))+" '"+yr;
}

// Builds the HTML shell for an industry insight callout + chart container
function buildIndInsightStrip(spec){
  if(!spec)return'';
  var callout=spec.callout||spec.reasoning||'';
  var h='';
  if(callout)h+='<div class="narrative chart-intro"><p>'+san(callout)+'</p></div>';
  h+='<div class="tldr-callout">';
  h+='<div class="tldr-callout-chart">';
  h+='<div class="tldr-callout-svg" id="indInsightSvg"><div style="height:280px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:12px">Loading chart\u2026</div></div>';
  h+='</div></div>';
  return h;
}

// Renders the industry insight chart through the shared SVG callout chart.
async function renderIndInsightChart(spec){
  if(!spec||!spec.dataKeys||!spec.dataKeys.length)return;
  var el=document.getElementById('indInsightSvg');
  if(!el)return;
  var series=await _loadChartSpecSeries(spec);
  if(!series.length){
    el.innerHTML='<div style="height:280px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No historical data available</div>';
    return;
  }
  var title=spec.title||'Industry Insight';
  var subtitle=(spec.subtitle||'').replace(/\b\d+[-\s]?month\b/i,'12-month');
  var chartType=spec.chartType||'line';
  var source=spec.source||(spec.dataSource==='indicators'?'Source: Statistics Canada':_deriveChartSource(spec.dataKeys));
  el.innerHTML=_svgCalloutChart(series,spec.annotations||[],title,subtitle,chartType,source);
}

async function _renderIndContent(){
  var code=selectedIndustry;
  var goodsArr=(D&&D.goodsIndustries)||[];
  var servArr=(D&&D.servicesIndustries)||[];
  var allSectors=goodsArr.concat(servArr);
  var industry=allSectors.find(function(s){return s.code===code})||allSectors[0];
  if(!industry)return;
  var mainEl=$('indMainContent');if(!mainEl)return;

  // Ensure projects are loaded for pipeline filtering
  if(!allProjects||!allProjects.length){
    try{await loadProjects()}catch(e){console.warn('loadProjects (industries):',e)}
  }

  var name=industry.name||NAICS_NAMES[code]||code;
  var mm=industry.mm||'\u2014';
  var yy=industry.yy||'\u2014';
  var isUp=!industry.isNegative;
  var mmArr=industry.mm?(isUp?'\u25B2':'\u25BC'):'\u2014';
  var mmCls=industry.mm?(isUp?'chg-up':'chg-down'):'chg-flat';
  var yyCls=(yy.indexOf('-')>=0||yy.indexOf('\u2212')>=0)?'chg-down':(yy==='\u2014'?'chg-flat':'chg-up');
  var yyArr=yy==='\u2014'?'\u2014':(yyCls==='chg-down'?'\u25BC':'\u25B2');
  var subsectors=Array.isArray(industry.subsectors)?industry.subsectors:[];
  var sources=industry.industrySources||[];

  // Filter projects to this industry by naics_code prefix match.
  // Compound codes (31-33, 44-45, 48-49) match any of the individual prefixes too.
  var prefixList=[];
  if(code.indexOf('-')>=0){
    var parts=code.split('-');
    var start=parseInt(parts[0],10),end=parseInt(parts[1],10);
    if(!isNaN(start)&&!isNaN(end)){for(var n=start;n<=end;n++)prefixList.push(String(n))}
    prefixList.push(code);
  }else{
    prefixList.push(code);
  }
  var relatedProjects=(allProjects||[]).filter(function(p){
    var pn=String(p.naics_code||'').trim();
    if(!pn||pn==='unknown')return false;
    for(var i=0;i<prefixList.length;i++){
      var pref=prefixList[i];
      if(pn===pref||pn.indexOf(pref)===0)return true;
      // Also match when project code contains a dash and prefix matches start
      if(pn.indexOf('-')>=0&&pn.split('-')[0]===pref.split('-')[0])return true;
    }
    return false;
  });
  var projCount=relatedProjects.length;
  var pipelineValueNum=relatedProjects.reduce(function(sum,p){
    var v=parseFloat(String(p.value||'').replace(/[^0-9.]/g,''));
    return sum+(isNaN(v)?0:v);
  },0);
  var pipelineValueDisplay=pipelineValueNum>=1000?'$'+(pipelineValueNum/1000).toFixed(1)+'B':(pipelineValueNum?'$'+fmtNum(pipelineValueNum)+'M':'\u2014');

  function addLeads(htmlStr){
    return _editorialProse(htmlStr);  // Demo-style lead-in + strip scattered inline bold (unified)
  }

  // Pre-fetch timeseries.json so Key Indicators rows can resolve commodity data synchronously
  var _indTsData={};
  try{_indTsData=await fetchJSON('timeseries.json')}catch(e){_indTsData={}}

  var html='';

  // Hero card (title + headline stats + attached subsector chip strip)
  // Consistent layout: title on the left (flex:1 1 auto), 4 stat blocks on the right (flex:0 0 auto).
  // Each stat-value is an inline-flex row with arrow + number as separate spans so the arrow
  // baseline-aligns cleanly with the number instead of floating inline.
  function statHtml(cls,arrow,num,label){
    var arrowHtml=arrow&&arrow!=='\u2014'?'<span class="stat-arrow">'+arrow+'</span>':'';
    return '<div><div class="stat-value '+cls+'">'+arrowHtml+'<span class="stat-num">'+num+'</span></div><div class="stat-label">'+label+'</div></div>';
  }
  html+='<div class="industry-header-card">';
  html+='<div class="industry-header-top">';
  html+='<div class="industry-header-title"><h2>'+san(name)+'</h2>';
  html+='<div class="industry-sub">Weekly industry analysis \u00B7 NAICS '+san(code)+'</div></div>';
  html+='<div class="industry-header-stats">';
  html+=statHtml(mmCls,mmArr,san(mm),'GDP M/M');
  html+=statHtml(yyCls,yyArr,san(yy),'GDP Y/Y');
  html+=statHtml('chg-flat','',projCount.toLocaleString('en-CA'),'Active Projects');
  html+=statHtml('chg-flat','',san(pipelineValueDisplay),'Pipeline Value');
  html+='</div>';
  html+='</div>'; // close industry-header-top

  // Subsector chip strip
  if(subsectors.length){
    html+='<div class="industry-subsector-strip">';
    html+='<div class="ind-strip-label">Subsectors ('+subsectors.length+')</div>';
    html+='<div class="ind-strip-chips">';
    subsectors.forEach(function(sub){
      var smmRaw=(sub.mm||'').trim();
      var sIsNum=/[+\-\u2212]?\d+(\.\d+)?%/.test(smmRaw);
      var sIsNA=!smmRaw||smmRaw==='N/A';
      var sCls='chip-flat';
      var sArr='';
      var sDisp='N/A';
      if(sIsNum){
        sCls=(smmRaw.indexOf('-')>=0||smmRaw.indexOf('\u2212')>=0)?'chip-down':'chip-up';
        sArr=sCls==='chip-down'?'\u25BC ':'\u25B2 ';
        sDisp=sArr+smmRaw;
      }else if(!sIsNA){
        // textual status like "declined"
        var lc=smmRaw.toLowerCase();
        if(lc.indexOf('decl')>=0||lc.indexOf('fell')>=0||lc.indexOf('down')>=0)sCls='chip-down';
        else if(lc.indexOf('rose')>=0||lc.indexOf('grew')>=0||lc.indexOf('up')>=0)sCls='chip-up';
        sDisp=smmRaw;
      }
      html+='<span class="ind-subsector-chip '+sCls+'">';
      html+='<span class="ind-chip-name">'+san(sub.name||'')+'</span>';
      html+='<span class="ind-chip-code">'+san(sub.code||'')+'</span>';
      html+='<span class="ind-chip-chg">'+san(sDisp)+'</span>';
      html+='</span>';
    });
    html+='</div>';
    html+='</div>'; // close industry-subsector-strip
  }
  html+='</div>'; // close industry-header-card

  // Section 1: Industry Analysis
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Industry Analysis</h3></div>';
  if(industry.analysis){
    var narrativeHtml=linkFootnotes(industry.analysis,sources);
    html+='<div class="narrative">'+addLeads(narrativeHtml)+'</div>';
  }else{
    html+='<div class="narrative"><p>No analysis available for '+san(name)+'.</p></div>';
  }
  // Insight chart container
  html+='<div id="indInsightChartArea"></div>';
  // Sources
  if(sources.length){
    html+='<details class="sources-section"><summary>Sources ('+sources.length+')</summary><ol>';
    sources.forEach(function(s){
      var url=s.url||s.archive_url||'';
      var title=s.title||'Source';
      html+='<li>'+(url?'<a href="'+san(url)+'" target="_blank" rel="noopener noreferrer">'+san(title)+'</a>':san(title))+'</li>';
    });
    html+='</ol></details>';
  }
  html+='</div>';

  // Section 2: Key Indicators — per-industry, StatCan-first, with commodity overlay rows from timeseries
  var statcanGdpUrl='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401';
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Key Indicators</h3>';
  html+='<span class="section-meta">'+san(name)+' \u00B7 NAICS '+san(code)+'</span></div>';
  html+='<div class="indicator-panel"><table class="ind-table"><thead><tr>';
  html+='<th>Indicator</th><th>Frequency</th><th>Value</th><th>Change</th><th>Source</th></tr></thead><tbody>';

  // Build the row list: universal GDP rows first, then industry-specific, then universal pipeline rows
  var rendered=[];
  rendered.push({name:'Real GDP (M/M)',ctx:'Jan 2026',freq:'Monthly',value:mm,chg:mmArr+' '+mm,cls:mmCls,src:'Statistics Canada',url:statcanGdpUrl});
  rendered.push({name:'Real GDP (Y/Y)',ctx:'Jan 2026',freq:'Monthly',value:yy,chg:yyArr+' '+yy,cls:yyCls,src:'Statistics Canada',url:statcanGdpUrl});

  var specList=IND_KEY_INDICATORS[code]||[];
  specList.forEach(function(spec){
    var row=_indResolveKeyRow(spec,_indTsData);
    if(!row)return;
    // Frequency: allow spec to override, otherwise heuristic from source/key
    var freq=spec.freq||'Monthly';
    if(!spec.freq){
      if(spec.source==='timeseries')freq='Daily';
      else if(spec.key.indexOf('capex')>=0||spec.key.indexOf('building_investment')>=0)freq='Quarterly';
      else if(spec.key.indexOf('household_')>=0||spec.key==='household_savings_rate'||spec.key==='household_debt_service_ratio'||spec.key==='household_disposable_income')freq='Annual';
    }
    rendered.push({name:row.label,ctx:row.period,freq:freq,value:row.valDisplay,chg:row.change,cls:row.chgCls,src:row.srcLabel,url:row.srcUrl});
  });
  // Active Projects + Pipeline Value intentionally excluded — they live in the hero card banner, not this table

  rendered.forEach(function(r){
    html+='<tr><td><span class="ind-name">'+san(r.name)+'</span><div class="ind-t-name-ctx">'+san(r.ctx)+'</div></td>';
    html+='<td class="ind-freq">'+san(r.freq)+'</td>';
    html+='<td class="ind-val">'+san(r.value)+'</td>';
    html+='<td class="'+r.cls+'">'+san(r.chg)+'</td>';
    html+='<td class="ind-src">'+(r.url?'<a href="'+r.url+'" target="_blank" rel="noopener noreferrer" class="ind-src-link">'+san(r.src)+'</a>':san(r.src))+'</td></tr>';
  });
  html+='</tbody></table></div></div>';

  // Section 4: Project Pipeline (top 10 by value)
  html+='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Project Pipeline</h3>';
  html+='<span class="section-meta">'+projCount.toLocaleString('en-CA')+' projects \u00B7 '+san(pipelineValueDisplay)+'</span></div>';
  if(relatedProjects.length){
    var sortedProj=relatedProjects.slice().sort(function(a,b){
      var va=parseFloat(String(a.value||'').replace(/[^0-9.]/g,''))||0;
      var vb=parseFloat(String(b.value||'').replace(/[^0-9.]/g,''))||0;
      return vb-va;
    }).slice(0,10);
    html+='<div class="indicator-panel" style="padding:0"><table class="projects-table"><thead><tr>';
    html+='<th>Project</th><th>Province</th><th>Value</th><th>Status</th></tr></thead><tbody>';
    sortedProj.forEach(function(p){
      var status=p.status||'Unknown';
      var statusCls='status-proposed';
      if(/construction|build/i.test(status))statusCls='status-construction';
      else if(/review|planning/i.test(status))statusCls='status-review';
      else if(/pre/i.test(status))statusCls='status-pre';
      var valNum=parseFloat(String(p.value||'').replace(/[^0-9.]/g,''))||0;
      var valStr=valNum?'$'+fmtNum(valNum)+'M':(p.value||'\u2014');
      html+='<tr><td><span class="ind-name">'+san(p.name||'Unknown')+'</span></td>';
      html+='<td>'+san(p.province||'\u2014')+'</td>';
      html+='<td class="ind-val">'+san(valStr)+'</td>';
      html+='<td><span class="status-badge '+statusCls+'">'+san(status)+'</span></td></tr>';
    });
    html+='</tbody></table></div></div>';
  }else{
    html+='<div class="narrative"><p>No tracked projects for '+san(name)+'.</p></div></div>';
  }

  mainEl.innerHTML=html;

  // Post-render: insight chart callout — consume industry.insightCharts[0] (produced by tldr-charts skill)
  var chartArea=$('indInsightChartArea');
  if(chartArea){
    var icSpec=(industry.insightCharts&&industry.insightCharts[0])||null;
    if(icSpec&&icSpec.dataKeys&&icSpec.dataKeys.length){
      chartArea.innerHTML=buildIndInsightStrip(icSpec);
      // Defer Chart.js render one tick so the canvas is attached to the DOM
      setTimeout(function(){renderIndInsightChart(icSpec)},50);
    }else{
      chartArea.innerHTML='<div class="tldr-callout" style="margin:20px 0"><div style="font-family:\'Inter\',sans-serif;font-size:14px;line-height:1.6;color:#64748B">No insight chart available for '+san(name)+' this week.</div></div>';
    }
  }
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
  const yAxes={y:{position:'left',grid:{color:'rgba(0,0,0,0.05)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'Inter',size:11},color:'#636363',callback:v=>st.mode==='pct'?v.toFixed(1)+'%':fmtNum(v)}}};
  if(useDualAxis){
    datasets[0].yAxisID='y';datasets[1].yAxisID='y1';
    yAxes.y1={position:'right',grid:{display:false},ticks:{font:{family:'Inter',size:11},color:datasets[1].borderColor,callback:v=>fmtNum(v)}};
    yAxes.y.ticks.color=datasets[0].borderColor;
  }
  charts[cid]=new Chart(canvas,{type:'line',data:{datasets},options:{
    responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    plugins:{
      legend:{display:datasets.length>1,position:'top',labels:{boxWidth:12,padding:8,font:{family:'Inter',size:11},usePointStyle:true,pointStyle:'circle'}},
      tooltip:{backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8,
        callbacks:{label:ctx=>{const v=ctx.parsed.y;return ctx.dataset.label+': '+(st.mode==='pct'?v.toFixed(2)+'%':fmtNum(v))}}}
    },
    scales:{x:{type:'time',time:{unit:rangeMonths<=3?'week':rangeMonths<=12?'month':'quarter',tooltipFormat:'MMM d, yyyy',displayFormats:{week:'MMM d',month:'MMM yyyy',quarter:'QQQ yyyy'}},grid:{display:false},ticks:{font:{family:'Inter',size:10},color:'#636363',maxTicksLimit:rangeMonths<=6?10:8}},...yAxes}
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
  for(var g=0;g<3;g++){var gy=pT+(g/2)*pH;var gv=mx-(g/2)*rng;s+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="#e8ecf0" stroke-width="1"/>';s+='<text x="'+(pL-6)+'" y="'+(gy+4)+'" fill="#7a8599" font-size="10" font-family="\'Inter\',sans-serif" text-anchor="end">'+_svgFmtVal(gv)+'</text>';}
  var poly=pts.map(function(p){return p.x+','+p.y}).join(' ');
  var lp=pts[pts.length-1],fp=pts[0],bot=pT+pH;
  s+='<path d="M'+fp.x+','+fp.y+' '+pts.slice(1).map(function(p){return 'L'+p.x+','+p.y}).join(' ')+' L'+lp.x+','+bot+' L'+fp.x+','+bot+' Z" fill="url(#'+fid+')"/>';
  s+='<polyline points="'+poly+'" fill="none" stroke="'+color+'" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>';
  s+='<circle cx="'+lp.x+'" cy="'+lp.y+'" r="4" fill="'+color+'" stroke="#fff" stroke-width="2"/>';
  var lc=Math.min(4,series.length);
  for(var li=0;li<lc;li++){var idx=Math.round(li/(lc-1)*(series.length-1));var anc=li===0?'start':li===lc-1?'end':'middle';var dl=li===lc-1?'Now':_svgFmtDate(series[idx].date);s+='<text x="'+pts[idx].x+'" y="'+(H-5)+'" fill="#7a8599" font-size="10" font-family="\'Inter\',sans-serif" text-anchor="'+anc+'">'+dl+'</text>';}
  s+='</svg>';return s;
}
function _svgFmtVal(v){if(Math.abs(v)>=10000)return(v/1000).toFixed(0)+'k';if(Math.abs(v)>=1000)return v.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',');if(Math.abs(v)>=1)return v.toFixed(2);return v.toFixed(4)}
function _svgFmtDate(d){try{var dt=new Date(d);return dt.toLocaleDateString('en-CA',{month:'short'})}catch(e){return d}}

/* Editorial SVG chart — editorial sibling of _svgCalloutChart (markets + explorer).
   Shares typography, grid, y-axis, source line of the callout chart family, but:
   no cream wrapper, thin 60x2 brand rule instead of the 48x5 brand tab, no area
   fill under the line, no annotation flags, and includes a mousemove hover tooltip. */
var _edChartStore={};var _edChartUid=0;
function _svgEditorialChart(series,opts){
  opts=opts||{};
  var H=opts.height||360;
  if(!series||!series.length)return'<div style="height:'+H+'px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No data available</div>';
  var W=1100,PAD_TOP=14,PAD_BOT=32;
  var pL=0,pR=48,pT=96,pB=82;
  var pW=W-pL-pR,pH=H-pT-pB;
  var BRAND=opts.color||'#003153',INK='#0f172a',MUTED='#4a5568',GRID='#e8ecf0',BASELINE='#cbd5e1';
  var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  function fmtVal(v){if(opts.valueFmt)return opts.valueFmt(v);return _svgFmtVal(v).replace(/\.00$/,'')}
  function fmtDate(iso){try{var d=new Date(iso);return MONTHS[d.getUTCMonth()]+' '+d.getUTCDate()+' '+d.getUTCFullYear()}catch(e){return String(iso)}}
  var sorted=series.slice().sort(function(a,b){return new Date(a.date)-new Date(b.date)});
  var vals=sorted.map(function(p){return p.value}).filter(function(v){return v!=null&&!isNaN(v)});
  if(vals.length<2)return'<div style="height:'+H+'px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">Insufficient data</div>';
  var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals),rng=mx-mn;
  if(rng===0)rng=Math.abs(mn)*0.1||1;
  var dataMin=mn;
  if(dataMin>0)mn=Math.max(0,dataMin-rng*0.25);
  else if(dataMin<0)mn-=rng*0.25;
  mx+=rng*0.14;rng=mx-mn;
  function xp(i){return pL+(i/Math.max(sorted.length-1,1))*pW}
  function yp(v){return pT+(1-(v-mn)/rng)*pH}
  var base_y=pT+pH;
  function smoothPath(pts){
    if(pts.length<2)return'';
    if(pts.length===2)return'M'+pts[0][0].toFixed(1)+','+pts[0][1].toFixed(1)+' L'+pts[1][0].toFixed(1)+','+pts[1][1].toFixed(1);
    var d='M'+pts[0][0].toFixed(1)+','+pts[0][1].toFixed(1);
    for(var i=0;i<pts.length-1;i++){
      var p0=i>0?pts[i-1]:pts[i];
      var p1=pts[i],p2=pts[i+1];
      var p3=i+2<pts.length?pts[i+2]:pts[i+1];
      var cp1x=p1[0]+(p2[0]-p0[0])/6,cp1y=p1[1]+(p2[1]-p0[1])/6;
      var cp2x=p2[0]-(p3[0]-p1[0])/6,cp2y=p2[1]-(p3[1]-p1[1])/6;
      d+=' C'+cp1x.toFixed(1)+','+cp1y.toFixed(1)+' '+cp2x.toFixed(1)+','+cp2y.toFixed(1)+' '+p2[0].toFixed(1)+','+p2[1].toFixed(1);
    }
    return d;
  }
  var pts=sorted.map(function(p,i){return[xp(i),yp(p.value==null?mn:p.value)]});
  var hoverPoints=sorted.map(function(p,i){return{x:pts[i][0],y:pts[i][1],label:fmtDate(p.date),val:p.value==null?'\u2014':fmtVal(p.value)}});
  var chartId='edChart_'+(++_edChartUid);
  _edChartStore[chartId]={points:hoverPoints};
  var svg='<svg id="'+chartId+'" class="editorial-chart" viewBox="0 0 '+W+' '+H+'" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;font-family:\'Inter\',-apple-system,sans-serif;overflow:visible" role="img" aria-label="'+esc(opts.title||'Chart')+'" onmousemove="_edChartHover(event,this)" onmouseleave="_edChartLeave(this)">';
  svg+='<rect x="0" y="'+PAD_TOP+'" width="60" height="2" fill="#E3120B"/>';
  var _ck=opts.kicker||'';
  var _ttlY=PAD_TOP+30;
  if(_ck){
    svg+='<text x="0" y="'+(PAD_TOP+18)+'" font-size="10" font-weight="700" fill="'+INK+'" letter-spacing="1.4">'+esc(_ck.toUpperCase())+'</text>';
    _ttlY=PAD_TOP+42;
  }
  svg+='<text x="0" y="'+_ttlY+'" font-size="22" font-weight="700" fill="'+INK+'" letter-spacing="-0.3" font-family="Inter,sans-serif">'+esc(opts.title||'')+'</text>';
  if(opts.subtitle)svg+='<text x="0" y="'+(_ttlY+22)+'" font-size="13" font-weight="500" font-style="italic" fill="'+MUTED+'" font-family="Inter,sans-serif">'+esc(opts.subtitle)+'</text>';
  for(var g=0;g<=4;g++){
    var gy=pT+(g/4)*pH;
    var gv=mx-(g/4)*rng;
    svg+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="'+GRID+'" stroke-width="1"/>';
    svg+='<text x="'+(W-pR+8)+'" y="'+(gy+4)+'" text-anchor="start" font-size="11" font-weight="400" fill="'+MUTED+'" style="font-variant-numeric:tabular-nums">'+fmtVal(gv)+'</text>';
  }
  svg+='<line x1="'+pL+'" y1="'+base_y+'" x2="'+(W-pR)+'" y2="'+base_y+'" stroke="'+BASELINE+'" stroke-width="1"/>';
  var NT=Math.min(6,sorted.length);
  for(var xi=0;xi<NT;xi++){
    var di=Math.round((xi/Math.max(NT-1,1))*(sorted.length-1));
    var dx=xp(di);
    var dObj=new Date(sorted[di].date);
    var lbl=MONTHS[dObj.getUTCMonth()];
    if(xi===0||dObj.getUTCMonth()===0)lbl=MONTHS[dObj.getUTCMonth()]+'\u2009'+dObj.getUTCFullYear();
    var xAnc=xi===0?'start':(xi===NT-1?'end':'middle');
    svg+='<text x="'+dx+'" y="'+(base_y+22)+'" text-anchor="'+xAnc+'" font-size="11" font-weight="400" fill="'+MUTED+'">'+lbl+'</text>';
  }
  svg+='<path d="'+smoothPath(pts)+'" fill="none" stroke="'+BRAND+'" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>';
  var last=pts[pts.length-1];
  svg+='<circle cx="'+last[0]+'" cy="'+last[1]+'" r="4" fill="'+BRAND+'"/>';
  var srcText=opts.source||'Source: The Lagging Indicator';
  svg+='<text x="0" y="'+(H-PAD_BOT-2)+'" font-size="10" font-weight="500" font-style="italic" fill="'+MUTED+'">'+esc(srcText)+'</text>';
  svg+='<g class="ed-hover-layer" opacity="0" pointer-events="none">';
  svg+='<line class="ed-hover-line" x1="0" y1="'+pT+'" x2="0" y2="'+base_y+'" stroke="'+INK+'" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>';
  svg+='<circle class="ed-hover-dot" r="5" fill="'+BRAND+'" stroke="#ffffff" stroke-width="2"/>';
  svg+='<rect class="ed-hover-tt-bg" width="160" height="40" rx="4" fill="#0f172a" opacity="0.92"/>';
  svg+='<text class="ed-hover-tt-date" font-size="10" fill="#cbd5e1" font-family="\'Inter\',sans-serif"></text>';
  svg+='<text class="ed-hover-tt-val" font-size="14" font-weight="700" fill="#ffffff" font-family="\'Inter\',sans-serif" style="font-variant-numeric:tabular-nums"></text>';
  svg+='</g>';
  svg+='<rect x="'+pL+'" y="'+pT+'" width="'+pW+'" height="'+pH+'" fill="transparent"/>';
  svg+='</svg>';
  return svg;
}
window._edChartHover=function(evt,svg){
  var store=_edChartStore[svg.id];
  if(!store||!store.points||!store.points.length)return;
  var rect=svg.getBoundingClientRect();
  var vb=svg.getAttribute('viewBox').split(' ');
  var vbW=parseFloat(vb[2]);
  var x=(evt.clientX-rect.left)*(vbW/rect.width);
  var best=0,bd=Infinity;
  for(var i=0;i<store.points.length;i++){
    var d=Math.abs(store.points[i].x-x);
    if(d<bd){bd=d;best=i}
  }
  var p=store.points[best];
  var layer=svg.querySelector('.ed-hover-layer');
  if(!layer)return;
  layer.setAttribute('opacity','1');
  var line=layer.querySelector('.ed-hover-line');
  line.setAttribute('x1',p.x);line.setAttribute('x2',p.x);
  var dot=layer.querySelector('.ed-hover-dot');
  dot.setAttribute('cx',p.x);dot.setAttribute('cy',p.y);
  var ttX=p.x+12,ttY=p.y-48;
  if(ttX+160>vbW-48)ttX=p.x-172;
  if(ttY<90)ttY=p.y+14;
  var ttBg=layer.querySelector('.ed-hover-tt-bg');
  ttBg.setAttribute('x',ttX);ttBg.setAttribute('y',ttY);
  var ttDate=layer.querySelector('.ed-hover-tt-date');
  ttDate.setAttribute('x',ttX+10);ttDate.setAttribute('y',ttY+16);
  ttDate.textContent=p.label;
  var ttVal=layer.querySelector('.ed-hover-tt-val');
  ttVal.setAttribute('x',ttX+10);ttVal.setAttribute('y',ttY+32);
  ttVal.textContent=p.val;
};
window._edChartLeave=function(svg){
  var layer=svg.querySelector('.ed-hover-layer');
  if(layer)layer.setAttribute('opacity','0');
};

function _svgYieldCurve(yc,ycPrev){
  if(!yc||!yc.length)return'';
  var W=1100,H=360,PAD_TOP=14,PAD_BOT=32;
  var pL=0,pR=48,pT=96,pB=82;
  var pW=W-pL-pR,pH=H-pT-pB;
  var BRAND='#003153',PREV='#c4320a',INK='#0f172a',MUTED='#4a5568',GRID='#e8ecf0',BASELINE='#cbd5e1';
  var data=yc.map(function(y){return parseFloat(y.yield)||0});
  var allVals=data.slice();if(ycPrev&&ycPrev.length)allVals=allVals.concat(ycPrev);
  var mn=Math.min.apply(null,allVals),mx=Math.max.apply(null,allVals),rng=mx-mn;
  if(rng===0)rng=1;mn-=rng*0.2;mx+=rng*0.18;rng=mx-mn;
  var n=yc.length;
  var xPts=yc.map(function(y,i){return pL+(i/Math.max(n-1,1))*pW});
  function yPos(v){return pT+(1-(v-mn)/rng)*pH}
  var base_y=pT+pH;
  var s='<svg viewBox="0 0 '+W+' '+H+'" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;font-family:\'Inter\',-apple-system,sans-serif;overflow:visible" role="img" aria-label="Government of Canada yield curve">';
  s+='<rect x="0" y="'+PAD_TOP+'" width="60" height="2" fill="#E3120B"/>';
  s+='<text x="0" y="'+(PAD_TOP+18)+'" font-size="10" font-weight="700" fill="'+INK+'" letter-spacing="1.4">INTEREST RATES \u00b7 CANADA</text>';
  s+='<text x="0" y="'+(PAD_TOP+42)+'" font-size="22" font-weight="700" fill="'+INK+'" letter-spacing="-0.3" font-family="Inter,sans-serif">Yield curve</text>';
  s+='<text x="0" y="'+(PAD_TOP+64)+'" font-size="13" font-weight="500" font-style="italic" fill="'+MUTED+'" font-family="Inter,sans-serif">Government of Canada benchmark bonds</text>';
  for(var g=0;g<=4;g++){
    var gy=pT+(g/4)*pH;
    var gv=mx-(g/4)*rng;
    s+='<line x1="'+pL+'" y1="'+gy+'" x2="'+(W-pR)+'" y2="'+gy+'" stroke="'+GRID+'" stroke-width="1"/>';
    s+='<text x="'+(W-pR+8)+'" y="'+(gy+4)+'" text-anchor="start" font-size="11" font-weight="400" fill="'+MUTED+'" style="font-variant-numeric:tabular-nums">'+gv.toFixed(1)+'%</text>';
  }
  s+='<line x1="'+pL+'" y1="'+base_y+'" x2="'+(W-pR)+'" y2="'+base_y+'" stroke="'+BASELINE+'" stroke-width="1"/>';
  yc.forEach(function(y,i){s+='<text x="'+xPts[i]+'" y="'+(base_y+22)+'" text-anchor="middle" font-size="11" font-weight="400" fill="'+MUTED+'">'+y.term+'</text>'});
  if(ycPrev&&ycPrev.length>=n){
    var prevPoly=xPts.map(function(x,i){return x.toFixed(1)+','+yPos(ycPrev[i]).toFixed(1)}).join(' ');
    s+='<polyline points="'+prevPoly+'" fill="none" stroke="'+PREV+'" stroke-width="2" stroke-dasharray="5,4" stroke-linejoin="round" stroke-linecap="round"/>';
    xPts.forEach(function(x,i){s+='<circle cx="'+x.toFixed(1)+'" cy="'+yPos(ycPrev[i]).toFixed(1)+'" r="3" fill="'+PREV+'"/>';});
  }
  var curPoly=xPts.map(function(x,i){return x.toFixed(1)+','+yPos(data[i]).toFixed(1)}).join(' ');
  s+='<polyline points="'+curPoly+'" fill="none" stroke="'+BRAND+'" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>';
  xPts.forEach(function(x,i){s+='<circle cx="'+x.toFixed(1)+'" cy="'+yPos(data[i]).toFixed(1)+'" r="4.5" fill="'+BRAND+'" stroke="#ffffff" stroke-width="2"/>';});
  if(ycPrev&&ycPrev.length>=n){
    var lgX=W-pR-260,lgY=pT+14;
    s+='<line x1="'+lgX+'" y1="'+lgY+'" x2="'+(lgX+22)+'" y2="'+lgY+'" stroke="'+BRAND+'" stroke-width="2.8"/>';
    s+='<text x="'+(lgX+28)+'" y="'+(lgY+4)+'" font-size="11" font-weight="500" fill="'+MUTED+'">Current</text>';
    s+='<line x1="'+(lgX+100)+'" y1="'+lgY+'" x2="'+(lgX+122)+'" y2="'+lgY+'" stroke="'+PREV+'" stroke-width="2" stroke-dasharray="5,4"/>';
    s+='<text x="'+(lgX+128)+'" y="'+(lgY+4)+'" font-size="11" font-weight="500" fill="'+MUTED+'">1 year ago</text>';
  }
  s+='<text x="0" y="'+(H-PAD_BOT-2)+'" font-size="10" font-weight="500" font-style="italic" fill="'+MUTED+'">Source: Bank of Canada</text>';
  s+='</svg>';
  return s;
}

async function _mktRenderSvg(key){
  var st=_mktState[key];if(!st)return;
  var chartDiv=document.getElementById('mktSvg_'+key);if(!chartDiv)return;
  var activeName=[].concat(Array.from(st.active))[0];
  var item=st.items.find(function(it){return it.name===activeName});
  if(!item){chartDiv.innerHTML='<div style="height:360px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">Select a series</div>';return;}
  var tsId=_mktTsMap[item.name]||'';
  var ts=await loadTimeseries(tsId);
  if(!ts){chartDiv.innerHTML='<div style="height:360px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No timeseries data for '+item.name+'</div>';return;}
  var raw=ts.series||ts;if(!Array.isArray(raw)){chartDiv.innerHTML='';return;}
  var rangeMonths=st.range||3;
  var cutoff=rangeMonths>0?(function(){var d=new Date();d.setMonth(d.getMonth()-rangeMonths);return d})():new Date('1900-01-01');
  var filtered=raw.filter(function(p){return new Date(p.date)>=cutoff}).sort(function(a,b){return new Date(a.date)-new Date(b.date)});
  if(!filtered.length){chartDiv.innerHTML='<div style="height:360px;display:flex;align-items:center;justify-content:center;color:#7a8599;font-size:13px">No data in selected range</div>';return;}
  var rangeLabel=rangeMonths===1?'1 month':rangeMonths===3?'3 months':rangeMonths===6?'6 months':rangeMonths===12?'1 year':rangeMonths===36?'3 years':rangeMonths+' months';
  var srcMap={equities:'Source: Yahoo Finance',fx:'Source: Bank of Canada',commodities:'Source: EIA, LME, LBMA'};
  var kickerMap={equities:'Equity indices',fx:'Foreign exchange',commodities:'Commodities'};
  var source=srcMap[key]||'Source: Market data';
  chartDiv.innerHTML=_svgEditorialChart(filtered,{
    title:item.name,
    subtitle:'Last '+rangeLabel,
    source:source,
    color:'#003153',
    height:360,
    kicker:kickerMap[key]||''
  });
}

/* Single-select pill handler for SVG charts */
window._mktSelectPill=function(pill){
  var name=pill.dataset.name,key=pill.dataset.key;
  var st=_mktState[key];if(!st)return;
  st.active=new Set([name]);
  pill.parentElement.querySelectorAll('.series-pill,.fx-pill').forEach(function(p){p.classList.toggle('active',p.dataset.name===name)});
  _mktRenderSvg(key);
  // Update per-index equity commentary when pill changes
  if(key==='equities'){
    var commEl=document.getElementById('mktEquityCommentary');
    if(commEl&&st.items){
      var sel=st.items.find(function(it){return it.name===name});
      var comm=sel&&sel.commentary?sel.commentary:'';
      commEl.innerHTML=comm?'<div class="market-narrative">'+DOMPurify.sanitize(comm,{ADD_ATTR:['target']})+'</div>':'';
    }
  }
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
  h+='<div class="narrative">'+_editorialProse(san(summary))+'</div>';
  // Market callout box — pipeline cross-reference data (project counts + dollar values)
  var calloutData=(fm.callout||(D&&D.marketCommentaryCallout))||null;
  if(calloutData&&calloutData.title&&Array.isArray(calloutData.items)&&calloutData.items.length){
    h+='<div class="inner-card" style="margin-top:16px;padding:16px 20px;border-left:3px solid #003153">';
    h+='<div style="font-family:Inter,sans-serif;font-weight:700;font-size:15px;color:#1a2744;margin-bottom:10px">'+san(calloutData.title)+'</div>';
    h+='<div style="display:flex;flex-wrap:wrap;gap:20px">';
    calloutData.items.forEach(function(ci){
      h+='<div style="flex:1;min-width:140px">';
      h+='<div style="font-family:Inter,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;color:#64748B;margin-bottom:4px">'+san(ci.label||'')+'</div>';
      h+='<div style="font-family:Inter,sans-serif;font-size:22px;font-weight:700;color:#1a2744;line-height:1.2">'+san(ci.value||'')+'</div>';
      if(ci.amount)h+='<div style="font-family:Inter,sans-serif;font-size:13px;color:#003153;margin-top:2px">'+san(ci.amount)+'</div>';
      h+='</div>';
    });
    h+='</div></div>';
  }
  h+='</div>';
  return h;
}

function _buildMktEquities(fm){
  var indices=fm.indices||[];
  if(!indices.length&&indicators.length){
    [{name:'S&P/TSX',ind:'tsx_composite'},{name:'S&P/TSX',ind:'tsx'},{name:'S&P 500',ind:'sp500'},{name:'Dow Jones',ind:'djia'},{name:'NASDAQ',ind:'nasdaq'},{name:'FTSE 100',ind:'ftse100'},{name:'DAX',ind:'dax'},{name:'Nikkei 225',ind:'nikkei225'}].forEach(function(m){var i=indicators.find(function(x){return x.indicator_name===m.ind});if(i&&!indices.find(function(x){return x.name===m.name}))indices.push({name:m.name,value:i.value,change:'',region:''})});
  }
  if(!indices.length)return '';
  var items=indices.map(function(it){return{name:it.name,value:it.value||it.val||it.price||'',change:it.change||it.day||'',mm:it.mm||'',yy:it.yy||'',commentary:it.commentary||''}});
  var defaults=[items[0].name];
  _mktState.equities={items:items,active:new Set(defaults),mode:'price',range:3,freq:'all'};

  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Equity Indices</h3>';
  h+='<span class="section-meta">'+items.length+' indices \u00B7 changes shown 1W / 1M / 1Y</span></div><div class="market-card">';
  h+='<div class="series-row">';
  items.forEach(function(it){
    var act=defaults.indexOf(it.name)>=0;
    h+='<div class="series-pill'+(act?' active':'')+'" data-name="'+it.name+'" data-key="equities" onclick="_mktSelectPill(this)">';
    h+='<div class="pill-name">'+it.name+'</div><div class="pill-value">'+(it.value||'\u2014')+'</div>';
    h+='<div class="pill-changes-row">';
    if(hasVal(it.change))h+='<div class="pill-chg-item"><span class="pill-chg-label">1W</span><span class="pill-chg-val '+_chgCls(it.change)+'">'+it.change+'</span></div>';
    if(hasVal(it.mm))h+='<div class="pill-chg-item"><span class="pill-chg-label">1M</span><span class="pill-chg-val '+_chgCls(it.mm)+'">'+it.mm+'</span></div>';
    if(hasVal(it.yy))h+='<div class="pill-chg-item"><span class="pill-chg-label">1Y</span><span class="pill-chg-val '+_chgCls(it.yy)+'">'+it.yy+'</span></div>';
    h+='</div></div>';
  });
  h+='</div>';
  h+='<div class="chart-controls"><div class="range-selector">';
  [{m:1,l:'1M'},{m:3,l:'3M'},{m:6,l:'6M'},{m:12,l:'1Y'},{m:36,l:'3Y'}].forEach(function(r){
    h+='<button class="range-btn'+(r.m===3?' active':'')+'" data-range="'+r.m+'" data-key="equities" onclick="_mktSvgSetRange(this)">'+r.l+'</button>';
  });
  h+='</div></div>';
  h+='<div class="chart-area" id="mktSvg_equities"></div>';
  // Per-index commentary — show the selected index's commentary text
  var initComm=items.length&&items[0].commentary?items[0].commentary:'';
  h+='<div class="mkt-equity-commentary" id="mktEquityCommentary">';
  if(initComm)h+='<div class="market-narrative">'+san(initComm)+'</div>';
  h+='</div>';
  h+='</div></div>';
  return h;
}

function _buildMktFx(fm){
  var fx=fm.fx||[];
  if(!fx.length&&indicators.length){
    [{name:'CAD/USD',ind:'cad_usd'},{name:'CAD/USD',ind:'cadusd'},{name:'EUR/USD',ind:'eurusd'},{name:'USD/CNY',ind:'usdcny'},{name:'USD/JPY',ind:'usdjpy'}].forEach(function(m){var i=indicators.find(function(x){return x.indicator_name===m.ind});if(i&&!fx.find(function(x){return x.name===m.name}))fx.push({name:m.name,value:i.value})});
  }
  if(!fx.length)return '';
  var items=fx.map(function(it){return{name:it.name,value:it.value||it.val||it.price||'',change:it.day||it.change||'',mm:it.mm||'',yy:it.yy||''}});
  var defaults=[items[0].name];
  _mktState.fx={items:items,active:new Set(defaults),mode:'price',range:3,freq:'all'};

  var h='<div class="section-block"><div class="section-header"><div class="accent-bar"></div><h3>Foreign Exchange</h3>';
  h+='<span class="section-meta">'+items.length+' pairs \u00B7 changes shown 1W / 1M / 1Y</span></div><div class="market-card">';
  h+='<div class="fx-series-row">';
  items.forEach(function(it){
    var act=defaults.indexOf(it.name)>=0;
    h+='<div class="fx-pill'+(act?' active':'')+'" data-name="'+it.name+'" data-key="fx" onclick="_mktSelectPill(this)">';
    h+='<div class="pill-name">'+it.name+'</div><div class="pill-value">'+(it.value||'\u2014')+'</div>';
    h+='<div class="pill-changes-row">';
    if(hasVal(it.change))h+='<div class="pill-chg-item"><span class="pill-chg-label">1W</span><span class="pill-chg-val '+_chgCls(it.change)+'">'+it.change+'</span></div>';
    if(hasVal(it.mm))h+='<div class="pill-chg-item"><span class="pill-chg-label">1M</span><span class="pill-chg-val '+_chgCls(it.mm)+'">'+it.mm+'</span></div>';
    if(hasVal(it.yy))h+='<div class="pill-chg-item"><span class="pill-chg-label">1Y</span><span class="pill-chg-val '+_chgCls(it.yy)+'">'+it.yy+'</span></div>';
    h+='</div></div>';
  });
  h+='</div>';
  var bocRate=(fm.bocRate||fm.boc_rate||(D&&D.bocRate))||'';
  if(bocRate){
    h+='<div class="stat-row">';
    h+='<div class="stat-item"><span class="stat-label">Bank of Canada Rate</span><span class="stat-val">'+bocRate+'</span></div>';
    h+='</div>';
  }
  h+='<div class="chart-controls"><div class="range-selector">';
  [{m:1,l:'1M'},{m:3,l:'3M'},{m:6,l:'6M'},{m:12,l:'1Y'},{m:36,l:'3Y'}].forEach(function(r){
    h+='<button class="range-btn'+(r.m===3?' active':'')+'" data-range="'+r.m+'" data-key="fx" onclick="_mktSvgSetRange(this)">'+r.l+'</button>';
  });
  h+='</div></div>';
  h+='<div class="chart-area" id="mktSvg_fx"></div>';
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
  // WCS Discount Analysis — render from D.wcs_analysis (dict) or D.wcsAnalysis (HTML string)
  var wcsObj=D&&D.wcs_analysis?D.wcs_analysis:null;
  var wcsHtml=D&&D.wcsAnalysis?D.wcsAnalysis:'';
  if(wcsObj&&wcsObj.narrative){
    h+='<div class="section-header" style="margin-top:20px"><div class="accent-bar"></div><h4>WCS Discount Analysis</h4></div>';
    h+='<div class="market-narrative">'+san(wcsObj.narrative);
    if(wcsObj.current_discount)h+='<br><strong>Current discount:</strong> '+san(wcsObj.current_discount);
    if(wcsObj.prior_discount)h+=' &middot; <strong>Prior:</strong> '+san(wcsObj.prior_discount);
    if(wcsObj.direction)h+=' &middot; <strong>Direction:</strong> '+san(wcsObj.direction);
    if(wcsObj.estimated_wcs_price)h+=' &middot; <strong>Est. WCS:</strong> '+san(wcsObj.estimated_wcs_price);
    h+='</div>';
  }else if(wcsHtml){
    h+='<div class="section-header" style="margin-top:20px"><div class="accent-bar"></div><h4>WCS Discount Analysis</h4></div>';
    h+='<div class="market-narrative">'+san(wcsHtml)+'</div>';
  }
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
  charts.yield=new Chart(canvas,{type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.08)',borderWidth:2,pointRadius:4,pointBackgroundColor:'#3B82F6',pointBorderColor:'#3B82F6',pointBorderWidth:2,fill:true,tension:0.3}]},plugins:[{id:'yieldEndpoint',afterDraw(chart){const ds=chart.data.datasets[0];const lastVal=ds.data[ds.data.length-1];const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 11px Inter';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal,2)+'%':lastVal,lastPt.x+6,lastPt.y-4);ctx.restore();}}],options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(45,75,130,0.95)',titleColor:'#ffffff',bodyColor:'#93C5FD',borderColor:'rgba(0,0,0,0.12)',borderWidth:1,padding:10,cornerRadius:6}},scales:{x:{grid:{display:false},ticks:{font:{family:'Inter',size:11},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'Inter',size:11},color:'#636363',callback:v=>fmtNum(v,2)+'%'}}}}});
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
          lcEvtAnnotations['evt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(245,158,11,0.5)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(evt.event_name||evt.name||'').substring(0,20),position:'start',backgroundColor:'rgba(245,158,11,0.85)',color:'#fff',font:{family:'Inter',size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
        }catch(e2){}
      });
    }
  }catch(e3){console.warn('Line chart event annotations:',e3)}
  const lcHasAnnotation=typeof window.ChartAnnotation!=='undefined'||Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation');
  const lcAnnotationCfg=lcHasAnnotation&&Object.keys(lcEvtAnnotations).length?{annotation:{annotations:{...lcEvtAnnotations}}}:{};
  charts[canvasId]=new Chart(canvas,{type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.06)',borderWidth:2,pointRadius:3,pointBackgroundColor:'#3B82F6',fill:true,tension:0.3}]},plugins:[{id:'lineEndpoint',afterDraw(chart){const ds=chart.data.datasets[0];const lastVal=ds.data[ds.data.length-1];const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 10px Outfit';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):lastVal,lastPt.x+4,lastPt.y-4);ctx.restore();}}],options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},...lcAnnotationCfg},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:6,font:{family:'Inter',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'Inter',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}});
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
  // Populate filter dropdowns (sync, before any data load)
  const provSel=$('filterProvince');
  if(provSel.options.length<=1){
    PROVS.forEach(p=>{const o=document.createElement('option');o.value=p.code;o.textContent=p.name;provSel.appendChild(o)});
  }
  const secSel=$('filterSector');
  if(secSel.options.length<=1){
    NAICS_CODES.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c+' '+NAICS_NAMES[c];secSel.appendChild(o)});
  }
  const stSel=$('filterStatus');
  if(stSel.options.length<=1){
    STATUSES.forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=s;stSel.appendChild(o)});
  }
  // Lazy load: default to Ontario (largest province, ~1.7 MB) instead of 6 MB projects_all.json
  if(!allProjects.length){
    const initProv=provSel.value||'ON';
    provSel.value=initProv;  // sync dropdown UI with loaded data to prevent double-load bug
    await loadProjects(initProv);
    populateCmaFilter();
  }
  // Event listeners
  $('projectSearch').oninput=filterProjects;
  $('filterProvince').onchange=filterProjects;
  $('filterCma').onchange=filterProjects;
  $('filterSector').onchange=filterProjects;
  $('filterStatus').onchange=filterProjects;
  $('sortProjects').onchange=filterProjects;
  $('filterNew').onchange=filterProjects;
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
function populateCmaFilter(){
  const sel=$('filterCma');
  if(!sel)return;
  const current=sel.value;
  const cmas=Array.from(new Set(allProjects.map(p=>(p.cma||'').trim()).filter(Boolean))).sort((a,b)=>a.localeCompare(b));
  sel.innerHTML='<option value="">All CMAs</option>'+cmas.map(c=>'<option value="'+c.replace(/"/g,'&quot;')+'">'+c+'</option>').join('');
  if(current&&cmas.includes(current))sel.value=current;
}
async function filterProjects(){
  const search=($('projectSearch').value||'').toLowerCase();
  const prov=$('filterProvince').value||null;
  const cma=$('filterCma').value;
  const sector=$('filterSector').value;
  const status=$('filterStatus').value;
  const sort=$('sortProjects').value;
  const newDays=parseInt(($('filterNew')&&$('filterNew').value)||'',10);
  let newCutoff=null;
  if(newDays>0){const d=new Date();d.setDate(d.getDate()-newDays);newCutoff=d.toISOString().split('T')[0];}
  // If province changed, reload from static JSON (lazy load)
  if(prov!==_lastLoadedProvince){
    await loadProjects(prov);
    populateCmaFilter();
    filterProjects();
    return;
  }
  filteredProjects=allProjects.filter(p=>{
    if(_confirmedOnly&&!meetsThreshold(p))return false;
    if(search&&!(p.name||'').toLowerCase().includes(search)&&!(p.cma||'').toLowerCase().includes(search)&&!(p.proponent||'').toLowerCase().includes(search))return false;
    if(prov&&normProvince(p.province)!==prov)return false;
    if(cma&&(p.cma||'').trim()!==cma)return false;
    if(sector&&p.naics_code!==sector&&!(NAICS_NAMES[sector]&&(NAICS_NAMES[sector].toLowerCase().includes((p.sector||'').replace(/_/g,' ').toLowerCase())||(p.sector||'').toLowerCase().includes(NAICS_NAMES[sector].toLowerCase().split(',')[0].trim().toLowerCase()))))return false;
    if(status&&p.status!==status)return false;
    if(newCutoff&&!(p.firstTracked&&p.firstTracked>=newCutoff))return false;
    return true;
  });
  if(sort==='new_updated'){
    // Projects newly added or updated in the most recent run first
    // (firstTracked / lastUpdated == the latest such date in the dataset),
    // then everything else by value.
    let maxD='';
    for(const p of allProjects){
      if(p.firstTracked&&p.firstTracked>maxD)maxD=p.firstTracked;
      if(p.lastUpdated&&p.lastUpdated>maxD)maxD=p.lastUpdated;
    }
    const isRecent=p=>maxD&&((p.firstTracked&&p.firstTracked>=maxD)||(p.lastUpdated&&p.lastUpdated>=maxD));
    filteredProjects.sort((a,b)=>{
      const ra=isRecent(a)?1:0,rb=isRecent(b)?1:0;
      if(ra!==rb)return rb-ra;
      return parseNumericValue(b.value)-parseNumericValue(a.value);
    });
  }
  else if(sort==='value_desc')filteredProjects.sort((a,b)=>parseNumericValue(b.value)-parseNumericValue(a.value));
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
  const approved=filteredProjects.filter(p=>{const s=(p.status||'').toLowerCase();return s.includes('approved')&&!s.includes('construction')}).length;
  const oneWeekAgo=new Date();oneWeekAgo.setDate(oneWeekAgo.getDate()-7);
  const oneWeekStr=oneWeekAgo.toISOString().split('T')[0];
  const newCount=filteredProjects.filter(p=>p.firstTracked&&p.firstTracked>=oneWeekStr).length;
  const fv=v=>v>=1e9?'$'+(v/1e9).toLocaleString('en-CA',{minimumFractionDigits:1,maximumFractionDigits:1})+'B':v>=1e6?'$'+Math.round(v/1e6).toLocaleString('en-CA')+'M':'$0';
  const slot=$('projHeroStats');
  if(slot)slot.innerHTML=
    '<div class="stat-item"><div class="stat-value">'+total.toLocaleString()+'</div><div class="stat-label">Total Projects</div></div>'+
    '<div class="stat-item"><div class="stat-value">'+fv(totalVal)+'</div><div class="stat-label">Total Value</div></div>'+
    '<div class="stat-item"><div class="stat-value">'+uc.toLocaleString()+'</div><div class="stat-label">Under Construction</div></div>'+
    '<div class="stat-item"><div class="stat-value">'+approved.toLocaleString()+'</div><div class="stat-label">Approved</div></div>'+
    '<div class="stat-item"><div class="stat-value">'+newCount.toLocaleString()+'</div><div class="stat-label">New This Week</div></div>';
}
function renderProjectTable(){
  const shown=filteredProjects.slice(0,(projectPage+1)*PAGE_SIZE);
  // Summary line
  const pf=$('filterProvince')?.value;
  const countNote=(!pf||pf==='')?'Showing '+shown.length+' of '+filteredProjects.length+' projects. Select a province for complete results. ('+allProjects.length+' most recent loaded)':'Showing '+shown.length+' of '+filteredProjects.length+' '+(PROVS.find(p=>p.code===pf)||{}).name+' projects';
  $('projectResultsSummary').textContent=countNote;
  // Table
  let html='<div class="project-table-wrap"><table class="project-table"><thead><tr><th scope="col">Value</th><th scope="col">Project</th><th scope="col">Type</th><th scope="col">Province</th><th scope="col">Proponent</th><th scope="col">Status</th><th scope="col">Sector</th><th scope="col">Updated</th><th scope="col">Source</th></tr></thead><tbody>';
  shown.forEach((p,i)=>{
    const rowId='proj_'+i;
    const firstEv=(p.evidence||[])[0]||{};
    const srcDead=firstEv.url_dead||false;
    const srcUrl=srcDead?'':(firstEv.url||'');
    const srcTitle=firstEv.name||firstEv.source_type||'Source';
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
  // Union-merge briefing watchlist + events.json + events_global.json, deduped by (date, normalized title)
  const _evtKey=e=>(e.date||'')+'|'+String(e.event_name||e.event||e.name||'').trim().toLowerCase();
  _calEvents=((D&&(D.watchlist||D.events))||[]).slice();
  const seen=new Set(_calEvents.map(_evtKey));
  try{
    const evts=await fetchJSON('events.json');
    const today=_localYMD(new Date());
    (Array.isArray(evts)?evts:[]).forEach(e=>{
      const title=String(e.event_name||e.event||e.name||'').trim();
      // Skip stale search-noise rows: past-dated items with social-media suffixed titles
      if((e.date||'')<today&&/- (Facebook|YouTube)$/.test(title))return;
      // events.json carries significance, the renderer reads impact
      if(!hasVal(e.impact)){
        const sig=String(e.significance||'').toLowerCase();
        e.impact=sig==='high'?'high':sig==='medium'?'medium':'low';
      }
      const key=_evtKey(e);
      if(!seen.has(key)){_calEvents.push(e);seen.add(key)}
    });
  }catch(_){}
  // Merge US + European institution releases from static bridge file
  try{
    const globalData=await fetchJSON('events_global.json');
    if(globalData&&Array.isArray(globalData.events)){
      globalData.events.forEach(e=>{
        const key=_evtKey(e);
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
      // Year-less dates anchor to the briefing week_of's year, not the displayed grid year
      if(parts.length>=2){eMonth=MONTHS_SHORT[(parts[0]||'').toLowerCase().slice(0,3)]??-1;eDay=parseInt(parts[1])||0;eYear=_evtAnchorYear();}
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
    // Policy dates arrive as RFC822 ("Thu, 12 Mar 2026 ...") or date-only strings — splitting on 'T' hits the T in "Thu"
    let dateDisp='';
    if(a.date){
      const rawDate=String(a.date);
      if(/^\d{4}-\d{2}-\d{2}/.test(rawDate)){dateDisp=rawDate.split('T')[0]}
      else{const pd=new Date(rawDate);dateDisp=isNaN(pd)?rawDate:pd.toLocaleDateString('en-CA',{month:'short',day:'numeric',year:'numeric'})}
    }
    const dateStr=dateDisp?'<span style="color:#94A3B8;font-size:9px;margin-right:6px">'+san(dateDisp)+'</span>':'';
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
// Normalize a StatCan table id to always end with -01 (the canonical "main table" suffix).
// Handles 3-part ids ("XX-XX-XXXX" → "XX-XX-XXXX-01") and 4-part ids with any other
// suffix ("XX-XX-XXXX-NN" → "XX-XX-XXXX-01"). Leaves non-StatCan references
// (e.g. Bank of Canada Valet) untouched.
function _normalizeStatcanTable(t){
  var s=String(t||'').trim();
  if(!s||s.indexOf('BoC')>=0)return s;
  var parts=s.split('-');
  if(parts.length===4){parts[3]='01';return parts.join('-')}
  if(parts.length===3)return s+'-01';
  return s;
}
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
let _fullDirRawLength=0;
let _fullDirLoaded=false;
let _expSearchPage=1;
let _expVcodeOnly=false;
const EXP_PAGE_SIZE=10;
const FREQ_MAP={M:'Monthly',Q:'Quarterly',A:'Annual',D:'Daily',W:'Weekly',E:'Every 2 months',S:'Semi-annual',O:'Occasional'};

(async function loadTableDirectory(){
  try{
    const resp=await fetch('data/statcan_tables.json');
    if(!resp.ok)return;
    const raw=await resp.json();
    _fullDirRawLength=Array.isArray(raw)?raw.length:0;
    /* Build a Set of normalized table IDs already in curated index (all canonical -01 form) */
    const curated=new Set(VCODE_INDEX.map(v=>_normalizeStatcanTable(v.table)));
    _fullTableDir=raw.map(r=>({
      vcode:'\u2014',table:_normalizeStatcanTable(r.t),title:r.n,keywords:r.k,
      category:r.c,freq:FREQ_MAP[r.f]||r.f,geo:r.g,_dir:true
    })).filter(r=>!curated.has(r.table));
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
  // StatCan Tables = raw statcan_tables.json directory count + curated VCODE_INDEX entries.
  // We track the raw length before dedup filtering so the headline count matches the real total
  // (directory rows + curated indicators) rather than undercounting due to overlap removal.
  const tablesTotal=_fullDirLoaded?(_fullDirRawLength+VCODE_INDEX.length):0;
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

  searchEl.innerHTML='<div class="exp-search-row"><input type="text" id="vcodeSearch" class="exp-search-input" placeholder="Search StatCan tables (e.g. unemployment, housing, GDP)..." onkeyup="if(event.key===\'Enter\'){_expSearchPage=1;window._doVcodeSearch()}"><button class="exp-search-btn" onclick="_expSearchPage=1;window._doVcodeSearch()">Search</button><label class="exp-toggle-switch" title="Show only entries with a V-Code (curated indicators)"><input type="checkbox" id="expVcodeOnlyBtn" onchange="window._toggleVcodeOnly()"'+(_expVcodeOnly?' checked':'')+'><span class="exp-toggle-slider"></span><span class="exp-toggle-label">V-codes only</span></label></div>';

  const categories=['Labour Market','GDP','Construction','Housing','Prices','Trade','Energy','Manufacturing','Agriculture','Infrastructure','Transportation','Health','Demographics','Tourism'];
  catEl.innerHTML='<div class="exp-cat-row">'+categories.map(c=>'<button class="exp-cat-btn" onclick="_expSearchPage=1;window._doVcodeSearch(\''+c+'\')">'+c+'</button>').join('')+'</div>';

  resEl.innerHTML='<div class="exp-empty">Enter a search term or click a category to find StatCan tables.</div>';
  const metaEl=$('expSearchMeta');if(metaEl)metaEl.textContent='';

  // National indicator section: single unified menu (explorer <select>) containing both the
  // curated Key Economic Indicators (INDICATOR_CATALOG) and the full Statistics Canada feed
  // (_statcanExplorerGroups, populated from statcan_latest.indicators).
  const cis=$('canadaIndicatorSection');
  if(cis){
    cis.innerHTML='<div class="exp-card"><div class="exp-card-title">Statistics Canada \u2014 Key Economic Indicators</div><div class="exp-card-sub">Official economic indicators published by Statistics Canada (<a href="https://www150.statcan.gc.ca/n1/dai-quo/ssi/homepage/ind-econ-eng.htm" target="_blank" rel="noopener noreferrer">source</a>)</div><section id="indicatorExplorer"></section></div>';
    // Build the StatCan feed groups for the explorer <select>
    const scData=_indJsonCache&&_indJsonCache.statcan_latest;
    const scInds=(scData&&scData.indicators)||[];
    if(scInds.length){
      const _catMap=(name)=>{
        const n=(name||'').toLowerCase();
        if(n.includes('gdp')||n.includes('capacity'))return 'GDP & Output (StatCan feed)';
        if(n.includes('employ')||n.includes('labour')||n.includes('wage')||n.includes('earning')||n.includes('insurance benefic'))return 'Labour Market (StatCan feed)';
        if(n.includes('price index')||n.includes('cpi')||n.includes('food')||n.includes('shelter')||n.includes('transportation'))return 'Prices (StatCan feed)';
        if(n.includes('housing')||n.includes('building')||n.includes('construction'))return 'Housing & Construction (StatCan feed)';
        if(n.includes('export')||n.includes('import')||n.includes('trade')||n.includes('inventory')||n.includes('merchandise')||n.includes('unfilled'))return 'Trade & Manufacturing (StatCan feed)';
        if(n.includes('household')||n.includes('saving')||n.includes('debt')||n.includes('net worth')||n.includes('retail')||n.includes('wholesale'))return 'Household & Retail (StatCan feed)';
        if(n.includes('tourism')||n.includes('visitor')||n.includes('returning'))return 'Tourism & Travel (StatCan feed)';
        if(n.includes('farm')||n.includes('canola')||n.includes('wheat')||n.includes('corn')||n.includes('soy'))return 'Agriculture (StatCan feed)';
        if(n.includes('investment')||n.includes('capital')||n.includes('securities')||n.includes('profit')||n.includes('current account')||n.includes('terms of trade'))return 'Investment & Finance (StatCan feed)';
        if(n.includes('productivity'))return 'Productivity (StatCan feed)';
        return 'Other (StatCan feed)';
      };
      const byGroup={};
      const seen=new Set();
      scInds.forEach(i=>{
        const nm=i.name||'';
        if(!nm)return;
        const id='sc_'+nm.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'').slice(0,80);
        if(seen.has(id))return;
        seen.add(id);
        const cat=_catMap(nm);
        if(!byGroup[cat])byGroup[cat]=[];
        byGroup[cat].push({
          id:id,
          label:nm,
          unit:'',
          source:'Statistics Canada',
          url:i.tableUrl||'',
          prov:false,
          statcan:true
        });
      });
      _statcanExplorerGroups=Object.keys(byGroup).sort().map(k=>({group:k,items:byGroup[k]}));
    }else{
      _statcanExplorerGroups=[];
    }
    renderIndicatorExplorer();
  }

  // Ontario Economic Accounts (OEA) section
  _renderOeaSection();

  // Quebec ISQ section
  _renderIsqSection();
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
  charts._provExp=new Chart(canvas,{type:'line',data:{labels:pts.map(p=>p.date),datasets:[{data:pts.map(p=>p.value),borderColor:'#003153',backgroundColor:'transparent',borderWidth:2.8,pointRadius:0,pointHoverRadius:5,pointBackgroundColor:'#003153',pointBorderColor:'#ffffff',pointBorderWidth:2,fill:false,tension:0.35}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f172a',titleColor:'#cbd5e1',bodyColor:'#ffffff',padding:10,cornerRadius:4,titleFont:{family:'Inter',size:10,weight:'400'},bodyFont:{family:'Inter',size:13,weight:'700'},displayColors:false}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'Inter',size:11},color:'#4a5568'}},y:{position:'right',grid:{color:'#e8ecf0',lineWidth:1,drawBorder:false},ticks:{font:{family:'Inter',size:11},color:'#4a5568',callback:v=>fmtNum(v)}}}}});
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
  charts._oea=new Chart(canvas,{type:'line',data:{labels:pts.map(p=>p.date),datasets:[{data:pts.map(p=>p.value),borderColor:'#003153',backgroundColor:'transparent',borderWidth:2.8,pointRadius:0,pointHoverRadius:5,pointBackgroundColor:'#003153',pointBorderColor:'#ffffff',pointBorderWidth:2,fill:false,tension:0.35}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f172a',titleColor:'#cbd5e1',bodyColor:'#ffffff',padding:10,cornerRadius:4,titleFont:{family:'Inter',size:10,weight:'400'},bodyFont:{family:'Inter',size:13,weight:'700'},displayColors:false}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'Inter',size:11},color:'#4a5568'}},y:{position:'right',grid:{color:'#e8ecf0',lineWidth:1,drawBorder:false},ticks:{font:{family:'Inter',size:11},color:'#4a5568',callback:v=>fmtNum(v)}}}}});
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
  charts._isq=new Chart(canvas,{type:'line',data:{labels:pts.map(p=>p.date),datasets:[{data:pts.map(p=>p.value),borderColor:'#003153',backgroundColor:'transparent',borderWidth:2.8,pointRadius:0,pointHoverRadius:5,pointBackgroundColor:'#003153',pointBorderColor:'#ffffff',pointBorderWidth:2,fill:false,tension:0.35}]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f172a',titleColor:'#cbd5e1',bodyColor:'#ffffff',padding:10,cornerRadius:4,titleFont:{family:'Inter',size:10,weight:'400'},bodyFont:{family:'Inter',size:13,weight:'700'},displayColors:false}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'Inter',size:11},color:'#4a5568'}},y:{position:'right',grid:{color:'#e8ecf0',lineWidth:1,drawBorder:false},ticks:{font:{family:'Inter',size:11},color:'#4a5568',callback:v=>fmtNum(v)}}}}});
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

window._toggleVcodeOnly=function(){
  _expVcodeOnly=!_expVcodeOnly;
  _expSearchPage=1;
  if(_expLastQuery)_expRenderVcodeResults();
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
  let results=_expSearchAll(q);
  if(_expVcodeOnly){
    results=results.filter(r=>r.vcode&&r.vcode!=='\u2014');
  }
  if(!results.length){
    const suffix=_expVcodeOnly?' (V-codes only filter is on)':'';
    resEl.innerHTML='<div class="exp-empty">No tables found for "'+_expEscapeHtml(q)+'"'+suffix+'. Try different keywords.</div>';
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
    const tableId=_normalizeStatcanTable(r.table);
    const _pidRaw=String(tableId||'').replace(/-/g,'');
    const _pid=_pidRaw.length===8?_pidRaw+'01':_pidRaw;
    const tableUrl=tableId&&tableId.indexOf('BoC')>=0?'https://www.bankofcanada.ca/rates/':('https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid='+_pid);
    const meta=_expEscapeHtml([r.freq,r.geo].filter(Boolean).join(' \u00b7 '));
    html+='<tr>';
    html+='<td><span class="exp-vcode-code">'+_expEscapeHtml(r.vcode||'\u2014')+'</span></td>';
    html+='<td><span class="exp-vcode-tbl">'+_expEscapeHtml(tableId||'')+'</span></td>';
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
