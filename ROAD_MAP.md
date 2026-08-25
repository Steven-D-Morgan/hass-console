# Road Map

A living backlog for **HASS Console**. Items are tagged `impact · effort` (`high/med/low` · `small/med/large`) and grouped by priority. Checkboxes track status; move items to **Recently Shipped** as they land.

Two constraints shape everything below:
- **Directory-tree HACS install.** HACS installs the integration by copying the whole `custom_components/hass_console/` tree from the release tag — there is no single build artifact. As of 2.6.1 the Lovelace cards live inside that tree (`custom_components/hass_console/frontend/`) and are served + auto-loaded by the integration, so they ship and register themselves — no `www/` copy and no manual Resources entry.
- **Backward compatibility / no data loss.** Existing `console.yaml` configs and CSV files must keep working; the engine already auto-migrates CSV schemas, and new behaviour should be opt-in with sensible defaults.

This backlog is seeded from the project's own notes (the CHANGELOG flags SQLite as the next storage step) and an Aug 2026 review; additional ideas are marked _(suggested)_.

---


## 🎯 Next Up

- [x] **UI editor for AND `conditions`** `high · med` — **✅ Shipped in 3.1.0.** Iterative Add/Edit/Delete under each trigger; numeric and state-match conditions. No engine change (the engine already evaluated them).
- [x] **One-click YAML → subentries import** `high · med` — **✅ Shipped in 3.1.0.** The `yaml_deprecated` Repairs issue is now fixable; one click creates a subentry per YAML-only point and reloads. `console.yaml` is left untouched.
- [ ] **Remove `console.yaml` support** `med · large` — with import + conditions editor in place, YAML setup can be dropped in a future major (probably `4.0`). The engine's point-map input shape stays the same; the removal is deleting `_load_yaml_sync`, the CONFIG_SCHEMA branch of `async_setup`, and the YAML path field from the config/options forms.
- [x] **Auto-register the Lovelace cards from the integration** `high · med` — **✅ Shipped in 2.6.1, fixed in 2.6.2.**
- [x] **Single-source the version + cut a clean stable 2.6.0** `high · small` — **✅ Shipped.**
- [x] **Release-time version guard** `med · small` — **✅ Shipped** as `.github/workflows/version-guard.yaml`. Updated in 3.0.0-rc1 to accept PEP440/semver pre-release suffixes on CHANGELOG headings.
- [x] **Consistent tag scheme** `low · small` — **✅ Standardized in 3.0.0-rc1** on `vX.Y.Z` for releases and `vX.Y.Z-rcN` / `vX.Y.Z-bN` for pre-releases.
- [x] **`.gitignore` + drop committed bytecode** `med · small` — **✅ Done.** `.gitignore` covers `__pycache__/` and `*.py[cod]`; no `.pyc` files are tracked.

---


## ✨ Features

- [ ] **SQLite storage backend for large datasets** `high · large` — the CHANGELOG already flags this as the next step beyond CSV retention. Keep CSV as the default/export format; add SQLite for high-volume logging and fast filtering/acknowledgment.
- [ ] **Template / time-pattern alarm triggers** `med · med` _(suggested)_ — the engine supports `numeric_state` and `state`; a `template` trigger (and optional time-pattern re-evaluation) would cover derived conditions the current platforms can't express.
- [ ] **Notify on new alarm** `med · small` _(suggested)_ — an optional per-severity `notify` target so a Critical/Major alarm can push without wiring a separate automation.
- [ ] **Acknowledge from the summary card** `low · med` _(suggested)_ — surface ACK / ACK-All on the at-a-glance summary card, not just the full card.

---
