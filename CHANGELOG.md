# HASS Console — Changelog

All notable changes to this project are documented here, newest first. Versions follow [Semantic Versioning](https://semver.org/) — MAJOR.MINOR.PATCH.

Scan the table for an at-a-glance history, or jump to any version for the full details below.

| Version | Date | Summary |
|---------|------|---------|
| [v3.4.0](#v340--2026-11-07) | 2026-11-07 | Seamless first-run setup — the add-integration form submits with zero edits on a fresh install (the Console YAML field no longer pre-fills a path that doesn't exist), and the default `alarms.csv` / `logs.csv` are created with headers the moment the entry is added. |
| [v3.3.2](#v332--2026-11-03) | 2026-11-03 | Card hardening follow-up — `ack_note` tooltip and `data-id` on the ACK button now escape attribute values via `_escAttr` instead of `_esc`. Bundled card version bumped to match the integration. |
| [v3.3.1](#v331--2026-11-03) | 2026-11-03 | 3.3.0 follow-ups — custom `target_csv` points no longer break setup, data view no longer blocks the event loop, card can view custom files via `/api/hass_console/file/<name>`, docs match the new paths |
| [v3.3.0](#v330--2026-11-02) | 2026-11-02 | Security hardening — authenticated CSV endpoint, path-traversal fix, admin-only services, Lovelace card XSS fix |
| [v3.2.1](#v321--2026-09-24) | 2026-09-24 | `appearance: hass_ui` is now the default; opt back into the Niagara look with `appearance: default` |
| [v3.2.0](#v320--2026-09-24) | 2026-09-24 | Card `appearance: hass_ui` — native Home Assistant look for both cards |
| [v3.1.0](#v310--2026-08-25) | 2026-08-25 | AND-conditions editor in the UI; one-click YAML import via Repairs |
| [v3.0.0](#v300--2026-08-21) | 2026-08-21 | Promotion of `v3.0.0-rc1` to stable — no code changes |
| [v3.0.0-rc1](#v300-rc1--2026-08-20) | 2026-08-20 | Points managed as UI subentries; YAML deprecated; HA 2025.3+ |
| [v2.6.3](#v263--2026-08-11) | 2026-08-11 | Hassfest validation fixes (http dependency, CONFIG_SCHEMA) |
| [v2.6.2](#v262--2026-08-11) | 2026-08-11 | Fix card auto-registration (register as a Lovelace resource) |
| [v2.6.1](#v261--2026-08-11) | 2026-08-11 | Cards auto-register — no more manual Dashboards → Resources |
| [v2.6.0](#v260--2026-07-10) | 2026-07-10 | Local-time cron, real restorable entities, retention/rotation, acknowledge notes, Config Repairs |
| [v2.5.2](#v252--2026-06-05) | 2026-06-05 | State-trigger duration fix; show/hide card tabs |
| [v2.5.1](#v251--2026-06-05) | 2026-06-05 | HACS/Hassfest validation fixes |
| [v2.5.0](#v250--2026-06-05) | 2026-06-05 | State triggers, AND conditions, theme, summary card, icon, HACS |
| [v2.4.1](#v241--2026-06-05) | 2026-06-05 | Dedicated `/config/www/hass-console/` CSV folder |
| [v2.4.0](#v240--2026-06-05) | 2026-06-05 | Custom target CSV files per point |
| [v2.3.0](#v230--2026-06-05) | 2026-06-05 | Niagara-style alarm acknowledgment |
| [v2.2.0](#v220--2026-06-05) | 2026-06-05 | Category column, clean timestamps, CSV auto-migration |
| [v2.1.1](#v211--2026-06-05) | 2026-06-05 | Config-flow 500 fix (HA 2024.11+) |
| [v2.1.0](#v210--2026-06-05) | 2026-06-05 | Web UI configuration (config + options flow) |
| [v2.0.0](#v200--2026-06-05) | 2026-06-05 | Dual CSV output + documentation rewrite |
| [v1.1.0](#v110--2026-06-05) | 2026-06-05 | Collapsible filter panel |
| [v1.0.0](#v100--2026-06-05) | 2026-06-05 | Initial release |

---

## v3.4.0 — 2026-11-07

### 🚀 Seamless first-run setup

A brand-new install could not finish the add-integration form without manual edits: the **Console YAML path** field defaulted to `/config/console.yaml`, and since that legacy file doesn't exist on a fresh install, clicking **Submit** returned "Console YAML file not found". Until the field was blanked by hand, the config entry — and therefore the default CSV files — were never created.

- **The Console YAML field now defaults to blank on a fresh install.** It pre-fills `/config/console.yaml` only when that file actually exists (upgraders from 2.x keep the old convenience). A new user clicks **Submit** on the untouched form and setup completes.
- **Default `alarms.csv` and `logs.csv` are created the moment the entry is added.** Previously, an entry set up while Home Assistant was still starting deferred all file creation to the `EVENT_HOMEASSISTANT_STARTED` listener; a new `async_ensure_files` on the engine now writes the data directory and both header-row CSVs immediately in that case too, so the files exist as soon as the integration appears — before the first point, cron fire, or alarm.
- **`simple-setup.md` caught up with the 3.3.0 paths.** Step 4 still showed the pre-3.3.0 `/config/www/hass-console/` defaults and Step 6 still configured the card with unauthenticated `/local/` URLs; the guide now shows the real defaults (`alarms.csv` / `logs.csv` in `/config/hass_console/`) and the minimal card config that uses the authenticated `/api/hass_console/{alarm,log}` endpoints the card already defaults to.

### 🔖 Card versions

- `VER` / `SVER` bumped to `3.4.0` in lockstep with the integration.

## v3.3.2 — 2026-11-03

### 🛡️ Card hardening follow-up

Advisory from `@frenck` on the hass/default#13009 approval review — the ack-cell renderer in `frontend/hass-console-card.js` was piping the acknowledgment tooltip and ACK button `data-id` through `_esc`, which escapes `<`, `>` and `&` but not quotes. `_escAttr` is already defined for exactly this case (and used for the filter chips and footer tags), so the ack cell should use it too.

- **`title="${ack_note}"`** on the acknowledged-cell `<span class="ack-done">` now goes through `_escAttr` instead of `_esc`.
- **`data-id="${r.id}"`** on the ACK `<button>` now goes through `_escAttr` instead of `_esc`.

Not a bug on current installs — `ack_note` is admin-written (`acknowledge_alarm` / `acknowledge_all` are admin-only since 3.3.0) and `r.id` is a locally generated 8-char hex string, so no user-controlled quote has ever reached either attribute. Shipping it so the invariant is enforced by the renderer rather than by where the data happens to come from.

### 🔖 Card versions bumped to match

- `VER` in `hass-console-card.js` and `SVER` in `hass-console-summary-card.js` bumped from `3.3.0` to `3.3.2`. The 3.3.1 release raised the integration version but not the bundled card constants; this release puts them back in lockstep.

Internal: no new helpers; this release only reuses the `_escAttr` added in 3.3.0.

## v3.3.1 — 2026-11-03

### 🧰 3.3.0 follow-ups

Three loose ends from the HACS submission review (hacs/default#13009 round 2) by `@frenck`. All affect existing 3.x installs that carried a non-default `target_csv` value or that opened the HASS Console card frequently.

- **Custom `target_csv` points no longer break setup.** 3.3.0's path validation raised `ServiceValidationError` from `_resolve_csv_path`, which is also called from `_parse_points` at engine startup. Any LOG or ALARM point whose `target_csv` held a nested path (e.g. `subfolder/meters.csv`) or an absolute path — both documented as valid in 3.2.1 — made the config entry fail to set up. `_parse_points` now calls a new `_resolve_point_csv_path` that falls back to the default log/alarm file and records a config problem (which surfaces in the Repairs issue your other invalid points use), so the engine starts and the operator sees exactly which point needs editing. The subentry forms (LOG and ALARM, user + reconfigure) now reject path separators and `..` at submit time with an `invalid_target_csv` form error, so UI points can no longer land in a half-configured state.
- **The authenticated data view no longer stats on the event loop.** `HassConsoleDataView.get` called `path.exists()` directly in the async handler, which every open card hit on each 30-second refresh. Both the alarm/log view and a new file view now check existence through `hass.async_add_executor_job(path.exists)`.
- **Custom target files are viewable in the card again.** 3.3.0 served only the two default files through `/api/hass_console/{alarm,log}`, so anyone using `target_csv` lost the "point a card at my meter CSV" workflow. New `HassConsoleFileView` at `/api/hass_console/file/<name>` serves any CSV that an active LOG/ALARM point or `write_alarm` call has registered as a target. The route only accepts bare filenames (no `/`, `\`, or `..`) and only serves files currently in `_log_files` or `_alarm_files`, so unregistered or arbitrary filenames return 404.
- **README and `services.yaml` match the 3.3.0 semantics.** The custom-target table and example card YAML, the "Viewing custom files in the card" section, the architecture diagram's `logs.csv` / `alarms.csv` paths, the card and summary-card configuration tables, the "CSV Output" section, the services tables, and the troubleshooting notes now describe the data directory, the authenticated endpoints, and the "bare filename only" rule. `services.yaml` descriptions for `target_csv` match.
- **i18n:** the new `invalid_target_csv` form error added to `strings.json` and `translations/en.json` under both the LOG and ALARM subentry error blocks; the 12 non-English translations will pick it up on the next backfill (missing entries render the key, which falls back to the English string anyway).

Internal: new `HassConsoleEngine._resolve_point_csv_path(name, target, default_path)` wraps `_resolve_csv_path` with a per-point try/except; a `_target_csv_invalid(value)` helper in `config_flow.py` reuses the same `/ \ ..` rejection; `HassConsoleFileView` registered next to `HassConsoleDataView` in `_register_data_view`.

## v3.3.0 — 2026-11-02

### 🔒 Security hardening

Three issues flagged in the HACS submission review (hacs/default#13009) by `@frenck`. All three affect existing 3.x installs — upgrading is strongly recommended.

- **CSV data is no longer served without authentication.** Pre-3.3.0 defaults put the alarm and log CSVs under `/config/www/hass-console/`, which Home Assistant serves at `/local/` with no auth check — anyone who could reach the HA instance could download the full alarm and log history, including whatever entity values are logged there (vehicle location, utility readings, anything). 3.3.0 moves the default location to the integration's own data directory (`/config/hass_console/`) and serves it through a new authenticated endpoint at `/api/hass_console/alarm` and `/api/hass_console/log`. New installs are safe by default. Existing installs with paths set under `/config/www/` get a Repairs issue pointing at the exact files and how to relocate them; see the README's "Relocating CSVs off `/local/`" section for the one-time cleanup.
- **Path traversal in `write_log` / `write_alarm` services closed.** Pre-3.3.0 these services accepted an arbitrary `target_csv` value, which `_resolve_csv_path` used as-is for absolute paths and joined without checking for relative ones — a non-admin user could call `write_alarm` with `target_csv: ../configuration.yaml` and the alarm handler would append CSV rows to `configuration.yaml`, then `acknowledge_all` would rewrite it as an alarm CSV. 3.3.0 restricts `target_csv` to bare filenames (no `/`, `\`, or `..`), resolved against the integration data directory; anything else raises a `ServiceValidationError`. Automations that previously supplied absolute or nested paths need updating to use a bare filename or omit the parameter.
- **Services registered as admin.** `write_log`, `write_alarm`, `acknowledge_alarm`, `acknowledge_all` and `reload` are now admin-only. Non-admin users calling them get an unauthorized response.
- **Lovelace card XSS fixed.** The card previously injected the configured title, filter chips (`class`, `category`, `entity` values), and footer tags into `innerHTML` without escaping. CSV values come from service data that any user with write access can set, so a crafted entity or category string could run script in every dashboard that opened the card. All interpolations into DOM are now escaped (text through `_esc`, attribute values through a new `_escAttr` helper that quotes `"`, `&`, `<`, `>`).

Internal: new `HassConsoleDataView` HTTP view, `HassConsoleEngine._data_dir` resolved from `hass.config.path("hass_console")`, Repairs issue `legacy_www_path` for existing `/config/www/` configurations, bundled Lovelace card bumped to 3.3.0.

## v3.2.1 — 2026-09-24

### 🎨 `hass_ui` is now the default card appearance

v3.2.0 shipped the HA-native look as an opt-in. In practice it's the right default for almost every dashboard — cards should read as first-class HA surfaces, not stand out from the rest of the UI — so this release flips the default. The Niagara-inspired look is still one line of YAML away for anyone who prefers it.

- **`appearance` now defaults to `hass_ui`** on both `hass-console-card` and `hass-console-summary-card`. Any card without an explicit `appearance:` key picks up the HA-native styling.
- **Opt back into the original look** with `appearance: default` in the card YAML. Nothing was removed; the Niagara palette, pulsing glow, and monospace headers still render exactly as before.
- **Stub configs updated** — the visual card editor's starter YAML for both cards now emits `appearance: hass_ui`.

### Impact

Existing dashboards that already set `appearance: hass_ui` or `appearance: default` explicitly are unaffected. Cards that omit the key will render in `hass_ui` on refresh — a visual change, not a behavioral one. No data migration.

### Files changed

- `custom_components/hass_console/frontend/hass-console-card.js` — default and coercion flipped; stub config updated; `VER` bumped.
- `custom_components/hass_console/frontend/hass-console-summary-card.js` — same treatment; `SVER` bumped.
- `custom_components/hass_console/manifest.json` — version `3.2.1`.
- `README.md` — configuration tables and example YAML updated to reflect the new default; the long "Using HASS Console in Automations" and "Real-World Examples" sections trimmed down to pointers into the new Cookbook (~160 fewer lines).
- `COOKBOOK.md` — filled in with the five automation recipes and two full point sets that used to live in the README, plus a table of contents and per-recipe *why* notes.

---

## v3.2.0 — 2026-09-24

### 🎨 Native Home Assistant look for both cards

Both `hass-console-card` and `hass-console-summary-card` gain a new `appearance` option that lets them render in the same visual language as the rest of the HA dashboard. Existing cards keep the Niagara-inspired look unchanged — the new mode is opt-in.

### ➕ Added

- **`appearance: default | hass_ui`** on both cards (defaults to `default`, so nothing changes without opting in).
  - `default` — the Niagara-inspired styling, exactly as `v3.1.0` rendered it.
  - `hass_ui` — restyles colors, typography, and severity mapping to match Home Assistant's own cards:
    - **Colors** flow from HA's CSS variables (`--ha-card-background`, `--primary-text-color`, `--secondary-text-color`, `--divider-color`, `--primary-color`) instead of the hard-coded Niagara palette.
    - **Severity** remaps to HA state colors — `--error-color` → Critical, `--warning-color` → Major, `--info-color` → Minor, `--success-color` → cleared/ACK'd — so the same hues used by HA badges and alerts show up on chips, gauges, and severity classes.
    - **Typography** switches to HA's Roboto/Noto sans-serif stack, with normal case and reduced letter-spacing on headers, tabs, and column labels (the monospace + uppercase treatment stays in `default`).
    - **Summary card gauges** drop the pulsing glow in `hass_ui`, keeping just a state-colored number, border, and label — closer to how HA info surfaces present counts.
- Independent of the existing `theme: auto | dark | light` option, which still controls dark/light mode following. The two combine — `appearance: hass_ui, theme: auto` gets HA-native styling that also tracks the user's dark/light preference.

### 📝 Notes

Existing configurations upgrade in place. No engine changes; no data migration. Nothing to reconfigure — anyone who wants the new look adds `appearance: hass_ui` to the card YAML (or picks it up in the visual card editor once that ships).

### Changed files

- `custom_components/hass_console/frontend/hass-console-card.js` — new `appearance` config key; palette helper + CSS-variable refactor so colors are single-sourced; `data-app="hass_ui"` structural overrides for the softer typography; `VER` bumped.
- `custom_components/hass_console/frontend/hass-console-summary-card.js` — same treatment for the severity gauges; glow/pulse gated on `default`; `SVER` bumped.
- `custom_components/hass_console/manifest.json` — version `3.2.0`.
- `CHANGELOG.md`, `README.md`, `ROADMAP.md` — documentation updated for the new option; roadmap item marked shipped.

---

## v3.1.0 — 2026-08-25

### 🎉 Richer point management from the UI

Everything `console.yaml` supports is now reachable from the WebGUI. Two additions:

1. **AND conditions on each trigger** are now edited from the UI, with the same iterative Add / Edit / Delete flow as the triggers list itself.
2. **YAML → UI import** in one click. The `console.yaml` deprecation Repairs issue is now **fixable** — click **Fix** and every YAML-only point becomes a UI subentry.

### ➕ Added

- **AND-conditions editor.** On the Triggers step of an ALARM point, each trigger now shows a **Manage AND conditions** row. Add, edit, and delete conditions the same way triggers work; both numeric (`above` / `below`) and state-match conditions are supported, matching what the engine already evaluates.
- **YAML import via Repairs.** The `yaml_deprecated` issue is fixable in 3.1.0 — clicking **Fix** shows the list of YAML-only points, creates one subentry per point, and reloads the integration so they're active immediately. `console.yaml` is left untouched; delete the migrated entries at your own pace.

### ⚙️ Changed

- **`yaml_deprecated` Repairs issue** — now `is_fixable=True` with `data={"entry_id": ...}`, driving the new `ImportYamlPointsFlow` in `repairs.py`. The Repairs card advertises the Fix button and embeds the outstanding-point count in the title (the top-level `description` is gone — Home Assistant's translation schema declares it mutually exclusive with `fix_flow` under `vol.Exclusive('fixable')`, so the informative copy lives under `fix_flow.step.confirm.description`).
- **Trigger edit step description** — replaces the "wait for the upcoming conditions editor" note with a pointer to the new Manage AND conditions row.

### 📝 Notes

Existing subentries and `console.yaml` configs upgrade in place — no data migration is required. Conditions imported from YAML in 3.0.0-rc1 (round-tripped but not editable) become fully editable in 3.1.0 without touching the on-disk shape.

### Changed files

- `custom_components/hass_console/config_flow.py` — condition list/form steps on `AlarmPointSubentryFlow`; deep-copy conditions on reconfigure so bail-outs don't mutate the subentry.
- `custom_components/hass_console/repairs.py` — **new file.** `async_create_fix_flow` + `ImportYamlPointsFlow`.
- `custom_components/hass_console/__init__.py` — `_report_yaml_deprecated` sets `is_fixable=True` and passes `entry_id` via `data`.
- `custom_components/hass_console/strings.json` + `translations/en.json` — new `conditions` / `add_condition` / `edit_condition` steps; new `state_needs_value` error; new `fix_flow` block on `yaml_deprecated` (no top-level `description`, so Hassfest's `vol.Exclusive('fixable')` rule is satisfied).
- `custom_components/hass_console/manifest.json` — version `3.1.0`.
- `custom_components/hass_console/frontend/hass-console-card.js` — `VER` bumped.
- `custom_components/hass_console/frontend/hass-console-summary-card.js` — `SVER` bumped.
- `CHANGELOG.md`, `RELEASE_NOTES.md`, `ROAD_MAP.md`, `simple-setup.md` — documentation updated for the conditions editor and one-click YAML import.

---

## v3.0.0 — 2026-08-21

Promotion of [`v3.0.0-rc1`](#v300-rc1--2026-08-20) to stable. **No code changes** between `v3.0.0-rc1` and `v3.0.0` — the RC feedback window closed with no new fixes required, so the identical build was re-tagged as the stable `3.0.0` release. See the [`v3.0.0-rc1`](#v300-rc1--2026-08-20) entry below for the full breakdown of what landed in the 3.0.0 line.

---

## v3.0.0-rc1 — 2026-08-20

### 🎉 Points managed from the UI

Every LOG and ALARM point is now a **config subentry** on the HASS Console integration entry — add, edit, and delete points from Settings → Devices & Services → HASS Console, the same UX as automations or helpers. `console.yaml` still works but is **deprecated** and will be removed in a future major release.

### ➕ Added

- **`LogPointSubentryFlow`** — one-form subentry flow for LOG points (name, cron, entity, category, note, target CSV).
- **`AlarmPointSubentryFlow`** — multi-step subentry flow for ALARM points:
  1. Header form (name, class, category, primary entity, note, target CSV).
  2. Triggers step with iterative **Add / Edit / Delete** per trigger.
  3. Trigger form with platform (numeric threshold or state match), entity, above/below or to/from, `for:` duration (hours/minutes/seconds), and alias.
- **AND `conditions` are preserved on edit** — the trigger editor does not yet expose a conditions form, but any conditions imported from `console.yaml` are round-tripped losslessly on trigger edits so the future conditions UI slots in on top without a data migration.
- **YAML deprecation Repairs issue** — a warning-severity issue lists how many points are still defined only in `console.yaml`, steering users to the UI. Auto-clears once every YAML point has a matching subentry.

### ⚙️ Changed

- **Minimum Home Assistant is now 2025.3** — required for `ConfigSubentryFlow`.
- **`console.yaml` path is now optional** on the config / options form. Leave it blank if all points are UI-managed.
- **Engine reads points from subentries and YAML together** — YAML points are loaded first, then UI subentries `.update()` on top so a same-named subentry always wins. Editing or deleting a subentry reloads the engine automatically.
- **Point-platform constants moved to `const.py`** (`PLATFORM_NUMERIC`, `PLATFORM_STATE`, `SUPPORTED_PLATFORMS`) so the config flow can validate triggers without importing from the engine module.
- **Version guard workflow** widened to accept PEP440/semver pre-release suffixes on CHANGELOG headings.

### 🗓️ Deprecated

- **`console.yaml`.** Still parsed and merged with UI subentries for compatibility, but slated for removal in a future major release. Users are encouraged to re-create each point through the UI (**ADD** button on the integration card) and then remove them from `console.yaml`.
- **`configuration.yaml: hass_console: !include console.yaml`** setup mode is still recognised on YAML-mode installs but is on the same deprecation timeline.

### ⬆️ Upgrading from 2.6.x

1. Update the integration (HACS or manual copy) and restart HA.
2. Confirm the CSV paths on the HASS Console setup form (they are unchanged).
3. Check the Repairs card — it will list how many YAML-only points remain. Add each one through **Settings → Devices & Services → HASS Console → ADD**; the equivalent YAML entry can then be deleted from `console.yaml`.
4. Same-named UI points always take precedence over YAML during the transition, so you can migrate at your own pace without duplicate rows.

Existing CSV files and acknowledgment state are untouched.

### Changed files

- `custom_components/hass_console/const.py` — subentry types, deprecation issue key, platform constants moved from `__init__.py`.
- `custom_components/hass_console/config_flow.py` — new `LogPointSubentryFlow` and `AlarmPointSubentryFlow`; YAML path made optional.
- `custom_components/hass_console/__init__.py` — merge subentries with YAML in `async_setup_entry`; raise the `yaml_deprecated` Repairs issue.
- `custom_components/hass_console/strings.json` + `translations/en.json` — subentry flow labels and error strings, deprecation issue text.
- `custom_components/hass_console/manifest.json` — version `3.0.0-rc1`.
- `custom_components/hass_console/frontend/hass-console-card.js` — `VER` bumped.
- `custom_components/hass_console/frontend/hass-console-summary-card.js` — `SVER` bumped.
- `hacs.json` — `homeassistant: "2025.3.0"`.
- `.github/workflows/version-guard.yaml` — CHANGELOG regex now accepts pre-release suffixes.
- `README.md`, `simple-setup.md`, `ROAD_MAP.md`, `RELEASE_NOTES.md` — documentation updated for the UI-first workflow and YAML deprecation.

---

## v2.6.3 — 2026-08-11

### 🔧 Hassfest validation fixes

No functional change to the cards or the alarm/log engine — 2.6.3 only clears CI-validation
errors that 2.6.2 tripped:

- Declare the `http` dependency (the integration imports `StaticPathConfig` from it to serve
  the cards) and reach Lovelace via `after_dependencies` — fixes the Hassfest `[DEPENDENCIES]`
  error.
- Add a permissive `CONFIG_SCHEMA` (`{DOMAIN: dict}`, extra allowed). The engine still
  validates `console.yaml` itself, so YAML-mode behaviour is unchanged; this only satisfies
  Hassfest's `[CONFIG_SCHEMA]` requirement for integrations that implement `async_setup`.

### Changed files

- `custom_components/hass_console/manifest.json` — `http` dependency, `after_dependencies: lovelace`
- `custom_components/hass_console/__init__.py` — `CONFIG_SCHEMA`

---

## v2.6.2 — 2026-08-11

### 🐛 Fixed: cards now actually auto-register

2.6.1 tried to auto-load the cards via the frontend `extra_module_url`, but that defines
the card too early — before Home Assistant's scoped element registry is in place — so the
dashboard couldn't find the element ("Custom element not found") and the cards wouldn't
render or appear selectable in the picker. 2.6.2 registers the cards as **Lovelace
resources** instead, which is the mechanism the dashboard actually waits for, so they load
reliably.

### Changed

- The integration now registers `/hass_console_frontend/…` as Lovelace resources
  (type: module), **idempotently** and only on **storage-mode** dashboards. Existing
  resources are loaded first, so nothing else in your Resources list is touched
  ([core#165767](https://github.com/home-assistant/core/issues/165767)).
- If you added the resources by hand as a 2.6.1 workaround, they're detected and **not
  duplicated**.
- **YAML-mode Lovelace:** an integration can't add resources there, so a log message lists
  the two URLs to add manually.
- Removed the `add_extra_js_url` auto-load that didn't work.

### Changed files

- `custom_components/hass_console/__init__.py` — register cards as Lovelace resources
  (load-before-write to avoid wiping resources, idempotent, storage-mode only)

---

## v2.6.1 — 2026-08-11

### ✨ Cards auto-register — no more Dashboards → Resources

The integration now serves and auto-loads both Lovelace cards itself. You no longer
copy card files to `/config/www/` or register resources by hand — install or update the
integration and the cards appear. The auto-loaded URL is versioned, so it cache-busts
automatically on update (no more hard-refresh).

### Changed

- **Cards moved into the integration** at `custom_components/hass_console/frontend/`,
  served at `/hass_console_frontend/…` and auto-loaded via the frontend `extra_module_url`
  list (`async_register_static_paths` + `add_extra_js_url`).
- **Minimum Home Assistant is now 2024.7** — required for `async_register_static_paths`
  (the old `register_static_path` was removed in HA 2025.7).
- Card custom-element registration is now **guarded** (`customElements.get(...)` check) so the
  bundled card won't redefine an element that's already registered (and updates from 2.6.1 on are
  double-load safe).

### Upgrade note

If you previously added the HASS Console cards under **Settings → Dashboards → Resources**,
remove those two entries after updating — the integration loads the cards automatically now.
If you leave them, the old (pre-2.6.1) card file is unguarded, so it can log an "already defined"
error in the browser console and may keep serving a stale cached copy — your dashboard keeps
working either way.

### Changed files

- `custom_components/hass_console/__init__.py` — serve + auto-load cards on setup
- `custom_components/hass_console/frontend/` — **new** home for both cards (moved from `www/`)
- `custom_components/hass_console/manifest.json` — `frontend` dependency, version 2.6.1
- `hacs.json` — minimum Home Assistant 2024.7.0

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
