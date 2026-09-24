# Roadmap

A living backlog for **HASS Console**. Items are tagged `impact · effort` (`high/med/low` · `small/med/large`) and grouped by priority. Shipped work lives in [CHANGELOG.md](CHANGELOG.md); this file is forward-looking only.

Two constraints shape everything below:
- **Directory-tree HACS install.** HACS installs the integration by copying the whole `custom_components/hass_console/` tree from the release tag — there is no single build artifact. The Lovelace cards live inside that tree (`custom_components/hass_console/frontend/`) and are served + auto-registered by the integration, so they ship and load themselves — no `www/` copy and no manual Resources entry.
- **Backward compatibility / no data loss.** Existing `console.yaml` configs and CSV files must keep working; the engine already auto-migrates CSV schemas, and new behavior should be opt-in with sensible defaults.

---

## 🎯 Next Up

- [x] **Card appearance option — Default vs. HASS UI** `high · med` — **✅ Shipped in 3.2.0.** Both cards now take `appearance: default | hass_ui`; `default` is unchanged and `hass_ui` maps colors, typography, and severity onto HA CSS variables (`--ha-card-background`, `--primary-text-color`, `--divider-color`, `--primary-color`) and state colors (`--error-color` → Critical, `--warning-color` → Major, `--info-color` → Minor). Independent from the existing `theme: auto | dark | light` — the two combine, so `appearance: hass_ui, theme: auto` gets HA-native styling that also follows the user's light/dark preference. Still to wire into the visual card editor once that lands (see **Visual card editors for both cards** below).
- [ ] **Remove `console.yaml` support** `med · large` — with UI subentries + AND-conditions editor + one-click YAML import all shipped, YAML setup can be dropped in a future major (probably `4.0`). The engine's point-map input shape stays the same; the removal is deleting `_load_yaml_sync`, the CONFIG_SCHEMA branch of `async_setup`, and the YAML path field from the config/options forms.

---

## ✨ Features — engine & storage

- [ ] **SQLite storage backend for large datasets** `high · large` — the CHANGELOG already flags this as the next step beyond CSV retention. Keep CSV as the default/export format; add SQLite for high-volume logging and fast filtering/acknowledgment.
- [ ] **Template / time-pattern alarm triggers** `med · med` — the engine supports `numeric_state` and `state`; a `template` trigger (and optional time-pattern re-evaluation) would cover derived conditions the current platforms can't express.
- [ ] **Template AND conditions** `med · med` — a `template` condition type in the UI editor would subsume most "(advanced)" YAML-imported condition shapes the condition form currently can't render, and pairs naturally with template triggers.
- [ ] **Change-based LOG points** `med · med` — log on value change (with optional min-delta and min-interval) as an alternative to cron, for entities where fixed snapshots miss the action.
- [ ] **Capture unit + friendly name at write time** `med · small` — record the entity's `unit_of_measurement` and friendly name alongside the raw value so `72.5` in a CSV two years later still means something. Schema auto-migration adds the columns for free.
- [ ] **Aggregate sensors + reduce card CSV polling** `med · med` — real sensors like `sensor.hass_console_unacked_critical` / `_major` / `_minor` plus totals, usable in any card, template, or automation. Would also let the summary card stop fetch-and-parsing CSVs on an interval — counts arrive as instant state updates.
- [ ] **Fire HA events on alarm lifecycle** `med · small` — emit `hass_console_alarm` (and `_acknowledged`, later `_cleared`) events carrying the full record, so users can build arbitrary automations without polling entities or CSVs.

---

## 🚨 Alarm model (Niagara parity)

- [ ] **Return-to-normal tracking** `high · large` — record when an alarm condition *clears*, giving the full Niagara lifecycle (active-unacked, active-acked, cleared-unacked, cleared-acked) and letting the card show "still in alarm" vs "returned to normal". The engine already detects the cleared transition in `_eval_alarm()` and the 30s duration checker (it uses it to reset the timer), so this is mostly recording + card work, not a rearchitecture.
- [ ] **`ack_by` — who acknowledged** `high · small` — the acknowledge service calls carry the HA user in their context; stamp the username into an `ack_by` column (shown next to the ack timestamp/note). CSV auto-migration handles old files.
- [ ] **Notify on new alarm** `med · small` — an optional per-severity `notify` target so a Critical/Major alarm can push without wiring a separate automation. Include the alarm `id` and an ACK action in the mobile notification payload so acknowledge-from-phone works out of the box (today it needs a hand-built automation).
- [ ] **Escalation / re-notify** `med · med` — if a Critical stays unacknowledged for N minutes, notify again (or a different target). Builds on notify-on-new-alarm.
- [ ] **Alarm shelving / snooze** `med · med` — temporarily suppress a known alarm (e.g. "shelve for 8 hours during maintenance") without deleting the point. Shelved alarms shown dimmed with an expiry.
- [ ] **Hysteresis / deadband on numeric triggers** `med · small` — e.g. fire above 80 but don't re-arm until below 78, so a value hovering at the threshold doesn't produce an incident per flicker.
- [ ] **Acknowledge from the summary card** `low · med` — surface ACK / ACK-All on the at-a-glance summary card, not just the full card.
- [ ] **Nuisance-alarm analytics** `low · med` — a "top offenders" view (most frequent alarms over a period) to help users tune thresholds — a staple of real alarm-management consoles.

