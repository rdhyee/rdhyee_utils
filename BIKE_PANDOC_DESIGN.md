# Bike as a First-Class Pandoc Format — Design

**Date**: 2026-07-05 (overnight Fable session)
**Status**: reader MVP **built and tested**; writer direction **designed, not built**
**Companion code**: `rdhyee_utils/bike/model.py` (tree model), `rdhyee_utils/bike/lua/bike.lua` (pandoc reader), `rdhyee_utils/bike/bikeformat.py` (prior panflute work)

## 1. Where Raymond's earlier pandoc work got to (prior-art assessment)

The pandoc ↔ Bike ambition dates to **September–October 2023** and produced a
working *Python-mediated* pipeline, not a pandoc-native format:

| Piece | Location | State |
|---|---|---|
| `bike_etree_to_panflute()` | `rdhyee_utils/bike/bikeformat.py` | **Working**; Bike XML → panflute AST. Powers the daily Hammerspoon `overall.bike → overall.md` conversion via `bike.py pandoc`. Known warts: heading levels increment globally rather than per-branch (a heading's *sibling* after a deeper subtree can land at the wrong level), plain-paragraph rows are flattened (the "flat-export lossiness" that mis-sliced topics in the 2026-07-04 triage), row ids/timestamps are dropped. |
| `panflute_inline_to_bike_xml()`, `markdown_to_bike_p_element()` | same file | **Working** for inlines — the markdown→Bike *inline* direction is done. |
| `panflute_to_bike_etree()` | same file | **Skeleton only** — returns an empty Bike document; block-level markdown→Bike went unfinished (the gap is worked around in `bike_obsidian._panflute_blocks_to_bike_lis()`, which converts panflute blocks to `<li>` elements for insertion). |
| `bike.py pandoc` CLI | `python-learning/bike/bike.py` | **Working**; wraps the above through pypandoc for md/html/docx/pdf output. |
| `bike_to_pandoc_json.py` | `python-learning/bike/` | Working one-shot: Bike (via AppleScript) → pandoc JSON. |
| `change_marker.lua`, `remove_spans.lua` | `python-learning/bike/` | Tiny pandoc *filters* (AST tweaks), ~5 lines each. **No custom reader/writer was ever started in Lua** — these are the only Lua artifacts. |
| `convert_json.sh`, `custom-template.tex` | `python-learning/bike/` | Fan-out script: pandoc JSON → docx/odt/md/LaTeX. |

The definitive record of this design intent is Raymond's own journal,
`~/dev-journal/projects/rdhyee_utils-bike.md` (2025-11-21): read path marked
COMPLETE (`Bike.app → AppleScript → lxml → panflute → markdown`), write path
marked PARTIAL (`Markdown → panflute → Bike XML → ??? → Bike.app` — the
import step is the acknowledged gap). This document is consistent with that
assessment and builds on it.

**Bottom line**: Bike has been a *pre-processor feeding* pandoc (Python required,
AppleScript sometimes required), never a format pandoc itself understands.
"First-class citizen" means: `pandoc -f bike overall.bike -o out.docx` with no
Python in the loop.

## 2. The architecture decision: Lua custom reader, line-regular parsing

Three candidate routes were evaluated (empirically, pandoc 3.8):

1. **Reuse pandoc's HTML reader** (a .bike file *is* XHTML) — rejected.
   Tested: `<li id data-type class>` → the HTML reader synthesizes a `Div`
   keeping only the **id**; both `data-type` and even `class` are dropped on
   `li`. The row semantics (heading/task/code/quote) cannot survive this path
   without a lossy pre-rewrite of the XML.
2. **Python custom reader via `-f json`** (upgrade the panflute path) — viable
   but it's what already exists; keeps Python in the loop, so Bike never
   becomes pandoc-native. Kept as the AST-manipulation route (see §5).
3. **Lua custom reader with line-based structure parsing** — **chosen & built**.
   Bike.app's serialization is strictly line-regular (one `<li ...>` per line,
   one `<p>` per line, deterministic 2-space indentation). This isn't an
   assumption: `rdhyee_utils.bike.model` reproduces that serialization
   **byte-for-byte** on the real 7.2 MB `overall.bike` (verified in tests), so
   the line grammar is effectively a proven spec for Bike-written files.
   The reader parses outline *structure* itself and delegates only the
   rich-text `<p>` inline content to `pandoc.read(..., "html")` — using the
   HTML reader exactly where it is lossless (inlines) and never where it is
   lossy (structure).

