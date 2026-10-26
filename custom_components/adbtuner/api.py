"""Small async client for the ADBTuner REST API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class ADBTunerError(Exception):
    """Base error talking to ADBTuner."""


class ADBTunerConnectionError(ADBTunerError):
    """ADBTuner could not be reached or returned an unexpected response."""


class ADBTunerClient:
    """Talks to one ADBTuner server."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")

    async def _request(self, method: str, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.request(method, url, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status >= 400:
                    raise ADBTunerConnectionError(f"{method} {path} returned HTTP {resp.status}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ADBTunerConnectionError(f"{method} {path} failed: {err}") from err

    async def get_server_info(self) -> dict[str, Any]:
        """Return {"version": ..., "tuners": [...]} from the health endpoint."""
        data = await self._request("GET", "/up")
        if not isinstance(data, list) or not data or "version" not in data[0]:
            raise ADBTunerConnectionError("Unexpected response from /up; is this an ADBTuner server?")
        # Later entries are tuners, plus bookkeeping such as {"proxy_routes": ...}.
        tuners = [e for e in data[1:] if isinstance(e, dict) and "id" in e]
        return {"version": data[0]["version"], "tuners": tuners}

    async def get_tuners(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v1/tuners")

    async def get_status(self) -> dict[str, dict[str, Any]]:
        """Active tuner locks, keyed by tuner id (as a string)."""
        data = await self._request("GET", "/api/v1/tuners/status")
        return data.get("active_tuners") or {}

    async def get_metadata(self) -> dict[str, dict[str, Any]]:
        """Per-tuner connectivity data, keyed by tuner id (as a string)."""
        data = await self._request("GET", "/api/v1/tuners/metadata")
        return data.get("tuner_data") or {}

    async def get_activity(self) -> list[dict[str, Any]]:
        """Recent tune attempts, newest first."""
        data = await self._request("GET", "/api/v1/activity")
        return data if isinstance(data, list) else []

    async def get_channels(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/v1/channels")
        if isinstance(data, dict):
            data = data.get("channels", [])
        return data

    async def get_screenshot(self, activity_id: int, kind: str) -> bytes | None:
        try:
            data = await self._request("GET", f"/api/v1/activity/{activity_id}/screenshot/{kind}")
        except ADBTunerConnectionError:
            return None
        return data if isinstance(data, bytes) and data else None

    async def unlock_tuner(self, tuner_id: int) -> None:
        await self._request("POST", f"/api/v1/tuners/{tuner_id}/unlock")

    async def retry_tuner(self, tuner_id: int) -> None:
        await self._request("POST", f"/api/v1/tuners/{tuner_id}/retry")
