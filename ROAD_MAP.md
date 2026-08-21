# Road Map

A living backlog for **HASS Console**. Items are tagged `impact · effort` (`high/med/low` · `small/med/large`) and grouped by priority. Checkboxes track status; move items to **Recently Shipped** as they land.

Two constraints shape everything below:
- **Directory-tree HACS install.** HACS installs the integration by copying the whole `custom_components/hass_console/` tree from the release tag — there is no single build artifact. As of 2.6.1 the Lovelace cards live inside that tree (`custom_components/hass_console/frontend/`) and are served + auto-loaded by the integration, so they ship and register themselves — no `www/` copy and no manual Resources entry.
- **Backward compatibility / no data loss.** Existing `console.yaml` configs and CSV files must keep working; the engine already auto-migrates CSV schemas, and new behaviour should be opt-in with sensible defaults.

This backlog is seeded from the project's own notes (the CHANGELOG flags SQLite as the next storage step) and an Aug 2026 review; additional ideas are marked _(suggested)_.

---

## ✅ Recently Shipped (for context)

- **v3.1.0** — **AND `conditions` are now edited from the UI**, with the same iterative Add / Edit / Delete flow as the triggers list. The `console.yaml` deprecation Repairs issue is now **fixable** — one click imports every YAML-only point as a UI subentry (leaves `console.yaml` untouched so you can delete migrated entries at your own pace). No engine changes; no data migration.
- **v3.0.0-rc1** — points (LOG and ALARM) are now managed as **config subentries** on the integration — add/edit/delete from Settings → Devices & Services → HASS Console, same UX as automations. Multi-trigger ALARM flow (iterative add/edit/delete). `console.yaml` deprecated with a Repairs issue steering users to the UI. Minimum HA bumped to 2025.3 (needed for `ConfigSubentryFlow`). Standardized on `X.Y.Z-rcN` pre-release tags.
- **v2.6.3** — Hassfest validation fixes (`http` dependency, permissive `CONFIG_SCHEMA`).
- **v2.6.2** — fix card auto-registration: register the cards as Lovelace resources (the 2.6.1 `extra_module_url` approach loaded too early for the dashboard to see).
- **v2.6.1** — bundle the cards inside the integration and serve them; minimum HA bumped to 2024.7. (Auto-registration didn't work reliably until 2.6.2.)
- **v2.6.0** — local-time cron + OR day-rule + name aliases, real restorable `hass_console.*` entities, opt-in retention/rotation (unacknowledged alarms never pruned), acknowledge notes, Config Repairs for invalid `console.yaml`.
- **v2.5.2** — state-trigger duration fix for entities already in the alarm state; `show_alarm`/`show_log` card tabs.
- **v2.5.0** — state triggers, multi-condition AND, theme support, summary card, integration icon, HACS support files.

---

## 🎯 Next Up

- [x] **UI editor for AND `conditions`** `high · med` — **✅ Shipped in 3.1.0.** Iterative Add/Edit/Delete under each trigger; numeric and state-match conditions. No engine change (the engine already evaluated them).
- [x] **One-click YAML → subentries import** `high · med` — **✅ Shipped in 3.1.0.** The `yaml_deprecated` Repairs issue is now fixable; one click creates a subentry per YAML-only point and reloads. `console.yaml` is left untouched.
- [ ] **Remove `console.yaml` support** `med · large` — with import + conditions editor in place, YAML setup can be dropped in a future major (probably `4.0`). The engine's point-map input shape stays the same; the removal is deleting `_load_yaml_sync`, the CONFIG_SCHEMA branch of `async_setup`, and the YAML path field from the config/options forms.
- [x] **Auto-register the Lovelace cards from the integration** `high · med` — **✅ Shipped in 2.6.1, fixed in 2.6.2.**
- [x] **Single-source the version + cut a clean stable 2.6.0** `high · small` — **✅ Shipped.**
- [x] **Release-time version guard** `med · small` — **✅ Shipped** as `.github/workflows/version-guard.yaml`. Updated in 3.0.0-rc1 to accept PEP440/semver pre-release suffixes on CHANGELOG headings.
- [x] **Consistent tag scheme** `low · small` — **✅ Standardized in 3.0.0-rc1** on `vX.Y.Z` for releases and `vX.Y.Z-rcN` / `vX.Y.Z-bN` for pre-releases.
- [ ] **`.gitignore` + drop committed bytecode** `med · small` — `custom_components/hass_console/__pycache__/*.pyc` (py3.14) is tracked and would otherwise ship to every user. Add a `.gitignore` and `git rm` the tracked `.pyc`.

---

## 📦 Distribution & Downloads

- [x] **Total + latest download badges** `low · small` — _done._ shields.io `downloads/…/total` and `…/latest/total` in the README.
- [x] **Release workflow attaches `hass_console.zip`** `low · small` — _done._ `.github/workflows/release.yml` runs on `release: published`, zips the integration, and uploads it as a release asset so the badges have a countable asset.
- [ ] **`zip_release` migration (optional, deliberate)** `med · med` — switching `hacs.json` to `zip_release: true` + `filename: hass_console.zip` makes HACS install *from* the zip asset, so the download counters reflect **real installs** instead of just manual downloads. Breaking: every installable release must then carry the asset, and the zip's internal layout must match what HACS expects — verify against HACS docs and ship as its own deliberate release.

---

## ✨ Features

- [ ] **SQLite storage backend for large datasets** `high · large` — the CHANGELOG already flags this as the next step beyond CSV retention. Keep CSV as the default/export format; add SQLite for high-volume logging and fast filtering/acknowledgment.
- [ ] **Template / time-pattern alarm triggers** `med · med` _(suggested)_ — the engine supports `numeric_state` and `state`; a `template` trigger (and optional time-pattern re-evaluation) would cover derived conditions the current platforms can't express.
- [ ] **Notify on new alarm** `med · small` _(suggested)_ — an optional per-severity `notify` target so a Critical/Major alarm can push without wiring a separate automation.
- [ ] **Acknowledge from the summary card** `low · med` _(suggested)_ — surface ACK / ACK-All on the at-a-glance summary card, not just the full card.

---

## 🧪 Testing & Quality

- [ ] **Unit tests for the pure logic** `high · med` — add `pytest-homeassistant-custom-component` and cover the cron parser (ranges/steps/lists, name aliases, local-time matching, OR day-rule), condition/AND evaluation, retention pruning (unacked never pruned), and CSV schema migration. None of these need a running HA instance.
- [ ] **Keep HACS + Hassfest green** `low · small` — the two existing validation workflows are the Python-native equivalent of a build gate; keep them passing on every PR.
- [ ] **Ruff/Black lint + format gate** `med · small` _(suggested)_ — a single Python lint/format check on PRs.

---

## 📚 Docs

- [x] **Trim manual card-install steps** `med · small` — **✅ Shipped in 2.6.1.** README + simple-setup.md no longer tell users to copy the card to `www` or add a Resource; they document the auto-load flow and the upgrade cleanup.
- [ ] **Example `console.yaml` library** `low · small` _(suggested)_ — a few small, focused annotated configs (just LOG points, just ALARMs, custom target CSVs) alongside the full reference.

---

_Last updated: 2026-08-20. Ratings are guidance, not gospel — revisit as the project changes._
