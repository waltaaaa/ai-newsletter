# The Lagging Indicator — Chart Library

Design system: light theme, `border: 0.5px solid var(--color-border-tertiary)`, `border-radius: var(--border-radius-lg)`, Chart.js 4.4.1 from cdnjs. All charts use `#185FA5` (blue) as primary, `#1D9E75` (teal) as secondary, `#BA7517` (amber), `#D4537E` (pink), `#7F77DD` (purple). Grid lines `rgba(0,0,0,.04)`, tick color `#888780`, axis border `rgba(0,0,0,.08)`.

---

## 1. Line chart

**Use for:** Pipeline value trends over time. Supports dual series (adjusted vs. gross).

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;flex-wrap:wrap;gap:8px;">
    <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);">Confidence-adjusted pipeline value</div>
    <div style="font-size:11px;color:var(--color-text-tertiary);">2025 Q1 – 2026 Q1 · $B</div>
  </div>
  <div style="display:flex;gap:16px;margin-bottom:1rem;flex-wrap:wrap;">
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);">
      <span style="width:20px;height:2px;background:#185FA5;display:inline-block;border-radius:2px;"></span>Adj. value
    </span>
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);">
      <span style="width:20px;height:2px;background:#B5D4F4;display:inline-block;border-radius:2px;border-top:2px dashed #B5D4F4;"></span>Gross announced
    </span>
  </div>
  <div style="position:relative;width:100%;height:220px;"><canvas id="lineC"></canvas></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('lineC'),{
  type:'line',
  data:{
    labels:['Q1 25','Q2 25','Q3 25','Q4 25','Q1 26'],
    datasets:[
      {label:'Adj. value',data:[618,641,672,689,703],borderColor:'#185FA5',backgroundColor:'rgba(24,95,165,.07)',pointBackgroundColor:'#185FA5',pointRadius:4,tension:.35,fill:true,borderWidth:2},
      {label:'Gross',data:[980,1050,1110,1170,1200],borderColor:'#B5D4F4',borderDash:[4,3],pointBackgroundColor:'#B5D4F4',pointRadius:3,tension:.35,fill:false,borderWidth:1.5}
    ]
  },
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},
    scales:{
      x:{grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780'},border:{color:'rgba(0,0,0,.08)'}},
      y:{grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780',callback:v=>'$'+v+'B'},border:{color:'rgba(0,0,0,.08)'}}
    }
  }
});
</script>
```

---

## 2. Horizontal bar with inline labels

**Use for:** Provincial or sector rankings. CSS-drawn (no Chart.js), fully customisable.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:1.25rem;">Capital pipeline by province · confidence-adjusted $B</div>
  <div id="bars"></div>
</div>
<script>
const data=[
  {label:'British Columbia',value:142,pct:100},
  {label:'Alberta',value:118,pct:83},
  {label:'Ontario',value:97,pct:68},
  {label:'Quebec',value:74,pct:52},
  {label:'Saskatchewan',value:48,pct:34},
  {label:'Nova Scotia',value:28,pct:20},
  {label:'Manitoba',value:22,pct:15},
  {label:'Other',value:9,pct:6}
];
const container=document.getElementById('bars');
data.forEach((d,i)=>{
  const row=document.createElement('div');
  row.style.cssText='display:flex;align-items:center;gap:10px;margin-bottom:10px;';
  row.innerHTML=`
    <div style="width:130px;font-size:12px;color:var(--color-text-secondary);text-align:right;flex-shrink:0;">${d.label}</div>
    <div style="flex:1;background:var(--color-background-secondary);border-radius:3px;height:20px;overflow:hidden;">
      <div style="width:${d.pct}%;height:100%;background:${i===0?'#185FA5':i<3?'#378ADD':'#85B7EB'};border-radius:3px;"></div>
    </div>
    <div style="width:48px;font-size:12px;font-weight:500;color:var(--color-text-primary);flex-shrink:0;">$${d.value}B</div>
  `;
  container.appendChild(row);
});
</script>
```

---

## 3. Scatter / bubble chart

