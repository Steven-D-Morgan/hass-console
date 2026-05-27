# Console — Alarm & Log Engine for Home Assistant

A Niagara-inspired alarm console and data logger that runs as a native HA custom component. Define alarm points and scheduled log snapshots in a simple YAML file, and view everything in a sortable, filterable Lovelace card with ALARM and LOG tabs.

---

## What's Included

```
console_component/
├── custom_components/
│   └── console/
│       ├── __init__.py          # Core engine (cron scheduler, alarm evaluator, CSV writer)
│       ├── manifest.json        # HA integration manifest
│       └── services.yaml        # Service definitions (write_log, write_alarm, reload)
├── www/
│   └── console-card.js          # Lovelace card (tabbed alarm/log viewer)
├── console.yaml                 # Example config — copy and edit for your setup
└── README.md
```

---

## Installation

### 1. Copy the custom component

```bash
cp -r custom_components/console/ /config/custom_components/console/
```

### 2. Copy the Lovelace card

```bash
cp www/console-card.js /config/www/console-card.js
```

### 3. Register the card resource

**Settings → Dashboards → ⋮ → Resources → Add Resource**

| Field | Value |
|-------|-------|
| URL   | `/local/console-card.js` |
| Type  | JavaScript Module |

### 4. Create your console.yaml

Copy `console.yaml` to `/config/console.yaml` and edit it to match your entities.

### 5. Include it in configuration.yaml

```yaml
console: !include console.yaml
```

### 6. Restart Home Assistant

---

## console.yaml Reference

### LOG Points (Scheduled Reads)

```yaml
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"                  # 5-field cron expression
  entity: sensor.energy_meter_kwh    # entity to read
  note: "Daily kWh snapshot"         # appears in Note column
```

**Creates entity:** `console.log_daily_kwh`

The cron scanner runs every minute. When a cron expression matches, the engine reads the source entity's current state and appends a LOG row to the CSV.

### ALARM Points (Threshold Triggers)

```yaml
TEMPERATURE_ALARM:
  type: ALARM
  class: "01"                               # severity class (01=critical, 02=major, 03=minor)
  entity: sensor.network_closet_temperature  # primary entity
  note: "Network closet overheat"
  trigger:
    - alias: "Above 78°F for 10 min"        # friendly name shown in Trigger column
      platform: numeric_state
      entity_id: sensor.network_closet_temperature
      above: 78
      for:
        minutes: 10
```

**Creates entity:** `console.alarm_temperature_alarm`

The engine listens for state changes on the target entity. When the numeric condition is met for the specified duration, it writes an ALARM row.

### Entity Naming Convention

```
console.<type>_<header_lowercase>
```

| YAML Key            | Type  | Entity ID                      |
|---------------------|-------|--------------------------------|
| `DAILY_KWH`        | LOG   | `console.log_daily_kwh`       |
| `TEMPERATURE_ALARM` | ALARM | `console.alarm_temperature_alarm` |

---

## CSV Output

Written to: `/config/www/console.csv`
Accessible at: `http://<your-ha>:8123/local/console.csv`

### Columns

| Column    | LOG | ALARM | Description |
|-----------|:---:|:-----:|-------------|
| row_type  | ✓   | ✓     | `LOG` or `ALARM` |
| timestamp | ✓   | ✓     | ISO 8601 datetime |
| entity    | ✓   | ✓     | Console entity ID |
| class     |     | ✓     | Alarm severity class |
| value     | ✓   | ✓     | Entity state at time of recording |
| duration  |     | ✓     | How long condition was active |
| note      | ✓   | ✓     | From YAML config |
| trigger   |     | ✓     | Friendly alias of what fired |

---

## Services

### `console.write_log`

Manually write a LOG entry (useful in automations).

```yaml
service: console.write_log
data:
  entity: console.log_daily_kwh
  value: "42.5"
  note: "Manual reading"
```

### `console.write_alarm`

Manually write an ALARM entry.

```yaml
service: console.write_alarm
data:
  entity: console.alarm_temperature_alarm
  class: "01"
  value: "82.3"
  duration: "0:10:00"
  note: "Manual alarm entry"
  trigger: "Operator override"
```

### `console.reload`

Reload the engine (re-reads console.yaml, restarts all listeners).

```yaml
service: console.reload
```

---

## Lovelace Card

Add a **Manual card** to any dashboard:

```yaml
type: custom:console-card
title: Console
csv_url: /local/console.csv
rows: 200
refresh_interval: 30
```

### Card Features

- **ALARM / LOG tabs** with row counts
- **Sortable columns** (click any header)
- **Text filter** across all columns
- **Auto-refresh** (configurable interval)
- **Download** button to open raw CSV
- **Severity badges** — color-coded by class (01=red, 02=amber, 03=blue)
- **Formatted timestamps** — date dimmed, time bold

---

## Using in Automations

You can call the services from any automation to inject custom entries:

```yaml
automation:
  - alias: "Log garage door open"
    trigger:
      - platform: state
        entity_id: binary_sensor.garage_door
        to: "on"
    action:
      - service: console.write_alarm
        data:
          entity: console.alarm_garage_door
          class: "02"
          value: "OPEN"
          note: "Garage door opened"
          trigger: "State change to ON"
```

---

## Cron Reference

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

| Expression      | Meaning |
|-----------------|---------|
| `0 0 * * *`     | Daily at midnight |
| `0 * * * *`     | Every hour on the hour |
| `*/5 * * * *`   | Every 5 minutes |
| `0 8 * * 1`     | Mondays at 8:00 AM |
| `0 0 1 * *`     | First of every month at midnight |
