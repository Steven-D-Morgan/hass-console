# Road Map

A living backlog for **HASS Console**. Items are tagged `impact · effort` (`high/med/low` · `small/med/large`) and grouped by priority. Checkboxes track status; move items to **Recently Shipped** as they land.

Two constraints shape everything below:
- **Directory-tree HACS install.** HACS installs the integration by copying the whole `custom_components/hass_console/` tree from the release tag — there is no single build artifact. As of 2.6.1 the Lovelace cards live inside that tree (`custom_components/hass_console/frontend/`) and are served + auto-loaded by the integration, so they ship and register themselves — no `www/` copy and no manual Resources entry.
- **Backward compatibility / no data loss.** Existing `console.yaml` configs and CSV files must keep working; the engine already auto-migrates CSV schemas, and new behaviour should be opt-in with sensible defaults.

This backlog is seeded from the project's own notes (the CHANGELOG flags SQLite as the next storage step) and an Aug 2026 review; additional ideas are marked _(suggested)_.

---

## ✅ Recently Shipped (for context)

- **v2.6.1** — cards auto-register from the integration (served + auto-loaded, versioned cache-bust); no more manual Dashboards → Resources. Minimum HA bumped to 2024.7.
- **v2.6.0** — local-time cron + OR day-rule + name aliases, real restorable `hass_console.*` entities, opt-in retention/rotation (unacknowledged alarms never pruned), acknowledge notes, Config Repairs for invalid `console.yaml`.
- **v2.5.2** — state-trigger duration fix for entities already in the alarm state; `show_alarm`/`show_log` card tabs.
- **v2.5.0** — state triggers, multi-condition AND, theme support, summary card, integration icon, HACS support files.

---

## 🎯 Next Up

- [x] **Auto-register the Lovelace cards from the integration** `high · med` — today users must copy `hass-console-card.js` + `hass-console-summary-card.js` into `/config/www/` and add two Lovelace **Resources** by hand, then bump a cache-buster on every update. Bundle the cards inside `custom_components/hass_console/` (so HACS ships them), serve them with `async_register_static_paths`, and auto-load them via `frontend.add_extra_js_url` with a `?v={manifest_version}` query — no manual Resources entry, cache busts itself on every release. _The #1 friction for new users._ **✅ Shipped in 2.6.1.**
- [x] **Single-source the version + cut a clean stable 2.6.0** `high · small` — **✅ Shipped.** manifest/card/CHANGELOG reconciled to one version and a clean stable `2.6.0` tag published, so default HACS users (beta toggle off) now receive the 2.6.0 feature set instead of being stuck on 2.5.2.
- [ ] **Release-time version guard** `med · small` — a job on `release: published` that fails if `manifest.json` version ≠ tag ≠ CHANGELOG heading ≠ card `VER`, so the four can never drift again.
- [ ] **`.gitignore` + drop committed bytecode** `med · small` — `custom_components/hass_console/__pycache__/*.pyc` (py3.14) is tracked and would otherwise ship to every user. Add a `.gitignore` and `git rm` the tracked `.pyc`.
- [ ] **Consistent tag scheme** `low · small` — tags mix unprefixed semver (`2.5.2`), non-semver (`2.6.0_BETA`), and PEP440 beta (`v2.6.0b1`). Standardize on one convention going forward.

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

_Last updated: 2026-08-11. Ratings are guidance, not gospel — revisit as the project changes._