**Use for:** Project value vs. maturity score. Bubble size encodes confidence-adjusted value. One dataset per sector.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;flex-wrap:wrap;gap:8px;">
    <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);">Project value vs. maturity score</div>
    <div style="font-size:11px;color:var(--color-text-tertiary);">Bubble size = confidence-adj. value</div>
  </div>
  <div style="display:flex;gap:16px;margin-bottom:1rem;flex-wrap:wrap;">
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);"><span style="width:10px;height:10px;border-radius:50%;background:#185FA5;display:inline-block;opacity:.7;"></span>Energy</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);"><span style="width:10px;height:10px;border-radius:50%;background:#1D9E75;display:inline-block;opacity:.7;"></span>Infrastructure</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);"><span style="width:10px;height:10px;border-radius:50%;background:#BA7517;display:inline-block;opacity:.7;"></span>Mining</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);"><span style="width:10px;height:10px;border-radius:50%;background:#7F77DD;display:inline-block;opacity:.7;"></span>Cleantech</span>
  </div>
  <div style="position:relative;width:100%;height:240px;"><canvas id="bubC"></canvas></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('bubC'),{
  type:'bubble',
  data:{datasets:[
    {label:'Energy',backgroundColor:'rgba(24,95,165,.55)',data:[{x:4.2,y:14,r:18},{x:3.8,y:8.4,r:13},{x:4.9,y:3.1,r:8},{x:1.5,y:70,r:7},{x:2.9,y:2.2,r:7}]},
    {label:'Infrastructure',backgroundColor:'rgba(29,158,117,.55)',data:[{x:4.5,y:6.8,r:14},{x:3.2,y:2.9,r:9},{x:4.7,y:1.4,r:7},{x:2.1,y:4.1,r:8}]},
    {label:'Mining',backgroundColor:'rgba(186,117,23,.55)',data:[{x:3.9,y:5.2,r:11},{x:3.4,y:3.8,r:10},{x:2.6,y:9.1,r:12},{x:4.1,y:1.2,r:6}]},
    {label:'Cleantech',backgroundColor:'rgba(127,119,221,.55)',data:[{x:2.2,y:0.62,r:6},{x:1.8,y:1.1,r:7},{x:3.1,y:0.39,r:5}]}
  ]},
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>`$${ctx.parsed.y}B · maturity ${ctx.parsed.x.toFixed(1)}`}}},
    scales:{
      x:{min:0.8,max:5.8,title:{display:true,text:'Maturity score (1–5)',font:{size:11},color:'#888780'},grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780'},border:{color:'rgba(0,0,0,.08)'}},
      y:{min:-5,max:80,title:{display:true,text:'Announced value ($B)',font:{size:11},color:'#888780'},grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780',callback:v=>'$'+v+'B'},border:{color:'rgba(0,0,0,.08)'}}
    }
  }
});
</script>
```

---

## 4. Multi-series area chart

**Use for:** Comparing two pipeline metrics over time (e.g. construction count vs. FID count).

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;flex-wrap:wrap;gap:8px;">
    <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);">Construction vs. FID pipeline · project count</div>
    <div style="font-size:11px;color:var(--color-text-tertiary);">Quarterly · 2024 Q1 – 2026 Q1</div>
  </div>
  <div style="display:flex;gap:16px;margin-bottom:1rem;flex-wrap:wrap;">
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);"><span style="width:20px;height:2px;background:#185FA5;display:inline-block;border-radius:2px;"></span>Under construction</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary);"><span style="width:20px;height:2px;background:#1D9E75;display:inline-block;border-radius:2px;"></span>FID reached</span>
  </div>
  <div style="position:relative;width:100%;height:220px;"><canvas id="areaC"></canvas></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('areaC'),{
  type:'line',
  data:{
    labels:['Q1 24','Q2 24','Q3 24','Q4 24','Q1 25','Q2 25','Q3 25','Q4 25','Q1 26'],
    datasets:[
      {label:'Under construction',data:[44,46,49,51,53,55,57,59,61],borderColor:'#185FA5',backgroundColor:'rgba(24,95,165,.08)',fill:true,tension:.4,pointRadius:3,pointBackgroundColor:'#185FA5',borderWidth:2},
      {label:'FID reached',data:[38,39,41,40,42,43,45,43,44],borderColor:'#1D9E75',backgroundColor:'rgba(29,158,117,.08)',fill:true,tension:.4,pointRadius:3,pointBackgroundColor:'#1D9E75',borderWidth:2}
    ]
  },
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},
    scales:{
      x:{grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780',autoSkip:false,maxRotation:0},border:{color:'rgba(0,0,0,.08)'}},
      y:{min:30,grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780'},border:{color:'rgba(0,0,0,.08)'},title:{display:true,text:'Projects',font:{size:11},color:'#888780'}}
    }
  }
});
</script>
```

