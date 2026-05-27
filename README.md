# HASS Console

A Niagara-inspired alarm console and data logger for Home Assistant. Define alarm thresholds and scheduled log snapshots in YAML, view and filter everything from a Lovelace dashboard card.

If you've used a Niagara AX/N4 alarm console, you know the value of a single pane of glass that shows every alarm and every logged data point across your facility. HASS Console brings that pattern to Home Assistant — threshold-based alarm evaluation with duration requirements, cron-scheduled data snapshots, severity classification, and a sortable/filterable viewer — all driven by one YAML file.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Console.yaml Reference](#consoleyaml-reference)
  - [LOG Points — Scheduled Data Snapshots](#log-points--scheduled-data-snapshots)
  - [ALARM Points — Threshold-Based Alerts](#alarm-points--threshold-based-alerts)
- [CSV Output](#csv-output)
- [Lovelace Card](#lovelace-card)
- [Services](#services)
- [Using HASS Console in Automations](#using-hass-console-in-automations)
- [Entity Naming Convention](#entity-naming-convention)
- [Cron Reference](#cron-reference)
- [Real-World Examples](#real-world-examples)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

HASS Console is a custom integration (domain: `hass_console`) with three parts:

```
┌──────────────────────────────────────────────────────────────┐
│  configuration.yaml                                          │
│    hass_console: !include console.yaml                       │
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
│  │  Matches cron    │     │  Watches entity      │           │
│  │  expressions →   │     │  state changes →     │           │
│  │  reads entity →  │     │  checks threshold →  │           │
│  │  writes LOG row  │     │  tracks duration →   │           │
│  │                  │     │  writes ALARM row    │           │
│  └───────┬──────────┘     └──────────┬───────────┘           │
│          │                           │                       │
│          ▼                           ▼                       │
│  /config/www/                /config/www/                    │
│  hass-console-logs.csv       hass-console-alarms.csv         │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  HASS Console Card  (www/hass-console-card.js)               │
│                                                              │
│  Fetches both CSVs → renders tabbed view with filters        │
│  Auto-refreshes on configurable interval                     │
└──────────────────────────────────────────────────────────────┘
```

Two separate CSV files keep alarm history and log history independent. This means different retention policies, cleaner Excel/Grafana imports, smaller files, and columns that actually match each tab's data (no wasted empty columns).

---

## Installation

### Step 1 — Copy the custom component

```bash
cp -r custom_components/hass_console/ <your-ha-config>/custom_components/hass_console/
```

Your config directory structure should look like:

```
config/
├── custom_components/
│   └── hass_console/
│       ├── __init__.py
│       ├── manifest.json
│       └── services.yaml
├── www/
│   └── hass-console-card.js      ← Step 2
├── console.yaml                  ← Step 3
└── configuration.yaml            ← Step 4
```

### Step 2 — Copy the Lovelace card

```bash
cp www/hass-console-card.js <your-ha-config>/www/hass-console-card.js
```

### Step 3 — Create your console.yaml

Copy the included `console.yaml` to your config root and edit it with your own entities. See the full reference below.

### Step 4 — Wire it into configuration.yaml

Add this line:

```yaml
hass_console: !include console.yaml
```

### Step 5 — Register the card resource

Go to **Settings → Dashboards → ⋮ (top right) → Resources → Add Resource**:

| Field | Value |
|-------|-------|
| URL   | `/local/hass-console-card.js` |
| Type  | JavaScript Module |

### Step 6 — Restart Home Assistant

A full restart is required (not just a config reload) since this is a custom integration.

### Step 7 — Add the card to a dashboard

Edit any dashboard → Add Card → Manual → paste:

```yaml
type: custom:hass-console-card
title: HASS Console
alarm_csv: /local/hass-console-alarms.csv
log_csv: /local/hass-console-logs.csv
rows: 200
refresh_interval: 30
```

---

## Quick Start

Here's the minimum viable `console.yaml` with one LOG and one ALARM point:

```yaml
# Log your energy meter reading every night at midnight
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  note: "Daily kWh snapshot at midnight"

# Alarm if the server closet gets too hot
SERVER_ROOM_TEMP:
  type: ALARM
  class: "01"
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
- A row in `hass-console-alarms.csv` each time the temperature stays above 80°F for 5+ minutes

---

## Console.yaml Reference

Every top-level key in `console.yaml` defines a **point** (a named data source to watch). The key name becomes part of the entity ID. Each point must have a `type` of either `LOG` or `ALARM`.

---

### LOG Points — Scheduled Data Snapshots

LOG points read an entity's current state on a cron schedule and write it to `hass-console-logs.csv`. Think of them as trend logging — periodic snapshots of values you want to track over time.

#### Full schema

```yaml
POINT_NAME:
  type: LOG                        # Required — must be "LOG"
  cron: "0 0 * * *"               # Required — 5-field cron expression (when to log)
  entity: sensor.some_entity       # Required — entity_id to read the value from
  note: "Description of this log"  # Optional — static text stored in the Note column
```

#### Fields explained

**`type: LOG`** (required)
Tells the engine this is a scheduled log point, not an alarm.

**`cron`** (required)
A standard 5-field cron expression that controls when the snapshot is taken. The engine checks every 60 seconds; when the current time matches the cron expression, it reads the entity and writes a row.

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

Common patterns:

| Expression        | Schedule |
|-------------------|----------|
| `"0 0 * * *"`    | Daily at midnight |
| `"0 * * * *"`    | Every hour on the hour |
| `"*/5 * * * *"`  | Every 5 minutes |
| `"*/15 * * * *"` | Every 15 minutes |
| `"0 8 * * 1"`    | Every Monday at 8:00 AM |
| `"0 0 1 * *"`    | First day of each month at midnight |
| `"0 6,18 * * *"` | Twice daily at 6 AM and 6 PM |
| `"30 23 * * *"`  | Daily at 11:30 PM |
| `"0 0 * * 1-5"`  | Weekdays at midnight |

**Important:** Always wrap cron expressions in quotes in YAML, or the `*` characters will cause parse errors.

**`entity`** (required)
The Home Assistant entity whose `.state` value gets logged. This can be any entity — sensors, binary sensors, input numbers, counters, etc. Whatever `.state` returns is written as the `value` column in the CSV.

**`note`** (optional, defaults to `""`)
A static string written to the `note` column every time this point logs. Use it to describe what this data point represents. This is metadata, not dynamic — the same note is written on every row from this point.

#### What gets written to hass-console-logs.csv

| Column    | Source | Example |
|-----------|--------|---------|
| timestamp | Auto-generated ISO 8601 | `2026-05-26T00:00:01.234567-04:00` |
| entity    | Point entity ID | `hass_console.log_daily_kwh` |
| value     | `state` of the source entity at time of log | `42.7` |
| note      | Static from config | `Daily kWh snapshot at midnight` |

#### What gets created in HA

Each LOG point creates a Home Assistant entity: `hass_console.log_<point_name_lowercase>`

The entity's state = the last logged value. Its attributes include:
- `friendly_name` — "HASS Console Log: DAILY_KWH"
- `last_logged` — ISO timestamp of the most recent log
- `note` — the note from config

You can use this entity in other automations, display it on cards, include it in history graphs, etc.

#### LOG examples

**Daily energy meter reading:**
```yaml
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  note: "Total kWh at midnight"
```

**Hourly temperature trend:**
```yaml
HOURLY_OUTDOOR_TEMP:
  type: LOG
  cron: "0 * * * *"
  entity: sensor.outdoor_temperature
  note: "Outdoor temp every hour"
```

**Every-5-minute power monitoring:**
```yaml
POWER_DRAW_5MIN:
  type: LOG
  cron: "*/5 * * * *"
  entity: sensor.main_panel_watts
  note: "5-min power draw snapshot"
```

**Weekly water meter (Monday morning):**
```yaml
WEEKLY_WATER:
  type: LOG
  cron: "0 8 * * 1"
  entity: sensor.water_meter_gallons
  note: "Weekly water usage"
```

**Monthly gas meter:**
```yaml
MONTHLY_GAS:
  type: LOG
  cron: "0 0 1 * *"
  entity: sensor.gas_meter_ccf
  note: "Monthly gas reading on the 1st"
```

**Twice-daily HVAC runtime:**
```yaml
HVAC_RUNTIME:
  type: LOG
  cron: "0 6,18 * * *"
  entity: sensor.hvac_runtime_today
  note: "HVAC runtime at 6am and 6pm"
```

---

### ALARM Points — Threshold-Based Alerts

ALARM points watch entity states in real time and fire when a numeric condition is met for a sustained duration. Think of them as a threshold alarm — if a temperature exceeds 78°F and stays there for 10 minutes, log it as an alarm event.

#### Full schema

```yaml
POINT_NAME:
  type: ALARM                             # Required — must be "ALARM"
  class: "01"                             # Optional — alarm severity classification
  entity: sensor.some_entity              # Optional — primary entity (informational)
  note: "Description of this alarm"       # Optional — static text for the Note column
  trigger:                                # Required — list of trigger definitions
    - alias: "Human-readable description" # Optional — friendly name for Trigger column
      platform: numeric_state             # Required — only "numeric_state" supported
      entity_id: sensor.some_entity       # Required — entity to monitor
      above: 78                           # Optional — fire when state > this value
      below: 20                           # Optional — fire when state < this value
      for:                                # Optional — how long condition must hold
        hours: 0
        minutes: 10
        seconds: 0
```

#### Fields explained

**`type: ALARM`** (required)
Tells the engine this is a real-time threshold alarm, not a scheduled log.

**`class`** (optional, defaults to `""`)
A severity classification string. This is freeform — you can use whatever scheme makes sense for your setup. The Lovelace card has built-in color coding for three common classes:

| Class | Card Color | Suggested Meaning |
|-------|-----------|-------------------|
| `"01"` | Red | Critical — immediate attention required |
| `"02"` | Amber | Major — needs attention soon |
| `"03"` | Blue | Minor — informational / low priority |

You can use any other string (e.g., `"CRITICAL"`, `"WARNING"`, `"INFO"`, `"04"`) — it will display with default gray styling.

**`entity`** (optional)
The primary entity associated with this alarm. This is informational — it appears in the entity column of the CSV. The actual entity being monitored is defined in the `trigger` section's `entity_id`. These can be the same or different.

**`note`** (optional, defaults to `""`)
Static text written to the `note` column when this alarm fires.

**`trigger`** (required)
A list of one or more trigger definitions. Each trigger independently monitors an entity and fires when its conditions are met. A single ALARM point can have multiple triggers (e.g., a high-temp trigger and a rate-of-change trigger).

Each trigger supports these fields:

**`trigger[].alias`** (optional)
A human-friendly name for this specific trigger condition. This is what appears in the "Trigger" column of the alarm CSV. Make it descriptive — `"Above 78°F for 10 min"` is much more useful than `"temp high"` when you're scanning the alarm log at 2 AM.

**`trigger[].platform`** (required)
Currently only `numeric_state` is supported. This evaluates the entity's state as a number and checks it against `above` and/or `below` thresholds.

**`trigger[].entity_id`** (required)
The entity to actually monitor. The engine subscribes to state change events on this entity.

**`trigger[].above`** (optional)
The upper threshold. The alarm condition is met when the entity's numeric state is **strictly greater than** this value. You can combine `above` and `below` to create a band — the alarm fires when the value is outside the band.

**`trigger[].below`** (optional)
The lower threshold. The alarm condition is met when the entity's numeric state is **strictly less than** this value.

At least one of `above` or `below` must be specified.

**`trigger[].for`** (optional)
How long the condition must be continuously true before the alarm fires. This prevents nuisance alarms from transient spikes. If omitted, the alarm fires immediately when the condition is met.

Accepts a dictionary with any combination of:
```yaml
for:
  hours: 0
  minutes: 10
  seconds: 0
```

#### How alarm evaluation works

1. The engine subscribes to `state_changed` events on the trigger's `entity_id`.
2. On each state change, it converts the new state to a number.
3. If the numeric condition (above/below) is met:
   - If the alarm was **not previously active**, it marks it active and records the time.
   - If the alarm **was already active** and the `for` duration has elapsed, it writes an ALARM row to the CSV and marks it as recorded.
4. If the condition is **no longer met**, the alarm resets — it clears the active state and the timer, ready to fire again the next time the condition holds.

This means:
- An alarm only fires **once per incident**. If the temperature exceeds 78°F and stays high for an hour, you get one alarm row (at the moment the duration requirement was first satisfied), not continuous repeats.
- When the value drops back below threshold and then exceeds it again, that's a **new incident** — a new alarm row will be generated.

#### What gets written to hass-console-alarms.csv

| Column    | Source | Example |
|-----------|--------|---------|
| timestamp | When the alarm fired | `2026-05-26T14:32:01.567890-04:00` |
| entity    | Point entity ID | `hass_console.alarm_temperature_alarm` |
| class     | From config | `01` |
| value     | Entity state when the alarm fired | `82.3` |
| duration  | How long the condition was active | `0:10:05` |
| note      | Static from config | `Network closet overheat` |
| trigger   | The alias of the trigger that fired | `Above 78°F for 10 min` |

#### What gets created in HA

Each ALARM point creates a Home Assistant entity: `hass_console.alarm_<point_name_lowercase>`

The entity's state toggles between the last logged value and `"ALARM"` when triggered. Its attributes include:
- `friendly_name` — "HASS Console Alarm: TEMPERATURE_ALARM"
- `last_alarm` — ISO timestamp of the most recent alarm
- `class`, `value`, `duration`, `trigger` — from the last alarm event

#### ALARM examples

**High temperature (critical):**
```yaml
NETWORK_CLOSET_OVERHEAT:
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

**Freezer failure (major):**
```yaml
GARAGE_FREEZER:
  type: ALARM
  class: "02"
  entity: sensor.garage_freezer_temperature
  note: "Garage freezer temperature rising"
  trigger:
    - alias: "Freezer above 10°F for 30 min"
      platform: numeric_state
      entity_id: sensor.garage_freezer_temperature
      above: 10
      for:
        minutes: 30
```

**Low battery (minor):**
```yaml
UPS_LOW_BATTERY:
  type: ALARM
  class: "03"
  entity: sensor.ups_battery_level
  note: "UPS battery getting low"
  trigger:
    - alias: "Battery below 20%"
      platform: numeric_state
      entity_id: sensor.ups_battery_level
      below: 20
      for:
        minutes: 5
```

**Excessive power draw (immediate, no duration):**
```yaml
POWER_SPIKE:
  type: ALARM
  class: "01"
  entity: sensor.main_panel_watts
  note: "Power spike detected"
  trigger:
    - alias: "Above 10000W (immediate)"
      platform: numeric_state
      entity_id: sensor.main_panel_watts
      above: 10000
```

**Out-of-band humidity (two-sided):**
```yaml
HUMIDITY_OUT_OF_RANGE:
  type: ALARM
  class: "02"
  entity: sensor.server_room_humidity
  note: "Server room humidity out of range"
  trigger:
    - alias: "Humidity above 60% for 15 min"
      platform: numeric_state
      entity_id: sensor.server_room_humidity
      above: 60
      for:
        minutes: 15
    - alias: "Humidity below 30% for 15 min"
      platform: numeric_state
      entity_id: sensor.server_room_humidity
      below: 30
      for:
        minutes: 15
```

**Multiple triggers on one alarm point:**
```yaml
WATER_LEAK_ZONE:
  type: ALARM
  class: "01"
  entity: binary_sensor.basement_leak
  note: "Basement water detection"
  trigger:
    - alias: "Sump pit above 90% for 2 min"
      platform: numeric_state
      entity_id: sensor.sump_pit_level
      above: 90
      for:
        minutes: 2
    - alias: "Water pressure drop below 30 PSI"
      platform: numeric_state
      entity_id: sensor.water_main_pressure
      below: 30
      for:
        minutes: 5
```

---

## CSV Output

HASS Console writes two separate CSV files:

| File | URL | Contents |
|------|-----|----------|
| `/config/www/hass-console-alarms.csv` | `/local/hass-console-alarms.csv` | Alarm events only |
| `/config/www/hass-console-logs.csv` | `/local/hass-console-logs.csv` | Log snapshots only |

**Why two files?** Alarm events and log snapshots have different schemas (alarms have class, duration, and trigger columns that logs don't need), different volumes, and likely different retention needs. Keeping them separate means cleaner imports, easier archival, and less wasted disk space on empty columns.

### Alarm CSV columns

```
timestamp, entity, class, value, duration, note, trigger
```

### Log CSV columns

```
timestamp, entity, value, note
```

Both files are standard CSV, accessible from any browser at their `/local/` URL, and can be imported into Excel, Google Sheets, Grafana, InfluxDB, or any other tool that reads CSV.

---

## Lovelace Card

### Configuration

```yaml
type: custom:hass-console-card
title: HASS Console            # Card header text
alarm_csv: /local/hass-console-alarms.csv   # URL to alarm CSV
log_csv: /local/hass-console-logs.csv       # URL to log CSV
rows: 200                      # Max rows to display per tab
refresh_interval: 30           # Seconds between auto-refresh
```

### Features

**Tabs** — ALARM and LOG tabs with live row counts. Switching tabs resets sorting and filters.

**Collapsible filter panel** — click ⚙ Filters to expand:
- **Alarm Class** — color-coded chip toggles (01 Critical = red, 02 Major = amber, 03 Minor = blue). Multi-select — toggle any combination. Only visible on the Alarm tab.
- **Entity** — chip toggles for every distinct entity in the current tab.
- **Date Range** — from/to date pickers plus quick presets: Today, Last 7d, Last 30d, This Month.
- **Clear All Filters** — resets everything in one click.

**Text search** — the search box at the top matches against all columns simultaneously.

**Sortable columns** — click any column header to sort ascending, click again for descending. The active sort shows a ▲/▼ indicator.

**Active filter tags** — active filters show as removable tags in the footer bar. Click ✕ on any tag to remove just that filter.

**Filter count badge** — the ⚙ Filters button shows a green badge with the number of active filters.

**Download** — the ↓ CSV button opens the raw CSV file for the active tab in a new browser tab.

**Auto-refresh** — the card re-fetches both CSVs on the configured interval and displays the "Refreshed" timestamp.

**Entity shorthand** — entity names in the table strip the `hass_console.` prefix for readability.

All filters stack — you can combine class + entity + date range + text search simultaneously. The row counter updates to show "12 of 347 rows" when filters are active.

---

## Services

HASS Console registers three services for use in automations, scripts, and the Developer Tools.

### hass_console.write_log

Manually inject a LOG entry into the log CSV. Useful for logging events that aren't tied to a cron schedule.

```yaml
service: hass_console.write_log
data:
  entity: "hass_console.log_custom_event"   # Any string — doesn't need to match a configured point
  value: "42.5"                             # Optional — the value to record
  note: "Manual reading from field tech"    # Optional — description
```

| Field  | Required | Description |
|--------|----------|-------------|
| entity | Yes | Entity name to record (freeform string) |
| value  | No | The value to write |
| note   | No | Descriptive note |

### hass_console.write_alarm

Manually inject an ALARM entry into the alarm CSV.

```yaml
service: hass_console.write_alarm
data:
  entity: "hass_console.alarm_manual_override"
  class: "02"
  value: "OPEN"
  duration: "0:00:00"
  note: "Garage door left open"
  trigger: "Manual observation"
```

| Field    | Required | Description |
|----------|----------|-------------|
| entity   | Yes | Entity name to record (freeform string) |
| class    | No | Severity class |
| value    | No | The value/state |
| duration | No | Duration string |
| note     | No | Descriptive note |
| trigger  | No | What caused the alarm |

### hass_console.reload

Reload the engine — re-reads `console.yaml`, tears down existing listeners, and re-initializes everything. No HA restart needed after editing `console.yaml`.

```yaml
service: hass_console.reload
```

---

## Using HASS Console in Automations

The services let you feed any HA event into the console. Here are patterns for common use cases.

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
          class: "02"
          value: "OPEN"
          note: "Garage door opened"
          trigger: "binary_sensor.garage_door → on"
```

### Log daily HVAC runtime

```yaml
automation:
  - alias: "Console — Log HVAC runtime at midnight"
    trigger:
      - platform: time
        at: "23:59:00"
    action:
      - service: hass_console.write_log
        data:
          entity: hass_console.log_hvac_runtime
          value: "{{ states('sensor.hvac_total_runtime_today') }}"
          note: "End-of-day HVAC runtime"
```

### Log when a person arrives or leaves

```yaml
automation:
  - alias: "Console — Person tracking"
    trigger:
      - platform: state
        entity_id: person.john
    action:
      - service: hass_console.write_log
        data:
          entity: hass_console.log_person_john
          value: "{{ states('person.john') }}"
          note: "John location changed"
```

### Alarm on washer/dryer cycle completion

```yaml
automation:
  - alias: "Console — Washer finished"
    trigger:
      - platform: state
        entity_id: sensor.washer_status
        to: "complete"
    action:
      - service: hass_console.write_alarm
        data:
          entity: hass_console.alarm_washer_done
          class: "03"
          value: "COMPLETE"
          note: "Washer cycle finished"
          trigger: "sensor.washer_status → complete"
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
          value: "{{ states('sensor.speedtest_download') }} Mbps down / {{ states('sensor.speedtest_upload') }} Mbps up"
          note: "Speed test result"
```

---

## Entity Naming Convention

Every point in `console.yaml` creates a Home Assistant entity following this pattern:

```
hass_console.<type>_<point_name_in_lowercase>
```

| YAML Key             | Type  | Entity ID |
|----------------------|-------|-----------|
| `DAILY_KWH`         | LOG   | `hass_console.log_daily_kwh` |
| `TEMPERATURE_ALARM`  | ALARM | `hass_console.alarm_temperature_alarm` |
| `WEEKLY_WATER`       | LOG   | `hass_console.log_weekly_water` |
| `UPS_LOW_BATTERY`    | ALARM | `hass_console.alarm_ups_low_battery` |

These entities are real HA entities — they appear in Developer Tools → States, can be used in automations, displayed on Lovelace cards, and tracked in history.

---

## Cron Reference

HASS Console uses standard 5-field cron expressions for LOG point scheduling.

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

### Supported syntax

| Syntax | Meaning | Example |
|--------|---------|---------|
| `*`    | Every value | `* * * * *` = every minute |
| `5`    | Specific value | `5 * * * *` = at minute 5 |
| `1,15` | Multiple values | `0 1,15 * * *` = at 1 AM and 3 PM |
| `1-5`  | Range | `0 0 * * 1-5` = weekdays |
| `*/10` | Step | `*/10 * * * *` = every 10 minutes |

### Common schedules

| Expression        | Meaning |
|-------------------|---------|
| `"0 0 * * *"`    | Daily at midnight |
| `"0 * * * *"`    | Every hour on the hour |
| `"*/5 * * * *"`  | Every 5 minutes |
| `"*/15 * * * *"` | Every 15 minutes |
| `"0 8 * * 1"`    | Monday at 8 AM |
| `"0 0 1 * *"`    | 1st of the month at midnight |
| `"0 6,18 * * *"` | 6 AM and 6 PM daily |
| `"0 0 * * 1-5"`  | Weekdays at midnight |
| `"30 2 * * 0"`   | Sunday at 2:30 AM |
| `"0 */4 * * *"`  | Every 4 hours |

---

## Real-World Examples

### Home energy monitoring console

```yaml
# ── LOG POINTS ──

DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.grid_consumption_kwh
  note: "Daily grid consumption"

DAILY_SOLAR:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.solar_production_kwh
  note: "Daily solar production"

PEAK_DEMAND_HOURLY:
  type: LOG
  cron: "0 * * * *"
  entity: sensor.main_panel_watts
  note: "Hourly demand reading"

# ── ALARM POINTS ──

HIGH_DEMAND:
  type: ALARM
  class: "01"
  entity: sensor.main_panel_watts
  note: "Excessive power draw — check for stuck loads"
  trigger:
    - alias: "Above 8kW for 5 min"
      platform: numeric_state
      entity_id: sensor.main_panel_watts
      above: 8000
      for:
        minutes: 5

SOLAR_INVERTER_DOWN:
  type: ALARM
  class: "02"
  entity: sensor.solar_inverter_power
  note: "Solar inverter producing zero during daylight"
  trigger:
    - alias: "Zero output for 30 min"
      platform: numeric_state
      entity_id: sensor.solar_inverter_power
      below: 1
      for:
        minutes: 30

BATTERY_LOW:
  type: ALARM
  class: "03"
  entity: sensor.powerwall_battery_level
  note: "Home battery getting low"
  trigger:
    - alias: "Battery below 15%"
      platform: numeric_state
      entity_id: sensor.powerwall_battery_level
      below: 15
      for:
        minutes: 10
```

### Server room / network closet monitoring

```yaml
TEMP_15MIN:
  type: LOG
  cron: "*/15 * * * *"
  entity: sensor.rack_inlet_temperature
  note: "Rack inlet temp"

HUMIDITY_15MIN:
  type: LOG
  cron: "*/15 * * * *"
  entity: sensor.server_room_humidity
  note: "Server room humidity"

OVERHEAT:
  type: ALARM
  class: "01"
  entity: sensor.rack_inlet_temperature
  note: "Rack inlet overheating"
  trigger:
    - alias: "Inlet above 85°F for 5 min"
      platform: numeric_state
      entity_id: sensor.rack_inlet_temperature
      above: 85
      for:
        minutes: 5

UPS_CRITICAL:
  type: ALARM
  class: "01"
  entity: sensor.ups_battery_percent
  note: "UPS battery critical"
  trigger:
    - alias: "Battery below 10%"
      platform: numeric_state
      entity_id: sensor.ups_battery_percent
      below: 10
      for:
        minutes: 2

HUMIDITY_HIGH:
  type: ALARM
  class: "02"
  entity: sensor.server_room_humidity
  note: "Server room humidity too high"
  trigger:
    - alias: "Above 65% RH for 15 min"
      platform: numeric_state
      entity_id: sensor.server_room_humidity
      above: 65
      for:
        minutes: 15
```

---

## Troubleshooting

**No CSV files created**
The engine creates the CSVs on first HA startup after installation. Check that `/config/www/` exists and is writable. Look at the HA log for lines starting with `hass_console`.

**Cron not firing**
Make sure the cron expression is wrapped in quotes in YAML. The scanner runs every 60 seconds, so there can be up to a 60-second delay. Check the HA log at debug level:

```yaml
logger:
  logs:
    custom_components.hass_console: debug
```

**Alarm not triggering**
Verify the entity actually reports a numeric state (check Developer Tools → States). If the state is `unavailable`, `unknown`, or a string, the numeric evaluation will skip it. Also verify the `entity_id` inside the trigger matches the real entity — a common mistake is putting the entity in the top-level `entity:` field but a different one (or none) in the `trigger[].entity_id`.

**Card shows "No entries yet"**
Click ↻ Refresh. Verify the CSV URLs in the card config match the actual file paths. Open the URL directly in a browser (e.g., `http://homeassistant.local:8123/local/hass-console-alarms.csv`) to check if the file is accessible.

**Card not loading**
Make sure the resource is registered (Settings → Dashboards → Resources) with the correct URL and type "JavaScript Module". Try a hard refresh (Ctrl+Shift+R) in the browser.

**Reloading after config changes**
Call `hass_console.reload` from Developer Tools → Services, or use it in a script. This tears down all existing cron schedules and alarm listeners, re-reads `console.yaml`, and sets everything up fresh — no HA restart needed.
