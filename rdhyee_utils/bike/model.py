"""
bike.model — a rigorous, round-trip-safe tree model for .bike files.

Why this exists (2026-07-04)
----------------------------
The flat ``overall.md`` mirror of ``overall.bike`` loses outline nesting for
plain-paragraph rows (only headings and list rows get markdown structure).
That lossiness caused real triage mistakes: sibling topics were mis-sliced
because their boundary was invisible in the flat export.  This module makes
the *XML tree* the source of truth: parse it into an explicit row tree,
guarantee we can write it back byte-for-byte, and let renderers (see
``bike.mdrender``) map the tree to markdown with explicit, pluggable rules.

Design notes
------------
* ``BikeDoc.from_path(p).to_bytes()`` is **byte-identical** to the input for
  files written by Bike.app (verified in tests against real Bike-written
  files).  To survive head/prolog variations, everything up to and including
  the ``<body>`` line is preserved verbatim; the outline itself is
  re-serialized structurally in Bike's own style (2-space indent, attribute
  order as parsed, ``<p/>`` for empty paragraphs, ``&amp;/&lt;/&gt;``
  escaping).
* Rows keep **all** attributes in file order (including unknown ones such as
  ``data-indent``), so we never silently drop data we don't understand.
* The rich-text ``<p>`` element is kept as an lxml element; its inner XML is
  re-serialized verbatim.  Renderers get both the raw inline tree and a
  plain-text view.

Known scope limits of the round-trip guarantee: it is verified against real
Bike.app output specifically, which (so far, empirically) is always LF-only
with a bare ``<body>`` tag and a bare ``<ul id="...">`` root. The outline
body is always re-serialized with ``\n`` line endings, so a hand-edited or
hypothetical file using CRLF line endings *below* the ``<body>`` line, a
``<body>`` tag carrying attributes, or a root ``<ul>`` carrying attributes
beyond ``id`` would NOT round-trip byte-identically — only the head/prolog
up to and including ``<body>`` is preserved verbatim as raw bytes; everything
after that point is re-derived from the parsed model, not copied through.

This module depends only on lxml (no pandoc/panflute/AppleScript), so it can
be used headlessly and in tests.  The pandoc bridge lives in ``bikeformat``;
the AppleScript bridge lives in ``bike.__init__``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple, Union

import lxml.etree as ET

XHTML_NS = "http://www.w3.org/1999/xhtml"
NSMAP = {"ns": XHTML_NS}
_NS = f"{{{XHTML_NS}}}"

# Row data-types that Bike understands.  "body" is the implicit default when
# no data-type attribute is present.
KNOWN_ROW_TYPES = (
    "body",
    "heading",
    "task",
    "quote",
    "code",
    "ordered",
    "unordered",
    "hr",
    "note",
)

# Empirical rule from real Bike-written files: ids may start with digits or
# dashes (e.g. "8jI_", "-auI", "3W5G"), contrary to BIKE_FORMAT.md v1.0's
# stricter letter-first claim.
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class BikeFormatError(ValueError):
    """Raised when a document violates the .bike format rules."""


def _localname(tag) -> str:
    """'{ns}li' -> 'li'; handles non-namespaced tags too."""
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return str(tag)


def _escape_text(s: str) -> str:
    """Escape character data the way Bike.app does (&, <, >)."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(s: str) -> str:
    """
    Escape attribute values the way Bike.app does (&, <, >, ", and literal
    whitespace-control characters as numeric entities so they survive XML
    attribute-value normalization).
    """
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
        .replace("\t", "&#9;")
        .replace("\r", "&#13;")
    )


def serialize_inline(elem: ET._Element) -> str:
    """
    Serialize the inner content of an inline-bearing element (usually <p>)
    verbatim: text, child elements (tag names without namespace, attributes
    in parse order), and tails, with Bike-style escaping.
    """
    parts: List[str] = []
    if elem.text:
        parts.append(_escape_text(elem.text))
    for child in elem:
        parts.append(_serialize_inline_element(child))
        if child.tail:
            parts.append(_escape_text(child.tail))
    return "".join(parts)


def _serialize_inline_element(elem: ET._Element) -> str:
    name = _localname(elem.tag)
    attrs = "".join(f' {k}="{_escape_attr(v)}"' for k, v in elem.attrib.items())
    inner = serialize_inline(elem)
    if not inner and elem.text is None and len(elem) == 0:
        return f"<{name}{attrs}/>"
    return f"<{name}{attrs}>{inner}</{name}>"


