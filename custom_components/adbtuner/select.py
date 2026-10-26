"""Pick a channel for a tuner; Home Assistant then holds the stream so the tuner stays on it."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ADBTunerConfigEntry
from .coordinator import ADBTunerCoordinator, GuideCoordinator
from .entity import ADBTunerTunerEntity
from .holder import StreamHolder
from .xmltv import programme_at

SEPARATOR = " · "


async def async_setup_entry(
    hass: HomeAssistant, entry: ADBTunerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        TuneSelect(runtime.coordinator, tuner_id, runtime.guide, runtime.holder)
        for tuner_id in runtime.coordinator.data.tuners
    )


class TuneSelect(ADBTunerTunerEntity, SelectEntity):
    """Options are what's airing now (from the guide) plus channels the guide doesn't cover."""

    def __init__(
        self,
        coordinator: ADBTunerCoordinator,
        tuner_id: int,
        guide: GuideCoordinator | None,
        holder: StreamHolder,
    ) -> None:
        super().__init__(coordinator, tuner_id, "tune")
        self.guide = guide
        self.holder = holder

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.holder.async_add_listener(self.async_write_ha_state))
        if self.guide:
            self.async_on_remove(self.guide.async_add_listener(self._handle_coordinator_update))

    def _label(self, channel: dict[str, Any]) -> str | None:
        """'2306 · Chelsea vs. Tottenham', or '2001 · ESPN' for channels without guide data."""
        number = channel.get("number")
        if self.guide and self.guide.data and channel.get("m3u_id") in self.guide.data:
            prog = programme_at(self.guide.data[channel["m3u_id"]], dt_util.utcnow())
            if prog is None or prog.is_idle:
                return None  # an empty lane; leave it out of the list
            return f"{number}{SEPARATOR}{prog.title}"
        return f"{number}{SEPARATOR}{channel.get('name')}"

    def _labels(self) -> dict[str, dict[str, Any]]:
        out = {}
        for channel in sorted(self.coordinator.data.channels.values(), key=lambda c: int(c.get("number") or 0)):
            if label := self._label(channel):
                out[label[:255]] = channel
        return out

    @property
    def options(self) -> list[str]:
        options = list(self._labels())
        if (current := self.current_option) and current not in options:
            options.insert(0, current)
        return options

    @property
    def current_option(self) -> str | None:
        session = self.holder.sessions.get(self.tuner_id)
        if not session:
            return None
        channel = self.coordinator.data.channels.get(session.channel_id)
        return (self._label(channel) or f"{channel.get('number')}{SEPARATOR}{channel.get('name')}") if channel else None

    async def async_select_option(self, option: str) -> None:
        channel = self._labels().get(option) or self.coordinator.find_channel(option)
        if channel is None:
            raise HomeAssistantError(f"Unknown channel '{option}'")
        await self.holder.start(self.tuner_id, channel["id"])
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        session = self.holder.sessions.get(self.tuner_id)
        return {"held_since": session.started, "held_until": session.until} if session else {}
