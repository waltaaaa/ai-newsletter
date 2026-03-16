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

/* ── State ── */
let D=null,indicators=[],allProjects=[],filteredProjects=[],projectPage=0,selectedProvince='BC',tsCache={},charts={},tabRendered={};
const PAGE_SIZE=25;
let _confirmedOnly=false;
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
let _projTypeFilter='all';

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
function fmtNum(n,d){if(typeof n!=='number'||isNaN(n))return String(n);const dec=d!=null?d:(Math.abs(n)>=100?0:Math.abs(n)>=1?1:2);return n.toLocaleString('en-CA',{minimumFractionDigits:dec,maximumFractionDigits:dec})}
function fmtVal(v){if(!v||v==='N/A'||v==='Not disclosed')return'<span style="color:#556B7A">N/D</span>';return v}
function parseNumericValue(v){if(!v)return 0;const s=String(v).toUpperCase();const m=s.match(/([\d.]+)\s*(B|M|K)?/);if(!m)return 0;let n=parseFloat(m[1])||0;if(m[2]==='B')n*=1e9;else if(m[2]==='M')n*=1e6;else if(m[2]==='K')n*=1e3;return n}
function fmtCurrency(v,p){if(!v||v==='—'||v==='N/A'||v==='Not disclosed'){if(p&&p.cost_unfindable)return'<span style="color:#556B7A;font-style:italic" title="Cost not publicly available after 3 search attempts">N/A</span>';if(p&&p.cost_search_attempts>0)return'<span style="color:#556B7A;font-style:italic" title="Searching for value (attempt '+p.cost_search_attempts+'/3)">Searching\u2026</span>';return'<span style="color:#556B7A">N/D</span>'}let out='';if(typeof v==='string'&&v.match(/\$[\d.]+[BMK]/i))out=v;else{const n=parseNumericValue(v);if(!n)out=String(v);else if(n>=1e9)out='$'+(n/1e9).toFixed(1)+'B';else if(n>=1e6)out='$'+(n/1e6).toFixed(0)+'M';else if(n>=1e3)out='$'+(n/1e3).toFixed(0)+'K';else out='$'+n.toLocaleString()}if(p&&p.value_low_millions&&p.value_high_millions)out+='<span style="color:#556B7A;font-size:10px;margin-left:3px" title="Range: $'+Math.round(p.value_low_millions)+'M\u2013$'+Math.round(p.value_high_millions)+'M">*</span>';if(p&&p.value_notes)out+='<span style="color:#556B7A;font-size:10px;margin-left:2px" title="'+p.value_notes.replace(/"/g,"&quot;")+'">\u2020</span>';return out}
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
  try{D=await fetchJSON('briefing_latest.json')}
  catch(e){console.error('Newsletter load:',e)}
}
async function loadEditionList(){
  try{
    const archive=await fetchJSON('briefing_archive.json');
    const editions=(archive||[]).map(e=>({id:e.week_of||'',edition:e.headline||'',date:e.generated_at||e.week_of||''}));
    const list=$('editionList');
    list.innerHTML=editions.map(e=>{
      const label=(e.edition||'').replace(/EDITION:\s*/i,'').split('//')[0].trim()||e.id;
      const active=e.id===currentEdition?'font-weight:700;background:var(--bg-subtle)':'';
      return'<div class="edition-item" data-id="'+e.id+'" style="padding:8px 14px;font-size:var(--text-xs);cursor:pointer;border-bottom:1px solid var(--border-light);'+active+'">'+label+'</div>';
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
  // Static mode: only latest briefing is available as full content
  await loadNewsletter();
  try{await renderTab('tldr');tabRendered.tldr=true}catch(e){console.error('renderTLDR:',e)}
  const edStr=D?(D.edition||D.headline||'').replace(/EDITION:\s*/i,'').split('//')[0].trim():'';
  $('navMeta').textContent=edStr||'Latest Edition';
  const activeTab=document.querySelector('.nav-tab.active');
  if(activeTab&&activeTab.dataset.tab!=='tldr'){renderTab(activeTab.dataset.tab);tabRendered[activeTab.dataset.tab]=true}
  loadEditionList();
}
async function loadIndicators(){
  try{
    const data=await fetchJSON('indicators.json');
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
    $('execSummary').innerHTML='<div class="empty-state"><div class="empty-state-text">Error rendering: '+e.message+'</div></div>';
  }
  const edStr=D?(D.edition||D.headline||'').replace(/EDITION:\s*/i,'').split('//')[0].trim():'';
  $('navMeta').textContent=edStr||((indicators.length)?indicators.length+' indicators loaded':'Data loaded');
  $('footerDate').textContent=D&&D.updated_at?'Last pipeline run: '+fmtDate(D.updated_at):(indicators.length?'Live indicator data loaded':'Awaiting first pipeline run');
  // Hero date subtitle
  const heroDate=$('heroDate');
  if(heroDate){
    const briefingDate=D&&(D.week_of||D.updated_at||D.date);
    if(briefingDate){
      const dt=new Date(briefingDate+'T00:00:00');
      heroDate.textContent='Week of '+dt.toLocaleDateString('en-CA',{month:'long',day:'numeric',year:'numeric'});
    }else{
      heroDate.textContent=new Date().toLocaleDateString('en-CA',{month:'long',day:'numeric',year:'numeric'});
    }
  }
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
    case'national':renderNational();break;
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

/* ══ TL;DR TAB (Editorial Digest) ══ */
let _editorialMode=false;
async function renderTLDR(){
  _editorialMode=true;
  const hasBriefing=D&&D.executive_summary;
  if(hasBriefing){
    let headline=(D.headline||'').trim();
    if(!headline||/^\d|^[A-Z]{3}\s\d/.test(headline)){
      const tmp=document.createElement('div');tmp.innerHTML=D.executive_summary||'';
      const firstLi=tmp.querySelector('li');
      const rawText=firstLi?firstLi.textContent.trim():(tmp.textContent||'').trim();
      const firstSentence=(rawText.split(/[.!]\s/)[0]||'').replace(/\d+$/,'').trim();
      if(firstSentence.length>90)headline=firstSentence.substring(0,87).replace(/\s\S*$/,'')+'...';
      else headline=firstSentence;
      if(!headline)headline='Weekly Summary';
    }
    // Meta stats
    let metaHtml='';
    const projCount=D.discovery_stats?D.discovery_stats.total_projects||'':D.project_count||'';
    const newProj=D.discovery_stats?D.discovery_stats.new_this_week||'':D.new_projects||'';
    const pipeVal=D.discovery_stats?D.discovery_stats.total_value_billions||'':D.pipeline_value||'';
    if(projCount||newProj||pipeVal){
      metaHtml='<div class="editorial-meta">';
      if(projCount)metaHtml+='<div class="editorial-meta-item"><strong>'+projCount+'</strong>Projects Tracked</div>';
      if(newProj)metaHtml+='<div class="editorial-meta-item"><strong>+'+newProj+'</strong>New This Week</div>';
      if(pipeVal)metaHtml+='<div class="editorial-meta-item"><strong>$'+pipeVal+'B</strong>Pipeline Value</div>';
      metaHtml+='</div>';
    }
    // Lead image as editorial float
    const leadImg=findLeadImage(D.sources||[]);
    const imgHtml=leadImg?`<img src="${leadImg}" alt="" class="editorial-lead-img" onerror="this.style.display='none'" loading="lazy">`:'';
    $('execSummary').innerHTML=`<div class="fade-in">
      <div class="editorial-eyebrow">Weekly Intelligence Briefing</div>
      <div class="editorial-headline">${san(headline)}</div>
      <hr class="editorial-accent">
      ${metaHtml}
    </div>`;
  }else{
    $('execSummary').innerHTML=`<div class="fade-in" style="text-align:center;padding:24px 0"><div style="color:#475569;font-size:var(--text-sm)">Weekly briefing pending. ${indicators.length} indicators loaded from primary sources.</div></div>`;
  }
  await renderEditorialFlow();
  renderMicroscopeHistory();
  $('overviewSources').innerHTML=sourcesFooter((D&&D.sources)||[]);
  collapseEmpty();
}
function bulletsToParas(html){
  // Convert <ul><li>...</li></ul> bullet lists into <p> paragraphs for narrative flow
  // Also handles content that's already <p> paragraphs (passes through unchanged)
  if(!html)return'';
  return html
    .replace(/<ul[^>]*>/gi,'')
    .replace(/<\/ul>/gi,'')
    .replace(/<li>/gi,'<p>')
    .replace(/<\/li>/gi,'</p>');
}
async function renderEditorialFlow(){
  const flow=$('editorialFlow');if(!flow){console.error('editorialFlow element not found');return}
  if(!D){flow.innerHTML='<div style="padding:24px;color:#475569;font-size:var(--text-sm);text-align:center">Awaiting pipeline data.</div>';return}
  try{
  // Executive summary — convert bullets to paragraphs
  const execHtml=bulletsToParas(san(linkFootnotes((D.executive_summary)||'',((D.sources)||[]))));

  // Unsplash or lead image
  const imgUrl=D.unsplash_image_url||findLeadImage(D.sources||[]);
  const imgHtml=imgUrl?`<img src="${san(imgUrl)}" alt="" class="ed-unsplash-img" onerror="this.style.display='none'" loading="lazy">`:'';

  // Consumer pulse
  let pulseHtml='';
  if(D.consumer_pulse){
    pulseHtml=bulletsToParas(san(D.consumer_pulse));
  }

  // Industry summary
  let industryHtml='';
  if(D.industry_executive_summary){
    industryHtml=bulletsToParas(san(D.industry_executive_summary));
  }

  // Word cloud topics
  const wcTopics=(D.word_cloud_topics&&D.word_cloud_topics.length)?D.word_cloud_topics:extractTopicsFromText();


  // Insert image after 3rd paragraph so it doesn't compete with the map float
  let execWithImg=execHtml;
  if(imgHtml){
    const parts=execWithImg.split('</p>');
    if(parts.length>3){
      parts.splice(3,0,imgHtml);
      execWithImg=parts.join('</p>');
    }else{
      execWithImg=imgHtml+execWithImg;
    }
  }

  // Generate short section subtitles — data-driven, no repetition
  function _shortSub(html,maxLen){
    if(!html)return '';
    const plain=html.replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
    // Extract the key clause — up to first comma or period, capped at maxLen
    const clause=plain.match(/^[^,.!?]+/);
    let sub=clause?clause[0].trim():plain.slice(0,maxLen);
    if(sub.length>maxLen)sub=sub.slice(0,maxLen).replace(/\s\S*$/,'')+'...';
    return sub;
  }
  const industrySub=_shortSub(D.industry_executive_summary||'',70);
  const marketsSub=(()=>{
    const fm=(D&&(D.financialMarkets||D.financial_markets||D.markets))||{};
    const idx=(fm.indices||[])[0];
    const wti=indicators.find(x=>x.indicator_name==='wti'||x.indicator_name==='wti_oil');
    const cad=indicators.find(x=>x.indicator_name==='cadusd'||x.indicator_name==='cad_usd');
    const parts=[];
    if(idx)parts.push(`TSX ${idx.value||''}${idx.change?' ('+idx.change+')':''}`);
    if(cad)parts.push(`CAD $${cad.value}`);
    if(wti)parts.push(`WTI $${wti.value}`);
    return parts.join(' · ')||'Markets and commodities';
  })();
  const pulseSub=_shortSub(D.consumer_pulse||'',70)||'Public sentiment and social signals';

  // Assemble — 4 sections: Overview, Industry, Markets, Consumer Pulse
  flow.innerHTML=`
    <div id="tldrMapSection"></div>
    ${execWithImg}
    <div class="ed-clear"></div>

    <div class="ed-section">
      <div class="ed-section-title">Industry Overview</div>
      <div class="ed-section-subtitle">${san(industrySub)}</div>
    </div>
    ${(()=>{
      const chart='<div class="ed-industry-chart" id="tldrSectorCard"><div class="ec-title">Capital by Sector</div><div class="ec-sub">Tracked investment by sector</div><div style="height:240px;position:relative"><canvas id="tldrSectorChart"></canvas></div><div class="ec-source">Pipeline database</div></div>';
      if(!industryHtml)return chart;
      const parts=industryHtml.split('</p>');
      if(parts.length<=3)return industryHtml+chart;
      // Insert ~halfway through so chart bottom aligns with text end
      const insertAt=Math.max(1,Math.floor(parts.length*0.57));
      parts.splice(insertAt,0,chart);
      return parts.join('</p>');
    })()}
    <div class="ed-clear"></div>

    <div class="ed-section">
      <div class="ed-section-title">Financial Markets</div>
      <div class="ed-section-subtitle">${san(marketsSub)}</div>
    </div>
    <div id="tldrMarketsSection"></div>
    <div class="ed-clear"></div>

    <div class="ed-section">
      <div class="ed-section-title">Consumer Pulse</div>
      <div class="ed-section-subtitle">${san(pulseSub)}</div>
    </div>
    <div id="tldrWordCloud" class="ed-wordcloud">
      <div class="ed-wc-title">Economic Sentiment</div>
      <div class="ed-wc-sub">Top themes from news articles and public discussion</div>
      <div id="tldrWordCloudSvg" style="width:100%"></div>
      <div class="ec-source">Pipeline: 300+ RSS feeds, Google News, Reddit, Google Trends</div>
    </div>
    ${pulseHtml}
    <div class="ed-clear"></div>
  `;
  await renderInteractiveMap();
  await renderTLDRMarkets();
  try{await _ensureChartData();_renderSectorChart('tldrSectorChart','tldrSectorCard','tldr')}catch(e){console.warn('Sector chart:',e)}
  if(wcTopics.length) renderTLDRWordCloud(wcTopics,'tldrWordCloudSvg');
  }catch(e){
    console.error('renderEditorialFlow error:',e);
    flow.innerHTML='<div style="padding:24px;color:#991B1B;font-size:var(--text-sm)">Error rendering editorial flow: '+e.message+'</div>';
  }
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
    // Keep latest by period
    const existing=data[prov]['_'+name+'_period']||'';
    if(ind.period>=existing){
      data[prov][name]=ind.value;
      data[prov]['_'+name+'_period']=ind.period;
    }
  });
  return data;
}

/* ── Interactive Canada Map with GDP choropleth + hover tooltips ── */
async function renderInteractiveMap(){
  const container=$('tldrMapSection');
  if(!container)return;
  const provData=getProvIndicators();
  // Shared toggle state — controls national panel AND province tooltips
  let _mapMode='indicators'; // 'indicators' or 'thisweek'

  // National stat boxes
  const ki=(D&&D.key_indicators)||[];
  const m=(D&&D.metrics)||{};
  const findKI=(label)=>{const item=ki.find(k=>k.label===label);return item?{value:item.value,change:item.change}:{value:'N/A',change:''}};
  const natPart=indicators.find(x=>x.indicator_name==='participationRate'&&(x.province||'').toLowerCase()==='national');
  const natEmp=indicators.find(x=>x.indicator_name==='employmentRate'&&(x.province||'').toLowerCase()==='national');
  const natWage=indicators.find(x=>x.indicator_name==='wageGrowth'&&(x.province||'').toLowerCase()==='national');

  // Two sets of national indicators
  const statsDefault=[
    {label:'Real GDP',value:m.realGdp||'N/A',change:''},
    {label:'Unemployment',value:findKI('UNEMPLOYMENT').value,change:findKI('UNEMPLOYMENT').change},
    {label:'Participation',value:natPart?natPart.value:(m.participation||'N/A'),change:''},
    {label:'Employment Rate',value:natEmp?natEmp.value:'N/A',change:''},
    {label:'Wage Growth',value:natWage?natWage.value:(m.wageGrowth||'N/A'),change:''},
    {label:'Trade Balance',value:findKI('TRADE BALANCE').value,change:findKI('TRADE BALANCE').change}
  ];
  // "This Week" indicators — the ones that moved or are newsworthy this week
  const statsThisWeek=[];
  ki.forEach(k=>{
    if(k.change&&k.change.trim())statsThisWeek.push({label:k.label,value:k.value,change:k.change});
  });
  // Add MFG sales if present
  const mfg=findKI('MFG SALES');if(mfg.value!=='N/A')statsThisWeek.push({label:'MFG Sales',value:mfg.value,change:mfg.change});
  // Pad to 6 with other key indicators
  if(statsThisWeek.length<6&&natWage)statsThisWeek.push({label:'Wage Growth',value:natWage.value,change:''});
  if(statsThisWeek.length<6&&natPart)statsThisWeek.push({label:'Participation',value:natPart.value,change:''});

  function buildNatPanel(){
    const isInd=_mapMode==='indicators';
    const activeStats=isInd?statsDefault:statsThisWeek.slice(0,6);
    let html=`<div class="ed-stat-header" style="display:flex;justify-content:space-between;align-items:center">
      <span>Canada &mdash; National</span>
      <span style="display:flex;gap:4px">
        <span class="ed-tt-tab${isInd?' active':''}" id="natToggleInd">Key Indicators</span>
        <span class="ed-tt-tab${!isInd?' active':''}" id="natToggleHL">This Week</span>
      </span>
    </div>`;
    html+='<div class="ed-stat-grid">';
    activeStats.forEach(s=>{
      const chgCls=s.change?(s.change.startsWith('-')||s.change.startsWith('\u2212')?'change-down':'change-up'):'';
      html+=`<div class="ed-stat-box"><div class="ed-stat-label">${s.label}</div><div class="ed-stat-value">${s.value}</div>${s.change?`<div class="ed-stat-change ${chgCls}">${s.change}</div>`:''}`;
      html+='</div>';
    });
    html+='</div>';
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
        svg.append('text').attr('x',pt[0]).attr('y',pt[1]).attr('text-anchor','middle').attr('font-family','Outfit').attr('font-size',11).attr('font-weight',700).attr('fill','#0f1b33').text(code);
      });

      // ── Maritime inset (top-right corner) — NB, NS, PE ──
      const maritimeCodes=new Set(['NB','NS','PE']);
      const maritimeFeatures=geojson.features.filter(f=>maritimeCodes.has(featureCode(f)));
      if(maritimeFeatures.length){
        const iw=Math.round(w*0.26);const ih=Math.round(iw*0.8);
        const ix=w-iw-12;const iy=12;
        const ig=svg.append('g').attr('class','maritime-inset');
        ig.append('rect').attr('x',ix).attr('y',iy).attr('width',iw).attr('height',ih).attr('fill','#F0F4FF').attr('stroke','rgba(37,99,235,0.25)').attr('stroke-width',1).attr('rx',6);
        ig.append('text').attr('x',ix+iw/2).attr('y',iy+12).attr('text-anchor','middle').attr('font-family','Outfit').attr('font-size',8).attr('font-weight',600).attr('fill','#64748B').text('Maritimes');
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
          ig.append('text').attr('x',pt[0]).attr('y',pt[1]).attr('text-anchor','middle').attr('font-family','Outfit').attr('font-size',9).attr('font-weight',700).attr('fill','#0f1b33').text(code);
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
  const layout=d3.layout.cloud().size([w,h]).words(words).padding(6).rotate(()=>0).font('Outfit').fontSize(d=>d.size).on('end',drawn);
  layout.start();
  function drawn(wds){
    const svg=d3.select(container).append('svg').attr('width',w).attr('height',h);
    const g=svg.append('g').attr('transform','translate('+w/2+','+h/2+')');
    g.selectAll('text').data(wds).enter().append('text')
      .style('font-size',d=>d.size+'px').style('font-family','Outfit')
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

/* ══ NATIONAL TAB (subtabs: Canada + Global Players) ══ */
let _nationalSubRendered={};
const NATIONAL_BANNERS={canada:{title:'Canada',sub:'National economic indicators, analysis, policy, and capital projects',img:'https://images.unsplash.com/photo-1517935706615-2717063c2225?w=1200&q=80'},us:{title:'United States',sub:'U.S. macro indicators and policy developments affecting Canada',img:'https://images.unsplash.com/photo-1501466044931-62695aada8e9?w=1200&q=80'},china:{title:'China',sub:'Chinese economic data and trade developments relevant to Canada',img:'https://images.unsplash.com/photo-1547981609-4b6bfe67ca0b?w=1200&q=80'},eu:{title:'European Union',sub:'EU economic conditions and policy affecting Canadian trade',img:'https://images.unsplash.com/photo-1519677100203-a0e668c92439?w=1200&q=80'},uk:{title:'United Kingdom',sub:'UK economic data and bilateral trade with Canada',img:'https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=1200&q=80'}};
window.switchNationalSub=function(key){
  document.querySelectorAll('.national-subtab').forEach(b=>b.classList.toggle('active',b.dataset.country===key));
  document.querySelectorAll('.national-subpanel').forEach(p=>p.classList.toggle('active',p.id==='nsub-'+key));
  const b=NATIONAL_BANNERS[key]||NATIONAL_BANNERS.canada;
  $('nationalBannerTitle').textContent=b.title;
  $('nationalBannerSub').textContent=b.sub;
  $('nationalBanner').style.setProperty('--banner-img',"url('"+b.img+"')");
  if(!_nationalSubRendered[key]){_nationalSubRendered[key]=true;if(key==='canada')renderCanadaSub();else renderGlobalPlayerSub(key)}
};
async function renderNational(){
  _nationalSubRendered={};
  renderCanadaSub();
  _nationalSubRendered.canada=true;
  // Pre-render global player subtabs
  renderAllGlobalPlayers();
}
/* == Indicator Panel + Infographic helpers == */
function buildIndicatorPanel(title,indRows,subtitle,chartCanvasId,chartTitle){
  // Find top movers (up to 3)
  const movers=indRows.filter(r=>{
    if(!r.change)return false;
    const n=parseFloat(String(r.change).replace(/[^0-9.\-]/g,''));
    return !isNaN(n)&&Math.abs(n)>0;
  }).sort((a,b)=>{
    const an=Math.abs(parseFloat(String(a.change).replace(/[^0-9.\-]/g,'')));
    const bn=Math.abs(parseFloat(String(b.change).replace(/[^0-9.\-]/g,'')));
    return bn-an;
  }).slice(0,3);
  const topMover=movers[0]||null;

  let html='<div class="ed-map" style="position:relative">';
  html+='<div class="ed-stat-header">'+title+'</div>';
  if(subtitle)html+='<div style="font-size:var(--text-xs);color:#475569;margin:-4px 0 8px;font-style:italic">'+subtitle+'</div>';
  html+='<table class="ed-ind-table"><thead><tr><th>Indicator</th><th style="text-align:right">Value</th><th style="text-align:right">Chg</th></tr></thead><tbody>';
  indRows.forEach(r=>{
    const chg=r.change||'';
    const cls=chg.startsWith('-')||chg.startsWith('\u2212')?'change-down':chg.startsWith('+')?'change-up':'';
    html+='<tr><td class="ind-label">'+r.label+'</td><td class="ind-value">'+r.value+'</td><td class="ind-change '+cls+'">'+(chg||'\u2014')+'</td></tr>';
  });
  html+='</tbody></table>';
  // Embedded chart inside the panel
  if(chartCanvasId){
    html+='<div style="margin-top:14px;border-top:2px solid rgba(37,99,235,0.15);padding-top:12px">';
    html+='<div class="ec-title">'+(chartTitle||'Investment by Sector')+'</div>';
    html+='<div style="height:180px;position:relative"><canvas id="'+chartCanvasId+'"></canvas></div>';
    html+='</div>';
  }
  html+='</div>';
  return {html:html,topMover:topMover,movers:movers};
}

function buildInsightStrip(prefix,movers){
  // Full-width strip with 1-3 infographic charts based on top movers
  if(!movers||!movers.length)return '';
  const count=movers.length;
  const colStyle=count===1?'':'display:grid;grid-template-columns:repeat('+count+',1fr);gap:12px';
  let html='<div style="margin:24px 0;padding:20px 0;border-top:2px solid rgba(37,99,235,0.12);border-bottom:2px solid rgba(37,99,235,0.12);'+colStyle+'">';
  movers.forEach((m,i)=>{
    const id=prefix+'Insight'+i;
    const chgText=m.change?(m.change+' ('+m.value+')'):(m.value||'');
    html+='<div style="text-align:center">';
    html+='<div style="font-size:var(--text-xs);font-weight:700;color:#003153;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px">'+m.label+'</div>';
    html+='<div style="font-size:10px;color:#475569;margin-bottom:8px">'+chgText+'</div>';
    html+='<div style="height:160px;position:relative"><canvas id="'+id+'"></canvas></div>';
    html+='<div style="font-size:9px;color:#94A3B8;margin-top:4px">'+(m.source||'Statistics Canada')+'</div>';
    html+='</div>';
  });
  html+='</div>';
  return html;
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

function renderTopMoverChart(canvasId,topMover,allInds,m,im){
  const canvas=document.getElementById(canvasId);
  if(!canvas)return;
  // Destroy existing chart on this canvas
  const existingKey='_topMover_'+canvasId;
  if(charts[existingKey]){charts[existingKey].destroy();delete charts[existingKey]}
  if(!topMover){
    // Fallback: macro pulse comparison — current vs previous for core indicators
    const labels=[];const cur=[];const prev=[];
    const core=[
      {label:'Unemp',key:'unemployment',mk:'unemployment'},
      {label:'CPI',key:'cpi',mk:'cpi'},
      {label:'GDP',key:'realGdp',mk:'realGdp'},
      {label:'Housing',key:'housingStarts',mk:'housingStarts'},
      {label:'BoC Rate',key:'overnight_rate',mk:'bocRate'},
      {label:'Emp Rate',key:'employmentRate',mk:'employmentRate'}
    ];
    core.forEach(c=>{
      const meta=(im&&im[c.mk])||{};
      const val=parseFloat(String((m&&m[c.mk])||(allInds.find(x=>x.indicator_name===c.key)||{}).value||'0').replace(/[^0-9.\-]/g,''));
      const prv=parseFloat(String(meta.prev||'0').replace(/[^0-9.\-]/g,''));
      if(!isNaN(val)){labels.push(c.label);cur.push(val);prev.push(isNaN(prv)?val:prv)}
    });
    if(!labels.length)return;
    try{
      charts[existingKey]=new Chart(canvas,{type:'bar',data:{labels:labels,datasets:[
        {label:'Current',data:cur,backgroundColor:'rgba(37,99,235,0.7)',borderRadius:3},
        {label:'Previous',data:prev,backgroundColor:'rgba(37,99,235,0.2)',borderRadius:3}
      ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:true,position:'bottom',labels:{font:{size:9}}}},scales:{x:{ticks:{font:{size:9}}},y:{ticks:{font:{size:9}}}}}});
    }catch(e){console.warn('Top mover fallback chart error:',e)}
    return;
  }
  // Single indicator chart — bar comparing current vs previous
  const meta=(im&&im[topMover.metaKey])||{};
  const curVal=parseFloat(String(topMover.value).replace(/[^0-9.\-]/g,''));
  const prevVal=parseFloat(String(meta.prev||'0').replace(/[^0-9.\-]/g,''));
  if(isNaN(curVal))return;
  try{
    charts[existingKey]=new Chart(canvas,{type:'bar',data:{labels:['Previous','Current'],datasets:[{
      data:[isNaN(prevVal)?curVal:prevVal,curVal],
      backgroundColor:['rgba(37,99,235,0.2)','rgba(37,99,235,0.7)'],borderRadius:4
    }]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{ticks:{font:{size:10}}},y:{ticks:{font:{size:10,weight:'bold'}}}}}});
  }catch(e){console.warn('Top mover chart error:',e)}
}

function renderInsightCharts(prefix,movers,allInds,m,im){
  movers.forEach((mover,i)=>{
    const canvasId=prefix+'Insight'+i;
    renderTopMoverChart(canvasId,mover,allInds,m,im);
  });
}

async function renderCanadaSub(){
  const m=(D&&D.metrics)||{};const im=(D&&D.indicatorMeta)||{};
  function indVal(name){const i=indicators.find(x=>x.indicator_name===name);return i?i.value:null}
  function indMeta(name){return (im&&im[name])||{}}
  const natPart=indicators.find(x=>x.indicator_name==='participationRate'&&(x.province||'').toLowerCase()==='national');
  const natEmp=indicators.find(x=>x.indicator_name==='employmentRate'&&(x.province||'').toLowerCase()==='national');
  const natWage=indicators.find(x=>x.indicator_name==='wageGrowth'&&(x.province||'').toLowerCase()==='national');
  const natTrade=indicators.find(x=>x.indicator_name==='tradeBalance');

  // Expanded indicator set (10)
  const natIndicators=[
    {label:'BoC Rate',value:m.bocRate||m.boc_rate||indVal('overnight_rate')||'N/A',change:(indMeta('bocRate').change)||'',source:'Bank of Canada',metaKey:'bocRate'},
    {label:'Real GDP YoY',value:m.realGdp||m.gdp||indVal('realGdp')||'N/A',change:(indMeta('realGdp').change)||'',source:'Statistics Canada',metaKey:'realGdp'},
    {label:'CPI',value:m.cpi||indVal('cpi')||'N/A',change:(indMeta('cpi').change)||'',source:'Statistics Canada',metaKey:'cpi'},
    {label:'Unemployment',value:m.unemployment||indVal('unemployment')||'N/A',change:(indMeta('unemployment').change)||'',source:'Statistics Canada',metaKey:'unemployment'},
    {label:'Participation',value:natPart?natPart.value:(m.participation||'N/A'),change:'',source:'Statistics Canada',metaKey:'participationRate'},
    {label:'Employment Rate',value:natEmp?natEmp.value:'N/A',change:'',source:'Statistics Canada',metaKey:'employmentRate'},
    {label:'Wage Growth',value:natWage?natWage.value:(m.wageGrowth||'N/A'),change:'',source:'Statistics Canada',metaKey:'wageGrowth'},
    {label:'CAD/USD',value:m.cadUsd||m.cad_usd||indVal('cad_usd')||'N/A',change:'',source:'Bank of Canada',metaKey:'cadUsd'},
    {label:'Housing Starts',value:m.housingStarts||m.housing_starts||indVal('housingStarts')||'N/A',change:(indMeta('housingStarts').change)||'',source:'CMHC',metaKey:'housingStarts'},
    {label:'Trade Balance',value:natTrade?natTrade.value:'N/A',change:'',source:'Statistics Canada',metaKey:'tradeBalance'}
  ];

  // Editorial header
  const projTotal=allProjects.length||(await fetchJSON('projects_all.json').then(d=>Array.isArray(d)?d.length:0).catch(()=>0));
  const ds=D&&D.discovery_stats||{};
  const newPrj=ds.new_this_week||D&&D.new_projects||0;
  const pipVal=ds.total_value_billions||D&&D.pipeline_value||'';
  const hdr=$('canadaEditorialHeader');
  if(hdr){
    hdr.innerHTML='<div class="fade-in"><div class="editorial-eyebrow">National Economic Overview</div>'+
      '<div class="editorial-headline">Canada</div><hr class="editorial-accent">'+
      '</div>';
  }

  // Analysis section with floating indicator panel (includes commodity chart inside)
  const hasBriefing=D&&D.executive_summary;
  const natContent=(D&&D.national&&D.national.analysis)||D&&D.national_analysis||'';
  const natSources=(D&&D.national&&D.national.sources)||[];
  const natSubtitle=deriveSubtitle(natContent);
  const panel=buildIndicatorPanel('Canada \u2014 National',natIndicators,natSubtitle,'natCommodityChart','Commodity Movers');

  let secHtml='';
  secHtml+=panel.html;
  if(natContent){
    secHtml+=san(linkFootnotes(natContent,natSources.length?natSources:(D&&D.sources||[])));
  }else if(!hasBriefing){
    secHtml+='<p style="color:#475569">National analysis available after next pipeline run.</p>';
  }
  if(natSources.length)secHtml+=sourcesFooter(natSources);
  secHtml+='<div class="ed-clear"></div>';
  // Insight strip — full width between analysis and projects
  secHtml+=buildInsightStrip('nat',panel.movers);

  const nas=$('natAnalysisSection');
  if(nas)nas.innerHTML=secHtml;

  // Render charts after DOM is set
  await _ensureChartData();
  _renderCommodityChart('natCommodityChart','natCommodityCard','nat');
  renderInsightCharts('nat',panel.movers,indicators,m,im);

  // Policy section with editorial header
  const ps=$('policySection');
  if(ps){
    // Wrap in editorial section — renderPolicySection targets 'policyContent' inside
    ps.innerHTML='<div class="ed-section"><div class="ed-section-title">Policy Monitor</div><div class="ed-section-subtitle">Legislative and regulatory developments</div></div><div id="policyContent"></div>';
  }
  renderPolicySection();


  // Projects with editorial header
  const pp=$('canadaProjectsPreview');
  if(pp){
    let projects=[];
    try{const d=await fetchJSON('projects_all.json');projects=Array.isArray(d)?d:[]}catch(e){}
    const topProjects=projects.filter(p=>parseNumericValue(p.value)>0).sort((a,b)=>parseNumericValue(b.value)-parseNumericValue(a.value)).slice(0,10);
    let projHtml='<div class="ed-section"><div class="ed-section-title">Capital Projects</div><div class="ed-section-subtitle">Major projects tracked nationally</div></div>'+
      '<div class="editorial-meta" style="margin-bottom:12px">'+
      '<div class="editorial-meta-item"><strong>'+projTotal+'</strong>Projects Tracked</div>'+
      (newPrj?'<div class="editorial-meta-item"><strong>+'+newPrj+'</strong>New This Week</div>':'')+
      (pipVal?'<div class="editorial-meta-item"><strong>$'+pipVal+'B</strong>Pipeline Value</div>':'')+
      '</div>';
    if(topProjects.length){
      projHtml+='<div class="project-table-wrap"><table class="project-table" style="margin-top:8px"><thead><tr><th scope="col">Value</th><th scope="col">Project</th><th scope="col">Province</th><th scope="col">Status</th><th scope="col">Sector</th></tr></thead><tbody>';
      topProjects.forEach(p=>{
        const sectorName=(p.sector||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
        projHtml+='<tr><td class="col-value">'+fmtCurrency(p.value,p)+'</td><td class="col-name">'+((p.name||'').substring(0,55))+'</td><td class="col-province">'+normProvince(p.province)+'</td><td>'+statusBadge(p.status||'Proposed')+'</td><td style="font-size:var(--text-xs);color:#475569">'+sectorName+'</td></tr>';
      });
      projHtml+='</tbody></table></div>';
      projHtml+='<div style="margin-top:12px;font-size:var(--text-sm)"><a href="#" style="color:var(--accent-blue);text-decoration:none" onclick="event.preventDefault();switchTab(\'projects\')">View all projects \u2192</a></div>';
    }else{
      projHtml+='<div class="empty-state"><div class="empty-state-text">No projects loaded yet.</div></div>';
    }
    pp.innerHTML=projHtml;
  }
  renderCostMonitor();
}
function renderAllGlobalPlayers(){
  const gv=D?D.globalVectors||D.global_vectors||{}:{};
  const globalArr=D?D.global||[]:[];
  const REGION_MAP={'United States':'us','China':'china','European Union':'eu','United Kingdom':'uk'};
  const players=[{key:'us',name:'United States'},{key:'china',name:'China'},{key:'eu',name:'European Union'},{key:'uk',name:'United Kingdom'}];
  players.forEach(v=>{
    const panel=$('nsub-'+v.key);if(!panel)return;
    const gData=globalArr.find(g=>REGION_MAP[g.region]===v.key)||{};
    const analysis=gData.analysis||gv[v.key]||'';
    let html='';
    const gi=gData.indicators||{};
    const giMeta=gData.indicatorMeta||{};
    const SRC_MAP={us:{gdp:'BEA',cpi:'BLS',rate:'Federal Reserve',unemployment:'BLS'},china:{gdp:'NBS',cpi:'NBS',rate:'PBoC',unemployment:'NBS'},eu:{gdp:'Eurostat',cpi:'Eurostat',rate:'ECB',unemployment:'Eurostat'},uk:{gdp:'ONS',cpi:'ONS',rate:'Bank of England',unemployment:'ONS'}};
    const srcs=SRC_MAP[v.key]||{};
    const hasInd=gi.gdp||gi.cpi||gi.rate||gi.unemployment;
    if(hasInd){
      html+='<div class="indicator-strip" style="margin-bottom:16px">';
      [{key:'gdp',label:'GDP'},{key:'cpi',label:'CPI'},{key:'rate',label:'POLICY RATE'},{key:'unemployment',label:'UNEMPLOYMENT'}].forEach(x=>{
        if(!gi[x.key])return;
        const gm=giMeta[x.key]||{};const chg=gm.change||'';
        const chgCls=chg.startsWith('-')?'change-down':chg.startsWith('+')?'change-up':'change-flat';
        html+='<div class="indicator-pill"><div class="indicator-pill-label">'+x.label+'</div><div class="indicator-pill-value">'+gi[x.key]+'</div>';
        if(chg)html+='<div class="indicator-pill-change '+chgCls+'">'+chg+'</div>';
        html+='<div class="indicator-pill-meta">'+(srcs[x.key]||'')+(gm.period?' \u00b7 '+gm.period:'')+'</div></div>';
      });
      html+='</div>';
    }
    if(analysis){
      html+='<div class="card fade-in"><div class="card-header">'+v.name+' Analysis</div><div class="card-body">'+san(linkFootnotes(analysis,gData.sources||[]))+'</div>';
      if(gData.sources&&gData.sources.length)html+=sourcesFooter(gData.sources);
      html+='</div>';
    }
    if(!analysis&&!hasInd){
      html+='<div class="empty-state" style="padding:48px 16px"><div class="empty-state-text">'+v.name+' analysis will be available after the next pipeline run.</div></div>';
    }
    panel.innerHTML=html;
    _nationalSubRendered[v.key]=true;
  });
}
function renderGlobalPlayerSub(key){
  renderAllGlobalPlayers();
}
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
  charts[key]=new Chart(canvas,{type:'bar',data:{labels:found.map(f=>f.label),datasets:[{label:'Current',data:found.map(f=>f.current),backgroundColor:'#2563EB',borderRadius:4,barPercentage:0.6},{label:'Previous',data:found.map(f=>f.prev),backgroundColor:'#CBD5E1',borderRadius:4,barPercentage:0.6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{boxWidth:10,padding:8,font:{family:'Outfit',size:10},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>ctx.dataset.label+': '+fmtNum(ctx.raw)}}},scales:{x:{grid:{display:false},ticks:{font:{family:'Outfit',size:9},color:'#475569'}},y:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Outfit',size:9},color:'#475569'}}}}});
}
function _renderCommodityChart(canvasId,cardId,prefix){
  const withPct=(_chartComms||[]).filter(c=>c.pct_1w&&c.pct_1w!=='N/A').map(c=>({name:(c.name||c.indicator_name||'').replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),pct:parseFloat(c.pct_1w)||0})).filter(c=>Math.abs(c.pct)>0.1);
  withPct.sort((a,b)=>Math.abs(b.pct)-Math.abs(a.pct));
  const top=withPct.slice(0,8);if(top.length<3)return;
  const canvas=$(canvasId);if(!canvas)return;
  const card=$(cardId);if(card)card.style.display='';
  const key='_cc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart(canvas,{type:'bar',data:{labels:top.map(c=>c.name),datasets:[{data:top.map(c=>c.pct),backgroundColor:top.map(c=>c.pct>=0?'#10B981':'#EF4444'),borderRadius:4,barPercentage:0.65}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%'}}},scales:{x:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Outfit',size:9},color:'#475569',callback:v=>(v>=0?'+':'')+v+'%'}},y:{grid:{display:false},ticks:{font:{family:'Outfit',size:9,weight:500},color:'#1a2744'}}}}});
}
function _renderPipelineChart(canvasId,prefix,projPool){
  const projects=projPool||_chartProjects||[];if(!projects.length)return;
  const statusOrder=['Proposed','Under Review','Approved','Under Construction','Partially Complete','Complete','On Hold','Cancelled'];
  const statusColors=['#94A3B8','#60A5FA','#3B82F6','#2563EB','#1D4ED8','#15803D','#F59E0B','#EF4444'];
  const statusCounts={};projects.forEach(p=>{const s=p.status||'Proposed';statusCounts[s]=(statusCounts[s]||0)+1});
  const pL=[],pD=[],pC=[];statusOrder.forEach((s,i)=>{if(statusCounts[s]){pL.push(s);pD.push(statusCounts[s]);pC.push(statusColors[i])}});
  if(!pD.length)return;
  const key='_pl_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart($(canvasId),{type:'bar',data:{labels:pL,datasets:[{data:pD,backgroundColor:pC,borderRadius:6,barPercentage:0.7}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>fmtNum(ctx.raw,0)+' projects'}}},scales:{x:{grid:{display:false},ticks:{font:{family:'Outfit',size:9},color:'#475569'}},y:{grid:{display:false},ticks:{font:{family:'Outfit',size:9,weight:500},color:'#1a2744'}}}}});
}
function _renderSectorChart(canvasId,prefix,projPool){
  const projects=projPool||_chartProjects||[];if(!projects.length)return;
  const sectorVal={};projects.forEach(p=>{const s=p.sector||'Other';const v=parseNumericValue(p.value);sectorVal[s]=(sectorVal[s]||0)+v});
  const sorted=Object.entries(sectorVal).sort((a,b)=>b[1]-a[1]);
  const top8=sorted.slice(0,8);const ov=sorted.slice(8).reduce((s,e)=>s+e[1],0);
  if(ov>0)top8.push(['Other',ov]);if(!top8.length)return;
  const key='_sc_'+prefix;if(charts[key])charts[key].destroy();
  charts[key]=new Chart($(canvasId),{type:'doughnut',data:{labels:top8.map(e=>e[0].replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())),datasets:[{data:top8.map(e=>e[1]),backgroundColor:_chartCfg.palCat.slice(0,top8.length),borderWidth:0,hoverOffset:6}]},options:{responsive:true,maintainAspectRatio:false,cutout:'55%',plugins:{legend:{position:'right',labels:{boxWidth:10,padding:6,font:{family:'Outfit',size:9},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{..._chartCfg.tt,callbacks:{label:ctx=>ctx.label+': '+_chartCfg.fv(ctx.raw)}}}}});
}
async function renderWovenCharts(ctx,projPool){
  await _ensureChartData();
  const p=ctx;
  _renderMacroChart(p+'MacroChart',p+'MacroCard',p);
  _renderCommodityChart(p+'CommodityChart',p+'CommodityCard',p);
  if($(p+'PipelineChart'))_renderPipelineChart(p+'PipelineChart',p,projPool);
  if($(p+'SectorChart'))_renderSectorChart(p+'SectorChart',p,projPool);
}

/* ====== INFOGRAPHICS (legacy — kept for non-TL;DR tabs) ====== */
async function renderInfographics(){
  const container=$('infographicsContainer');
  if(!container)return;
  const ttCfg={backgroundColor:'rgba(15,23,42,0.92)',titleColor:'#fff',bodyColor:'#CBD5E1',padding:10,cornerRadius:8};
  const fv=v=>v>=1e9?'$'+(v/1e9).toFixed(1)+'B':v>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+fmtNum(v,0);
  const palBlue=['#1E40AF','#2563EB','#3B82F6','#60A5FA','#93C5FD','#BFDBFE','#DBEAFE','#94A3B8','#CBD5E1'];
  const palCat=['#2563EB','#10B981','#F59E0B','#8B5CF6','#EC4899','#EF4444','#0EA5E9','#84CC16','#94A3B8'];

  // Load data sources
  let projects=[],comms=[];
  try{const d=await fetchJSON('projects_all.json');projects=Array.isArray(d)?d:[]}catch(e){}
  try{
    const cd=await fetchJSON('commodities.json');
    comms=Array.isArray(cd)?cd:Object.values(cd).flat().filter(c=>c&&c.pct_1w);
  }catch(e){}

  // Check for editorial directives from the pipeline
  const directives=(D&&D.infographic_directives&&D.infographic_directives.length>=2)?D.infographic_directives:null;

  // Build chart from a directive
  function buildDirectiveChart(dir,canvasId){
    const src=dir.data_source;const metric=dir.metric||'count';const filter=dir.filter||{};
    const groupBy=dir.group_by||'name';const topN=filter.top_n||10;
    const sortDir=dir.sort||'desc';
    let items=[];

    if(src==='indicators'){
      const names=filter.names||[];
      let pool=names.length?indicators.filter(x=>names.some(n=>x.indicator_name&&x.indicator_name.includes(n))):indicators.filter(x=>!x.province||x.province==='National'||x.province==='national');
      items=pool.map(x=>({label:(x.indicator_name||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()),value:parseFloat(x.value)||0,prev:parseFloat(x.previous_value)||0,change:parseFloat(x.change)||0})).filter(x=>x.value);
    }else if(src==='commodities'){
      const names=filter.names||[];
      let pool=names.length?comms.filter(c=>{const n=(c.name||c.indicator_name||'').toLowerCase();return names.some(f=>n.includes(f.toLowerCase()))}):comms;
      items=pool.filter(c=>c.pct_1w&&c.pct_1w!=='N/A').map(c=>({label:(c.name||c.indicator_name||'').replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),value:parseFloat(c.pct_1w)||0}));
    }else if(src==='projects'||src==='sectors'){
      let pool=projects;
      if(filter.sectors)pool=pool.filter(p=>filter.sectors.includes(p.sector));
      if(filter.statuses)pool=pool.filter(p=>filter.statuses.includes(p.status));
      if(filter.provinces)pool=pool.filter(p=>filter.provinces.includes(p.province));
      const grouped={};
      pool.forEach(p=>{
        const key=groupBy==='sector'?(p.sector||'Other'):groupBy==='province'?(p.province||'Unknown'):groupBy==='status'?(p.status||'Proposed'):(p.name||'');
        if(!grouped[key])grouped[key]={count:0,value:0};
        grouped[key].count++;grouped[key].value+=parseNumericValue(p.value);
      });
      items=Object.entries(grouped).map(([k,v])=>({label:k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()),value:metric==='value'?v.value:v.count}));
    }

    if(sortDir==='desc')items.sort((a,b)=>b.value-a.value);
    else if(sortDir==='asc')items.sort((a,b)=>a.value-b.value);
    else items.sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
    items=items.slice(0,topN);
    if(!items.length)return false;

    const chartType=dir.type==='horizontal_bar'?'bar':dir.type||'bar';
    const isHoriz=dir.type==='horizontal_bar';
    const isDoughnut=chartType==='doughnut';
    const labels=items.map(i=>i.label);
    const data=items.map(i=>i.value);

    const colors=src==='commodities'?data.map(v=>v>=0?'#10B981':'#EF4444'):isDoughnut?palCat.slice(0,data.length):palBlue.slice(0,data.length);

    const canvas=document.getElementById(canvasId);
    if(!canvas)return false;
    const chartKey='_ig_'+canvasId;
    if(charts[chartKey])charts[chartKey].destroy();

    // Determine unit and formatting from directive
    const unit=dir.unit||'';
    const isCurrency=metric==='value'||unit==='$'||unit==='CAD';
    const isPct=src==='commodities'||metric==='pct_change'||unit==='%';
    const isCount=metric==='count'||(!isCurrency&&!isPct);
    const unitSuffix=unit&&unit!=='$'&&unit!=='%'&&unit!=='CAD'?' '+unit:'';

    function fmtAxis(v){
      if(isPct)return(v>=0?'+':'')+v+'%';
      if(isCurrency)return fv(v);
      return fmtNum(v,0)+unitSuffix;
    }
    function fmtTooltip(ctx){
      if(isPct)return(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'%';
      if(isCurrency)return fv(ctx.raw);
      return fmtNum(ctx.raw,0)+unitSuffix+(isCount&&src==='projects'?' projects':'');
    }

    const opts={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:isDoughnut,position:'right',labels:{boxWidth:10,padding:8,font:{family:'Outfit',size:11},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{...ttCfg,callbacks:{label:fmtTooltip}}}};

    if(!isDoughnut){
      opts.indexAxis=isHoriz?'y':'x';
      const valueAxis={grid:{display:true,color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Outfit',size:10},color:'#475569',callback:fmtAxis}};
      const labelAxis={grid:{display:false},ticks:{font:{family:'Outfit',size:10,weight:isHoriz?500:400},color:isHoriz?'#1a2744':'#475569'}};
      opts.scales=isHoriz?{x:valueAxis,y:labelAxis}:{x:labelAxis,y:valueAxis};
    }else{opts.cutout='55%'}

    charts[chartKey]=new Chart(canvas,{type:chartType,data:{labels,datasets:[{data,backgroundColor:colors,borderWidth:isDoughnut?0:0,borderRadius:isDoughnut?0:6,barPercentage:0.65,hoverOffset:isDoughnut?6:0}]},options:opts});
    return true;
  }

  if(directives){
    // Editorial mode — render directive-driven charts
    let html='';
    for(let i=0;i<directives.length;i+=2){
      html+='<div class="ws-row ws-row-2"'+(i>0?' style="margin-top:20px"':'')+'>';
      for(let j=i;j<Math.min(i+2,directives.length);j++){
        const d=directives[j];const cid='igChart'+j;
        html+='<div class="card fade-in">';
        html+='<div class="card-header">'+san(d.title||'')+'</div>';
        html+='<div style="font-size:var(--text-xs);color:#475569;margin:-6px 0 10px">'+san(d.subtitle||'')+'</div>';
        html+='<div style="height:220px;position:relative"><canvas id="'+cid+'"></canvas></div>';
        if(d.insight)html+='<div style="font-size:var(--text-xs);color:#2563EB;margin-top:8px;font-weight:500;border-left:3px solid #2563EB;padding-left:8px">'+san(d.insight)+'</div>';
        html+='</div>';
      }
      html+='</div>';
    }
    container.innerHTML=html;
    // Render each directive chart
    directives.forEach((d,i)=>buildDirectiveChart(d,'igChart'+i));
  }else{
    // Default mode — static fallback charts
    container.innerHTML=`
    <div class="ws-row ws-row-2">
      <div class="card fade-in" id="macroPulseCard" style="display:none">
        <div class="card-header">Macro Pulse</div>
        <div style="font-size:var(--text-xs);color:#475569;margin:-6px 0 12px">Key national indicators — latest readings vs. previous period</div>
        <div style="height:220px;position:relative"><canvas id="macroPulseChart"></canvas></div>
      </div>
      <div class="card fade-in" id="commodityMoversCard" style="display:none">
        <div class="card-header">Commodity Movers This Week</div>
        <div style="font-size:var(--text-xs);color:#475569;margin:-6px 0 12px">Biggest weekly price changes across energy, metals, and agriculture</div>
        <div style="height:220px;position:relative"><canvas id="commodityMoversChart"></canvas></div>
      </div>
    </div>
    <div class="ws-row ws-row-2" style="margin-top:20px">
      <div class="card fade-in" id="pipelineFunnelCard" style="display:none">
        <div class="card-header">Project Pipeline</div>
        <div style="font-size:var(--text-xs);color:#475569;margin:-6px 0 12px">Capital projects tracked across Canada by lifecycle stage</div>
        <div style="height:220px;position:relative"><canvas id="pipelineFunnelChart"></canvas></div>
      </div>
      <div class="card fade-in" id="sectorDonutCard" style="display:none">
        <div class="card-header">Where Capital Is Flowing</div>
        <div style="font-size:var(--text-xs);color:#475569;margin:-6px 0 12px">Total tracked investment value by sector — top 8 sectors shown</div>
        <div style="height:220px;position:relative"><canvas id="sectorDonutChart"></canvas></div>
      </div>
    </div>`;
    renderDefaultInfographics(projects,comms,ttCfg,fv,palBlue,palCat);
  }
}
function renderDefaultInfographics(projects,comms,ttCfg,fv,palBlue,palCat){
  // Macro Pulse
  if(indicators.length){
    const macroKeys=['unemployment_rate','cpi','gdp_monthly','housing_starts_total','boc_rate','participation_rate'];
    const macroLabels=['Unemployment','CPI','GDP Monthly','Housing Starts','BoC Rate','Participation'];
    const found=[];
    macroKeys.forEach((k,i)=>{
      const ind=indicators.find(x=>x.indicator_name===k&&(!x.province||x.province==='National'||x.province==='national'));
      if(ind&&ind.value!=null)found.push({label:macroLabels[i],current:parseFloat(ind.value)||0,prev:parseFloat(ind.previous_value)||(parseFloat(ind.value)||0)});
    });
    if(found.length>=3){
      $('macroPulseCard').style.display='';
      if(charts._macro)charts._macro.destroy();
      charts._macro=new Chart($('macroPulseChart'),{type:'bar',data:{labels:found.map(f=>f.label),datasets:[
        {label:'Current',data:found.map(f=>f.current),backgroundColor:'#2563EB',borderRadius:4,barPercentage:0.6},
        {label:'Previous',data:found.map(f=>f.prev),backgroundColor:'#CBD5E1',borderRadius:4,barPercentage:0.6}
      ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{boxWidth:10,padding:12,font:{family:'Outfit',size:11},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{...ttCfg,callbacks:{label:ctx=>ctx.dataset.label+': '+fmtNum(ctx.raw)}}},scales:{x:{grid:{display:false},ticks:{font:{family:'Outfit',size:10},color:'#475569'}},y:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Outfit',size:10},color:'#475569'}}}}});
    }
  }
  // Commodity Movers
  const withPct=comms.filter(c=>c.pct_1w&&c.pct_1w!=='N/A').map(c=>({name:(c.name||c.indicator_name||'').replace(/_/g,' ').replace(/\b\w/g,x=>x.toUpperCase()),pct:parseFloat(c.pct_1w)||0})).filter(c=>Math.abs(c.pct)>0.1);
  withPct.sort((a,b)=>Math.abs(b.pct)-Math.abs(a.pct));
  const top10=withPct.slice(0,10);
  if(top10.length>=3){
    $('commodityMoversCard').style.display='';
    if(charts._comMovers)charts._comMovers.destroy();
    charts._comMovers=new Chart($('commodityMoversChart'),{type:'bar',data:{labels:top10.map(c=>c.name),datasets:[{data:top10.map(c=>c.pct),backgroundColor:top10.map(c=>c.pct>=0?'#10B981':'#EF4444'),borderRadius:4,barPercentage:0.65}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{...ttCfg,callbacks:{label:ctx=>(ctx.raw>=0?'+':'')+ctx.raw.toFixed(1)+'% this week'}}},scales:{x:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{font:{family:'Outfit',size:10},color:'#475569',callback:v=>(v>=0?'+':'')+v+'%'}},y:{grid:{display:false},ticks:{font:{family:'Outfit',size:10,weight:500},color:'#1a2744'}}}}});
  }
  // Pipeline
  if(!projects.length)return;
  const statusOrder=['Proposed','Under Review','Approved','Under Construction','Partially Complete','Complete','On Hold','Cancelled'];
  const statusColors=['#94A3B8','#60A5FA','#3B82F6','#2563EB','#1D4ED8','#15803D','#F59E0B','#EF4444'];
  const statusCounts={};
  projects.forEach(p=>{const s=p.status||'Proposed';statusCounts[s]=(statusCounts[s]||0)+1});
  const pLabels=[],pData=[],pColors=[];
  statusOrder.forEach((s,i)=>{if(statusCounts[s]){pLabels.push(s);pData.push(statusCounts[s]);pColors.push(statusColors[i])}});
  if(pData.length){
    $('pipelineFunnelCard').style.display='';
    if(charts._pipeline)charts._pipeline.destroy();
    charts._pipeline=new Chart($('pipelineFunnelChart'),{type:'bar',data:{labels:pLabels,datasets:[{data:pData,backgroundColor:pColors,borderRadius:6,barPercentage:0.7}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{...ttCfg,callbacks:{label:ctx=>fmtNum(ctx.raw,0)+' projects'}}},scales:{x:{grid:{display:false},ticks:{font:{family:'Outfit',size:11},color:'#475569'}},y:{grid:{display:false},ticks:{font:{family:'Outfit',size:11,weight:500},color:'#1a2744'}}}}});
  }
  // Sector Donut
  const sectorVal={};
  projects.forEach(p=>{const s=p.sector||'Other';const v=parseNumericValue(p.value);sectorVal[s]=(sectorVal[s]||0)+v});
  const sorted=Object.entries(sectorVal).sort((a,b)=>b[1]-a[1]);
  const top8=sorted.slice(0,8);
  const otherVal=sorted.slice(8).reduce((s,e)=>s+e[1],0);
  if(otherVal>0)top8.push(['Other',otherVal]);
  const sLabels=top8.map(e=>e[0].replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()));
  const sData=top8.map(e=>e[1]);
  if(sData.length){
    $('sectorDonutCard').style.display='';
    if(charts._sector)charts._sector.destroy();
    charts._sector=new Chart($('sectorDonutChart'),{type:'doughnut',data:{labels:sLabels,datasets:[{data:sData,backgroundColor:palCat.slice(0,sData.length),borderWidth:0,hoverOffset:6}]},options:{responsive:true,maintainAspectRatio:false,cutout:'55%',plugins:{legend:{position:'right',labels:{boxWidth:10,padding:8,font:{family:'Outfit',size:11},color:'#1a2744',usePointStyle:true,pointStyle:'circle'}},tooltip:{...ttCfg,callbacks:{label:ctx=>ctx.label+': '+fv(ctx.raw)}}}}});
  }
}

function renderKeyIndicators(){
  function indVal(name){const i=indicators.find(x=>x.indicator_name===name);return i?i.value:null}
  const m=(D&&D.metrics)||{};const yc=(D&&D.yieldCurve)||[];
  const im=(D&&D.indicatorMeta)||{};

  // Static metadata for grounding each indicator
  const META={
    'POLICY RATE':{imKey:'bocRate',source:'Bank of Canada',freq:'8x/yr',desc:'Overnight target rate'},
    'BOC RATE':{imKey:'bocRate',source:'Bank of Canada',freq:'8x/yr',desc:'Overnight target rate'},
    'GDP':{imKey:'realGdp',source:'Statistics Canada',freq:'Quarterly',desc:'Real GDP growth YoY'},
    'GDP YOY':{imKey:'realGdp',source:'Statistics Canada',freq:'Quarterly',desc:'Real GDP growth YoY'},
    'CPI':{imKey:'cpi',source:'Statistics Canada',freq:'Monthly',desc:'Consumer Price Index YoY'},
    'INFLATION':{imKey:'cpi',source:'Statistics Canada',freq:'Monthly',desc:'Consumer Price Index YoY'},
    'UNEMPLOYMENT':{imKey:'unemployment',source:'Statistics Canada',freq:'Monthly',desc:'National unemployment rate'},
    'JOBS':{imKey:'unemployment',source:'Statistics Canada',freq:'Monthly',desc:'Employment change'},
    'CAD/USD':{imKey:null,source:'Bank of Canada',freq:'Daily',desc:'Canadian dollar exchange rate'},
    'CAD':{imKey:null,source:'Bank of Canada',freq:'Daily',desc:'Canadian dollar exchange rate'},
    '10Y YIELD':{imKey:null,source:'Bank of Canada',freq:'Daily',desc:'Gov. of Canada 10-year bond yield'},
    'HOUSING STARTS':{imKey:'housingStarts',source:'CMHC',freq:'Monthly',desc:'Annualized housing starts (SAAR)'},
    'HOUSING':{imKey:'housingStarts',source:'CMHC',freq:'Monthly',desc:'Annualized housing starts (SAAR)'},
    'WAGE GROWTH':{imKey:null,source:'Statistics Canada',freq:'Monthly',desc:'Average hourly wages YoY'},
    'WAGES':{imKey:null,source:'Statistics Canada',freq:'Monthly',desc:'Average hourly wages YoY'},
    'PARTICIPATION':{imKey:null,source:'Statistics Canada',freq:'Monthly',desc:'Labour force participation rate'},
    'TRADE':{imKey:null,source:'Statistics Canada',freq:'Monthly',desc:'Merchandise trade balance'},
    'OIL':{imKey:null,source:'Yahoo Finance',freq:'Daily',desc:'WTI crude oil price'},
    'WTI':{imKey:null,source:'Yahoo Finance',freq:'Daily',desc:'WTI crude oil price'},
  };

  // Pipeline-driven indicators (adapts to each week's narrative)
  const pipelineKI=D&&D.key_indicators;
  let headline;
  if(pipelineKI&&Array.isArray(pipelineKI)&&pipelineKI.length>=4){
    headline=pipelineKI.map(ki=>{
      const lbl=(ki.label||'').toUpperCase();
      const meta=META[lbl]||{};
      const imData=meta.imKey?im[meta.imKey]||{}:{};
      return {label:ki.label||'',value:ki.value||'',change:ki.change||'',
        prev:imData.prev||'',period:imData.period||'',
        source:meta.source||'',freq:meta.freq||'',desc:meta.desc||''};
    });
  }else{
    // Default fallback — core macro indicators
    headline=[
      {label:'POLICY RATE',value:m.bocRate||m.boc_rate||indVal('overnight_rate')||''},
      {label:'GDP',value:m.realGdp||m.gdp||indVal('realGdp')||''},
      {label:'CPI',value:m.cpi||indVal('cpi')||''},
      {label:'UNEMPLOYMENT',value:m.unemployment||indVal('unemployment')||''},
      {label:'CAD/USD',value:m.cadUsd||m.cad_usd||indVal('cad_usd')||''},
      {label:'10Y YIELD',value:(yc.find(y=>y.term==='10Y')||{}).yield||indVal('goc_10y_yield')||''},
      {label:'HOUSING STARTS',value:m.housingStarts||m.housing_starts||indVal('housingStarts')||''}
    ].map(h=>{
      const meta=META[h.label]||{};
      const imData=meta.imKey?im[meta.imKey]||{}:{};
      return Object.assign(h,{change:imData.change||'',prev:imData.prev||'',
        period:imData.period||'',source:meta.source||'',freq:meta.freq||'',desc:meta.desc||''});
    });
  }
  let strip='<div class="indicator-strip">';
  headline.forEach(h=>{
    const chg=h.change||'';
    const chgCls=chg.startsWith('-')?'change-down':chg.startsWith('+')?'change-up':'change-flat';
    strip+=`<div class="indicator-pill" title="${h.desc}"><div class="indicator-pill-label">${h.label}</div><div class="indicator-pill-value">${h.value||'N/A'}</div>`;
    if(chg)strip+=`<div class="indicator-pill-change ${chgCls}">${chg}${h.prev?' (prev '+h.prev+')':''}</div>`;
    if(h.source||h.period)strip+=`<div class="indicator-pill-meta">${h.source}${h.period?' \u00b7 '+h.period:''}${h.freq?' \u00b7 '+h.freq:''}</div>`;
    strip+='</div>';
  });
  strip+='</div>';
  $('keyIndicators').innerHTML=strip;
}


/* == Indicator Dropdown (reused in Overview + Provinces) == */
function renderIndicatorDropdown(inds,title,idSuffix){
  const id='indDropdown'+(idSuffix||'');const filtId='indFilter'+(idSuffix||'');
  const n=inds.length;
  let html='<div class="indicator-dropdown"><button class="indicator-dropdown-toggle" onclick="this.classList.toggle(\x27open\x27);this.nextElementSibling.classList.toggle(\x27open\x27)">'+title+' ('+n+') <span class="chevron">\u25be</span></button>';
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
  ]},
  {group:'Ontario (OEA)',items:[
    {id:'on_real_consumption',label:'ON Real Consumption',unit:'$M',source:'Ontario Economic Accounts',url:'https://data.ontario.ca/dataset/ontario-economic-accounts',prov:false},
    {id:'on_real_household',label:'ON Household Spending',unit:'$M',source:'Ontario Economic Accounts',prov:false},
    {id:'on_real_gov_expenditure',label:'ON Gov Expenditure',unit:'$M',source:'Ontario Economic Accounts',prov:false},
    {id:'on_real_capital_investment',label:'ON Capital Investment',unit:'$M',source:'Ontario Economic Accounts',prov:false},
    {id:'on_exports',label:'ON Exports',unit:'$M',source:'Ontario Economic Accounts',prov:false},
    {id:'on_imports',label:'ON Imports',unit:'$M',source:'Ontario Economic Accounts',prov:false},
    {id:'on_gdp_goods',label:'ON GDP Goods-Producing',unit:'$M',source:'Ontario Economic Accounts',prov:false},
    {id:'on_consumption_pct',label:'ON Consumption Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false},
    {id:'on_household_pct',label:'ON Household Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false},
    {id:'on_gov_expenditure_pct',label:'ON Gov Spend Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false},
    {id:'on_capital_investment_pct',label:'ON Capital Inv Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false},
    {id:'on_exports_pct',label:'ON Exports Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false},
    {id:'on_imports_pct',label:'ON Imports Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false},
    {id:'on_gdp_goods_pct',label:'ON GDP Goods Q/Q %',unit:'%',source:'Ontario Economic Accounts',prov:false}
  ]},
  {group:'Quebec (ISQ)',items:[
    {id:'qc_real_gdp',label:'QC Real GDP',unit:'$M',source:'ISQ',url:'https://statistique.quebec.ca/en/document/comptes-economiques-du-quebec-quaterly',prov:false},
    {id:'qc_nominal_gdp',label:'QC Nominal GDP',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_household_consumption',label:'QC Household Spending',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_gov_consumption',label:'QC Gov Spending',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_business_investment',label:'QC Business Investment',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_exports',label:'QC Exports',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_imports',label:'QC Imports',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_compensation',label:'QC Employee Compensation',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_household_income',label:'QC Household Income',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_real_gdp_pct',label:'QC Real GDP Q/Q %',unit:'%',source:'ISQ',prov:false},
    {id:'qc_monthly_gdp',label:'QC Monthly GDP',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_housing_starts',label:'QC Housing Starts',unit:'units',source:'ISQ',prov:false},
    {id:'qc_retail_sales',label:'QC Retail Sales',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_manufacturing_sales',label:'QC Manufacturing Sales',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_wholesale_sales',label:'QC Wholesale Sales',unit:'$M',source:'ISQ',prov:false},
    {id:'qc_weekly_earnings',label:'QC Avg Weekly Earnings',unit:'$',source:'ISQ',prov:false},
    {id:'qc_employment',label:'QC Employment',unit:'K',source:'ISQ',prov:false},
    {id:'qc_unemployment_rate',label:'QC Unemployment Rate',unit:'%',source:'ISQ',prov:false},
    {id:'qc_participation_rate',label:'QC Participation Rate',unit:'%',source:'ISQ',prov:false},
    {id:'qc_cpi',label:'QC CPI Index',unit:'index',source:'ISQ',prov:false}
  ]}
];

let _indExpData={},_indExpSel='overnight_rate',_indExpRange=12,_indExpProv='national';

function renderIndicatorExplorer(){
  // Build selector
  let selHtml='<div class="card fade-in"><div class="card-header">Indicator Explorer</div><div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px">';
  selHtml+='<select id="indExpSelect" onchange="onIndExpChange()" style="padding:6px 10px;border-radius:6px;border:1px solid #c0c0c0;background:#f0f0f0;color:#1a2744;font-size:var(--text-sm)">';
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
    selHtml+='<select id="indExpProv" onchange="onIndExpChange()" style="padding:6px 10px;border-radius:6px;border:1px solid #c0c0c0;background:#f0f0f0;color:#1a2744;font-size:var(--text-sm)">';
    selHtml+='<option value="national"'+((_indExpProv==='national')?' selected':'')+'>National</option>';
    PROVS.forEach(p=>{selHtml+='<option value="'+p.code+'"'+(_indExpProv===p.code?' selected':'')+'>'+p.name+'</option>'});
    selHtml+='</select>';
  }
  // Time range buttons
  selHtml+='<div style="display:flex;gap:4px">';
  [3,12,36,60].forEach(m=>{
    const lbl=m===3?'3M':m===12?'1Y':m===36?'3Y':'5Y';
    const active=_indExpRange===m?'background:#2563EB;color:#FFFFFF':'background:rgba(0,0,0,0.05);color:#475569';
    selHtml+='<button onclick="_indExpRange='+m+';loadIndExpData()" style="padding:4px 10px;border-radius:4px;border:none;cursor:pointer;font-size:var(--text-xs);'+active+'">'+lbl+'</button>';
  });
  selHtml+='</div></div>';
  // Callout + chart
  selHtml+='<div id="indExpCallout" style="margin-bottom:8px"></div>';
  selHtml+='<div style="height:200px;position:relative"><canvas id="indExpCanvas"></canvas></div>';
  // Source link
  if(selItem){
    const linkUrl=selItem.statcan?'https://www150.statcan.gc.ca/n1/en/type/data':selItem.url||'#';
    const linkLabel=selItem.statcan?'View on StatsCan \u2197':selItem.source+' \u2197';
    selHtml+='<div style="margin-top:8px;text-align:right"><a href="'+linkUrl+'" target="_blank" rel="noopener noreferrer" style="font-size:var(--text-xs);color:var(--accent-blue)">'+linkLabel+'</a></div>';
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
    const cls=diff>0?'change-up':diff<0?'change-down':'change-flat';
    const allVals=allPts.map(p=>p.value);
    const mn=fmtNum(Math.min(...allVals));const mx=fmtNum(Math.max(...allVals));
    callout.innerHTML='<div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap"><span style="font-size:1.5rem;font-weight:700;font-family:Outfit,sans-serif">'+fmtNum(latest.value)+'</span><span class="'+cls+'" style="font-family:var(--font-mono);font-size:var(--text-sm)">'+arrow+' '+(diff>=0?'+':'')+fmtNum(diff)+' vs prev</span><span style="font-family:var(--font-mono);font-size:var(--text-xs);color:var(--text-muted)">5Y range: '+mn+' \u2013 '+mx+'</span><span style="font-size:var(--text-xs);color:var(--text-muted)">'+latest.date+'</span></div>';
  }else if(pts.length===1){
    callout.innerHTML='<span style="font-size:1.5rem;font-weight:700;font-family:Outfit,sans-serif">'+fmtNum(pts[0].value)+'</span>';
  }else{
    callout.innerHTML='<span style="color:var(--text-muted);font-size:var(--text-sm)">No data for this period.</span>';
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
          evtAnnotations['evt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(245,158,11,0.5)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(evt.event_name||evt.name||'').substring(0,20),position:'start',backgroundColor:'rgba(245,158,11,0.85)',color:'#fff',font:{family:'Work Sans',size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
        }catch(evtErr){}
      });
    }
  }catch(annErr){console.warn('Event annotations:',annErr)}
  const hasAnnotationPlugin=typeof window.ChartAnnotation!=='undefined'||(typeof Chart!=='undefined'&&Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation'));
  const bandAnnotation=(bandLow!==null&&bandHigh!==null)?{band:{type:'box',yMin:bandLow,yMax:bandHigh,backgroundColor:'rgba(59,130,246,0.06)',borderWidth:0}}:{};
  const annotationCfg=hasAnnotationPlugin?{annotation:{annotations:{...bandAnnotation,...evtAnnotations}}}:{};
  const endpointPlugin={id:'endpointLabel',afterDraw(chart){try{const ds=chart.data.datasets[0];if(!ds||!ds.data||!ds.data.length)return;const lastVal=ds.data[ds.data.length-1];if(lastVal==null)return;const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 11px Outfit';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):String(lastVal),lastPt.x+6,lastPt.y-4);ctx.restore();}catch(e){}}};
  const chartCfg={type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.08)',borderWidth:2,pointRadius:pts.length>60?0:3,pointBackgroundColor:'#3B82F6',fill:true,tension:0.3}]},plugins:[endpointPlugin],options:{responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:'index'},plugins:{legend:{display:false},...annotationCfg,tooltip:{backgroundColor:'rgba(45,75,130,0.95)',titleColor:'#ffffff',bodyColor:'#93C5FD',borderColor:'rgba(255,255,255,0.12)',borderWidth:1,padding:10,cornerRadius:6,callbacks:{label:function(ctx){
    const val=ctx.parsed.y;const idx=ctx.dataIndex;
    if(idx>0){const prev=data[idx-1];const diff=val-prev;return fmtNum(val)+' ('+(diff>=0?'+':'')+fmtNum(diff)+' vs prev)';}
    return fmtNum(val);
  }}}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{family:'Work Sans',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'Outfit',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}};
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
      .style('font-size',d=>d.size+'px').style('font-family','Outfit')
      .style('font-weight',d=>d.size>30?'700':d.size>20?'600':'400')
      .style('fill',d=>d.score>0.05?'#065F46':d.score<-0.05?'#991B1B':'#334155')
      .style('opacity',d=>0.5+Math.min(d.size/40,0.5))
      .style('cursor','pointer')
      .attr('text-anchor','middle').attr('transform',d=>'translate('+d.x+','+d.y+') rotate('+d.rotate+')')
      .text(d=>d.text)
      .append('title').text(d=>d.text+'\nSentiment: '+d.score.toFixed(2)+'\nFrequency: '+d.freq);
  }
}

/* == Trend Summary == */
async function renderTrendSummary(){
  const el=$('trendSummary');if(!el)return;
  try{
    let narrative='';
    const briefing=await fetchJSON('briefing_latest.json');
    if(briefing&&briefing.content)narrative=briefing.content;
    if(!narrative){el.innerHTML='';return}
    const pdfUrl=(briefing&&briefing.pdf_url)||'';const docxUrl=(briefing&&briefing.docx_url)||'';
    const dlBtns=(pdfUrl||docxUrl)?`<div style="display:flex;gap:8px;margin-bottom:12px">${pdfUrl?`<a href="${san(pdfUrl)}" target="_blank" download style="font-size:var(--text-xs);background:#EC4899;color:#fff;padding:6px 14px;border-radius:6px;text-decoration:none;display:inline-flex;align-items:center;gap:4px">Download PDF</a>`:''}${docxUrl?`<a href="${san(docxUrl)}" target="_blank" download style="font-size:var(--text-xs);background:#3B82F6;color:#fff;padding:6px 14px;border-radius:6px;text-decoration:none;display:inline-flex;align-items:center;gap:4px">Download Word</a>`:''}</div>`:'';
    if(_editorialMode){
      // Editorial: narrative flows as prose in main column; charts are in sidebar
      el.innerHTML=`<div class="fade-in"><hr class="editorial-rule"><div class="editorial-section-label">Weekly Briefing</div>${dlBtns}<div class="editorial-prose" style="white-space:pre-line">${san(narrative)}</div></div>`;
    }else{
      el.innerHTML=`<div class="card fade-in"><div class="card-header">Weekly Intelligence Briefing</div><div class="card-body">${dlBtns}<div style="line-height:1.65;color:var(--text-secondary);white-space:pre-line">${san(narrative)}</div><div class="ws-row ws-row-2" style="margin-top:16px"><div class="card" id="briefPipelineCard"><div class="card-header" style="font-size:var(--text-sm)">Project Pipeline</div><div style="font-size:8px;color:#475569;margin:-4px 0 8px">Capital projects by lifecycle stage</div><div style="height:180px;position:relative"><canvas id="briefPipelineChart"></canvas></div><div style="font-size:8px;color:#64748B;margin-top:6px;border-top:1px solid rgba(0,0,0,0.06);padding-top:4px">Source: Pipeline database</div></div><div class="card" id="briefSectorCard"><div class="card-header" style="font-size:var(--text-sm)">Capital by Sector</div><div style="font-size:8px;color:#475569;margin:-4px 0 8px">Tracked investment by sector</div><div style="height:180px;position:relative"><canvas id="briefSectorChart"></canvas></div><div style="font-size:8px;color:#64748B;margin-top:6px;border-top:1px solid rgba(0,0,0,0.06);padding-top:4px">Source: Pipeline database</div></div></div></div></div>`;
      renderWovenCharts('brief');
    }
  }catch(e){console.warn('Trend summary:',e);el.innerHTML=''}
}

/* == Global Vectors == */
function renderGlobalVectors(){
  const gv=D.globalVectors||D.global_vectors||{};
  const globalArr=D.global||[];
  const REGION_MAP={'United States':'us','China':'china','European Union':'eu','United Kingdom':'uk'};
  const vectors=[
    {key:'us',name:'United States',cls:'gv-us'},
    {key:'china',name:'China',cls:'gv-china'},
    {key:'eu',name:'European Union',cls:'gv-eu'},
    {key:'uk',name:'United Kingdom',cls:'gv-uk'}
  ];
  let html='<h2 style="font-size:var(--text-lg);font-weight:700;margin-bottom:12px">Global Players</h2>';
  let hasAny=false;
  vectors.forEach(v=>{
    // Try rich global array first, fall back to globalVectors text
    const gData=globalArr.find(g=>REGION_MAP[g.region]===v.key)||{};
    const vectorText=gv[v.key]||'';
    const analysis=gData.analysis||vectorText;
    if(!analysis)return;
    hasAny=true;
    html+='<div class="gv-card '+v.cls+' fade-in"><div class="gv-header">'+v.name+'</div>';
    // Show indicators if available
    const gi=gData.indicators||{};
    const hasInd=gi.gdp||gi.cpi||gi.rate||gi.unemployment;
    if(hasInd){
      html+='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">';
      if(gi.gdp)html+='<div class="indicator-pill" style="padding:4px 10px"><div class="indicator-pill-label">GDP</div><div class="indicator-pill-value">'+gi.gdp+'</div></div>';
      if(gi.cpi)html+='<div class="indicator-pill" style="padding:4px 10px"><div class="indicator-pill-label">CPI</div><div class="indicator-pill-value">'+gi.cpi+'</div></div>';
      if(gi.rate)html+='<div class="indicator-pill" style="padding:4px 10px"><div class="indicator-pill-label">Rate</div><div class="indicator-pill-value">'+gi.rate+'</div></div>';
      if(gi.unemployment)html+='<div class="indicator-pill" style="padding:4px 10px"><div class="indicator-pill-label">Unemployment</div><div class="indicator-pill-value">'+gi.unemployment+'</div></div>';
      html+='</div>';
    }
    html+='<div class="gv-body">'+san(linkFootnotes(analysis,gData.sources||[]))+'</div>';
    if(gData.sources&&gData.sources.length)html+=sourcesFooter(gData.sources);
    html+='</div>';
  });
  if(!hasAny)html+='<div class="empty-state"><div class="empty-state-text">Global vector analysis not yet available.</div></div>';
  $('globalVectors').innerHTML=html;
}


/* ====== PROVINCES TAB ====== */
function renderProvinces(){
  // Province selector pills
  let sel='';
  PROVS.forEach(p=>{
    sel+='<div class="province-pill'+(p.code===selectedProvince?' active':'')+'" data-prov="'+p.code+'" onclick="window.selectProvince(this.dataset.prov)">'+p.code+'</div>';
  });
  $('provSelector').innerHTML=sel;
  renderProvinceContent();
}
window.selectProvince=function(code){
  selectedProvince=code;
  document.querySelectorAll('.province-pill').forEach(p=>p.classList.toggle('active',p.dataset.prov===code));
  // Update banner image and province map silhouette
  const img=PROV_IMGS[code]||PROV_IMGS.BC;
  $('provBanner').style.setProperty('--banner-img',"url('"+img+"')");
  renderProvinceContent();
};
async function renderProvinceContent(){
  const prov=PROVS.find(p=>p.code===selectedProvince)||PROVS[0];
  $('provBannerTitle').textContent=prov.name;
  if(_lastLoadedProvince!==prov.code){await loadProjects(prov.code)}
  const provArr=D?(D.provinces||[]):[];
  const norm=s=>(s||'').toLowerCase().replace(/&/g,'and').replace(/[^a-z]/g,'');
  const provData=provArr.find(p=>norm(p.name)===norm(prov.name))||{};
  const provInd=provData.indicators||{};
  const provMeta=provData.indicatorMeta||{};
  const provPrefix=prov.code.toLowerCase();
  function provIndVal(key){
    const nameMap={gdp:'realGdp',unemployment:'unemployment',cpi:'cpi',housingStarts:'housingStarts',participationRate:'participationRate',employmentRate:'employmentRate',populationGrowth:'populationGrowth',buildingPermits:'buildingPermits'};
    const indName=nameMap[key]||key;
    const provMatch=indicators.find(x=>x.indicator_name===provPrefix+'_'+indName);
    if(provMatch)return provMatch.value;
    const natMatch=indicators.find(x=>x.indicator_name===indName);
    return natMatch?natMatch.value:null;
  }

  // Expanded indicator set (8)
  const provIndicators=[
    {label:'GDP YoY',value:provInd.gdp||provIndVal('gdp')||'N/A',change:(provMeta.gdp||{}).change||'',source:'Statistics Canada',metaKey:'gdp'},
    {label:'Unemployment',value:provInd.unemployment||provIndVal('unemployment')||'N/A',change:(provMeta.unemployment||{}).change||'',source:'Statistics Canada',metaKey:'unemployment'},
    {label:'CPI',value:provInd.cpi||provIndVal('cpi')||'N/A',change:(provMeta.cpi||{}).change||'',source:'Statistics Canada',metaKey:'cpi'},
    {label:'Participation',value:provInd.participationRate||provIndVal('participationRate')||'N/A',change:(provMeta.participationRate||{}).change||'',source:'Statistics Canada',metaKey:'participationRate'},
    {label:'Employment Rate',value:provInd.employmentRate||provIndVal('employmentRate')||'N/A',change:(provMeta.employmentRate||{}).change||'',source:'Statistics Canada',metaKey:'employmentRate'},
    {label:'Housing Starts',value:provInd.housingStarts||provIndVal('housingStarts')||'N/A',change:(provMeta.housingStarts||{}).change||'',source:'CMHC',metaKey:'housingStarts'},
    {label:'Pop. Growth',value:provInd.populationGrowth||provIndVal('populationGrowth')||'N/A',change:'',source:'Statistics Canada',metaKey:'populationGrowth'},
    {label:'Building Permits',value:provInd.buildingPermits||provIndVal('buildingPermits')||'N/A',change:(provMeta.buildingPermits||{}).change||'',source:'Statistics Canada',metaKey:'buildingPermits'}
  ];

  // Editorial header
  const provProj=allProjects.filter(p=>p.province===prov.name||p.province===prov.code);
  const projCount=provProj.length;
  const projValue=provProj.reduce((s,p)=>s+parseNumericValue(p.value),0);
  const fmtVal=projValue>=1e9?'$'+(projValue/1e9).toFixed(1)+'B':projValue>=1e6?'$'+(projValue/1e6).toFixed(0)+'M':'';
  const hdr=$('provEditorialHeader');
  if(hdr){
    hdr.innerHTML='<div class="fade-in"><div class="editorial-eyebrow">Provincial Analysis</div>'+
      '<div class="editorial-headline">'+prov.name+'</div><hr class="editorial-accent">'+
      '</div>';
  }

  // Analysis section with floating indicator panel (includes sector pie chart)
  const provContent=provData.analysis||'';
  const provSources=provData.sources||[];
  const provSubtitle=deriveSubtitle(provContent);
  const sectorCanvas=provProj.length>=3?'pvSectorChart':null;
  const panel=buildIndicatorPanel(prov.name,provIndicators,provSubtitle,sectorCanvas);

  let secHtml='';
  secHtml+=panel.html;
  if(provContent){
    secHtml+=san(linkFootnotes(provContent,provSources.length?provSources:(D&&D.sources||[])));
  }else{
    secHtml+='<p style="color:#475569">No provincial analysis available for '+prov.name+'.</p>';
  }
  if(provSources.length)secHtml+=sourcesFooter(provSources);
  // Upcoming events
  const wl=D&&(D.watchlist||D.events)?D.watchlist||D.events||[]:[];
  const provEvents=wl.filter(e=>{const desc=(e.description||'')+(e.event_name||'');return desc.toLowerCase().includes(prov.name.toLowerCase())});
  if(provEvents.length){
    secHtml+='<details style="margin-top:16px"><summary style="cursor:pointer;font-size:var(--text-sm);font-weight:600;color:#475569">Upcoming Events ('+provEvents.length+')</summary><div style="padding:8px 0;font-size:var(--text-sm);color:#475569">';
    provEvents.forEach(e=>{secHtml+='<div style="margin-bottom:4px">'+(e.date||'')+' \u2014 '+(e.event_name||e.event||'')+(e.institution?' ('+e.institution+')':'')+'</div>'});
    secHtml+='</div></details>';
  }
  secHtml+='<div class="ed-clear"></div>';
  // Insight strip — full width between analysis and projects
  secHtml+=buildInsightStrip('prov',panel.movers);

  const pas=$('provAnalysisSection');
  if(pas)pas.innerHTML=secHtml;

  // Render charts
  if(provProj.length>=3){
    _renderSectorChart('pvSectorChart','pv',provProj);
  }
  renderInsightCharts('prov',panel.movers,indicators,(D&&D.metrics)||{},(provData.indicatorMeta||{}));


  // Projects
  const topProvProj=provProj.slice(0,5);
  let projHtml='<div class="ed-section"><div class="ed-section-title">Major Projects</div><div class="ed-section-subtitle">Top projects in '+prov.name+'</div></div>'+
    '<div class="editorial-meta" style="margin-bottom:12px">'+
    '<div class="editorial-meta-item"><strong>'+projCount+'</strong>Projects Tracked</div>'+
    (fmtVal?'<div class="editorial-meta-item"><strong>'+fmtVal+'</strong>Pipeline Value</div>':'')+
    '</div>';
  if(topProvProj.length){
    projHtml+='<div class="project-table-wrap"><table class="project-table" style="margin-top:8px"><thead><tr><th scope="col">Value</th><th scope="col">Project</th><th scope="col">Status</th><th scope="col">Source</th></tr></thead><tbody>';
    topProvProj.forEach(p=>{
      projHtml+='<tr><td class="col-value">'+fmtCurrency(p.value,p)+'</td><td class="col-name">'+((p.name||'').substring(0,60))+'</td><td>'+statusBadge(p.status||'Proposed')+'</td><td>'+srcLink((p.sources||[])[0]?.url,(p.sources||[])[0]?.title)+'</td></tr>';
    });
    projHtml+='</tbody></table></div>';
    projHtml+='<div style="margin-top:12px;font-size:var(--text-sm)"><a href="#" style="color:var(--accent-blue);text-decoration:none" onclick="event.preventDefault();switchTab(\'projects\')">View all projects \u2192</a></div>';
  }else{
    projHtml+='<div class="empty-state"><div class="empty-state-text">No projects tracked for '+prov.name+' yet.</div></div>';
  }
  $('provProjectsPreview').innerHTML=projHtml;
}



/* ====== INDUSTRIES TAB ====== */
let _industryView='all';
window.toggleIndustryView=function(view){
  _industryView=view;
  document.querySelectorAll('.ind-toggle').forEach(b=>{b.classList.toggle('active',b.dataset.view===view)});
  renderIndustrySectors();
};
function renderIndustries(){
  renderIndustrySectors();
}
function renderIndustrySectors(){
  const goodsArr=(D&&D.goodsIndustries)||[];
  const servArr=(D&&D.servicesIndustries)||[];
  const showGoods=_industryView==='all'||_industryView==='goods';
  const showServ=_industryView==='all'||_industryView==='services';
  let html='';
  if(showGoods){
    html+='<h3 style="font-size:var(--text-sm);font-weight:700;color:#ffffff;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Goods-Producing Industries</h3><div class="sector-grid" style="margin-bottom:16px">';
    goodsArr.forEach(s=>{html+=sectorCard(s)});
    if(!goodsArr.length)['11','21','22','23','31-33'].forEach(code=>{html+=sectorCard({code,name:NAICS_NAMES[code]})});
    html+='</div>';
  }
  if(showServ){
    html+='<h3 style="font-size:var(--text-sm);font-weight:700;color:#ffffff;text-transform:uppercase;letter-spacing:.5px;margin:'+(showGoods?'12px':'0')+' 0 8px">Services-Producing Industries</h3><div class="sector-grid">';
    servArr.forEach(s=>{html+=sectorCard(s)});
    if(!servArr.length)['41','44-45','48-49','51','52','53','54','55','56','61','62','71','72','81','91'].forEach(code=>{html+=sectorCard({code,name:NAICS_NAMES[code]})});
    html+='</div>';
  }
  $('industrySectorGrid').innerHTML=html;
}
function sectorCard(s){
  const code=s.code||'';
  const name=s.name||NAICS_NAMES[code]||code;
  const cls=NAICS_CLS[code]||'';
  const analysis=s.analysis||'';
  const mm=s.mm||'';const yy=s.yy||'';
  const mmCls=s.isNegative?'change-down':'change-up';
  let mmBadge='';
  if(mm||yy)mmBadge='<div style="display:flex;gap:12px;margin-bottom:8px;font-size:var(--text-xs);color:#556B7A">'+(mm?'<span>M/M <span class="'+mmCls+'" style="font-family:var(--font-mono);font-weight:600">'+mm+'</span></span>':'')+(yy?'<span>Y/Y <span style="font-family:var(--font-mono);font-weight:600">'+yy+'</span></span>':'')+(s.indicatorSrc?'<span>'+s.indicatorSrc+'</span>':'')+'</div>';
  return '<div class="sector-card '+cls+'"><div class="sector-card-header"><span class="naics-badge">'+code+'</span><span class="sector-card-name">'+name+'</span></div><div class="sector-card-body">'+mmBadge+(analysis?san(analysis):'<em style="color:#556B7A">No analysis available.</em>')+'</div></div>';
}

/* ====== MARKETS TAB ====== */
function renderMarkets(){
  const fm=(D&&(D.financialMarkets||D.financial_markets||D.markets))||{};
  let indices=fm.indices||[];let fx=fm.fx||[];
  // Build from indicators[] if briefing has no market data
  if(!indices.length&&indicators.length){
    const idxMap=[{name:'S&P/TSX',ind:'tsx_composite'},{name:'S&P/TSX',ind:'tsx'},{name:'S&P 500',ind:'sp500'},{name:'Dow Jones',ind:'djia'},{name:'NASDAQ',ind:'nasdaq'},{name:'FTSE 100',ind:'ftse100'},{name:'DAX',ind:'dax'},{name:'Nikkei 225',ind:'nikkei225'}];
    idxMap.forEach(m=>{const i=indicators.find(x=>x.indicator_name===m.ind);if(i&&!indices.find(x=>x.name===m.name))indices.push({name:m.name,value:i.value,change:'',region:''})});
  }
  if(!fx.length&&indicators.length){
    const fxMap=[{name:'CAD/USD',ind:'cad_usd'},{name:'CAD/USD',ind:'cadusd'},{name:'EUR/USD',ind:'eurusd'},{name:'USD/CNY',ind:'usdcny'},{name:'USD/JPY',ind:'usdjpy'}];
    fxMap.forEach(m=>{const i=indicators.find(x=>x.indicator_name===m.ind);if(i&&!fx.find(x=>x.name===m.name))fx.push({name:m.name,value:i.value})});
  }
  // Equity + Currency cards
  const mktTsMap={'S&P/TSX':'tsx_composite','TSX Composite':'tsx_composite','S&P 500':'sp500','Dow Jones':'djia','NASDAQ':'nasdaq','FTSE 100':'ftse100','DAX':'dax','Nikkei 225':'nikkei225','Hang Seng':'idx_hangseng','Shanghai':'idx_shanghai','CAD/USD':'cadusd','EUR/USD':'eurusd','GBP/USD':'fx_gbpusd','USD/JPY':'usdjpy','USD/CNY':'usdcny','AUD/USD':'fx_audusd','Crude Oil (WTI)':'wti','Crude Oil (Brent)':'brent','Natural Gas':'natural_gas','Gold':'gold','Silver':'silver','Platinum':'platinum','Palladium':'palladium','Copper':'copper','Aluminum':'aluminum','Wheat':'wheat','Corn':'corn','Rice':'comm_rice','Soybeans':'soybeans','Coffee':'coffee','Cocoa':'cocoa','Sugar #11':'sugar','Cotton':'cotton','Soybean Oil':'comm_soyoil','Soybean Meal':'comm_soymeal','Coal (Newcastle)':'comm_coal','Propane':'comm_propane','Lumber':'lumber'};
  const normMktId=(name)=>(name||'').toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
  const mktDate=D?fmtDate(D.updated_at||D.date)||'':'';
  let eqHtml='';let mktSparkJobs=[];let mktIdx=0;
  if(indices.length){
    eqHtml+='<h3 style="font-size:var(--text-sm);font-weight:600;margin:0 0 8px;color:#8ea8cc;text-transform:uppercase;letter-spacing:1px">Equity Indices</h3><div class="market-grid">';
    indices.forEach(item=>{
      const chg=item.change||item.day||'';const isNeg=chg.startsWith('-');
      const cls=isNeg?'change-down':(chg?'change-up':'change-flat');
      const sid='spark_mkt_'+mktIdx++;
      const tsId=mktTsMap[item.name]||null;
      eqHtml+='<div class="market-card" data-cat="equity"><div class="market-card-ticker">'+(item.name||'')+(item.region?' <small style="color:#475569">'+item.region+'</small>':'')+'</div><div class="market-card-price">'+(item.value||'N/A')+'</div>';
      if(chg)eqHtml+='<div class="market-card-change '+cls+'">'+(isNeg?'\u2193':'\u2191')+' '+chg+'</div>';
      if(item.yy)eqHtml+='<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:#475569">YoY: '+item.yy+'</div>';
      if(mktDate)eqHtml+='<div style="font-size:var(--text-xs);color:#666666;margin-top:2px">'+mktDate+'</div>';
      eqHtml+='<div class="sparkline-wrap"><canvas class="sparkline" id="'+sid+'"></canvas></div></div>';
      if(tsId)mktSparkJobs.push({canvasId:sid,docId:tsId,change:chg});
    });
    eqHtml+='</div>';
  }
  if(fx.length){
    eqHtml+='<h3 style="font-size:var(--text-sm);font-weight:600;margin:16px 0 8px;color:#8ea8cc;text-transform:uppercase;letter-spacing:1px">Foreign Exchange</h3><div class="market-grid">';
    fx.forEach(item=>{
      const chg=item.day||'';const isNeg=chg.startsWith('-');
      const cls=isNeg?'change-down':(chg?'change-up':'change-flat');
      const sid='spark_mkt_'+mktIdx++;
      const tsId=mktTsMap[item.name]||null;
      eqHtml+='<div class="market-card" data-cat="fx"><div class="market-card-ticker">'+(item.name||'')+'</div><div class="market-card-price">'+(item.value||'N/A')+'</div>';
      if(chg)eqHtml+='<div class="market-card-change '+cls+'">'+(isNeg?'\u2193':'\u2191')+' '+chg+'</div>';
      if(item.yy)eqHtml+='<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:#475569">YoY: '+item.yy+'</div>';
      if(mktDate)eqHtml+='<div style="font-size:var(--text-xs);color:#666666;margin-top:2px">'+mktDate+'</div>';
      eqHtml+='<div class="sparkline-wrap"><canvas class="sparkline" id="'+sid+'"></canvas></div></div>';
      if(tsId)mktSparkJobs.push({canvasId:sid,docId:tsId,change:chg});
    });
    eqHtml+='</div>';
  }
  $('marketsGrid').innerHTML=eqHtml||'<div class="empty-state"><div class="empty-state-text">No equity/currency data.</div></div>';
  mktSparkJobs.forEach(j=>loadAndDrawSparkline(j.canvasId,j.docId,j.change));

  // Yield curve
  let yc=(D&&D.yieldCurve)||[];
  // Build from indicators[] if briefing has no yield data
  if(!yc.length&&indicators.length){
    const yieldTerms=[{term:'2Y',ind:'goc_2y_yield'},{term:'5Y',ind:'goc_5y_yield'},{term:'10Y',ind:'goc_10y_yield'}];
    yieldTerms.forEach(t=>{const i=indicators.find(x=>x.indicator_name===t.ind);if(i)yc.push({term:t.term,yield:i.value})});
  }
  if(yc.length){
    let ycHtml='<div class="yield-card" style="padding:16px"><h3 style="font-size:var(--text-sm);font-weight:600;margin:0 0 8px;color:#1a2744;text-transform:uppercase;letter-spacing:1px">Gov. of Canada Yield Curve</h3><canvas id="yieldChart" style="width:100%;max-height:200px"></canvas>';
    const y2=yc.find(y=>y.term==='2Y');const y10=yc.find(y=>y.term==='10Y');
    if(y2&&y10){
      const spread=((parseFloat(y10.yield)-parseFloat(y2.yield))*100).toFixed(0);
      ycHtml+='<div class="yield-spread">10Y-2Y Spread: '+spread+'bp';
      if(parseInt(spread)<0)ycHtml+=' <span class="inversion">Inverted</span>';
      ycHtml+='</div>';
    }
    ycHtml+='<a class="market-card-source" href="https://www.bankofcanada.ca/rates/interest-rates/" target="_blank">Bank of Canada Valet API \u2197</a></div>';
    $('yieldCurveCard').innerHTML=ycHtml;
    setTimeout(()=>drawYieldChart(yc),50);
  } else {
    $('yieldCurveCard').innerHTML='<div class="yield-card" style="padding:16px"><div class="empty-state"><div class="empty-state-text" style="color:#475569">No yield curve data.</div></div></div>';
  }

  // Commodities — pipeline stores [{category, color, items: [{name, unit, val, yy, day}]}]
  const rawComms=(D&&D.commodities)||fm.commodities||[];
  // Build commodity cards from indicators[] if pipeline data is empty
  if(!rawComms.length&&indicators.length){
    const commMap=[{name:'Crude Oil (WTI)',ind:'wti'},{name:'Crude Oil (WTI)',ind:'wti_oil'},{name:'Crude Oil (Brent)',ind:'brent'},{name:'Natural Gas',ind:'natural_gas'},{name:'Gold',ind:'gold'},{name:'Silver',ind:'silver'},{name:'Platinum',ind:'platinum'},{name:'Palladium',ind:'palladium'},{name:'Copper',ind:'copper'},{name:'Aluminum',ind:'aluminum'},{name:'Wheat',ind:'wheat'},{name:'Corn',ind:'corn'},{name:'Soybeans',ind:'soybeans'},{name:'Coffee',ind:'coffee'},{name:'Cocoa',ind:'cocoa'},{name:'Sugar #11',ind:'sugar'},{name:'Cotton',ind:'cotton'},{name:'Lumber',ind:'lumber'}];
    commMap.forEach(m=>{const i=indicators.find(x=>x.indicator_name===m.ind);if(i&&!rawComms.find(x=>x.name===m.name))rawComms.push({name:m.name,val:i.value,change:''})});
  }
  let commHtml='';
  const commSparkJobs=[];
  const commCatMap={'Energy':'energy','Precious Metals':'precious','Base Metals':'base','Agriculture - Grains':'agriculture','Agriculture - Softs':'agriculture','Agriculture - Oils & Meals':'agriculture','Fertilizers':'agriculture','Livestock':'agriculture','Forest Products':'forest'};
  if(Array.isArray(rawComms)&&rawComms.length&&rawComms[0].items){
    // Nested category structure from pipeline
    rawComms.forEach(cat=>{
      const dataCat=commCatMap[cat.category]||'energy';
      commHtml+='<h3 style="font-size:var(--text-sm);font-weight:600;margin:16px 0 8px;color:#8ea8cc;text-transform:uppercase;letter-spacing:1px">'+cat.category+'</h3><div class="market-grid">';
      (cat.items||[]).forEach(c=>{
        const yy=c.yy||'';const isNeg=yy.startsWith('-');
        const cls=isNeg?'change-down':(yy?'change-up':'change-flat');
        const cid='spark_comm_'+mktIdx++;
        const tsId=mktTsMap[c.name]||null;
        commHtml+='<div class="market-card" data-cat="'+dataCat+'"><div class="market-card-ticker">'+(c.name||'')+'</div><div class="market-card-price">'+(c.val||'N/A')+(c.unit?' <small style="color:#475569">'+c.unit+'</small>':'')+'</div>';
        if(yy)commHtml+='<div class="market-card-change '+cls+'">'+(isNeg?'\u2193':'\u2191')+' '+yy+' YoY</div>';
        if(c.day)commHtml+='<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:#475569">'+c.day+' today</div>';
        if(mktDate)commHtml+='<div style="font-size:var(--text-xs);color:#666666;margin-top:2px">'+mktDate+'</div>';
        commHtml+='<div class="sparkline-wrap"><canvas class="sparkline" id="'+cid+'"></canvas></div></div>';
        if(tsId)commSparkJobs.push({canvasId:cid,docId:tsId,change:yy});
      });
      commHtml+='</div>';
    });
  } else if(Array.isArray(rawComms)){
    // Flat array fallback
    rawComms.forEach(c=>{
      const chg=c.change||c.yy||'';const isNeg=chg.startsWith('-');
      const cls=isNeg?'change-down':'change-up';
      const cid='spark_comm_'+mktIdx++;
      const tsId=mktTsMap[c.name]||null;
      commHtml+='<div class="market-card" data-cat="energy"><div class="market-card-ticker">'+(c.name||'')+'</div><div class="market-card-price">'+(c.val||c.value||'N/A')+'</div><div class="market-card-change '+cls+'">'+(isNeg?'\u2193':'\u2191')+' '+chg+'</div><div class="sparkline-wrap"><canvas class="sparkline" id="'+cid+'"></canvas></div></div>';
      if(tsId)commSparkJobs.push({canvasId:cid,docId:tsId,change:chg});
    });
  }
  $('commoditiesGrid').innerHTML=commHtml||'<div class="empty-state"><div class="empty-state-text">No commodity data.</div></div>';
  commSparkJobs.forEach(j=>loadAndDrawSparkline(j.canvasId,j.docId,j.change));
  // Canadian-specific commodities
  renderCanadianCommodities();
}

/* == Chart Helpers == */
function drawYieldChart(yc){
  const canvas=document.getElementById('yieldChart');
  if(!canvas)return;
  if(charts.yield)charts.yield.destroy();
  const labels=yc.map(y=>y.term);
  const data=yc.map(y=>parseFloat(y.yield)||0);
  charts.yield=new Chart(canvas,{type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.08)',borderWidth:2,pointRadius:4,pointBackgroundColor:'#3B82F6',pointBorderColor:'#3B82F6',pointBorderWidth:2,fill:true,tension:0.3}]},plugins:[{id:'yieldEndpoint',afterDraw(chart){const ds=chart.data.datasets[0];const lastVal=ds.data[ds.data.length-1];const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 11px Outfit';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal,2)+'%':lastVal,lastPt.x+6,lastPt.y-4);ctx.restore();}}],options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(45,75,130,0.95)',titleColor:'#ffffff',bodyColor:'#93C5FD',borderColor:'rgba(0,0,0,0.12)',borderWidth:1,padding:10,cornerRadius:6}},scales:{x:{grid:{display:false},ticks:{font:{family:'Outfit',size:11},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'Outfit',size:11},color:'#636363',callback:v=>fmtNum(v,2)+'%'}}}}});
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
          lcEvtAnnotations['evt_'+i]={type:'line',xMin:li,xMax:li,borderColor:'rgba(245,158,11,0.5)',borderWidth:1,borderDash:[4,3],label:{display:true,content:(evt.event_name||evt.name||'').substring(0,20),position:'start',backgroundColor:'rgba(245,158,11,0.85)',color:'#fff',font:{family:'Work Sans',size:9,weight:'600'},padding:{top:2,bottom:2,left:5,right:5},borderRadius:3,rotation:-90}};
        }catch(e2){}
      });
    }
  }catch(e3){console.warn('Line chart event annotations:',e3)}
  const lcHasAnnotation=typeof window.ChartAnnotation!=='undefined'||Chart.registry&&Chart.registry.plugins&&Chart.registry.plugins.get('annotation');
  const lcAnnotationCfg=lcHasAnnotation&&Object.keys(lcEvtAnnotations).length?{annotation:{annotations:{...lcEvtAnnotations}}}:{};
  charts[canvasId]=new Chart(canvas,{type:'line',data:{labels,datasets:[{data,borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.06)',borderWidth:2,pointRadius:3,pointBackgroundColor:'#3B82F6',fill:true,tension:0.3}]},plugins:[{id:'lineEndpoint',afterDraw(chart){const ds=chart.data.datasets[0];const lastVal=ds.data[ds.data.length-1];const meta=chart.getDatasetMeta(0);const lastPt=meta.data[meta.data.length-1];if(!lastPt)return;const ctx=chart.ctx;ctx.save();ctx.font='600 10px Outfit';ctx.fillStyle='#3B82F6';ctx.textAlign='left';ctx.fillText(typeof lastVal==='number'?fmtNum(lastVal):lastVal,lastPt.x+4,lastPt.y-4);ctx.restore();}}],options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},...lcAnnotationCfg},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:6,font:{family:'Outfit',size:10},color:'#636363'}},y:{grid:{color:'rgba(0,0,0,0.06)',lineWidth:0.5,drawTicks:false},ticks:{font:{family:'Outfit',size:10},color:'#636363',callback:v=>fmtNum(v)}}}}});
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
  // Type toggle
  document.querySelectorAll('#projTypeToggle button').forEach(btn=>{
    btn.addEventListener('click',()=>{
      document.querySelectorAll('#projTypeToggle button').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      _projTypeFilter=btn.dataset.type;
      filterProjects();
    });
  });
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
    if(sector&&p.naics_code!==sector)return false;
    if(status&&p.status!==status)return false;
    if(_projTypeFilter==='greenfield'&&p.is_brownfield)return false;
    if(_projTypeFilter==='brownfield'&&!p.is_brownfield)return false;
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
  const gf=filteredProjects.filter(p=>!p.is_brownfield).length;
  const bf=filteredProjects.filter(p=>p.is_brownfield).length;
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
    '<div class="proj-stat-card"><div class="proj-stat-val">'+gf+'</div><div class="proj-stat-label">Greenfield</div></div>'+
    '<div class="proj-stat-card"><div class="proj-stat-val">'+bf+'</div><div class="proj-stat-label">Brownfield</div></div>'+
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
    const naicsShort=NAICS_NAMES[p.naics_code]||(p.sector||'').substring(0,20)||'';
    const pType=p.project_type||'greenfield';
    const isUnconf=!meetsThreshold(p);
    html+='<tr onclick="window.toggleProjectRow(\''+rowId+'\')"'+(isUnconf&&!_confirmedOnly?' class="unconfirmed-row"':'')+'>';
    html+='<td class="col-value">'+fmtCurrency(p.value,p)+(isUnconf?'<span class="unconfirmed-badge">unconfirmed</span>':'')+'</td>';
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
let _calMonth=null,_calYear=null,_calEvents=[];
async function renderCalendar(){
  _calEvents=(D&&(D.watchlist||D.events))||[];
  if(!_calEvents.length){try{_calEvents=await fetchJSON('events.json')||[]}catch(_){_calEvents=[]}}
  const now=new Date();
  _calMonth=now.getMonth();_calYear=now.getFullYear();
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
function renderCalendarEvents(){
  const events=_calEvents;
  const now=new Date();
  const year=now.getFullYear(),month=now.getMonth(),today=now.getDate();
  const MONTHS_SHORT={jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11};

  // Helper to parse both ISO "2026-03-14" and short "Mar 14" dates
  function parseEvtDate(d){
    if(!d)return null;
    if(d.includes('-')&&d.length>=8)return new Date(d+'T00:00:00');
    const parts=d.trim().split(/\s+/);
    if(parts.length>=2){const m=MONTHS_SHORT[(parts[0]||'').toLowerCase().slice(0,3)];if(m!=null)return new Date(year,m,parseInt(parts[1])||1)}
    return null;
  }

  // This week events
  const weekFromNow=new Date(now.getTime()+7*864e5);
  const thisWeek=events.filter(e=>{
    const ed=parseEvtDate(e.date);
    return ed&&ed>=new Date(year,month,today)&&ed<=weekFromNow;
  });
  // Group by week_label if available
  const byWeek={};thisWeek.forEach(e=>{const wl=e.week_label||'This Week';if(!byWeek[wl])byWeek[wl]=[];byWeek[wl].push(e)});

  if(thisWeek.length){
    let twHtml='<div class="events-section-wrap"><button class="events-toggle" onclick="this.classList.toggle(\'open\');this.nextElementSibling.classList.toggle(\'open\')">This Week ('+thisWeek.length+') <span class="chevron">\u25be</span></button><div class="events-collapsible">';
    Object.keys(byWeek).forEach(wl=>{
      twHtml+='<div class="events-week-card"><h3>'+wl+'</h3>';
      byWeek[wl].forEach(e=>{
        const impact=(e.impact||'low').toLowerCase();
        const isHigh=impact==='high';
        const ed=parseEvtDate(e.date);
        twHtml+='<div class="event-row'+(isHigh?' event-high-accent':'')+'">';
        if(ed){twHtml+='<div><div class="event-date-day">'+ed.getDate()+'</div><div class="event-date-month">'+ed.toLocaleDateString('en-CA',{month:'short'})+'</div></div>'}
        else{twHtml+='<div>'+(e.date||'-')+'</div>'}
        twHtml+='<div><div class="event-name">'+(e.event_name||e.event||e.name||'')+'</div>';
        if(e.description)twHtml+='<div style="font-size:var(--text-xs);color:#475569;margin-top:2px">'+e.description+'</div>';
        twHtml+='</div>';
        twHtml+='<div class="event-institution">'+(e.institution||e.source||'')+'</div>';
        twHtml+='<div class="event-impact"><span class="impact-badge impact-'+impact+'">'+impact.charAt(0).toUpperCase()+impact.slice(1)+'</span></div>';
        twHtml+='<div>'+srcLink(e.source_url||e.url,'')+'</div>';
        twHtml+='</div>';
      });
      twHtml+='</div>';
    });
    twHtml+='</div></div>';
    $('thisWeekEvents').innerHTML=twHtml;
  }

  // All events table
  const sorted=[...events].sort((a,b)=>{const da=parseEvtDate(a.date),db=parseEvtDate(b.date);return (da||new Date(0))-(db||new Date(0))}).slice(0,25);
  if(sorted.length){
    let allHtml='<div class="events-section-wrap"><button class="events-toggle" onclick="this.classList.toggle(\'open\');this.nextElementSibling.classList.toggle(\'open\')">All Events ('+sorted.length+') <span class="chevron">\u25be</span></button><div class="events-collapsible">';
    allHtml+='<div class="events-week-card">';
    sorted.forEach(e=>{
      const impact=(e.impact||'low').toLowerCase();
      const isHigh=impact==='high';
      const ed=parseEvtDate(e.date);
      allHtml+='<div class="event-row'+(isHigh?' event-high-accent':'')+'">';
      if(ed){allHtml+='<div><div class="event-date-day">'+ed.getDate()+'</div><div class="event-date-month">'+ed.toLocaleDateString('en-CA',{month:'short'})+'</div></div>'}
      else{allHtml+='<div>'+(e.date||'-')+'</div>'}
      allHtml+='<div><div class="event-name">'+(e.event_name||e.event||e.name||'')+'</div>';
      if(e.description)allHtml+='<div style="font-size:var(--text-xs);color:#475569;margin-top:2px">'+e.description+'</div>';
      allHtml+='</div>';
      allHtml+='<div class="event-institution">'+(e.institution||e.source||'')+'</div>';
      allHtml+='<div class="event-impact"><span class="impact-badge impact-'+impact+'">'+impact.charAt(0).toUpperCase()+impact.slice(1)+'</span></div>';
      allHtml+='<div>'+srcLink(e.source_url||e.url,'')+'</div>';
      allHtml+='</div>';
    });
    allHtml+='</div></div></div>';
    $('allEventsTable').innerHTML=allHtml;
  } else {
    $('allEventsTable').innerHTML='<div class="empty-state"><div class="empty-state-text">No upcoming economic events.</div></div>';
  }
}

/* ====== PHASE 1: PIPELINE STATUS WIDGET ====== */
async function renderPipelineStatus(){
  const el=$('pipelineStatus');if(!el)return;
  try{
    const ps=await fetchJSON('pipeline_status.json');
    const run=ps.last_run||{};
    if(!run.started_at){el.innerHTML='';return}
    const st=run.status||'unknown';
    const stColor=st==='success'?'var(--status-green)':st==='partial'?'var(--status-amber)':'var(--status-red)';
    const dur=run.duration_seconds?Math.round(run.duration_seconds/60)+'m':'—';
    const disc=run.discovery||{};
    el.innerHTML=`<div class="card fade-in" style="padding:14px 18px"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px"><div style="font-size:var(--text-sm);font-weight:600;color:#475569">Pipeline Status</div><div style="display:flex;gap:16px;font-family:var(--font-mono);font-size:var(--text-xs);color:#475569;flex-wrap:wrap"><span>Last run: <b>${fmtDate(run.started_at)}</b></span><span>Duration: <b>${dur}</b></span><span>Articles: <b>${disc.articles_found||0}</b></span><span>Projects added: <b>${disc.projects_added||0}</b></span><span>Status: <b style="color:${stColor}">${st}</b></span>${(run.errors||[]).length?'<span style="color:var(--status-amber)">'+run.errors.length+' error(s)</span>':''}</div></div></div>`;
  }catch(e){
    console.warn('Pipeline status:',e);
    el.innerHTML='<div class="card" style="padding:18px;text-align:center">'+
      '<div style="color:var(--status-red);font-size:var(--text-sm);margin-bottom:8px">Could not load pipeline status</div>'+
      '<button onclick="renderPipelineStatus()" style="padding:6px 16px;border:1px solid var(--border-light);border-radius:var(--radius-sm);background:var(--bg-subtle);color:var(--text-primary);cursor:pointer;font-size:var(--text-xs)">Retry</button></div>';
  }
}

/* ====== PHASE 1: COST MONITOR WIDGET ====== */
async function renderCostMonitor(){
  const el=$('costMonitor');if(!el)return;
  try{
    const ps=await fetchJSON('pipeline_status.json');
    const tavilyUsed=ps.tavily?.used||0;
    const tavilyMonth=ps.tavily?.month||'';
    const claudeIn=ps.claude_tokens?.input||0;
    const claudeOut=ps.claude_tokens?.output||0;
    const claudeCost=((claudeIn/1e6)*3+(claudeOut/1e6)*15).toFixed(2);
    const tavilyPct=Math.round((tavilyUsed/1000)*100);
    el.innerHTML=`<details class="card fade-in" style="padding:14px 18px"><summary style="cursor:pointer;font-size:var(--text-sm);font-weight:600;color:#475569;user-select:none">Cost Monitor <span style="font-weight:400;color:#556B7A;font-size:.75rem">(click to expand)</span></summary><div style="display:flex;gap:24px;flex-wrap:wrap;margin-top:10px;font-size:var(--text-xs);color:#475569"><div><div style="margin-bottom:4px">Tavily Credits</div><div style="background:#e5e7eb;border-radius:4px;height:8px;width:120px"><div style="background:${tavilyPct>80?'var(--status-red)':'var(--status-green)'};height:100%;border-radius:4px;width:${Math.min(tavilyPct,100)}%"></div></div><div style="font-family:var(--font-mono);margin-top:2px">${tavilyUsed} / 1,000 (${tavilyMonth})</div></div><div><div style="margin-bottom:4px">Claude Sonnet (est.)</div><div style="font-family:var(--font-mono);font-size:var(--text-sm);font-weight:600">~$${claudeCost}</div><div style="font-family:var(--font-mono);margin-top:2px">${(claudeIn/1000).toFixed(0)}K in / ${(claudeOut/1000).toFixed(0)}K out tokens</div></div><div><div style="margin-bottom:4px">Annual Budget</div><div style="font-family:var(--font-mono);font-size:var(--text-sm);font-weight:600">$55/yr</div></div></div></details>`;
  }catch(e){
    console.warn('Cost monitor:',e);
    el.innerHTML='<div class="card" style="padding:18px;text-align:center">'+
      '<div style="color:var(--status-red);font-size:var(--text-sm);margin-bottom:8px">Could not load cost data</div>'+
      '<button onclick="renderCostMonitor()" style="padding:6px 16px;border:1px solid var(--border-light);border-radius:var(--radius-sm);background:var(--bg-subtle);color:var(--text-primary);cursor:pointer;font-size:var(--text-xs)">Retry</button></div>';
  }
}

/* ====== PHASE 1: MICROSCOPE HISTORY ====== */
async function renderMicroscopeHistory(){
  const el=$('microscopeHistory');if(!el)return;
  try{
    const data=await fetchJSON('microscope.json');
    const history=(data&&(data.topics||data.history))||[];
    if(!history.length){el.innerHTML='';return}
    let items='';
    history.slice(0,12).forEach(h=>{
      items+=`<div style="padding:8px 0;border-bottom:1px solid var(--border-light)"><div style="display:flex;justify-content:space-between"><span style="font-weight:600;font-size:var(--text-sm)">${h.topic||h.title||''}</span><span style="font-size:var(--text-xs);color:#556B7A">${h.date||h.week||''}</span></div>${h.description?'<div style="font-size:var(--text-xs);color:#475569;margin-top:2px">'+h.description+'</div>':''}</div>`;
    });
    el.innerHTML=`<details class="card fade-in"><summary style="cursor:pointer;font-size:var(--text-sm);font-weight:600;color:#475569;padding:14px 18px;user-select:none">Under the Microscope Archives (<span style="font-family:var(--font-mono)">${history.length}</span> weeks)</summary><div style="padding:0 18px 14px">${items}</div></details>`;
  }catch(e){
    console.warn('Microscope history:',e);
    el.innerHTML='<div class="card" style="padding:18px;text-align:center">'+
      '<div style="color:var(--status-red);font-size:var(--text-sm);margin-bottom:8px">Could not load microscope history</div>'+
      '<button onclick="renderMicroscopeHistory()" style="padding:6px 16px;border:1px solid var(--border-light);border-radius:var(--radius-sm);background:var(--bg-subtle);color:var(--text-primary);cursor:pointer;font-size:var(--text-xs)">Retry</button></div>';
  }
}

/* ====== PHASE 2: UNDER THE MICROSCOPE ====== */
async function renderMicroscope(){
  const el=$('microscopeSection');if(!el)return;
  try{
    const data=await fetchJSON('microscope.json');
    const m=(data&&data.current)||data||{};
    if(!m.topic&&!m.text){el.innerHTML='';return}
    const sectors=(m.affected_sectors||[]).map(s=>'<span class="editorial-sector-tag">'+s+'</span>').join(' ');
    const weeks=m.weeks_running?'<span style="font-size:var(--text-xs);color:#64748B;margin-left:8px">Week '+m.weeks_running+'</span>':'';
    if(_editorialMode){
      el.innerHTML=`<div class="fade-in"><hr class="editorial-rule"><div class="editorial-section-label">Under the Microscope ${weeks}</div><div class="editorial-section-title">${m.topic||''}</div>${sectors?'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:12px">'+sectors+'</div>':''}<div class="editorial-prose">${san(m.text||m.analysis||'')}</div></div>`;
    }else{
      el.innerHTML=`<div class="card fade-in"><div class="card-header">Under the Microscope ${weeks}</div><div style="font-size:var(--text-sm);font-weight:600;color:var(--accent-blue);margin-bottom:8px">${m.topic||''}</div>${sectors?'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">'+sectors+'</div>':''}<div class="card-body">${san(m.text||m.analysis||'')}</div></div>`;
    }
  }catch(e){
    console.warn('Microscope:',e);
    el.innerHTML='<div class="card" style="padding:18px;text-align:center">'+
      '<div style="color:var(--status-red);font-size:var(--text-sm);margin-bottom:8px">Could not load microscope data</div>'+
      '<button onclick="renderMicroscope()" style="padding:6px 16px;border:1px solid var(--border-light);border-radius:var(--radius-sm);background:var(--bg-subtle);color:var(--text-primary);cursor:pointer;font-size:var(--text-xs)">Retry</button></div>';
  }
}

/* ====== PHASE 2: POLICY SECTION ====== */
async function renderPolicySection(){
  const el=$('policyContent')||$('policySection');if(!el)return;
  try{
    let policyData;
    try{policyData=await fetchJSON('policy.json')}catch(_){el.innerHTML='';return}
    const articles=policyData?.articles||[];
    if(!articles.length){el.innerHTML='';return}
    // Category summary
    const cats={};articles.forEach(a=>{const c=a.category||'other';cats[c]=(cats[c]||0)+1});
    const catBadges=Object.entries(cats).sort((a,b)=>b[1]-a[1]).map(([c,n])=>'<span style="background:var(--bg-subtle);color:var(--text-secondary);padding:2px 8px;border-radius:4px;font-size:var(--text-xs)">'+c.replace(/_/g,' ')+' ('+n+')</span>').join(' ');
    // Article list (top 8)
    let listHtml='';
    articles.slice(0,8).forEach(a=>{
      const provBadge=a.scope?'<span style="background:var(--status-blue-bg);color:var(--status-blue);padding:1px 6px;border-radius:3px;font-size:.65rem;margin-left:4px">'+a.scope+'</span>':'';
      listHtml+=`<div style="padding:6px 0;border-bottom:1px solid var(--border-light);font-size:var(--text-xs)"><a href="${a.url||'#'}" target="_blank" rel="noopener noreferrer" style="color:var(--accent-blue);text-decoration:none">${a.headline||a.title||'Untitled'}</a>${provBadge}<span style="color:#556B7A;margin-left:6px">${a.source||''}</span></div>`;
    });
    el.innerHTML=`<details class="card fade-in"><summary style="cursor:pointer;font-size:var(--text-sm);font-weight:600;color:#475569;padding:14px 18px;user-select:none">Policy Monitor (<span style="font-family:var(--font-mono)">${articles.length}</span> articles this week)</summary><div style="padding:0 18px 14px"><div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px">${catBadges}</div>${listHtml}</div></details>`;
  }catch(e){console.warn('Policy section:',e);el.innerHTML=''}
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
    _renderExplorerStats();
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

function _renderExplorerStats(){
  const el=$('explorerStats');
  if(!el)return;
  const total=VCODE_INDEX.length+_fullTableDir.length;
  const curated=VCODE_INDEX.length;
  const dir=_fullTableDir.length;
  const pill=(label,value,color)=>`<div style="display:flex;align-items:center;gap:8px;padding:8px 16px;border-radius:var(--radius-md);background:var(--bg-white);border:1px solid var(--border-light)"><span style="font-size:var(--text-xs);color:#556B7A">${label}</span><span style="font-family:var(--font-mono);font-size:var(--text-base);font-weight:700;color:${color}">${value.toLocaleString()}</span></div>`;
  el.innerHTML=pill('Total Tables',total,'var(--accent-blue)')+pill('Curated',curated,'#10b981')+pill('Full Directory',dir,_fullDirLoaded?'#6366f1':'#919191')+(!_fullDirLoaded?'<span style="font-size:var(--text-xs);color:#556B7A;align-self:center">Loading directory\u2026</span>':'');
}

function renderExplorer(){
  const searchEl=$('explorerSearch');
  const catEl=$('explorerCategories');
  const resEl=$('explorerResults');
  if(!searchEl)return;

  searchEl.innerHTML=`<div style="display:flex;gap:8px"><input type="text" id="vcodeSearch" placeholder="Search StatCan tables (e.g. unemployment, housing, GDP)..." style="flex:1;padding:10px 14px;border-radius:var(--radius-md);border:1px solid var(--border-light);background:var(--bg-white);color:#1a2744;font-size:var(--text-sm);font-family:var(--font-body)" onkeyup="if(event.key==='Enter')window._doVcodeSearch()"><button onclick="window._doVcodeSearch()" style="padding:10px 20px;border-radius:var(--radius-md);border:none;background:var(--accent-blue);color:#fff;font-size:var(--text-sm);cursor:pointer;font-weight:600">Search</button></div>`;

  _renderExplorerStats();

  const categories=['Labour Market','GDP','Construction','Housing','Prices','Trade','Energy','Manufacturing','Agriculture','Infrastructure','Transportation','Health','Demographics','Tourism'];
  catEl.innerHTML='<div style="display:flex;gap:6px;flex-wrap:wrap">'+categories.map(c=>'<button onclick="window._doVcodeSearch(\''+c+'\')" style="padding:6px 14px;border-radius:20px;border:1px solid var(--border-light);background:var(--bg-white);color:#2d3a52;font-size:var(--text-xs);cursor:pointer;font-weight:500">'+c+'</button>').join('')+'</div>';

  resEl.innerHTML='<div style="color:#556B7A;font-size:var(--text-sm);padding:20px 0">Enter a search term or click a category to find StatCan tables.</div>';

  // National indicator dropdown + explorer
  const cis=$('canadaIndicatorSection');
  if(cis){
    cis.innerHTML='<h3 style="font-size:var(--text-lg);font-weight:700;color:#003153;margin-bottom:4px">National Indicator Explorer</h3><p style="font-size:var(--text-sm);color:#475569;margin-bottom:12px">All national indicators with time-series history</p><div id="canadaIndicatorDropdown"></div><section id="indicatorExplorer" style="margin-top:16px"></section>';
    const dd=$('canadaIndicatorDropdown');
    if(dd)dd.innerHTML=renderIndicatorDropdown(indicators,'All National Indicators','_canada');
    renderIndicatorExplorer();
  }

  // Provincial indicator dropdown
  const pis=$('provIndicatorSection');
  if(pis){
    const prov=PROVS.find(p=>p.code===selectedProvince)||PROVS[0];
    pis.innerHTML='<h3 style="font-size:var(--text-lg);font-weight:700;color:#003153;margin-bottom:4px">'+prov.name+' Indicators</h3><p style="font-size:var(--text-sm);color:#475569;margin-bottom:12px">Full indicator list for '+prov.name+'</p>'+
      renderIndicatorDropdown(indicators,prov.name+' Indicators','_prov');
  }
}

window._doVcodeSearch=function(cat){
  const q=cat||($('vcodeSearch')?$('vcodeSearch').value:'');
  if(!q)return;
  if(cat&&$('vcodeSearch'))$('vcodeSearch').value=cat;
  const results=searchVCodes(q);
  const resEl=$('explorerResults');
  if(!results.length){
    resEl.innerHTML='<div style="color:#556B7A;font-size:var(--text-sm);padding:20px 0">No tables found for "'+q+'". Try different keywords.</div>';
    return;
  }
  let html='<div style="font-size:var(--text-xs);color:#556B7A;margin-bottom:8px">Showing '+results.length+' of '+(VCODE_INDEX.length+_fullTableDir.length).toLocaleString()+' indexed tables</div>';
  results.forEach(r=>{
    const tableUrl=r.table.includes('BoC')?'https://www.bankofcanada.ca/rates/':`https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=${r.table.replace(/-/g,'')}`;
    html+=`<div class="card" style="margin-bottom:8px;padding:14px 18px"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><span style="font-family:var(--font-mono);font-size:var(--text-xs);background:var(--bg-subtle);color:var(--text-secondary);padding:2px 6px;border-radius:3px">${r.vcode}</span> <span style="font-size:var(--text-xs);color:#556B7A;margin-left:4px">Table ${r.table}</span><div style="font-size:var(--text-sm);font-weight:600;margin-top:4px">${r.title}</div><div style="font-size:var(--text-xs);color:#556B7A;margin-top:2px">${r.freq} \u00b7 ${r.geo} \u00b7 ${r.category}</div></div><a href="${tableUrl}" target="_blank" rel="noopener noreferrer" style="font-size:var(--text-xs);color:var(--accent-blue);text-decoration:none;white-space:nowrap;padding:4px 10px;border:1px solid var(--border-light);border-radius:4px">View on StatCan \u2197</a></div></div>`;
  });
  resEl.innerHTML=html;
};

/* ====== INITIALIZATION ====== */
// Module scripts are deferred — DOM is already ready, run immediately
if($('execSummary'))$('execSummary').innerHTML='<div style="padding:28px 0">'+skeleton(4)+'</div>';
if($('editorialFlow'))$('editorialFlow').innerHTML=skeleton(6);
if($('natAnalysisSection'))$('natAnalysisSection').innerHTML='<div class="card">'+skeleton(3)+'</div>';
if($('keyIndicators'))$('keyIndicators').innerHTML='<div class="indicator-strip">'+Array(7).fill('<div class="skeleton sk-pill"></div>').join('')+'</div>';
// Section-level skeleton placeholders while async sections load
if($('costMonitor'))$('costMonitor').innerHTML='<div class="card">'+skeleton(2)+'</div>';
if($('microscopeSection'))$('microscopeSection').innerHTML='<div class="card">'+skeleton(3)+'</div>';
if($('microscopeHistory'))$('microscopeHistory').innerHTML='<div class="card">'+skeleton(2)+'</div>';
$('footerDate').textContent='Loading...';
// No auth required — data is served as static JSON files
loadAll();