---

## 5. Proportional ribbon

**Use for:** Sector share of pipeline. Single-row proportional bar with legend below. CSS-only, no library.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:1rem;">Pipeline share by sector</div>
  <div id="ribbon" style="display:flex;height:32px;border-radius:4px;overflow:hidden;gap:2px;"></div>
  <div id="ribbon-leg" style="display:flex;flex-wrap:wrap;gap:10px;margin-top:10px;"></div>
</div>
<script>
const sectors=[
  {label:'Energy',pct:38,color:'#185FA5'},
  {label:'Infrastructure',pct:22,color:'#1D9E75'},
  {label:'Mining',pct:18,color:'#BA7517'},
  {label:'Real estate',pct:12,color:'#D4537E'},
  {label:'Cleantech',pct:10,color:'#7F77DD'},
];
const rb=document.getElementById('ribbon');
const rl=document.getElementById('ribbon-leg');
sectors.forEach(s=>{
  const seg=document.createElement('div');
  seg.style.cssText=`flex:${s.pct};background:${s.color};`;
  rb.appendChild(seg);
  const li=document.createElement('span');
  li.style.cssText='display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);';
  li.innerHTML=`<span style="width:8px;height:8px;border-radius:1px;background:${s.color};display:inline-block;"></span>${s.label} ${s.pct}%`;
  rl.appendChild(li);
});
</script>
```

---

## 6. Delta summary cards

**Use for:** Week-over-week pipeline movement summary. Four tinted cards showing additions, revisions, deferrals, and net change.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:1rem;">Week-over-week pipeline movement</div>
  <div id="delta-cards" style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;"></div>
</div>
<script>
const deltas=[
  {label:'New entries',value:'+$2.1B',c:'#E1F5EE',tc:'#0F6E56'},
  {label:'Upward rev.',value:'+$3.8B',c:'#E1F5EE',tc:'#0F6E56'},
  {label:'Deferrals',value:'-$3.7B',c:'#FCEBEB',tc:'#A32D2D'},
  {label:'Net change',value:'+$14B',c:'#E6F1FB',tc:'#185FA5'},
];
const dc=document.getElementById('delta-cards');
deltas.forEach(d=>{
  const card=document.createElement('div');
  card.style.cssText=`background:${d.c};border-radius:var(--border-radius-md);padding:10px 12px;`;
  card.innerHTML=`<div style="font-size:10px;color:var(--color-text-tertiary);margin-bottom:5px;">${d.label}</div><div style="font-size:15px;font-weight:500;color:${d.tc};">${d.value}</div>`;
  dc.appendChild(card);
});
</script>
```

---

## 7. Grouped bar (sector × stage)

