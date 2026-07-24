"""
Dia - Python bindings for the Dia macOS browser.

Dia is a Chromium-based AI browser from The Browser Company (the makers of
Arc); the bundle is built on ArcCore.framework. It is NOT an OpenAI product
and it is NOT a native SwiftUI app -- both claims appeared in earlier versions
of this docstring and were wrong. This module provides Pythonic access to its
AppleScript dictionary plus GUI automation via macOS Accessibility APIs.

SDEF capabilities (verified against /Applications/Dia.app, 2026-07-24):
- Window management (list, close; minimized/visible/zoomed are settable)
- Tab management (list, focus, close)
- Tab properties: id, title, URL (read/write), loading, isPinned, isFocused
- `execute` -- run arbitrary JavaScript in a tab, returns the result as text

IMPORTANT -- the `execute` command is gated behind a launch flag. Without it
every call fails with:
    "JavaScript execution via AppleScript requires the
     --enable-applescript-javascript launch flag." (-10006)
Unlike Chrome/Comet (a View > Developer menu toggle), this cannot be enabled
from inside a running app. Dia must be relaunched:
    open -a Dia --args --enable-applescript-javascript

GUI Automation capabilities (via PyObjC Accessibility):
- Send messages to Dia's AI chat sidebar via ask_dia()
- Requires: Accessibility permissions granted to your terminal/IDE
- NOTE: the chat sidebar is NOT reachable via AppleScript. It is not exposed
  as a `tab`, so `execute` cannot reach it. Accessibility is the only route to
  the chat panel; AppleScript handles navigation. Verified 2026-07-24.

Example:
    >>> from rdhyee_utils.applescript_bridge import Dia
    >>> dia = Dia()
    >>> dia.name
    'Dia'
    >>> for window in dia.windows:
    ...     print(window.name)
    ...     for tab in window.tabs:
    ...         print(f"  - {tab.title}")

    # Send a message to Dia's AI assistant:
    >>> result = dia.ask_dia("What is the capital of France?")
    >>> print(result)
    {'success': True, 'message': "Sent: 'What is the capital of France?'"}
"""

from typing import List, Optional, Dict, Any
import json
import time


class DiaJavaScriptDisabled(RuntimeError):
    """Raised when Dia was launched without --enable-applescript-javascript.

    Dia gates its AppleScript `execute` command behind a launch flag. Unlike
    Chrome/Comet (a View > Developer menu toggle), this cannot be switched on
    from inside a running app -- Dia must be quit and relaunched:

        open -a Dia --args --enable-applescript-javascript

    The flag does NOT persist. A normal relaunch silently drops it, and every
    execute() call starts failing again with AppleScript error -10006.
    """

    RELAUNCH_CMD = "open -a Dia --args --enable-applescript-javascript"

    def __init__(self, original: Optional[Exception] = None):
        super().__init__(
            "Dia's JavaScript execution is disabled. Quit Dia and relaunch with:\n"
            f"    {self.RELAUNCH_CMD}\n"
            "(the flag does not survive a normal relaunch)"
        )
        self.original = original

try:
    from appscript import app as appscript_app

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False

# PyObjC Accessibility API for GUI automation
try:
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementCopyAttributeValue,
        AXUIElementSetAttributeValue,
        kAXErrorSuccess,
    )
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        kCGHIDEventTap,
    )
    import Cocoa

    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False


# --- Accessibility API Helpers ---


def _get_pid_for_app(app_name: str) -> Optional[int]:
    """Get the process ID for a running application by name."""
    if not HAS_PYOBJC:
        return None
    workspace = Cocoa.NSWorkspace.sharedWorkspace()
    apps = workspace.runningApplications()
    for app in apps:
        if app.localizedName() == app_name:
            return app.processIdentifier()
    return None


def _get_ax_attribute(element, attr_name):
    """Get an Accessibility attribute from an element."""
    err, value = AXUIElementCopyAttributeValue(element, attr_name, None)
    if err == kAXErrorSuccess:
        return value
    return None


def _find_element_by_identifier(element, target_id: str, depth: int = 0, max_depth: int = 20):
    """Recursively find an element by its AXIdentifier."""
    if depth > max_depth:
        return None
    identifier = _get_ax_attribute(element, "AXIdentifier") or ""
    if identifier == target_id:
        return element
    children = _get_ax_attribute(element, "AXChildren")
    if children:
        for child in children:
            result = _find_element_by_identifier(child, target_id, depth + 1, max_depth)
            if result:
                return result
    return None