@dataclass
class Row:
    """One outline row (an <li> in the .bike file)."""

    attrs: "dict[str, str]"  # all attributes in file order; includes "id"
    p: ET._Element  # the row's <p> element (may be empty)
    children: List["Row"] = field(default_factory=list)
    parent: Optional["Row"] = field(default=None, repr=False, compare=False)

    # -- identity / typed attribute views ---------------------------------

    @property
    def id(self) -> str:
        return self.attrs["id"]

    @property
    def row_type(self) -> str:
        """The row's data-type; 'body' when absent (Bike's default)."""
        return self.attrs.get("data-type", "body")

    @property
    def created(self) -> Optional[str]:
        return self.attrs.get("data-created")

    @property
    def modified(self) -> Optional[str]:
        return self.attrs.get("data-modified")

    @property
    def done(self) -> Optional[str]:
        """ISO timestamp when a task row was checked off; None otherwise."""
        return self.attrs.get("data-done")

    @property
    def is_done(self) -> bool:
        return "data-done" in self.attrs

    # -- content views -----------------------------------------------------

    @property
    def text(self) -> str:
        """Plain-text content of the row (rich formatting stripped)."""
        return "".join(self.p.itertext())

    @property
    def inner_xml(self) -> str:
        """The row's rich-text content as verbatim inline XML."""
        return serialize_inline(self.p)

    @property
    def is_empty(self) -> bool:
        """
        True for visual-spacer rows: an untyped (body) row with an empty
        <p> and no children.  Typed rows (e.g. ``hr``) are never spacers.
        """
        return (
            self.row_type == "body"
            and not self.text.strip()
            and not self.children
        )

    # -- tree navigation ----------------------------------------------------

    def walk(self, depth: int = 0) -> Iterator[Tuple["Row", int]]:
        """Yield (row, depth) for this row and all descendants, pre-order."""
        yield self, depth
        for child in self.children:
            yield from child.walk(depth + 1)

    def descendant_count(self) -> int:
        return sum(1 for _ in self.walk()) - 1

    def find_by_id(self, row_id: str) -> Optional["Row"]:
        for row, _ in self.walk():
            if row.id == row_id:
                return row
        return None

    def ancestors(self) -> Iterator["Row"]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    # -- serialization -------------------------------------------------------

    def to_lines(self, indent_level: int) -> List[str]:
        """Serialize this row (and children) as Bike-style XML lines."""
        pad = "  " * indent_level
        attrs = "".join(
            f' {k}="{_escape_attr(v)}"' for k, v in self.attrs.items()
        )
        lines = [f"{pad}<li{attrs}>"]
        inner = serialize_inline(self.p)
        if inner:
            lines.append(f"{pad}  <p>{inner}</p>")
        else:
            lines.append(f"{pad}  <p/>")
        if self.children:
            lines.append(f"{pad}  <ul>")
            for child in self.children:
                lines.extend(child.to_lines(indent_level + 2))
            lines.append(f"{pad}  </ul>")
        lines.append(f"{pad}</li>")
        return lines


_BODY_SPLIT_RE = re.compile(rb"^(.*?<body>\r?\n)", re.DOTALL)

_DEFAULT_PROLOG = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    f'<html xmlns="{XHTML_NS}">\n'
    "  <head>\n"
    '    <meta charset="utf-8"/>\n'
    "  </head>\n"
    "  <body>\n"
)


