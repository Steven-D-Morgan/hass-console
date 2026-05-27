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
import yaml

from homeassistant.config_entries import ConfigEntry
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

from .const import (
    DOMAIN,
    CONF_TYPE, CONF_CRON, CONF_ENTITY, CONF_NOTE, CONF_CLASS, CONF_TRIGGER, CONF_CATEGORY,
    CONF_CONSOLE_YAML, CONF_ALARM_CSV, CONF_LOG_CSV,
    DEFAULT_CONSOLE_YAML, DEFAULT_ALARM_CSV, DEFAULT_LOG_CSV,
    ALARM_COLUMNS, LOG_COLUMNS, TIMESTAMP_FORMAT, TYPE_LOG, TYPE_ALARM,
)

_LOGGER = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Cron parsing
# ──────────────────────────────────────────────────────────────────

def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
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
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        _LOGGER.warning("Invalid cron expression: %s", cron_expr)
        return False
    minute, hour, dom, month, dow = fields
    try:
        if now.minute not in _parse_cron_field(minute, 0, 59): return False
        if now.hour not in _parse_cron_field(hour, 0, 23): return False
        if now.day not in _parse_cron_field(dom, 1, 31): return False
        if now.month not in _parse_cron_field(month, 1, 12): return False
        cron_dow = now.isoweekday() % 7
        if cron_dow not in _parse_cron_field(dow, 0, 6): return False
    except (ValueError, TypeError):
        _LOGGER.warning("Failed to parse cron expression: %s", cron_expr)
        return False
    return True


# ──────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────

