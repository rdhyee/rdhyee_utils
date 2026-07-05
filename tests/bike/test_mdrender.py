"""
Tests for rdhyee_utils.bike.mdrender — the pluggable bike→markdown styles.

Golden files live next to the fixtures:
    tests/bike/data/kitchen_sink.<style>.golden.md
Regenerate them (after an INTENTIONAL mapping change) with:
    python -m rdhyee_utils.bike.convert render tests/bike/data/kitchen_sink.bike \
        --style <style> -o tests/bike/data/kitchen_sink.<style>.golden.md
and eyeball the diff before committing.
"""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[2]))

from rdhyee_utils.bike.model import BikeDoc  # noqa: E402
from rdhyee_utils.bike.mdrender import (  # noqa: E402
    STYLES,
    get_style,
    render_row,
    row_markdown,
)

DATA = Path(__file__).parent / "data"
KITCHEN_SINK = DATA / "kitchen_sink.bike"


@pytest.fixture
def doc() -> BikeDoc:
    return BikeDoc.from_path(KITCHEN_SINK)


# ---------------------------------------------------------------------------
# golden renders
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("style", sorted(STYLES))
def test_golden_render(doc, style):
    golden = (DATA / f"kitchen_sink.{style}.golden.md").read_text(encoding="utf-8")
    assert get_style(style).render(doc.roots) == golden


# ---------------------------------------------------------------------------
# inline mapping
# ---------------------------------------------------------------------------


def test_inline_mapping(doc):
    b1 = doc.find_by_id("b1")
    assert row_markdown(b1) == (
        "Intro paragraph with **bold** and *italic* and `inline_code`."
    )
    b2 = doc.find_by_id("b2")
    md = row_markdown(b2)
    assert "[Example & Co](https://example.com/?a=1&b=2)" in md
    assert "==highlight==" in md
    assert "~~struck~~" in md
    assert "a span" in md and "<span>" not in md


def test_href_newline_is_percent_encoded(doc):
    z1 = doc.find_by_id("z1")
    assert "(#line1%0Aline2)" in row_markdown(z1)


# ---------------------------------------------------------------------------
# style-specific structure
# ---------------------------------------------------------------------------


def test_outline_preserves_nesting_of_body_rows(doc):
    """The flat-export lossiness bug can't happen: body-row children nest."""
    out = get_style("outline").render(doc.roots)
    assert "  - Body row with children (the lossiness case)" in out
    assert "    - nested plain child" in out
    assert "      - **Heading buried under body rows**" in out


def test_sections_heading_spine_and_buried_heading(doc):
    out = get_style("sections").render(doc.roots)
    assert "# Project Alpha" in out
    assert "## Details" in out
    # a heading buried under body rows must NOT be promoted to ATX
    assert "# Heading buried under body rows" not in out
    assert "- **Heading buried under body rows**" in out


def test_sections_code_run_merges_to_fence(doc):
    out = get_style("sections").render(doc.roots)
    assert '```\ndef hello():\n    return "world"\n```' in out


def test_sections_quote_run_merges(doc):
    out = get_style("sections").render(doc.roots)
    assert "> First quoted line\n> Second quoted line" in out


def test_prose_body_rows_are_paragraphs(doc):
    out = get_style("prose").render(doc.roots)
    assert "\nIntro paragraph with **bold** and *italic* and `inline_code`.\n" in out
    # tasks are real checkbox lists
    assert "- [ ] Open task" in out
    assert "- [x] Done task" in out
    assert "  - [ ] Nested subtask" in out


def test_prose_note_becomes_callout(doc):
    assert "> [!note] A note row" in get_style("prose").render(doc.roots)


def _one_row_doc(rtype: str, text: str, child_text: str) -> BikeDoc:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><meta charset="utf-8"/></head>
  <body>
    <ul id="root">
      <li id="p1" data-type="{rtype}"><p>{text}</p>
        <ul><li id="c1"><p>{child_text}</p></li></ul>
      </li>
    </ul>
  </body>
</html>
""".encode("utf-8")
    return BikeDoc.from_bytes(xml)


def test_prose_quote_children_stay_inside_blockquote():
    """A quote row's children must every line be "> "-prefixed so they stay
    part of the SAME blockquote, not become an unrelated top-level list."""
    doc = _one_row_doc("quote", "quote parent", "quoted child")
    out = get_style("prose").render(doc.roots)
    assert "> quote parent\n> - quoted child" in out


def test_prose_note_children_stay_inside_callout():
    """Same rule for Obsidian callouts: every continuation line needs '> '
    or Obsidian stops treating it as part of the callout."""
    doc = _one_row_doc("note", "note parent", "note child")
    out = get_style("prose").render(doc.roots)
    assert "> [!note] note parent\n> - note child" in out


def test_hr_row_renders(doc):
    assert "\n---\n" in get_style("prose").render(doc.roots)
    assert "\n---\n" in get_style("sections").render(doc.roots)


def test_ordered_numbering_and_indent(doc):
    out = get_style("prose").render(doc.roots)
    assert "1. step one\n2. step two\n   - sub bullet" in out


def test_empty_spacer_rows_skipped(doc):
    for style in STYLES:
        out = get_style(style).render(doc.roots)
        assert "sp1" not in out
        assert "\n- \n" not in out


# ---------------------------------------------------------------------------
# render_row convenience
# ---------------------------------------------------------------------------


def test_render_row_title_from_row(doc):
    h2 = doc.find_by_id("h2")
    md = render_row(h2, style="sections")
    assert md.startswith("# Details\n")
    # children got re-based: quotes render at top level under the H1
    assert "> First quoted line" in md


def test_render_row_title_rebases_child_headings(doc):
    """With a title H1, body headings start at ## (no level collision)."""
    h1 = doc.find_by_id("h1")
    md = render_row(h1, style="sections")
    assert md.startswith("# Project Alpha\n")
    assert "\n## Details\n" in md
    assert "\n# Details\n" not in md
    # prose style honors the same re-basing
    md_prose = render_row(h1, style="prose")
    assert "\n## Details\n" in md_prose


def test_render_row_without_title(doc):
    h2 = doc.find_by_id("h2")
    md = render_row(h2, style="outline", title_from_row=False)
    assert md.startswith("- **Details**")


def test_unknown_style_raises():
    with pytest.raises(KeyError):
        get_style("nope")
