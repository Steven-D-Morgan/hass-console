# HASS Console

A Niagara-inspired alarm console and data logger for Home Assistant. Define alarm thresholds and scheduled log snapshots in YAML, acknowledge alarms from the dashboard, and filter everything from a Lovelace card with ALARM and LOG tabs.

If you've used a Niagara AX/N4 alarm console, you know the value of a single pane of glass that shows every alarm and every logged data point across your facility. HASS Console brings that pattern to Home Assistant — threshold-based alarm evaluation with duration requirements, alarm acknowledgment, cron-scheduled data snapshots, severity classification, system categorization, and a sortable/filterable viewer — all driven by one YAML file.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Console.yaml Reference](#consoleyaml-reference)
  - [LOG Points](#log-points--scheduled-data-snapshots)
  - [ALARM Points](#alarm-points--threshold-based-alerts)
- [Alarm Acknowledgment](#alarm-acknowledgment)
- [CSV Output](#csv-output)
- [Lovelace Card](#lovelace-card)
- [Services](#services)
- [Using HASS Console in Automations](#using-hass-console-in-automations)
- [Entity Naming Convention](#entity-naming-convention)
- [Cron Reference](#cron-reference)
- [Real-World Examples](#real-world-examples)
- [Troubleshooting](#troubleshooting)
- [Author & License](#author--license)

---

## Architecture Overview

HASS Console is a custom integration (domain: `hass_console`) with three parts:

```
┌──────────────────────────────────────────────────────────────┐
│  Settings → Devices & Services → HASS Console                │
│    or  configuration.yaml:  hass_console: !include console.yaml
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  HASS Console Engine  (custom_components/hass_console/)      │
│                                                              │
│  ┌─────────────────┐     ┌──────────────────────┐           │
│  │  Cron Scanner    │     │  Alarm Evaluator     │           │
│  │  (every 1 min)   │     │  (state listeners)   │           │
│  │                  │     │                      │           │
│  │  Reads entity →  │     │  Checks threshold →  │           │
│  │  writes LOG row  │     │  tracks duration →   │           │
│  │                  │     │  writes ALARM row    │           │
│  └───────┬──────────┘     └──────────┬───────────┘           │
│          │                           │                       │
│          ▼                           ▼                       │
│  hass-console-logs.csv       hass-console-alarms.csv         │
│  /config/www/                /config/www/                    │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  HASS Console Card  (www/hass-console-card.js)               │
│                                                              │
│  Fetches both CSVs → tabbed view with filters                │
│  Acknowledge alarms → calls HA service → updates CSV         │
│  Auto-refreshes on configurable interval                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Installation

See [simple-setup.md](simple-setup.md) for the 5-minute walkthrough. The short version:

1. Copy `custom_components/hass_console/` → `/config/custom_components/hass_console/`
2. Copy `www/hass-console-card.js` → `/config/www/hass-console-card.js`
3. Create `/config/console.yaml` with your alarm and log points
4. Restart Home Assistant
5. **Settings → Devices & Services → + Add Integration → HASS Console**
6. Register the card resource → `/local/hass-console-card.js` (JavaScript Module)
7. Add the card to a dashboard

Existing users with `hass_console: !include console.yaml` in `configuration.yaml` can continue using YAML setup — both modes are supported.

---

## Quick Start

Minimum viable `console.yaml`:

```yaml
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  category: E-METER
  note: "Daily kWh snapshot at midnight"

SERVER_ROOM_TEMP:
  type: ALARM
  class: "01"
  category: HVAC
  entity: sensor.server_room_temperature
  note: "Server room overheat"
  trigger:
    - alias: "Above 80°F for 5 min"
      platform: numeric_state
      entity_id: sensor.server_room_temperature
      above: 80
      for:
        minutes: 5
```

After restarting HA, you'll have:
- Entity `hass_console.log_daily_kwh` — updates at midnight with the meter's value
- Entity `hass_console.alarm_server_room_temp` — goes to "ALARM" when triggered
- A row in `hass-console-logs.csv` every midnight
- A row in `hass-console-alarms.csv` each time the temperature stays above 80°F for 5+ minutes, starting as unacknowledged

Add the Lovelace card and test immediately with:
```yaml
service: hass_console.write_log
data:
  entity: hass_console.log_test
  category: TEST
  value: "Hello World"
  note: "Testing the console"
```

---

## Console.yaml Reference

Every top-level key defines a **point** — a named data source to watch. The key name becomes part of the entity ID. Each point must have a `type` of either `LOG` or `ALARM`.

---

### LOG Points — Scheduled Data Snapshots

LOG points read an entity's current state on a cron schedule and write it to `hass-console-logs.csv`.

#### Schema

```yaml
POINT_NAME:
  type: LOG                        # Required
  cron: "0 0 * * *"               # Required — 5-field cron expression
  entity: sensor.some_entity       # Required — entity to read
  category: E-METER                # Optional — system type grouping
  note: "Description"              # Optional — static text for the Note column
```

#### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Must be `LOG` |
| `cron` | Yes | 5-field cron expression (when to snapshot). Always wrap in quotes. |
| `entity` | Yes | The HA entity whose `.state` gets logged. |
| `category` | No | System type grouping — HVAC, E-METER, GPS, W-METER, UPS, or any string. Shows as a filterable badge in the card. Defaults to empty. |
| `note` | No | Static text written to the Note column every time this point logs. Defaults to empty. |

#### How it works

The engine runs a cron scanner every 60 seconds. When the current time matches a LOG point's cron expression, it reads the entity's `.state` and appends a row to the log CSV. Each match produces exactly one row.

#### LOG examples

```yaml
# Daily energy reading at midnight
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  category: E-METER
  note: "Daily kWh snapshot"

# Hourly temperature trend
HOURLY_TEMP:
  type: LOG
  cron: "0 * * * *"
  entity: sensor.outdoor_temperature
  category: HVAC
  note: "Hourly outdoor temp"

# Every 5 minutes — power monitoring
POWER_5MIN:
  type: LOG
  cron: "*/5 * * * *"
  entity: sensor.main_panel_watts
  category: E-METER
  note: "5-min power snapshot"

# Weekly water meter (Monday 8am)
WEEKLY_WATER:
  type: LOG
  cron: "0 8 * * 1"
  entity: sensor.water_meter_gallons
  category: W-METER
  note: "Weekly water usage"

# Vehicle location every 15 minutes
CAR_GPS:
  type: LOG
  cron: "*/15 * * * *"
  entity: device_tracker.my_car
  category: GPS
  note: "Vehicle location"
```

---

### ALARM Points — Threshold-Based Alerts

ALARM points watch entity states in real time and fire when a numeric condition is met for a sustained duration. New alarms start as **unacknowledged** and remain visible until an operator acknowledges them.

#### Schema

```yaml
POINT_NAME:
  type: ALARM                             # Required
  class: "01"                             # Optional — severity (01/02/03)
  category: HVAC                          # Optional — system type grouping
  entity: sensor.some_entity              # Optional — primary entity
  note: "Description"                     # Optional — static Note column text
  trigger:                                # Required — list of triggers
    - alias: "Human-readable description" # Optional — shows in Trigger column
      platform: numeric_state             # Required — only numeric_state supported
      entity_id: sensor.some_entity       # Required — entity to monitor
      above: 78                           # Optional — fire when state > value
      below: 20                           # Optional — fire when state < value
      for:                                # Optional — sustained duration
        hours: 0
        minutes: 10
        seconds: 0
```

#### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Must be `ALARM` |
| `class` | No | Severity classification. Card color-codes `01` (red/critical), `02` (amber/major), `03` (blue/minor). Any other string gets default styling. |
| `category` | No | System type grouping (HVAC, E-METER, etc.). |
| `entity` | No | The primary entity associated with this alarm. Informational — the actual monitored entity is in the trigger's `entity_id`. |
| `note` | No | Static text written to the Note column when this alarm fires. |
| `trigger` | Yes | List of trigger definitions. Each trigger independently monitors an entity. |

#### Trigger fields

| Field | Required | Description |
|-------|----------|-------------|
| `alias` | No | Human-friendly name shown in the Trigger column. Make it descriptive. |
| `platform` | Yes | Only `numeric_state` is supported. |
| `entity_id` | Yes | The entity to monitor for state changes. |
| `above` | No | Fire when state is strictly greater than this value. |
| `below` | No | Fire when state is strictly less than this value. At least one of `above`/`below` required. |
| `for` | No | How long the condition must hold before firing. Prevents nuisance alarms from transient spikes. Omit for immediate firing. |

#### How alarm evaluation works

1. The engine subscribes to `state_changed` events on the trigger's `entity_id`.
2. On each state change, it checks the numeric condition (above/below).
3. If the condition is met and wasn't before, it starts a timer.
4. If the condition holds for the `for` duration, it writes an ALARM row (unacknowledged) and marks it recorded.
5. If the condition clears, the timer resets — ready for the next incident.

**One alarm per incident.** A sustained 2-hour overheat produces one row, not continuous repeats. When the value drops back below threshold and exceeds it again, that's a new incident.

#### ALARM examples

```yaml
# Critical — server room overheat
RACK_OVERHEAT:
  type: ALARM
  class: "01"
  category: HVAC
  entity: sensor.rack_inlet_temperature
  note: "Rack inlet overheating"
  trigger:
    - alias: "Above 85°F for 5 min"
      platform: numeric_state
      entity_id: sensor.rack_inlet_temperature
      above: 85
      for:
        minutes: 5

# Major — freezer failure
GARAGE_FREEZER:
  type: ALARM
  class: "02"
  category: HVAC
  entity: sensor.garage_freezer_temperature
  note: "Garage freezer temp rising"
  trigger:
    - alias: "Above 10°F for 30 min"
      platform: numeric_state
      entity_id: sensor.garage_freezer_temperature
      above: 10
      for:
        minutes: 30

# Minor — UPS low battery
UPS_LOW:
  type: ALARM
  class: "03"
  category: UPS
  entity: sensor.ups_battery_level
  note: "UPS battery low"
  trigger:
    - alias: "Below 20% for 5 min"
      platform: numeric_state
      entity_id: sensor.ups_battery_level
      below: 20
      for:
        minutes: 5

# Immediate — power spike (no duration)
POWER_SPIKE:
  type: ALARM
  class: "01"
  category: E-METER
  entity: sensor.main_panel_watts
  note: "Power spike"
  trigger:
    - alias: "Above 10kW (immediate)"
      platform: numeric_state
      entity_id: sensor.main_panel_watts
      above: 10000

# Multiple triggers on one alarm
HUMIDITY_BAND:
  type: ALARM
  class: "02"
  category: HVAC
  entity: sensor.server_room_humidity
  note: "Humidity out of range"
  trigger:
    - alias: "Above 60% RH for 15 min"
      platform: numeric_state
      entity_id: sensor.server_room_humidity
      above: 60
      for:
        minutes: 15
    - alias: "Below 30% RH for 15 min"
      platform: numeric_state
      entity_id: sensor.server_room_humidity
      below: 30
      for:
        minutes: 15
```

---

## Alarm Acknowledgment

HASS Console follows the Niagara alarm acknowledgment model: alarms arrive as unacknowledged and stay visible until an operator acknowledges them.

### How it works

```
Alarm fires → written to CSV with ack="" (unacknowledged)
    ↓
Appears in the Alarm tab (default view = unacknowledged only)
    ↓
Operator clicks ACK → service updates CSV → row disappears from default view
    ↓
Toggle "Show ACK'd" → acknowledged rows visible (dimmed, green ✓ with timestamp)
```

### Card controls

| Control | Location | Behavior |
|---------|----------|----------|
| **ACK button** | Per alarm row | Acknowledges that single alarm |
| **ACK All (N)** | Toolbar | Acknowledges all unacknowledged alarms in one click |
| **Show ACK'd / Hide ACK'd** | Toolbar toggle | Shows or hides acknowledged alarms |
| **Unack count badge** | Alarm tab label | Red badge showing the number of unacknowledged alarms |
| **Row counter** | Footer | Shows `"12 rows (8 ack'd hidden)"` when filtering |

### From automations

```yaml
# Acknowledge a specific alarm by its ID
service: hass_console.acknowledge_alarm
data:
  id: "a1b2c3d4"

# Acknowledge all open alarms
service: hass_console.acknowledge_all
```

### In the CSV

The `ack` column is empty for unacknowledged alarms and contains the acknowledgment timestamp (`YYYY-MM-DD HH:MM:SS`) for acknowledged ones. The `id` column is a unique 8-character hex string generated per alarm.

---

## CSV Output

Two separate CSV files in `/config/www/`, accessible at `/local/` URLs:

### hass-console-alarms.csv

```
id, timestamp, category, entity, class, value, duration, note, trigger, ack
```

| Column | Description |
|--------|-------------|
| id | Unique 8-char hex ID for this alarm |
| timestamp | `YYYY-MM-DD HH:MM:SS` when the alarm fired |
| category | System type (HVAC, E-METER, etc.) |
| entity | HASS Console entity ID |
| class | Severity class (01, 02, 03, etc.) |
| value | Entity state when the alarm fired |
| duration | How long the condition held before firing |
| note | Static note from config |
| trigger | Alias of the trigger that fired |
| ack | Empty = unacknowledged, timestamp = when acknowledged |

### hass-console-logs.csv

```
timestamp, category, entity, value, note
```

| Column | Description |
|--------|-------------|
| timestamp | `YYYY-MM-DD HH:MM:SS` when the snapshot was taken |
| category | System type |
| entity | HASS Console entity ID |
| value | Entity state at time of log |
| note | Static note from config |

### Automatic migration

On every startup, the engine checks existing CSV headers against the current schema. If columns are missing (e.g., upgrading from an older version), it rewrites the file with the new columns, filling existing rows with empty values and generating IDs where needed. No data loss.

---

## Lovelace Card

### Configuration

```yaml
type: custom:hass-console-card
title: HASS Console
alarm_csv: /local/hass-console-alarms.csv
log_csv: /local/hass-console-logs.csv
rows: 200
refresh_interval: 30
```

| Key | Default | Description |
|-----|---------|-------------|
| `title` | HASS Console | Card header text |
| `alarm_csv` | `/local/hass-console-alarms.csv` | URL to alarm CSV |
| `log_csv` | `/local/hass-console-logs.csv` | URL to log CSV |
| `rows` | 200 | Max rows to display per tab |
| `refresh_interval` | 30 | Seconds between auto-refresh |

### Features

**Tabs** — ALARM and LOG tabs. The alarm tab badge shows the unacknowledged alarm count in red.

**Alarm acknowledgment** — ACK button per row, ACK All in toolbar, Show/Hide ACK'd toggle. Default view hides acknowledged alarms.

**Collapsible filter panel** (⚙ Filters):
- **Alarm Class** — chip toggles for 01 Critical (red), 02 Major (amber), 03 Minor (blue). Alarm tab only.
- **Category** — chip toggles for each distinct category (HVAC, E-METER, GPS, etc.).
- **Entity** — chip toggles for each distinct entity.
- **Date Range** — from/to date pickers plus presets: Today, Last 7d, Last 30d, This Month.
- **Clear All Filters** — one click reset.

**Text search** — matches all columns simultaneously.

**Sortable columns** — click any header. Active sort shows ▲/▼.

**Active filter tags** — removable tags in the footer.

**CSV download** — opens the raw CSV for the active tab.

**Auto-refresh** — configurable interval, shows "Refreshed" timestamp.

All filters stack — class + category + entity + date range + text search.

---

## Services

### hass_console.write_log

Manually inject a LOG entry.

```yaml
service: hass_console.write_log
data:
  entity: "hass_console.log_custom"
  category: "HVAC"
  value: "72.5"
  note: "Manual reading"
```

| Field | Required | Description |
|-------|----------|-------------|
| entity | Yes | Entity name (freeform string) |
| category | No | System type |
| value | No | Value to record |
| note | No | Description |

### hass_console.write_alarm

Manually inject an ALARM entry (starts as unacknowledged).

```yaml
service: hass_console.write_alarm
data:
  entity: "hass_console.alarm_manual"
  category: "HVAC"
  class: "02"
  value: "OPEN"
  note: "Garage door left open"
  trigger: "Manual observation"
```

| Field | Required | Description |
|-------|----------|-------------|
| entity | Yes | Entity name |
| category | No | System type |
| class | No | Severity class |
| value | No | Value/state |
| duration | No | Duration string |
| note | No | Description |
| trigger | No | What caused the alarm |

### hass_console.acknowledge_alarm

Acknowledge a single alarm by its ID.

```yaml
service: hass_console.acknowledge_alarm
data:
  id: "a1b2c3d4"
```

| Field | Required | Description |
|-------|----------|-------------|
| id | Yes | The alarm's unique ID (from the CSV `id` column) |
| note | No | Optional acknowledgment note |

### hass_console.acknowledge_all

Acknowledge all unacknowledged alarms at once.

```yaml
service: hass_console.acknowledge_all
```

| Field | Required | Description |
|-------|----------|-------------|
| note | No | Optional acknowledgment note |

### hass_console.reload

Reload the engine — re-reads `console.yaml` and restarts all listeners. No HA restart needed.

```yaml
service: hass_console.reload
```

---

## Using HASS Console in Automations

### Log a door open event as an alarm

```yaml
automation:
  - alias: "Console — Garage door alarm"
    trigger:
      - platform: state
        entity_id: binary_sensor.garage_door
        to: "on"
    action:
      - service: hass_console.write_alarm
        data:
          entity: hass_console.alarm_garage_door
          category: SECURITY
          class: "02"
          value: "OPEN"
          note: "Garage door opened"
          trigger: "binary_sensor.garage_door → on"
```

### Log daily HVAC runtime

```yaml
automation:
  - alias: "Console — HVAC runtime at midnight"
    trigger:
      - platform: time
        at: "23:59:00"
    action:
      - service: hass_console.write_log
        data:
          entity: hass_console.log_hvac_runtime
          category: HVAC
          value: "{{ states('sensor.hvac_total_runtime_today') }}"
          note: "End-of-day HVAC runtime"
```

### Auto-acknowledge alarms at shift change

```yaml
automation:
  - alias: "Console — Auto-ACK at 7am"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: hass_console.acknowledge_all
```

### Acknowledge a specific alarm from a notification action

```yaml
automation:
  - alias: "Console — ACK from phone notification"
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
        event_data:
          action: ACK_ALARM
    action:
      - service: hass_console.acknowledge_alarm
        data:
          id: "{{ trigger.event.data.alarm_id }}"
```

### Log internet speed test results

```yaml
automation:
  - alias: "Console — Speed test log"
    trigger:
      - platform: state
        entity_id: sensor.speedtest_download
    action:
      - service: hass_console.write_log
        data:
          entity: hass_console.log_speedtest
          category: NETWORK
          value: "{{ states('sensor.speedtest_download') }} down / {{ states('sensor.speedtest_upload') }} up"
          note: "Speed test result"
```

---

## Entity Naming Convention

```
hass_console.<type>_<point_name_in_lowercase>
```

| YAML Key | Type | Entity ID |
|----------|------|-----------|
| `DAILY_KWH` | LOG | `hass_console.log_daily_kwh` |
| `TEMPERATURE_ALARM` | ALARM | `hass_console.alarm_temperature_alarm` |
| `WEEKLY_WATER` | LOG | `hass_console.log_weekly_water` |
| `UPS_LOW` | ALARM | `hass_console.alarm_ups_low` |

These are real HA entities — usable in automations, Lovelace cards, history graphs, etc.

---

## Cron Reference

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

| Syntax | Meaning |
|--------|---------|
| `*` | Every value |
| `5` | Specific value |
| `1,15` | Multiple values |
| `1-5` | Range |
| `*/10` | Every Nth value |

| Expression | Schedule |
|------------|----------|
| `"0 0 * * *"` | Daily at midnight |
| `"0 * * * *"` | Every hour |
| `"*/5 * * * *"` | Every 5 minutes |
| `"*/15 * * * *"` | Every 15 minutes |
| `"0 8 * * 1"` | Monday at 8 AM |
| `"0 0 1 * *"` | 1st of month at midnight |
| `"0 6,18 * * *"` | 6 AM and 6 PM |
| `"0 0 * * 1-5"` | Weekdays at midnight |
| `"0 */4 * * *"` | Every 4 hours |

Always wrap cron expressions in quotes in YAML.

---

## Real-World Examples

### Home energy monitoring

```yaml
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.grid_consumption_kwh
  category: E-METER
  note: "Daily grid consumption"

DAILY_SOLAR:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.solar_production_kwh
  category: E-METER
  note: "Daily solar production"

HOURLY_DEMAND:
  type: LOG
  cron: "0 * * * *"
  entity: sensor.main_panel_watts
  category: E-METER
  note: "Hourly demand reading"

HIGH_DEMAND:
  type: ALARM
  class: "01"
  category: E-METER
  entity: sensor.main_panel_watts
  note: "Excessive power draw"
  trigger:
    - alias: "Above 8kW for 5 min"
      platform: numeric_state
      entity_id: sensor.main_panel_watts
      above: 8000
      for:
        minutes: 5

BATTERY_LOW:
  type: ALARM
  class: "03"
  category: E-METER
  entity: sensor.powerwall_battery_level
  note: "Home battery low"
  trigger:
    - alias: "Below 15% for 10 min"
      platform: numeric_state
      entity_id: sensor.powerwall_battery_level
      below: 15
      for:
        minutes: 10
```

### Server room monitoring

```yaml
TEMP_15MIN:
  type: LOG
  cron: "*/15 * * * *"
  entity: sensor.rack_inlet_temperature
  category: HVAC
  note: "Rack inlet temp"

OVERHEAT:
  type: ALARM
  class: "01"
  category: HVAC
  entity: sensor.rack_inlet_temperature
  note: "Rack inlet overheating"
  trigger:
    - alias: "Above 85°F for 5 min"
      platform: numeric_state
      entity_id: sensor.rack_inlet_temperature
      above: 85
      for:
        minutes: 5

UPS_CRITICAL:
  type: ALARM
  class: "01"
  category: UPS
  entity: sensor.ups_battery_percent
  note: "UPS battery critical"
  trigger:
    - alias: "Below 10% for 2 min"
      platform: numeric_state
      entity_id: sensor.ups_battery_percent
      below: 10
      for:
        minutes: 2
```

---

## Troubleshooting

**No CSV files created** — The engine creates CSVs on first startup. Check that `/config/www/` exists. Look at the HA log for `hass_console` entries.

**Cron not firing** — Wrap cron expressions in quotes in YAML. The scanner runs every 60 seconds so there can be up to a 60-second delay. Enable debug logging:
```yaml
logger:
  logs:
    custom_components.hass_console: debug
```

**Alarm not triggering** — Verify the entity reports a numeric state (check Developer Tools → States). `unavailable` and `unknown` states are skipped. Make sure `entity_id` inside the trigger matches the real entity.

**Card shows "No entries yet"** — Click ↻ Refresh. Verify the CSV URLs in the card config. Open the URL directly in a browser to check the file.

**Card not loading** — Verify the resource is registered (Settings → Dashboards → Resources) with type "JavaScript Module". Hard refresh (Ctrl+Shift+R).

**Config flow 500 error** — Restart HA after copying the integration files. The config flow requires a full restart to register.

**ACK button not working** — The card calls `hass_console.acknowledge_alarm` via the HA service API. Verify the service is registered in Developer Tools → Services.

**Reloading after config changes** — Use the ⋮ → Reload menu on the integration card, or call `hass_console.reload` from Developer Tools → Services.

---

## Author & License

Created and maintained by [Steven D. Morgan](https://github.com/Steven-D-Morgan).

MIT License — see [LICENSE](LICENSE) for details.
