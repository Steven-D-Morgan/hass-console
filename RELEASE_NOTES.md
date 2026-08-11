# Release Notes

User-facing notes for each release, newest first. For the full change-by-change history see [CHANGELOG.md](CHANGELOG.md); notes for releases before 2.6.0 are on the [GitHub Releases](https://github.com/Steven-D-Morgan/hass-console/releases) page.

---

## 2.6.2 — Fix: cards now actually auto-register

2.6.1's auto-load didn't work — the cards showed a "Custom element not found" error and wouldn't render, because the loading mechanism defined them too early for the dashboard to see. 2.6.2 registers the cards as **Lovelace resources** (the mechanism the dashboard waits for), so they load reliably with no manual setup.

### 🐛 Fixed
- Cards now auto-register and render (previously failed with "Custom element not found").

### 📝 Notes
- Auto-registration works on standard **storage-mode** dashboards. In YAML-mode Lovelace, add the two resources manually (`/hass_console_frontend/hass-console-card.js` and `…summary-card.js`, type: JavaScript Module) — the HA log lists them.
- **If you added those resources by hand on 2.6.1**, 2.6.2 detects them and won't create duplicates.
- Requires Home Assistant 2024.7+.

---

## 2.6.1 — Cards install themselves (no more Dashboards → Resources)

The integration now ships the Lovelace cards inside itself and loads them for you. Fresh installs *and* updates no longer need the "copy the card to `/config/www/` and add it under Settings → Dashboards → Resources" steps — the cards just appear, and they cache-bust automatically on every update.

### ⚙️ Changed
- Both cards moved into the integration and are served + auto-loaded by it.
- **Minimum Home Assistant is now 2024.7.**

### ⚠️ Upgrade note — remove old card resources
If you added the HASS Console cards under **Settings → Dashboards → Resources** in a previous version, delete those two entries after updating. The integration loads the cards automatically now; a leftover resource pointing at the old (pre-2.6.1, unguarded) card can log an "already defined" error in the browser console and keep serving an older cached copy — the dashboard still works, but it's cleaner to remove it. You can also delete the old `/config/www/hass-console-card.js` and `hass-console-summary-card.js` files.

### 📝 Notes
No config or entity changes — existing dashboards keep working.

---

## 2.6.0 — Local-time cron, real entities, retention & acknowledge notes

A feature and correctness release. Existing `console.yaml` configs and CSV files keep working — CSVs auto-migrate on first start, so this is a drop-in upgrade.

### 🐛 Fixed
- **Cron ran in UTC, not your local time.** LOG cron schedules and log-row timestamps were evaluated against UTC while alarms used local time, so `"0 0 * * *"` fired at UTC midnight instead of your local midnight. The scanner now converts to Home Assistant's configured timezone before matching and timestamping, so LOG and ALARM rows stay consistent.

### ⚙️ Changed
- **Standard cron day-of-month/day-of-week semantics.** When *both* the day-of-month and day-of-week fields are restricted, a match on *either* now fires (standard Vixie-cron behavior) instead of requiring both.
- **Cron name aliases.** Month (`jan`–`dec`) and weekday (`sun`–`sat`) names are now accepted, and `7` means Sunday — e.g. `"0 9 * * mon-fri"`, `"0 0 1 jan *"`.
- **LOG/ALARM points are now real, restorable entities.** `hass_console.log_*` and `alarm_*` are proper Home Assistant entities (unique IDs, registry entries, UI-manageable) created at startup, and they **restore their last value across restarts**. Entity IDs are unchanged.
- **Acknowledge notes are saved.** The `note` you pass to `acknowledge_alarm` / `acknowledge_all` is stored in a new `ack_note` column and shown on hover over the ✓ in the card.

### ➕ Added
- **Retention & rotation (opt-in, off by default).** New `retention_days` and `max_rows` options (config/options flow) trim old rows on a daily schedule to keep files bounded and acknowledgment fast. **Unacknowledged alarms are never pruned, regardless of age.**
- **Config Repairs.** An invalid or incomplete `console.yaml` point (bad type, missing `cron`/`entity`/`trigger`, unsupported platform, numeric trigger without `above`/`below`) now raises a Home Assistant **Repairs** issue that lists each problem and clears itself once you fix it and reload.

### 📝 Notes
Existing `alarms.csv` / `logs.csv` files **auto-migrate** to add the new `ack_note` column on first start — no data is lost. No changes to entity IDs or the card layout.
