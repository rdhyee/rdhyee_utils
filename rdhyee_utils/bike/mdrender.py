"""
bike.mdrender — bike → markdown rendering with EXPLICIT, pluggable styles.

Every style is a small class whose mapping rules are stated in its docstring;
choosing how a Bike subtree should read in Obsidian is a *style decision*,
not something buried in conversion code.  Three built-in styles:

* ``outline``  — maximum structural fidelity: every row is a bullet, nesting
  is exactly the Bike tree.  Nothing is ever flattened (this is the style
  that can never reproduce the flat-export lossiness bug).
* ``sections`` — heading rows become ATX ``#`` headings; everything else
  stays an outline bullet, with indentation counted relative to the nearest
  heading.  Reads like a structured outline document.
* ``prose``    — row types drive markdown semantics: body rows become
  paragraphs, list-typed rows become real markdown lists, code runs become
  fenced blocks, quotes become blockquotes.  Reads like a written document.

Content is rendered **verbatim** — no smoothing, no rewriting.  All styles
skip Bike's empty spacer rows.

Known limitation: "verbatim" means the row's *text* is preserved unchanged,
not that the output is safe from markdown reinterpretation. Row text that
happens to look like markdown syntax (e.g. a body row whose text literally
starts with ``# `` or ``[ ] ``) will render as that syntax (a heading, a
task) rather than as escaped literal text — plain-text characters are not
escaped on the way out. This mirrors how the row's own ``data-type`` (not
its text) decides structure, so it's a pre-existing tradeoff, not something
introduced here; flagging it because a naive reading of "verbatim" could
suggest otherwise.

Shared inline mapping (all styles):

===========  =====================
Bike inline  markdown
===========  =====================
<strong>     ``**bold**``
<em>         ``*italic*``
<code>       `` `code` ``
<a href>     ``[text](href)``
<mark>       ``==highlight==``
<s>          ``~~strikethrough~~``
<span>       (unwrapped, text kept)
===========  =====================
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

import lxml.etree as ET

from .model import Row, _localname

# ---------------------------------------------------------------------------
# shared inline rendering
# ---------------------------------------------------------------------------

_INLINE_WRAPPERS = {
    "strong": ("**", "**"),
    "em": ("*", "*"),
    "mark": ("==", "=="),
    "s": ("~~", "~~"),
}


def inline_markdown(elem: ET._Element) -> str:
    """Render the inline content of a <p> (or nested inline element)."""
    parts: List[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(_render_inline_element(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _render_inline_element(elem: ET._Element) -> str:
    name = _localname(elem.tag)
    inner = inline_markdown(elem)
    if name in _INLINE_WRAPPERS:
        pre, post = _INLINE_WRAPPERS[name]
        return f"{pre}{inner}{post}" if inner else ""
    if name == "code":
        return f"`{inner}`" if inner else ""
    if name == "a":
        # newlines inside an href would break the markdown link syntax;
        # percent-encode them (content preserved, link stays intact)
        href = elem.get("href", "").replace("\n", "%0A").replace(" ", "%20")
        return f"[{inner}]({href})" if inner else href
    # span and anything unknown: keep the text, drop the wrapper
    return inner


def row_markdown(row: Row) -> str:
    """
    A row's rich text as a single line of markdown (verbatim content).
    Literal newlines inside a row (rare) are collapsed to spaces so that
    line-oriented contexts (bullets, headings) can't be broken.
    """
    return " ".join(inline_markdown(row.p).split("\n")).strip()


# ---------------------------------------------------------------------------
# style machinery
# ---------------------------------------------------------------------------


class Style:
    """Base class for render styles.  Subclasses set name/description."""

    name: str = ""
    description: str = ""

    def render(self, rows: Sequence[Row], title: Optional[str] = None) -> str:
        """
        Render a sequence of sibling rows (a subtree's children, or the row
        itself) to markdown.  ``title`` renders as an H1 above the body; in
        that case heading rows in the body start at ``##`` so they can't
        collide with the document title.
        """
        if title:
            body = self.render_rows(rows, start_level=2)
            return f"# {title}\n\n{body}".rstrip() + "\n"
        return self.render_rows(rows).rstrip() + "\n"

    def render_rows(self, rows: Sequence[Row], start_level: int = 1) -> str:  # pragma: no cover
        raise NotImplementedError


def _runs(rows: Iterable[Row], key) -> List[List[Row]]:
    """Group consecutive rows by key(row)."""
    groups: List[List[Row]] = []
    for row in rows:
        if groups and key(groups[-1][0]) == key(row):
            groups[-1].append(row)
        else:
            groups.append([row])
    return groups


class OutlineStyle(Style):
    """
    ``outline`` — every row is a bullet; nesting mirrors the Bike tree 1:1.

    Mapping rules:
      heading   → ``- **text**``
      task      → ``- [ ] text`` / ``- [x] text`` (done)
      code      → ``- `text` ``
      quote     → ``- > text``
      note      → ``- *text*``
      ordered   → numbered ``1.`` items (numbered within each sibling run)
      hr        → ``- ―――``
      body/unordered → ``- text``
      empty spacer rows are skipped
    """

    name = "outline"
    description = "list-preserving: every row a bullet, exact Bike nesting"

    def render_rows(self, rows: Sequence[Row], start_level: int = 1) -> str:
        # outline style has no heading levels; start_level is irrelevant
        lines: List[str] = []
        self._emit(rows, "", lines)
        return "\n".join(lines) + ("\n" if lines else "")

    def _emit(self, rows: Sequence[Row], pad: str, lines: List[str]) -> None:
        ordered_n = 0
        for row in rows:
            if row.is_empty:
                ordered_n = 0
                continue
            text = row_markdown(row)
            rtype = row.row_type
            if rtype == "ordered":
                ordered_n += 1
            else:
                ordered_n = 0
            marker_width = 2  # "- "
            if rtype == "heading":
                lines.append(f"{pad}- **{text}**")
            elif rtype == "task":
                mark = "x" if row.is_done else " "
                lines.append(f"{pad}- [{mark}] {text}")
            elif rtype == "code":
                plain = row.text.strip()
                lines.append(f"{pad}- `{plain}`" if plain else f"{pad}-")
            elif rtype == "quote":
                lines.append(f"{pad}- > {text}")
            elif rtype == "note":
                lines.append(f"{pad}- *{text}*")
            elif rtype == "ordered":
                marker = f"{ordered_n}. "
                marker_width = len(marker)
                lines.append(f"{pad}{marker}{text}")
            elif rtype == "hr":
                lines.append(f"{pad}- ―――")
            else:  # body, unordered, anything unknown
                lines.append(f"{pad}- {text}")
            if row.children:
                # children indent by the parent's marker width so nested
                # lists stay valid under ordered items too (CommonMark)
                self._emit(row.children, pad + " " * marker_width, lines)


class SectionsStyle(Style):
    """
    ``sections`` — headings become document structure, content stays outline.

    Mapping rules:
      heading   → ATX heading when reached through an unbroken chain of
                  heading rows from the subtree root ("heading spine");
                  level = 1 + number of heading ancestors, capped at
                  ``######`` (deeper spine headings render bold).
                  A heading nested under a NON-heading row is content, not
                  structure: it renders as a bold bullet, keeping its place
                  in the outline (no false promotion).
      code      → runs of childless sibling code rows directly under a
                  heading merge into a fenced block; code rows inside a
                  bullet subtree render as `` `code` `` bullets
      quote     → ``> text`` blockquote lines (consecutive siblings merge);
                  their children render as bullets inside the blockquote
      hr        → ``---`` (directly under a heading)
      everything else → outline bullets exactly as in the ``outline`` style,
                  with indentation counted relative to the nearest heading
      empty spacer rows are skipped
    """

    name = "sections"
    description = "headings-forward: # headings for heading rows, bullets beneath"

    max_heading_level = 6

    def render_rows(self, rows: Sequence[Row], start_level: int = 1) -> str:
        blocks: List[str] = []
        self._emit_sections(rows, level=start_level, blocks=blocks)
        return "\n\n".join(b for b in blocks if b) + ("\n" if blocks else "")

    def _emit_sections(self, rows: Sequence[Row], level: int, blocks: List[str]) -> None:
        content: List[Row] = []

        def flush_content():
            if content:
                blocks.extend(self._content_blocks(content))
                content.clear()

        for row in rows:
            if row.is_empty:
                continue
            if row.row_type == "heading":
                flush_content()
                text = row_markdown(row)
                if level <= self.max_heading_level:
                    blocks.append(f"{'#' * level} {text}")
                else:
                    blocks.append(f"**{text}**")
                self._emit_sections(row.children, level + 1, blocks)
            else:
                content.append(row)
        flush_content()

    def _content_blocks(self, rows: Sequence[Row]) -> List[str]:
        """Render non-heading sibling rows under a heading."""
        blocks: List[str] = []
        outline = OutlineStyle()

        def kind(r: Row) -> str:
            t = r.row_type
            if t == "code" and not r.children:
                return "code"
            if t == "quote":
                return "quote"
            if t == "hr":
                return "hr"
            return "bullets"

        for run in _runs(rows, key=kind):
            k = kind(run[0])
            if k == "code":
                code = "\n".join(r.text for r in run)
                blocks.append(f"```\n{code}\n```")
            elif k == "quote":
                quote_lines: List[str] = []
                for r in run:
                    quote_lines.append(f"> {row_markdown(r)}")
                    child_lines: List[str] = []
                    outline._emit(r.children, "", child_lines)
                    quote_lines.extend(f"> {line}" for line in child_lines)
                blocks.append("\n".join(quote_lines))
            elif k == "hr":
                blocks.append("---")
            else:
                lines: List[str] = []
                outline._emit(run, "", lines)
                blocks.append("\n".join(lines))
        return blocks


class ProseStyle(Style):
    """
    ``prose`` — row types drive markdown semantics; reads like a document.

    Mapping rules:
      heading   → ATX heading, level = 1 + number of heading ancestors
      body      → paragraph; a body row WITH children renders its subtree
                  as an indented bullet list after the paragraph (this is
                  the explicit fix for the flat-export lossiness bug)
      unordered/ordered/task → real markdown lists (nested via children)
      code      → runs of childless code rows merge into a fenced block
      quote     → blockquote paragraphs (consecutive rows merge)
      note      → Obsidian callout ``> [!note] text``
      hr        → ``---``
      empty spacer rows are skipped
    """

    name = "prose"
    description = "row-type-mapped: paragraphs, real lists, fenced code, blockquotes"

    max_heading_level = 6

    def render_rows(self, rows: Sequence[Row], start_level: int = 1) -> str:
        blocks: List[str] = []
        self._emit_blocks(rows, heading_level=start_level, blocks=blocks)
        return "\n\n".join(b for b in blocks if b) + ("\n" if blocks else "")

    # ---- block context ----------------------------------------------------

    def _emit_blocks(self, rows: Sequence[Row], heading_level: int, blocks: List[str]) -> None:
        rows = [r for r in rows if not r.is_empty]

        def type_key(r: Row) -> str:
            t = r.row_type
            if t in ("unordered", "ordered", "task"):
                return "list"
            if t in ("code", "quote"):
                return t
            return "one"

        for run in _runs(rows, key=type_key):
            kind = type_key(run[0])
            if kind == "list":
                lines: List[str] = []
                self._emit_list(run, 0, lines)
                blocks.append("\n".join(lines))
            elif kind == "code" and not any(r.children for r in run):
                code = "\n".join(r.text for r in run)
                blocks.append(f"```\n{code}\n```")
            elif kind == "quote":
                # children stay INSIDE the blockquote (each line "> "-prefixed),
                # same rule as SectionsStyle._content_blocks
                quote_lines: List[str] = []
                for r in run:
                    quote_lines.append(f"> {row_markdown(r)}")
                    if r.children:
                        child_lines: List[str] = []
                        self._emit_list(r.children, 0, child_lines)
                        quote_lines.extend(f"> {line}" for line in child_lines)
                blocks.append("\n".join(quote_lines))
            else:
                for row in run:
                    self._emit_block_row(row, heading_level, blocks)

    def _emit_block_row(self, row: Row, heading_level: int, blocks: List[str]) -> None:
        text = row_markdown(row)
        rtype = row.row_type
        if rtype == "heading":
            if heading_level <= self.max_heading_level:
                blocks.append(f"{'#' * heading_level} {text}")
            else:
                blocks.append(f"**{text}**")
            if row.children:
                self._emit_blocks(row.children, heading_level + 1, blocks)
        elif rtype == "hr":
            blocks.append("---")
        elif rtype == "note":
            # children stay INSIDE the callout (every line "> "-prefixed) —
            # same rule as the quote case above
            note_lines = [f"> [!note] {text}"]
            if row.children:
                child_lines: List[str] = []
                self._emit_list(row.children, 0, child_lines)
                note_lines.extend(f"> {line}" for line in child_lines)
            blocks.append("\n".join(note_lines))
        elif rtype == "code":
            # childless code runs are handled in _emit_blocks; a code row
            # with children degrades to paragraph-with-sublist
            blocks.append(f"`{row.text}`")
            if row.children:
                lines = []
                self._emit_list(row.children, 0, lines)
                blocks.append("\n".join(lines))
        else:  # body
            if text:
                blocks.append(text)
            if row.children:
                lines = []
                self._emit_list(row.children, 0, lines)
                blocks.append("\n".join(lines))

    # ---- list context ------------------------------------------------------

    def _emit_list(self, rows: Sequence[Row], depth: int, lines: List[str]) -> None:
        # identical list semantics to OutlineStyle (single source of truth)
        pad = "  " * depth
        OutlineStyle()._emit(rows, pad, lines)


STYLES = {
    style.name: style
    for style in (OutlineStyle(), SectionsStyle(), ProseStyle())
}


def get_style(name: str) -> Style:
    try:
        return STYLES[name]
    except KeyError:
        raise KeyError(
            f"unknown style {name!r}; available: {', '.join(sorted(STYLES))}"
        )


def render_row(row: Row, style: str = "sections", title_from_row: bool = True) -> str:
    """
    Convenience: render one row's subtree.  When ``title_from_row`` is true,
    the row's own PLAIN text becomes the document H1 (inline markup would
    look wrong in a title) and its children the body, with body headings
    starting at ``##``.
    """
    s = get_style(style)
    if title_from_row:
        title = " ".join(row.text.split()) or "(untitled)"
        return s.render(row.children, title=title)
    return s.render([row])
