"""Tests for orchestrate.router — input kind to step chain."""

from material_to_notes.orchestrate import router as RT


def test_classify_by_extension():
    assert RT.classify("a.mp4") == "video"
    assert RT.classify("a.MP3") == "audio"
    assert RT.classify("a.png") == "image"
    assert RT.classify("a.pdf") == "pdf"
    assert RT.classify("a.docx") == "docx"


def test_classify_url_and_dir(tmp_path):
    assert RT.classify("https://x.com/v") == "links"
    assert RT.classify(tmp_path) == "album"


def test_classify_unknown():
    assert RT.classify("a.exe") == RT.UNKNOWN
    assert RT.classify("") == RT.UNKNOWN
    assert RT.classify("   ") == RT.UNKNOWN


def test_route_direct_kinds():
    assert RT.route("video") == ("media", "clean", "note")
    assert RT.route("pdf") == ("document", "clean", "note")


def test_route_source_kinds():
    assert RT.route("terms") == ("fetch",)
    assert RT.route("links") == ("fetch",)


def test_route_unknown_is_empty():
    assert RT.route("nothing") == ()
    assert RT.route(RT.UNKNOWN) == ()


def test_route_after_fetch():
    assert RT.route_after_fetch(["video"]) == ("media", "clean", "note")
    assert RT.route_after_fetch(["pdf"]) == ("document", "clean", "note")
    assert RT.route_after_fetch(["pdf", "video"]) == ("media", "clean", "note")
    assert RT.route_after_fetch([]) == ()