class HassConsoleEngine:
    """Core engine that manages alarm/log points."""

    def __init__(
        self,
        hass: HomeAssistant,
        points_config: dict[str, Any],
        alarm_csv_path: str,
        log_csv_path: str,
    ) -> None:
        self.hass = hass
        self.config = points_config
        self.points: dict[str, dict] = {}
        self._alarm_states: dict[str, dict] = {}
        self._unsub_listeners: list = []
        self._alarm_csv = Path(alarm_csv_path)
        self._log_csv = Path(log_csv_path)
        self._alarm_lock = asyncio.Lock()
        self._log_lock = asyncio.Lock()

    async def async_setup(self) -> None:
        await self.hass.async_add_executor_job(self._ensure_csvs)
        self._parse_points()
        await self._setup_cron_scanner()
        self._setup_alarm_listeners()
        _LOGGER.info("HASS Console engine started: %d points loaded", len(self.points))

    def _ensure_csvs(self) -> None:
        """Create CSVs if missing, or migrate them to the current schema."""
        self._alarm_csv.parent.mkdir(parents=True, exist_ok=True)
        self._log_csv.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_or_create(self._alarm_csv, ALARM_COLUMNS)
        self._migrate_or_create(self._log_csv, LOG_COLUMNS)

    def _migrate_or_create(self, path: Path, expected_columns: list[str]) -> None:
        """Create the CSV with the expected header, or migrate an existing one."""
        if not path.exists():
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(expected_columns)
            _LOGGER.info("Created CSV at %s", path)
            return

        # Read existing header
        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            try:
                existing_header = next(reader)
            except StopIteration:
                existing_header = []

        if existing_header == expected_columns:
            return

        # Migrate: read all rows as dicts, fill missing columns with "", write back
        _LOGGER.info(
            "Migrating CSV %s: %s -> %s",
            path, existing_header, expected_columns,
        )
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=expected_columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in expected_columns})

    def _parse_points(self) -> None:
        for name, point_cfg in self.config.items():
            if not isinstance(point_cfg, dict):
                continue
            point_type = str(point_cfg.get(CONF_TYPE, "")).upper()
            if point_type not in (TYPE_LOG, TYPE_ALARM):
                _LOGGER.warning("Point '%s' has invalid type '%s', skipping", name, point_type)
                continue
            header = name.upper()
            entity_id = f"hass_console.{point_type.lower()}_{header.lower()}"
            self.points[name] = {
                "name": name, "header": header, "type": point_type,
                "entity_id": entity_id,
                "source_entity": point_cfg.get(CONF_ENTITY),
                "cron": point_cfg.get(CONF_CRON),
                "note": point_cfg.get(CONF_NOTE, ""),
                "class": point_cfg.get(CONF_CLASS, ""),
                "category": str(point_cfg.get(CONF_CATEGORY, "")).strip(),
                "trigger": point_cfg.get(CONF_TRIGGER, []),
            }

    async def _setup_cron_scanner(self) -> None:
        @callback
        def _cron_tick(now: datetime) -> None:
            for name, point in self.points.items():
                if point["type"] != TYPE_LOG: continue
                cron_expr = point.get("cron")
                if not cron_expr: continue
                if cron_matches_now(cron_expr, now):
                    self.hass.async_create_task(self._record_log_point(point, now))

        self._unsub_listeners.append(
            async_track_time_interval(self.hass, _cron_tick, timedelta(minutes=1))
        )

    def _setup_alarm_listeners(self) -> None:
        for name, point in self.points.items():
            if point["type"] != TYPE_ALARM: continue
            for trig in point.get("trigger", []):
                if not isinstance(trig, dict): continue
                if trig.get(CONF_PLATFORM, trig.get("platform")) != "numeric_state": continue

                target_entity = trig.get(
                    CONF_ENTITY_ID,
                    trig.get("entity_id", point.get("source_entity")),
                )
                if not target_entity: continue

                above = trig.get(CONF_ABOVE, trig.get("above"))
                below = trig.get(CONF_BELOW, trig.get("below"))
                for_d = trig.get(CONF_FOR, trig.get("for", {}))
                alias = trig.get(CONF_ALIAS, trig.get("alias", name))
                dur_seconds = (
                    for_d.get("hours", 0) * 3600 +
                    for_d.get("minutes", 0) * 60 +
                    for_d.get("seconds", 0)
                ) if isinstance(for_d, dict) else 0

                alarm_key = f"{name}_{target_entity}_{alias}"
                self._alarm_states[alarm_key] = {
                    "active": False, "triggered_at": None, "recorded": False,
                    "point": point, "above": above, "below": below,
                    "duration": dur_seconds, "alias": alias, "entity_id": target_entity,
                }

                @callback
                def _state_changed(event: Event, _key: str = alarm_key) -> None:
                    self.hass.async_create_task(self._evaluate_alarm(_key, event))

                self._unsub_listeners.append(
                    async_track_state_change_event(self.hass, target_entity, _state_changed)
                )

    async def _evaluate_alarm(self, key: str, event: Event) -> None:
        alarm = self._alarm_states.get(key)
        if not alarm: return
        new_state: State | None = event.data.get("new_state")
        if new_state is None: return
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
                await self._record_alarm_point(alarm["point"], now, value, elapsed, alarm["alias"])
                alarm["recorded"] = True
        elif not condition_met and alarm["active"]:
            alarm["active"] = False
            alarm["triggered_at"] = None
            alarm["recorded"] = False

    async def _record_log_point(self, point: dict, now: datetime) -> None:
        source = point.get("source_entity")
        value = ""
        if source:
            state = self.hass.states.get(source)
            if state: value = state.state
        row = {
            "timestamp": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
            "entity": point["entity_id"],
            "value": value,
            "note": point.get("note", ""),
        }
        await self._write_log_row(row)
        self.hass.states.async_set(
            point["entity_id"], value,
            {
                "friendly_name": f"HASS Console Log: {point['header']}",
                "last_logged": now.strftime(TIMESTAMP_FORMAT),
                "category": point.get("category", ""),
                "note": point.get("note", ""),
            },
        )
        _LOGGER.info("LOG recorded: %s = %s", point["entity_id"], value)

    async def _record_alarm_point(
        self, point: dict, now: datetime,
        value: float, duration: float, alias: str,
    ) -> None:
        dur_str = str(timedelta(seconds=int(duration)))
        row = {
            "timestamp": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
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
                "last_alarm": now.strftime(TIMESTAMP_FORMAT),
                "category": point.get("category", ""),
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
        async with self._alarm_lock:
            await self.hass.async_add_executor_job(
                self._write_row_sync, self._alarm_csv, row, ALARM_COLUMNS
            )

    async def _write_log_row(self, row: dict) -> None:
        async with self._log_lock:
            await self.hass.async_add_executor_job(
                self._write_row_sync, self._log_csv, row, LOG_COLUMNS
            )

    def _write_row_sync(self, path: Path, row: dict, columns: list[str]) -> None:
        with open(path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=columns).writerow(row)

    async def async_teardown(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _load_yaml_sync(path: str) -> dict[str, Any]:
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError) as err:
        _LOGGER.error("Failed to load %s: %s", path, err)
        return {}


# ──────────────────────────────────────────────────────────────────
# Setup — YAML mode (legacy)
# ──────────────────────────────────────────────────────────────────

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    _register_services(hass)

    if DOMAIN not in config:
        return True

    points_config = config[DOMAIN]
    engine = HassConsoleEngine(hass, points_config, DEFAULT_ALARM_CSV, DEFAULT_LOG_CSV)
    hass.data.setdefault(DOMAIN, {})["_yaml_engine"] = engine

    async def _start(event: Event) -> None:
        await engine.async_setup()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)
    _LOGGER.info("HASS Console set up via YAML (legacy mode)")
    return True


