"""HASS Console - Alarm & Log Engine for Home Assistant."""
from __future__ import annotations

import asyncio
import csv
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_ALIAS,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_FOR,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hass_console"
CONF_TYPE = "type"
CONF_CRON = "cron"
CONF_ENTITY = "entity"
CONF_NOTE = "note"
CONF_CLASS = "class"
CONF_TRIGGER = "trigger"

ALARM_CSV_PATH = "/config/www/hass-console-alarms.csv"
LOG_CSV_PATH = "/config/www/hass-console-logs.csv"

ALARM_COLUMNS = ["timestamp", "entity", "class", "value", "duration", "note", "trigger"]
LOG_COLUMNS = ["timestamp", "entity", "value", "note"]

TYPE_LOG = "LOG"
TYPE_ALARM = "ALARM"


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field into a set of matching integers."""
    values = set()
    for part in field.split(","):
        part = part.strip()
        step = None
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)

        if part == "*":
            start, end = min_val, max_val
        elif "-" in part:
            s, e = part.split("-", 1)
            start, end = int(s), int(e)
        else:
            start = end = int(part)

        if step:
            values.update(range(start, end + 1, step))
        else:
            values.update(range(start, end + 1))
    return values


def cron_matches_now(cron_expr: str, now: datetime) -> bool:
    """Check if a 5-field cron expression matches the given datetime."""
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        _LOGGER.warning("Invalid cron expression: %s", cron_expr)
        return False

    minute, hour, dom, month, dow = fields

    try:
        if now.minute not in _parse_cron_field(minute, 0, 59):
            return False
        if now.hour not in _parse_cron_field(hour, 0, 23):
            return False
        if now.day not in _parse_cron_field(dom, 1, 31):
            return False
        if now.month not in _parse_cron_field(month, 1, 12):
            return False
        cron_dow = now.isoweekday() % 7
        if cron_dow not in _parse_cron_field(dow, 0, 6):
            return False
    except (ValueError, TypeError):
        _LOGGER.warning("Failed to parse cron expression: %s", cron_expr)
        return False

    return True


class HassConsoleEngine:
    """Core engine that manages alarm/log points."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self.points: dict[str, dict] = {}
        self._alarm_states: dict[str, dict] = {}
        self._unsub_listeners: list = []
        self._alarm_csv = Path(ALARM_CSV_PATH)
        self._log_csv = Path(LOG_CSV_PATH)
        self._alarm_lock = asyncio.Lock()
        self._log_lock = asyncio.Lock()

    async def async_setup(self) -> None:
        """Initialize the engine: parse config, create CSVs, start listeners."""
        self._ensure_csvs()
        self._parse_points()
        await self._setup_cron_scanner()
        self._setup_alarm_listeners()
        _LOGGER.info(
            "HASS Console engine started: %d points loaded", len(self.points)
        )

    def _ensure_csvs(self) -> None:
        """Create CSV files with headers if they don't exist."""
        self._alarm_csv.parent.mkdir(parents=True, exist_ok=True)

        if not self._alarm_csv.exists():
            with open(self._alarm_csv, "w", newline="") as f:
                csv.writer(f).writerow(ALARM_COLUMNS)
            _LOGGER.info("Created alarm CSV at %s", self._alarm_csv)

        if not self._log_csv.exists():
            with open(self._log_csv, "w", newline="") as f:
                csv.writer(f).writerow(LOG_COLUMNS)
            _LOGGER.info("Created log CSV at %s", self._log_csv)

    def _parse_points(self) -> None:
        """Parse all point definitions from the hass_console config."""
        for name, point_cfg in self.config.items():
            if not isinstance(point_cfg, dict):
                continue
            point_type = str(point_cfg.get(CONF_TYPE, "")).upper()
            if point_type not in (TYPE_LOG, TYPE_ALARM):
                _LOGGER.warning(
                    "HASS Console point '%s' has invalid type '%s', skipping",
                    name, point_type,
                )
                continue

            header = name.upper()
            entity_id = f"hass_console.{point_type.lower()}_{header.lower()}"

            point = {
                "name": name,
                "header": header,
                "type": point_type,
                "entity_id": entity_id,
                "source_entity": point_cfg.get(CONF_ENTITY),
                "cron": point_cfg.get(CONF_CRON),
                "note": point_cfg.get(CONF_NOTE, ""),
                "class": point_cfg.get(CONF_CLASS, ""),
                "trigger": point_cfg.get(CONF_TRIGGER, []),
            }
            self.points[name] = point
            _LOGGER.debug("Loaded hass_console point: %s -> %s", name, entity_id)

    async def _setup_cron_scanner(self) -> None:
        """Run a per-minute scanner that checks LOG-type cron schedules."""

        @callback
        def _cron_tick(now: datetime) -> None:
            for name, point in self.points.items():
                if point["type"] != TYPE_LOG:
                    continue
                cron_expr = point.get("cron")
                if not cron_expr:
                    continue
                if cron_matches_now(cron_expr, now):
                    self.hass.async_create_task(
                        self._record_log_point(point, now)
                    )

        self._unsub_listeners.append(
            async_track_time_interval(
                self.hass, _cron_tick, timedelta(minutes=1)
            )
        )

    def _setup_alarm_listeners(self) -> None:
        """Set up state listeners for ALARM-type points."""
        for name, point in self.points.items():
            if point["type"] != TYPE_ALARM:
                continue
            triggers = point.get("trigger", [])
            for trig in triggers:
                if not isinstance(trig, dict):
                    continue
                platform = trig.get(CONF_PLATFORM, trig.get("platform"))
                if platform != "numeric_state":
                    continue

                target_entity = trig.get(
                    CONF_ENTITY_ID,
                    trig.get("entity_id", point.get("source_entity")),
                )
                if not target_entity:
                    continue

                above = trig.get(CONF_ABOVE, trig.get("above"))
                below = trig.get(CONF_BELOW, trig.get("below"))
                for_duration = trig.get(CONF_FOR, trig.get("for", {}))
                alias = trig.get(CONF_ALIAS, trig.get("alias", name))

                if isinstance(for_duration, dict):
                    dur_seconds = (
                        for_duration.get("hours", 0) * 3600
                        + for_duration.get("minutes", 0) * 60
                        + for_duration.get("seconds", 0)
                    )
                else:
                    dur_seconds = 0

                alarm_key = f"{name}_{target_entity}_{alias}"
                self._alarm_states[alarm_key] = {
                    "active": False,
                    "triggered_at": None,
                    "recorded": False,
                    "point": point,
                    "above": above,
                    "below": below,
                    "duration": dur_seconds,
                    "alias": alias,
                    "entity_id": target_entity,
                }

                @callback
                def _state_changed(
                    event: Event,
                    _key: str = alarm_key,
                ) -> None:
                    self.hass.async_create_task(
                        self._evaluate_alarm(_key, event)
                    )

                self._unsub_listeners.append(
                    async_track_state_change_event(
                        self.hass, target_entity, _state_changed
                    )
                )
                _LOGGER.debug(
                    "Alarm listener on %s for point %s (key=%s)",
                    target_entity, name, alarm_key,
                )

    async def _evaluate_alarm(self, key: str, event: Event) -> None:
        """Evaluate whether an alarm condition is met."""
        alarm = self._alarm_states.get(key)
        if not alarm:
            return

        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return

        try:
            value = float(new_state.state)
        except (ValueError, TypeError):
            return

        condition_met = True
        if alarm["above"] is not None and value <= float(alarm["above"]):
            condition_met = False
        if alarm["below"] is not None and value >= float(alarm["below"]):
            condition_met = False

        now = dt_util.now()

        if condition_met and not alarm["active"]:
            alarm["active"] = True
            alarm["triggered_at"] = now
            alarm["recorded"] = False

        elif condition_met and alarm["active"] and not alarm["recorded"]:
            elapsed = (now - alarm["triggered_at"]).total_seconds()
            if elapsed >= alarm["duration"]:
                await self._record_alarm_point(
                    alarm["point"], now, value, elapsed, alarm["alias"],
                )
                alarm["recorded"] = True

        elif not condition_met and alarm["active"]:
            alarm["active"] = False
            alarm["triggered_at"] = None
            alarm["recorded"] = False

    async def _record_log_point(self, point: dict, now: datetime) -> None:
        """Read the source entity and write a LOG row to CSV."""
        source = point.get("source_entity")
        value = ""
        if source:
            state = self.hass.states.get(source)
            if state:
                value = state.state

        row = {
            "timestamp": now.isoformat(),
            "entity": point["entity_id"],
            "value": value,
            "note": point.get("note", ""),
        }
        await self._write_log_row(row)

        self.hass.states.async_set(
            point["entity_id"], value,
            {
                "friendly_name": f"HASS Console Log: {point['header']}",
                "last_logged": now.isoformat(),
                "note": point.get("note", ""),
                "unit_of_measurement": "",
            },
        )
        _LOGGER.info("LOG recorded: %s = %s", point["entity_id"], value)

    async def _record_alarm_point(
        self, point: dict, now: datetime,
        value: float, duration: float, alias: str,
    ) -> None:
        """Write an ALARM row to CSV."""
        dur_str = str(timedelta(seconds=int(duration)))
        row = {
            "timestamp": now.isoformat(),
            "entity": point["entity_id"],
            "class": point.get("class", ""),
            "value": str(value),
            "duration": dur_str,
            "note": point.get("note", ""),
            "trigger": alias,
        }
        await self._write_alarm_row(row)

        self.hass.states.async_set(
            point["entity_id"], "ALARM",
            {
                "friendly_name": f"HASS Console Alarm: {point['header']}",
                "last_alarm": now.isoformat(),
                "class": point.get("class", ""),
                "value": str(value),
                "duration": dur_str,
                "trigger": alias,
            },
        )
        _LOGGER.info(
            "ALARM recorded: %s triggered by '%s' (value=%s, dur=%s)",
            point["entity_id"], alias, value, dur_str,
        )

    async def _write_alarm_row(self, row: dict) -> None:
        """Append a row to the alarm CSV (thread-safe)."""
        async with self._alarm_lock:
            await self.hass.async_add_executor_job(
                self._write_row_sync, self._alarm_csv, row, ALARM_COLUMNS
            )

    async def _write_log_row(self, row: dict) -> None:
        """Append a row to the log CSV (thread-safe)."""
        async with self._log_lock:
            await self.hass.async_add_executor_job(
                self._write_row_sync, self._log_csv, row, LOG_COLUMNS
            )

    def _write_row_sync(self, path: Path, row: dict, columns: list[str]) -> None:
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writerow(row)

    async def async_teardown(self) -> None:
        """Unsubscribe all listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up HASS Console integration from configuration.yaml."""
    if DOMAIN not in config:
        return True

    console_config = config[DOMAIN]
    engine = HassConsoleEngine(hass, console_config)
    hass.data[DOMAIN] = engine

    async def _start(event: Event) -> None:
        await engine.async_setup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)

    hass.services.async_register(
        DOMAIN, "write_log", _handle_write_log,
        schema=vol.Schema({
            vol.Required("entity"): cv.string,
            vol.Optional("value", default=""): cv.string,
            vol.Optional("note", default=""): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN, "write_alarm", _handle_write_alarm,
        schema=vol.Schema({
            vol.Required("entity"): cv.string,
            vol.Optional("class", default=""): cv.string,
            vol.Optional("value", default=""): cv.string,
            vol.Optional("duration", default=""): cv.string,
            vol.Optional("note", default=""): cv.string,
            vol.Optional("trigger", default=""): cv.string,
        }),
    )

    hass.services.async_register(DOMAIN, "reload", _handle_reload)

    return True


async def _handle_write_log(call) -> None:
    """Service: hass_console.write_log"""
    hass = call.hass if hasattr(call, "hass") else None
    if not hass:
        return
    engine: HassConsoleEngine = hass.data.get(DOMAIN)
    if not engine:
        return

    row = {
        "timestamp": dt_util.now().isoformat(),
        "entity": call.data.get("entity", ""),
        "value": call.data.get("value", ""),
        "note": call.data.get("note", ""),
    }
    await engine._write_log_row(row)


async def _handle_write_alarm(call) -> None:
    """Service: hass_console.write_alarm"""
    hass = call.hass if hasattr(call, "hass") else None
    if not hass:
        return
    engine: HassConsoleEngine = hass.data.get(DOMAIN)
    if not engine:
        return

    row = {
        "timestamp": dt_util.now().isoformat(),
        "entity": call.data.get("entity", ""),
        "class": call.data.get("class", ""),
        "value": call.data.get("value", ""),
        "duration": call.data.get("duration", ""),
        "note": call.data.get("note", ""),
        "trigger": call.data.get("trigger", ""),
    }
    await engine._write_alarm_row(row)


async def _handle_reload(call) -> None:
    """Service: hass_console.reload"""
    hass = call.hass if hasattr(call, "hass") else None
    if not hass:
        return
    engine: HassConsoleEngine | None = hass.data.get(DOMAIN)
    if engine:
        await engine.async_teardown()
        await engine.async_setup()
        _LOGGER.info("HASS Console engine reloaded")
