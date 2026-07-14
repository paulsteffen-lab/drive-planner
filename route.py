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
        text = path.read_text()
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise RouteError(f"Cannot read route file {path}: {exc}") from exc

    try:
        data = json.loads(text)
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
