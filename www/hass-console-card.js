/**
 * HASS Console Card v2.2.0 — Niagara-style Alarm & Log viewer
 *
 * INSTALL:
 *   1. Copy to /config/www/hass-console-card.js
 *   2. Settings → Dashboards → Resources → Add:
 *        /local/hass-console-card.js  (JavaScript Module)
 *   3. Add Manual card: type: custom:hass-console-card
 *
 * CONFIG:
 *   type: custom:hass-console-card
 *   title: HASS Console
 *   alarm_csv: /local/hass-console-alarms.csv
 *   log_csv: /local/hass-console-logs.csv
 *   rows: 200
 *   refresh_interval: 30
 */

const CARD_VERSION = "2.2.0";

// Parse the engine's "YYYY-MM-DD HH:MM:SS" format (also handles legacy ISO timestamps)
function parseTimestamp(val) {
  if (!val) return null;
  const normalized = (val.indexOf(' ') !== -1 && val.indexOf('T') === -1)
    ? val.replace(' ', 'T') : val;
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? null : d;
}

class HassConsoleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._alarmData = [];
    this._logData = [];
    this._activeTab = "ALARM";
    this._refreshTimer = null;
    this._sortCol = null;
    this._sortDir = "desc";
    this._filterText = "";
    this._filterClasses = new Set();
    this._filterCategories = new Set();
    this._filterEntities = new Set();
    this._filterDateFrom = "";
    this._filterDateTo = "";
    this._filtersOpen = false;
    this._activeFilterCount = 0;
  }

  setConfig(config) {
    this._config = {
      title: config.title || "HASS Console",
      alarm_csv: config.alarm_csv || "/local/hass-console-alarms.csv",
      log_csv: config.log_csv || "/local/hass-console-logs.csv",
      rows: config.rows || 200,
      refresh_interval: config.refresh_interval || 30,
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._render();
      this._fetchCSVs();
      this._startAutoRefresh();
    }
  }

  _startAutoRefresh() {
    if (this._refreshTimer) clearInterval(this._refreshTimer);
    this._refreshTimer = setInterval(() => this._fetchCSVs(), this._config.refresh_interval * 1000);
  }

  async _fetchCSVs() {
    await Promise.all([this._fetchCSV("alarm"), this._fetchCSV("log")]);
    this._updateTable();
  }

  async _fetchCSV(type) {
    try {
      const url = type === "alarm" ? this._config.alarm_csv : this._config.log_csv;
      const resp = await fetch(url + `?_=${Date.now()}`);
      if (!resp.ok) { if (type === "alarm") this._alarmData = []; else this._logData = []; return; }
      const text = await resp.text();
      const rows = this._parseCSV(text);
      if (type === "alarm") this._alarmData = rows; else this._logData = rows;
    } catch (e) {
      console.error(`HASS Console: ${type} CSV fetch error:`, e);
    }
  }

  _parseCSV(text) {
    const lines = text.trim().split("\n");
    if (lines.length < 2) return [];
    const headers = this._splitCSVLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = this._splitCSVLine(lines[i]);
      if (cols.length < headers.length) continue;
      const row = {};
      headers.forEach((h, idx) => (row[h.trim()] = cols[idx]?.trim() || ""));
      rows.push(row);
    }
    return rows;
  }

  _splitCSVLine(line) {
    const result = []; let current = ""; let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') inQuotes = !inQuotes;
      else if (ch === "," && !inQuotes) { result.push(current); current = ""; }
      else current += ch;
    }
    result.push(current);
    return result;
  }

  _getData() { return this._activeTab === "ALARM" ? this._alarmData : this._logData; }

  _getDistinctClasses() {
    const s = new Set();
    this._alarmData.forEach(r => { if (r.class) s.add(r.class); });
    return [...s].sort();
  }
  _getDistinctCategories() {
    const s = new Set();
    this._getData().forEach(r => { if (r.category) s.add(r.category); });
    return [...s].sort();
  }
  _getDistinctEntities() {
    const s = new Set();
    this._getData().forEach(r => { if (r.entity) s.add(r.entity); });
    return [...s].sort();
  }

  _getRows() {
    let rows = [...this._getData()];

    if (this._filterText) {
      const ft = this._filterText.toLowerCase();
      rows = rows.filter(r => Object.values(r).some(v => v.toLowerCase().includes(ft)));
    }
    if (this._filterClasses.size > 0 && this._activeTab === "ALARM") {
      rows = rows.filter(r => this._filterClasses.has(r.class || ""));
    }
    if (this._filterCategories.size > 0) {
      rows = rows.filter(r => this._filterCategories.has(r.category || ""));
    }
    if (this._filterEntities.size > 0) {
      rows = rows.filter(r => this._filterEntities.has(r.entity || ""));
    }
    if (this._filterDateFrom) {
      const from = new Date(this._filterDateFrom + "T00:00:00");
      rows = rows.filter(r => { const d = parseTimestamp(r.timestamp); return d ? d >= from : true; });
    }
    if (this._filterDateTo) {
      const to = new Date(this._filterDateTo + "T23:59:59");
      rows = rows.filter(r => { const d = parseTimestamp(r.timestamp); return d ? d <= to : true; });
    }

    if (this._sortCol) {
      rows.sort((a, b) => {
        const va = a[this._sortCol] || ""; const vb = b[this._sortCol] || "";
        const cmp = va.localeCompare(vb, undefined, { numeric: true });
        return this._sortDir === "asc" ? cmp : -cmp;
      });
    } else { rows.reverse(); }
    return rows.slice(0, this._config.rows);
  }

  _countActiveFilters() {
    let n = 0;
    if (this._filterClasses.size > 0) n++;
    if (this._filterCategories.size > 0) n++;
    if (this._filterEntities.size > 0) n++;
    if (this._filterDateFrom) n++;
    if (this._filterDateTo) n++;
    this._activeFilterCount = n;
    return n;
  }

  _clearAllFilters() {
    this._filterClasses.clear(); this._filterCategories.clear(); this._filterEntities.clear();
    this._filterDateFrom = ""; this._filterDateTo = ""; this._filterText = "";
    const fi = this.shadowRoot.getElementById("filter");
    if (fi) fi.value = "";
    this._updateFilterPanel(); this._updateTable();
  }

  _render() {
    const style = `
      :host {
        --con-bg: #0c1117; --con-surface: #141b24; --con-border: #1e2a36;
        --con-text: #c8d6e0; --con-text-dim: #6b7f8e; --con-accent: #00d4aa;
        --con-alarm-red: #ff4757; --con-alarm-amber: #ffa502; --con-alarm-blue: #3b82f6;
        --con-tab-active: #00d4aa; --con-row-hover: rgba(0,212,170,0.06);
        --con-header-bg: #0f1820;
        --con-font: "SF Mono","Cascadia Code","JetBrains Mono","Fira Code",monospace;
      }
      *{box-sizing:border-box;margin:0;padding:0}
      .console-wrap{background:var(--con-bg);border:1px solid var(--con-border);border-radius:12px;overflow:hidden;font-family:var(--con-font);font-size:12px;color:var(--con-text)}
      .header-bar{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--con-surface);border-bottom:1px solid var(--con-border)}
      .header-title{font-size:14px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--con-accent);display:flex;align-items:center;gap:8px}
      .header-title .dot{width:8px;height:8px;border-radius:50%;background:var(--con-accent);animation:pulse 2s infinite}
      @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
      .header-meta{font-size:11px;color:var(--con-text-dim)}
      .tab-bar{display:flex;background:var(--con-header-bg);border-bottom:2px solid var(--con-border)}
      .tab-btn{flex:1;padding:10px 0;text-align:center;font-family:var(--con-font);font-size:12px;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;color:var(--con-text-dim);background:none;border:none;cursor:pointer;position:relative;transition:color .2s}
      .tab-btn:hover{color:var(--con-text)}
      .tab-btn.active{color:var(--con-tab-active)}
      .tab-btn.active::after{content:"";position:absolute;bottom:-2px;left:10%;width:80%;height:2px;background:var(--con-tab-active);border-radius:1px}
      .tab-btn .badge{display:inline-block;min-width:18px;padding:1px 5px;margin-left:6px;border-radius:9px;font-size:10px;font-weight:700;background:var(--con-border);color:var(--con-text-dim)}
      .tab-btn.active .badge{background:rgba(0,212,170,.15);color:var(--con-accent)}
      .toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--con-surface);border-bottom:1px solid var(--con-border)}
      .filter-input{flex:1;padding:6px 10px;border:1px solid var(--con-border);border-radius:6px;background:var(--con-bg);color:var(--con-text);font-family:var(--con-font);font-size:11px;outline:none}
      .filter-input:focus{border-color:var(--con-accent);box-shadow:0 0 0 2px rgba(0,212,170,.15)}
      .filter-input::placeholder{color:var(--con-text-dim)}
      .toolbar-btn{padding:5px 10px;border:1px solid var(--con-border);border-radius:6px;background:var(--con-surface);color:var(--con-text-dim);font-family:var(--con-font);font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap}
      .toolbar-btn:hover{border-color:var(--con-accent);color:var(--con-accent)}
      .toolbar-btn.has-filters{border-color:var(--con-accent);color:var(--con-accent);background:rgba(0,212,170,.08)}
      .filter-count{display:inline-block;min-width:16px;height:16px;line-height:16px;text-align:center;border-radius:8px;font-size:9px;font-weight:800;background:var(--con-accent);color:var(--con-bg);margin-left:4px}
      .filter-panel{max-height:0;overflow:hidden;transition:max-height .3s ease,padding .3s ease;background:var(--con-header-bg);border-bottom:0px solid var(--con-border)}
      .filter-panel.open{max-height:500px;padding:12px 14px;border-bottom-width:1px}
      .filter-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
      .filter-group{display:flex;flex-direction:column;gap:5px}
      .filter-label{font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--con-text-dim)}
      .filter-date{padding:6px 8px;border:1px solid var(--con-border);border-radius:6px;background:var(--con-bg);color:var(--con-text);font-family:var(--con-font);font-size:11px;outline:none;-webkit-appearance:none;appearance:none}
      .filter-date:focus{border-color:var(--con-accent);box-shadow:0 0 0 2px rgba(0,212,170,.15)}
      .filter-date::-webkit-calendar-picker-indicator{filter:invert(.7)}
      .chip-container{display:flex;flex-wrap:wrap;gap:4px}
      .chip{display:inline-flex;align-items:center;gap:3px;padding:3px 9px;border-radius:12px;font-size:10px;font-weight:600;cursor:pointer;border:1px solid var(--con-border);background:var(--con-surface);color:var(--con-text-dim);transition:all .15s;user-select:none}
      .chip:hover{border-color:var(--con-text-dim)}
      .chip.selected{border-color:var(--con-accent);color:var(--con-accent);background:rgba(0,212,170,.1)}
      .chip.class-01.selected{border-color:var(--con-alarm-red);color:var(--con-alarm-red);background:rgba(255,71,87,.1)}
      .chip.class-02.selected{border-color:var(--con-alarm-amber);color:var(--con-alarm-amber);background:rgba(255,165,2,.1)}
      .chip.class-03.selected{border-color:var(--con-alarm-blue);color:var(--con-alarm-blue);background:rgba(59,130,246,.1)}
      .filter-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid var(--con-border)}
      .filter-clear-btn{padding:4px 12px;border:1px solid var(--con-border);border-radius:6px;background:none;color:var(--con-text-dim);font-family:var(--con-font);font-size:10px;cursor:pointer;transition:all .15s}
      .filter-clear-btn:hover{border-color:var(--con-alarm-red);color:var(--con-alarm-red)}
      .date-range-row{display:flex;align-items:center;gap:6px}
      .date-range-row span{font-size:10px;color:var(--con-text-dim);font-weight:600}
      .preset-row{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
      .preset-btn{padding:2px 8px;border:1px solid var(--con-border);border-radius:10px;background:none;color:var(--con-text-dim);font-family:var(--con-font);font-size:9px;cursor:pointer;transition:all .12s}
      .preset-btn:hover{border-color:var(--con-accent);color:var(--con-accent)}
      .preset-btn.active{border-color:var(--con-accent);color:var(--con-accent);background:rgba(0,212,170,.08)}
      .table-scroll{overflow-x:auto;overflow-y:auto;max-height:520px}
      table{width:100%;border-collapse:collapse;table-layout:auto}
      thead{position:sticky;top:0;z-index:2}
      thead th{padding:8px 10px;background:var(--con-header-bg);border-bottom:2px solid var(--con-border);text-align:left;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--con-text-dim);white-space:nowrap;cursor:pointer;user-select:none;transition:color .15s}
      thead th:hover{color:var(--con-accent)}
      thead th .sort-arrow{margin-left:3px;font-size:9px;opacity:.5}
      thead th.sorted{color:var(--con-accent)}
      thead th.sorted .sort-arrow{opacity:1}
      tbody tr{border-bottom:1px solid var(--con-border);transition:background .1s}
      tbody tr:hover{background:var(--con-row-hover)}
      td{padding:7px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;font-size:11.5px}
      .class-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.5px}
      .class-01{background:rgba(255,71,87,.15);color:var(--con-alarm-red)}
      .class-02{background:rgba(255,165,2,.15);color:var(--con-alarm-amber)}
      .class-03{background:rgba(59,130,246,.15);color:var(--con-alarm-blue)}
      .class-default{background:rgba(200,214,224,.1);color:var(--con-text-dim)}
      .category-badge{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600;letter-spacing:.3px;background:rgba(0,212,170,.1);color:var(--con-accent);border:1px solid rgba(0,212,170,.25)}
      .ts-date{color:var(--con-text-dim)}.ts-time{color:var(--con-text);font-weight:600}
      .empty-state{padding:48px 16px;text-align:center;color:var(--con-text-dim)}
      .empty-state .icon{font-size:32px;margin-bottom:8px}
      .empty-state .msg{font-size:13px}
      .footer{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--con-surface);border-top:1px solid var(--con-border);font-size:10px;color:var(--con-text-dim)}
      .footer-filters{display:flex;gap:6px;flex-wrap:wrap}
      .active-filter-tag{display:inline-flex;align-items:center;gap:3px;padding:1px 7px;border-radius:8px;font-size:9px;background:rgba(0,212,170,.1);color:var(--con-accent);border:1px solid rgba(0,212,170,.2)}
      .active-filter-tag .x{cursor:pointer;font-weight:800;margin-left:2px;opacity:.6;transition:opacity .1s}
      .active-filter-tag .x:hover{opacity:1}
    `;

    this.shadowRoot.innerHTML = `
      <style>${style}</style>
      <div class="console-wrap">
        <div class="header-bar">
          <div class="header-title"><span class="dot"></span>${this._config.title}</div>
          <div class="header-meta" id="meta"></div>
        </div>
        <div class="tab-bar" id="tabs"></div>
        <div class="toolbar">
          <input class="filter-input" id="filter" placeholder="Search all columns…" />
          <button class="toolbar-btn" id="filterToggle">⚙ Filters</button>
          <button class="toolbar-btn" id="refreshBtn">↻ Refresh</button>
          <button class="toolbar-btn" id="downloadBtn">↓ CSV</button>
        </div>
        <div class="filter-panel" id="filterPanel"></div>
        <div class="table-scroll"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div>
        <div class="footer">
          <div style="display:flex;align-items:center;gap:10px">
            <span id="rowcount"></span>
            <div class="footer-filters" id="footerFilters"></div>
          </div>
          <span>HASS Console v${CARD_VERSION}</span>
        </div>
      </div>`;

    this.shadowRoot.getElementById("filter").addEventListener("input", e => { this._filterText = e.target.value; this._updateTable(); });
    this.shadowRoot.getElementById("refreshBtn").addEventListener("click", () => this._fetchCSVs());
    this.shadowRoot.getElementById("downloadBtn").addEventListener("click", () => {
      const url = this._activeTab === "ALARM" ? this._config.alarm_csv : this._config.log_csv;
      window.open(url, "_blank");
    });
    this.shadowRoot.getElementById("filterToggle").addEventListener("click", () => {
      this._filtersOpen = !this._filtersOpen; this._updateFilterPanel();
    });
    this._renderTabs();
  }

  _renderTabs() {
    const c = this.shadowRoot.getElementById("tabs");
    c.innerHTML = `
      <button class="tab-btn ${this._activeTab==="ALARM"?"active":""}" data-tab="ALARM">Alarm <span class="badge">${this._alarmData.length}</span></button>
      <button class="tab-btn ${this._activeTab==="LOG"?"active":""}" data-tab="LOG">Log <span class="badge">${this._logData.length}</span></button>`;
    c.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        this._activeTab = btn.dataset.tab;
        this._sortCol = null; this._sortDir = "desc";
        this._filterClasses.clear(); this._filterCategories.clear(); this._filterEntities.clear();
        this._renderTabs(); this._updateFilterPanel(); this._updateTable();
      });
    });
  }

  _updateFilterPanel() {
    const panel = this.shadowRoot.getElementById("filterPanel");
    const toggle = this.shadowRoot.getElementById("filterToggle");
    const n = this._countActiveFilters();
    panel.classList.toggle("open", this._filtersOpen);
    toggle.className = `toolbar-btn${n>0?" has-filters":""}`;
    toggle.innerHTML = `⚙ Filters${n>0?`<span class="filter-count">${n}</span>`:""}`;
    if (!this._filtersOpen) { panel.innerHTML = ""; return; }

    const classes = this._getDistinctClasses();
    const categories = this._getDistinctCategories();
    const entities = this._getDistinctEntities();
    const today = new Date(); const fmt = d => d.toISOString().slice(0,10);
    const presets = [
      {label:"Today",from:fmt(today),to:fmt(today)},
      {label:"Last 7d",from:fmt(new Date(today-7*864e5)),to:fmt(today)},
      {label:"Last 30d",from:fmt(new Date(today-30*864e5)),to:fmt(today)},
      {label:"This Month",from:fmt(new Date(today.getFullYear(),today.getMonth(),1)),to:fmt(today)},
    ];

    let classSection = "";
    if (this._activeTab === "ALARM" && classes.length > 0) {
      const chips = classes.map(c => {
        const sel = this._filterClasses.has(c)?"selected":"";
        const cc = c==="01"?"class-01":c==="02"?"class-02":c==="03"?"class-03":"";
        const label = c==="01"?"01 Critical":c==="02"?"02 Major":c==="03"?"03 Minor":c;
        return `<span class="chip ${cc} ${sel}" data-class="${c}">${label}</span>`;
      }).join("");
      classSection = `<div class="filter-group"><div class="filter-label">Alarm Class</div><div class="chip-container" id="classChips">${chips}</div></div>`;
    }

    let categorySection = "";
    if (categories.length > 0) {
      const chips = categories.map(c => {
        const sel = this._filterCategories.has(c)?"selected":"";
        return `<span class="chip ${sel}" data-category="${c}">${c}</span>`;
      }).join("");
      categorySection = `<div class="filter-group"><div class="filter-label">Category</div><div class="chip-container" id="categoryChips">${chips}</div></div>`;
    }

    let entitySection = "";
    if (entities.length > 0) {
      const opts = entities.map(e => {
        const sel = this._filterEntities.has(e)?"selected":"";
        return `<span class="chip ${sel}" data-entity="${e}">${e.replace("hass_console.","")}</span>`;
      }).join("");
      entitySection = `<div class="filter-group"><div class="filter-label">Entity</div><div class="chip-container" id="entityChips">${opts}</div></div>`;
    }

    const presetBtns = presets.map(p => {
      const active = (this._filterDateFrom===p.from&&this._filterDateTo===p.to)?"active":"";
      return `<button class="preset-btn ${active}" data-pfrom="${p.from}" data-pto="${p.to}">${p.label}</button>`;
    }).join("");

    panel.innerHTML = `
      <div class="filter-grid">
        ${classSection}${categorySection}${entitySection}
        <div class="filter-group">
          <div class="filter-label">Date Range</div>
          <div class="date-range-row">
            <input type="date" class="filter-date" id="dateFrom" value="${this._filterDateFrom}" />
            <span>→</span>
            <input type="date" class="filter-date" id="dateTo" value="${this._filterDateTo}" />
          </div>
          <div class="preset-row">${presetBtns}</div>
        </div>
      </div>
      <div class="filter-actions"><button class="filter-clear-btn" id="clearAllFilters">✕ Clear All Filters</button></div>`;

    panel.querySelectorAll("#classChips .chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const v = chip.dataset.class;
        if (this._filterClasses.has(v)) this._filterClasses.delete(v); else this._filterClasses.add(v);
        this._updateFilterPanel(); this._updateTable();
      });
    });
    panel.querySelectorAll("#categoryChips .chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const v = chip.dataset.category;
        if (this._filterCategories.has(v)) this._filterCategories.delete(v); else this._filterCategories.add(v);
        this._updateFilterPanel(); this._updateTable();
      });
    });
    panel.querySelectorAll("#entityChips .chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const v = chip.dataset.entity;
        if (this._filterEntities.has(v)) this._filterEntities.delete(v); else this._filterEntities.add(v);
        this._updateFilterPanel(); this._updateTable();
      });
    });
    const df = panel.querySelector("#dateFrom"), dt = panel.querySelector("#dateTo");
    if (df) df.addEventListener("change", e => { this._filterDateFrom = e.target.value; this._updateFilterPanel(); this._updateTable(); });
    if (dt) dt.addEventListener("change", e => { this._filterDateTo = e.target.value; this._updateFilterPanel(); this._updateTable(); });
    panel.querySelectorAll(".preset-btn").forEach(btn => {
      btn.addEventListener("click", () => { this._filterDateFrom=btn.dataset.pfrom; this._filterDateTo=btn.dataset.pto; this._updateFilterPanel(); this._updateTable(); });
    });
    panel.querySelector("#clearAllFilters").addEventListener("click", () => this._clearAllFilters());
  }

  _renderFooterFilters() {
    const el = this.shadowRoot.getElementById("footerFilters"); if (!el) return;
    const tags = [];
    if (this._filterClasses.size>0) tags.push({label:`Class: ${[...this._filterClasses].join(", ")}`,clear:()=>{this._filterClasses.clear()}});
    if (this._filterCategories.size>0) tags.push({label:`Category: ${[...this._filterCategories].join(", ")}`,clear:()=>{this._filterCategories.clear()}});
    if (this._filterEntities.size>0) tags.push({label:`Entity: ${[...this._filterEntities].map(e=>e.replace("hass_console.","")).join(", ")}`,clear:()=>{this._filterEntities.clear()}});
    if (this._filterDateFrom||this._filterDateTo) tags.push({label:`Date: ${this._filterDateFrom||"…"} → ${this._filterDateTo||"…"}`,clear:()=>{this._filterDateFrom="";this._filterDateTo=""}});
    el.innerHTML = tags.map((t,i)=>`<span class="active-filter-tag">${t.label}<span class="x" data-idx="${i}">✕</span></span>`).join("");
    el.querySelectorAll(".x").forEach(x => {
      x.addEventListener("click", () => { const i=parseInt(x.dataset.idx); if(tags[i]){tags[i].clear();this._updateFilterPanel();this._updateTable()} });
    });
  }

  _getColumns() {
    if (this._activeTab === "ALARM") return [
      {key:"timestamp",label:"Timestamp"},{key:"category",label:"Category"},
      {key:"entity",label:"Entity"},{key:"class",label:"Class"},
      {key:"value",label:"Value"},{key:"duration",label:"Duration"},
      {key:"note",label:"Note"},{key:"trigger",label:"Trigger"},
    ];
    return [
      {key:"timestamp",label:"Timestamp"},{key:"category",label:"Category"},
      {key:"entity",label:"Entity"},{key:"value",label:"Value"},{key:"note",label:"Note"},
    ];
  }

  _updateTable() {
    this._renderTabs(); this._renderFooterFilters();
    const cols = this._getColumns(); const rows = this._getRows();
    const thead = this.shadowRoot.getElementById("thead");
    thead.innerHTML = `<tr>${cols.map(c=>{
      const sorted=this._sortCol===c.key;
      const arrow=sorted?(this._sortDir==="asc"?"▲":"▼"):"⇅";
      return `<th class="${sorted?"sorted":""}" data-col="${c.key}">${c.label}<span class="sort-arrow">${arrow}</span></th>`;
    }).join("")}</tr>`;
    thead.querySelectorAll("th").forEach(th=>{
      th.addEventListener("click",()=>{
        const col=th.dataset.col;
        if(this._sortCol===col) this._sortDir=this._sortDir==="asc"?"desc":"asc";
        else{this._sortCol=col;this._sortDir="asc"}
        this._updateTable();
      });
    });
    const tbody = this.shadowRoot.getElementById("tbody");
    if (rows.length===0) {
      const hasF=this._countActiveFilters()>0||this._filterText;
      const icon=hasF?"🔍":(this._activeTab==="ALARM"?"🔔":"📋");
      const msg=hasF?"No entries match current filters":`No ${this._activeTab.toLowerCase()} entries yet`;
      tbody.innerHTML=`<tr><td colspan="${cols.length}"><div class="empty-state"><div class="icon">${icon}</div><div class="msg">${msg}</div></div></td></tr>`;
    } else {
      tbody.innerHTML=rows.map(r=>`<tr>${cols.map(c=>`<td>${this._formatCell(c.key,r[c.key]||"")}</td>`).join("")}</tr>`).join("");
    }
    const total=this._getData().length; const showing=rows.length;
    this.shadowRoot.getElementById("rowcount").textContent=total!==showing?`${showing} of ${total} rows`:`${showing} rows`;
    this.shadowRoot.getElementById("meta").textContent=`Refreshed ${new Date().toLocaleTimeString()}`;
  }

  _formatCell(key, val) {
    if (key==="timestamp"&&val) {
      // Fast path: engine writes "YYYY-MM-DD HH:MM:SS" with a single space
      const parts = val.split(' ');
      if (parts.length===2 && /^\d{4}-\d{2}-\d{2}$/.test(parts[0])) {
        return `<span class="ts-date">${this._escHTML(parts[0])}</span> <span class="ts-time">${this._escHTML(parts[1])}</span>`;
      }
      // Fallback: legacy ISO format
      const d = parseTimestamp(val);
      if (d) {
        const date=d.toLocaleDateString("en-US",{year:"numeric",month:"short",day:"numeric"});
        const time=d.toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
        return `<span class="ts-date">${date}</span> <span class="ts-time">${time}</span>`;
      }
      return this._escHTML(val);
    }
    if (key==="class"&&val) {
      const cls=val==="01"?"class-01":val==="02"?"class-02":val==="03"?"class-03":"class-default";
      return `<span class="class-badge ${cls}">${this._escHTML(val)}</span>`;
    }
    if (key==="category"&&val) {
      return `<span class="category-badge">${this._escHTML(val)}</span>`;
    }
    if (key==="entity"&&val) return this._escHTML(val.replace("hass_console.",""));
    return this._escHTML(val);
  }

  _escHTML(str){const d=document.createElement("div");d.textContent=str;return d.innerHTML}
  getCardSize(){return 8}
  disconnectedCallback(){if(this._refreshTimer)clearInterval(this._refreshTimer)}
  static getStubConfig(){return{title:"HASS Console",alarm_csv:"/local/hass-console-alarms.csv",log_csv:"/local/hass-console-logs.csv",rows:200,refresh_interval:30}}
}

customElements.define("hass-console-card", HassConsoleCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "hass-console-card", name: "HASS Console Card", description: "Niagara-style Alarm & Log console with filters for Home Assistant" });
