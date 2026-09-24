# Cookbook

Worked examples and copy-pasteable recipes for **HASS Console**. The [README](README.md) explains *what* the integration does; this file collects the *how* — real dashboards, real automations, real point definitions that people can lift verbatim into their own setups.

Recipes will land here as they're written. Each one should follow the shape below so the file stays scannable.

---

## Recipe template

```markdown
### <One-line goal, e.g. "Acknowledge a Critical from the mobile notification">

**Why you'd want this:** <one or two sentences>

**What you need:** <HA version, HASS Console version, any extras — mobile companion, notify service, etc.>

**Steps:**
1. …
2. …

**YAML / config:**
```yaml
# minimal, complete, paste-and-go
```

**Notes / gotchas:** <edge cases, follow-ups, links to related recipes>
```

---

## Planned recipes

_Placeholders — fill in as they're written._

- [ ] Acknowledge a Critical alarm straight from the mobile notification (actionable notification payload)
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
