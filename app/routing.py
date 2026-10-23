import asyncio
import json
import logging
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance for a resilient routing estimate."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(min(1.0, sqrt(a)))


class RouteClient:
    def __init__(self, base_url: str, timeout_seconds: float = 1.2,
                 redis: Redis | None = None, cache_ttl: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = min(timeout_seconds, 1.49)
        self.redis = redis
        self.cache_ttl = cache_ttl
        self._failures = 0
        self._open_until = 0.0
        self._lock = asyncio.Lock()

    async def route(self, origin: tuple[float, float], destination: tuple[float, float]) -> dict[str, Any]:
        key = "route:" + ":".join(f"{v:.3f}" for v in (*origin, *destination))
        if self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:
                logger.warning("route_cache_unavailable", exc_info=True)
        now = asyncio.get_running_loop().time()
        if now < self._open_until:
            return self._fallback(origin, destination, "circuit_open")
        try:
            url = (f"{self.base_url}/route/v1/driving/{origin[1]},{origin[0]};"
                   f"{destination[1]},{destination[0]}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params={"overview": "false"})
                response.raise_for_status()
                body = response.json()
                route = body["routes"][0]
                result = {"distance_km": route["distance"] / 1000,
                          "duration_h": route["duration"] / 3600,
                          "fallback": False}
            async with self._lock:
                self._failures = 0
            if self.redis:
                try:
                    await self.redis.set(key, json.dumps(result), ex=self.cache_ttl)
                except Exception:
                    logger.warning("route_cache_write_failed", exc_info=True)
            return result
        except Exception as exc:
            async with self._lock:
                self._failures += 1
                if self._failures >= 3:
                    self._open_until = asyncio.get_running_loop().time() + 15
                    self._failures = 0
            logger.warning("osrm_failed_using_haversine", error=str(exc))
            return self._fallback(origin, destination, type(exc).__name__)

    async def route_many(self, origin: tuple[float, float],
                         destinations: list[tuple[float, float]]) -> list[dict[str, Any]]:
        """Request one OSRM table for candidates, with TTL caching and Haversine fallback."""
        if not destinations:
            return []
        key = "route-matrix:" + ":".join(
            f"{v:.3f}" for pair in (origin, *destinations) for v in pair)
        if self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:
                logger.warning("route_matrix_cache_unavailable", exc_info=True)
        if asyncio.get_running_loop().time() < self._open_until:
            return [self._fallback(origin, destination, "circuit_open")
                    for destination in destinations]
        try:
            points = [origin, *destinations]
            coordinates = ";".join(f"{lon},{lat}" for lat, lon in points)
            url = f"{self.base_url}/table/v1/driving/{coordinates}"
            params = {"sources": "0", "destinations": ";".join(
                str(index) for index in range(1, len(points))),
                "annotations": "distance,duration"}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                body = response.json()
            distances = body["distances"][0]
            durations = body["durations"][0]
            result = [{"distance_km": distance / 1000, "duration_h": duration / 3600,
                       "fallback": False}
                      for distance, duration in zip(distances, durations, strict=True)]
            async with self._lock:
                self._failures = 0
            if self.redis:
                try:
                    await self.redis.set(key, json.dumps(result), ex=self.cache_ttl)
                except Exception:
                    logger.warning("route_matrix_cache_write_failed", exc_info=True)
            return result
        except Exception as exc:
            async with self._lock:
                self._failures += 1
                if self._failures >= 3:
                    self._open_until = asyncio.get_running_loop().time() + 15
                    self._failures = 0
            logger.warning("osrm_matrix_failed_using_haversine", error=str(exc))
            return [self._fallback(origin, destination, type(exc).__name__)
                    for destination in destinations]

    @staticmethod
    def _fallback(origin: tuple[float, float], destination: tuple[float, float],
                  reason: str) -> dict[str, Any]:
        km = haversine_km(*origin, *destination) * 1.3
        return {"distance_km": km, "duration_h": km / 45.0, "fallback": True,
                "fallback_reason": reason}
