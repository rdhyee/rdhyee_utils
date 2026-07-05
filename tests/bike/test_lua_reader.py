"""
Smoke tests for the custom pandoc Lua reader (rdhyee_utils/bike/lua/bike.lua).

These shell out to pandoc; they skip cleanly when pandoc isn't installed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parents[2]
READER = REPO / "rdhyee_utils" / "bike" / "lua" / "bike.lua"
KITCHEN_SINK = Path(__file__).parent / "data" / "kitchen_sink.bike"

pandoc = shutil.which("pandoc")
pytestmark = pytest.mark.skipif(pandoc is None, reason="pandoc not installed")


def run_pandoc(*args) -> str:
    result = subprocess.run(
        [pandoc, "-f", str(READER), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_bike_to_gfm():
    out = run_pandoc(str(KITCHEN_SINK), "-t", "gfm")
    assert "# Project Alpha" in out
    assert "## Details" in out  # heading nesting
    assert "**bold**" in out and "*italic*" in out and "`inline_code`" in out
    assert "[Example & Co](https://example.com/?a=1&b=2)" in out
    assert "- [ ] Open task" in out  # tasks become GFM task list items
    assert "- [x] Done task" in out
    assert "> First quoted line" in out
    assert 'def hello():\n        return "world"' in out  # code indent kept
    assert "1.  step one" in out or "1. step one" in out
    assert "Second Topic — unicode ✓ 中文" in out


def test_body_row_children_keep_nesting():
    """The flat-export lossiness bug must not reappear via pandoc."""
    out = run_pandoc(str(KITCHEN_SINK), "-t", "gfm")
    assert "Body row with children (the lossiness case)" in out
    assert "- nested plain child" in out
    # the heading buried under body rows is NOT promoted to ATX
    assert "# Heading buried under body rows" not in out


def test_heading_ids_survive_to_native():
    out = run_pandoc(str(KITCHEN_SINK), "-t", "native")
    assert '"h1"' in out  # Bike row id carried as the Header identifier
    assert '"h2"' in out


def test_bike_to_docx(tmp_path):
    out_file = tmp_path / "kitchen_sink.docx"
    subprocess.run(
        [pandoc, "-f", str(READER), str(KITCHEN_SINK), "-o", str(out_file)],
        check=True,
    )
    assert out_file.stat().st_size > 5000  # a real docx, not an empty shell
