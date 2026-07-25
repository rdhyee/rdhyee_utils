"""
test_dia.py -- hermetic tests for the Dia bridge.

NO live Dia, no network, no YouTube, no screen focus stolen. Everything below
drives DiaTab through a fake AppleScript transport, so the suite runs in
milliseconds and is safe in CI.

WHAT THIS SUITE CAN AND CANNOT CATCH -- worth stating plainly, because the
gap bit us:

  CAN catch  -- timestamp parsing, reply decoding, the retry/raise contract,
                and every scrape-termination path. Nearly all of the defects
                found on 2026-07-24, including the ones a Codex review
                flagged, lived here.

  CANNOT catch -- anything that depends on a real browser rendering a real
                page. The two WORST bugs that day were exactly that: YouTube
                (a single-page app) left the previous video's transcript panel
                in the DOM, so a Short returned another video's transcript;
                and tab focus() silently did nothing unless Dia was frontmost.
                A green run here is not evidence that live scraping works.

The live counterpart is deliberately opt-in; see test_live_smoke at the end.
"""

import math
import sys
from pathlib import Path as P

sys.path.append(str(P(__file__).parents[2]))  # noqa: E402

import pytest  # noqa: E402

from rdhyee_utils.applescript_bridge.apps.dia import (  # noqa: E402
    Dia,
    DiaTab,
    DiaExecuteFailed,
    DiaJavaScriptDisabled,
    IncompleteTranscriptError,
    TranscriptUnavailable,
)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeRawTab:
    """Stands in for the appscript tab reference.

    `replies` is a list of raw strings for successive execute() calls, exactly
    as Dia would return them: JSON-encoded results, or '' for the throttled
    empty reply. A callable may be supplied instead to vary by script.
    """

    def __init__(self, replies=None, url="https://example.com", focused=True):
        self.replies = list(replies or [])
        self.scripts = []
        self._url = url
        self._focused = focused
        self.focus_calls = 0
        self.closed = False

    def execute(self, javascript=""):
        self.scripts.append(javascript)
        if not self.replies:
            raise AssertionError("FakeRawTab ran out of replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    # appscript-style property accessors
    def URL(self):
        return self._url

    def isFocused(self):
        return self._focused

    def loading(self):
        return False

    def focus(self):
        self.focus_calls += 1
        self._focused = True

    def close(self):
        self.closed = True

    def properties(self):
        return {}


def make_tab(replies=None, **kw):
    return DiaTab(FakeRawTab(replies, **kw), window=None, index=0)


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    """Drop the 1s inter-call floor so the suite is fast.

    The real value exists because Dia silently returns '' when called faster
    than ~1s; that behaviour is simulated with explicit '' replies instead.
    """
    monkeypatch.setattr(DiaTab, "MIN_EXECUTE_INTERVAL", 0.0)
    monkeypatch.setattr(DiaTab, "_last_execute_at", 0.0)
    monkeypatch.setattr("time.sleep", lambda *_: None)


# --------------------------------------------------------------------------
# Layer 1 -- pure functions
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ts,secs",
    [("0:00", 0), ("12:30", 750), ("51:32", 3092), ("1:02:03", 3723), ("0:07", 7)],
)
def test_ts_seconds_valid(ts, secs):
    assert DiaTab._ts_seconds(ts) == secs


@pytest.mark.parametrize("ts", ["1:x:03", "not-a-time", "1:99", "", "1:2:3:4", "12", None])
def test_ts_seconds_rejects_malformed(ts):
    """Malformed timestamps must RAISE, not yield a plausible number.

    Regression: an earlier version discarded non-numeric components, turning
    '1:x:03' into 63 and 'not-a-time' into 0 -- silently reordering rows.
    """
    with pytest.raises(ValueError):
        DiaTab._ts_seconds(ts)


def test_transcript_to_text_preserves_all_text():
    """`every` drops TIMESTAMPS only; no transcript text may be lost."""
    rows = [{"ts": f"0:{i:02d}", "text": f"word{i}"} for i in range(6)]
    out = DiaTab.transcript_to_text(rows, every=3)
    for i in range(6):
        assert f"word{i}" in out
    assert out.count("[") == 2  # timestamps at index 0 and 3 only


