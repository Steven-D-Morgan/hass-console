"""HASS Console - Alarm & Log Engine for Home Assistant."""
from __future__ import annotations

import asyncio
import csv
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol
import yaml

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ALIAS, CONF_ENTITY_ID, CONF_PLATFORM,
    CONF_ABOVE, CONF_BELOW, CONF_FOR,
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
    CONF_TYPE, CONF_CRON, CONF_ENTITY, CONF_NOTE, CONF_CLASS,
    CONF_TRIGGER, CONF_CATEGORY,
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
        values.update(range(start, end + 1, step) if step else range(start, end + 1))
    return values


def cron_matches_now(cron_expr: str, now: datetime) -> bool:
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    try:
        if now.minute not in _parse_cron_field(minute, 0, 59): return False
        if now.hour not in _parse_cron_field(hour, 0, 23): return False
        if now.day not in _parse_cron_field(dom, 1, 31): return False
        if now.month not in _parse_cron_field(month, 1, 12): return False
        if (now.isoweekday() % 7) not in _parse_cron_field(dow, 0, 6): return False
    except (ValueError, TypeError):
        return False
    return True


def _gen_id() -> str:
    """Generate a short unique ID for an alarm row."""
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────

class HassConsoleEngine:

    def __init__(
        self, hass: HomeAssistant, points_config: dict[str, Any],
        alarm_csv_path: str, log_csv_path: str,
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
        self._alarm_csv.parent.mkdir(parents=True, exist_ok=True)
        self._log_csv.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_or_create(self._alarm_csv, ALARM_COLUMNS, generate_ids=True)
        self._migrate_or_create(self._log_csv, LOG_COLUMNS, generate_ids=False)

    def _migrate_or_create(
        self, path: Path, expected: list[str], generate_ids: bool = False,
    ) -> None:
        if not path.exists():
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(expected)
            _LOGGER.info("Created CSV at %s", path)
            return

        with open(path, "r", newline="") as f:
            reader = csv.reader(f)
            try:
                header = [h.strip() for h in next(reader)]
            except StopIteration:
                header = []

        if header == expected:
            return

        _LOGGER.info("Migrating CSV %s to new schema", path)
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=expected)
            writer.writeheader()
            for row in rows:
                filled = {col: row.get(col, "") for col in expected}
                if generate_ids and not filled.get("id"):
                    filled["id"] = _gen_id()
                writer.writerow(filled)

    def _parse_points(self) -> None:
        for name, pcfg in self.config.items():
            if not isinstance(pcfg, dict):
                continue
            pt = str(pcfg.get(CONF_TYPE, "")).upper()
            if pt not in (TYPE_LOG, TYPE_ALARM):
                continue
            header = name.upper()
            eid = f"hass_console.{pt.lower()}_{header.lower()}"
            self.points[name] = {
                "name": name, "header": header, "type": pt, "entity_id": eid,
                "source_entity": pcfg.get(CONF_ENTITY),
                "cron": pcfg.get(CONF_CRON),
                "note": pcfg.get(CONF_NOTE, ""),
                "class": pcfg.get(CONF_CLASS, ""),
                "category": str(pcfg.get(CONF_CATEGORY, "")).strip(),
                "trigger": pcfg.get(CONF_TRIGGER, []),
            }

    # ── Cron (LOG) ──

    async def _setup_cron_scanner(self) -> None:
        @callback
        def _tick(now):
            for point in self.points.values():
                if point["type"] != TYPE_LOG: continue
                cron = point.get("cron")
                if cron and cron_matches_now(cron, now):
                    self.hass.async_create_task(self._record_log(point, now))
        self._unsub_listeners.append(
            async_track_time_interval(self.hass, _tick, timedelta(minutes=1))
        )

    # ── Alarm listeners ──

    def _setup_alarm_listeners(self) -> None:
        for name, point in self.points.items():
            if point["type"] != TYPE_ALARM: continue
            for trig in point.get("trigger", []):
                if not isinstance(trig, dict): continue
                if trig.get(CONF_PLATFORM, trig.get("platform")) != "numeric_state": continue
                target = trig.get(CONF_ENTITY_ID, trig.get("entity_id", point.get("source_entity")))
                if not target: continue
                above = trig.get(CONF_ABOVE, trig.get("above"))
                below = trig.get(CONF_BELOW, trig.get("below"))
                for_d = trig.get(CONF_FOR, trig.get("for", {}))
                alias = trig.get(CONF_ALIAS, trig.get("alias", name))
                dur = (
                    for_d.get("hours", 0) * 3600 +
                    for_d.get("minutes", 0) * 60 +
                    for_d.get("seconds", 0)
                ) if isinstance(for_d, dict) else 0

                akey = f"{name}_{target}_{alias}"
                self._alarm_states[akey] = {
                    "active": False, "triggered_at": None, "recorded": False,
                    "point": point, "above": above, "below": below,
                    "duration": dur, "alias": alias, "entity_id": target,
                }

                @callback
                def _changed(event, _k=akey):
                    self.hass.async_create_task(self._eval_alarm(_k, event))
                self._unsub_listeners.append(
                    async_track_state_change_event(self.hass, target, _changed)
                )

    async def _eval_alarm(self, key, event):
        a = self._alarm_states.get(key)
        if not a: return
        ns = event.data.get("new_state")
        if not ns: return
        try:
            val = float(ns.state)
        except (ValueError, TypeError):
            return
        ok = True
        if a["above"] is not None and val <= float(a["above"]): ok = False
        if a["below"] is not None and val >= float(a["below"]): ok = False
        now = dt_util.now()
        if ok and not a["active"]:
            a["active"], a["triggered_at"], a["recorded"] = True, now, False
        elif ok and a["active"] and not a["recorded"]:
            if (now - a["triggered_at"]).total_seconds() >= a["duration"]:
                await self._record_alarm(a["point"], now, val,
                    (now - a["triggered_at"]).total_seconds(), a["alias"])
                a["recorded"] = True
        elif not ok and a["active"]:
            a["active"], a["triggered_at"], a["recorded"] = False, None, False

    # ── Record rows ──

    async def _record_log(self, point, now):
        src = point.get("source_entity")
        val = ""
        if src:
            s = self.hass.states.get(src)
            if s: val = s.state
        row = {
            "timestamp": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
            "entity": point["entity_id"],
            "value": val,
            "note": point.get("note", ""),
        }
        await self._write_log_row(row)
        self.hass.states.async_set(point["entity_id"], val, {
            "friendly_name": f"HASS Console Log: {point['header']}",
            "last_logged": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
            "note": point.get("note", ""),
        })

    async def _record_alarm(self, point, now, value, duration, alias):
        dur_str = str(timedelta(seconds=int(duration)))
        row = {
            "id": _gen_id(),
            "timestamp": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
            "entity": point["entity_id"],
            "class": point.get("class", ""),
            "value": str(value),
            "duration": dur_str,
            "note": point.get("note", ""),
            "trigger": alias,
            "ack": "",
        }
        await self._write_alarm_row(row)
        self.hass.states.async_set(point["entity_id"], "ALARM", {
            "friendly_name": f"HASS Console Alarm: {point['header']}",
            "last_alarm": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
            "class": point.get("class", ""),
            "value": str(value),
            "duration": dur_str,
            "trigger": alias,
        })
        _LOGGER.info("ALARM: %s → '%s' (val=%s dur=%s)", point["entity_id"], alias, value, dur_str)

    # ── CSV writers ──

    async def _write_alarm_row(self, row):
        async with self._alarm_lock:
            await self.hass.async_add_executor_job(
                self._append_sync, self._alarm_csv, row, ALARM_COLUMNS)

    async def _write_log_row(self, row):
        async with self._log_lock:
            await self.hass.async_add_executor_job(
                self._append_sync, self._log_csv, row, LOG_COLUMNS)

    def _append_sync(self, path, row, cols):
        with open(path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=cols).writerow(row)

    # ── Acknowledge ──

    async def acknowledge_alarm(self, alarm_id: str, note: str = "") -> bool:
        """Mark a single alarm as acknowledged. Returns True if found."""
        async with self._alarm_lock:
            return await self.hass.async_add_executor_job(
                self._ack_sync, alarm_id, note)

    async def acknowledge_all(self, note: str = "") -> int:
        """Acknowledge all unacknowledged alarms. Returns count."""
        async with self._alarm_lock:
            return await self.hass.async_add_executor_job(
                self._ack_all_sync, note)

    def _ack_sync(self, alarm_id: str, note: str) -> bool:
        rows = self._read_alarm_rows()
        found = False
        for row in rows:
            if row.get("id") == alarm_id and not row.get("ack"):
                row["ack"] = dt_util.now().strftime(TIMESTAMP_FORMAT)
                found = True
                break
        if found:
            self._write_alarm_rows(rows)
        return found

    def _ack_all_sync(self, note: str) -> int:
        rows = self._read_alarm_rows()
        now_str = dt_util.now().strftime(TIMESTAMP_FORMAT)
        count = 0
        for row in rows:
            if not row.get("ack"):
                row["ack"] = now_str
                count += 1
        if count:
            self._write_alarm_rows(rows)
        return count

    def _read_alarm_rows(self) -> list[dict]:
        if not self._alarm_csv.exists():
            return []
        with open(self._alarm_csv, "r", newline="") as f:
            return list(csv.DictReader(f))

    def _write_alarm_rows(self, rows: list[dict]) -> None:
        with open(self._alarm_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ALARM_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({c: row.get(c, "") for c in ALARM_COLUMNS})

    async def async_teardown(self):
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _load_yaml_sync(path):
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError) as err:
        _LOGGER.error("Failed to load %s: %s", path, err)
        return {}


