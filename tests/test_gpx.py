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
