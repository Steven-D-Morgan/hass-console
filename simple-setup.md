# HASS Console — Simple Setup

A step-by-step guide to get HASS Console running. Total time: ~5 minutes.

---

## What You Need

- Home Assistant (2024.1 or newer)
- Access to your HA config directory (via File Editor add-on, SSH, Samba, etc.)

---

## Step 1 — Download

Download the [latest release](https://github.com/Steven-D-Morgan/hass-console/releases/latest) `.tar.gz` and extract it, or clone the repo:

```bash
git clone https://github.com/Steven-D-Morgan/hass-console.git
```

---

## Step 2 — Copy Two Folders

Copy these into your Home Assistant config directory:

| From | To |
|------|----|
| `custom_components/hass_console/` | `/config/custom_components/hass_console/` |
| `www/hass-console-card.js` | `/config/www/hass-console-card.js` |

If `custom_components/` or `www/` don't exist in your config directory yet, create them.

---

## Step 3 — Create console.yaml

Create a new file at `/config/console.yaml`. Start with this minimal example and swap in your own entities:

```yaml
# ─── LOG EXAMPLE ───
# Reads sensor.energy_meter_kwh every night at midnight
# and saves the value to hass-console-logs.csv

DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  note: "Daily kWh snapshot at midnight"


# ─── ALARM EXAMPLE ───
# Watches sensor.network_closet_temperature
# If it stays above 78 for 10 minutes, writes an alarm
# to hass-console-alarms.csv

TEMPERATURE_ALARM:
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

## Step 4 — Edit configuration.yaml

Add this one line to `/config/configuration.yaml`:

```yaml
hass_console: !include console.yaml
```

---

## Step 5 — Register the Card

In Home Assistant:

1. Go to **Settings → Dashboards**
2. Click the **⋮** menu (top right) → **Resources**
3. Click **Add Resource**
4. URL: `/local/hass-console-card.js`
5. Type: **JavaScript Module**
6. Click **Create**

---

## Step 6 — Restart Home Assistant

Go to **Settings → System → Restart** and do a full restart.

After restart, the integration will automatically create:
- `/config/www/hass-console-alarms.csv`
- `/config/www/hass-console-logs.csv`

You don't need to create the CSV files — they're generated on first boot.

---

## Step 7 — Add the Card to a Dashboard

1. Open any dashboard
2. Click **Edit** (pencil icon) → **Add Card**
3. Scroll down and choose **Manual**
4. Paste this:

```yaml
type: custom:hass-console-card
title: HASS Console
alarm_csv: /local/hass-console-alarms.csv
log_csv: /local/hass-console-logs.csv
rows: 200
refresh_interval: 30
```

5. Click **Save**

---

## You're Done

The card will show two tabs — **Alarm** and **Log**. They'll be empty until your first cron fires or an alarm triggers. To test immediately, go to **Developer Tools → Services** and run:

```yaml
service: hass_console.write_log
data:
  entity: hass_console.log_test
  value: "Hello World"
  note: "Testing the console"
```

Switch to the Log tab on your card, click **↻ Refresh**, and you should see the entry.

---

## Adding More Points

Open `/config/console.yaml` and add more entries. You don't need to restart HA — just call the reload service:

**Developer Tools → Services:**

```yaml
service: hass_console.reload
```

---

## Quick Reference

### LOG point template

```yaml
MY_LOG_NAME:
  type: LOG
  cron: "CRON_EXPRESSION"
  entity: sensor.your_entity
  note: "What this log tracks"
```

### ALARM point template

```yaml
MY_ALARM_NAME:
  type: ALARM
  class: "01"                          # 01=Critical  02=Major  03=Minor
  entity: sensor.your_entity
  note: "What this alarm means"
  trigger:
    - alias: "Human-readable description"
      platform: numeric_state
      entity_id: sensor.your_entity
      above: 80                        # or use "below: 20" for low alarms
      for:
        minutes: 10
```

### Common cron schedules

| Schedule | Expression |
|----------|-----------|
| Every 5 minutes | `"*/5 * * * *"` |
| Every hour | `"0 * * * *"` |
| Daily at midnight | `"0 0 * * *"` |
| Daily at 6 AM | `"0 6 * * *"` |
| Monday at 8 AM | `"0 8 * * 1"` |
| 1st of the month | `"0 0 1 * *"` |

---

## Need More Detail?

See the full [README](README.md) for the complete reference — all fields, alarm evaluation logic, automation examples, and troubleshooting.
