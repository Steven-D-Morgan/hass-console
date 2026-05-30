"""HASS Console - Alarm & Log Engine for Home Assistant."""
from __future__ import annotations

import asyncio
import csv
import logging
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
    CONF_TRIGGER, CONF_CATEGORY, CONF_TARGET_CSV,
    CONF_CONSOLE_YAML, CONF_ALARM_CSV, CONF_LOG_CSV,
    DEFAULT_CONSOLE_YAML, DEFAULT_ALARM_CSV, DEFAULT_LOG_CSV,
    ALARM_COLUMNS, LOG_COLUMNS, TIMESTAMP_FORMAT, TYPE_LOG, TYPE_ALARM,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_NUMERIC = "numeric_state"
PLATFORM_STATE = "state"
SUPPORTED_PLATFORMS = {PLATFORM_NUMERIC, PLATFORM_STATE}


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
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────
# Condition evaluation helpers
# ──────────────────────────────────────────────────────────────────

def _check_numeric(state_val: str, above, below) -> bool:
    """Check if a numeric value exceeds above/below thresholds."""
    try:
        val = float(state_val)
    except (ValueError, TypeError):
        return False
    if above is not None and val <= float(above):
        return False
    if below is not None and val >= float(below):
        return False
    return True


def _check_state_match(new_state: str, old_state: str | None, to_val, from_val) -> bool:
    """Check if a state transition matches to/from criteria."""
    if to_val is not None:
        to_list = to_val if isinstance(to_val, list) else [str(to_val)]
        if new_state not in [str(v) for v in to_list]:
            return False
    if from_val is not None and old_state is not None:
        from_list = from_val if isinstance(from_val, list) else [str(from_val)]
        if old_state not in [str(v) for v in from_list]:
            return False
    return True


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
        self._log_files: set[Path] = {self._log_csv}
        self._alarm_files: set[Path] = {self._alarm_csv}
        self._file_locks: dict[str, asyncio.Lock] = {}

    async def async_setup(self) -> None:
        self._parse_points()
        await self.hass.async_add_executor_job(self._ensure_csvs)
        await self._setup_cron_scanner()
        self._setup_alarm_listeners()
        _LOGGER.info(
            "HASS Console started: %d points, %d log file(s), %d alarm file(s)",
            len(self.points), len(self._log_files), len(self._alarm_files),
        )

    # ── Path + lock helpers ──

    def _resolve_csv_path(self, target: str, default_path: Path) -> Path:
        if not target:
            return default_path
        p = Path(target)
        return p if p.is_absolute() else default_path.parent / target

    def _lock_for(self, path: Path) -> asyncio.Lock:
        key = str(path)
        lock = self._file_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._file_locks[key] = lock
        return lock

    # ── CSV file management ──

    def _ensure_csvs(self) -> None:
        for path in self._log_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._migrate_or_create(path, LOG_COLUMNS, generate_ids=False)
        for path in self._alarm_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._migrate_or_create(path, ALARM_COLUMNS, generate_ids=True)

    def _migrate_or_create(self, path: Path, expected: list[str], generate_ids: bool = False) -> None:
        if not path.exists():
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(expected)
            return
        with open(path, "r", newline="") as f:
            try:
                header = [h.strip() for h in next(csv.reader(f))]
            except StopIteration:
                header = []
        if header == expected:
            return
        _LOGGER.info("Migrating CSV %s to new schema", path)
        with open(path, "r", newline="") as f:
            rows = list(csv.DictReader(f))
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=expected)
            writer.writeheader()
            for row in rows:
                filled = {col: row.get(col, "") for col in expected}
                if generate_ids and not filled.get("id"):
                    filled["id"] = _gen_id()
                writer.writerow(filled)

    def _parse_points(self) -> None:
        self._log_files = {self._log_csv}
        self._alarm_files = {self._alarm_csv}
        for name, pcfg in self.config.items():
            if not isinstance(pcfg, dict):
                continue
            pt = str(pcfg.get(CONF_TYPE, "")).upper()
            if pt not in (TYPE_LOG, TYPE_ALARM):
                continue
            header = name.upper()
            eid = f"hass_console.{pt.lower()}_{header.lower()}"
            target = str(pcfg.get(CONF_TARGET_CSV, "")).strip()
            if pt == TYPE_LOG:
                target_file = self._resolve_csv_path(target, self._log_csv)
                self._log_files.add(target_file)
            else:
                target_file = self._resolve_csv_path(target, self._alarm_csv)
                self._alarm_files.add(target_file)
            self.points[name] = {
                "name": name, "header": header, "type": pt, "entity_id": eid,
                "source_entity": pcfg.get(CONF_ENTITY),
                "cron": pcfg.get(CONF_CRON),
                "note": pcfg.get(CONF_NOTE, ""),
                "class": pcfg.get(CONF_CLASS, ""),
                "category": str(pcfg.get(CONF_CATEGORY, "")).strip(),
                "target_file": target_file,
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
            if point["type"] != TYPE_ALARM:
                continue
            for trig in point.get("trigger", []):
                if not isinstance(trig, dict):
                    continue
                platform = trig.get(CONF_PLATFORM, trig.get("platform", ""))
                if platform not in SUPPORTED_PLATFORMS:
                    _LOGGER.warning(
                        "Point '%s' trigger has unsupported platform '%s', skipping",
                        name, platform,
                    )
                    continue

                target = trig.get(CONF_ENTITY_ID, trig.get("entity_id", point.get("source_entity")))
                if not target:
                    continue
                alias = trig.get(CONF_ALIAS, trig.get("alias", name))
                for_d = trig.get(CONF_FOR, trig.get("for", {}))
                dur = (
                    for_d.get("hours", 0) * 3600 +
                    for_d.get("minutes", 0) * 60 +
                    for_d.get("seconds", 0)
                ) if isinstance(for_d, dict) else 0

                # Parse AND conditions (optional)
                raw_conditions = trig.get("conditions", [])
                conditions = []
                for cond in raw_conditions:
                    if isinstance(cond, dict):
                        conditions.append(cond)

                akey = f"{name}_{target}_{alias}"
                self._alarm_states[akey] = {
                    "active": False, "triggered_at": None, "recorded": False,
                    "point": point,
                    "platform": platform,
                    "alias": alias,
                    "entity_id": target,
                    "duration": dur,
                    "conditions": conditions,
                    # numeric_state fields
                    "above": trig.get(CONF_ABOVE, trig.get("above")),
                    "below": trig.get(CONF_BELOW, trig.get("below")),
                    # state fields
                    "to_state": trig.get("to"),
                    "from_state": trig.get("from"),
                }

                @callback
                def _changed(event, _k=akey):
                    self.hass.async_create_task(self._eval_alarm(_k, event))
                self._unsub_listeners.append(
                    async_track_state_change_event(self.hass, target, _changed)
                )

    async def _eval_alarm(self, key, event):
        a = self._alarm_states.get(key)
        if not a:
            return
        new_s: State | None = event.data.get("new_state")
        old_s: State | None = event.data.get("old_state")
        if not new_s:
            return
        if new_s.state in ("unavailable", "unknown"):
            return

        # ── Primary condition check based on platform ──
        platform = a["platform"]
        if platform == PLATFORM_NUMERIC:
            primary_ok = _check_numeric(new_s.state, a["above"], a["below"])
            display_val = new_s.state
        elif platform == PLATFORM_STATE:
            old_val = old_s.state if old_s else None
            primary_ok = _check_state_match(
                new_s.state, old_val, a["to_state"], a["from_state"]
            )
            display_val = new_s.state
        else:
            return

        # ── AND conditions — all must be true right now ──
        if primary_ok and a["conditions"]:
            for cond in a["conditions"]:
                if not self._check_condition(cond):
                    primary_ok = False
                    break

        # ── Duration tracking + recording ──
        now = dt_util.now()
        if primary_ok and not a["active"]:
            a["active"] = True
            a["triggered_at"] = now
            a["recorded"] = False
        elif primary_ok and a["active"] and not a["recorded"]:
            elapsed = (now - a["triggered_at"]).total_seconds()
            if elapsed >= a["duration"]:
                await self._record_alarm(
                    a["point"], now, display_val, elapsed, a["alias"]
                )
                a["recorded"] = True
        elif not primary_ok and a["active"]:
            a["active"] = False
            a["triggered_at"] = None
            a["recorded"] = False

    def _check_condition(self, cond: dict) -> bool:
        """Evaluate an AND condition against current entity state."""
        entity_id = cond.get("entity_id")
        if not entity_id:
            return True
        state_obj = self.hass.states.get(entity_id)
        if not state_obj:
            return False
        if state_obj.state in ("unavailable", "unknown"):
            return False

        # Numeric: above / below
        above = cond.get("above")
        below = cond.get("below")
        if above is not None or below is not None:
            return _check_numeric(state_obj.state, above, below)

        # State: exact match
        state_val = cond.get("state")
        if state_val is not None:
            match_list = state_val if isinstance(state_val, list) else [str(state_val)]
            return state_obj.state in [str(v) for v in match_list]

        return True

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
        await self._write_log_row(row, point.get("target_file"))
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
        await self._write_alarm_row(row, point.get("target_file"))
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

    async def _write_log_row(self, row, target: Path | None = None):
        path = target or self._log_csv
        async with self._lock_for(path):
            await self.hass.async_add_executor_job(self._append_sync, path, row, LOG_COLUMNS)

    async def _write_alarm_row(self, row, target: Path | None = None):
        path = target or self._alarm_csv
        async with self._lock_for(path):
            await self.hass.async_add_executor_job(self._append_sync, path, row, ALARM_COLUMNS)

    def _append_sync(self, path: Path, row, cols):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        need_header = not path.exists() or path.stat().st_size == 0
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            if need_header:
                writer.writeheader()
            writer.writerow({c: row.get(c, "") for c in cols})

    # ── Acknowledge ──

    async def acknowledge_alarm(self, alarm_id: str, note: str = "") -> bool:
        for path in self._alarm_files:
            async with self._lock_for(path):
                found = await self.hass.async_add_executor_job(self._ack_sync, path, alarm_id, note)
            if found:
                return True
        return False

    async def acknowledge_all(self, note: str = "") -> int:
        total = 0
        for path in self._alarm_files:
            async with self._lock_for(path):
                total += await self.hass.async_add_executor_job(self._ack_all_sync, path, note)
        return total

    def _ack_sync(self, path, alarm_id, note):
        rows = self._read_rows(path)
        found = False
        for row in rows:
            if row.get("id") == alarm_id and not row.get("ack"):
                row["ack"] = dt_util.now().strftime(TIMESTAMP_FORMAT)
                found = True
                break
        if found:
            self._write_rows(path, rows)
        return found

    def _ack_all_sync(self, path, note):
        rows = self._read_rows(path)
        now_str = dt_util.now().strftime(TIMESTAMP_FORMAT)
        count = 0
        for row in rows:
            if not row.get("ack"):
                row["ack"] = now_str
                count += 1
        if count:
            self._write_rows(path, rows)
        return count

    def _read_rows(self, path):
        path = Path(path)
        if not path.exists(): return []
        with open(path, "r", newline="") as f:
            return list(csv.DictReader(f))

    def _write_rows(self, path, rows):
        with open(path, "w", newline="") as f:
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
    if engine: await engine.async_teardown()
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
        target = call.data.get("target_csv", "").strip()
        path = engine._resolve_csv_path(target, engine._log_csv) if target else None
        await engine._write_log_row({
            "timestamp": dt_util.now().strftime(TIMESTAMP_FORMAT),
            "category": call.data.get("category", ""),
            "entity": call.data.get("entity", ""),
            "value": call.data.get("value", ""),
            "note": call.data.get("note", ""),
        }, path)

    async def _svc_write_alarm(call):
        engine = _get_active_engine(hass)
        if not engine: return
        target = call.data.get("target_csv", "").strip()
        path = engine._resolve_csv_path(target, engine._alarm_csv) if target else None
        if path: engine._alarm_files.add(path)
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
        }, path)

    async def _svc_ack(call):
        engine = _get_active_engine(hass)
        if not engine: return
        found = await engine.acknowledge_alarm(call.data.get("id", ""), call.data.get("note", ""))
        if not found:
            _LOGGER.warning("Acknowledge: alarm ID '%s' not found", call.data.get("id", ""))

    async def _svc_ack_all(call):
        engine = _get_active_engine(hass)
        if not engine: return
        count = await engine.acknowledge_all(call.data.get("note", ""))
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
        vol.Optional("target_csv", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "write_alarm", _svc_write_alarm, schema=vol.Schema({
        vol.Required("entity"): cv.string,
        vol.Optional("category", default=""): cv.string,
        vol.Optional("class", default=""): cv.string,
        vol.Optional("value", default=""): cv.string,
        vol.Optional("duration", default=""): cv.string,
        vol.Optional("note", default=""): cv.string,
        vol.Optional("trigger", default=""): cv.string,
        vol.Optional("target_csv", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "acknowledge_alarm", _svc_ack, schema=vol.Schema({
        vol.Required("id"): cv.string,
        vol.Optional("note", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "acknowledge_all", _svc_ack_all, schema=vol.Schema({
        vol.Optional("note", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "reload", _svc_reload)
