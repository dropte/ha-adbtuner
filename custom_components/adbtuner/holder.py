"""Hold an ADBTuner stream open so a tuner stays on a channel.

ADBTuner only tunes while a client is reading the stream, and releases the tuner when the
client disconnects. To use a tuner for watching the encoder directly (or anything else
outside an IPTV client), Home Assistant reads the stream and discards it until stopped.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import aiohttp

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOLD = timedelta(hours=4)
CHUNK = 64 * 1024


@dataclass
class HoldSession:
    tuner_id: int
    channel_id: int
    started: datetime
    until: datetime
    task: asyncio.Task


class StreamHolder:
    """One held stream per tuner."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        self.hass = hass
        self.base_url = base_url
        self.sessions: dict[int, HoldSession] = {}
        self._listeners: list = []

    @callback
    def async_add_listener(self, update_callback) -> callable:
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def start(self, tuner_id: int, channel_id: int, duration: timedelta = DEFAULT_HOLD) -> None:
        await self.stop(tuner_id)
        now = dt_util.utcnow()
        task = self.hass.async_create_background_task(
            self._run(tuner_id, channel_id, duration), f"adbtuner hold tuner {tuner_id}"
        )
        self.sessions[tuner_id] = HoldSession(tuner_id, channel_id, now, now + duration, task)
        self._notify()

    async def stop(self, tuner_id: int) -> None:
        session = self.sessions.pop(tuner_id, None)
        if session and not session.task.done():
            session.task.cancel()
            try:
                await session.task
            except asyncio.CancelledError:
                pass
        if session:
            self._notify()

    async def stop_all(self) -> None:
        for tuner_id in list(self.sessions):
            await self.stop(tuner_id)

    async def _run(self, tuner_id: int, channel_id: int, duration: timedelta) -> None:
        # ADBTuner has no "this tuner" stream route; it reserves a free tuner itself (by
        # priority), which is the requested one when there is a single tuner.
        url = f"{self.base_url}/stream/{channel_id}"
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(duration.total_seconds()):
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as resp:
                    if resp.status >= 400:
                        _LOGGER.warning("ADBTuner refused to tune channel %s on tuner %s: HTTP %s",
                                        channel_id, tuner_id, resp.status)
                        return
                    async for _ in resp.content.iter_chunked(CHUNK):
                        pass
        except TimeoutError:
            _LOGGER.info("Released tuner %s after the %s hold limit", tuner_id, duration)
        except aiohttp.ClientError as err:
            _LOGGER.warning("Stream for tuner %s ended: %s", tuner_id, err)
        finally:
            current = self.sessions.get(tuner_id)
            if current and current.task is asyncio.current_task():
                self.sessions.pop(tuner_id, None)
                self.hass.loop.call_soon(self._notify)
