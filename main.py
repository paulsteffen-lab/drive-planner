"""CLI entrypoint: convert a route JSON file into shareable outputs.

Usage:
    uv run python main.py <route_json_path> [output_dir]
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from geocode import GeocodeError, Geocoder
from gpx import build_gpx
from maps_link import build_links
from output import slugify, write_gpx_file, write_link_files
from route import Route, RouteError, load_route


@dataclass
class GenerateResult:
    route_name: str
    stop_count: int
    gpx_path: Path
    link_paths: list[Path]
    links: list[str]


def generate(
    route: Route,
    output_dir: str = "output",
    cache_path: str = ".geocode_cache.json",
) -> GenerateResult:
    """Run the geocode -> GPX -> Maps-link pipeline for an already-loaded Route.

    Raises GeocodeError if an address cannot be geocoded, or OSError if the
    output files cannot be written. On OSError, any partially-written output
    files for this route are removed before re-raising, so a failed run
    never leaves misleading artifacts behind.
    """
    geocoder = Geocoder(cache_path=cache_path)
    geocoded_stops = geocoder.geocode_all(route.stops)

    name_slug = slugify(route.name)
    output_path = Path(output_dir)

    try:
        gpx_xml = build_gpx(geocoded_stops)
        gpx_path = write_gpx_file(gpx_xml, name_slug, output_path)

        links = build_links(route.stops)
        link_paths = write_link_files(links, name_slug, output_path)
    except OSError:
        for stray in output_path.glob(f"{name_slug}*"):
            stray.unlink(missing_ok=True)
        raise

    return GenerateResult(
        route_name=route.name,
        stop_count=len(route.stops),
        gpx_path=gpx_path,
        link_paths=link_paths,
        links=links,
    )


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

    try:
        result = generate(route, output_dir=output_dir, cache_path=cache_path)
    except GeocodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: Cannot write output files: {exc}", file=sys.stderr)
        return 1

    print(f"Route '{result.route_name}': {result.stop_count} stops")
    print(f"  GPX file: {result.gpx_path}")
    if len(result.link_paths) == 1:
        print(f"  Link file: {result.link_paths[0]}")
    else:
        print(f"  Segmented into {len(result.link_paths)} legs:")
        for path in result.link_paths:
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
