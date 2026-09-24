/**
 * HASS Console Summary Card v3.2.1
 *
 * Minimalist alarm severity gauges. Three numbers. That's it.
 *
 * CONFIG:
 *   type: custom:hass-console-summary-card
 *   alarm_csv: /local/hass-console/alarms.csv
 *   theme: auto           # auto | dark | light  (dark/light mode following)
 *   appearance: hass_ui   # hass_ui | default   (visual style — native HA vs. Niagara)
 *   refresh_interval: 30
 */
const SVER = "3.2.1";

class HassConsoleSummaryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._c = {};
    this._alarm = [];
    this._timer = null;
    this._theme = "auto";
    this._appearance = "hass_ui";
  }

  setConfig(c) {
    this._c = {
      alarm_csv: c.alarm_csv || "/local/hass-console/alarms.csv",
      refresh: c.refresh_interval || 30,
    };
    this._theme = c.theme || "auto";
    this._appearance = c.appearance === "default" ? "default" : "hass_ui";
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
    try {
      const r = await fetch(this._c.alarm_csv + `?_=${Date.now()}`);
      if (!r.ok) { this._alarm = []; this._render(); return; }
      const lines = (await r.text()).trim().split("\n");
      if (lines.length < 2) { this._alarm = []; this._render(); return; }
      const hdr = lines[0].split(",").map(h => h.trim());
      this._alarm = [];
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(",");
        if (cols.length < hdr.length) continue;
        const row = {};
        hdr.forEach((h, j) => row[h] = (cols[j] || "").trim());
        this._alarm.push(row);
      }
    } catch (e) { console.error("HASS Console Summary:", e); }
    this._render();
  }

  _render() {
    const dk = this._isDark();
    const isHass = this._appearance === "hass_ui";
    const unack = this._alarm.filter(r => !r.ack);
    const c01 = unack.filter(r => r.class === "01").length;
    const c02 = unack.filter(r => r.class === "02").length;
    const c03 = unack.filter(r => r.class === "03").length;

    // `default` keeps the Niagara hex palette; `hass_ui` swaps to HA CSS
    // variables so the card sits natively next to other HA cards. Severity
    // remaps to HA state colors so Critical/Major/Minor pick up the same
    // hues badges and alerts use elsewhere in the dashboard.
    const bg      = isHass ? "var(--ha-card-background, var(--card-background-color, #fff))"
                           : (dk ? "#0c1117" : "var(--ha-card-background, var(--card-background-color, #fff))");
    const gaugeBg = isHass ? "var(--secondary-background-color, #f5f5f5)"
                           : (dk ? "#141b24" : "var(--secondary-background-color, #f5f5f5)");
    const bd      = isHass ? "var(--divider-color, #e0e0e0)"
                           : (dk ? "#1e2a36" : "var(--divider-color, #e0e0e0)");
    const dim     = isHass ? "var(--secondary-text-color, #727272)"
                           : (dk ? "#4a5a6a" : "#aaa");
    const fn      = isHass ? 'var(--paper-font-body1_-_font-family, Roboto, "Noto Sans", "Helvetica Neue", Arial, sans-serif)'
                           : '"SF Mono","Cascadia Code","JetBrains Mono","Fira Code",monospace';
    const critColor  = isHass ? "var(--error-color, #db4437)"   : "#ff4757";
    const majColor   = isHass ? "var(--warning-color, #ffa726)" : "#ffa502";
    const minColor   = isHass ? "var(--info-color, #039be5)"    : "#3b82f6";

    const gauges = [
      { n: c01, color: critColor, label: "CRITICAL", glow: c01 > 0 },
      { n: c02, color: majColor,  label: "MAJOR",    glow: c02 > 0 },
      { n: c03, color: minColor,  label: "MINOR",    glow: c03 > 0 },
    ];

    // In hass_ui the pulse/glow effect is dropped so the card looks like a
    // regular HA info surface rather than a lit-up alarm panel; the number
    // and border still color-shift with state so severity stays legible.
    const S = `
:host{display:block}
*{box-sizing:border-box;margin:0;padding:0}
.card{
  background:${bg};
  border-radius:12px;
  padding:16px 12px;
  font-family:${fn};
}
.gauges{display:flex;gap:10px}
.gauge{
  flex:1;text-align:center;
  padding:18px 8px 14px;
  border-radius:10px;
  border:1px solid ${bd};
  background:${gaugeBg};
  transition:border-color .3s,box-shadow .3s;
}
${isHass ? "" : `.gauge.glow{border-color:var(--gc);box-shadow:0 0 12px var(--gc)30}`}
${isHass ? ".gauge.glow{border-color:var(--gc)}" : ""}
.gauge-num{
  font-size:36px;font-weight:${isHass ? "600" : "800"};line-height:1;
  letter-spacing:${isHass ? "-1px" : "-2px"};color:var(--gc);
  transition:text-shadow .3s;
}
${isHass ? "" : `.gauge.glow .gauge-num{text-shadow:0 0 16px var(--gc)60}`}
.gauge-lbl{
  font-size:${isHass ? "11px" : "9px"};font-weight:${isHass ? "500" : "700"};
  letter-spacing:${isHass ? ".4px" : "2px"};
  text-transform:${isHass ? "none" : "uppercase"};
  margin-top:8px;color:${dim};
}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
${isHass ? "" : `.gauge.glow.crit{animation:pulse 2s infinite}`}
`;

    // In hass_ui the CRITICAL label is title-cased for readability alongside
    // the softened typography; other severity labels keep their original casing
    // logic (all-caps in default, sentence-case in hass_ui via CSS).
    const displayLabel = (raw) => isHass
      ? raw.charAt(0) + raw.slice(1).toLowerCase()
      : raw;

    this.shadowRoot.innerHTML = `<style>${S}</style>
    <div class="card">
      <div class="gauges">
        ${gauges.map(g => `
          <div class="gauge ${g.glow ? "glow" : ""} ${g.label === "CRITICAL" && g.glow ? "crit" : ""}" style="--gc:${g.color}">
            <div class="gauge-num">${g.n}</div>
            <div class="gauge-lbl">${displayLabel(g.label)}</div>
          </div>
        `).join("")}
      </div>
    </div>`;
  }

  getCardSize() { return 2; }
  disconnectedCallback() { if (this._timer) clearInterval(this._timer); }
  static getStubConfig() {
    return { alarm_csv: "/local/hass-console/alarms.csv", refresh_interval: 30, theme: "auto", appearance: "hass_ui" };
  }
}

if (!customElements.get("hass-console-summary-card")) {
  customElements.define("hass-console-summary-card", HassConsoleSummaryCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "hass-console-summary-card",
    name: "HASS Console Summary Card",
    description: "Minimalist alarm severity gauges",
  });
}