def _is_dia_generating(window, depth: int = 0, max_depth: int = 20) -> bool:
    """Check if Dia is currently generating a response.

    Looks for the "Thinking…" indicator text that appears during generation.
    """
    if depth > max_depth:
        return False

    role = _get_ax_attribute(window, "AXRole")
    value = _get_ax_attribute(window, "AXValue") or ""

    # Check for "Thinking…" or "Thinking..." text
    if role == "AXStaticText" and "Thinking" in str(value):
        return True

    children = _get_ax_attribute(window, "AXChildren")
    if children:
        for child in children:
            if _is_dia_generating(child, depth + 1, max_depth):
                return True

    return False


def _activate_app(app_name: str) -> bool:
    """Bring an application to the foreground."""
    if not HAS_PYOBJC:
        return False
    workspace = Cocoa.NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.localizedName() == app_name:
            app.activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
            return True
    return False


def _press_return():
    """Simulate pressing the Return key."""
    # Return key is keycode 36
    event = CGEventCreateKeyboardEvent(None, 36, True)
    CGEventPost(kCGHIDEventTap, event)
    time.sleep(0.02)
    event = CGEventCreateKeyboardEvent(None, 36, False)
    CGEventPost(kCGHIDEventTap, event)


class DiaTab:
    """A tab in a Dia window.

    Properties:
        id: Unique tab identifier
        title: Tab title
        url: Tab URL
        is_pinned: Whether tab is pinned
        is_focused: Whether tab is currently focused
    """

    def __init__(self, raw_tab, window: "DiaWindow", index: int = 0):
        self._raw = raw_tab
        self._window = window
        self._index = index
        self._props = None

    def _get_props(self) -> dict:
        """Get tab properties (cached)."""
        if self._props is None:
            try:
                self._props = self._raw.properties()
            except Exception:
                self._props = {}
        return self._props

    @property
    def id(self) -> str:
        """Unique identifier of the tab."""
        from appscript import k
        return self._get_props().get(k.id, "")

    @property
    def title(self) -> str:
        """The title of the tab."""
        from appscript import k
        # Try both 'title' and 'pnam' (name)
        props = self._get_props()
        return props.get(k.title, props.get(k.name, ""))

    @property
    def url(self) -> str:
        """The URL of the tab."""
        from appscript import k
        return self._get_props().get(k.URL, "")

    @url.setter
    def url(self, value: str) -> None:
        """Navigate this tab. `URL` is read/write in Dia's dictionary.

        Navigation is asynchronous and Dia keeps reporting the OLD url for a
        moment afterwards, so an immediate read-back can look like the set
        failed when it did not. Poll (`while 'expected' not in tab.url`) or
        wait a beat before trusting the value.
        """
        self._raw.URL.set(value)
        self._props = None  # cached properties are now stale

    @property
    def loading(self) -> bool:
        """Whether the tab is currently loading."""
        from appscript import k
        # Not cached -- the whole point is that it changes.
        try:
            return bool(self._raw.loading())
        except Exception:
            return self._get_props().get(k.loading, False)

    @property
    def is_pinned(self) -> bool:
        """Whether the tab is pinned."""
        from appscript import k
        return self._get_props().get(k.isPinned, False)

    @property
    def is_focused(self) -> bool:
        """Whether the tab is currently focused."""
        from appscript import k
        return self._get_props().get(k.isFocused, False)

    def focus(self) -> None:
        """Focus on this tab, bringing its window forward if needed."""
        self._raw.focus()

    def close(self) -> None:
        """Close this tab."""
        self._raw.close()

    # ------------------------------------------------------------------
    # JavaScript execution (requires --enable-applescript-javascript)
    # ------------------------------------------------------------------

    def execute_raw(self, javascript: str) -> str:
        """Run JavaScript and return Dia's raw reply text, unparsed.

        Dia JSON-encodes whatever the JS evaluates to, so the reply for
        `document.title` is the 9 characters `"a title"` -- quotes included.
        You almost always want execute() instead, which decodes that.

        Rate-limited: see DiaTab.MIN_EXECUTE_INTERVAL.
        """
        self._throttle()
        try:
            return self._raw.execute(javascript=javascript)
        except Exception as e:
            if "enable-applescript-javascript" in str(e) or "-10006" in str(e):
                raise DiaJavaScriptDisabled(e) from e
            raise

    def execute(self, javascript: str, retries: int = 3) -> Any:
        """Run JavaScript in this tab and return the result as a Python value.

        Dia serialises the JS result as JSON before handing it back over
        AppleScript, so objects and arrays survive the trip intact and there
        is NO need to call JSON.stringify() yourself:

            >>> tab.execute("document.title")
            'Opus 5 is FINALLY here! (WOAH) - YouTube'
            >>> tab.execute("({a: 1, b: [1, 2]})")
            {'a': 1, 'b': [1, 2]}
            >>> tab.execute("1 + 1")
            2

        `undefined` comes back as None (Dia encodes it as JSON null).

        Requires the --enable-applescript-javascript launch flag; see
        DiaJavaScriptDisabled.
        """
        for attempt in range(retries + 1):
            raw = self.execute_raw(javascript)
            if raw:
                return json.loads(raw)
            # Empty reply == throttled (see MIN_EXECUTE_INTERVAL). A genuine
            # empty-string JS result would come back as '""', never ''. Back
            # off and retry rather than silently returning None.
            if attempt < retries:
                time.sleep(self.MIN_EXECUTE_INTERVAL * (attempt + 1))
        return None

    # Dia silently returns an empty reply if execute() is called too soon
    # after the previous one -- no error, no warning, just ''. Measured
    # 2026-07-24: <=0.6s apart fails, >=0.8s succeeds, and once it starts
    # failing it stays broken until a full ~1s gap. 1.0s is the safe floor.
    MIN_EXECUTE_INTERVAL = 1.0
    _last_execute_at = 0.0  # class-level: the limit is Dia's, not per-tab

    @classmethod
    def _throttle(cls) -> None:
        """Sleep as needed to keep calls MIN_EXECUTE_INTERVAL apart."""
        wait = cls.MIN_EXECUTE_INTERVAL - (time.time() - cls._last_execute_at)
        if wait > 0:
            time.sleep(wait)
        cls._last_execute_at = time.time()

    @property
    def javascript_enabled(self) -> bool:
        """Whether Dia will accept execute() calls (i.e. was the flag set?).

        Cheap probe -- useful for failing early with a clear message rather
        than deep inside a scraping routine.
        """
        try:
            self.execute("1")
            return True
        except DiaJavaScriptDisabled:
            return False

    # ------------------------------------------------------------------
    # YouTube helpers -- verified against youtube.com on 2026-07-24
    # ------------------------------------------------------------------

    # No JSON.stringify anywhere below -- Dia JSON-encodes the result for us.
    # Each execute() costs ~1s (see MIN_EXECUTE_INTERVAL), so these scripts are
    # written to do as much as possible per round-trip.

    # NaN is DROPPED by Dia's JSON encoder -- the key vanishes from the result
    # rather than arriving as null. video.duration is NaN until metadata loads,
    # so `num()` normalises it or youtube_state() comes back missing 'duration'
    # and callers KeyError. Same for currentTime on a fresh page.
    _YT_STATE_JS = """
    (() => {
      const v = document.querySelector('video');
      const num = x => (typeof x === 'number' && Number.isFinite(x)) ? x : null;
      return {
        title: document.title,
        url: location.href,
        hasVideo: !!v,
        currentTime:  v ? num(v.currentTime)  : null,
        duration:     v ? num(v.duration)     : null,
        paused:       v ? v.paused            : null,
        playbackRate: v ? num(v.playbackRate) : null
      };
    })()
    """

    # YouTube ships TWO transcript renderings and you will meet both:
    #   old: <ytd-transcript-segment-renderer>  -- whole transcript in the DOM
    #   new: <transcript-segment-view-model>    -- VIRTUALISED, ~98 nodes max,
    #                                              so a single read truncates
    # _read() below handles either; the virtualised one additionally needs the
    # panel scrolled to page the rest of the segments in.
    _YT_READ_FN = """
      const _read = () => {
        const olds = [...document.querySelectorAll('ytd-transcript-segment-renderer')];
        if (olds.length) return olds.map(s => ({
          ts:   (s.querySelector('.segment-timestamp')?.textContent || '').trim(),
          text: (s.querySelector('.segment-text')?.textContent || '').trim()
        })).filter(r => r.text);
        return [...document.querySelectorAll('transcript-segment-view-model')].map(s => ({
          ts:   (s.querySelector('.ytwTranscriptSegmentViewModelTimestamp')?.textContent || '').trim(),
          text: (s.querySelector('.ytAttributedStringHost')?.textContent || '').trim()
        })).filter(r => r.text);
      };
    """

    # Expand the description, then click a *visible* "Show transcript".
    # The button exists while the description is collapsed but is 0x0, and
    # clicking it then does nothing -- silently. That is the trap here.
    _YT_OPEN_JS = (
        """
    (() => {
      %s
      if (_read().length) return {alreadyOpen: true};
      const exp = document.querySelector('#expand');
      if (exp) exp.click();
      const vis = b => b.getBoundingClientRect().height > 0;
      const btn = [...document.querySelectorAll('button, tp-yt-paper-button, yt-button-shape button')]
        .filter(b => /transcript/i.test(b.getAttribute('aria-label') || '')
                  || /transcript/i.test(b.textContent || ''))
        .filter(b => !/close/i.test(b.getAttribute('aria-label') || ''))
        .sort((a, b) => (vis(b) ? 1 : 0) - (vis(a) ? 1 : 0))[0];
      if (!btn) return {noButton: true, expanded: !!exp};
      btn.click();
      return {clicked: true, wasVisible: vis(btn), expanded: !!exp};
    })()
    """
        % _YT_READ_FN
    )

    # Read the current window of segments, then scroll one page forward so the
    # next call sees fresh ones. Returns enough state for the caller to know
    # when it has reached the bottom.
    _YT_SCRAPE_JS = (
        """
    (() => {
      %s
      const rows = _read();
      let sc = null;
      const seg = document.querySelector('transcript-segment-view-model, ytd-transcript-segment-renderer');
      for (let e = seg; e; e = e.parentElement) {
        if (e.scrollHeight > e.clientHeight + 20) { sc = e; break; }
      }
      if (!sc) return {rows, atEnd: true, scrollable: false};
      const before = sc.scrollTop;
      sc.scrollTop = before + Math.max(sc.clientHeight * 0.8, 200);
      return {
        rows,
        scrollTop: before,
        scrollHeight: sc.scrollHeight,
        clientHeight: sc.clientHeight,
        atEnd: before + sc.clientHeight >= sc.scrollHeight - 5,
        scrollable: true
      };
    })()
    """
        % _YT_READ_FN
    )

    @staticmethod
    def _ts_seconds(ts: str) -> int:
        """'12:30' -> 750, '1:02:03' -> 3723. Used to order scraped segments."""
        parts = [int(p) for p in ts.split(":") if p.strip().isdigit()]
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        return secs

    def youtube_state(self) -> Dict[str, Any]:
        """Read the <video> element's state: currentTime, duration, paused, rate."""
        return self.execute(self._YT_STATE_JS)

    def seek(self, seconds: float) -> Optional[float]:
        """Jump the video to `seconds`. Returns the resulting currentTime.

        Works on any page with a <video> element, not just YouTube.
        """
        return self.execute(
            "(() => { const v = document.querySelector('video');"
            "  if (!v) return null;"
            f" v.currentTime = {float(seconds)};"
            "  return Number.isFinite(v.currentTime) ? v.currentTime : null; })()"
        )

    def youtube_transcript(
        self, open_panel: bool = True, max_scrolls: int = 40
    ) -> List[Dict[str, str]]:
        """Return the full video transcript as [{'ts': '12:30', 'text': ...}, ...].

        Handles both of YouTube's transcript renderings, including the newer
        virtualised one that keeps only ~98 segments in the DOM at a time --
        this scrolls the panel and accumulates until it reaches the bottom.

            >>> rows = tab.youtube_transcript()
            >>> len(rows)
            498
            >>> rows[0]
            {'ts': '0:00', 'text': "I know it's crazy, but there are people..."}

        Each round trip costs ~1s (see MIN_EXECUTE_INTERVAL), so a long video
        takes a few seconds. Returns [] if the video has no transcript, which
        is common -- check before assuming failure.

        IMPORTANT preconditions, both learned the hard way:
          * The tab must be FOCUSED. YouTube does not render the description
            or transcript controls in a background tab, so this silently
            returns [] on an unfocused tab even though the video is loaded.
            Call tab.focus() and give it a couple of seconds first.
          * Opening the panel more than once leaves MULTIPLE
            ytd-transcript-segment-list-renderer copies in the DOM, each with
            the full transcript. A naive count double-counts (996 nodes for a
            498-segment video). The (ts, text) dedup below absorbs that.

        This opens the transcript panel in the real browser and leaves it
        open -- a visible side effect, not a background read.
        """
        if open_panel:
            opened = self.execute(self._YT_OPEN_JS) or {}
            if opened.get("noButton"):
                return []

        # Dedup on (ts, text), NOT ts alone: duplicate panels produce identical
        # pairs and collapse correctly, while a genuine second line sharing a
        # timestamp is preserved rather than silently dropped.
        seen: Dict[tuple, None] = {}
        stagnant = 0
        for _ in range(max_scrolls):
            res = self.execute(self._YT_SCRAPE_JS) or {}
            rows = res.get("rows") or []
            before = len(seen)
            for r in rows:
                if r.get("ts") and r.get("text"):
                    seen.setdefault((r["ts"], r["text"]), None)
            if res.get("atEnd") or not res.get("scrollable", True):
                break
            stagnant = stagnant + 1 if len(seen) == before else 0
            if stagnant >= 3:
                break

        # Stable sort by timestamp keeps same-ts lines in discovery order.
        return [
            {"ts": ts, "text": text}
            for ts, text in sorted(seen, key=lambda p: self._ts_seconds(p[0]))
        ]

    @staticmethod
    def transcript_to_text(rows: List[Dict[str, str]], every: int = 1) -> str:
        """Flatten transcript rows into timestamped lines for prompting/notes.

        `every=N` keeps one timestamp per N segments, which cuts the token
        cost of a long transcript without losing the ability to cite roughly
        where something was said.
        """
        out = []
        for i, r in enumerate(rows):
            if i % every == 0:
                out.append(f"[{r['ts']}] {r['text']}")
            else:
                out.append(r["text"])
        return "\n".join(out)

    def __repr__(self) -> str:
        return f"<DiaTab: {self.title}>"


