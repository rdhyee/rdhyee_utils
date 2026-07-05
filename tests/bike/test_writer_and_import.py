"""
Tests for the writer direction:
  * bike_writer.lua — the custom pandoc WRITER (-t bike)
  * rdhyee_utils.bike.mdimport — markdown grafting on the tree model

These shell out to pandoc; they skip cleanly when pandoc isn't installed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[2]))

from rdhyee_utils.bike.model import BikeDoc  # noqa: E402
from rdhyee_utils.bike import mdimport  # noqa: E402

REPO = Path(__file__).parents[2]
WRITER = REPO / "rdhyee_utils" / "bike" / "lua" / "bike_writer.lua"
READER = REPO / "rdhyee_utils" / "bike" / "lua" / "bike.lua"
KITCHEN_SINK = Path(__file__).parent / "data" / "kitchen_sink.bike"

pandoc = shutil.which("pandoc")
pytestmark = pytest.mark.skipif(pandoc is None, reason="pandoc not installed")

SAMPLE_MD = """\
# Trip Planning

Intro with **bold**, *italic*, `code`, and a [link](https://example.com/?a=1&b=2).

## Tasks

- [ ] book flights
- [x] renew passport
- regular bullet
  - nested bullet

1. first step
2. second step

> A quoted line

```
def hello():
    return "world"
```

---

Final paragraph.
"""


def md_to_bike_bytes(md: str) -> bytes:
    result = subprocess.run(
        [pandoc, "-f", "gfm", "-t", str(WRITER)],
        input=md.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# the Lua writer
# ---------------------------------------------------------------------------


def test_writer_output_is_bike_conformant():
    """Writer output must byte-round-trip through BikeDoc and validate."""
    data = md_to_bike_bytes(SAMPLE_MD)
    doc = BikeDoc.from_bytes(data)
    assert doc.to_bytes() == data  # matches Bike.app serialization exactly
    assert doc.validate() == []


def test_writer_structure_and_types():
    doc = BikeDoc.from_bytes(md_to_bike_bytes(SAMPLE_MD))
    h1 = doc.roots[0]
    assert h1.row_type == "heading" and h1.text == "Trip Planning"

    intro = h1.children[0]
    assert intro.row_type == "body"
    assert "<strong>bold</strong>" in intro.inner_xml
    assert 'href="https://example.com/?a=1&amp;b=2"' in intro.inner_xml

    # H2 nests under H1 (outline-ization by level)
    h2 = h1.children[1]
    assert h2.row_type == "heading" and h2.text == "Tasks"

    todo = doc.find_by_text("book flights", exact=True)[0]
    assert todo.row_type == "task" and not todo.is_done
    done = doc.find_by_text("renew passport", exact=True)[0]
    assert done.row_type == "task" and done.is_done

    nested = doc.find_by_text("nested bullet", exact=True)[0]
    assert nested.parent.text == "regular bullet"
    assert nested.row_type == "unordered"

    assert doc.find_by_text("first step", exact=True)[0].row_type == "ordered"
    assert doc.find_by_text("A quoted line", exact=True)[0].row_type == "quote"

    code_rows = [r for r, _ in doc.walk() if r.row_type == "code"]
    assert [r.text for r in code_rows] == ["def hello():", '    return "world"']

    assert any(r.row_type == "hr" for r, _ in doc.walk())


def test_reader_writer_semantic_roundtrip():
    """kitchen_sink -f bike.lua -t bike_writer.lua keeps texts and key types."""
    result = subprocess.run(
        [pandoc, "-f", str(READER), str(KITCHEN_SINK), "-t", str(WRITER)],
        capture_output=True,
        check=True,
    )
    original = BikeDoc.from_path(KITCHEN_SINK)
    roundtripped = BikeDoc.from_bytes(result.stdout)

    assert roundtripped.to_bytes() == result.stdout  # still Bike-conformant
    assert roundtripped.validate() == []

    def texts(doc):
        return [
            r.text for r, _ in doc.walk()
            if r.text.strip() and r.row_type != "hr"
        ]

    # every substantive row's text survives, in order
    assert texts(roundtripped) == texts(original)

    # tasks keep their done/undone state
    assert roundtripped.find_by_text("Open task")[0].is_done is False
    assert roundtripped.find_by_text("Done task")[0].is_done is True

    # heading spine survives as headings
    for h in ("Project Alpha", "Details"):
        assert roundtripped.find_by_text(h, exact=True)[0].row_type == "heading"


# ---------------------------------------------------------------------------
# mdimport — grafting on the model
# ---------------------------------------------------------------------------


def test_insert_markdown_at_root():
    doc = BikeDoc.from_path(KITCHEN_SINK)
    before = doc.row_count()
    new_ids = mdimport.insert_markdown(doc, "## Imported\n\n- [ ] new task\n")
    assert new_ids  # top-level ids returned
    assert doc.row_count() > before
    assert doc.validate() == []
    imported = doc.find_by_text("Imported", exact=True)[0]
    assert imported.row_type == "heading"
    assert imported.attrs["id"] == new_ids[0]
    # serialization stays Bike-conformant after grafting
    assert BikeDoc.from_bytes(doc.to_bytes()).to_bytes() == doc.to_bytes()


def test_insert_markdown_under_parent_prepend():
    doc = BikeDoc.from_path(KITCHEN_SINK)
    new_ids = mdimport.insert_markdown(
        doc, "prepended paragraph\n", parent_id="h2", position="prepend"
    )
    h2 = doc.find_by_id("h2")
    assert h2.children[0].attrs["id"] == new_ids[0]
    assert h2.children[0].text == "prepended paragraph"
    assert h2.children[0].parent is h2
    assert doc.validate() == []


def test_insert_markdown_missing_parent_raises():
    doc = BikeDoc.from_path(KITCHEN_SINK)
    with pytest.raises(KeyError):
        mdimport.insert_markdown(doc, "x\n", parent_id="nope")


def test_double_import_rekeys_colliding_ids():
    """Two imports both start life with ids rb1, rb2… — must not collide."""
    doc = BikeDoc.from_path(KITCHEN_SINK)
    ids1 = mdimport.insert_markdown(doc, "first import\n")
    ids2 = mdimport.insert_markdown(doc, "second import\n")
    assert set(ids1).isdisjoint(ids2)
    assert doc.validate() == []  # validate() also checks global id uniqueness


def test_import_markdown_into_file(tmp_path):
    src = tmp_path / "target.bike"
    src.write_bytes(KITCHEN_SINK.read_bytes())
    out = tmp_path / "result.bike"

    new_ids = mdimport.import_markdown_into_file(
        src, "## From File\n\ncontent line\n", output_path=out
    )
    assert new_ids
    assert src.read_bytes() == KITCHEN_SINK.read_bytes()  # input untouched
    result = BikeDoc.from_path(out)
    assert result.find_by_text("From File", exact=True)
    assert result.validate() == []
    assert result.to_bytes() == out.read_bytes()
