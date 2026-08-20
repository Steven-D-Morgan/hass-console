# HASS Console — Simple Setup

A step-by-step guide to get HASS Console running. Total time: ~5 minutes.

**As of 3.0.0**, points are added from the UI (Settings → Devices & Services → HASS Console → ADD) — same UX as automations. `console.yaml` still works but is deprecated and will be removed in a future major release.

---

## What You Need

- Home Assistant (2025.3 or newer)
- Access to your HA config directory (File Editor add-on, SSH, Samba, etc.)

---

## Step 1 — Download

Download the [latest release](https://github.com/Steven-D-Morgan/hass-console/releases/latest) `.tar.gz` and extract it, or clone the repo:

```bash
git clone https://github.com/Steven-D-Morgan/hass-console.git
```

---

## Step 2 — Copy the Integration Folder

Copy this into your Home Assistant config directory:

| From | To |
|------|----|
| `custom_components/hass_console/` | `/config/custom_components/hass_console/` |

If `custom_components/` doesn't exist yet, create it. The Lovelace cards ship **inside** this folder and load automatically — there's nothing to copy into `/config/www/` and no resource to register.

---

## Step 3 — Restart Home Assistant

Settings → System → Restart. A full restart is required because this is a custom integration.

---

## Step 4 — Add the Integration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration** (bottom right)
3. Search for **HASS Console**
4. On the setup form, confirm the CSV paths (defaults are usually correct):
   - **Alarm CSV output path** — `/config/www/hass-console/alarms.csv`
   - **Log CSV output path** — `/config/www/hass-console/logs.csv`
   - **Console YAML path** — leave blank if you're not using the legacy YAML file
5. Click **Submit**

You'll see a HASS Console card on the Integrations page with an **ADD** button (for new points), a **Configure** button (to change paths later), and a **⋮ → Reload** option.

---

## Step 5 — Add Your First Points

On the HASS Console integration card, click **ADD**.

### Add a LOG point

Pick **Add LOG point** and fill in:

| Field | Example |
|-------|---------|
| Point name | `DAILY_KWH` |
| Cron schedule | `0 0 * * *` (daily at midnight) |
| Entity to snapshot | `sensor.energy_meter_kwh` |
| Category | `E-METER` |
| Note | `Daily kWh snapshot at midnight` |

Click **Submit**. You now have `hass_console.log_daily_kwh` — an entity that captures the meter reading every midnight and writes a row to `logs.csv`.

### Add an ALARM point

Click **ADD** again and pick **Add ALARM point**.

1. On the header form:
   - Point name: `TEMPERATURE_ALARM`
   - Severity: `01 — Critical`
   - Primary entity: `sensor.network_closet_temperature`
   - Note: `Network closet overheat`
2. On the **Triggers** step, pick **Add trigger** and fill in:
   - Trigger type: **Numeric threshold**
   - Entity to monitor: `sensor.network_closet_temperature`
   - Above: `78`
   - For — minutes: `10`
   - Alias: `Above 78°F for 10 min`
3. Back on the Triggers step, pick **Save alarm point**.

You now have `hass_console.alarm_temperature_alarm` — an entity that flips to `ALARM` and writes a row to `alarms.csv` when the closet stays above 78°F for 10 minutes.

---

## Step 6 — Add the Card to a Dashboard

1. Open any dashboard, click **Edit** (pencil icon) → **Add Card**
2. Scroll down and choose **Manual**
3. Paste this:

```yaml
type: custom:hass-console-card
title: HASS Console
alarm_csv: /local/hass-console/alarms.csv
log_csv: /local/hass-console/logs.csv
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

### Adding, editing, or deleting points

- **Add** — Settings → Devices & Services → HASS Console → **ADD**
- **Edit** — click any point in the list → **Configure**
- **Delete** — the **⋮** menu on a point

The engine reloads automatically after each change. No HA restart or manual reload needed.

### Changing file paths

Settings → Devices & Services → HASS Console → **Configure**. Changes apply immediately.

### Legacy console.yaml

If you're upgrading from 2.x, existing `console.yaml` points keep working. A Repairs issue lists how many are still YAML-only — migrate them by adding each one through the UI, then remove them from `console.yaml`. UI points always take precedence when names collide.

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