@pytest.mark.parametrize("bad", [0, -1, 1.5, "2", None])
def test_transcript_to_text_rejects_bad_every(bad):
    with pytest.raises(ValueError):
        DiaTab.transcript_to_text([{"ts": "0:00", "text": "a"}], every=bad)


def test_order_rows_sorts_by_time_and_keeps_malformed():
    """A single bad timestamp must not abort a long scrape -- but is kept."""
    seen = {("12:30", "b"): None, ("0:00", "a"): None, ("bogus", "c"): None}
    out = make_tab()._order_rows(seen)
    assert [r["text"] for r in out] == ["a", "b", "c"]  # malformed sorts last
    assert len(out) == 3  # and is NOT dropped


# --------------------------------------------------------------------------
# Layer 2 -- reply decoding and the error contract
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"a":1,"b":[1,2]}', {"a": 1, "b": [1, 2]}),
        ("[1,2,3]", [1, 2, 3]),
        ('"hi"', "hi"),
        ("42", 42),
        ("true", True),
        ("null", None),
        ('""', ""),  # a GENUINE empty string, distinct from '' below
    ],
)
def test_execute_decodes_once(raw, expected):
    """Dia JSON-encodes the result, so execute() decodes exactly once.

    Note '""' -> '': a real empty-string result is 2 chars on the wire and
    must NOT be mistaken for the throttled empty reply.
    """
    assert make_tab([raw]).execute("whatever") == expected


def test_execute_retries_then_succeeds():
    tab = make_tab(["", "", "7"])
    assert tab.execute("x") == 7


def test_execute_raises_rather_than_returning_none_when_throttled():
    """Exhausted retries must RAISE.

    Regression: returning None was indistinguishable from a genuine JS null,
    so a throttle failure silently became "the page said null" downstream.
    """
    tab = make_tab([""] * 4)
    with pytest.raises(DiaExecuteFailed):
        tab.execute("x", retries=3)


def test_execute_null_is_none_but_does_not_raise():
    """The other half of the same contract: real null is a VALUE, not an error."""
    assert make_tab(["null"]).execute("x") is None


def test_execute_maps_missing_launch_flag_to_typed_error():
    err = Exception("Dia got an error: JavaScript execution via AppleScript "
                    "requires the --enable-applescript-javascript launch flag. (-10006)")
    with pytest.raises(DiaJavaScriptDisabled) as ei:
        make_tab([err]).execute("x")
    assert "--enable-applescript-javascript" in str(ei.value)


def test_execute_propagates_unrelated_errors():
    with pytest.raises(RuntimeError, match="something else"):
        make_tab([RuntimeError("something else")]).execute("x")


def test_javascript_enabled_checks_the_value_not_just_absence_of_error():
    """Regression: a throttled reply used to report True."""
    assert make_tab(["1"]).javascript_enabled is True
    assert make_tab([""] * 4).javascript_enabled is False          # exhausted
    assert make_tab(["999"]).javascript_enabled is False           # wrong value
    err = Exception("requires the --enable-applescript-javascript launch flag (-10006)")
    assert make_tab([err]).javascript_enabled is False


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_seek_rejects_non_finite(bad):
    """nan/inf render as bare `nan`/`inf` -- undefined identifiers in JS."""
    with pytest.raises(ValueError):
        make_tab([]).seek(bad)


def test_seek_interpolates_a_safe_literal():
    tab = make_tab(["750.0"])
    assert tab.seek(750) == 750.0
    assert "v.currentTime = 750.0" in tab._raw.scripts[0]


def test_url_getter_is_uncached():
    """Regression: caching made the documented poll-until-changed loop hang."""
    tab = make_tab([], url="https://old.example")
    assert tab.url == "https://old.example"
    tab._raw._url = "https://new.example"
    assert tab.url == "https://new.example"  # would still be 'old' if cached


