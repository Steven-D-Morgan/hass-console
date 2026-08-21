"""Config flow for HASS Console."""
from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_CONSOLE_YAML,
    CONF_ALARM_CSV,
    CONF_LOG_CSV,
    CONF_RETENTION_DAYS,
    CONF_MAX_ROWS,
    CONF_NAME,
    CONF_TYPE,
    CONF_CRON,
    CONF_ENTITY,
    CONF_NOTE,
    CONF_CLASS,
    CONF_CATEGORY,
    CONF_TARGET_CSV,
    CONF_TRIGGER,
    DEFAULT_CONSOLE_YAML,
    DEFAULT_ALARM_CSV,
    DEFAULT_LOG_CSV,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_MAX_ROWS,
    SUBENTRY_LOG,
    SUBENTRY_ALARM,
    PLATFORM_NUMERIC,
    PLATFORM_STATE,
    TYPE_LOG,
    TYPE_ALARM,
)

_LOGGER = logging.getLogger(__name__)


def _validate_paths(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}

    yaml_path = (data.get(CONF_CONSOLE_YAML) or "").strip()
    alarm_path = (data.get(CONF_ALARM_CSV) or "").strip()
    log_path = (data.get(CONF_LOG_CSV) or "").strip()

    if yaml_path and not os.path.isfile(yaml_path):
        errors[CONF_CONSOLE_YAML] = "yaml_not_found"

    for key, path in (
        (CONF_ALARM_CSV, alarm_path),
        (CONF_LOG_CSV, log_path),
    ):
        if not path:
            errors[key] = "path_required"
            continue
        parent = os.path.dirname(path) or "."
        if not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError:
                errors[key] = "parent_not_writable"

    return errors


def _normalize_name(raw: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw.strip())
    return cleaned.upper().strip("_")


class HassConsoleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self.hass.async_add_executor_job(
                _validate_paths, user_input
            )
            if not errors:
                return self.async_create_entry(
                    title="HASS Console",
                    data=user_input,
                )

        defaults = user_input or {}
        schema = vol.Schema({
            vol.Optional(
                CONF_CONSOLE_YAML,
                default=defaults.get(CONF_CONSOLE_YAML, DEFAULT_CONSOLE_YAML),
            ): str,
            vol.Required(
                CONF_ALARM_CSV,
                default=defaults.get(CONF_ALARM_CSV, DEFAULT_ALARM_CSV),
            ): str,
            vol.Required(
                CONF_LOG_CSV,
                default=defaults.get(CONF_LOG_CSV, DEFAULT_LOG_CSV),
            ): str,
            vol.Optional(
                CONF_RETENTION_DAYS,
                default=defaults.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS),
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                CONF_MAX_ROWS,
                default=defaults.get(CONF_MAX_ROWS, DEFAULT_MAX_ROWS),
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HassConsoleOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            SUBENTRY_LOG: LogPointSubentryFlow,
            SUBENTRY_ALARM: AlarmPointSubentryFlow,
        }


class HassConsoleOptionsFlow(config_entries.OptionsFlow):
    """Options flow — edit paths after initial setup.

    Do NOT override __init__ to store config_entry — HA provides
    self.config_entry automatically since 2024.11.
    """

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}
        entry = self.config_entry
        current = {**entry.data, **entry.options}

        if user_input is not None:
            errors = await self.hass.async_add_executor_job(
                _validate_paths, user_input
            )
            if not errors:
                return self.async_create_entry(title="", data=user_input)
            current = {**current, **user_input}

        schema = vol.Schema({
            vol.Optional(
                CONF_CONSOLE_YAML,
                default=current.get(CONF_CONSOLE_YAML, DEFAULT_CONSOLE_YAML),
            ): str,
            vol.Required(
                CONF_ALARM_CSV,
                default=current.get(CONF_ALARM_CSV, DEFAULT_ALARM_CSV),
            ): str,
            vol.Required(
                CONF_LOG_CSV,
                default=current.get(CONF_LOG_CSV, DEFAULT_LOG_CSV),
            ): str,
            vol.Optional(
                CONF_RETENTION_DAYS,
                default=current.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS),
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                CONF_MAX_ROWS,
                default=current.get(CONF_MAX_ROWS, DEFAULT_MAX_ROWS),
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )


_CATEGORY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
)


