"""Data update coordinators for ADBTuner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ADBTunerClient, ADBTunerError
from .const import CHANNELS_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, GUIDE_SCAN_INTERVAL
from .xmltv import Programme, parse_xmltv

_LOGGER = logging.getLogger(__name__)


@dataclass
class ADBTunerData:
    """A snapshot of the ADBTuner server."""

    version: str
    tuners: dict[int, dict[str, Any]]
    status: dict[int, dict[str, Any]]
    metadata: dict[int, dict[str, Any]]
    activity: list[dict[str, Any]]
    channels: dict[int, dict[str, Any]] = field(default_factory=dict)

    def last_activity(self, tuner_id: int) -> dict[str, Any] | None:
        return next((a for a in self.activity if a.get("tuner_id") == tuner_id), None)


class ADBTunerCoordinator(DataUpdateCoordinator[ADBTunerData]):
    """Polls tuner state, health and recent activity."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ADBTunerClient) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )
        self.client = client
        self._channels: dict[int, dict[str, Any]] = {}
        self._channels_fetched: datetime | None = None

    async def _async_update_data(self) -> ADBTunerData:
        try:
            info = await self.client.get_server_info()
            tuners = await self.client.get_tuners()
            status = await self.client.get_status()
            metadata = await self.client.get_metadata()
            activity = await self.client.get_activity()
            now = dt_util.utcnow()
            if self._channels_fetched is None or now - self._channels_fetched > CHANNELS_REFRESH_INTERVAL:
                self._channels = {c["id"]: c for c in await self.client.get_channels()}
                self._channels_fetched = now
        except ADBTunerError as err:
            raise UpdateFailed(str(err)) from err
        return ADBTunerData(
            version=info["version"],
            tuners={t["id"]: t for t in tuners},
            status={int(k): v for k, v in status.items()},
            metadata={int(k): v for k, v in metadata.items()},
            activity=activity,
            channels=self._channels,
        )

    def find_channel(self, query: str) -> dict[str, Any] | None:
        """Match a channel by number, M3U id, id or (case-insensitive) name."""
        query = str(query).strip()
        # Accept select-style labels such as "2306 · Chelsea vs. Tottenham".
        number = query.split(" ", 1)[0]
        channels = self.data.channels.values() if self.data else ()
        for c in channels:
            if str(c.get("number")) in (query, number) or c.get("m3u_id") == query or str(c.get("id")) == query:
                return c
        lowered = query.lower()
        return next((c for c in channels if str(c.get("name", "")).lower() == lowered), None)


class GuideCoordinator(DataUpdateCoordinator[dict[str, list[Programme]]]):
    """Downloads and parses an XMLTV guide matching ADBTuner's channel ids."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, url: str) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} guide", update_interval=GUIDE_SCAN_INTERVAL
        )
        self.url = url

    async def _async_update_data(self) -> dict[str, list[Programme]]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self.url, timeout=60) as resp:
                resp.raise_for_status()
                raw = await resp.read()
        except Exception as err:  # noqa: BLE001 - any fetch failure just marks the guide unavailable
            raise UpdateFailed(f"Could not download guide: {err}") from err
        return await self.hass.async_add_executor_job(parse_xmltv, raw)
