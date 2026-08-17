"""Entity model for HASS Console points."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, TYPE_ALARM


class HassConsolePointEntity(RestoreEntity):
    """A single LOG or ALARM point exposed as a ``hass_console.*`` entity.

    Keeps the documented ``hass_console.<type>_<name>`` entity ID while adding
    a unique ID, a registry entry, and last-value restore across restarts.
    """

    _attr_should_poll = False

    def __init__(self, point: dict[str, Any]) -> None:
        self._point = point
        self.entity_id = point["entity_id"]
        self._attr_unique_id = (
            f"{DOMAIN}_{point['type'].lower()}_{point['header'].lower()}"
        )
        prefix = "Alarm" if point["type"] == TYPE_ALARM else "Log"
        self._attr_name = f"HASS Console {prefix}: {point['header']}"
        self._state: str | None = None
        self._attrs: dict[str, Any] = {
            "category": point.get("category", ""),
            "note": point.get("note", ""),
        }

    @property
    def state(self) -> str | None:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attrs

    def update_value(self, state: str, attributes: dict[str, Any]) -> None:
        """Set the current state + attributes and write to HA."""
        self._state = state
        self._attrs = {k: v for k, v in attributes.items() if k != "friendly_name"}
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last known value when HA restarts."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            self._state = last.state
            restored = dict(last.attributes)
            restored.pop("friendly_name", None)
            self._attrs = restored
