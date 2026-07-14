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


def test_run_cleans_up_partial_output_on_write_failure(tmp_path, monkeypatch, capsys):
    route_path = tmp_path / "route.json"
    route_path.write_text(
        json.dumps({"name": "Short Loop", "stops": ["Addr A", "Addr B", "Addr C"]})
    )
    output_dir = tmp_path / "output"
    cache_path = tmp_path / "cache.json"

    def failing_write_link_files(links, name_slug, out_dir):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(main, "write_link_files", failing_write_link_files)

    exit_code = main.run(str(route_path), output_dir=str(output_dir), cache_path=str(cache_path))

    assert exit_code == 1
    # The GPX file written before the simulated failure must not survive.
    assert not (output_dir / "short_loop.gpx").exists()
    captured = capsys.readouterr()
    assert "Cannot write output files" in captured.err
