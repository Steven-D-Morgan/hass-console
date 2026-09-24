# Cookbook

Worked examples and copy-pasteable recipes for **HASS Console**. The [README](README.md) explains *what* the integration does and *how* each piece is configured; this file collects the *how it fits together* — real dashboards, real automations, real point definitions people can lift verbatim into their own setups.

Each recipe is self-contained. Copy the YAML, adjust the entity IDs, and drop it into your `automations.yaml` or `console.yaml`.

---

## Contents

- [Automations](#automations)
  - [Log a door open event as an alarm](#log-a-door-open-event-as-an-alarm)
  - [Log daily HVAC runtime](#log-daily-hvac-runtime)
  - [Auto-acknowledge alarms at shift change](#auto-acknowledge-alarms-at-shift-change)
  - [Acknowledge a specific alarm from a notification action](#acknowledge-a-specific-alarm-from-a-notification-action)
  - [Log internet speed test results](#log-internet-speed-test-results)
- [Full point sets](#full-point-sets)
  - [Home energy monitoring](#home-energy-monitoring)
  - [Server room monitoring](#server-room-monitoring)
- [Planned recipes](#planned-recipes)

---

## Automations

Each recipe below is a full `automation:` entry — paste it into `automations.yaml` (or a `!include`-d file) and reload automations. All of them call one of the [HASS Console services](README.md#services); see the service reference in the README for the full field list.

### Log a door open event as an alarm

**Why:** You want a durable, acknowledgeable record every time a specific door opens — not just a state history entry.

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

**Why:** Snapshot a daily total to the LOG CSV at the end of every day, so the utility-side sensor's reset doesn't erase the historical value.

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

**Why:** Clear the board at the start of each day so only new events show as unacknowledged.

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

**Why:** Pair a mobile actionable notification with the ACK service so the responder can clear the alarm from their lock screen.

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

The notification itself must be posted with `data.actions[].action: ACK_ALARM` and the alarm's ID passed through as an action payload — see the HA mobile app docs for actionable-notification syntax.

### Log internet speed test results

**Why:** Keep a rolling history of speed test results in a single CSV, one row per test, for later charting or SLA review.

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

## Full point sets

These are complete `console.yaml` blocks for common install shapes. Paste, adjust entity IDs, reload the integration.

### Home energy monitoring

Two LOG points capture daily totals, one LOG point captures hourly demand, and two ALARM points flag overdraw and low home-battery conditions.

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

A 15-minute rack-inlet LOG point plus two Critical ALARMs on temperature and UPS state.

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

## Planned recipes

_Placeholders — fill in as they're written._

- [ ] Escalate an unacknowledged Critical to a second target after N minutes
- [ ] Weekly rollup email of LOG values (parse the CSV, email the summary)
- [ ] Shelve an alarm during a scheduled maintenance window
- [ ] Trend a LOG point in ApexCharts / mini-graph-card
- [ ] Log on change instead of on cron (workaround pattern until change-based LOG points ship)
- [ ] Custom severity class (e.g. `04 = INFO`) with matching color in the card
- [ ] Multi-condition ALARM: only fire if the *door was opened* **and** the *alarm system is armed*
- [ ] Restore CSVs to a new HA instance without losing acknowledgment history
- [ ] Automating on `hass_console.*` entity states in scripts and blueprints

---

_Last updated: 2026-09-24._
