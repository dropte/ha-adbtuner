"""Screenshot of the most recent tune, as captured by ADBTuner."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ADBTunerConfigEntry
from .coordinator import ADBTunerCoordinator
from .entity import ADBTunerTunerEntity, ts

# ADBTuner saves up to three screenshots per tune: "before" (often a sleeping device),
# "after" (just after the tune commands, usually still a launcher) and "end" (taken when
# the stream stops, which shows what was actually on). Prefer the most informative one.
SCREENSHOT_KINDS = ("end", "after", "before")


async def async_setup_entry(
    hass: HomeAssistant, entry: ADBTunerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(LastTuneScreenshot(hass, coordinator, tuner_id) for tuner_id in coordinator.data.tuners)


class LastTuneScreenshot(ADBTunerTunerEntity, ImageEntity):
    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        ADBTunerTunerEntity.__init__(self, coordinator, tuner_id, "last_tune_screenshot")
        ImageEntity.__init__(self, hass)
        self._activity_id: int | None = None
        self._activity_key: tuple | None = None
        self._sync_activity()

    def _sync_activity(self) -> None:
        act = self.coordinator.data.last_activity(self.tuner_id) or {}
        # The "end" screenshot only appears once the stream stops, so refresh on that too.
        key = (act.get("id"), act.get("ended_at"))
        if key != self._activity_key:
            self._activity_key = key
            self._activity_id = act.get("id")
            self._cached_image = None
            self._attr_image_last_updated = ts(act.get("ended_at") or act.get("started_at"))

    @callback
    def _handle_coordinator_update(self) -> None:
        self._sync_activity()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        if self._activity_id is None:
            return None
        for kind in SCREENSHOT_KINDS:
            if image := await self.coordinator.client.get_screenshot(self._activity_id, kind):
                return image
        return None
