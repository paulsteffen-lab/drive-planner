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
