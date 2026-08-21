"""Repairs flow for HASS Console."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONSOLE_YAML,
    CONF_NAME,
    CONF_TYPE,
    DEFAULT_CONSOLE_YAML,
    ISSUE_YAML_DEPRECATED,
    SUBENTRY_ALARM,
    SUBENTRY_LOG,
    TYPE_ALARM,
    TYPE_LOG,
)

_LOGGER = logging.getLogger(__name__)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    if issue_id == ISSUE_YAML_DEPRECATED:
        return ImportYamlPointsFlow((data or {}).get("entry_id"))
    return ConfirmRepairFlow()


class ImportYamlPointsFlow(RepairsFlow):

    def __init__(self, entry_id: str | None) -> None:
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        from . import _load_yaml_sync, _points_from_subentries

        hass = self.hass
        entry = (
            hass.config_entries.async_get_entry(self._entry_id)
            if self._entry_id
            else None
        )
        if entry is None:
            return self.async_abort(reason="no_points")

        settings = {**entry.data, **entry.options}
        yaml_path = settings.get(CONF_CONSOLE_YAML, DEFAULT_CONSOLE_YAML)
        yaml_points: dict[str, Any] = {}
        if yaml_path:
            yaml_points = await hass.async_add_executor_job(
                _load_yaml_sync, yaml_path
            )
        sub_points = _points_from_subentries(entry)
        yaml_only_names = [n for n in yaml_points if n not in sub_points]
        if not yaml_only_names:
            return self.async_abort(reason="no_points")

        if user_input is not None:
            imported = 0
            skipped: list[str] = []
            for name in yaml_only_names:
                cfg = yaml_points.get(name)
                if not isinstance(cfg, dict):
                    skipped.append(name)
                    continue
                subentry_type = _subentry_type_for(cfg)
                if subentry_type is None:
                    skipped.append(name)
                    _LOGGER.warning(
                        "HASS Console: cannot import YAML point '%s' — "
                        "unrecognized type '%s', skipping",
                        name, cfg.get(CONF_TYPE, ""),
                    )
                    continue
                hass.config_entries.async_add_subentry(
                    entry,
                    ConfigSubentry(
                        data=_build_subentry_data(name, cfg),
                        subentry_type=subentry_type,
                        title=name,
                        unique_id=None,
                    ),
                )
                imported += 1

            _LOGGER.info(
                "HASS Console: imported %d YAML point(s) as UI subentries "
                "(skipped %d)",
                imported, len(skipped),
            )

            try:
                await hass.config_entries.async_reload(entry.entry_id)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "HASS Console: reload after YAML import failed: %s", err
                )
                return self.async_abort(reason="reload_failed")

            return self.async_create_entry(title="", data={})

        names_block = "\n".join(f"- **{n}**" for n in yaml_only_names)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "count": str(len(yaml_only_names)),
                "names": names_block,
            },
        )


def _subentry_type_for(cfg: dict[str, Any]) -> str | None:
    t = str(cfg.get(CONF_TYPE, "")).upper()
    if t == TYPE_LOG:
        return SUBENTRY_LOG
    if t == TYPE_ALARM:
        return SUBENTRY_ALARM
    return None


def _build_subentry_data(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    data = dict(cfg)
    data[CONF_NAME] = name
    data[CONF_TYPE] = str(cfg.get(CONF_TYPE, "")).upper()
    return data
