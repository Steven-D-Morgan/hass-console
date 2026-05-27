# HASS Console — Simple Setup

A step-by-step guide to get HASS Console running. Total time: ~5 minutes.

There are **two ways to set up** the integration:
- **UI Mode (recommended)** — configure via Settings → Devices & Integrations
- **YAML Mode (legacy)** — add `hass_console:` to configuration.yaml

Both modes are supported and use the same `console.yaml` for defining alarm and log points.

---

## What You Need

- Home Assistant (2024.1 or newer)
- Access to your HA config directory (File Editor add-on, SSH, Samba, etc.)

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

If `custom_components/` or `www/` don't exist yet, create them.

---

## Step 3 — Create console.yaml

Create `/config/console.yaml` with at least one point. Minimal example:

```yaml
# ─── LOG EXAMPLE ───
DAILY_KWH:
  type: LOG
  cron: "0 0 * * *"
  entity: sensor.energy_meter_kwh
  note: "Daily kWh snapshot at midnight"


# ─── ALARM EXAMPLE ───
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

## Step 4 — Restart Home Assistant

Settings → System → Restart. A full restart is required because this is a custom integration.

---

## Step 5 — Set Up the Integration

### Option A — UI Mode (Recommended)

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration** (bottom right)
3. Search for **HASS Console**
4. Confirm the three paths (defaults are usually correct):
   - **Console YAML path** — `/config/console.yaml`
   - **Alarm CSV output path** — `/config/www/hass-console-alarms.csv`
   - **Log CSV output path** — `/config/www/hass-console-logs.csv`
5. Click **Submit**

You'll see a HASS Console card on the Integrations page with a **Configure** button (to change paths later) and a **⋮ → Reload** option.

### Option B — YAML Mode (Legacy)

Add this one line to `/config/configuration.yaml`:

```yaml
hass_console: !include console.yaml
```

Restart HA again.

> **Note:** In YAML mode, the CSV paths are fixed at the defaults. Use UI mode if you want custom paths.

---

## Step 6 — Register the Lovelace Card

1. **Settings → Dashboards → ⋮ (top right) → Resources**
2. Click **Add Resource**
3. URL: `/local/hass-console-card.js`
4. Type: **JavaScript Module**
5. Click **Create**

---

## Step 7 — Add the Card to a Dashboard

1. Open any dashboard, click **Edit** (pencil icon) → **Add Card**
2. Scroll down and choose **Manual**
3. Paste this:

```yaml
type: custom:hass-console-card
title: HASS Console
alarm_csv: /local/hass-console-alarms.csv
log_csv: /local/hass-console-logs.csv
rows: 200
refresh_interval: 30
```

4. Click **Save**

---

## You're Done

The card will show two tabs — **Alarm** and **Log**. They'll be empty until your first cron fires or an alarm triggers.

To test immediately, go to **Developer Tools → Services** and run:

```yaml
service: hass_console.write_log
data:
  entity: hass_console.log_test
  value: "Hello World"
  note: "Testing the console"
```

Switch to the Log tab on your card, click **↻ Refresh**, and you should see the entry.

---

## Editing Your Configuration

### Adding more points

Open `/config/console.yaml` and add more entries. To pick up the changes without restarting HA:

- **UI Mode:** Settings → Devices & Services → HASS Console → **⋮ → Reload**
- **YAML Mode:** Developer Tools → Services → call `hass_console.reload`

### Changing file paths (UI Mode only)

Settings → Devices & Services → HASS Console → **Configure**. Changes apply immediately.

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
