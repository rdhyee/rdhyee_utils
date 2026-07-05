"""
bike.convert — headless CLI for the rigorous .bike ↔ markdown machinery.

Reads .bike files directly (no AppleScript, no pandoc); rendering styles are
the explicit pluggable ones in ``bike.mdrender``.

Examples
--------
List the top-level topics of a document (id, type, descendant count, text)::

    python -m rdhyee_utils.bike.convert topics ~/obsidian/Main/bike/overall.bike

Verify a file round-trips byte-for-byte (parse → serialize → compare)::

    python -m rdhyee_utils.bike.convert roundtrip ~/obsidian/Main/bike/overall.bike

Validate against the .bike format rules::

    python -m rdhyee_utils.bike.convert validate somefile.bike

Render one row's subtree to markdown (row text becomes the H1)::

    python -m rdhyee_utils.bike.convert render overall.bike --row PDzgV \\
        --style prose -o Decluttering.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .model import BikeDoc
from .mdrender import STYLES, get_style, render_row


def cmd_topics(args) -> int:
    doc = BikeDoc.from_path(args.file)
    for row in doc.roots:
        text = row.text.strip() or "(empty)"
        print(f"{row.id:12} {row.row_type:9} rows={row.descendant_count():6}  {text[:70]}")
        if args.depth > 1:
            for child in row.children:
                ctext = child.text.strip() or "(empty)"
                print(
                    f"  {child.id:12} {child.row_type:9} rows={child.descendant_count():5}  {ctext[:66]}"
                )
    return 0


def cmd_roundtrip(args) -> int:
    path = Path(args.file)
    orig = path.read_bytes()
    out = BikeDoc.from_bytes(orig).to_bytes()
    if out == orig:
        print(f"PASS: {path} round-trips byte-for-byte ({len(orig):,} bytes)")
        return 0
    i = next(
        (i for i, (a, b) in enumerate(zip(orig, out)) if a != b),
        min(len(orig), len(out)),
    )
    print(f"FAIL: {path} diverges at byte {i}")
    print(f"  original:     ...{orig[max(0, i - 40):i + 40]!r}...")
    print(f"  reserialized: ...{out[max(0, i - 40):i + 40]!r}...")
    return 1


def cmd_validate(args) -> int:
    doc = BikeDoc.from_path(args.file)
    problems = doc.validate()
    if not problems:
        print(f"VALID: {args.file} ({doc.row_count():,} rows)")
        return 0
    print(f"INVALID: {args.file} — {len(problems)} problem(s)")
    for p in problems[: args.max_problems]:
        print(f"  - {p}")
    return 1


def cmd_render(args) -> int:
    doc = BikeDoc.from_path(args.file)
    if args.row:
        row = doc.find_by_id(args.row)
        if row is None:
            print(f"error: no row with id {args.row!r}", file=sys.stderr)
            return 1
        md = render_row(row, style=args.style, title_from_row=not args.no_title)
    else:
        md = get_style(args.style).render(doc.roots)
    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.write(md)
    return 0


def cmd_styles(args) -> int:
    for name, style in sorted(STYLES.items()):
        print(f"{name:10} {style.description}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rdhyee_utils.bike.convert",
        description="Headless .bike parsing, validation, and markdown rendering.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("topics", help="list top-level rows (the document's topics)")
    p.add_argument("file")
    p.add_argument("--depth", type=int, default=1, help="1 = top-level only, 2 = one level down")
    p.set_defaults(func=cmd_topics)

    p = sub.add_parser("roundtrip", help="verify parse→serialize is byte-identical")
    p.add_argument("file")
    p.set_defaults(func=cmd_roundtrip)

    p = sub.add_parser("validate", help="check .bike format rules")
    p.add_argument("file")
    p.add_argument("--max-problems", type=int, default=20)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("render", help="render document or row subtree to markdown")
    p.add_argument("file")
    p.add_argument("--row", help="row id; renders that row's subtree (row text becomes H1)")
    p.add_argument("--style", default="sections", choices=sorted(STYLES))
    p.add_argument("--no-title", action="store_true", help="don't emit the row text as H1")
    p.add_argument("-o", "--output", help="write to file instead of stdout")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("styles", help="list available render styles")
    p.set_defaults(func=cmd_styles)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
