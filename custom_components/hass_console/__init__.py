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

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.loader import async_get_integration
from homeassistant.const import (
    CONF_ALIAS, CONF_ENTITY_ID, CONF_PLATFORM,
    CONF_ABOVE, CONF_BELOW, CONF_FOR,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_component import EntityComponent
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
    CONF_RETENTION_DAYS, CONF_MAX_ROWS,
    DEFAULT_CONSOLE_YAML, DEFAULT_ALARM_CSV, DEFAULT_LOG_CSV,
    DEFAULT_RETENTION_DAYS, DEFAULT_MAX_ROWS,
    ALARM_COLUMNS, LOG_COLUMNS, TIMESTAMP_FORMAT, TYPE_LOG, TYPE_ALARM,
    ISSUE_INVALID_CONFIG,
)
from .entity import HassConsolePointEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_NUMERIC = "numeric_state"
PLATFORM_STATE = "state"
SUPPORTED_PLATFORMS = {PLATFORM_NUMERIC, PLATFORM_STATE}

FRONTEND_URL_BASE = "/hass_console_frontend"
FRONTEND_CARDS = ("hass-console-card.js", "hass-console-summary-card.js")


# ──────────────────────────────────────────────────────────────────
# Cron parsing
# ──────────────────────────────────────────────────────────────────

MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
DOW_NAMES = {
    "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
}


def _cron_token(tok: str, names: dict[str, int] | None) -> int:
    """Translate a single cron token to an int, honoring name aliases."""
    tok = tok.strip().lower()
    if names and tok in names:
        return names[tok]
    return int(tok)


def _parse_cron_field(
    field: str, min_val: int, max_val: int, names: dict[str, int] | None = None
) -> set[int]:
    values: set[int] = set()
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
            start, end = _cron_token(s, names), _cron_token(e, names)
        else:
            start = end = _cron_token(part, names)
        values.update(range(start, end + 1, step) if step else range(start, end + 1))
    return values


