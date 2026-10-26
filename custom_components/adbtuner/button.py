"""Buttons for ADBTuner."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ADBTunerConfigEntry
from .api import ADBTunerError
from .coordinator import ADBTunerCoordinator
from .entity import ADBTunerTunerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ADBTunerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        entity
        for tuner_id in coordinator.data.tuners
        for entity in (UnlockButton(coordinator, tuner_id), RetryButton(coordinator, tuner_id))
    )


class _TunerButton(ADBTunerTunerEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    async def _call(self, func) -> None:
        try:
            await func(self.tuner_id)
        except ADBTunerError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class UnlockButton(_TunerButton):
    """Release a tuner ADBTuner thinks is still in use."""

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "unlock")

    async def async_press(self) -> None:
        await self._call(self.coordinator.client.unlock_tuner)


class RetryButton(_TunerButton):
    """Ask ADBTuner to retry a tuner that failed its connectivity check."""

    def __init__(self, coordinator: ADBTunerCoordinator, tuner_id: int) -> None:
        super().__init__(coordinator, tuner_id, "retry")

    async def async_press(self) -> None:
        await self._call(self.coordinator.client.retry_tuner)
