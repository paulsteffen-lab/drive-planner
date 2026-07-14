# Shareable Driving Routes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert a curated, ordered list of stop addresses (JSON input) into a shareable Google Maps link (or sequence of links for long routes) and a GPX file, so tour-guide routes can be opened directly on a smartphone via free GPS apps.

**Architecture:** A small set of focused modules — `route.py` (load/validate input), `geocode.py` (address → coordinates, cached, via Nominatim), `maps_link.py` (pure URL-building + segmentation logic, no I/O), `gpx.py` (pure GPX XML building, no I/O), `output.py` (all file-writing + filename slugification) — orchestrated by `main.py` as a CLI entrypoint. Pure logic (segmentation, URL building, GPX structure, validation) is unit-tested without any network access; geocoding is tested via dependency injection of a fake geocode function.

**Tech Stack:** Python 3.13, `uv` for dependency/venv management, `geopy` (Nominatim geocoding client), `gpxpy` (GPX file building), `pytest` for testing.

---

## Reference: spec

Full design spec: `docs/superpowers/specs/2026-07-14-shareable-driving-routes-design.md`

## Reference: example route data

The 20-stop "Béziers loop 1" example (loop starts and ends at the same address):

```json
{
  "name": "B\u00e9ziers loop 1",
  "stops": [
    "14 boulevard de Verdun, 34500 B\u00e9ziers",
    "3 Carrefour de l'Hours, 34500 B\u00e9ziers",
    "Avenue du Pr\u00e9sident-Wilson, 34500 B\u00e9ziers",
    "Place Jean-Jaur\u00e8s, 34500 B\u00e9ziers",
    "Place Gabriel-P\u00e9ri, 34500 B\u00e9ziers",
    "Place Pierre-S\u00e9mard, 34500 B\u00e9ziers",
    "Place de la Madeleine, 34500 B\u00e9ziers",
    "Plan des Albigeois, 34500 B\u00e9ziers",
    "Avenue Henri-Galinier, 34500 B\u00e9ziers",
    "Rue de l'Orb, 34500 B\u00e9ziers",
    "74 rue Casimir-P\u00e9ret, 34500 B\u00e9ziers",
    "Avenue Georges-Clemenceau, 34500 B\u00e9ziers",
    "Place du 14-Juillet, 34500 B\u00e9ziers",
    "75 boulevard Colette-Besson, 34500 B\u00e9ziers",
    "Avenue des Olympiades, 34500 B\u00e9ziers",
    "Avenue Jean-Moulin, 34500 B\u00e9ziers",
    "2 rue Valentin-Ha\u00fcy, 34500 B\u00e9ziers",
    "9 avenue Pierre-Verdier, 34500 B\u00e9ziers",
    "Avenue \u00c9mile-Clapar\u00e8de, 34500 B\u00e9ziers",
    "14 boulevard de Verdun, 34500 B\u00e9ziers"
  ]
}
```

---

### Task 1: Project setup — dependencies and gitignore

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Add runtime and dev dependencies to `pyproject.toml`**

Replace the contents of `pyproject.toml` with:

```toml
[project]
name = "drive-planner"
version = "0.1.0"
description = "Convert curated driving-tour stop lists into shareable Google Maps links and GPX files"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "geopy>=2.4",
    "gpxpy>=1.6",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: completes without error, creates/updates `.venv` and `uv.lock`.

- [ ] **Step 3: Add generated files to `.gitignore`**

Append to `.gitignore`:

```

# Generated output
output/
.geocode_cache.json
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .gitignore uv.lock
git commit -m "chore: add geopy, gpxpy, pytest dependencies"
```

---

### Task 2: Route loading and validation

**Files:**
- Create: `route.py`
- Test: `tests/test_route.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_route.py`:

```python
import json

import pytest

from route import Route, RouteError, load_route


def test_load_valid_route(tmp_path):
    route_path = tmp_path / "test_route.json"
    route_path.write_text(
        json.dumps({"name": "Test Loop", "stops": ["Address A", "Address B"]})
    )

    route = load_route(route_path)

    assert route == Route(name="Test Loop", stops=["Address A", "Address B"])


