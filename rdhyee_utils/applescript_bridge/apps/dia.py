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
import time

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
