# HASS Console — Changelog

All notable changes to this project are documented here, newest first. Versions follow [Semantic Versioning](https://semver.org/) — MAJOR.MINOR.PATCH.

---

## v2.6.0 — 2026-07-10

### 🐛 Fixed: Cron evaluated in local time

LOG cron schedules and log-row timestamps were being evaluated against **UTC**, while
alarms used local time — so `"0 0 * * *"` fired at UTC midnight, not your local midnight.
The cron scanner now converts to the configured local timezone before matching and
timestamping, so LOG and ALARM timestamps are consistent.

### Changed

- **Standard cron day semantics.** When **both** day-of-month and day-of-week are restricted,
  a match on **either** now fires (standard Vixie-cron behaviour), instead of requiring both.
- **Cron name aliases.** Month (`jan`–`dec`) and weekday (`sun`–`sat`) names are accepted, and
  `7` is treated as Sunday — e.g. `"0 9 * * mon-fri"`, `"0 0 1 jan *"`.
- **Real entities with restore.** `hass_console.log_*` / `alarm_*` are now proper Home Assistant
  entities (unique IDs, registry entries, UI-manageable) that are created at startup and
  **restore their last value across restarts**. Entity IDs are unchanged.
- **Acknowledge notes persist.** The `note` passed to `acknowledge_alarm` / `acknowledge_all`
  is now saved to a new `ack_note` column and shown on hover over the ✓ in the card. Existing
  CSVs auto-migrate to add the column (no data loss).

### Added

- **Retention & rotation** (opt-in, off by default). New `retention_days` and `max_rows`
  options (config flow / options flow) trim old rows on a daily schedule. **Unacknowledged
  alarms are never pruned**, regardless of age. Keeping files bounded also keeps acknowledgment
  fast. A future SQLite backend is noted as the next step for very large datasets.
- **Config Repairs issue.** Invalid or incomplete `console.yaml` points (bad type, missing
  `cron`/`entity`/`trigger`, unsupported platform, numeric trigger without `above`/`below`) now
  raise a Home Assistant Repairs issue listing each problem, and clear automatically once fixed
  and reloaded.

### Changed files

- `custom_components/hass_console/__init__.py` — local-time cron, cron OR-rule + name aliases,
  entity wiring, `ack_note`, retention prune, config Repairs
- `custom_components/hass_console/entity.py` — **new** `HassConsolePointEntity` (RestoreEntity)
- `custom_components/hass_console/const.py` — `ack_note` column, retention constants, issue ID
- `custom_components/hass_console/config_flow.py` — `retention_days` / `max_rows` fields
- `custom_components/hass_console/strings.json`, `translations/en.json` — new labels + issue text
- `www/hass-console-card.js` — ack-note hover
- `manifest.json` — version 2.6.0

---

## v2.5.2 — 2026-06-05

### 🐛 Bugfix: State Trigger Duration

**Fixed:** State-based alarm triggers with `for:` durations would never fire for entities already in the target state.

- **Initial alarm evaluation** — engine now checks the current state of all alarm entities immediately at startup. If an entity is already in an alarm condition (e.g. garage door was already open when HA restarted), the duration timer starts immediately instead of waiting for a state change event.
- **Periodic duration checker** — new 30-second interval timer evaluates all active alarm timers, re-verifies conditions are still met, and fires alarms that have exceeded their `for:` duration. Fixes the case where an entity sits in the same state (like a door stuck at `open`) and generates no state change events.

### ✨ Card: Show/Hide Tabs

New `show_alarm` and `show_log` config options. Set either to `false` to hide that tab entirely:
```yaml
type: custom:hass-console-card
show_alarm: false    # log-only view
show_log: true
```
When only one tab is enabled, the tab bar is hidden and the card shows just that view. Useful for dedicated alarm-only or log-only card instances pointing at custom target CSVs.

### Changed
- `__init__.py` — added `_initial_alarm_eval()` and `_setup_alarm_duration_checker()`
- `hass-console-card.js` — `show_alarm`/`show_log` config, tab bar hidden when single tab

---

## v2.5.1 — 2026-06-05

### 🔧 HACS/Hassfest Validation Fixes

- **Brand assets** moved to correct location: `custom_components/hass_console/brand/icon.png`
- **Manifest keys** sorted alphabetically after `domain` and `name` (Hassfest requirement)
- Both GitHub Actions (HACS Validation + Hassfest) now pass cleanly

### Changed
- `manifest.json` — keys reordered: domain, name, then alphabetical
- `brand/` directory — relocated inside `custom_components/hass_console/`

---

## v2.5.0 — 2026-06-05

### ✨ State Triggers, Multi-Condition AND, Theme Support, Summary Card, Icon, HACS

**State-based triggers** — alarm points can now trigger on entity state transitions using `platform: state`. Supports `to` and `from` fields, both accepting single values or lists for OR matching. Works with `for:` duration.

**Multi-condition AND logic** — any trigger now supports an optional `conditions:` list. All conditions must be true simultaneously for the alarm to fire. Conditions support numeric (`above`/`below`) and state (`state: "value"`) checks. Mix trigger platforms with any condition type.

**Theme support** — card adapts to HA's light/dark theme via `theme: auto | dark | light` config option. Reads HA's CSS variables with dark fallbacks. Alarm severity colors stay fixed in both modes.

**Summary card** — `hass-console-summary-card.js`, a minimalist at-a-glance widget showing three severity gauges (Critical/Major/Minor) with active glow effects. Critical gauge pulses when non-zero.

**Custom icon** — integration icon shows in Settings → Devices & Services. 256×256 and 512×512.

**HACS support files** — `hacs.json`, GitHub Actions workflows. Repo is installable as a HACS custom repository.

### Added
- `__init__.py` — `PLATFORM_STATE`, `_check_state_match()`, `_check_condition()`, condition evaluation in `_eval_alarm()`
- `www/hass-console-summary-card.js`
- `hacs.json`, `.github/workflows/hacs-validate.yaml`, `.github/workflows/hassfest.yaml`
- `custom_components/hass_console/brand/` — icon assets

### Changed
- `hass-console-card.js` — theme-aware CSS, `theme` config option
- `console.yaml` — examples for state triggers, AND conditions

---

## v2.4.1 — 2026-06-05

### 📁 Dedicated CSV Folder

All CSV files now live under `/config/www/hass-console/` instead of loose in `/config/www/`:
- Default alarms: `/config/www/hass-console/alarms.csv`
- Default logs: `/config/www/hass-console/logs.csv`
- Custom targets: `/config/www/hass-console/<name>.csv`

### Changed
- `const.py` — default paths updated
- All files — path references updated throughout

---

## v2.4.0 — 2026-06-05

### 🗂️ Custom Target Files

New optional `target_csv` field routes a point's entries to a separate CSV file. Bare filenames resolve next to the default CSVs. Works for both LOG and ALARM points. Acknowledgment searches across all alarm files automatically.

### Added
- `const.py` — `CONF_TARGET_CSV`
- `__init__.py` — `_resolve_csv_path()`, per-file lock management, multi-file acknowledgment
- `services.yaml` — `target_csv` field on write_log and write_alarm

---

## v2.3.0 — 2026-06-05

### ✅ Alarm Acknowledgment

Niagara-style alarm acknowledgment workflow:
- Default view shows only unacknowledged alarms
- Per-alarm ACK button, ACK All button, Show/Hide ACK'd toggle
- Unique 8-character hex ID per alarm row
- `ack` column: empty = unacknowledged, timestamp = when acknowledged
- Unacknowledged count badge (red) on Alarm tab
- Acknowledged rows dimmed with green ✓

### Added
- `__init__.py` — `_gen_id()`, `acknowledge_alarm()`, `acknowledge_all()`, CSV read-modify-write
- `services.yaml` — `acknowledge_alarm` and `acknowledge_all` services
- `const.py` — `id` and `ack` added to `ALARM_COLUMNS`

---

## v2.2.0 — 2026-06-05

### 🏷️ Category Column + Clean Timestamps

**Category** — new optional `category` field on every point (HVAC, GPS, E-METER, etc.). Filterable in the card with multi-select chips. Teal badge display.

**Timestamps** — changed from ISO 8601 to `YYYY-MM-DD HH:MM:SS`. Excel auto-recognizes this format.

**Automatic CSV migration** — engine detects old CSV schemas on startup and rewrites files with new columns, preserving all existing data.

### Added
- `const.py` — `CONF_CATEGORY`, `TIMESTAMP_FORMAT`
- Both CSVs — `category` column

### Changed
- `__init__.py` — category parsing, `strftime()` timestamps, `_migrate_or_create()` schema evolution
- `hass-console-card.js` — category column, category filter chips, dual timestamp format handling
- `services.yaml` — `category` field on write_log and write_alarm

---

## v2.1.1 — 2026-06-05

### 🐛 Config Flow 500 Error Fix

Fixed `Config flow could not be loaded: 500 Internal Server Error` on HA 2024.11+.

### Changed
- `config_flow.py` — removed deprecated `FlowResult` import, removed `OptionsFlow.__init__` override

---

## v2.1.0 — 2026-06-05

### 🔧 Web UI Configuration

HASS Console now appears under Settings → Devices & Services with a Configure button and Reload option.

### Added
- `config_flow.py` — config flow + options flow
- `const.py` — shared constants extracted from `__init__.py`
- `strings.json` + `translations/en.json`

### Changed
- `manifest.json` — `config_flow: true`, `integration_type: "service"`
- `__init__.py` — `async_setup_entry()`, `async_unload_entry()`, dual-mode setup (YAML + config entry)

---

## v2.0.0 — 2026-06-05

### 🗂️ Dual CSV Output + Comprehensive Documentation

Split from single CSV to two purpose-built files:
- `alarms.csv` — timestamp, entity, class, value, duration, note, trigger
- `logs.csv` — timestamp, entity, value, note

### Added
- Separate write locks per CSV file
- `simple-setup.md` — 5-minute setup guide
- `RELEASE.md` — GitHub release description

### Changed
- `__init__.py` — separate alarm/log write methods and locks
- `hass-console-card.js` — `alarm_csv` and `log_csv` config options, tab-aware download
- `README.md` — complete rewrite

---

## v1.1.0 — 2026-06-05

### ⚙️ Filter Panel

### Added
- Collapsible filter panel (⚙ Filters button)
- Alarm class chips (01 Critical / 02 Major / 03 Minor)
- Entity chips (multi-select)
- Date range picker + presets (Today, Last 7d, Last 30d, This Month)
- Active filter tags in footer
- Filter count badge
- Clear All Filters button

---

## v1.0.0 — 2026-06-05

### 🎉 Initial Release

Niagara-inspired alarm console and data logger for Home Assistant.

### Added
- Core engine — cron-scheduled LOG points, `numeric_state` ALARM triggers with duration requirements, CSV writer with async locking
- Cron parser — full 5-field cron syntax with ranges, steps, and lists
- Lovelace card — ALARM/LOG tabs, sortable columns, text search, auto-refresh, severity badges, formatted timestamps
- Three services — `write_log`, `write_alarm`, `reload`
- YAML configuration via `console.yaml`
- `manifest.json`, `services.yaml`, `README.md`, example `console.yaml`