def test_load_route_missing_name(tmp_path):
    route_path = tmp_path / "test_route.json"
    route_path.write_text(json.dumps({"stops": ["Address A", "Address B"]}))

    with pytest.raises(RouteError, match="name"):
        load_route(route_path)


def test_load_route_missing_stops(tmp_path):
    route_path = tmp_path / "test_route.json"
    route_path.write_text(json.dumps({"name": "Test Loop"}))

    with pytest.raises(RouteError, match="stops"):
        load_route(route_path)


def test_load_route_empty_stops(tmp_path):
    route_path = tmp_path / "test_route.json"
    route_path.write_text(json.dumps({"name": "Test Loop", "stops": []}))

    with pytest.raises(RouteError, match="stops"):
        load_route(route_path)


def test_load_route_single_stop(tmp_path):
    route_path = tmp_path / "test_route.json"
    route_path.write_text(json.dumps({"name": "Test Loop", "stops": ["Address A"]}))

    with pytest.raises(RouteError, match="at least 2 stops"):
        load_route(route_path)


def test_load_route_invalid_json(tmp_path):
    route_path = tmp_path / "test_route.json"
    route_path.write_text("{not valid json")

    with pytest.raises(RouteError, match="Invalid JSON"):
        load_route(route_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_route.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'route'`

- [ ] **Step 3: Write the implementation**

Create `route.py`:

```python
"""Load and validate driving-route definitions from JSON files."""

import json
from dataclasses import dataclass
from pathlib import Path


class RouteError(Exception):
    """Raised when a route file is missing, malformed, or invalid."""


@dataclass
class Route:
    name: str
    stops: list[str]


def load_route(path: Path | str) -> Route:
    """Load a Route from a JSON file, validating its structure.

    Expected format:
        {"name": "...", "stops": ["address 1", "address 2", ...]}
    """
    path = Path(path)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise RouteError(f"Invalid JSON in {path}: {exc}") from exc

    name = data.get("name")
    if not name:
        raise RouteError(f"Route file {path} is missing a non-empty 'name' field")

    stops = data.get("stops")
    if not stops or not isinstance(stops, list):
        raise RouteError(f"Route file {path} is missing a non-empty 'stops' list")

    if len(stops) < 2:
        raise RouteError(
            f"Route file {path} must have at least 2 stops, got {len(stops)}"
        )

    return Route(name=name, stops=stops)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_route.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add route.py tests/test_route.py
git commit -m "feat: add route loading and validation"
```

---

### Task 3: Google Maps link building and segmentation (pure logic)

**Files:**
- Create: `maps_link.py`
- Test: `tests/test_maps_link.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_maps_link.py`:

```python
from maps_link import build_link, build_links, segment_stops


def test_segment_stops_under_limit_returns_single_chunk():
    stops = [f"Stop {i}" for i in range(5)]

    chunks = segment_stops(stops, max_points=10)

    assert chunks == [stops]


def test_segment_stops_exactly_at_limit_returns_single_chunk():
    stops = [f"Stop {i}" for i in range(10)]

    chunks = segment_stops(stops, max_points=10)

    assert chunks == [stops]


def test_segment_stops_11_stops_splits_into_two_overlapping_chunks():
    stops = [f"Stop {i}" for i in range(11)]

    chunks = segment_stops(stops, max_points=10)

    assert chunks == [
        [f"Stop {i}" for i in range(0, 10)],
        [f"Stop {i}" for i in range(9, 11)],
    ]


def test_segment_stops_20_stops_splits_into_three_overlapping_chunks():
    stops = [f"Stop {i}" for i in range(20)]

    chunks = segment_stops(stops, max_points=10)

    assert chunks == [
        [f"Stop {i}" for i in range(0, 10)],
        [f"Stop {i}" for i in range(9, 19)],
        [f"Stop {i}" for i in range(18, 20)],
    ]


def test_build_link_with_no_waypoints():
    link = build_link(["Origin Address", "Destination Address"])

    assert link == (
        "https://www.google.com/maps/dir/?api=1"
        "&origin=Origin%20Address"
        "&destination=Destination%20Address"
        "&travelmode=driving"
    )


def test_build_link_with_waypoints():
    link = build_link(["Origin", "Middle 1", "Middle 2", "Destination"])

    assert link == (
        "https://www.google.com/maps/dir/?api=1"
        "&origin=Origin"
        "&destination=Destination"
        "&travelmode=driving"
        "&waypoints=Middle%201%7CMiddle%202"
    )


def test_build_links_short_route_returns_single_link():
    stops = ["Origin", "Middle", "Destination"]

    links = build_links(stops)

    assert len(links) == 1
    assert links[0].startswith("https://www.google.com/maps/dir/?api=1")


def test_build_links_long_route_returns_multiple_links():
    stops = [f"Stop {i}" for i in range(20)]

    links = build_links(stops)

    assert len(links) == 3
    for link in links:
        assert link.startswith("https://www.google.com/maps/dir/?api=1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_maps_link.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'maps_link'`

- [ ] **Step 3: Write the implementation**

Create `maps_link.py`:

```python
"""Build shareable Google Maps multi-stop links, segmenting long routes.

Google Maps' in-app turn-by-turn navigation reliably supports only ~9-10
total stops (origin + up to 8 waypoints + destination). Routes with more
stops are split into multiple sequential links, where each chunk's last
stop becomes the next chunk's origin (no gaps, no backtracking).
"""

from urllib.parse import quote

BASE_URL = "https://www.google.com/maps/dir/?api=1"
DEFAULT_MAX_POINTS = 10


def segment_stops(
    stops: list[str], max_points: int = DEFAULT_MAX_POINTS
) -> list[list[str]]:
    """Split stops into overlapping chunks of at most `max_points` each.

    Each chunk after the first starts with the previous chunk's last stop,
    so consecutive links form a continuous route with no gaps.
    """
    if len(stops) <= max_points:
        return [stops]

    chunks = []
    step = max_points - 1
    i = 0
    while i < len(stops) - 1:
        chunks.append(stops[i : i + max_points])
        i += step
    return chunks


def build_link(chunk: list[str]) -> str:
    """Build a single Google Maps directions URL for one chunk of stops."""
    origin = quote(chunk[0])
    destination = quote(chunk[-1])
    waypoints = chunk[1:-1]

    url = f"{BASE_URL}&origin={origin}&destination={destination}&travelmode=driving"
    if waypoints:
        waypoints_str = "|".join(quote(w) for w in waypoints)
        url += f"&waypoints={waypoints_str}"
    return url


def build_links(stops: list[str]) -> list[str]:
    """Build one or more Google Maps links covering the full stop list."""
    return [build_link(chunk) for chunk in segment_stops(stops)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_maps_link.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add maps_link.py tests/test_maps_link.py
git commit -m "feat: add Google Maps link building with route segmentation"
```

---

### Task 4: Geocoding with local cache

**Files:**
- Create: `geocode.py`
- Test: `tests/test_geocode.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_geocode.py`:

```python
import json

import pytest

from geocode import GeocodedStop, GeocodeError, Geocoder


def make_fake_geocode_func(responses, calls):
    def fake_geocode_func(address):
        calls.append(address)
        return responses.get(address)

    return fake_geocode_func


def test_geocode_returns_coordinates(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = []
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func({"Addr A": (1.0, 2.0)}, calls),
        sleep_seconds=0,
    )

    result = geocoder.geocode("Addr A")

    assert result == (1.0, 2.0)
    assert calls == ["Addr A"]


def test_geocode_uses_cache_on_second_call(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = []
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func({"Addr A": (1.0, 2.0)}, calls),
        sleep_seconds=0,
    )

    geocoder.geocode("Addr A")
    geocoder.geocode("Addr A")

    assert calls == ["Addr A"]  # only called once, second was a cache hit


def test_geocode_persists_cache_to_disk(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = []
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func({"Addr A": (1.0, 2.0)}, calls),
        sleep_seconds=0,
    )

    geocoder.geocode("Addr A")

    assert json.loads(cache_path.read_text()) == {"Addr A": [1.0, 2.0]}


def test_geocode_raises_on_unresolvable_address(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = []
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func({}, calls),
        sleep_seconds=0,
    )

    with pytest.raises(GeocodeError, match="Addr A"):
        geocoder.geocode("Addr A")


def test_geocode_all_returns_geocoded_stops_in_order(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = []
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func(
            {"Addr A": (1.0, 2.0), "Addr B": (3.0, 4.0)}, calls
        ),
        sleep_seconds=0,
    )

    result = geocoder.geocode_all(["Addr A", "Addr B"])

    assert result == [
        GeocodedStop(address="Addr A", lat=1.0, lon=2.0),
        GeocodedStop(address="Addr B", lat=3.0, lon=4.0),
    ]


def test_geocode_all_error_message_includes_stop_index(tmp_path):
    cache_path = tmp_path / "cache.json"
    calls = []
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func({"Addr A": (1.0, 2.0)}, calls),
        sleep_seconds=0,
    )

    with pytest.raises(GeocodeError, match="Stop 2"):
        geocoder.geocode_all(["Addr A", "Addr B (unresolvable)"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_geocode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geocode'`

- [ ] **Step 3: Write the implementation**

Create `geocode.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_geocode.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add geocode.py tests/test_geocode.py
git commit -m "feat: add geocoding with local disk cache"
```

---

### Task 5: GPX file building (pure logic)

**Files:**
- Create: `gpx.py`
- Test: `tests/test_gpx.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gpx.py`:

```python
import gpxpy

from geocode import GeocodedStop
from gpx import build_gpx


def test_build_gpx_contains_all_stops_in_order():
    stops = [
        GeocodedStop(address="Addr A", lat=1.0, lon=2.0),
        GeocodedStop(address="Addr B", lat=3.0, lon=4.0),
    ]

    xml = build_gpx(stops)
    parsed = gpxpy.parse(xml)

    assert len(parsed.routes) == 1
    points = parsed.routes[0].points
    assert len(points) == 2
    assert points[0].latitude == 1.0
    assert points[0].longitude == 2.0
    assert points[0].name == "Addr A"
    assert points[1].latitude == 3.0
    assert points[1].longitude == 4.0
    assert points[1].name == "Addr B"


def test_build_gpx_produces_parseable_xml():
    stops = [
        GeocodedStop(address="Addr A", lat=1.0, lon=2.0),
        GeocodedStop(address="Addr B", lat=3.0, lon=4.0),
        GeocodedStop(address="Addr C", lat=5.0, lon=6.0),
    ]

    xml = build_gpx(stops)
    parsed = gpxpy.parse(xml)

    assert len(parsed.routes[0].points) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_gpx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gpx'`

- [ ] **Step 3: Write the implementation**

Create `gpx.py`:

```python
"""Build a GPX route file from geocoded stops.

GPX is the universal, reliable fallback for apps that handle long stop
lists better than Google Maps' in-app navigation (e.g. OsmAnd, Organic
Maps), and can also be imported into Google Maps as a saved route.
"""

import gpxpy.gpx

from geocode import GeocodedStop


def build_gpx(stops: list[GeocodedStop]) -> str:
    """Build a GPX document containing all stops as an ordered route."""
    gpx = gpxpy.gpx.GPX()
    route = gpxpy.gpx.GPXRoute()
    gpx.routes.append(route)

    for stop in stops:
        point = gpxpy.gpx.GPXRoutePoint(
            latitude=stop.lat, longitude=stop.lon, name=stop.address
        )
        route.points.append(point)

    return gpx.to_xml()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gpx.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add gpx.py tests/test_gpx.py
git commit -m "feat: add GPX route file building"
```

---

### Task 6: Output file writing (slugified filenames)

**Files:**
- Create: `output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_output.py`:

```python
from output import slugify, write_gpx_file, write_link_files


def test_slugify_replaces_spaces_and_accents_and_lowercases():
    assert slugify("Béziers loop 1") == "b_ziers_loop_1"


def test_slugify_empty_name_returns_fallback():
    assert slugify("   ") == "route"


def test_write_gpx_file_creates_file_with_slug_name(tmp_path):
    path = write_gpx_file("<gpx>content</gpx>", "b_ziers_loop_1", tmp_path)

    assert path == tmp_path / "b_ziers_loop_1.gpx"
    assert path.read_text() == "<gpx>content</gpx>"


def test_write_gpx_file_creates_output_dir_if_missing(tmp_path):
    output_dir = tmp_path / "nested" / "output"

    path = write_gpx_file("<gpx/>", "route", output_dir)

    assert path.exists()


def test_write_link_files_single_link(tmp_path):
    paths = write_link_files(["https://example.com/single"], "route", tmp_path)

    assert paths == [tmp_path / "route_link.txt"]
    assert paths[0].read_text() == "https://example.com/single\n"


def test_write_link_files_multiple_legs(tmp_path):
    links = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

    paths = write_link_files(links, "route", tmp_path)

    assert paths == [
        tmp_path / "route_leg1.txt",
        tmp_path / "route_leg2.txt",
        tmp_path / "route_leg3.txt",
    ]
    assert paths[0].read_text() == "https://example.com/1\n"
    assert paths[2].read_text() == "https://example.com/3\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_output.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'output'`

- [ ] **Step 3: Write the implementation**

Create `output.py`:

```python
"""Write generated GPX and link files to disk, with safe filenames."""

import re
from pathlib import Path


def slugify(name: str) -> str:
    """Turn a route name into a filesystem-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower()
    return slug or "route"


def write_gpx_file(gpx_xml: str, name_slug: str, output_dir: Path | str) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name_slug}.gpx"
    path.write_text(gpx_xml)
    return path


def write_link_files(
    links: list[str], name_slug: str, output_dir: Path | str
) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if len(links) == 1:
        path = output_dir / f"{name_slug}_link.txt"
        path.write_text(links[0] + "\n")
        return [path]

    paths = []
    for i, link in enumerate(links, start=1):
        path = output_dir / f"{name_slug}_leg{i}.txt"
        path.write_text(link + "\n")
        paths.append(path)
    return paths
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_output.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add output.py tests/test_output.py
git commit -m "feat: add output file writing with filename slugification"
```

---

### Task 7: CLI orchestration in `main.py`

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main.py`:

```python
import json

import pytest

import geocode
import main


@pytest.fixture(autouse=True)
def fake_geocoder(monkeypatch):
    """Replace Geocoder's network-dependent geocode_func with a fake."""

    def fake_geocode_func(address):
        # Deterministic fake coordinates based on address length.
        return (float(len(address)), float(len(address)) / 2)

    original_init = geocode.Geocoder.__init__

    def patched_init(self, cache_path=".geocode_cache.json", geocode_func=None, sleep_seconds=1.0):
        original_init(
            self,
            cache_path=cache_path,
            geocode_func=fake_geocode_func,
            sleep_seconds=0,
        )

    monkeypatch.setattr(geocode.Geocoder, "__init__", patched_init)


def test_run_short_route_creates_gpx_and_single_link_file(tmp_path):
    route_path = tmp_path / "route.json"
    route_path.write_text(
        json.dumps({"name": "Short Loop", "stops": ["Addr A", "Addr B", "Addr C"]})
    )
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"

    exit_code = main.run(str(route_path), output_dir=str(output_dir), cache_path=str(cache_path))

    assert exit_code == 0
    assert (output_dir / "short_loop.gpx").exists()
    assert (output_dir / "short_loop_link.txt").exists()
    link_content = (output_dir / "short_loop_link.txt").read_text()
    assert link_content.startswith("https://www.google.com/maps/dir/?api=1")


def test_run_long_route_creates_gpx_and_multiple_leg_files(tmp_path):
    stops = [f"Stop {i}" for i in range(20)]
    route_path = tmp_path / "route.json"
    route_path.write_text(json.dumps({"name": "Long Loop", "stops": stops}))
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"

    exit_code = main.run(str(route_path), output_dir=str(output_dir), cache_path=str(cache_path))

    assert exit_code == 0
    assert (output_dir / "long_loop.gpx").exists()
    assert (output_dir / "long_loop_leg1.txt").exists()
    assert (output_dir / "long_loop_leg2.txt").exists()
    assert (output_dir / "long_loop_leg3.txt").exists()


def test_run_returns_nonzero_on_invalid_route_file(tmp_path, capsys):
    route_path = tmp_path / "bad_route.json"
    route_path.write_text(json.dumps({"name": "No Stops"}))
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"

    exit_code = main.run(str(route_path), output_dir=str(output_dir), cache_path=str(cache_path))

    assert exit_code == 1
    assert not output_dir.exists()
    captured = capsys.readouterr()
    assert "stops" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL — `main.run` does not exist yet (`AttributeError`)

- [ ] **Step 3: Write the implementation**

Replace the contents of `main.py`:

```python
"""CLI entrypoint: convert a route JSON file into shareable outputs.

Usage:
    uv run python main.py <route_json_path> [output_dir]
"""

import sys
from pathlib import Path

from geocode import GeocodeError, Geocoder
from gpx import build_gpx
from maps_link import build_links
from output import slugify, write_gpx_file, write_link_files
from route import RouteError, load_route


def run(
    route_path: str,
    output_dir: str = "output",
    cache_path: str = ".geocode_cache.json",
) -> int:
    try:
        route = load_route(route_path)
    except RouteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    geocoder = Geocoder(cache_path=cache_path)
    try:
        geocoded_stops = geocoder.geocode_all(route.stops)
    except GeocodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    name_slug = slugify(route.name)
    output_path = Path(output_dir)

    gpx_xml = build_gpx(geocoded_stops)
    gpx_path = write_gpx_file(gpx_xml, name_slug, output_path)

    links = build_links(route.stops)
    link_paths = write_link_files(links, name_slug, output_path)

    print(f"Route '{route.name}': {len(route.stops)} stops")
    print(f"  GPX file: {gpx_path}")
    if len(link_paths) == 1:
        print(f"  Link file: {link_paths[0]}")
    else:
        print(f"  Segmented into {len(link_paths)} legs:")
        for path in link_paths:
            print(f"    {path}")

    return 0


def main() -> None:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python main.py <route_json_path> [output_dir]", file=sys.stderr)
        sys.exit(1)

    output_dir = sys.argv[2] if len(sys.argv) == 3 else "output"
    sys.exit(run(sys.argv[1], output_dir=output_dir))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: wire up CLI orchestration in main.py"
```

---

### Task 8: Fill in the real Béziers example route and verify end-to-end with real geocoding

**Files:**
- Modify: `resources/routes/beziers_1.json`

- [ ] **Step 1: Fill in the example route file**

Replace the contents of `resources/routes/beziers_1.json`:

```json
{
  "name": "Béziers loop 1",
  "stops": [
    "14 boulevard de Verdun, 34500 Béziers",
    "3 Carrefour de l'Hours, 34500 Béziers",
    "Avenue du Président-Wilson, 34500 Béziers",
    "Place Jean-Jaurès, 34500 Béziers",
    "Place Gabriel-Péri, 34500 Béziers",
    "Place Pierre-Sémard, 34500 Béziers",
    "Place de la Madeleine, 34500 Béziers",
    "Plan des Albigeois, 34500 Béziers",
    "Avenue Henri-Galinier, 34500 Béziers",
    "Rue de l'Orb, 34500 Béziers",
    "74 rue Casimir-Péret, 34500 Béziers",
    "Avenue Georges-Clemenceau, 34500 Béziers",
    "Place du 14-Juillet, 34500 Béziers",
    "75 boulevard Colette-Besson, 34500 Béziers",
    "Avenue des Olympiades, 34500 Béziers",
    "Avenue Jean-Moulin, 34500 Béziers",
    "2 rue Valentin-Haüy, 34500 Béziers",
    "9 avenue Pierre-Verdier, 34500 Béziers",
    "Avenue Émile-Claparède, 34500 Béziers",
    "14 boulevard de Verdun, 34500 Béziers"
  ]
}
```

- [ ] **Step 2: Run the CLI against the real route (real network call to Nominatim)**

Run: `uv run python main.py resources/routes/beziers_1.json`
Expected: exit code 0, stdout shows `Route 'Béziers loop 1': 20 stops`, a GPX file, and 3 leg files listed (20 stops → 3 segments per the segmentation logic in Task 3). This will take ~20 seconds due to the 1-request/second geocoding rate limit on cache misses.

- [ ] **Step 3: Manually inspect one output**

Run: `cat output/b_ziers_loop_1_leg1.txt`
Expected: a single line starting with `https://www.google.com/maps/dir/?api=1&origin=...`. Paste it into a browser to confirm it opens Google Maps with a driving route through the first 10 stops.

- [ ] **Step 4: Commit the filled-in fixture**

```bash
git add resources/routes/beziers_1.json
git commit -m "feat: add real Béziers loop 1 route data"
```

(The `output/` directory and `.geocode_cache.json` are gitignored and intentionally not committed.)

---

### Task 9: Document usage in README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the README**

Replace the contents of `README.md`:

```markdown
# drive-planner

Convert a curated, ordered list of driving-tour stop addresses into formats
that are easy to share and open directly on a smartphone:

- A tappable Google Maps link (or a sequence of links for routes with more
  than ~10 stops, since Google Maps' in-app navigation reliably supports
  only that many)
- A GPX file — a reliable fallback for apps that handle long stop lists
  better (OsmAnd, Organic Maps), and importable into Google Maps too

This tool does not choose or optimize stops — you provide the final,
ordered address list, and it geocodes and packages it for sharing.

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

1. Create a route file in `resources/routes/<name>.json`:

```json
{
  "name": "My route",
  "stops": [
    "14 boulevard de Verdun, 34500 Béziers",
    "Place Jean-Jaurès, 34500 Béziers"
  ]
}
```

2. Run:

```bash
uv run python main.py resources/routes/<name>.json
```

3. Find the outputs in `output/`:
   - `<name>.gpx` — full route, all stops, for GPX-compatible apps
   - `<name>_link.txt` — a single Google Maps link (routes with ≤10 stops)
   - `<name>_leg1.txt`, `_leg2.txt`, ... — sequential Google Maps links
     (routes with more than 10 stops)

Geocoding results are cached in `.geocode_cache.json` (gitignored) to avoid
re-querying the same addresses on repeated runs.

## Testing

```bash
uv run pytest tests -v
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add usage instructions to README"
```

---

## Self-Review Notes

- **Spec coverage:** input format/validation (Task 2), geocoding+cache+fail-fast (Task 4), Google Maps link generation+segmentation (Task 3), GPX generation (Task 5), CLI orchestration+error handling (Task 7), output file location (Task 6), testing strategy including mocked geocoder (Tasks 2–7), real-data fixture (Task 8), README docs (Task 9) — all spec sections are covered.
- **Placeholder scan:** no TBD/TODO markers; every step has complete, runnable code.
- **Type consistency:** `GeocodedStop(address, lat, lon)` defined in Task 4 is used identically in Tasks 5 and 7. `Route(name, stops)` from Task 2 is used identically in Task 7. `build_links`/`segment_stops`/`build_link` signatures from Task 3 match their usage in Task 7. `slugify`/`write_gpx_file`/`write_link_files` from Task 6 match their usage in Task 7.
