"""Geocode addresses to coordinates, with a local on-disk cache.

Uses geopy's Nominatim (OpenStreetMap) geocoder by default: free, no API
key required. Nominatim's usage policy requires no more than 1 request per
second, so cache misses sleep between requests; cache hits do not.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from geopy.geocoders import Nominatim

GeocodeFunc = Callable[[str], tuple[float, float] | None]


class GeocodeError(Exception):
    """Raised when an address cannot be geocoded."""


@dataclass
class GeocodedStop:
    address: str
    lat: float
    lon: float


def _nominatim_geocode_func() -> GeocodeFunc:
    nominatim = Nominatim(user_agent="drive-planner")

    def geocode_func(address: str) -> tuple[float, float] | None:
        location = nominatim.geocode(address)
        if location is None:
            return None
        return (location.latitude, location.longitude)

    return geocode_func


class Geocoder:
    def __init__(
        self,
        cache_path: Path | str = ".geocode_cache.json",
        geocode_func: GeocodeFunc | None = None,
        sleep_seconds: float = 1.0,
    ):
        self.cache_path = Path(cache_path)
        self._cache: dict[str, list[float]] = self._load_cache()
        self._geocode_func = geocode_func or _nominatim_geocode_func()
        self.sleep_seconds = sleep_seconds

    def _load_cache(self) -> dict[str, list[float]]:
        if self.cache_path.exists():
            return json.loads(self.cache_path.read_text())
        return {}

    def _save_cache(self) -> None:
        self.cache_path.write_text(json.dumps(self._cache, indent=2))

    def geocode(self, address: str) -> tuple[float, float]:
        if address in self._cache:
            lat, lon = self._cache[address]
            return (lat, lon)

        result = self._geocode_func(address)
        if result is None:
            raise GeocodeError(f"Could not geocode address: {address!r}")

        lat, lon = result
        self._cache[address] = [lat, lon]
        self._save_cache()
        time.sleep(self.sleep_seconds)
        return (lat, lon)

    def geocode_all(self, addresses: list[str]) -> list[GeocodedStop]:
        results = []
        for i, address in enumerate(addresses):
            try:
                lat, lon = self.geocode(address)
            except GeocodeError as exc:
                raise GeocodeError(f"Stop {i + 1}: {exc}") from exc
            results.append(GeocodedStop(address=address, lat=lat, lon=lon))
        return results