@dataclass
class BikeDoc:
    """
    A parsed .bike document: a root <ul> id plus a forest of Rows.

    ``prolog`` preserves the original bytes up to and including the
    ``<body>`` line so that ``to_bytes()`` round-trips exactly even if the
    head section varies between Bike versions.
    """

    root_ul_id: str
    roots: List[Row] = field(default_factory=list)
    prolog: str = _DEFAULT_PROLOG
    source_path: Optional[Path] = None

    # -- construction --------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes, source_path: Optional[Path] = None) -> "BikeDoc":
        m = _BODY_SPLIT_RE.match(data)
        prolog = m.group(1).decode("utf-8") if m else _DEFAULT_PROLOG

        tree = ET.fromstring(data)
        body = tree.find(f"{_NS}body")
        if body is None:
            body = tree.find("body")
        if body is None:
            raise BikeFormatError("no <body> element found")
        uls = [c for c in body if _localname(c.tag) == "ul"]
        if len(uls) != 1:
            raise BikeFormatError(
                f"expected exactly one root <ul> under <body>, found {len(uls)}"
            )
        root_ul = uls[0]
        root_ul_id = root_ul.get("id")
        if root_ul_id is None:
            raise BikeFormatError("root <ul> has no id attribute")

        doc = cls(root_ul_id=root_ul_id, prolog=prolog, source_path=source_path)
        doc.roots = [_parse_li(li, parent=None) for li in root_ul if _localname(li.tag) == "li"]
        return doc

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "BikeDoc":
        path = Path(path)
        return cls.from_bytes(path.read_bytes(), source_path=path)

    # -- serialization --------------------------------------------------------

    def to_string(self) -> str:
        lines = [f'    <ul id="{_escape_attr(self.root_ul_id)}">']
        for row in self.roots:
            lines.extend(row.to_lines(3))
        lines.append("    </ul>")
        lines.append("  </body>")
        lines.append("</html>")
        return self.prolog + "\n".join(lines) + "\n"

    def to_bytes(self) -> bytes:
        return self.to_string().encode("utf-8")

    def write(self, path: Union[str, Path]) -> None:
        """Write to an explicit path.  (Never writes anywhere implicitly.)"""
        Path(path).write_bytes(self.to_bytes())

    # -- navigation / queries ---------------------------------------------------

    def walk(self) -> Iterator[Tuple[Row, int]]:
        for row in self.roots:
            yield from row.walk(0)

    def find_by_id(self, row_id: str) -> Optional[Row]:
        for row, _ in self.walk():
            if row.id == row_id:
                return row
        return None

    def find(self, predicate: Callable[[Row], bool]) -> List[Row]:
        return [row for row, _ in self.walk() if predicate(row)]

    def find_by_text(self, needle: str, exact: bool = False) -> List[Row]:
        needle_lower = needle.lower()
        if exact:
            return self.find(lambda r: r.text.strip() == needle)
        return self.find(lambda r: needle_lower in r.text.lower())

    def row_count(self) -> int:
        return sum(1 for _ in self.walk())

    # -- validation ---------------------------------------------------------------

    def validate(self) -> List[str]:
        """
        Check .bike format rules (see BIKE_FORMAT.md).  Returns a list of
        problems; empty list means valid.
        """
        problems: List[str] = []
        seen_ids = set()
        if not ID_RE.match(self.root_ul_id or ""):
            problems.append(f"root ul id {self.root_ul_id!r} is not a valid id")
        elif self.root_ul_id is not None:
            # seed with the root id so a row can't silently reuse it
            seen_ids.add(self.root_ul_id)
        for row, _ in self.walk():
            rid = row.attrs.get("id")
            if rid is None:
                problems.append(f"row with text {row.text[:40]!r} has no id")
                continue
            if rid in seen_ids:
                problems.append(f"duplicate id {rid!r}")
            seen_ids.add(rid)
            if not ID_RE.match(rid):
                problems.append(f"id {rid!r} does not match {ID_RE.pattern}")
            rtype = row.row_type
            if rtype not in KNOWN_ROW_TYPES:
                problems.append(f"row {rid!r} has unknown data-type {rtype!r}")
        return problems


def _parse_li(li: ET._Element, parent: Optional[Row]) -> Row:
    attrs = dict(li.attrib)  # lxml preserves document order
    p_elem = None
    ul_elem = None
    for child in li:
        name = _localname(child.tag)
        if name == "p" and p_elem is None:
            p_elem = child
        elif name == "ul" and ul_elem is None:
            ul_elem = child
        else:
            raise BikeFormatError(
                f"row {attrs.get('id')!r}: unexpected/duplicate child <{name}>"
            )
    if p_elem is None:
        raise BikeFormatError(f"row {attrs.get('id')!r} has no <p> child")
    row = Row(attrs=attrs, p=p_elem, parent=parent)
    if ul_elem is not None:
        row.children = [
            _parse_li(c, parent=row) for c in ul_elem if _localname(c.tag) == "li"
        ]
    return row
