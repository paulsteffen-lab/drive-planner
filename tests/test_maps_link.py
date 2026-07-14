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
