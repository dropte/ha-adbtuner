"""A calendar of what's on ADBTuner's channels, from the configured XMLTV guide."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import ADBTunerConfigEntry
from .coordinator import ADBTunerCoordinator, GuideCoordinator
from .entity import server_device
from .xmltv import Programme


async def async_setup_entry(
    hass: HomeAssistant, entry: ADBTunerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    if runtime.guide:
        async_add_entities([GuideCalendar(runtime.guide, runtime.coordinator)])


class GuideCalendar(CoordinatorEntity[GuideCoordinator], CalendarEntity):
    """Every non-idle programme on a channel ADBTuner can tune."""

    _attr_has_entity_name = True
    _attr_translation_key = "guide"

    def __init__(self, guide: GuideCoordinator, coordinator: ADBTunerCoordinator) -> None:
        super().__init__(guide)
        self.tuner_coordinator = coordinator
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_guide"
        self._attr_device_info = server_device(coordinator)

    def _channels_by_m3u(self) -> dict[str, dict]:
        return {c["m3u_id"]: c for c in self.tuner_coordinator.data.channels.values() if c.get("m3u_id")}

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        events = []
        for m3u_id, channel in self._channels_by_m3u().items():
            for prog in (self.coordinator.data or {}).get(m3u_id, ()):
                if prog.stop <= start or prog.start >= end or prog.is_idle:
                    continue
                events.append(self._event(prog, channel))
        events.sort(key=lambda e: e.start)
        return events

    @staticmethod
    def _event(prog: Programme, channel: dict) -> CalendarEvent:
        where = " ".join(str(p) for p in (channel.get("number"), channel.get("name")) if p)
        return CalendarEvent(
            start=prog.start,
            end=prog.stop,
            summary=prog.title,
            description=prog.description,
            location=where,
            uid=f"{prog.channel_id}-{int(prog.start.timestamp())}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """The next event to start (or one in progress)."""
        now = dt_util.utcnow()
        upcoming = self._events(now, now + timedelta(days=2))
        return upcoming[0] if upcoming else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return self._events(start_date, end_date)
