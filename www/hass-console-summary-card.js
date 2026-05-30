/**
 * HASS Console Summary Card v2.5.0
 *
 * A compact at-a-glance alarm status widget.
 * Shows alarm counts by severity, ack status, log count,
 * and a 7-day alarm trend sparkline.
 *
 * CONFIG:
 *   type: custom:hass-console-summary-card
 *   title: Console Status
 *   alarm_csv: /local/hass-console/alarms.csv
 *   log_csv: /local/hass-console/logs.csv
 *   refresh_interval: 30
 *   theme: auto           # auto | dark | light
 *   show_trend: true      # 7-day alarm trend sparkline
 *   show_log_count: true  # log entries total
 */
const SVER = "2.5.0";

function _parseTS(v) {
  if (!v) return null;
  const n = v.includes(" ") && !v.includes("T") ? v.replace(" ", "T") : v;
  const d = new Date(n);
  return isNaN(d) ? null : d;
}

class HassConsoleSummaryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._c = {};
    this._alarm = [];
    this._log = [];
    this._timer = null;
    this._theme = "auto";
  }

  setConfig(c) {
    this._c = {
      title: c.title || "Console Status",
      alarm_csv: c.alarm_csv || "/local/hass-console/alarms.csv",
      log_csv: c.log_csv || "/local/hass-console/logs.csv",
      refresh: c.refresh_interval || 30,
      show_trend: c.show_trend !== false,
      show_log: c.show_log_count !== false,
    };
    this._theme = c.theme || "auto";
  }

  set hass(h) {
    this._hass = h;
    if (!this._init) {
      this._init = true;
      this._fetch();
      this._startRefresh();
    }
  }

  _isDark() {
    if (this._theme === "dark") return true;
    if (this._theme === "light") return false;
    const bg = getComputedStyle(document.documentElement)
      .getPropertyValue("--primary-background-color").trim();
    if (!bg) return true;
    const m = bg.match(/\d+/g);
    if (!m || m.length < 3) return true;
    return (parseInt(m[0]) * 299 + parseInt(m[1]) * 587 + parseInt(m[2]) * 114) / 1000 < 128;
  }

  _startRefresh() {
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this._fetch(), this._c.refresh * 1000);
  }

  async _fetch() {
    await Promise.all([this._fetchOne("alarm"), this._fetchOne("log")]);
    this._render();
  }

  async _fetchOne(t) {
    try {
      const u = t === "alarm" ? this._c.alarm_csv : this._c.log_csv;
      const r = await fetch(u + `?_=${Date.now()}`);
      if (!r.ok) { if (t === "alarm") this._alarm = []; else this._log = []; return; }
      const lines = (await r.text()).trim().split("\n");
      if (lines.length < 2) { if (t === "alarm") this._alarm = []; else this._log = []; return; }
      const hdr = lines[0].split(",").map(h => h.trim());
      const rows = [];
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(",");
        if (cols.length < hdr.length) continue;
        const row = {};
        hdr.forEach((h, j) => row[h] = (cols[j] || "").trim());
        rows.push(row);
      }
      if (t === "alarm") this._alarm = rows; else this._log = rows;
    } catch (e) {
      console.error("HASS Console Summary:", e);
    }
  }

  _counts() {
    const alarms = this._alarm;
    const unack = alarms.filter(r => !r.ack);
    const acked = alarms.filter(r => !!r.ack);
    const c01 = unack.filter(r => r.class === "01").length;
    const c02 = unack.filter(r => r.class === "02").length;
    const c03 = unack.filter(r => r.class === "03").length;
    const other = unack.length - c01 - c02 - c03;
    return { total: alarms.length, unack: unack.length, acked: acked.length, c01, c02, c03, other, logs: this._log.length };
  }

  _trend() {
    // Count alarms per day for the last 7 days
    const now = new Date();
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      days.push(d.toISOString().slice(0, 10));
    }
    const counts = days.map(day => {
      return this._alarm.filter(r => {
        const ts = r.timestamp || "";
        return ts.startsWith(day);
      }).length;
    });
    const max = Math.max(...counts, 1);
    return { days, counts, max };
  }

  _dayLabel(iso) {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", { weekday: "short" }).slice(0, 2);
  }

  _render() {
    const dk = this._isDark();
    const c = this._counts();
    const trend = this._c.show_trend ? this._trend() : null;

    // Status indicator
    let statusColor, statusLabel;
    if (c.c01 > 0) { statusColor = "#ff4757"; statusLabel = "CRITICAL"; }
    else if (c.c02 > 0) { statusColor = "#ffa502"; statusLabel = "ATTENTION"; }
    else if (c.c03 > 0) { statusColor = "#3b82f6"; statusLabel = "MINOR"; }
    else { statusColor = dk ? "#2ed573" : "#27ae60"; statusLabel = "ALL CLEAR"; }

    const acBg = dk ? "rgba(0,212,170,.1)" : "rgba(3,169,244,.08)";
    const acBd = dk ? "rgba(0,212,170,.25)" : "rgba(3,169,244,.2)";
    const ac = dk ? "#00d4aa" : "#03a9f4";

    const S = `
:host{display:block}
*{box-sizing:border-box;margin:0;padding:0}
.card{
  background:${dk ? "#0c1117" : "var(--ha-card-background, var(--card-background-color, #fff))"};
  border:1px solid ${dk ? "#1e2a36" : "var(--divider-color, #e0e0e0)"};
  border-radius:12px;overflow:hidden;
  font-family:"SF Mono","Cascadia Code","JetBrains Mono","Fira Code",monospace;
  font-size:12px;color:${dk ? "#c8d6e0" : "var(--primary-text-color, #212121)"};
}

/* ── Header ── */
.hdr{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px;
  background:${dk ? "#141b24" : "var(--secondary-background-color, #f5f5f5)"};
  border-bottom:1px solid ${dk ? "#1e2a36" : "var(--divider-color, #e0e0e0)"}}
.hdr-left{display:flex;align-items:center;gap:10px}
.hdr-dot{width:10px;height:10px;border-radius:50%;background:${statusColor};box-shadow:0 0 8px ${statusColor}80;animation:${c.c01>0?"blink 1s infinite":"none"}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.hdr-title{font-size:13px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:${ac}}
.hdr-status{font-size:10px;font-weight:700;letter-spacing:1px;color:${statusColor};padding:2px 8px;border:1px solid ${statusColor}40;border-radius:6px;background:${statusColor}15}

/* ── Severity gauges ── */
.gauges{display:flex;gap:8px;padding:16px 16px 12px;justify-content:center}
.gauge{flex:1;max-width:100px;text-align:center;padding:10px 6px;border-radius:8px;border:1px solid ${dk?"#1e2a36":"#e8e8e8"};background:${dk?"#141b24":"#fafafa"};transition:transform .15s}
.gauge:hover{transform:translateY(-2px)}
.gauge-num{font-size:28px;font-weight:800;line-height:1;letter-spacing:-1px}
.gauge-lbl{font-size:8px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-top:4px;color:${dk?"#6b7f8e":"#999"}}
.g-crit .gauge-num{color:#ff4757}
.g-major .gauge-num{color:#ffa502}
.g-minor .gauge-num{color:#3b82f6}
.g-other .gauge-num{color:${dk?"#6b7f8e":"#999"}}

/* ── Stats row ── */
.stats{display:flex;gap:10px;padding:0 16px 14px;flex-wrap:wrap}
.stat{display:flex;align-items:center;gap:5px;font-size:11px;color:${dk?"#6b7f8e":"#888"}}
.stat-icon{font-size:13px}
.stat-num{font-weight:700;color:${dk?"#c8d6e0":"#333"}}

/* ── Trend sparkline ── */
.trend{padding:4px 16px 14px}
.trend-label{font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:${dk?"#6b7f8e":"#999"};margin-bottom:6px}
.spark{display:flex;align-items:flex-end;gap:3px;height:36px}
.spark-bar{flex:1;border-radius:3px 3px 0 0;min-height:2px;transition:height .3s ease;position:relative}
.spark-bar:hover{opacity:.8}
.spark-bar .tip{display:none;position:absolute;bottom:calc(100% + 4px);left:50%;transform:translateX(-50%);
  font-size:9px;font-weight:700;background:${dk?"#1e2a36":"#333"};color:${dk?"#c8d6e0":"#fff"};
  padding:2px 6px;border-radius:4px;white-space:nowrap;z-index:5}
.spark-bar:hover .tip{display:block}
.spark-days{display:flex;gap:3px;margin-top:3px}
.spark-day{flex:1;text-align:center;font-size:8px;color:${dk?"#4a5a6a":"#bbb"};font-weight:600}

/* ── Footer ── */
.foot{padding:8px 16px;background:${dk?"#141b24":"#f5f5f5"};border-top:1px solid ${dk?"#1e2a36":"#e0e0e0"};
  font-size:9px;color:${dk?"#4a5a6a":"#bbb"};display:flex;justify-content:space-between}
`;

    // Build gauges
    const gaugeData = [
      { cls: "g-crit", num: c.c01, label: "Critical" },
      { cls: "g-major", num: c.c02, label: "Major" },
      { cls: "g-minor", num: c.c03, label: "Minor" },
    ];
    if (c.other > 0) gaugeData.push({ cls: "g-other", num: c.other, label: "Other" });

    const gaugesHTML = gaugeData.map(g =>
      `<div class="gauge ${g.cls}"><div class="gauge-num">${g.num}</div><div class="gauge-lbl">${g.label}</div></div>`
    ).join("");

    // Stats
    let statsHTML = `
      <div class="stat"><span class="stat-icon">⚠</span><span class="stat-num">${c.unack}</span> unack'd</div>
      <div class="stat"><span class="stat-icon">✓</span><span class="stat-num">${c.acked}</span> ack'd</div>
      <div class="stat"><span class="stat-icon">∑</span><span class="stat-num">${c.total}</span> total alarms</div>`;
    if (this._c.show_log) {
      statsHTML += `<div class="stat"><span class="stat-icon">📋</span><span class="stat-num">${c.logs}</span> log entries</div>`;
    }

    // Trend sparkline
    let trendHTML = "";
    if (trend) {
      const barColor = (count) => {
        if (count === 0) return dk ? "#1e2a36" : "#e8e8e8";
        const intensity = Math.min(count / trend.max, 1);
        if (intensity > 0.7) return "#ff4757";
        if (intensity > 0.4) return "#ffa502";
        return ac;
      };
      const bars = trend.counts.map((count, i) => {
        const h = count === 0 ? 2 : Math.max(4, (count / trend.max) * 36);
        const day = this._dayLabel(trend.days[i]);
        return `<div class="spark-bar" style="height:${h}px;background:${barColor(count)}">
          <span class="tip">${trend.days[i]}: ${count}</span>
        </div>`;
      }).join("");
      const dayLabels = trend.days.map(d => `<div class="spark-day">${this._dayLabel(d)}</div>`).join("");
      trendHTML = `<div class="trend">
        <div class="trend-label">7-Day Alarm Trend</div>
        <div class="spark">${bars}</div>
        <div class="spark-days">${dayLabels}</div>
      </div>`;
    }

    this.shadowRoot.innerHTML = `<style>${S}</style>
    <div class="card">
      <div class="hdr">
        <div class="hdr-left">
          <div class="hdr-dot"></div>
          <div class="hdr-title">${this._c.title}</div>
        </div>
        <div class="hdr-status">${statusLabel}</div>
      </div>
      <div class="gauges">${gaugesHTML}</div>
      <div class="stats">${statsHTML}</div>
      ${trendHTML}
      <div class="foot">
        <span>Refreshed ${new Date().toLocaleTimeString()}</span>
        <span>HASS Console v${SVER}</span>
      </div>
    </div>`;
  }

  getCardSize() { return 4; }
  disconnectedCallback() { if (this._timer) clearInterval(this._timer); }

  static getStubConfig() {
    return {
      title: "Console Status",
      alarm_csv: "/local/hass-console/alarms.csv",
      log_csv: "/local/hass-console/logs.csv",
      refresh_interval: 30,
      theme: "auto",
    };
  }
}

customElements.define("hass-console-summary-card", HassConsoleSummaryCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "hass-console-summary-card",
  name: "HASS Console Summary Card",
  description: "Compact alarm status widget — counts by severity, ack status, 7-day trend",
});