def _get_active_engine(hass):
    d = hass.data.get(DOMAIN, {})
    if not d: return None
    for k, v in d.items():
        if k != "_yaml_engine" and isinstance(v, HassConsoleEngine):
            return v
    return d.get("_yaml_engine")


# ──────────────────────────────────────────────────────────────────
# Setup — YAML mode (legacy)
# ──────────────────────────────────────────────────────────────────

async def async_setup(hass, config):
    _register_services(hass)
    if DOMAIN not in config:
        return True
    engine = HassConsoleEngine(hass, config[DOMAIN], DEFAULT_ALARM_CSV, DEFAULT_LOG_CSV)
    hass.data.setdefault(DOMAIN, {})["_yaml_engine"] = engine
    async def _start(event):
        await engine.async_setup()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)
    return True


# ──────────────────────────────────────────────────────────────────
# Setup — Config Entry mode (UI)
# ──────────────────────────────────────────────────────────────────

async def async_setup_entry(hass, entry):
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
        async def _start(event):
            await engine.async_setup()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass, entry):
    d = hass.data.get(DOMAIN, {})
    engine = d.pop(entry.entry_id, None)
    if engine:
        await engine.async_teardown()
    return True


async def _async_update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


# ──────────────────────────────────────────────────────────────────
# Services
# ──────────────────────────────────────────────────────────────────