**Use for:** Comparing construction / FID / planning mix across sectors side by side.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:1rem;">Projects by sector and stage</div>
  <div style="position:relative;width:100%;height:180px;"><canvas id="groupC"></canvas></div>
  <div style="display:flex;gap:14px;margin-top:10px;">
    <span style="display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);"><span style="width:9px;height:9px;border-radius:2px;background:#185FA5;display:inline-block;"></span>Construction</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);"><span style="width:9px;height:9px;border-radius:2px;background:#85B7EB;display:inline-block;"></span>FID reached</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);"><span style="width:9px;height:9px;border-radius:2px;background:#D3D1C7;display:inline-block;"></span>Planning</span>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('groupC'),{
  type:'bar',
  data:{
    labels:['Energy','Infrastructure','Mining','Real estate','Cleantech'],
    datasets:[
      {label:'Construction',data:[18,14,12,9,4],backgroundColor:'#185FA5',borderWidth:0,borderRadius:3,barThickness:12},
      {label:'FID reached',data:[12,8,10,7,4],backgroundColor:'#85B7EB',borderWidth:0,borderRadius:3,barThickness:12},
      {label:'Planning',data:[8,10,6,7,2],backgroundColor:'#D3D1C7',borderWidth:0,borderRadius:3,barThickness:12}
    ]
  },
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},
    scales:{
      x:{grid:{display:false},ticks:{font:{size:11},color:'#888780'},border:{color:'rgba(0,0,0,.08)'}},
      y:{grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780'},border:{color:'rgba(0,0,0,.08)'}}
    }
  }
});
</script>
```

---

## 8. Range bar (project value spread by sector)

**Use for:** Showing the min, median, and max project value within each sector. CSS-drawn, no library.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:1rem;">Project value range by sector · $B</div>
  <div id="rangebar" style="display:flex;flex-direction:column;gap:9px;padding:4px 0;"></div>
</div>
<script>
const rangeData=[
  {label:'Energy',min:0.2,med:2.1,max:14.0,color:'#185FA5'},
  {label:'Infrastructure',min:0.1,med:1.4,max:6.8,color:'#1D9E75'},
  {label:'Mining',min:0.3,med:1.8,max:9.1,color:'#BA7517'},
  {label:'Real estate',min:0.1,med:0.9,max:4.2,color:'#D4537E'},
  {label:'Cleantech',min:0.2,med:0.7,max:2.1,color:'#7F77DD'},
];
const rb=document.getElementById('rangebar');
const maxVal=14;
rangeData.forEach(d=>{
  const row=document.createElement('div');
  row.style.cssText='display:flex;align-items:center;gap:10px;';
  const minPct=(d.min/maxVal)*100;
  const maxPct=(d.max/maxVal)*100;
  const medPct=(d.med/maxVal)*100;
  row.innerHTML=`
    <span style="width:90px;font-size:11px;color:var(--color-text-secondary);text-align:right;flex-shrink:0;">${d.label}</span>
    <div style="position:relative;flex:1;height:6px;background:var(--color-background-secondary);border-radius:3px;">
      <div style="position:absolute;left:${minPct}%;width:${maxPct-minPct}%;height:100%;background:${d.color};opacity:.25;border-radius:3px;"></div>
      <div style="position:absolute;left:${minPct}%;width:${maxPct-minPct}%;height:100%;border-left:2px solid ${d.color};border-right:2px solid ${d.color};border-radius:3px;"></div>
      <div style="position:absolute;left:${medPct}%;transform:translateX(-50%);width:3px;height:14px;top:-4px;background:${d.color};border-radius:2px;"></div>
    </div>
    <span style="font-size:11px;color:var(--color-text-tertiary);width:80px;flex-shrink:0;">$${d.min}B – $${d.max}B</span>
  `;
  rb.appendChild(row);
});
</script>
```

---

## 9. Stacked area (project count by stage over time)

**Use for:** Showing total pipeline volume and stage composition simultaneously over multiple quarters.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;flex-wrap:wrap;gap:8px;">
    <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);">Project count by stage over time</div>
    <div style="font-size:11px;color:var(--color-text-tertiary);">Quarterly · 2024 Q1 – 2026 Q1</div>
  </div>
  <div style="display:flex;gap:14px;margin-bottom:1rem;">
    <span style="display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);"><span style="width:9px;height:9px;border-radius:2px;background:#185FA5;display:inline-block;"></span>Construction</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);"><span style="width:9px;height:9px;border-radius:2px;background:#1D9E75;display:inline-block;"></span>FID reached</span>
    <span style="display:flex;align-items:center;gap:5px;font-size:11px;color:var(--color-text-secondary);"><span style="width:9px;height:9px;border-radius:2px;background:#B4B2A9;display:inline-block;"></span>Planning</span>
  </div>
  <div style="position:relative;width:100%;height:180px;"><canvas id="stackareaC"></canvas></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
