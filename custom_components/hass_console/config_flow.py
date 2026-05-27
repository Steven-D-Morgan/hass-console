"""Config flow for HASS Console."""
from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_CONSOLE_YAML,
    CONF_ALARM_CSV,
    CONF_LOG_CSV,
    DEFAULT_CONSOLE_YAML,
    DEFAULT_ALARM_CSV,
    DEFAULT_LOG_CSV,
)

_LOGGER = logging.getLogger(__name__)


def _validate_paths(data: dict[str, Any]) -> dict[str, str]:
    """Return a dict of {field_key: error_code} for any invalid paths."""
    errors: dict[str, str] = {}

    yaml_path = (data.get(CONF_CONSOLE_YAML) or "").strip()
    alarm_path = (data.get(CONF_ALARM_CSV) or "").strip()
    log_path = (data.get(CONF_LOG_CSV) or "").strip()

    if not yaml_path:
        errors[CONF_CONSOLE_YAML] = "yaml_required"
    elif not os.path.isfile(yaml_path):
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


class HassConsoleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the user-initiated setup step."""
        # Only one instance — the engine is a singleton
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
            vol.Required(
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
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow for editing settings later."""
        return HassConsoleOptionsFlow()


class HassConsoleOptionsFlow(config_entries.OptionsFlow):
    """Options flow — edit paths after initial setup.

    Note: do NOT override __init__ to store config_entry —
    HA provides self.config_entry automatically since 2024.11.
    """

    async def async_step_init(self, user_input=None):
        """Show/handle the options form."""
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
            vol.Required(
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
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
