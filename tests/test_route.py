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