new Chart(document.getElementById('stackareaC'),{
  type:'line',
  data:{
    labels:['Q1 24','Q2 24','Q3 24','Q4 24','Q1 25','Q2 25','Q3 25','Q4 25','Q1 26'],
    datasets:[
      {label:'Construction',data:[44,46,49,51,53,55,57,59,61],borderColor:'#185FA5',backgroundColor:'rgba(24,95,165,.15)',fill:true,tension:.4,pointRadius:0,borderWidth:1.5},
      {label:'FID reached',data:[38,39,41,40,42,43,45,43,44],borderColor:'#1D9E75',backgroundColor:'rgba(29,158,117,.15)',fill:true,tension:.4,pointRadius:0,borderWidth:1.5},
      {label:'Planning',data:[28,30,31,33,34,36,37,38,37],borderColor:'#B4B2A9',backgroundColor:'rgba(180,178,169,.15)',fill:true,tension:.4,pointRadius:0,borderWidth:1.5}
    ]
  },
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},
    scales:{
      x:{grid:{display:false},ticks:{font:{size:11},color:'#888780',autoSkip:false,maxRotation:0},border:{color:'rgba(0,0,0,.08)'}},
      y:{grid:{color:'rgba(0,0,0,.04)'},ticks:{font:{size:11},color:'#888780'},border:{color:'rgba(0,0,0,.08)'},title:{display:true,text:'Projects',font:{size:11},color:'#888780'}}
    }
  }
});
</script>
```

---

## 10. Gantt timeline (project construction windows)

**Use for:** Top projects section showing when each major project starts and ends construction. CSS-drawn, no library.

```html
<div style="border:0.5px solid var(--color-border-tertiary);border-radius:var(--border-radius-lg);padding:1.25rem 1.5rem;">
  <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);margin-bottom:1rem;">Major project construction windows</div>
  <div id="gantt" style="display:flex;flex-direction:column;gap:7px;padding:2px 0;"></div>
</div>
<script>
const projects=[
  {label:'LNG Canada Ph.2',start:2022,end:2027,color:'#185FA5'},
  {label:'Rideau Corridor',start:2025,end:2028,color:'#1D9E75'},
  {label:'NS Offshore Wind',start:2026,end:2031,color:'#BA7517'},
  {label:'Atikokan H2',start:2027,end:2030,color:'#7F77DD'},
  {label:'Lynn Lake Gold',start:2024,end:2027,color:'#D4537E'},
];
const gantt=document.getElementById('gantt');
const minY=2022,maxY=2032,span=maxY-minY;
const header=document.createElement('div');
header.style.cssText='display:flex;margin-left:130px;margin-bottom:4px;';
for(let y=minY;y<=maxY;y+=2){
  const t=document.createElement('div');
  t.style.cssText=`flex:${2/span};font-size:10px;color:var(--color-text-tertiary);`;
  t.textContent=y;
  header.appendChild(t);
}
gantt.appendChild(header);
projects.forEach(p=>{
  const row=document.createElement('div');
  row.style.cssText='display:flex;align-items:center;';
  const leftPct=((p.start-minY)/span)*100;
  const widthPct=((p.end-p.start)/span)*100;
  row.innerHTML=`
    <span style="width:130px;font-size:11px;color:var(--color-text-secondary);text-align:right;padding-right:10px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${p.label}</span>
    <div style="flex:1;height:14px;position:relative;border-left:0.5px solid var(--color-border-tertiary);">
      <div style="position:absolute;left:${leftPct}%;width:${widthPct}%;height:100%;background:${p.color};border-radius:3px;opacity:.8;"></div>
    </div>
  `;
  gantt.appendChild(row);
});
</script>
```

---

*Last updated: 2026-03-31 · 10 charts total*