## 3. What was built (MVP, tested)

`rdhyee_utils/bike/lua/bike.lua` — a pandoc **Reader**:

```bash
pandoc -f rdhyee_utils/bike/lua/bike.lua topic.bike -t gfm     # markdown
pandoc -f rdhyee_utils/bike/lua/bike.lua topic.bike -o out.docx # Word
```

Mapping (mirrors the `prose` style in `bike.mdrender`):

| Bike row type | pandoc AST |
|---|---|
| heading | `Header` (level = 1 + heading ancestors, cap 6) — **row id becomes the header identifier** (anchors survive) |
| body | `Para`; children → nested `BulletList` (lossiness fix, same rule as `mdrender`) |
| task | list item prefixed ☐/☒ (pandoc's markdown writers emit `- [ ]`/`- [x]` task-list syntax) |
| ordered / unordered | `OrderedList` / `BulletList` (consecutive siblings merge) |
| quote | `BlockQuote` (consecutive siblings merge) |
| code | `CodeBlock` (consecutive childless siblings merge; leading whitespace preserved via direct entity decoding, NOT the HTML reader) |
| hr | `HorizontalRule` |
| note | `Div` with class `note` |
| empty untyped rows | skipped (visual spacers) |

**Measured**: converts the full `overall.bike` (7.2 MB, 27,423 rows) → 60k-line
markdown in ~3.3 s. Smoke-tested via `tests/bike/test_lua_reader.py` (gfm
content checks, nesting preservation, header-id survival, docx generation);
tests skip when pandoc is absent.

## 4. Known limitations of the MVP (deliberate)

- **Line-regular input assumed.** Files written by Bike.app (or by
  `model.BikeDoc.write()`) parse perfectly; hand-mangled XML with several
  `<li>` on one line won't. Escape hatch: round-trip through
  `model.BikeDoc` first, which normalizes to Bike's own serialization.
- `data-created` / `data-modified` timestamps are not carried into the AST
  (pandoc has no natural per-block metadata slot; could go into Div attrs —
  see §5).
- Only headings keep their row ids in this MVP. Wrapping *every* row in an
  attributed `Div` would preserve all ids at the cost of much noisier AST and
  markdown output; wrong default, could be a reader option later.
- No `Reader options` (e.g. `--from bike.lua+ids`) implemented yet.

## 5. Designed but NOT built (the roadmap)

1. **Writer direction (`-t bike`)** — a custom Lua *writer* so pandoc can emit
   `.bike`: markdown → Bike for the "restructure in Bike" half of the
   [[Bike-Obsidian Triage Pipeline]] vision. Design: map Header→heading row,
   ordered/bullet lists→typed rows, CodeBlock→one code row per line,
   BlockQuote→quote rows, Para→body rows; generate ids with the documented
   `[A-Za-z0-9_-]` alphabet; serialize in Bike's byte-exact style (the grammar
   lives in `model.py::Row.to_lines` — port of ~40 lines to Lua).
   Until then the Python path (`bike_obsidian._panflute_blocks_to_bike_lis`)
   covers this direction.
2. **Style parity** — the Lua reader implements `prose` only. `outline` /
   `sections` equivalents could be reader extensions, but the cheaper path is:
   keep style choice in Python (`mdrender`), use the Lua reader when the
   *output* is non-markdown (docx/odt/pdf/html).
3. **Row-id preservation option** (`#ids`) for provenance-carrying pipelines.
4. **Packaging** — install the reader to `~/.local/share/pandoc/custom/` (or
   `--data-dir`) so `pandoc -f bike.lua` works from anywhere; add a
   `bike2docx` convenience wrapper in `bike_cli`.
5. **Retire the known-buggy `bikeformat.bike_etree_to_panflute` heading logic**
   in favor of a `model.py`-based AST builder if/when the Hammerspoon pipeline
   migrates; until then, don't touch the working daily pipeline.

## 6. Test & verification summary

```
tests/bike/test_model.py      — 20 tests (round-trip byte-compare incl. real files)
tests/bike/test_mdrender.py   — 18 tests (golden renders, style rules)
tests/bike/test_lua_reader.py —  4 tests (pandoc smoke: gfm, native, docx)
```

<!-- cc:2026.07.05 -->
