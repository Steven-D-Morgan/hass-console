# Release Notes

User-facing notes for each release, newest first. For the full change-by-change history see [CHANGELOG.md](CHANGELOG.md); notes for releases before 2.6.0 are on the [GitHub Releases](https://github.com/Steven-D-Morgan/hass-console/releases) page.

---

## 3.1.0 — AND conditions in the UI, one-click YAML migration

**Release title:** `3.1.0 — AND conditions in the UI, one-click YAML migration`
**Tag:** `v3.1.0`
**Mark as pre-release:** ❌

Everything `console.yaml` supports is now reachable from the WebGUI. 3.1.0 closes the two remaining gaps from the 3.0.0 rollout:

- **AND conditions** on each ALARM trigger are now edited from the UI, with the same iterative Add / Edit / Delete pattern as the triggers list itself.
- **YAML → UI import** in one click. The deprecation Repairs issue is now a **fixable** issue — click **Fix** and every YAML-only point becomes a UI subentry in a single step.

### 🎉 What's new

- **Manage AND conditions from the ALARM flow.** Each trigger on the Triggers step gets a **Manage AND conditions** row that opens a sub-list. Add numeric (`above` / `below`) or state-match conditions; every condition must be true when the trigger fires, matching the engine's existing AND semantics.
- **One-click YAML import.** In Repairs, the "HASS Console: console.yaml is deprecated" issue now has a **Fix** button. It shows the list of YAML-only points, creates a UI subentry for each, and reloads the integration. `console.yaml` is left untouched — remove the migrated entries at your own pace.
- **Trigger edit form updated.** Its description now points at the new Manage AND conditions row instead of the previous "wait for the upcoming conditions editor" note.

### ⚠️ Breaking

None. Existing subentries and `console.yaml` configs upgrade in place.

### 📝 Upgrading from 3.0.0-rc1 (or 2.6.x)

1. Update the integration (HACS or manual copy) and restart HA.
2. Open Repairs — the deprecation issue now has a **Fix** button. Click it to migrate every remaining YAML point in one shot, or keep migrating manually via **ADD**.
3. On any existing ALARM point, use **Configure → Triggers step → Manage AND conditions** to view or edit conditions that were previously YAML-only.

Existing CSV files, entity IDs, and acknowledgment state are untouched.

### Full changelog

See [CHANGELOG.md](CHANGELOG.md#v310--2026-08-20) for the file-by-file breakdown.

---

## 3.0.0-rc1 — Points from the UI, YAML deprecated

**Release title:** `3.0.0-rc1 — Points from the UI, YAML deprecated`
**Tag:** `v3.0.0-rc1`
**Mark as pre-release:** ✅ (hides it from HACS users without "Show beta versions" enabled)

> ⚠️ **Release candidate.** Enable **Show beta versions** in HACS to receive this update. Existing 2.6.x users will not auto-update to `3.0.0-rc1`.

Every LOG and ALARM point is now a **config subentry** on the HASS Console integration entry, so you add, edit, and delete them from Settings → Devices & Services → HASS Console — the same UX as automations. Multi-trigger ALARM points are supported natively (iterative Add / Edit / Delete on the triggers step).

### 🎉 What's new

- **Add points from the UI.** Settings → Devices & Services → HASS Console → **ADD** → LOG point or ALARM point. Existing points get a **Configure** button for edits and a **⋮ → Delete** option.
- **Multi-trigger ALARM support in the UI.** The ALARM flow's Triggers step lets you add any number of triggers, edit each one, and delete individually before saving.
- **AND `conditions` are preserved on edit.** The trigger editor doesn't yet expose a conditions form, but any `conditions:` imported from `console.yaml` are round-tripped losslessly when you edit the trigger — the future conditions UI slots in on top without a data migration.
- **YAML deprecation surfaced in Repairs.** A warning-severity Repairs issue lists how many points are still defined only in `console.yaml` and clears itself once you've re-created each one through the UI.

### ⚠️ Breaking

- **Minimum Home Assistant is now 2025.3** (required for `ConfigSubentryFlow`).
- **`console.yaml` is deprecated.** It still works during the 3.x line but will be removed in a future major release. New points should be added through the UI.

### 📝 Upgrading from 2.6.x

1. Update the integration (HACS or manual copy) and restart HA.
2. Confirm the CSV paths on the HASS Console setup form (unchanged).
3. Check Repairs — it lists how many YAML-only points remain. Re-add each one through **ADD** on the integration card, then remove the YAML entry.
4. UI points always take precedence over same-named YAML points during the transition, so migration can happen at your own pace with no duplicate rows.

Existing CSV files and acknowledgment state are untouched.

### 🧪 Testing an RC

Please try adding a few LOG and ALARM points from the UI and file issues against anything that feels rough. Particular things worth exercising:

- LOG points with cron schedules (the entity selector should list the right entity).
- ALARM points with multiple triggers — add, edit, and delete triggers before saving.
- ALARM points migrated from a `console.yaml` entry that used `conditions:` — edit a trigger, save, and confirm the alarm still fires with the conditions intact.
- The Repairs issue about YAML deprecation clearing correctly after moving every point to the UI.

### Full changelog

See [CHANGELOG.md](CHANGELOG.md#v300-rc1--2026-08-20) for the file-by-file breakdown.

---

## 2.6.3 — Hassfest validation fixes

Passes Home Assistant's Hassfest validation cleanly. **No change to how the cards or the alarm/log engine behave** — 2.6.3 only fixes CI-validation errors that 2.6.2 tripped:

- Declares the `http` dependency (used to serve the bundled cards).
- Adds a `CONFIG_SCHEMA` — the engine still validates `console.yaml` itself, so YAML config is unaffected.

Requires Home Assistant 2024.7+.

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