---

## 🃏 Cards & card editor

- [ ] **Visual card editors for both cards** `high · med` — implement `getConfigElement()` + `getStubConfig()` so every option (`rows`, `refresh_interval`, `theme`, `appearance`, `show_alarm`/`show_log`, CSV paths) is a form field in the dashboard UI with live preview, instead of raw YAML. Table stakes for HACS cards, and the natural place to surface the new `appearance` toggle.
- [ ] **Row detail / more-info popup** `high · med` — click a row to open a dialog with the full record, a link to the underlying HA entity's more-info/history, and (for alarms) ACK-with-note right in the dialog.
- [ ] **Persist filter & view state** `med · small` — remember active filters, sort, Show-ACK'd toggle, and active tab per browser (localStorage) so the console reopens the way the operator left it.
- [ ] **Download the *filtered* view** `med · small` — the download button opens the raw CSV today; exporting exactly what's on screen (filters + search applied) is what reporting actually needs.
- [ ] **Multi-select ACK** `med · small` — row checkboxes + "ACK selected", between per-row ACK and ACK-All.
- [ ] **Pagination / virtual scrolling** `med · med` — `rows` is a hard display cap today; virtualized rendering handles years of data smoothly (pairs with the SQLite backend).
- [ ] **Inline value sparkline for LOG points** `med · med` — click a LOG entity to see a mini-chart of its logged values over the selected date range; turns the log tab from a table into a trending tool.
- [ ] **Column visibility & order** `med · med` — hide/reorder columns (e.g. drop `id` and `duration` on a narrow dashboard) from the card editor and/or the ⚙ panel.
- [ ] **Responsive / mobile layout** `med · med` — a compact rendering for phone-width screens (HA companion app), e.g. stacked two-line rows instead of a wide table.
- [ ] **Custom severity classes with colors** `med · small` — non-01/02/03 classes currently get default styling / an "Other" gauge; let card config map custom class strings to labels and colors. Coordinates with the `appearance: hass_ui` severity remap.
- [ ] **Audible / visual annunciation** `med · small` — opt-in chime + tab-title flash when a new unacknowledged Critical arrives while the dashboard is open. Classic alarm-console behavior.
- [ ] **Relative timestamps option** `low · small` — "4 min ago" display toggle, absolute time on hover.
- [ ] **Group-by-category view** `low · med` — collapsible category groups in the table as an alternative to chip filtering.

---

## 🧰 Point management & polish

- [ ] **Enable / disable a point** `high · small` — pause a LOG or ALARM point without deleting it (an `enabled` flag on the subentry), for maintenance windows or seasonal points.
- [ ] **Duplicate a point** `med · small` — "duplicate" on a subentry's menu, pre-filling the add flow with an existing point's config. Users with 20 similar meters will ask for this.
- [ ] **Test / run-now for points** `med · small` — a "log now" action on LOG points and a "test fire" on ALARM points, so users can verify a new point end-to-end without waiting for cron or forcing a real threshold breach.
- [ ] **Point health attributes** `med · small` — expose `last_run` / `next_run` on LOG entities and `last_fired` / current condition status on ALARM entities, so users can see at a glance that a point is alive.
- [ ] **Repairs issue for broken entity references** `med · small` — if a point's monitored entity gets renamed or deleted, raise a fixable Repairs issue instead of silently skipping `unavailable`/`unknown` states forever.
- [ ] **Config backup / import-export** `med · small` — export all subentries to a JSON/YAML file and re-import them, for backup or cloning a setup to another HA instance (the YAML-import fix flow already built most of the machinery).
- [ ] **Diagnostics support** `low · small` — implement `async_get_config_entry_diagnostics` so users can attach a redacted config dump to bug reports.
- [ ] **Localization** `med · med` — move card UI strings into a translation table and broaden `translations/` coverage; helps HACS default-repo review too.
- [ ] **12/24-hour + date format preference** `low · small` — follow HA's locale (or a card option) for timestamp rendering.

---

## 📦 Distribution

- [ ] **Submit to the HACS default repository** `high · med` — hassfest + HACS support files are already in place; being in the default store removes the "add custom repository" step and is the biggest single adoption lever.

---

_Last updated: 2026-09-24. Ratings are guidance, not gospel — revisit as the project changes._
