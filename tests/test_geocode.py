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


def test_geocode_recovers_from_corrupted_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    # Write invalid JSON to the cache file
    cache_path.write_text("{ invalid json }")
    calls = []
    
    # Should not raise; should treat corrupted cache as empty
    geocoder = Geocoder(
        cache_path=cache_path,
        geocode_func=make_fake_geocode_func({"Addr A": (1.0, 2.0)}, calls),
        sleep_seconds=0,
    )

    # Should work normally, calling the geocode_func (not a cache hit)
    result = geocoder.geocode("Addr A")
    assert result == (1.0, 2.0)
    assert calls == ["Addr A"]  # Should have called the geocode_func, not found in cache

