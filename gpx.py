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
