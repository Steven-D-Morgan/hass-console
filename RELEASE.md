# HASS Console v2.1.0

**Now configurable through the Home Assistant UI.**

HASS Console is a Niagara-inspired alarm console and data logger for Home Assistant. Define alarm thresholds and scheduled log snapshots in a single YAML file. View, sort, and filter everything from a dark-themed Lovelace card with ALARM and LOG tabs — just like a BAS operator workstation.

---

## ✨ What's New in v2.1.0

### 🔧 Web UI Configuration

HASS Console now appears under **Settings → Devices & Services**. Add the integration through the standard "+ Add Integration" flow — no editing `configuration.yaml` required.

- **Configure button** — change file paths anytime through the integration card
- **Reload button** (⋮ menu) — pick up `console.yaml` changes without restarting HA
- **Status display** — see how many points are loaded right from the integration card
- **Translations** — UI labels and error messages localized via `translations/en.json`

### 🔄 Backward Compatible

Existing YAML setups (`hass_console: !include console.yaml` in `configuration.yaml`) continue to work unchanged. The integration auto-detects which mode you're using and runs the appropriate setup path.

### 🏗️ Internal Refactor

- Constants extracted to `const.py` for cleaner code organization
- Engine now takes explicit file paths — same class powers both YAML and UI modes
- Cleaner service registration (services available in both modes)

---

## 🎯 Core Features

### Alarm Engine
Real-time threshold monitoring with duration requirements. When a sensor exceeds a limit and *stays* there for the configured time, HASS Console writes a timestamped alarm record with the value, duration, severity class, and a human-readable trigger alias.

### Log Engine
Cron-scheduled data snapshots. Record any entity's value on a schedule — daily meter reads, hourly temperature trends, weekly usage totals. Full 5-field cron syntax with support for ranges, steps, and lists.

### Lovelace Card
Sortable, filterable viewer with tabbed interface:
- **Alarm Class chips** — toggle 01 Critical (red), 02 Major (amber), 03 Minor (blue)
- **Entity chips** — filter to specific points
- **Date range picker** — manual from/to dates + presets (Today, Last 7d, Last 30d, This Month)
- **Full-text search** across all columns
- **Sortable columns** — click any header
- **Auto-refresh** on a configurable interval
- **Active filter tags** in the footer — click ✕ to remove individually

### Dual CSV Output
Alarms and logs write to separate files with purpose-built schemas:

| File | Columns |
|------|---------|
| `hass-console-alarms.csv` | timestamp, entity, class, value, duration, note, trigger |
| `hass-console-logs.csv` | timestamp, entity, value, note |

Both are served from `/config/www/` and accessible at `/local/` URLs — ready for Excel, Grafana, InfluxDB, or any CSV-compatible tool.

### Three Services
Inject entries from any automation or script:
- `hass_console.write_log` — manual log entry
- `hass_console.write_alarm` — manual alarm entry
- `hass_console.reload` — hot-reload config (works in both modes)

---

## 🚀 Quick Start (UI Mode)

**1.** Copy `custom_components/hass_console/` to your HA config
**2.** Copy `www/hass-console-card.js` to `/config/www/`
**3.** Create `/config/console.yaml` (see [simple-setup.md](simple-setup.md) for the format)
**4.** Restart Home Assistant
**5.** Go to **Settings → Devices & Services → + Add Integration → HASS Console**
**6.** Confirm the file paths and click Submit
**7.** Register the card resource → `/local/hass-console-card.js` (JavaScript Module)
**8.** Add the card to a dashboard:

```yaml
type: custom:hass-console-card
title: HASS Console
alarm_csv: /local/hass-console-alarms.csv
log_csv: /local/hass-console-logs.csv
```

---

## 📝 Example console.yaml

```yaml
# Log energy usage at midnight
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  note: "Daily kWh snapshot"

# Alarm if the network closet overheats
NETWORK_CLOSET:
  type: ALARM
  class: "01"
  entity: sensor.network_closet_temperature
  note: "Network closet overheat"
  trigger:
    - alias: "Above 78°F for 10 min"
      platform: numeric_state
      entity_id: sensor.network_closet_temperature
      above: 78
      for:
        minutes: 10
```

---

## 📦 What's Inside

```
hass-console/
├── custom_components/hass_console/
│   ├── __init__.py             # Core engine + setup logic
│   ├── config_flow.py          # UI configuration flow (new)
│   ├── const.py                # Shared constants (new)
│   ├── manifest.json           # Now declares config_flow: true
│   ├── services.yaml
│   ├── strings.json            # UI labels (new)
│   └── translations/
│       └── en.json             # English translations (new)
├── www/
│   └── hass-console-card.js    # Lovelace card
├── console.yaml                # Example config
├── simple-setup.md             # Quick-start guide
├── README.md                   # Full documentation
└── RELEASE.md
```

---

## 🔁 Upgrading from v2.0.0

No breaking changes. Just replace the `custom_components/hass_console/` folder with the new version and restart HA.

- **YAML users:** Nothing to do. Your existing `hass_console: !include console.yaml` setup continues to work.
- **Want to switch to UI mode?** Remove the `hass_console:` line from `configuration.yaml`, restart, then add the integration from Settings → Devices & Services.

---

## 📚 Documentation

- [simple-setup.md](simple-setup.md) — 5-minute setup guide with both UI and YAML modes
- [README.md](README.md) — complete reference (field schemas, alarm evaluation logic, automation examples, troubleshooting)

---

## 🧰 Requirements

- Home Assistant 2024.1+
- No external dependencies
- Manual install (HACS support coming in a future release)

---

## 📜 License

MIT