def _name_taken(flow: ConfigSubentryFlow, name: str) -> bool:
    parent = flow.hass.config_entries.async_get_entry(flow.handler)
    if parent is None:
        return False
    current_id = getattr(flow, "_reconfigure_subentry_id", None)
    for sub_id, sub in parent.subentries.items():
        if sub_id == current_id:
            continue
        if (sub.data or {}).get(CONF_NAME) == name:
            return True
    return False


def _duration_to_dict(hours: int, minutes: int, seconds: int) -> dict[str, int]:
    d: dict[str, int] = {}
    if hours:
        d["hours"] = hours
    if minutes:
        d["minutes"] = minutes
    if seconds:
        d["seconds"] = seconds
    return d


class LogPointSubentryFlow(ConfigSubentryFlow):
    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        return await self._show_form(user_input, reconfigure=False)

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        return await self._show_form(user_input, reconfigure=True)

    async def _show_form(
        self, user_input: dict[str, Any] | None, *, reconfigure: bool
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        current: dict[str, Any] = {}

        if reconfigure:
            sub = self._get_reconfigure_subentry()
            current = dict(sub.data)

        if user_input is not None:
            name = _normalize_name(user_input.get(CONF_NAME, ""))
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not reconfigure and _name_taken(self, name):
                errors[CONF_NAME] = "name_taken"
            elif reconfigure and name != current.get(CONF_NAME) and _name_taken(self, name):
                errors[CONF_NAME] = "name_taken"

            if not user_input.get(CONF_CRON, "").strip():
                errors[CONF_CRON] = "cron_required"
            if not user_input.get(CONF_ENTITY, "").strip():
                errors[CONF_ENTITY] = "entity_required"

            if not errors:
                data = {
                    CONF_NAME: name,
                    CONF_TYPE: TYPE_LOG,
                    CONF_CRON: user_input[CONF_CRON].strip(),
                    CONF_ENTITY: user_input[CONF_ENTITY].strip(),
                    CONF_CATEGORY: user_input.get(CONF_CATEGORY, "").strip(),
                    CONF_NOTE: user_input.get(CONF_NOTE, "").strip(),
                    CONF_TARGET_CSV: user_input.get(CONF_TARGET_CSV, "").strip(),
                }
                if reconfigure:
                    return self.async_update_and_abort(
                        self._get_reconfigure_entry(),
                        self._get_reconfigure_subentry(),
                        data=data,
                        title=name,
                    )
                return self.async_create_entry(title=name, data=data)

            current = {**current, **user_input}

        schema = vol.Schema({
            vol.Required(
                CONF_NAME, default=current.get(CONF_NAME, "")
            ): str,
            vol.Required(
                CONF_CRON, default=current.get(CONF_CRON, "0 * * * *")
            ): str,
            vol.Required(
                CONF_ENTITY, default=current.get(CONF_ENTITY, "")
            ): selector.EntitySelector(),
            vol.Optional(
                CONF_CATEGORY, default=current.get(CONF_CATEGORY, "")
            ): _CATEGORY_SELECTOR,
            vol.Optional(
                CONF_NOTE, default=current.get(CONF_NOTE, "")
            ): str,
            vol.Optional(
                CONF_TARGET_CSV, default=current.get(CONF_TARGET_CSV, "")
            ): str,
        })

        return self.async_show_form(
            step_id="reconfigure" if reconfigure else "user",
            data_schema=schema,
            errors=errors,
        )


_ALARM_CLASS_OPTIONS = [
    selector.SelectOptionDict(value="01", label="01 — Critical"),
    selector.SelectOptionDict(value="02", label="02 — Major"),
    selector.SelectOptionDict(value="03", label="03 — Minor"),
]
_ALARM_CLASS_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=_ALARM_CLASS_OPTIONS,
        custom_value=True,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

_TRIGGER_PLATFORM_OPTIONS = [
    selector.SelectOptionDict(value=PLATFORM_NUMERIC, label="Numeric threshold (above/below)"),
    selector.SelectOptionDict(value=PLATFORM_STATE, label="State match (to/from)"),
]
_TRIGGER_PLATFORM_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=_TRIGGER_PLATFORM_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

_CONDITION_TYPE_NUMERIC = "numeric"
_CONDITION_TYPE_STATE = "state"
_CONDITION_TYPE_OPTIONS = [
    selector.SelectOptionDict(
        value=_CONDITION_TYPE_NUMERIC, label="Numeric threshold (above/below)"
    ),
    selector.SelectOptionDict(
        value=_CONDITION_TYPE_STATE, label="State match"
    ),
]
_CONDITION_TYPE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=_CONDITION_TYPE_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


class AlarmPointSubentryFlow(ConfigSubentryFlow):
    _data: dict[str, Any]
    _reconfigure: bool
    _editing_trigger_index: int | None
    _editing_conditions_trigger_index: int | None
    _editing_condition_index: int | None

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        if not hasattr(self, "_data"):
            self._reconfigure = False
            self._data = {
                CONF_TYPE: TYPE_ALARM,
                CONF_TRIGGER: [],
            }
            self._editing_trigger_index = None
            self._editing_conditions_trigger_index = None
            self._editing_condition_index = None
        return await self._show_header(user_input)

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        if not hasattr(self, "_data"):
            self._reconfigure = True
            sub = self._get_reconfigure_subentry()
            stored = dict(sub.data)
            stored[CONF_TRIGGER] = [
                {**dict(t), "conditions": [dict(c) for c in (t.get("conditions") or [])]}
                if (t.get("conditions") or []) else dict(t)
                for t in stored.get(CONF_TRIGGER, [])
            ]
            self._data = stored
            self._editing_trigger_index = None
            self._editing_conditions_trigger_index = None
            self._editing_condition_index = None
        return await self._show_header(user_input)

    async def _show_header(
        self, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        current = dict(self._data)

        if user_input is not None:
            name = _normalize_name(user_input.get(CONF_NAME, ""))
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not self._reconfigure and _name_taken(self, name):
                errors[CONF_NAME] = "name_taken"
            elif self._reconfigure and name != current.get(CONF_NAME) and _name_taken(self, name):
                errors[CONF_NAME] = "name_taken"

            if not errors:
                self._data.update({
                    CONF_NAME: name,
                    CONF_CLASS: user_input.get(CONF_CLASS, "").strip(),
                    CONF_CATEGORY: user_input.get(CONF_CATEGORY, "").strip(),
                    CONF_ENTITY: user_input.get(CONF_ENTITY, "").strip(),
                    CONF_NOTE: user_input.get(CONF_NOTE, "").strip(),
                    CONF_TARGET_CSV: user_input.get(CONF_TARGET_CSV, "").strip(),
                })
                return await self.async_step_triggers()

            current = {**current, **user_input}

        schema = vol.Schema({
            vol.Required(
                CONF_NAME, default=current.get(CONF_NAME, "")
            ): str,
            vol.Optional(
                CONF_CLASS, default=current.get(CONF_CLASS, "01")
            ): _ALARM_CLASS_SELECTOR,
            vol.Optional(
                CONF_CATEGORY, default=current.get(CONF_CATEGORY, "")
            ): _CATEGORY_SELECTOR,
            vol.Optional(
                CONF_ENTITY, default=current.get(CONF_ENTITY, "")
            ): selector.EntitySelector(),
            vol.Optional(
                CONF_NOTE, default=current.get(CONF_NOTE, "")
            ): str,
            vol.Optional(
                CONF_TARGET_CSV, default=current.get(CONF_TARGET_CSV, "")
            ): str,
        })

        return self.async_show_form(
            step_id="reconfigure" if self._reconfigure else "user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_triggers(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        triggers = self._data.get(CONF_TRIGGER, [])

        options: dict[str, str] = {}
        for idx, trig in enumerate(triggers):
            label = self._trigger_summary(trig, idx)
            options[f"edit_{idx}"] = f"Edit — {label}"
            cond_count = len(trig.get("conditions") or [])
            cond_suffix = f" ({cond_count})" if cond_count else ""
            options[f"conditions_{idx}"] = (
                f"Manage AND conditions{cond_suffix} — {label}"
            )
            options[f"delete_{idx}"] = f"Delete — {label}"
        options["add"] = "Add trigger"
        if triggers:
            options["save"] = "Save alarm point"
        options["back"] = "Back to alarm settings"

        if user_input is not None:
            choice = user_input.get("next_step")
            if choice == "add":
                self._editing_trigger_index = None
                return await self.async_step_add_trigger()
            if choice == "back":
                return await self._show_header(None)
            if choice == "save":
                if not triggers:
                    return self.async_show_form(
                        step_id="triggers",
                        data_schema=self._triggers_schema(options),
                        errors={"base": "at_least_one_trigger"},
                    )
                return self._finalize()
            if choice and choice.startswith("edit_"):
                self._editing_trigger_index = int(choice.split("_", 1)[1])
                return await self.async_step_edit_trigger()
            if choice and choice.startswith("conditions_"):
                self._editing_conditions_trigger_index = int(
                    choice.split("_", 1)[1]
                )
                self._editing_condition_index = None
                return await self.async_step_conditions()
            if choice and choice.startswith("delete_"):
                idx = int(choice.split("_", 1)[1])
                if 0 <= idx < len(triggers):
                    del triggers[idx]
                return await self.async_step_triggers()

        return self.async_show_form(
            step_id="triggers",
            data_schema=self._triggers_schema(options),
        )

    def _triggers_schema(self, options: dict[str, str]) -> vol.Schema:
        return vol.Schema({
            vol.Required("next_step", default="add"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in options.items()
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        })

    async def async_step_add_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._trigger_form(user_input, edit_index=None)

    async def async_step_edit_trigger(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._trigger_form(user_input, edit_index=self._editing_trigger_index)

    async def _trigger_form(
        self,
        user_input: dict[str, Any] | None,
        *,
        edit_index: int | None,
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        triggers = self._data.setdefault(CONF_TRIGGER, [])

        seed: dict[str, Any]
        if edit_index is not None and 0 <= edit_index < len(triggers):
            existing = triggers[edit_index]
            for_d = existing.get("for") or {}
            seed = {
                "platform": existing.get("platform", PLATFORM_NUMERIC),
                "alias": existing.get("alias", ""),
                "entity_id": existing.get("entity_id", ""),
                "above": existing.get("above"),
                "below": existing.get("below"),
                "to": _list_to_csv(existing.get("to")),
                "from": _list_to_csv(existing.get("from")),
                "for_hours": (for_d or {}).get("hours", 0),
                "for_minutes": (for_d or {}).get("minutes", 0),
                "for_seconds": (for_d or {}).get("seconds", 0),
            }
        else:
            seed = {
                "platform": PLATFORM_NUMERIC,
                "alias": "",
                "entity_id": self._data.get(CONF_ENTITY, ""),
                "above": None,
                "below": None,
                "to": "",
                "from": "",
                "for_hours": 0,
                "for_minutes": 0,
                "for_seconds": 0,
            }

        if user_input is not None:
            platform = user_input.get("platform", PLATFORM_NUMERIC)
            entity_id = (user_input.get("entity_id") or "").strip()
            alias = (user_input.get("alias") or "").strip()

            if not entity_id:
                errors["entity_id"] = "entity_required"

            above = user_input.get("above")
            below = user_input.get("below")
            to_raw = (user_input.get("to") or "").strip()
            from_raw = (user_input.get("from") or "").strip()

            if platform == PLATFORM_NUMERIC:
                if above in (None, "") and below in (None, ""):
                    errors["base"] = "numeric_needs_threshold"
            elif platform == PLATFORM_STATE:
                if not to_raw:
                    errors["to"] = "state_needs_to"

            if not errors:
                trig: dict[str, Any] = {
                    "platform": platform,
                    "entity_id": entity_id,
                }
                if alias:
                    trig["alias"] = alias
                if platform == PLATFORM_NUMERIC:
                    if above not in (None, ""):
                        trig["above"] = float(above)
                    if below not in (None, ""):
                        trig["below"] = float(below)
                else:
                    trig["to"] = _csv_to_list_or_scalar(to_raw)
                    if from_raw:
                        trig["from"] = _csv_to_list_or_scalar(from_raw)

                dur = _duration_to_dict(
                    int(user_input.get("for_hours", 0) or 0),
                    int(user_input.get("for_minutes", 0) or 0),
                    int(user_input.get("for_seconds", 0) or 0),
                )
                if dur:
                    trig["for"] = dur

                if edit_index is not None and 0 <= edit_index < len(triggers):
                    prev_conditions = triggers[edit_index].get("conditions")
                    if prev_conditions:
                        trig["conditions"] = prev_conditions
                    triggers[edit_index] = trig
                else:
                    triggers.append(trig)

                return await self.async_step_triggers()

            seed = {**seed, **user_input}

        schema = vol.Schema({
            vol.Required(
                "platform", default=seed.get("platform", PLATFORM_NUMERIC)
            ): _TRIGGER_PLATFORM_SELECTOR,
            vol.Optional("alias", default=seed.get("alias", "")): str,
            vol.Required(
                "entity_id", default=seed.get("entity_id", "")
            ): selector.EntitySelector(),
            vol.Optional("above", default=_num_default(seed.get("above"))): vol.Any(
                vol.Coerce(float), None, ""
            ),
            vol.Optional("below", default=_num_default(seed.get("below"))): vol.Any(
                vol.Coerce(float), None, ""
            ),
            vol.Optional("to", default=seed.get("to", "")): str,
            vol.Optional("from", default=seed.get("from", "")): str,
            vol.Optional(
                "for_hours", default=int(seed.get("for_hours", 0) or 0)
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                "for_minutes", default=int(seed.get("for_minutes", 0) or 0)
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(
                "for_seconds", default=int(seed.get("for_seconds", 0) or 0)
            ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        })

        step_id = "edit_trigger" if edit_index is not None else "add_trigger"
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
        )

    def _finalize(self) -> SubentryFlowResult:
        name = self._data.get(CONF_NAME, "")
        if self._reconfigure:
            return self.async_update_and_abort(
                self._get_reconfigure_entry(),
                self._get_reconfigure_subentry(),
                data=self._data,
                title=name,
            )
        return self.async_create_entry(title=name, data=self._data)

    @staticmethod
    def _trigger_summary(trig: dict[str, Any], idx: int) -> str:
        alias = trig.get("alias")
        if alias:
            return f"#{idx + 1}: {alias}"
        platform = trig.get("platform", "?")
        entity = trig.get("entity_id", "?")
        if platform == PLATFORM_NUMERIC:
            parts = []
            if trig.get("above") is not None:
                parts.append(f">{trig['above']}")
            if trig.get("below") is not None:
                parts.append(f"<{trig['below']}")
            desc = " ".join(parts) if parts else "numeric"
            return f"#{idx + 1}: {entity} {desc}"
        return f"#{idx + 1}: {entity} state={trig.get('to')}"

    async def async_step_conditions(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        triggers = self._data.get(CONF_TRIGGER, [])
        tidx = self._editing_conditions_trigger_index
        if tidx is None or not (0 <= tidx < len(triggers)):
            return await self.async_step_triggers()
        trig = triggers[tidx]
        conditions = trig.setdefault("conditions", [])

        options: dict[str, str] = {}
        for cidx, cond in enumerate(conditions):
            label = self._condition_summary(cond, cidx)
            options[f"edit_{cidx}"] = f"Edit — {label}"
            options[f"delete_{cidx}"] = f"Delete — {label}"
        options["add"] = "Add condition"
        options["done"] = "Back to triggers"

        if user_input is not None:
            choice = user_input.get("next_step")
            if choice == "add":
                self._editing_condition_index = None
                return await self.async_step_add_condition()
            if choice == "done":
                if not conditions:
                    trig.pop("conditions", None)
                self._editing_conditions_trigger_index = None
                self._editing_condition_index = None
                return await self.async_step_triggers()
            if choice and choice.startswith("edit_"):
                self._editing_condition_index = int(choice.split("_", 1)[1])
                return await self.async_step_edit_condition()
            if choice and choice.startswith("delete_"):
                cidx = int(choice.split("_", 1)[1])
                if 0 <= cidx < len(conditions):
                    del conditions[cidx]
                return await self.async_step_conditions()

        return self.async_show_form(
            step_id="conditions",
            data_schema=self._triggers_schema(options),
            description_placeholders={
                "trigger": self._trigger_summary(trig, tidx),
            },
        )

    async def async_step_add_condition(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._condition_form(user_input, edit_index=None)

    async def async_step_edit_condition(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._condition_form(
            user_input, edit_index=self._editing_condition_index
        )

    async def _condition_form(
        self,
        user_input: dict[str, Any] | None,
        *,
        edit_index: int | None,
    ) -> SubentryFlowResult:
        triggers = self._data.get(CONF_TRIGGER, [])
        tidx = self._editing_conditions_trigger_index
        if tidx is None or not (0 <= tidx < len(triggers)):
            return await self.async_step_triggers()
        trig = triggers[tidx]
        conditions = trig.setdefault("conditions", [])

        errors: dict[str, str] = {}

        if edit_index is not None and 0 <= edit_index < len(conditions):
            existing = conditions[edit_index]
            has_num = (
                existing.get("above") is not None
                or existing.get("below") is not None
            )
            seed = {
                "condition_type": (
                    _CONDITION_TYPE_NUMERIC if has_num else _CONDITION_TYPE_STATE
                ),
                "entity_id": existing.get("entity_id", ""),
                "above": existing.get("above"),
                "below": existing.get("below"),
                "state": _list_to_csv(existing.get("state")),
            }
        else:
            seed = {
                "condition_type": _CONDITION_TYPE_NUMERIC,
                "entity_id": "",
                "above": None,
                "below": None,
                "state": "",
            }

        if user_input is not None:
            ctype = user_input.get("condition_type", _CONDITION_TYPE_NUMERIC)
            entity_id = (user_input.get("entity_id") or "").strip()
            above = user_input.get("above")
            below = user_input.get("below")
            state_raw = (user_input.get("state") or "").strip()

            if not entity_id:
                errors["entity_id"] = "entity_required"

            if ctype == _CONDITION_TYPE_NUMERIC:
                if above in (None, "") and below in (None, ""):
                    errors["base"] = "numeric_needs_threshold"
            elif ctype == _CONDITION_TYPE_STATE:
                if not state_raw:
                    errors["state"] = "state_needs_value"

            if not errors:
                cond: dict[str, Any] = {"entity_id": entity_id}
                if ctype == _CONDITION_TYPE_NUMERIC:
                    if above not in (None, ""):
                        cond["above"] = float(above)
                    if below not in (None, ""):
                        cond["below"] = float(below)
                else:
                    cond["state"] = _csv_to_list_or_scalar(state_raw)

                if edit_index is not None and 0 <= edit_index < len(conditions):
                    conditions[edit_index] = cond
                else:
                    conditions.append(cond)
                return await self.async_step_conditions()

            seed = {**seed, **user_input}

        schema = vol.Schema({
            vol.Required(
                "condition_type",
                default=seed.get("condition_type", _CONDITION_TYPE_NUMERIC),
            ): _CONDITION_TYPE_SELECTOR,
            vol.Required(
                "entity_id", default=seed.get("entity_id", "")
            ): selector.EntitySelector(),
            vol.Optional(
                "above", default=_num_default(seed.get("above"))
            ): vol.Any(vol.Coerce(float), None, ""),
            vol.Optional(
                "below", default=_num_default(seed.get("below"))
            ): vol.Any(vol.Coerce(float), None, ""),
            vol.Optional("state", default=seed.get("state", "")): str,
        })

        step_id = "edit_condition" if edit_index is not None else "add_condition"
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "trigger": self._trigger_summary(trig, tidx),
            },
        )

    @staticmethod
    def _condition_summary(cond: dict[str, Any], idx: int) -> str:
        entity = cond.get("entity_id", "?")
        if cond.get("above") is not None or cond.get("below") is not None:
            parts = []
            if cond.get("above") is not None:
                parts.append(f">{cond['above']}")
            if cond.get("below") is not None:
                parts.append(f"<{cond['below']}")
            return f"#{idx + 1}: {entity} {' '.join(parts)}"
        if cond.get("state") is not None:
            return f"#{idx + 1}: {entity} = {cond['state']}"
        return f"#{idx + 1}: {entity} (advanced)"


def _num_default(v: Any) -> Any:
    if v in (None, ""):
        return ""
    return v


def _list_to_csv(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def _csv_to_list_or_scalar(s: str) -> Any:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) == 1:
        return parts[0]
    return parts