class DiaWindow:
    """A Dia window.

    Properties:
        id: Unique window identifier
        name: Window title (uses 'title' property internally)
        tabs: List of tabs in this window
    """

    def __init__(self, raw_window, app: "Dia", index: int):
        self._raw = raw_window
        self._app = app
        self._index = index
        # Cache properties since Dia's window refs can be fragile
        self._props = None

    def _get_props(self) -> dict:
        """Get window properties (cached)."""
        if self._props is None:
            self._props = self._raw.properties()
        return self._props

    @property
    def id(self) -> str:
        """Unique identifier of the window."""
        from appscript import k
        return self._get_props().get(k.id, "")

    @property
    def name(self) -> str:
        """The window title."""
        from appscript import k
        return self._get_props().get(k.title, "")

    @property
    def title(self) -> str:
        """Alias for name - the window title."""
        return self.name

    @property
    def tabs(self) -> List[DiaTab]:
        """All tabs in this window."""
        tabs = []
        # Use indexed access like windows
        i = 1
        while True:
            try:
                t = self._raw.tabs[i]
                # Test if tab exists
                t.properties()
                tabs.append(DiaTab(t, self, i))
                i += 1
            except Exception:
                break
        return tabs

    def __repr__(self) -> str:
        try:
            return f"<DiaWindow: {self.name}>"
        except Exception:
            return f"<DiaWindow: (index {self._index})>"