def test_wait_for_url_returns_false_on_timeout():
    tab = make_tab([], url="https://old.example")
    assert tab.wait_for_url("never-appears", timeout=0.01) is False


# --------------------------------------------------------------------------
# Layer 3 -- transcript scraping termination (Codex's regression list)
# --------------------------------------------------------------------------


def rows(*specs):
    return [{"ts": ts, "text": txt} for ts, txt in specs]


ALREADY_OPEN = '{"alreadyOpen":true}'
NO_BUTTON = '{"noButton":true}'
OPENED = '{"clicked":true}'


def scrape(renderer, row_list, at_end=True, scrollable=False):
    """Build a raw _YT_SCRAPE_JS reply."""
    import json

    return json.dumps(
        {"renderer": renderer, "rows": row_list, "atEnd": at_end, "scrollable": scrollable}
    )


def test_old_renderer_is_complete_after_one_read():
    """Regression: the whole transcript is already in the DOM, so scrolling
    adds nothing -- which must NOT be read as stalling. A complete
    498-segment scrape once raised 'incomplete' because of this.

    NOTE the fixture: scrollable=True, atEnd=False, and the SAME rows returned
    on every call. That is what the real page does -- the transcript panel is
    a scrollable container, so scrolling "works" while yielding nothing new.
    An earlier version of this test passed scrollable=False, which let the
    code succeed through an unrelated branch and made the test blind to the
    very regression it was named for (caught by mutation testing).
    """
    full = scrape("old", rows(("0:00", "a"), ("0:07", "b")), at_end=False, scrollable=True)
    tab = make_tab([ALREADY_OPEN] + [full] * 6)
    out = tab.youtube_transcript()
    assert [r["text"] for r in out] == ["a", "b"]


def test_old_renderer_without_scroll_container_also_completes():
    """The other old-renderer shape: nothing scrollable at all."""
    tab = make_tab([ALREADY_OPEN, scrape("old", rows(("0:00", "a")), at_end=True, scrollable=False)])
    assert len(tab.youtube_transcript()) == 1


def test_virtualised_renderer_accumulates_across_scrolls():
    tab = make_tab([
        ALREADY_OPEN,
        scrape("new", rows(("0:00", "a")), at_end=False, scrollable=True),
        scrape("new", rows(("0:07", "b")), at_end=False, scrollable=True),
        scrape("new", rows(("0:14", "c")), at_end=True, scrollable=True),
    ])
    out = tab.youtube_transcript()
    assert [r["text"] for r in out] == ["a", "b", "c"]


def test_max_scrolls_exhaustion_raises_with_partial_rows():
    """Hitting the cap is incompleteness -- it must not look like success."""
    replies = [ALREADY_OPEN] + [
        scrape("new", rows((f"0:{i:02d}", f"t{i}")), at_end=False, scrollable=True)
        for i in range(6)
    ]
    tab = make_tab(replies)
    with pytest.raises(IncompleteTranscriptError) as ei:
        tab.youtube_transcript(max_scrolls=5)
    assert "max_scrolls" in ei.value.reason
    assert len(ei.value.rows) == 5  # partial result still recoverable


def test_stagnation_before_end_raises():
    same = scrape("new", rows(("0:00", "a")), at_end=False, scrollable=True)
    tab = make_tab([ALREADY_OPEN, same, same, same, same])
    with pytest.raises(IncompleteTranscriptError) as ei:
        tab.youtube_transcript()
    assert "nothing new" in ei.value.reason
    assert len(ei.value.rows) == 1


def test_missing_button_raises_rather_than_returning_empty():
    """'no transcript' and 'page not ready' must be distinguishable."""
    with pytest.raises(TranscriptUnavailable):
        make_tab([NO_BUTTON]).youtube_transcript()


def test_unfocused_tab_raises():
    """YouTube renders no transcript UI in a background tab, so any result
    would be a false 'no transcript'."""
    tab = make_tab([], focused=False)
    tab._raw.focus = lambda: None  # focus() fails to take effect
    with pytest.raises(TranscriptUnavailable, match="not focused"):
        tab.youtube_transcript()


