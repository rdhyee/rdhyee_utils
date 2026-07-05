"""
Tests for rdhyee_utils.bike.model — parsing, navigation, validation, and the
round-trip guarantee (parse → serialize → byte-compare).
"""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[2]))  # repo root, like test_bike.py

from rdhyee_utils.bike.model import (  # noqa: E402
    BikeDoc,
    BikeFormatError,
    serialize_inline,
)

DATA = Path(__file__).parent / "data"
KITCHEN_SINK = DATA / "kitchen_sink.bike"
MINIMAL = DATA / "minimal.bike"

# Real, Bike.app-written documents (only exist on Raymond's machine).
REAL_BIKE_DIR = Path.home() / "obsidian" / "Main" / "bike"
REAL_FILES = ["overall.bike", "Sandbox.bike", "test_20231010.bike", "test_overall.bike"]


@pytest.fixture
def doc() -> BikeDoc:
    return BikeDoc.from_path(KITCHEN_SINK)


# ---------------------------------------------------------------------------
# round-trip guarantee
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", [KITCHEN_SINK, MINIMAL])
def test_roundtrip_fixtures_byte_identical(fixture):
    orig = fixture.read_bytes()
    assert BikeDoc.from_bytes(orig).to_bytes() == orig


@pytest.mark.parametrize("name", REAL_FILES)
def test_roundtrip_real_files_byte_identical(name):
    path = REAL_BIKE_DIR / name
    if not path.exists():
        pytest.skip(f"real bike file not present: {path}")
    orig = path.read_bytes()
    assert BikeDoc.from_bytes(orig).to_bytes() == orig


def test_roundtrip_is_stable_after_reparse(doc):
    """parse → serialize → parse → serialize is a fixed point."""
    once = doc.to_bytes()
    assert BikeDoc.from_bytes(once).to_bytes() == once


# ---------------------------------------------------------------------------
# parsing & the tree model
# ---------------------------------------------------------------------------


def test_root_structure(doc):
    assert doc.root_ul_id == "rootUL01"
    assert [r.id for r in doc.roots] == ["h1", "h9"]
    assert doc.row_count() == 22


def test_row_types_and_attrs(doc):
    h1 = doc.find_by_id("h1")
    assert h1.row_type == "heading"
    assert h1.created == "2024-01-01T00:00:00Z"
    assert h1.modified == "2024-01-02T00:00:00Z"

    t2 = doc.find_by_id("t2")
    assert t2.row_type == "task"
    assert t2.is_done
    assert t2.done == "2024-02-03T04:05:06Z"
    assert not doc.find_by_id("t1").is_done

    # default type is body; unknown attributes are preserved
    body2 = doc.find_by_id("body2")
    assert body2.row_type == "body"
    assert body2.attrs["data-indent"] == "2"


def test_nesting_and_navigation(doc):
    t2a = doc.find_by_id("t2a")
    assert t2a.parent.id == "t2"
    assert [a.id for a in t2a.ancestors()] == ["t2", "h1"]

    # walk depths
    depths = {row.id: depth for row, depth in doc.walk()}
    assert depths["h1"] == 0
    assert depths["t2a"] == 2
    assert depths["nesth"] == 3


def test_plain_text_and_rich_text(doc):
    b1 = doc.find_by_id("b1")
    assert b1.text == "Intro paragraph with bold and italic and inline_code."
    assert "<strong>bold</strong>" in b1.inner_xml

    # entity escaping is preserved verbatim on reserialization
    b2 = doc.find_by_id("b2")
    assert "Example & Co" in b2.text
    assert 'href="https://example.com/?a=1&amp;b=2"' in b2.inner_xml


def test_empty_rows(doc):
    assert doc.find_by_id("sp1").is_empty
    assert not doc.find_by_id("t1").is_empty
    # an hr row has an empty <p> but is typed, still "empty" text-wise
    assert doc.find_by_id("hr1").text == ""


def test_find_by_text(doc):
    hits = doc.find_by_text("quoted line")
    assert {r.id for r in hits} == {"q1", "q2"}
    assert doc.find_by_text("Open task", exact=True)[0].id == "t1"


def test_validate_fixture_is_valid(doc):
    assert doc.validate() == []


def test_validate_flags_duplicate_ids(doc):
    doc.find_by_id("t2a").attrs["id"] = "t1"  # collide
    problems = doc.validate()
    assert any("duplicate id" in p for p in problems)


def test_validate_flags_unknown_type(doc):
    doc.find_by_id("b1").attrs["data-type"] = "wibble"
    assert any("unknown data-type" in p for p in doc.validate())


def test_malformed_document_raises():
    bad = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<html xmlns="http://www.w3.org/1999/xhtml">\n'
        b"  <head>\n"
        b'    <meta charset="utf-8"/>\n'
        b"  </head>\n"
        b"  <body>\n"
        b"  </body>\n"
        b"</html>\n"
    )
    with pytest.raises(BikeFormatError):
        BikeDoc.from_bytes(bad)


# ---------------------------------------------------------------------------
# serialization details
# ---------------------------------------------------------------------------


def test_serialize_inline_escapes_like_bike(doc):
    z1 = doc.find_by_id("z1")
    inner = serialize_inline(z1.p)
    assert "3 &gt; 2 &lt; 5" in inner
    assert 'href="#line1&#10;line2"' in inner  # newline survives as entity


def test_empty_p_serializes_self_closed(doc):
    lines = doc.find_by_id("sp1").to_lines(0)
    assert lines[1].strip() == "<p/>"


def test_write_reads_back(tmp_path, doc):
    out = tmp_path / "copy.bike"
    doc.write(out)
    assert BikeDoc.from_path(out).to_bytes() == doc.to_bytes()