def cron_matches_now(cron_expr: str, now: datetime) -> bool:
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    try:
        if now.minute not in _parse_cron_field(minute, 0, 59):
            return False
        if now.hour not in _parse_cron_field(hour, 0, 23):
            return False
        if now.month not in _parse_cron_field(month, 1, 12, MONTH_NAMES):
            return False

        # Day-of-month / day-of-week follow standard (Vixie) cron semantics:
        # when BOTH fields are restricted (not "*"), a match on EITHER fires;
        # otherwise only the restricted field(s) must match.
        dom_restricted = dom.strip() != "*"
        dow_restricted = dow.strip() != "*"

        dow_vals = _parse_cron_field(dow, 0, 6, DOW_NAMES)
        if 7 in dow_vals:               # accept 7 as Sunday
            dow_vals.add(0)
        now_dow = now.isoweekday() % 7  # Mon=1..Sat=6, Sun=0

        dom_ok = now.day in _parse_cron_field(dom, 1, 31)
        dow_ok = now_dow in dow_vals

        if dom_restricted and dow_restricted:
            return dom_ok or dow_ok
        if dom_restricted:
            return dom_ok
        if dow_restricted:
            return dow_ok
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
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_rows: int = DEFAULT_MAX_ROWS,
        component: EntityComponent | None = None,
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
        self._retention_days = int(retention_days or 0)
        self._max_rows = int(max_rows or 0)
        self._component = component
        self._entities: dict[str, HassConsolePointEntity] = {}
        self._config_problems: list[str] = []

    async def async_setup(self) -> None:
        self._parse_points()
        await self.hass.async_add_executor_job(self._ensure_csvs)
        await self._register_entities()
        await self._setup_cron_scanner()
        self._setup_alarm_listeners()
        self._initial_alarm_eval()
        self._setup_alarm_duration_checker()
        self._setup_retention()
        self._report_config_problems()
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
        self.points = {}
        self._config_problems = []
        self._log_files = {self._log_csv}
        self._alarm_files = {self._alarm_csv}
        for name, pcfg in self.config.items():
            if not isinstance(pcfg, dict):
                self._config_problems.append(
                    f"'{name}': entry is not a mapping — skipped"
                )
                continue
            pt = str(pcfg.get(CONF_TYPE, "")).upper()
            if pt not in (TYPE_LOG, TYPE_ALARM):
                self._config_problems.append(
                    f"'{name}': type must be LOG or ALARM "
                    f"(got '{pcfg.get(CONF_TYPE, '')}') — skipped"
                )
                continue

            # Per-type required-field checks. Problems are recorded but the
            # point is still registered so partial configs keep working.
            if pt == TYPE_LOG:
                if not pcfg.get(CONF_CRON):
                    self._config_problems.append(f"'{name}': LOG point is missing 'cron'")
                if not pcfg.get(CONF_ENTITY):
                    self._config_problems.append(f"'{name}': LOG point is missing 'entity'")
            else:
                triggers = pcfg.get(CONF_TRIGGER, [])
                if not triggers:
                    self._config_problems.append(f"'{name}': ALARM point has no 'trigger' list")
                else:
                    self._validate_alarm_triggers(name, triggers, pcfg.get(CONF_ENTITY))

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

    def _validate_alarm_triggers(self, name, triggers, fallback_entity) -> None:
        for i, trig in enumerate(triggers):
            if not isinstance(trig, dict):
                self._config_problems.append(f"'{name}': trigger #{i + 1} is not a mapping")
                continue
            platform = trig.get(CONF_PLATFORM, trig.get("platform", ""))
            if platform not in SUPPORTED_PLATFORMS:
                self._config_problems.append(
                    f"'{name}': trigger #{i + 1} has unsupported platform '{platform}' "
                    f"(expected {' or '.join(sorted(SUPPORTED_PLATFORMS))})"
                )
                continue
            if not trig.get(CONF_ENTITY_ID, trig.get("entity_id", fallback_entity)):
                self._config_problems.append(
                    f"'{name}': trigger #{i + 1} is missing 'entity_id'"
                )
            if platform == PLATFORM_NUMERIC:
                has_above = trig.get(CONF_ABOVE, trig.get("above")) is not None
                has_below = trig.get(CONF_BELOW, trig.get("below")) is not None
                if not (has_above or has_below):
                    self._config_problems.append(
                        f"'{name}': numeric_state trigger #{i + 1} needs 'above' or 'below'"
                    )

    @callback
    def _report_config_problems(self) -> None:
        """Raise (or clear) a Repairs issue summarizing invalid config points."""
        if self._config_problems:
            for p in self._config_problems:
                _LOGGER.warning("HASS Console config: %s", p)
            ir.async_create_issue(
                self.hass, DOMAIN, ISSUE_INVALID_CONFIG,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_INVALID_CONFIG,
                translation_placeholders={
                    "count": str(len(self._config_problems)),
                    "problems": "\n".join(f"• {p}" for p in self._config_problems),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_INVALID_CONFIG)

    # ── Entities ──

    async def _register_entities(self) -> None:
        """Create one HA entity per configured point (LOG and ALARM).

        Entities keep the documented ``hass_console.<type>_<name>`` IDs, gain
        unique IDs + registry entries, and restore their last value across
        restarts. They are created up front so they exist before the first
        log/alarm fires.
        """
        if self._component is None:
            return
        entities: list[HassConsolePointEntity] = []
        for name, point in self.points.items():
            ent = HassConsolePointEntity(point)
            self._entities[name] = ent
            entities.append(ent)
        if entities:
            await self._component.async_add_entities(entities)

    # ── Cron (LOG) ──

    async def _setup_cron_scanner(self) -> None:
        @callback
        def _tick(now):
            # async_track_time_interval fires with a UTC time; cron expressions
            # and log timestamps are evaluated in the user's local timezone.
            now = dt_util.as_local(now)
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

    @callback
    def _initial_alarm_eval(self) -> None:
        """Check current state of all alarm entities on startup.

        If an entity is already in an alarm condition when the engine
        starts (e.g. door was already open), start the duration timer
        immediately so the alarm fires after the configured 'for' period.
        Without this, the engine would miss alarm conditions that existed
        before startup.
        """
        now = dt_util.now()
        for key, a in self._alarm_states.items():
            entity_id = a["entity_id"]
            state_obj = self.hass.states.get(entity_id)
            if not state_obj or state_obj.state in ("unavailable", "unknown"):
                continue

            platform = a["platform"]
            primary_ok = False

            if platform == PLATFORM_NUMERIC:
                primary_ok = _check_numeric(state_obj.state, a["above"], a["below"])
            elif platform == PLATFORM_STATE:
                to_val = a["to_state"]
                if to_val is not None:
                    to_list = to_val if isinstance(to_val, list) else [str(to_val)]
                    primary_ok = state_obj.state in [str(v) for v in to_list]
                else:
                    primary_ok = True

            # Check AND conditions
            if primary_ok and a["conditions"]:
                for cond in a["conditions"]:
                    if not self._check_condition(cond):
                        primary_ok = False
                        break

            if primary_ok:
                a["active"] = True
                a["triggered_at"] = now
                a["recorded"] = False
                _LOGGER.debug(
                    "Initial eval: %s already in alarm condition (%s=%s), timer started",
                    key, entity_id, state_obj.state,
                )

    def _setup_alarm_duration_checker(self) -> None:
        """Run every 30 seconds to check if any active alarm has exceeded its duration.

        This is needed because state triggers (e.g. door open) don't fire
        repeated events while the entity sits in the same state. Without
        this checker, the 'for' duration would never be evaluated for
        entities that don't change state frequently.
        """
        @callback
        def _check_durations(now):
            for key, a in self._alarm_states.items():
                if not a["active"] or a["recorded"]:
                    continue
                elapsed = (now - a["triggered_at"]).total_seconds()
                if elapsed >= a["duration"]:
                    # Re-verify the condition is still true
                    entity_id = a["entity_id"]
                    state_obj = self.hass.states.get(entity_id)
                    if not state_obj or state_obj.state in ("unavailable", "unknown"):
                        a["active"] = False
                        a["triggered_at"] = None
                        continue

                    still_ok = False
                    if a["platform"] == PLATFORM_NUMERIC:
                        still_ok = _check_numeric(state_obj.state, a["above"], a["below"])
                        display_val = state_obj.state
                    elif a["platform"] == PLATFORM_STATE:
                        to_val = a["to_state"]
                        if to_val is not None:
                            to_list = to_val if isinstance(to_val, list) else [str(to_val)]
                            still_ok = state_obj.state in [str(v) for v in to_list]
                        else:
                            still_ok = True
                        display_val = state_obj.state

                    # Re-check AND conditions
                    if still_ok and a["conditions"]:
                        for cond in a["conditions"]:
                            if not self._check_condition(cond):
                                still_ok = False
                                break

                    if still_ok:
                        self.hass.async_create_task(
                            self._record_alarm(
                                a["point"], now, display_val, elapsed, a["alias"]
                            )
                        )
                        a["recorded"] = True
                    else:
                        # Condition cleared between checks
                        a["active"] = False
                        a["triggered_at"] = None

        self._unsub_listeners.append(
            async_track_time_interval(self.hass, _check_durations, timedelta(seconds=30))
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
        self._set_point_state(point, val, {
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
        self._set_point_state(point, "ALARM", {
            "friendly_name": f"HASS Console Alarm: {point['header']}",
            "last_alarm": now.strftime(TIMESTAMP_FORMAT),
            "category": point.get("category", ""),
            "class": point.get("class", ""),
            "value": str(value),
            "duration": dur_str,
            "trigger": alias,
        })
        _LOGGER.info("ALARM: %s → '%s' (val=%s dur=%s)", point["entity_id"], alias, value, dur_str)

    @callback
    def _set_point_state(self, point, state, attributes) -> None:
        """Update a point's entity, falling back to a raw state write."""
        ent = self._entities.get(point["name"])
        if ent is not None:
            ent.update_value(state, attributes)
        else:
            self.hass.states.async_set(point["entity_id"], state, attributes)

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
                row["ack_note"] = note
                found = True
                break
        if found:
            self._write_all_rows(path, rows, ALARM_COLUMNS)
        return found

    def _ack_all_sync(self, path, note):
        rows = self._read_rows(path)
        now_str = dt_util.now().strftime(TIMESTAMP_FORMAT)
        count = 0
        for row in rows:
            if not row.get("ack"):
                row["ack"] = now_str
                row["ack_note"] = note
                count += 1
        if count:
            self._write_all_rows(path, rows, ALARM_COLUMNS)
        return count

    def _read_rows(self, path):
        path = Path(path)
        if not path.exists(): return []
        with open(path, "r", newline="") as f:
            return list(csv.DictReader(f))

    def _write_all_rows(self, path, rows, cols):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for row in rows:
                writer.writerow({c: row.get(c, "") for c in cols})

    # ── Retention / rotation ──

    def _setup_retention(self) -> None:
        """Prune old rows daily. Disabled entirely when both limits are 0."""
        if self._retention_days <= 0 and self._max_rows <= 0:
            return

        @callback
        def _tick(now):
            self.hass.async_create_task(self._prune())

        # Run once shortly after startup, then daily.
        self.hass.async_create_task(self._prune())
        self._unsub_listeners.append(
            async_track_time_interval(self.hass, _tick, timedelta(hours=24))
        )

    async def _prune(self) -> None:
        cutoff = (
            dt_util.now() - timedelta(days=self._retention_days)
            if self._retention_days > 0 else None
        )
        for path, cols, is_alarm in (
            *((p, LOG_COLUMNS, False) for p in self._log_files),
            *((p, ALARM_COLUMNS, True) for p in self._alarm_files),
        ):
            async with self._lock_for(path):
                await self.hass.async_add_executor_job(
                    self._prune_sync, path, cols, is_alarm, cutoff
                )

    def _prune_sync(self, path, cols, is_alarm, cutoff) -> None:
        path = Path(path)
        if not path.exists():
            return
        rows = self._read_rows(path)
        original = len(rows)
        if not rows:
            return

        def _keep(row) -> bool:
            # Never drop an unacknowledged alarm, whatever its age.
            if is_alarm and not row.get("ack"):
                return True
            if cutoff is None:
                return True
            ts = row.get("timestamp", "")
            try:
                when = dt_util.as_local(datetime.strptime(ts, TIMESTAMP_FORMAT))
            except (ValueError, TypeError):
                return True  # unparseable → keep (fail safe)
            return when >= cutoff

        rows = [r for r in rows if _keep(r)]

        if self._max_rows > 0 and len(rows) > self._max_rows:
            if is_alarm:
                # Keep every unacked alarm, then the newest acked rows up to cap.
                unacked = [r for r in rows if not r.get("ack")]
                acked = [r for r in rows if r.get("ack")]
                room = max(self._max_rows - len(unacked), 0)
                rows = unacked + acked[-room:] if room else unacked
            else:
                rows = rows[-self._max_rows:]

        if len(rows) != original:
            self._write_all_rows(path, rows, cols)
            _LOGGER.debug(
                "Retention: pruned %s from %d to %d rows", path, original, len(rows)
            )

    async def async_teardown(self):
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        # Remove this engine's entities so a reload re-adds them cleanly.
        if self._component is not None:
            for ent in self._entities.values():
                if ent.entity_id:
                    await self._component.async_remove_entity(ent.entity_id)
        self._entities.clear()
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_INVALID_CONFIG)


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
        if k not in ("_yaml_engine", "_component") and isinstance(v, HassConsoleEngine):
            return v
    return d.get("_yaml_engine")


def _get_component(hass) -> EntityComponent:
    """Return the shared entity component, creating it once per hass."""
    data = hass.data.setdefault(DOMAIN, {})
    component = data.get("_component")
    if component is None:
        component = EntityComponent(_LOGGER, DOMAIN, hass)
        data["_component"] = component
    return component


async def _async_register_frontend(hass) -> None:
    """Serve the bundled cards and register them as Lovelace resources (once per hass)."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("_frontend_registered"):
        return
    data["_frontend_registered"] = True

    root = Path(__file__).parent / "frontend"
    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(f"{FRONTEND_URL_BASE}/{name}", str(root / name), False)
                for name in FRONTEND_CARDS
            ]
        )
    except RuntimeError:
        pass  # already registered (e.g. on reload)

    # Register the cards as Lovelace resources — the mechanism the dashboard actually
    # waits for. (add_extra_js_url loads too early / into the wrong registry, so the
    # dashboard can't find the element: "Custom element not found".) Run in a background
    # task so a slow resource store can't hold up setup.
    hass.async_create_task(_async_register_card_resources(hass))


async def _async_register_card_resources(hass) -> None:
    """Add the bundled cards to Lovelace resources, idempotently (storage mode only)."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return
    mode = getattr(lovelace, "mode", getattr(lovelace, "resource_mode", "yaml"))
    resources = getattr(lovelace, "resources", None)
    manual_hint = ", ".join(f"{FRONTEND_URL_BASE}/{n}" for n in FRONTEND_CARDS)
    if mode != "storage" or resources is None:
        _LOGGER.info(
            "Lovelace is not in storage mode; add the HASS Console cards as resources "
            "(type: JavaScript Module) manually if needed: %s",
            manual_hint,
        )
        return

    try:
        # Load existing resources BEFORE creating anything: calling async_create_item()
        # on an unloaded collection wipes all existing resources (home-assistant/core#165767).
        if not getattr(resources, "loaded", False):
            await resources.async_load()
            resources.loaded = True

        try:
            version = str((await async_get_integration(hass, DOMAIN)).version)
        except Exception:  # pragma: no cover - best-effort cache-buster
            version = "0"

        items = resources.async_items()
        for name in FRONTEND_CARDS:
            base = f"{FRONTEND_URL_BASE}/{name}"
            desired = f"{base}?v={version}"
            existing = next(
                (r for r in items if str(r.get("url", "")).split("?", 1)[0] == base),
                None,
            )
            if existing is None:
                await resources.async_create_item(
                    {"res_type": "module", "url": desired}
                )
                _LOGGER.info("Registered HASS Console card resource: %s", base)
            elif existing.get("url") != desired and existing.get("id"):
                await resources.async_update_item(
                    existing["id"], {"res_type": "module", "url": desired}
                )
    except Exception as err:  # never crash setup, never risk the resource store
        _LOGGER.warning(
            "Could not auto-register HASS Console card resources (%s); add them "
            "manually if the cards don't appear: %s",
            err,
            manual_hint,
        )


# ──────────────────────────────────────────────────────────────────
# Setup — YAML mode (legacy)
# ──────────────────────────────────────────────────────────────────

async def async_setup(hass, config):
    _register_services(hass)
    await _async_register_frontend(hass)
    if DOMAIN not in config:
        return True
    component = _get_component(hass)
    engine = HassConsoleEngine(
        hass, config[DOMAIN], DEFAULT_ALARM_CSV, DEFAULT_LOG_CSV, component=component
    )
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
    retention_days = settings.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)
    max_rows = settings.get(CONF_MAX_ROWS, DEFAULT_MAX_ROWS)
    points = await hass.async_add_executor_job(_load_yaml_sync, yaml_path)
    component = _get_component(hass)
    engine = HassConsoleEngine(
        hass, points, alarm_csv, log_csv, retention_days, max_rows, component
    )
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
