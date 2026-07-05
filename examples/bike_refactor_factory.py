"""
bike_refactor_factory.py — the "Conversion Factory" for the overall.bike
Phase-2 refactor (2026-07-05 overnight run).

For every remaining non-daily topic in overall.bike (top-level topics plus
Archive sub-topics, MINUS the six Phase-1 orphans already staged and MINUS
the RY-gated Spiritual Autobiography subtree), render the subtree in each of
the pluggable markdown styles (outline / sections / prose) into the vault
staging folder:

    ~/obsidian/Main/Bike Refactor Staging/<Topic>/<Topic> — <style>.md

Rules honored:
  * bike/*.bike and bike/overall.md are READ-ONLY (we only ever read).
  * Vault writes go ONLY inside the staging folder (the index note is
    written separately, by hand).
  * Content is verbatim — no smoothing; frontmatter records provenance
    (bike-source-id, source file, render style).

If two styles produce identical bodies for a topic (e.g. no heading rows →
sections ≡ outline), the duplicate is skipped and noted, so each topic gets
2–3 genuinely different preview options.

The script prints a per-topic report (rows, words, options written, style
metrics) that feeds the Phase-2 Preview Index note.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from rdhyee_utils.bike.model import BikeDoc, Row  # noqa: E402
from rdhyee_utils.bike.mdrender import STYLES, get_style, row_markdown  # noqa: E402

OVERALL = Path.home() / "obsidian/Main/bike/overall.bike"
STAGING = Path.home() / "obsidian/Main/Bike Refactor Staging"
RUN_DATE = "2026-07-05"

# ---------------------------------------------------------------------------
# scope: what is and is not in this run
# ---------------------------------------------------------------------------

# Non-topic top-level rows.
SKIP_TOP_IDS = {
    "stud",  # INBOX (empty)
    "_em",  # Daily Notes (the live capture stream — Phase 4, not this run)
    "yrBIG7pS8lhPMNk94o7u-",  # blank spacer row
}

# RY-gated: Spiritual Autobiography (+ its Lindi content) — excluded per brief.
RY_GATED_IDS = {"NJuhu"}

# Phase-1 orphans already staged as vault notes on 2026-07-04.
PHASE1_ORPHAN_IDS = {
    "hM1Xp",  # Joy Shih AI talk
    "B4fl",  # Portable Dashboard Unit (2025.01)
    "z1Jk",  # A Still Small Voice Film
    "BZcR2",  # Paris/London 2024
    "fSQ",  # Linda Garvin
    "-NqR5",  # AI for Writers Workshop
}

ARCHIVE_ID = "KWvU"  # Archive is a container: its children are the topics


def safe_name(text: str, max_len: int = 60) -> str:
    """Row text → a filesystem/Obsidian-safe folder/file stem."""
    name = text.strip() or "(untitled)"
    name = re.sub(r'[/\\:*?"<>|#^\[\]]', "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .-")
    return name[:max_len].strip(" .-") or "(untitled)"


def topic_rows(doc: BikeDoc):
    """Yield (row, group) for every topic in scope; group is '' or 'Archive'."""
    for row in doc.roots:
        if row.id in SKIP_TOP_IDS or row.id in RY_GATED_IDS:
            continue
        if row.id == ARCHIVE_ID:
            for child in row.children:
                if child.id in PHASE1_ORPHAN_IDS or child.is_empty:
                    continue
                yield child, "Archive"
            continue
        if row.is_empty:
            continue
        yield row, ""


def metrics(row: Row) -> dict:
    rows = [r for r, _ in row.walk()][1:]  # exclude the topic row itself
    n = len(rows)
    words = sum(len(r.text.split()) for r in rows)
    type_counts: dict = {}
    for r in rows:
        type_counts[r.row_type] = type_counts.get(r.row_type, 0) + 1
    max_depth = max((d for _, d in row.walk()), default=0)
    n_links = sum(1 for r in rows if r.p.findall(".//{*}a") or r.p.findall(".//a"))
    return {
        "rows": n,
        "words": words,
        "types": type_counts,
        "max_depth": max_depth,
        "links": n_links,
    }


def frontmatter(row: Row, style_name: str, group: str) -> str:
    lines = [
        "---",
        "tags:",
        "  - bike-refactor-staging",
        f"created: {RUN_DATE}",
        "status: preview",
        f"render-style: {style_name}",
        f"bike-source-id: {row.id}",
        "bike-source-file: bike/overall.bike",
    ]
    if group:
        lines.append(f"bike-source-group: {group}")
    NULL_DATE = "0001-01-01T00:00:00Z"  # Bike's null sentinel — omit
    if row.created and row.created != NULL_DATE:
        lines.append(f"bike-created: {row.created}")
    if row.modified and row.modified != NULL_DATE:
        lines.append(f"bike-modified: {row.modified}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def main() -> int:
    doc = BikeDoc.from_path(OVERALL)
    STAGING.mkdir(exist_ok=True)
    report = []
    style_order = ["outline", "sections", "prose"]

    for row, group in topic_rows(doc):
        title = " ".join(row.text.split()) or "(untitled)"
        stem = safe_name(row.text)
        folder = STAGING / stem
        folder.mkdir(exist_ok=True)

        bodies = {}
        for sname in style_order:
            md = get_style(sname).render(row.children, title=title)
            bodies[sname] = md

        written, skipped = [], []
        seen = {}
        for sname in style_order:
            body = bodies[sname]
            if body in seen:
                skipped.append((sname, seen[body]))
                continue
            seen[body] = sname
            out = folder / f"{stem} — {sname}.md"
            out.write_text(frontmatter(row, sname, group) + body, encoding="utf-8")
            written.append(sname)

        m = metrics(row)
        report.append(
            {
                "id": row.id,
                "title": title,
                "stem": stem,
                "group": group,
                "written": written,
                "skipped": [f"{a} (≡ {b})" for a, b in skipped],
                **m,
            }
        )
        print(
            f"{row.id:8} {stem[:44]:44} rows={m['rows']:4} words={m['words']:6} "
            f"opts={len(written)} skipped={','.join(s for s, _ in skipped) or '-'}"
        )

    (STAGING / "_factory_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    n_files = sum(len(r["written"]) for r in report)
    print(f"\n{len(report)} topics, {n_files} preview files written under {STAGING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