# ──────────────────────────────────────────────────────────────────
# Setup — Config Entry mode (UI)
# ──────────────────────────────────────────────────────────────────

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    settings = {**entry.data, **entry.options}
    yaml_path = settings.get(CONF_CONSOLE_YAML, DEFAULT_CONSOLE_YAML)
    alarm_csv = settings.get(CONF_ALARM_CSV, DEFAULT_ALARM_CSV)
    log_csv = settings.get(CONF_LOG_CSV, DEFAULT_LOG_CSV)

    points = await hass.async_add_executor_job(_load_yaml_sync, yaml_path)

    engine = HassConsoleEngine(hass, points, alarm_csv, log_csv)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = engine

    if hass.is_running:
        await engine.async_setup()
    else:
        async def _start(event: Event) -> None:
            await engine.async_setup()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info(
        "HASS Console set up via config entry (yaml=%s, alarms=%s, logs=%s, points=%d)",
        yaml_path, alarm_csv, log_csv, len(points),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.get(DOMAIN, {})
    engine: HassConsoleEngine | None = domain_data.pop(entry.entry_id, None)
    if engine:
        await engine.async_teardown()
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


# ──────────────────────────────────────────────────────────────────
# Services
# ──────────────────────────────────────────────────────────────────

def _get_active_engine(hass: HomeAssistant) -> HassConsoleEngine | None:
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        return None
    for key, value in domain_data.items():
        if key != "_yaml_engine" and isinstance(value, HassConsoleEngine):
            return value
    return domain_data.get("_yaml_engine")


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "write_log"):
        return

    async def _handle_write_log(call) -> None:
        engine = _get_active_engine(hass)
        if not engine: return
        row = {
            "timestamp": dt_util.now().strftime(TIMESTAMP_FORMAT),
            "category": call.data.get("category", ""),
            "entity": call.data.get("entity", ""),
            "value": call.data.get("value", ""),
            "note": call.data.get("note", ""),
        }
        await engine._write_log_row(row)

    async def _handle_write_alarm(call) -> None:
        engine = _get_active_engine(hass)
        if not engine: return
        row = {
            "timestamp": dt_util.now().strftime(TIMESTAMP_FORMAT),
            "category": call.data.get("category", ""),
            "entity": call.data.get("entity", ""),
            "class": call.data.get("class", ""),
            "value": call.data.get("value", ""),
            "duration": call.data.get("duration", ""),
            "note": call.data.get("note", ""),
            "trigger": call.data.get("trigger", ""),
        }
        await engine._write_alarm_row(row)

    async def _handle_reload(call) -> None:
        entries = hass.config_entries.async_entries(DOMAIN)
        if entries:
            for entry in entries:
                await hass.config_entries.async_reload(entry.entry_id)
            _LOGGER.info("Reloaded %d HASS Console entries", len(entries))
            return
        engine = _get_active_engine(hass)
        if engine:
            await engine.async_teardown()
            await engine.async_setup()
            _LOGGER.info("Reloaded YAML-mode HASS Console engine")

    hass.services.async_register(
        DOMAIN, "write_log", _handle_write_log,
        schema=vol.Schema({
            vol.Required("entity"): cv.string,
            vol.Optional("category", default=""): cv.string,
            vol.Optional("value", default=""): cv.string,
            vol.Optional("note", default=""): cv.string,
        }),
    )
    hass.services.async_register(
        DOMAIN, "write_alarm", _handle_write_alarm,
        schema=vol.Schema({
            vol.Required("entity"): cv.string,
            vol.Optional("category", default=""): cv.string,
            vol.Optional("class", default=""): cv.string,
            vol.Optional("value", default=""): cv.string,
            vol.Optional("duration", default=""): cv.string,
            vol.Optional("note", default=""): cv.string,
            vol.Optional("trigger", default=""): cv.string,
        }),
    )
    hass.services.async_register(DOMAIN, "reload", _handle_reload)