def _register_services(hass):
    if hass.services.has_service(DOMAIN, "write_log"):
        return

    async def _svc_write_log(call):
        engine = _get_active_engine(hass)
        if not engine: return
        await engine._write_log_row({
            "timestamp": dt_util.now().strftime(TIMESTAMP_FORMAT),
            "category": call.data.get("category", ""),
            "entity": call.data.get("entity", ""),
            "value": call.data.get("value", ""),
            "note": call.data.get("note", ""),
        })

    async def _svc_write_alarm(call):
        engine = _get_active_engine(hass)
        if not engine: return
        await engine._write_alarm_row({
            "id": _gen_id(),
            "timestamp": dt_util.now().strftime(TIMESTAMP_FORMAT),
            "category": call.data.get("category", ""),
            "entity": call.data.get("entity", ""),
            "class": call.data.get("class", ""),
            "value": call.data.get("value", ""),
            "duration": call.data.get("duration", ""),
            "note": call.data.get("note", ""),
            "trigger": call.data.get("trigger", ""),
            "ack": "",
        })

    async def _svc_ack(call):
        engine = _get_active_engine(hass)
        if not engine: return
        alarm_id = call.data.get("id", "")
        note = call.data.get("note", "")
        found = await engine.acknowledge_alarm(alarm_id, note)
        if not found:
            _LOGGER.warning("Acknowledge: alarm ID '%s' not found or already acknowledged", alarm_id)

    async def _svc_ack_all(call):
        engine = _get_active_engine(hass)
        if not engine: return
        note = call.data.get("note", "")
        count = await engine.acknowledge_all(note)
        _LOGGER.info("Acknowledged %d alarms", count)

    async def _svc_reload(call):
        entries = hass.config_entries.async_entries(DOMAIN)
        if entries:
            for entry in entries:
                await hass.config_entries.async_reload(entry.entry_id)
            return
        engine = _get_active_engine(hass)
        if engine:
            await engine.async_teardown()
            await engine.async_setup()

    hass.services.async_register(DOMAIN, "write_log", _svc_write_log, schema=vol.Schema({
        vol.Required("entity"): cv.string,
        vol.Optional("category", default=""): cv.string,
        vol.Optional("value", default=""): cv.string,
        vol.Optional("note", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "write_alarm", _svc_write_alarm, schema=vol.Schema({
        vol.Required("entity"): cv.string,
        vol.Optional("category", default=""): cv.string,
        vol.Optional("class", default=""): cv.string,
        vol.Optional("value", default=""): cv.string,
        vol.Optional("duration", default=""): cv.string,
        vol.Optional("note", default=""): cv.string,
        vol.Optional("trigger", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "acknowledge_alarm", _svc_ack, schema=vol.Schema({
        vol.Required("id"): cv.string,
        vol.Optional("note", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "acknowledge_all", _svc_ack_all, schema=vol.Schema({
        vol.Optional("note", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "reload", _svc_reload)
