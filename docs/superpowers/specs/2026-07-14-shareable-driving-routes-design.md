# Shareable Driving Routes — Design

## Purpose

Convert a manually-curated, ordered list of stop addresses (a driving tour, e.g.
for a tour-guide business) into formats that are easy to share with clients and
open directly on a smartphone via free GPS apps:

- A tappable Google Maps link (or a sequence of links for long routes)
- A GPX file, as a robust fallback for apps that handle many stops better
  (OsmAnd, Organic Maps, or import into Google Maps)

The tool does **not** select or optimize stops — the ordered address list is
provided by the user (or business) and is treated as final. The tool's job is
purely to geocode and package that list for sharing.

## Input format & data model

Route files live in `resources/routes/<name>.json`:

```json
{
  "name": "Béziers loop 1",
  "stops": [
    "14 boulevard de Verdun, 34500 Béziers",
    "3 Carrefour de l'Hours, 34500 Béziers",
    "Avenue du Président-Wilson, 34500 Béziers"
  ]
}
```

A `Route` dataclass (`name: str`, `stops: list[str]`) is loaded and validated
by `route.py`:
- `stops` must be present and contain at least 2 addresses
- Clear error messages identify the problem (missing field, empty list, etc.)

`resources/routes/beziers_1.json` (currently empty) is filled in as the first
real fixture, using the 20-stop Béziers example provided during brainstorming.

## Geocoding

`geocode.py` wraps `geopy`'s `Nominatim` geocoder (free, OpenStreetMap-based,
no API key required).

- For each address, check a local on-disk cache (`.geocode_cache.json`, keyed
  by the exact address string) before calling the geocoding service.
- On a cache miss, call Nominatim, sleep 1 second (to respect Nominatim's
  usage policy rate limit), then store the result in the cache.
- If an address cannot be geocoded, fail fast with a clear error naming the
  offending address and its stop index. Silently dropping a stop from a
  client-facing route is worse than stopping and asking the user to fix the
  source data.

## Google Maps link generation

`maps_link.py` builds URLs using Google's documented format:

```
https://www.google.com/maps/dir/?api=1&origin=<first>&destination=<last>&waypoints=<addr2>|<addr3>|...&travelmode=driving
```

**Constraint:** Google Maps' in-app turn-by-turn navigation reliably supports
only ~9-10 total stops (origin + up to 8 waypoints + destination). Routes
with more stops than that are **segmented** into multiple sequential links:

- Chunks of at most 10 points each (origin + ≤8 waypoints + destination)
- Each chunk's last stop becomes the next chunk's origin (no gaps, no
  backtracking, no duplicated travel)
- Routes with ≤10 stops produce a single link; no segmentation needed

Output files:
- `output/<route_name>_link.txt` — single link, when no segmentation needed
- `output/<route_name>_leg1.txt`, `_leg2.txt`, ... — one file per segment,
  when segmentation is needed

## GPX file generation

`gpx.py` uses `gpxpy` to build a single GPX route (`<rte>`) containing all
geocoded stops as `<rtept>` waypoints, named after their address, in order.
One `.gpx` file is produced per route regardless of stop count — this is the
universal, reliable fallback for apps that handle long stop lists better than
Google Maps' in-app navigation (e.g. OsmAnd, Organic Maps), and can also be
imported into Google Maps as a saved list/route.

Output file: `output/<route_name>.gpx`

## CLI & orchestration

`main.py` accepts a route JSON path as its argument:

```
uv run python main.py resources/routes/beziers_1.json
```

Steps:
1. Load and validate the route (`route.py`)
2. Geocode all stops, using the on-disk cache (`geocode.py`)
3. Write `output/<route_name>.gpx` (`gpx.py`)
4. Compute link segments and write `output/<route_name>_link.txt` (single) or
   `output/<route_name>_leg1.txt`, `_leg2.txt`, etc. (segmented)
   (`maps_link.py`)
5. Print a short summary to stdout: stop count, files written, segment count
   if segmented

Errors (invalid JSON, unresolvable address, network failure) print a clear,
actionable message and exit with a non-zero status. No partial or corrupt
output files are left behind on failure.

## Testing

- `route.py`: unit tests for loading/validation (valid route, missing
  `stops`, empty `stops`, single-stop route)
- `maps_link.py`: unit tests for segmentation math — given N stops, verify
  correct number of segments, correct chunk boundaries/overlap, and correct
  URL construction for both single-link and segmented cases
- `gpx.py`: unit tests verifying GPX structure — given a list of geocoded
  stops, output contains the right number of `<rtept>` elements in the right
  order with correct coordinates
- `geocode.py`: tested with a mocked/fake geocoder — no real network calls,
  no dependency on Nominatim availability or rate limits in tests; verify
  cache-hit/cache-miss behavior and fail-fast behavior on unresolvable
  addresses
- One end-to-end test runs the full `main.py` flow with the geocoder mocked,
  checking that the expected output files are created with correct content

Test runner: `pytest`, run via `uv run pytest tests -v`.

## Out of scope (for this iteration)

- Selecting, suggesting, or optimizing the order of stops
- Waze-specific link format
- A web UI (CLI only)
- Batch-processing multiple route files in a single invocation