def test_panel_opened_but_nothing_rendered_raises():
    tab = make_tab([OPENED, scrape("none", [], at_end=True, scrollable=False)])
    with pytest.raises(TranscriptUnavailable):
        tab.youtube_transcript()


def test_duplicate_panels_are_deduped():
    """Opening the panel twice leaves two identical lists in the DOM; a naive
    count double-counts (996 nodes for a 498-segment video)."""
    dupes = rows(("0:00", "a"), ("0:07", "b")) * 2
    tab = make_tab([ALREADY_OPEN, scrape("old", dupes)])
    assert len(tab.youtube_transcript()) == 2


def test_same_timestamp_distinct_lines_are_both_kept():
    """Dedup is on (ts, text), not ts alone -- two lines can share a stamp."""
    tab = make_tab([ALREADY_OPEN, scrape("old", rows(("0:00", "first"), ("0:00", "second")))])
    out = tab.youtube_transcript()
    assert len(out) == 2
    assert {r["text"] for r in out} == {"first", "second"}


def test_open_panel_false_skips_the_open_step():
    tab = make_tab([scrape("old", rows(("0:00", "a")))], focused=True)
    assert len(tab.youtube_transcript(open_panel=False)) == 1


# --------------------------------------------------------------------------
# Layer 3 -- chat role inference (geometric, therefore fragile)
# --------------------------------------------------------------------------


def bubble(x, y, text):
    return {"x": x, "y": y, "text": text, "width": 0}


def test_conversation_roles_from_geometry():
    """Real coordinates observed 2026-07-24: Dia flush left at 3342,
    the user indented to ~3470."""
    turns = Dia._classify_turns([
        bubble(3481, -240, "I was thinking Gabon"),
        bubble(3342, -132, "Same, Gabon feels like the obvious guess"),
        bubble(3469, 550, "so what is the answer?"),
        bubble(3342, 612, "It's Kiribati."),
    ])
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
    assert turns[0]["text"].startswith("I was thinking")  # negative y sorts first


def test_conversation_is_ordered_by_y_not_discovery_order():
    turns = Dia._classify_turns([bubble(3342, 900, "last"), bubble(3342, 100, "first")])
    assert [t["text"] for t in turns] == ["first", "last"]


def test_single_message_is_ambiguous_and_reports_assistant():
    """Documented limitation: one bubble defines the left edge itself."""
    turns = Dia._classify_turns([bubble(3469, 0, "lonely user message")])
    assert turns[0]["role"] == "assistant"


def test_role_tolerance_absorbs_sub_pixel_drift():
    turns = Dia._classify_turns(
        [bubble(3342, 0, "dia"), bubble(3347, 1, "also dia"), bubble(3470, 2, "me")]
    )
    assert [t["role"] for t in turns] == ["assistant", "assistant", "user"]


def test_empty_conversation():
    assert Dia._classify_turns([]) == []
    assert Dia.conversation_to_markdown([]) == ""


def test_conversation_to_markdown_labels_both_roles():
    md = Dia.conversation_to_markdown(
        [{"role": "user", "text": "q", "x": 0, "y": 0},
         {"role": "assistant", "text": "a", "x": 0, "y": 1}],
        heading="Session",
    )
    assert "# Session" in md and "**Me**" in md and "**Dia**" in md


# --------------------------------------------------------------------------
# Live smoke test -- opt-in, needs a real Dia
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    "--run-live" not in sys.argv,
    reason="needs a running Dia launched with --enable-applescript-javascript; "
           "steals screen focus. Run: pytest tests/applescript_bridge -k live --run-live",
)
def test_live_smoke():
    """The class of failure the hermetic suite structurally cannot reach.

    Kept minimal on purpose: it only asserts that JS round-trips at all. The
    real live risks (stale SPA panels, focus not taking effect) need a
    specific page in a specific state and are exercised by hand.
    """
    tab = Dia().windows[0].tabs[0]
    assert tab.javascript_enabled is True
    assert tab.execute("1 + 1") == 2
    assert isinstance(tab.execute("({ok: true})"), dict)