class Dia:
    """The Dia macOS browser (The Browser Company; Chromium/ArcCore-based).

    Provides access to Dia's windows and tabs via AppleScript, and to its AI
    chat sidebar via the macOS Accessibility API.

    Example:
        >>> dia = Dia()
        >>> print(dia.name)
        'Dia'
        >>> print(dia.version)
        '1.0.0'
        >>> for window in dia.windows:
        ...     print(window.name)
    """

    APP_NAME = "Dia"
    APP_PATH = "/Applications/Dia.app"

    def __init__(self, app_name: str = APP_NAME):
        """Initialize Dia app connection.

        Args:
            app_name: Application name (default: "Dia")
        """
        if not HAS_APPSCRIPT:
            raise ImportError(
                "appscript package required. Install with: pip install appscript"
            )
        self._app_name = app_name
        self._app = appscript_app(app_name)

    @property
    def name(self) -> str:
        """The name of the application."""
        return self._app.name()

    @property
    def version(self) -> str:
        """The version of the application."""
        return self._app.version()

    @property
    def windows(self) -> List[DiaWindow]:
        """All windows currently open in Dia."""
        windows = []
        # Use indexed access since Dia returns element references from .get()
        # that don't support .properties() directly
        i = 1
        while True:
            try:
                w = self._app.windows[i]
                # Test if window exists by getting its properties
                w.properties()
                windows.append(DiaWindow(w, self, i))
                i += 1
            except Exception:
                break
        return windows

    def get_window_by_id(self, window_id: str) -> Optional[DiaWindow]:
        """Get a window by its ID.

        Args:
            window_id: The unique window identifier

        Returns:
            DiaWindow if found, None otherwise
        """
        for window in self.windows:
            if window.id == window_id:
                return window
        return None

    def get_all_tabs(self) -> List[DiaTab]:
        """Get all tabs across all windows.

        Returns:
            List of all tabs in the application
        """
        tabs = []
        for window in self.windows:
            tabs.extend(window.tabs)
        return tabs

    def focus_tab(self, tab: DiaTab) -> None:
        """Focus on a specific tab.

        Args:
            tab: The tab to focus
        """
        tab.focus()

    def __repr__(self) -> str:
        try:
            return f"<Dia: {self.name} v{self.version}>"
        except Exception:
            return "<Dia: (not running)>"

    # --- GUI Automation Methods (via PyObjC Accessibility API) ---

    def ask_dia(self, question: str) -> Dict[str, Any]:
        """Send a question to Dia's AI assistant sidebar.

        This uses macOS Accessibility APIs to interact with Dia's GUI.
        The sidebar must be visible (click the sidebar button in Dia if hidden).

        Requirements:
            - Dia must be running with sidebar visible
            - Accessibility permissions must be granted to your terminal/IDE
            - PyObjC must be installed

        Args:
            question: The question to send to Dia's AI assistant

        Returns:
            Dict with keys:
                - success: bool indicating if message was sent
                - message: description of what happened
                - error: (on failure) description of the error

        Example:
            >>> dia = Dia()
            >>> result = dia.ask_dia("What is 2+2?")
            >>> print(result)
            {'success': True, 'message': "Sent: 'What is 2+2?'"}
        """
        if not HAS_PYOBJC:
            return {
                "success": False,
                "error": "PyObjC not installed. Install with: pip install pyobjc",
            }

        # Find Dia process
        dia_pid = _get_pid_for_app(self.APP_NAME)
        if not dia_pid:
            return {"success": False, "error": "Dia is not running"}

        # Create AX element for the app
        app_element = AXUIElementCreateApplication(dia_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return {"success": False, "error": "No Dia windows found"}

        main_window = windows[0]

        # Find the sidebar command bar text field
        command_bar_field = _find_element_by_identifier(main_window, "commandBarTextField")
        if not command_bar_field:
            return {
                "success": False,
                "error": "Command bar not found - is the sidebar visible? "
                "Click the sidebar button in Dia to show it.",
            }

        # Activate Dia (bring to front - REQUIRED for keyboard events)
        if not _activate_app(self.APP_NAME):
            return {"success": False, "error": "Could not activate Dia"}
        time.sleep(0.2)

        # Focus and set text
        AXUIElementSetAttributeValue(command_bar_field, "AXFocused", True)
        time.sleep(0.1)
        AXUIElementSetAttributeValue(command_bar_field, "AXValue", question)
        time.sleep(0.1)

        # Press Return to submit
        _press_return()
        time.sleep(0.3)

        # Verify submission by checking if text was cleared
        after = _get_ax_attribute(command_bar_field, "AXValue")
        if after == question:
            return {
                "success": False,
                "error": "Message may not have been sent - text still in field",
            }

        return {"success": True, "message": f"Sent: '{question}'"}

    def ask_dia_and_wait(
        self,
        question: str,
        timeout: float = 30.0,
        stability_count: int = 3,
    ) -> Dict[str, Any]:
        """Send a question to Dia and wait for the response.

        This is a convenience method that combines ask_dia() and read_dia_response().
        It captures the current response before sending, then waits for a new one.

        Args:
            question: The question to send to Dia's AI assistant
            timeout: Maximum time to wait for response (seconds)
            stability_count: Number of identical reads required for stability

        Returns:
            Dict with keys:
                - success: bool indicating if message was sent and response received
                - response: The AI's response text (on success)
                - error: (on failure) description of the error

        Example:
            >>> dia = Dia()
            >>> result = dia.ask_dia_and_wait("What is 2+2?")
            >>> print(result)
            {'success': True, 'response': '4'}
        """
        if not HAS_PYOBJC:
            return {
                "success": False,
                "error": "PyObjC not installed. Install with: pip install pyobjc",
            }

        # Capture current response before sending
        dia_pid = _get_pid_for_app(self.APP_NAME)
        if not dia_pid:
            return {"success": False, "error": "Dia is not running"}

        app_element = AXUIElementCreateApplication(dia_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return {"success": False, "error": "No Dia windows found"}

        previous_response = self._get_last_ai_response(windows[0])

        # Send the question
        send_result = self.ask_dia(question)
        if not send_result.get("success"):
            return send_result

        # Wait for new response
        return self.read_dia_response(
            timeout=timeout,
            stability_count=stability_count,
            previous_response=previous_response,
        )

    def is_generating(self) -> bool:
        """Check if Dia is currently generating a response.

        This looks for the "Thinking…" indicator that appears during generation.

        Returns:
            True if Dia is generating, False otherwise.

        Example:
            >>> dia = Dia()
            >>> dia.ask_dia("Write a long essay")
            >>> dia.is_generating()
            True
        """
        if not HAS_PYOBJC:
            return False

        dia_pid = _get_pid_for_app(self.APP_NAME)
        if not dia_pid:
            return False

        app_element = AXUIElementCreateApplication(dia_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return False

        return _is_dia_generating(windows[0])

    def read_dia_response(
        self,
        timeout: float = 30.0,
        stability_count: int = 3,
        previous_response: Optional[str] = None,
        use_waitidle: bool = True,
    ) -> Dict[str, Any]:
        """Read the latest AI response from Dia's conversation.

        This uses macOS Accessibility APIs to read the conversation history
        and extract the most recent AI response. It uses a WaitIdle pattern
        to detect when generation is complete:

        1. First waits for the "Thinking…" indicator to disappear (WaitIdle)
        2. Then polls until response stabilizes (same text for multiple reads)

        Args:
            timeout: Maximum time to wait for response (seconds)
            stability_count: Number of identical reads required for stability
            previous_response: If provided, wait for response to be different
                from this value before starting stability checks. Use this
                when calling after ask_dia() to ensure you get the new response.
            use_waitidle: If True (default), wait for "Thinking…" to disappear
                before checking response stability. Set to False to use only
                stability polling.

        Returns:
            Dict with keys:
                - success: bool indicating if response was read
                - response: The AI's response text (on success)
                - was_generating: (on success) True if WaitIdle was triggered
                - error: (on failure) description of the error

        Example:
            >>> dia = Dia()
            >>> dia.ask_dia("What is 2+2?")
            >>> result = dia.read_dia_response()
            >>> print(result)
            {'success': True, 'response': '4', 'was_generating': True}
        """
        if not HAS_PYOBJC:
            return {
                "success": False,
                "error": "PyObjC not installed. Install with: pip install pyobjc",
            }

        dia_pid = _get_pid_for_app(self.APP_NAME)
        if not dia_pid:
            return {"success": False, "error": "Dia is not running"}

        app_element = AXUIElementCreateApplication(dia_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return {"success": False, "error": "No Dia windows found"}

        main_window = windows[0]

        start_time = time.time()
        last_response = None
        stable_count = 0
        found_new_response = previous_response is None  # If no previous, any response is "new"
        was_generating = False

        while (time.time() - start_time) < timeout:
            # WaitIdle: Check if Dia is still generating
            if use_waitidle and _is_dia_generating(main_window):
                was_generating = True
                time.sleep(0.3)  # Poll more frequently when generating
                continue

            response = self._get_last_ai_response(main_window)

            if response:
                # If we're waiting for a new response, check if it's different
                if not found_new_response:
                    if response != previous_response:
                        found_new_response = True
                        last_response = response
                        stable_count = 1
                    # Still seeing old response, keep waiting
                    time.sleep(0.5)
                    continue

                # Stability check for the new response
                if response == last_response:
                    stable_count += 1
                    if stable_count >= stability_count:
                        return {
                            "success": True,
                            "response": response,
                            "was_generating": was_generating,
                        }
                else:
                    stable_count = 1
                    last_response = response

            time.sleep(0.5)

        if last_response and found_new_response:
            return {
                "success": True,
                "response": last_response,
                "was_generating": was_generating,
            }

        if not found_new_response:
            return {"success": False, "error": "Timeout: response did not change from previous"}

        return {"success": False, "error": "Timeout waiting for response"}

    def _get_last_ai_response(self, window) -> Optional[str]:
        """Extract the last AI response from Dia's conversation.

        The conversation is in an AXScrollArea at window level (not in commandBar).
        AI responses are AXGroup elements containing only AXTextArea (no AXImage).
        User messages have an AXImage (avatar) alongside the text.
        """
        # Find the conversation scroll area at window level
        # It's the AXScrollArea that contains an AXList with AXSectionList
        window_children = _get_ax_attribute(window, "AXChildren") or []

        conv_scroll = None
        for child in window_children:
            role = _get_ax_attribute(child, "AXRole")
            if role == "AXScrollArea":
                # Check if this scroll area has the conversation list structure
                scroll_children = _get_ax_attribute(child, "AXChildren") or []
                for sc in scroll_children:
                    sc_role = _get_ax_attribute(sc, "AXRole")
                    sc_subrole = _get_ax_attribute(sc, "AXSubrole")
                    if sc_role == "AXList" and sc_subrole == "AXCollectionList":
                        conv_scroll = child
                        break
            if conv_scroll:
                break

        if not conv_scroll:
            return None

        # Navigate: AXScrollArea -> AXList(Collection) -> AXList(Section) -> AXGroups
        scroll_children = _get_ax_attribute(conv_scroll, "AXChildren") or []
        collection_list = None
        for child in scroll_children:
            if _get_ax_attribute(child, "AXRole") == "AXList":
                collection_list = child
                break

        if not collection_list:
            return None

        section_lists = _get_ax_attribute(collection_list, "AXChildren") or []
        section_list = None
        for child in section_lists:
            if _get_ax_attribute(child, "AXRole") == "AXList":
                section_list = child
                break

        if not section_list:
            return None

        # Get all groups - iterate backwards to find last AI response
        groups = _get_ax_attribute(section_list, "AXChildren") or []

        # Find the last AI response (group with AXTextArea but no AXImage)
        for group in reversed(groups):
            if _get_ax_attribute(group, "AXRole") != "AXGroup":
                continue

            group_children = _get_ax_attribute(group, "AXChildren") or []

            # Skip groups with buttons (action bar at end of conversation)
            has_button = any(_get_ax_attribute(c, "AXRole") == "AXButton" for c in group_children)
            if has_button:
                continue

            # Skip "Thought for X seconds" indicators
            has_static_text = any(_get_ax_attribute(c, "AXRole") == "AXStaticText" for c in group_children)
            if has_static_text:
                continue

            # Check for AXTextArea without AXImage (AI response, not user message)
            has_text_area = False
            has_image = False
            text_value = None

            for child in group_children:
                child_role = _get_ax_attribute(child, "AXRole")
                if child_role == "AXTextArea":
                    has_text_area = True
                    text_value = _get_ax_attribute(child, "AXValue")
                elif child_role == "AXImage":
                    has_image = True
                elif child_role == "AXScrollArea":
                    # Nested scroll area (occurs in some messages) - skip this group
                    has_image = True  # Treat as user message to skip

            # AI responses have AXTextArea but no AXImage
            if has_text_area and not has_image and text_value:
                return str(text_value)

        return None
