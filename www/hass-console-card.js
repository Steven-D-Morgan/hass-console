/**
 * HASS Console Card v2.3.0
 *
 * CONFIG:
 *   type: custom:hass-console-card
 *   title: HASS Console
 *   alarm_csv: /local/hass-console-alarms.csv
 *   log_csv: /local/hass-console-logs.csv
 *   rows: 200
 *   refresh_interval: 30
 */
const VER="2.3.0";
function parseTS(v){if(!v)return null;const n=v.indexOf(' ')!==-1&&v.indexOf('T')===-1?v.replace(' ','T'):v;const d=new Date(n);return isNaN(d)?null:d}

class HassConsoleCard extends HTMLElement{
constructor(){super();this.attachShadow({mode:"open"});this._c={};this._alarm=[];this._log=[];this._tab="ALARM";this._timer=null;this._sortCol=null;this._sortDir="desc";
this._fText="";this._fClass=new Set;this._fCat=new Set;this._fEnt=new Set;this._fFrom="";this._fTo="";this._filtersOpen=false;this._showAck=false}

setConfig(c){this._c={title:c.title||"HASS Console",alarm_csv:c.alarm_csv||"/local/hass-console-alarms.csv",log_csv:c.log_csv||"/local/hass-console-logs.csv",rows:c.rows||200,refresh:c.refresh_interval||30}}

set hass(h){this._hass=h;if(!this._init){this._init=true;this._render();this._fetch();this._startRefresh()}}

_startRefresh(){if(this._timer)clearInterval(this._timer);this._timer=setInterval(()=>this._fetch(),this._c.refresh*1000)}

async _fetch(){await Promise.all([this._fetchOne("alarm"),this._fetchOne("log")]);this._update()}
async _fetchOne(t){try{const u=t==="alarm"?this._c.alarm_csv:this._c.log_csv;const r=await fetch(u+`?_=${Date.now()}`);if(!r.ok){if(t==="alarm")this._alarm=[];else this._log=[];return}
const rows=this._parseCSV(await r.text());if(t==="alarm")this._alarm=rows;else this._log=rows}catch(e){console.error("HASS Console fetch:",e)}}

_parseCSV(text){const lines=text.trim().split("\n");if(lines.length<2)return[];const hdr=this._splitLine(lines[0]);const out=[];
for(let i=1;i<lines.length;i++){const cols=this._splitLine(lines[i]);if(cols.length<hdr.length)continue;const row={};hdr.forEach((h,j)=>row[h.trim()]=cols[j]?.trim()||"");out.push(row)}return out}
_splitLine(l){const r=[];let c="",q=false;for(let i=0;i<l.length;i++){const ch=l[i];if(ch==='"')q=!q;else if(ch===","&&!q){r.push(c);c=""}else c+=ch}r.push(c);return r}

_data(){return this._tab==="ALARM"?this._alarm:this._log}
_unackCount(){return this._alarm.filter(r=>!r.ack).length}
_distClasses(){const s=new Set;this._alarm.forEach(r=>{if(r.class)s.add(r.class)});return[...s].sort()}
_distCats(){const s=new Set;this._data().forEach(r=>{if(r.category)s.add(r.category)});return[...s].sort()}
_distEnts(){const s=new Set;this._data().forEach(r=>{if(r.entity)s.add(r.entity)});return[...s].sort()}

_rows(){
let rows=[...this._data()];
// Default: hide acknowledged alarms
if(this._tab==="ALARM"&&!this._showAck)rows=rows.filter(r=>!r.ack);
if(this._fText){const ft=this._fText.toLowerCase();rows=rows.filter(r=>Object.values(r).some(v=>v.toLowerCase().includes(ft)))}
if(this._fClass.size>0&&this._tab==="ALARM")rows=rows.filter(r=>this._fClass.has(r.class||""));
if(this._fCat.size>0)rows=rows.filter(r=>this._fCat.has(r.category||""));
if(this._fEnt.size>0)rows=rows.filter(r=>this._fEnt.has(r.entity||""));
if(this._fFrom){const f=new Date(this._fFrom+"T00:00:00");rows=rows.filter(r=>{const d=parseTS(r.timestamp);return d?d>=f:true})}
if(this._fTo){const t=new Date(this._fTo+"T23:59:59");rows=rows.filter(r=>{const d=parseTS(r.timestamp);return d?d<=t:true})}
if(this._sortCol){rows.sort((a,b)=>{const va=a[this._sortCol]||"",vb=b[this._sortCol]||"";const c=va.localeCompare(vb,undefined,{numeric:true});return this._sortDir==="asc"?c:-c})}
else rows.reverse();
return rows.slice(0,this._c.rows)}

_cntFilters(){let n=0;if(this._fClass.size>0)n++;if(this._fCat.size>0)n++;if(this._fEnt.size>0)n++;if(this._fFrom)n++;if(this._fTo)n++;return n}
_clearFilters(){this._fClass.clear();this._fCat.clear();this._fEnt.clear();this._fFrom="";this._fTo="";this._fText="";
const fi=this.shadowRoot.getElementById("filter");if(fi)fi.value="";this._updatePanel();this._update()}

// ── Acknowledge ──
async _ack(id){if(!this._hass)return;await this._hass.callService("hass_console","acknowledge_alarm",{id});await this._fetch()}
async _ackAll(){if(!this._hass)return;await this._hass.callService("hass_console","acknowledge_all",{});await this._fetch()}

// ── Render ──
_render(){
const S=`
:host{--bg:#0c1117;--sf:#141b24;--bd:#1e2a36;--tx:#c8d6e0;--dim:#6b7f8e;--ac:#00d4aa;--red:#ff4757;--amb:#ffa502;--blu:#3b82f6;--hbg:#0f1820;--hov:rgba(0,212,170,.06);--fn:"SF Mono","Cascadia Code","JetBrains Mono","Fira Code",monospace}
*{box-sizing:border-box;margin:0;padding:0}
.wrap{background:var(--bg);border:1px solid var(--bd);border-radius:12px;overflow:hidden;font-family:var(--fn);font-size:12px;color:var(--tx)}
.hbar{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--sf);border-bottom:1px solid var(--bd)}
.htitle{font-size:14px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--ac);display:flex;align-items:center;gap:8px}
.htitle .dot{width:8px;height:8px;border-radius:50%;background:var(--ac);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.hmeta{font-size:11px;color:var(--dim)}
.tbar{display:flex;background:var(--hbg);border-bottom:2px solid var(--bd)}
.tbtn{flex:1;padding:10px 0;text-align:center;font-family:var(--fn);font-size:12px;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;color:var(--dim);background:none;border:none;cursor:pointer;position:relative;transition:color .2s}
.tbtn:hover{color:var(--tx)}.tbtn.active{color:var(--ac)}
.tbtn.active::after{content:"";position:absolute;bottom:-2px;left:10%;width:80%;height:2px;background:var(--ac);border-radius:1px}
.badge{display:inline-block;min-width:18px;padding:1px 5px;margin-left:6px;border-radius:9px;font-size:10px;font-weight:700;background:var(--bd);color:var(--dim)}
.tbtn.active .badge{background:rgba(0,212,170,.15);color:var(--ac)}
.badge-unack{background:rgba(255,71,87,.15);color:var(--red)}
.toolbar{display:flex;align-items:center;gap:6px;padding:8px 12px;background:var(--sf);border-bottom:1px solid var(--bd);flex-wrap:wrap}
.finput{flex:1;min-width:120px;padding:6px 10px;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--tx);font-family:var(--fn);font-size:11px;outline:none}
.finput:focus{border-color:var(--ac);box-shadow:0 0 0 2px rgba(0,212,170,.15)}
.finput::placeholder{color:var(--dim)}
.btn{padding:5px 10px;border:1px solid var(--bd);border-radius:6px;background:var(--sf);color:var(--dim);font-family:var(--fn);font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap}
.btn:hover{border-color:var(--ac);color:var(--ac)}
.btn.has{border-color:var(--ac);color:var(--ac);background:rgba(0,212,170,.08)}
.btn.ack-all{border-color:var(--red);color:var(--red)}.btn.ack-all:hover{background:rgba(255,71,87,.1)}
.btn.show-ack.active{border-color:var(--ac);color:var(--ac);background:rgba(0,212,170,.08)}
.fcnt{display:inline-block;min-width:16px;height:16px;line-height:16px;text-align:center;border-radius:8px;font-size:9px;font-weight:800;background:var(--ac);color:var(--bg);margin-left:4px}
.fpanel{max-height:0;overflow:hidden;transition:max-height .3s ease,padding .3s ease;background:var(--hbg);border-bottom:0px solid var(--bd)}
.fpanel.open{max-height:500px;padding:12px 14px;border-bottom-width:1px}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.fgrp{display:flex;flex-direction:column;gap:5px}
.flbl{font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--dim)}
.fdate{padding:6px 8px;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--tx);font-family:var(--fn);font-size:11px;outline:none;-webkit-appearance:none}
.fdate:focus{border-color:var(--ac)}.fdate::-webkit-calendar-picker-indicator{filter:invert(.7)}
.chips{display:flex;flex-wrap:wrap;gap:4px}
.chip{display:inline-flex;align-items:center;padding:3px 9px;border-radius:12px;font-size:10px;font-weight:600;cursor:pointer;border:1px solid var(--bd);background:var(--sf);color:var(--dim);transition:all .15s;user-select:none}
.chip:hover{border-color:var(--dim)}.chip.sel{border-color:var(--ac);color:var(--ac);background:rgba(0,212,170,.1)}
.chip.c01.sel{border-color:var(--red);color:var(--red);background:rgba(255,71,87,.1)}
.chip.c02.sel{border-color:var(--amb);color:var(--amb);background:rgba(255,165,2,.1)}
.chip.c03.sel{border-color:var(--blu);color:var(--blu);background:rgba(59,130,246,.1)}
.factions{display:flex;justify-content:flex-end;margin-top:10px;padding-top:10px;border-top:1px solid var(--bd)}
.fclr{padding:4px 12px;border:1px solid var(--bd);border-radius:6px;background:none;color:var(--dim);font-family:var(--fn);font-size:10px;cursor:pointer}.fclr:hover{border-color:var(--red);color:var(--red)}
.drow{display:flex;align-items:center;gap:6px}.drow span{font-size:10px;color:var(--dim);font-weight:600}
.prow{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.pbtn{padding:2px 8px;border:1px solid var(--bd);border-radius:10px;background:none;color:var(--dim);font-family:var(--fn);font-size:9px;cursor:pointer}.pbtn:hover,.pbtn.active{border-color:var(--ac);color:var(--ac)}
.tscroll{overflow-x:auto;overflow-y:auto;max-height:520px}
table{width:100%;border-collapse:collapse}thead{position:sticky;top:0;z-index:2}
thead th{padding:8px 10px;background:var(--hbg);border-bottom:2px solid var(--bd);text-align:left;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--dim);white-space:nowrap;cursor:pointer;user-select:none}
thead th:hover{color:var(--ac)}thead th .sa{margin-left:3px;font-size:9px;opacity:.5}thead th.sorted{color:var(--ac)}thead th.sorted .sa{opacity:1}
tbody tr{border-bottom:1px solid var(--bd);transition:background .1s}tbody tr:hover{background:var(--hov)}
tbody tr.acked{opacity:.45}
td{padding:7px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;font-size:11.5px}
.clb{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.5px}
.c01{background:rgba(255,71,87,.15);color:var(--red)}.c02{background:rgba(255,165,2,.15);color:var(--amb)}.c03{background:rgba(59,130,246,.15);color:var(--blu)}.cdf{background:rgba(200,214,224,.1);color:var(--dim)}
.catb{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600;background:rgba(0,212,170,.1);color:var(--ac);border:1px solid rgba(0,212,170,.25)}
.tsd{color:var(--dim)}.tst{color:var(--tx);font-weight:600}
.ack-btn{padding:2px 8px;border:1px solid var(--red);border-radius:4px;background:rgba(255,71,87,.08);color:var(--red);font-family:var(--fn);font-size:9px;font-weight:700;cursor:pointer;transition:all .15s;letter-spacing:.5px}
.ack-btn:hover{background:rgba(255,71,87,.2)}
.ack-done{font-size:10px;color:var(--ac);font-weight:600}
.empty{padding:48px 16px;text-align:center;color:var(--dim)}.empty .icon{font-size:32px;margin-bottom:8px}.empty .msg{font-size:13px}
.foot{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--sf);border-top:1px solid var(--bd);font-size:10px;color:var(--dim)}
.ftags{display:flex;gap:6px;flex-wrap:wrap}
.ftag{display:inline-flex;align-items:center;gap:3px;padding:1px 7px;border-radius:8px;font-size:9px;background:rgba(0,212,170,.1);color:var(--ac);border:1px solid rgba(0,212,170,.2)}
.ftag .x{cursor:pointer;font-weight:800;margin-left:2px;opacity:.6}.ftag .x:hover{opacity:1}`;

this.shadowRoot.innerHTML=`<style>${S}</style>
<div class="wrap">
<div class="hbar"><div class="htitle"><span class="dot"></span>${this._c.title}</div><div class="hmeta" id="meta"></div></div>
<div class="tbar" id="tabs"></div>
<div class="toolbar" id="toolbar">
<input class="finput" id="filter" placeholder="Search all columns…"/>
<button class="btn" id="filterToggle">⚙ Filters</button>
<span id="ackBtns"></span>
<button class="btn" id="refreshBtn">↻</button>
<button class="btn" id="dlBtn">↓ CSV</button>
</div>
<div class="fpanel" id="fp"></div>
<div class="tscroll"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div>
<div class="foot"><div style="display:flex;align-items:center;gap:10px"><span id="rc"></span><div class="ftags" id="ftags"></div></div><span>HASS Console v${VER}</span></div>
</div>`;

this.shadowRoot.getElementById("filter").addEventListener("input",e=>{this._fText=e.target.value;this._update()});
this.shadowRoot.getElementById("refreshBtn").addEventListener("click",()=>this._fetch());
this.shadowRoot.getElementById("dlBtn").addEventListener("click",()=>{window.open(this._tab==="ALARM"?this._c.alarm_csv:this._c.log_csv,"_blank")});
this.shadowRoot.getElementById("filterToggle").addEventListener("click",()=>{this._filtersOpen=!this._filtersOpen;this._updatePanel()});
this._renderTabs()}

// ── Tabs ──
_renderTabs(){const c=this.shadowRoot.getElementById("tabs");const unack=this._unackCount();
c.innerHTML=`<button class="tbtn ${this._tab==="ALARM"?"active":""}" data-t="ALARM">Alarm <span class="badge badge-unack">${unack}</span></button>
<button class="tbtn ${this._tab==="LOG"?"active":""}" data-t="LOG">Log <span class="badge">${this._log.length}</span></button>`;
c.querySelectorAll(".tbtn").forEach(b=>b.addEventListener("click",()=>{
this._tab=b.dataset.t;this._sortCol=null;this._sortDir="desc";this._fClass.clear();this._fCat.clear();this._fEnt.clear();
this._renderTabs();this._updatePanel();this._update()}))}

// ── Ack buttons in toolbar ──
_renderAckBtns(){const el=this.shadowRoot.getElementById("ackBtns");
if(this._tab!=="ALARM"){el.innerHTML="";return}
const unack=this._unackCount();
let html=`<button class="btn show-ack ${this._showAck?"active":""}" id="toggleAck">${this._showAck?"Hide":"Show"} ACK'd</button>`;
if(unack>0)html+=` <button class="btn ack-all" id="ackAllBtn">ACK All (${unack})</button>`;
el.innerHTML=html;
el.querySelector("#toggleAck")?.addEventListener("click",()=>{this._showAck=!this._showAck;this._update()});
el.querySelector("#ackAllBtn")?.addEventListener("click",()=>this._ackAll())}

// ── Filter Panel ──
_updatePanel(){const p=this.shadowRoot.getElementById("fp");const t=this.shadowRoot.getElementById("filterToggle");const n=this._cntFilters();
p.classList.toggle("open",this._filtersOpen);t.className=`btn${n>0?" has":""}`;t.innerHTML=`⚙ Filters${n>0?`<span class="fcnt">${n}</span>`:""}`;
if(!this._filtersOpen){p.innerHTML="";return}
const cls=this._distClasses(),cats=this._distCats(),ents=this._distEnts();
const today=new Date(),fmt=d=>d.toISOString().slice(0,10);
const presets=[{l:"Today",f:fmt(today),t:fmt(today)},{l:"7d",f:fmt(new Date(today-7*864e5)),t:fmt(today)},{l:"30d",f:fmt(new Date(today-30*864e5)),t:fmt(today)},{l:"Month",f:fmt(new Date(today.getFullYear(),today.getMonth(),1)),t:fmt(today)}];

let clsH="";if(this._tab==="ALARM"&&cls.length){clsH=`<div class="fgrp"><div class="flbl">Alarm Class</div><div class="chips" id="clsC">${cls.map(c=>{
const s=this._fClass.has(c)?"sel":"";const cc=c==="01"?"c01":c==="02"?"c02":c==="03"?"c03":"";
const l=c==="01"?"01 Crit":c==="02"?"02 Major":c==="03"?"03 Minor":c;
return`<span class="chip ${cc} ${s}" data-v="${c}">${l}</span>`}).join("")}</div></div>`}
let catH="";if(cats.length){catH=`<div class="fgrp"><div class="flbl">Category</div><div class="chips" id="catC">${cats.map(c=>`<span class="chip ${this._fCat.has(c)?"sel":""}" data-v="${c}">${c}</span>`).join("")}</div></div>`}
let entH="";if(ents.length){entH=`<div class="fgrp"><div class="flbl">Entity</div><div class="chips" id="entC">${ents.map(e=>`<span class="chip ${this._fEnt.has(e)?"sel":""}" data-v="${e}">${e.replace("hass_console.","")}</span>`).join("")}</div></div>`}
const pbtns=presets.map(pr=>`<button class="pbtn ${this._fFrom===pr.f&&this._fTo===pr.t?"active":""}" data-f="${pr.f}" data-t="${pr.t}">${pr.l}</button>`).join("");

p.innerHTML=`<div class="fgrid">${clsH}${catH}${entH}<div class="fgrp"><div class="flbl">Date Range</div><div class="drow"><input type="date" class="fdate" id="df" value="${this._fFrom}"/><span>→</span><input type="date" class="fdate" id="dt" value="${this._fTo}"/></div><div class="prow">${pbtns}</div></div></div><div class="factions"><button class="fclr" id="fclr">✕ Clear All</button></div>`;

const wire=(sel,set)=>{p.querySelectorAll(sel).forEach(ch=>ch.addEventListener("click",()=>{const v=ch.dataset.v;if(set.has(v))set.delete(v);else set.add(v);this._updatePanel();this._update()}))};
wire("#clsC .chip",this._fClass);wire("#catC .chip",this._fCat);wire("#entC .chip",this._fEnt);
p.querySelector("#df")?.addEventListener("change",e=>{this._fFrom=e.target.value;this._updatePanel();this._update()});
p.querySelector("#dt")?.addEventListener("change",e=>{this._fTo=e.target.value;this._updatePanel();this._update()});
p.querySelectorAll(".pbtn").forEach(b=>b.addEventListener("click",()=>{this._fFrom=b.dataset.f;this._fTo=b.dataset.t;this._updatePanel();this._update()}));
p.querySelector("#fclr")?.addEventListener("click",()=>this._clearFilters())}

// ── Footer tags ──
_renderFoot(){const el=this.shadowRoot.getElementById("ftags");if(!el)return;const tags=[];
if(this._fClass.size)tags.push({l:`Class: ${[...this._fClass]}`,c:()=>this._fClass.clear()});
if(this._fCat.size)tags.push({l:`Cat: ${[...this._fCat]}`,c:()=>this._fCat.clear()});
if(this._fEnt.size)tags.push({l:`Ent: ${[...this._fEnt].map(e=>e.replace("hass_console.",""))}`,c:()=>this._fEnt.clear()});
if(this._fFrom||this._fTo)tags.push({l:`Date: ${this._fFrom||"…"}→${this._fTo||"…"}`,c:()=>{this._fFrom="";this._fTo=""}});
el.innerHTML=tags.map((t,i)=>`<span class="ftag">${t.l}<span class="x" data-i="${i}">✕</span></span>`).join("");
el.querySelectorAll(".x").forEach(x=>x.addEventListener("click",()=>{tags[parseInt(x.dataset.i)]?.c();this._updatePanel();this._update()}))}

// ── Columns ──
_cols(){
if(this._tab==="ALARM"){const cols=[{k:"timestamp",l:"Timestamp"},{k:"category",l:"Category"},{k:"entity",l:"Entity"},{k:"class",l:"Class"},
{k:"value",l:"Value"},{k:"duration",l:"Duration"},{k:"note",l:"Note"},{k:"trigger",l:"Trigger"},{k:"_ack",l:""}];return cols}
return[{k:"timestamp",l:"Timestamp"},{k:"category",l:"Category"},{k:"entity",l:"Entity"},{k:"value",l:"Value"},{k:"note",l:"Note"}]}

// ── Table update ──
_update(){this._renderTabs();this._renderAckBtns();this._renderFoot();
const cols=this._cols(),rows=this._rows();
const thead=this.shadowRoot.getElementById("thead");
thead.innerHTML=`<tr>${cols.map(c=>{if(c.k==="_ack")return`<th style="width:70px"></th>`;
const s=this._sortCol===c.k;const a=s?(this._sortDir==="asc"?"▲":"▼"):"⇅";
return`<th class="${s?"sorted":""}" data-c="${c.k}">${c.l}<span class="sa">${a}</span></th>`}).join("")}</tr>`;
thead.querySelectorAll("th[data-c]").forEach(th=>th.addEventListener("click",()=>{
const c=th.dataset.c;if(this._sortCol===c)this._sortDir=this._sortDir==="asc"?"desc":"asc";else{this._sortCol=c;this._sortDir="asc"}this._update()}));

const tbody=this.shadowRoot.getElementById("tbody");
if(!rows.length){const hasF=this._cntFilters()>0||this._fText;const icon=hasF?"🔍":this._tab==="ALARM"?"🔔":"📋";
const msg=hasF?"No entries match current filters":this._tab==="ALARM"&&!this._showAck?"No unacknowledged alarms":`No ${this._tab.toLowerCase()} entries yet`;
tbody.innerHTML=`<tr><td colspan="${cols.length}"><div class="empty"><div class="icon">${icon}</div><div class="msg">${msg}</div></div></td></tr>`}
else{tbody.innerHTML=rows.map(r=>{
const isAcked=!!(r.ack);const trCls=isAcked?"acked":"";
return`<tr class="${trCls}">${cols.map(c=>{
if(c.k==="_ack"){if(isAcked)return`<td><span class="ack-done">✓ ${this._esc(r.ack)}</span></td>`;
return`<td><button class="ack-btn" data-id="${this._esc(r.id||"")}">ACK</button></td>`}
return`<td>${this._fmtCell(c.k,r[c.k]||"")}</td>`}).join("")}</tr>`}).join("")}

// Wire ACK buttons
tbody.querySelectorAll(".ack-btn").forEach(b=>b.addEventListener("click",e=>{e.stopPropagation();this._ack(b.dataset.id)}));

const total=this._data().length;const showing=rows.length;
const filteredNote=this._tab==="ALARM"&&!this._showAck?` (${this._alarm.length-this._unackCount()} ack'd hidden)`:"";
this.shadowRoot.getElementById("rc").textContent=total!==showing?`${showing} of ${total} rows${filteredNote}`:`${showing} rows${filteredNote}`;
this.shadowRoot.getElementById("meta").textContent=`Refreshed ${new Date().toLocaleTimeString()}`}

_fmtCell(k,v){
if(k==="timestamp"&&v){const p=v.split(' ');if(p.length===2&&/^\d{4}-\d{2}-\d{2}$/.test(p[0]))return`<span class="tsd">${this._esc(p[0])}</span> <span class="tst">${this._esc(p[1])}</span>`;
const d=parseTS(v);if(d){return`<span class="tsd">${d.toLocaleDateString("en-US",{year:"numeric",month:"short",day:"numeric"})}</span> <span class="tst">${d.toLocaleTimeString("en-US",{hour12:false})}</span>`}return this._esc(v)}
if(k==="class"&&v){const c=v==="01"?"c01":v==="02"?"c02":v==="03"?"c03":"cdf";return`<span class="clb ${c}">${this._esc(v)}</span>`}
if(k==="category"&&v)return`<span class="catb">${this._esc(v)}</span>`;
if(k==="entity"&&v)return this._esc(v.replace("hass_console.",""));
return this._esc(v)}

_esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML}
getCardSize(){return 8}
disconnectedCallback(){if(this._timer)clearInterval(this._timer)}
static getStubConfig(){return{title:"HASS Console",alarm_csv:"/local/hass-console-alarms.csv",log_csv:"/local/hass-console-logs.csv",rows:200,refresh_interval:30}}
}

customElements.define("hass-console-card",HassConsoleCard);
window.customCards=window.customCards||[];
window.customCards.push({type:"hass-console-card",name:"HASS Console Card",description:"Niagara-style Alarm & Log console for Home Assistant"});
