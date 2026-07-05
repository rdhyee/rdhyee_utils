"""
bike.mdimport — markdown → Bike, on the rigorous tree model.

This closes the loop named in the 2025-11-21 design journal
("Markdown → panflute → Bike XML → ??? → Bike.app").  The missing "???"
was the import step; here it is grafting at the model level:

    from rdhyee_utils.bike.mdimport import insert_markdown
    from rdhyee_utils.bike.model import BikeDoc

    doc = BikeDoc.from_path("some.bike")
    new_ids = insert_markdown(doc, "## Heading\\n\\n- [ ] a task\\n")
    doc.write("some.bike")   # explicit write; Bike.app offers "Revert to Saved"

Pipeline: markdown → pandoc (custom Lua writer ``bike_writer.lua``) →
``BikeDoc`` rows → graft with collision-free ids.  Because the Lua writer
emits Bike's exact serialization (byte-round-trip verified in tests), the
grafted document remains byte-round-trip clean and Bike.app-loadable.

Relationship to ``bike_obsidian.BikeObsidianBridge.import_markdown_to_bike``:
the committed version of that method raises NotImplementedError; a
file-write implementation exists in Raymond's (uncommitted, 2025-11)
working tree using the panflute path.  This module is the committed,
tested equivalent built on ``model.py``; the two can converge when that
work lands — the bridge method could delegate here.

Requires pandoc on PATH (same dependency as the Lua reader).
"""

from __future__ import annotations

import random
import shutil
import string
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from .model import BikeDoc, Row

LUA_DIR = Path(__file__).parent / "lua"
BIKE_WRITER = LUA_DIR / "bike_writer.lua"
BIKE_READER = LUA_DIR / "bike.lua"

#: pandoc input format used for markdown; mirrors the extensions Raymond
#: settled on in bike_obsidian.SOURCE_MARKDOWN_FORMAT where pandoc supports
#: them for reading.
DEFAULT_FROM_FORMAT = "markdown+lists_without_preceding_blankline+mark"

_ID_ALPHABET = string.ascii_letters + string.digits + "-_"


class PandocMissingError(RuntimeError):
    """Raised when pandoc is not installed / not on PATH."""


def _require_pandoc() -> str:
    exe = shutil.which("pandoc")
    if exe is None:
        raise PandocMissingError(
            "pandoc is required for markdown→bike conversion "
            "(brew install pandoc)"
        )
    return exe


def markdown_to_bike_bytes(
    markdown: str, from_format: str = DEFAULT_FROM_FORMAT
) -> bytes:
    """Convert markdown to a complete, standalone .bike document (bytes)."""
    exe = _require_pandoc()
    result = subprocess.run(
        [exe, "-f", from_format, "-t", str(BIKE_WRITER)],
        input=markdown.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return result.stdout


def markdown_to_rows(
    markdown: str, from_format: str = DEFAULT_FROM_FORMAT
) -> List[Row]:
    """Convert markdown to a list of top-level Rows (a row forest)."""
    doc = BikeDoc.from_bytes(markdown_to_bike_bytes(markdown, from_format))
    return doc.roots


def generate_id(existing: set, length: int = 5) -> str:
    """A fresh row id not present in ``existing`` (empirical Bike alphabet)."""
    while True:
        rid = "".join(random.choice(_ID_ALPHABET) for _ in range(length))
        if rid not in existing:
            return rid


def _rekey_collisions(rows: List[Row], existing: set) -> None:
    """Re-generate any row ids that collide with ``existing`` (in place)."""
    for root in rows:
        for row, _ in root.walk():
            rid = row.attrs.get("id")
            if rid is None or rid in existing:
                new_id = generate_id(existing)
                row.attrs["id"] = new_id
                # keep id first, as Bike serializes it
                row.attrs = {"id": new_id, **{
                    k: v for k, v in row.attrs.items() if k != "id"
                }}
            existing.add(row.attrs["id"])


def insert_rows(
    doc: BikeDoc,
    rows: List[Row],
    parent_id: Optional[str] = None,
    position: str = "append",
) -> List[str]:
    """
    Graft a row forest into ``doc`` with collision-free ids.

    Args:
        doc: target document (mutated in place; caller decides when/where
             to write — this function never touches the filesystem)
        rows: a FRESH forest not already attached to ``doc`` (or any other
             document) — e.g. from :func:`markdown_to_rows`. Reusing the
             same Row objects across more than one insert_rows() call
             corrupts the tree (the same object would land twice in a
             children list); this is checked and raises ValueError rather
             than silently corrupting. :func:`insert_markdown` always
             builds a fresh forest per call, so calling it repeatedly is
             safe — this caveat is only for direct insert_rows() callers.
        parent_id: id of the row to insert under; ``None`` = document root
        position: ``"append"`` (after existing children) or ``"prepend"``

    Returns:
        ids of the inserted top-level rows (post collision-rekeying)

    Raises:
        ValueError: if any row in ``rows`` (or its descendants) is already
            part of ``doc``'s tree
    """
    doc_rows = set()
    existing = set()
    for row, _ in doc.walk():
        doc_rows.add(id(row))
        if "id" in row.attrs:
            existing.add(row.attrs["id"])
    existing.add(doc.root_ul_id)

    for root in rows:
        for row, _ in root.walk():
            if id(row) in doc_rows:
                raise ValueError(
                    "insert_rows() was given a Row already present in the "
                    "target document; reusing the same Row objects across "
                    "multiple insert_rows() calls corrupts the tree. Build "
                    "a fresh forest per call (e.g. via markdown_to_rows())."
                )

    _rekey_collisions(rows, existing)

    if parent_id is None:
        target_list = doc.roots
        parent = None
    else:
        parent = doc.find_by_id(parent_id)
        if parent is None:
            raise KeyError(f"no row with id {parent_id!r} in document")
        target_list = parent.children

    for row in rows:
        row.parent = parent

    if position == "prepend":
        target_list[0:0] = rows
    elif position == "append":
        target_list.extend(rows)
    else:
        raise ValueError(f"position must be 'append' or 'prepend', got {position!r}")

    return [row.attrs["id"] for row in rows]


def insert_markdown(
    doc: BikeDoc,
    markdown: str,
    parent_id: Optional[str] = None,
    position: str = "append",
    from_format: str = DEFAULT_FROM_FORMAT,
) -> List[str]:
    """markdown → rows → graft into ``doc``.  Returns new top-level row ids."""
    return insert_rows(
        doc, markdown_to_rows(markdown, from_format), parent_id, position
    )


def import_markdown_into_file(
    bike_path: Union[str, Path],
    markdown: str,
    output_path: Union[str, Path],
    parent_id: Optional[str] = None,
    position: str = "append",
) -> List[str]:
    """
    File-level convenience: read ``bike_path``, graft markdown, write to
    ``output_path``.  The output path is REQUIRED and explicit — in-place
    modification is a deliberate caller decision (pass the same path), and
    Bike.app will then prompt "Revert to Saved".
    """
    doc = BikeDoc.from_path(bike_path)
    new_ids = insert_markdown(doc, markdown, parent_id, position)
    doc.write(output_path)
    return new_ids
