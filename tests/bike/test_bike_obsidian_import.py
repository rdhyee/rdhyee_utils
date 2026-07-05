"""
Tests for BikeObsidianBridge.import_markdown_to_bike — the file-level
delegation to rdhyee_utils.bike.mdimport (see BIKE_PANDOC_DESIGN.md and the
docstring on the method itself for the full design rationale).

These must NEVER touch the live Bike.app: BikeObsidianBridge.__init__ only
resolves the AppleScript app lazily (safe), but ensure_overall_open() /
get_overall_document() would actually query (and potentially launch) the
real app. Every test here monkeypatches get_overall_document instead of
letting it run for real, and every test points bike_file at a tmp_path
copy — never at the user's real overall.bike.
"""

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).parents[2]))

from rdhyee_utils.bike.bike_obsidian import BikeObsidianBridge  # noqa: E402
from rdhyee_utils.bike.model import BikeDoc  # noqa: E402
from rdhyee_utils.bike import BikeRow  # noqa: E402

pandoc = shutil.which("pandoc")
pytestmark = pytest.mark.skipif(pandoc is None, reason="pandoc not installed")

KITCHEN_SINK = Path(__file__).parent / "data" / "kitchen_sink.bike"


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    """A BikeObsidianBridge pointed at a throwaway copy of kitchen_sink.bike,
    with get_overall_document() stubbed so no test ever talks to Bike.app.

    _bike_is_running() is also stubbed to False by default: real machines
    (including Raymond's, where Bike.app is routinely open) shouldn't make
    these tests' outcomes depend on whatever happens to be running when
    they execute. Tests that specifically exercise the open-document guard
    override it to True.
    """
    target = tmp_path / "target.bike"
    target.write_bytes(KITCHEN_SINK.read_bytes())
    b = BikeObsidianBridge(bike_file=target, obsidian_vault=tmp_path)
    monkeypatch.setattr(b, "get_overall_document", lambda: None)
    monkeypatch.setattr("rdhyee_utils.bike.bike_obsidian._bike_is_running", lambda: False)
    return b


def test_import_writes_in_place_by_default(bridge):
    before = BikeDoc.from_path(bridge.bike_file)
    new_ids = bridge.import_markdown_to_bike("## Imported\n\n- [ ] new task\n")

    assert new_ids
    after = BikeDoc.from_path(bridge.bike_file)
    assert after.row_count() > before.row_count()
    assert after.validate() == []
    imported = after.find_by_text("Imported", exact=True)[0]
    assert imported.row_type == "heading"
    assert imported.attrs["id"] == new_ids[0]


def test_import_under_parent_id_string(bridge):
    new_ids = bridge.import_markdown_to_bike(
        "grafted paragraph\n", parent_row="h2", position="prepend"
    )
    doc = BikeDoc.from_path(bridge.bike_file)
    h2 = doc.find_by_id("h2")
    assert h2.children[0].attrs["id"] == new_ids[0]
    assert h2.children[0].text == "grafted paragraph"


def test_import_accepts_bikerow_parent(bridge):
    """parent_row may be a live BikeRow (its .id is used), not just a str."""
    fake_row = BikeRow(bike=None, rawrow=SimpleNamespace(id=lambda: "h2"))
    new_ids = bridge.import_markdown_to_bike("x\n", parent_row=fake_row)
    doc = BikeDoc.from_path(bridge.bike_file)
    assert doc.find_by_id("h2").children[-1].attrs["id"] == new_ids[0]


def test_import_to_explicit_output_path_leaves_source_untouched(bridge, tmp_path):
    original_bytes = bridge.bike_file.read_bytes()
    out = tmp_path / "elsewhere.bike"

    new_ids = bridge.import_markdown_to_bike("## Elsewhere\n", output_path=out)

    assert new_ids
    assert bridge.bike_file.read_bytes() == original_bytes  # source untouched
    result = BikeDoc.from_path(out)
    assert result.find_by_text("Elsewhere", exact=True)
    assert result.validate() == []


def test_refuses_to_overwrite_open_unsaved_document(bridge, monkeypatch):
    """If Bike.app has the target open with unsaved edits, writing in place
    would risk losing them on the next GUI save — refuse instead."""
    original_bytes = bridge.bike_file.read_bytes()
    fake_open_doc = SimpleNamespace(modified=True)
    monkeypatch.setattr(bridge, "get_overall_document", lambda: fake_open_doc)
    monkeypatch.setattr("rdhyee_utils.bike.bike_obsidian._bike_is_running", lambda: True)

    with pytest.raises(RuntimeError, match="unsaved"):
        bridge.import_markdown_to_bike("## Should Not Land\n")

    assert bridge.bike_file.read_bytes() == original_bytes  # untouched


def test_open_but_unmodified_document_is_not_blocked(bridge, monkeypatch):
    """Open-with-no-unsaved-changes is safe to overwrite (Bike.app will just
    prompt to revert)."""
    fake_open_doc = SimpleNamespace(modified=False)
    monkeypatch.setattr(bridge, "get_overall_document", lambda: fake_open_doc)
    monkeypatch.setattr("rdhyee_utils.bike.bike_obsidian._bike_is_running", lambda: True)

    new_ids = bridge.import_markdown_to_bike("## Fine\n")
    assert new_ids


def test_explicit_output_path_bypasses_open_unsaved_guard(bridge, monkeypatch, tmp_path):
    """Writing to a genuinely different path is always safe, even if the
    canonical file is open with unsaved changes."""
    fake_open_doc = SimpleNamespace(modified=True)
    monkeypatch.setattr(bridge, "get_overall_document", lambda: fake_open_doc)
    monkeypatch.setattr("rdhyee_utils.bike.bike_obsidian._bike_is_running", lambda: True)
    out = tmp_path / "safe_elsewhere.bike"

    new_ids = bridge.import_markdown_to_bike("## Safe\n", output_path=out)
    assert new_ids
    assert BikeDoc.from_path(out).find_by_text("Safe", exact=True)


def test_guard_check_skipped_when_bike_not_running(bridge, monkeypatch):
    """The open/modified check must not even run get_overall_document() —
    which would send an AppleEvent and could auto-launch Bike.app — when
    Bike.app isn't already running."""
    monkeypatch.setattr("rdhyee_utils.bike.bike_obsidian._bike_is_running", lambda: False)

    def _boom():
        raise AssertionError("get_overall_document() must not be called")

    monkeypatch.setattr(bridge, "get_overall_document", _boom)
    new_ids = bridge.import_markdown_to_bike("## Fine\n")
    assert new_ids


def test_output_path_aliasing_bike_file_is_still_guarded(bridge, monkeypatch):
    """An output_path that resolves to the SAME file as bike_file (e.g. via
    a symlink) must still be treated as an in-place write, not waved
    through as 'elsewhere'."""
    alias = bridge.bike_file.parent / "alias.bike"
    alias.symlink_to(bridge.bike_file)
    fake_open_doc = SimpleNamespace(modified=True)
    monkeypatch.setattr(bridge, "get_overall_document", lambda: fake_open_doc)
    monkeypatch.setattr("rdhyee_utils.bike.bike_obsidian._bike_is_running", lambda: True)

    with pytest.raises(RuntimeError, match="unsaved"):
        bridge.import_markdown_to_bike("## Should Not Land\n", output_path=alias)
