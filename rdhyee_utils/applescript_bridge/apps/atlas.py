"""
Atlas - Python bindings for ChatGPT Atlas macOS app.

Atlas is OpenAI's ChatGPT desktop application built on Chromium.
It has a full Chromium-based AppleScript dictionary similar to Chrome/Comet.

Note: The outer wrapper app doesn't expose SDEF, but the inner browser
at Contents/Support/ChatGPT Atlas.app does. However, you can connect
simply by app name "ChatGPT Atlas".

Capabilities:
- Window management (list, create, close, bounds, zoom, minimize)
- Tab management (list, create, close, navigate)
- JavaScript execution in tabs (requires View > Developer > Allow JavaScript)
- Bookmarks access
- Navigation (back, forward, reload, stop)
- Chat with ChatGPT sidebar via ask_atlas() using PyAutoGUI

Example:
    >>> from rdhyee_utils.applescript_bridge import Atlas
    >>> atlas = Atlas()
    >>> atlas.name
    'ChatGPT Atlas'
    >>> for window in atlas.windows:
    ...     print(window.name)
    ...     for tab in window.tabs:
    ...         print(f"  - {tab.title}: {tab.url}")

    # Send a message to ChatGPT sidebar:
    >>> result = atlas.ask_atlas("What is 2+2?")
    >>> print(result)
    {'success': True, 'message': "Sent: 'What is 2+2?'"}
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

try:
    from appscript import app as appscript_app

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False

# PyAutoGUI for GUI automation
try:
    import pyautogui
    import pyperclip

    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

# PyObjC Accessibility API for finding UI elements
try:
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementCopyAttributeValue,
        kAXErrorSuccess,
    )
    import Cocoa

    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False


# --- Accessibility API Helpers for PyAutoGUI ---


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


def _parse_ax_point(ax_value) -> Optional[tuple]:
    """Parse CGPoint from AXValue string representation."""
    if not ax_value:
        return None
    s = str(ax_value)
    match = re.search(r'x:(\d+\.?\d*)\s*y:(\d+\.?\d*)', s)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    return None


def _parse_ax_size(ax_value) -> Optional[tuple]:
    """Parse CGSize from AXValue string representation."""
    if not ax_value:
        return None
    s = str(ax_value)
    match = re.search(r'w:(\d+\.?\d*)\s*h:(\d+\.?\d*)', s)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    return None


def _get_position(element) -> Optional[tuple]:
    """Get element position as (x, y) tuple."""
    return _parse_ax_point(_get_ax_attribute(element, "AXPosition"))


def _get_size(element) -> Optional[tuple]:
    """Get element size as (width, height) tuple."""
    return _parse_ax_size(_get_ax_attribute(element, "AXSize"))


def _find_element_by_desc(element, target_desc: str, depth: int = 0, max_depth: int = 20):
    """Recursively find an element by its AXDescription."""
    if depth > max_depth:
        return None
    desc = _get_ax_attribute(element, "AXDescription") or ""
    if target_desc in desc:
        return element
    children = _get_ax_attribute(element, "AXChildren")
    if children:
        for child in children:
            result = _find_element_by_desc(child, target_desc, depth + 1, max_depth)
            if result:
                return result
    return None


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


class AtlasTab:
    """A tab in an Atlas window.

    Atlas tabs support JavaScript execution, navigation controls,
    and full content interaction (Chromium-based).

    Properties:
        id: Unique tab identifier
        title: Tab title
        url: Tab URL (readable and writable)
        loading: Whether tab is currently loading
    """

    def __init__(self, raw_tab, window: "AtlasWindow"):
        self._raw = raw_tab
        self._window = window

    @property
    def id(self) -> str:
        """Unique identifier of the tab."""
        return self._raw.id()

    @property
    def title(self) -> str:
        """The title of the tab."""
        return self._raw.title()

    @property
    def url(self) -> str:
        """The URL visible to the user."""
        return self._raw.URL()

    @url.setter
    def url(self, value: str) -> None:
        """Navigate the tab to a new URL."""
        self._raw.URL.set(value)

    @property
    def loading(self) -> bool:
        """Whether the tab is currently loading."""
        return self._raw.loading()

    # Navigation methods
    def go_back(self) -> None:
        """Go back in history (if possible)."""
        self._raw.go_back()

    def go_forward(self) -> None:
        """Go forward in history (if possible)."""
        self._raw.go_forward()

    def reload(self) -> None:
        """Reload the tab."""
        self._raw.reload()

    def stop(self) -> None:
        """Stop loading the tab."""
        self._raw.stop()

    def view_source(self) -> None:
        """View the HTML source of the tab."""
        self._raw.view_source()

    # Content interaction
    def execute(self, javascript: str) -> Any:
        """Execute JavaScript in the tab.

        Args:
            javascript: JavaScript code to execute

        Returns:
            Result of the JavaScript execution

        Example:
            >>> tab.execute("document.title")
            'ChatGPT'
        """
        return self._raw.execute(javascript=javascript)

    def execute_json(self, javascript: str) -> Any:
        """Execute JavaScript and parse result as JSON.

        Args:
            javascript: JavaScript that returns a JSON-serializable value

        Returns:
            Parsed Python object
        """
        result = self.execute(javascript)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return None

    # Clipboard operations
    def select_all(self) -> None:
        """Select all content in the tab."""
        self._raw.select_all()

    def copy_selection(self) -> None:
        """Copy selected text."""
        self._raw.copy_selection()

    def paste_selection(self) -> None:
        """Paste clipboard content."""
        self._raw.paste_selection()

    def cut_selection(self) -> None:
        """Cut selected text."""
        self._raw.cut_selection()

    def undo(self) -> None:
        """Undo the last action."""
        self._raw.undo()

    def redo(self) -> None:
        """Redo the last undone action."""
        self._raw.redo()

    def close(self) -> None:
        """Close this tab."""
        self._raw.close()

    def __repr__(self) -> str:
        return f"<AtlasTab: {self.title}>"


class AtlasWindow:
    """An Atlas browser window.

    Properties:
        id: Unique window identifier
        name: Window title (alias for active tab title)
        given_name: User-assigned window name
        index: Window index (front to back)
        bounds: Window bounds (x, y, width, height)
        mode: 'normal' or 'incognito'
        active_tab: Currently selected tab
        active_tab_index: Index of active tab
        tabs: List of all tabs
    """

    def __init__(self, raw_window, app: "Atlas"):
        self._raw = raw_window
        self._app = app

    @property
    def id(self) -> str:
        """Unique identifier of the window."""
        return self._raw.id()

    @property
    def name(self) -> str:
        """The full title of the window."""
        return self._raw.name()

    @property
    def given_name(self) -> str:
        """The user-assigned name of the window."""
        return self._raw.given_name()

    @given_name.setter
    def given_name(self, value: str) -> None:
        """Set the user-assigned window name."""
        self._raw.given_name.set(value)

    @property
    def index(self) -> int:
        """The index of the window (front to back)."""
        return self._raw.index()

    @index.setter
    def index(self, value: int) -> None:
        """Set window index (reorder windows)."""
        self._raw.index.set(value)

    @property
    def bounds(self) -> tuple:
        """The bounding rectangle of the window."""
        return self._raw.bounds()

    @bounds.setter
    def bounds(self, value: tuple) -> None:
        """Set window bounds (x, y, width, height)."""
        self._raw.bounds.set(value)

    @property
    def mode(self) -> str:
        """Window mode: 'normal' or 'incognito'."""
        return self._raw.mode()

    @property
    def closeable(self) -> bool:
        """Whether the window has a close box."""
        return self._raw.closeable()

    @property
    def minimizable(self) -> bool:
        """Whether the window can be minimized."""
        return self._raw.minimizable()

    @property
    def minimized(self) -> bool:
        """Whether the window is currently minimized."""
        return self._raw.minimized()

    @minimized.setter
    def minimized(self, value: bool) -> None:
        """Minimize or restore the window."""
        self._raw.minimized.set(value)

    @property
    def resizable(self) -> bool:
        """Whether the window can be resized."""
        return self._raw.resizable()

    @property
    def visible(self) -> bool:
        """Whether the window is visible."""
        return self._raw.visible()

    @visible.setter
    def visible(self, value: bool) -> None:
        """Show or hide the window."""
        self._raw.visible.set(value)

    @property
    def zoomable(self) -> bool:
        """Whether the window can be zoomed."""
        return self._raw.zoomable()

    @property
    def zoomed(self) -> bool:
        """Whether the window is zoomed (fullscreen)."""
        return self._raw.zoomed()

    @zoomed.setter
    def zoomed(self, value: bool) -> None:
        """Zoom or unzoom the window."""
        self._raw.zoomed.set(value)

    @property
    def active_tab(self) -> AtlasTab:
        """Returns the currently selected tab."""
        return AtlasTab(self._raw.active_tab(), self)

    @property
    def active_tab_index(self) -> int:
        """The index of the active tab."""
        return self._raw.active_tab_index()

    @active_tab_index.setter
    def active_tab_index(self, value: int) -> None:
        """Set active tab by index."""
        self._raw.active_tab_index.set(value)

    @property
    def tabs(self) -> List[AtlasTab]:
        """All tabs in this window."""
        return [AtlasTab(tab, self) for tab in self._raw.tabs()]

    def close(self) -> None:
        """Close this window."""
        self._raw.close()

    def __repr__(self) -> str:
        return f"<AtlasWindow: {self.name}>"


class Atlas:
    """ChatGPT Atlas macOS application.

    Provides full access to Atlas's Chromium-based browser features
    via AppleScript, including window/tab management, JavaScript
    execution, and navigation.

    Example:
        >>> atlas = Atlas()
        >>> print(atlas.name)
        'ChatGPT Atlas'

        >>> # List all windows and tabs
        >>> for window in atlas.windows:
        ...     print(window.name)
        ...     for tab in window.tabs:
        ...         print(f"  - {tab.title}")

        >>> # Execute JavaScript
        >>> tab = atlas.windows[0].active_tab
        >>> tab.execute("document.title")
        'ChatGPT'
    """

    APP_NAME = "ChatGPT Atlas"
    BUNDLE_ID = "com.openai.atlas"

    def __init__(self, app_name: str = APP_NAME):
        """Initialize Atlas app connection.

        Args:
            app_name: Application name (default: "ChatGPT Atlas")
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
    def frontmost(self) -> bool:
        """Is this the frontmost (active) application?"""
        return self._app.frontmost()

    @property
    def windows(self) -> List[AtlasWindow]:
        """All windows in the application, ordered front to back."""
        return [AtlasWindow(w, self) for w in self._app.windows()]

    def get_window_by_id(self, window_id: str) -> Optional[AtlasWindow]:
        """Get a window by its ID.

        Args:
            window_id: The unique window identifier

        Returns:
            AtlasWindow if found, None otherwise
        """
        for window in self.windows:
            if window.id == window_id:
                return window
        return None

    def get_all_tabs(self) -> List[AtlasTab]:
        """Get all tabs across all windows.

        Returns:
            List of all tabs in the application
        """
        tabs = []
        for window in self.windows:
            tabs.extend(window.tabs)
        return tabs

    def open_url(self, url: str) -> None:
        """Open a URL in a new tab.

        Args:
            url: URL to open
        """
        self._app.open(url)

    def quit(self) -> None:
        """Quit the application."""
        self._app.quit()

    def __repr__(self) -> str:
        try:
            return f"<Atlas: {self.name} v{self.version}>"
        except Exception:
            return "<Atlas: (not running)>"

    # --- GUI Automation Methods (via PyAutoGUI + Accessibility API) ---

    def _find_all_webareas(self, element, depth: int = 0, max_depth: int = 20, webareas: list = None) -> list:
        """Recursively find all AXWebArea elements in the UI tree."""
        if webareas is None:
            webareas = []
        if depth > max_depth:
            return webareas

        role = _get_ax_attribute(element, "AXRole") or ""
        if role == "AXWebArea":
            pos = _get_position(element)
            size = _get_size(element)
            if pos and size:
                webareas.append({
                    "element": element,
                    "position": pos,
                    "size": size
                })

        children = _get_ax_attribute(element, "AXChildren")
        if children:
            for child in children:
                self._find_all_webareas(child, depth + 1, max_depth, webareas)

        return webareas

    def _find_sidebar_webarea(self, window):
        """Find the ChatGPT sidebar WebArea.

        The sidebar is the rightmost AXWebArea that is narrow (~300-400px wide)
        and tall (>500px). When there are multiple web areas, the sidebar is
        the one with the highest x position.
        """
        webareas = self._find_all_webareas(window)

        if not webareas:
            return None

        # Filter to tall, narrow elements (sidebar characteristics)
        # Sidebar is typically ~340px wide and ~900px+ tall
        candidates = [
            wa for wa in webareas
            if wa["size"][0] < 500 and wa["size"][1] > 500  # Narrow and tall
        ]

        if not candidates:
            return None

        # Return the rightmost one (highest x position)
        rightmost = max(candidates, key=lambda wa: wa["position"][0])
        return rightmost["element"]

    def ask_atlas(self, question: str) -> Dict[str, Any]:
        """Send a question to ChatGPT Atlas sidebar using PyAutoGUI.

        This uses macOS Accessibility APIs to find the ChatGPT sidebar position,
        then uses PyAutoGUI to click and type. The sidebar must be visible.

        Requirements:
            - ChatGPT Atlas must be running with sidebar visible
            - PyAutoGUI and pyperclip must be installed
            - PyObjC must be installed for Accessibility APIs

        Args:
            question: The question to send to ChatGPT

        Returns:
            Dict with keys:
                - success: bool indicating if message was sent
                - message: description of what happened
                - error: (on failure) description of the error

        Example:
            >>> atlas = Atlas()
            >>> result = atlas.ask_atlas("What is 2+2?")
            >>> print(result)
            {'success': True, 'message': "Sent: 'What is 2+2?'"}
        """
        if not HAS_PYAUTOGUI:
            return {
                "success": False,
                "error": "PyAutoGUI not installed. Install with: pip install pyautogui pyperclip",
            }
        if not HAS_PYOBJC:
            return {
                "success": False,
                "error": "PyObjC not installed. Install with: pip install pyobjc",
            }

        # Find Atlas process
        atlas_pid = _get_pid_for_app(self.APP_NAME)
        if not atlas_pid:
            return {"success": False, "error": "ChatGPT Atlas is not running"}

        # Create AX element for the app
        app_element = AXUIElementCreateApplication(atlas_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return {"success": False, "error": "No Atlas windows found"}

        # Find the ChatGPT sidebar - it's the rightmost AXWebArea in the window
        # The sidebar description changes based on conversation topic, so we can't rely on "ChatGPT"
        sidebar_area = self._find_sidebar_webarea(windows[0])

        if not sidebar_area:
            return {
                "success": False,
                "error": "ChatGPT sidebar not visible - click the toggle button to show it.",
            }

        chatgpt_area = sidebar_area

        area_pos = _get_position(chatgpt_area)
        area_size = _get_size(chatgpt_area)

        if not area_pos or not area_size:
            return {"success": False, "error": "Could not get sidebar position"}

        # Calculate input field location (bottom center of sidebar)
        input_x = int(area_pos[0] + area_size[0] / 2)
        input_y = int(area_pos[1] + area_size[1] - 40)  # Near bottom

        # Activate Atlas (bring to front)
        if not _activate_app(self.APP_NAME):
            return {"success": False, "error": "Could not activate Atlas"}
        time.sleep(0.3)

        # Set up PyAutoGUI
        pyautogui.PAUSE = 0.05

        # Click on the input area
        pyautogui.click(input_x, input_y)
        time.sleep(0.2)

        # Use clipboard for Unicode support
        old_clipboard = pyperclip.paste()  # Save current clipboard
        pyperclip.copy(question)
        pyautogui.hotkey('command', 'v')  # Paste
        time.sleep(0.1)
        pyperclip.copy(old_clipboard)  # Restore clipboard

        # Press Enter to send
        pyautogui.press('enter')

        return {"success": True, "message": f"Sent: '{question}'"}

    def is_generating(self) -> bool:
        """Check if ChatGPT Atlas is currently generating a response.

        This reads the sidebar content and checks for generating indicators
        like "ChatGPT is still generating" or "Stop generating".

        Note: This method involves GUI interaction (clipboard read) and may
        briefly flash the selection. Use sparingly.

        Returns:
            True if ChatGPT is generating, False otherwise.

        Example:
            >>> atlas = Atlas()
            >>> atlas.ask_atlas("Write a long essay")
            >>> atlas.is_generating()
            True
        """
        if not HAS_PYAUTOGUI or not HAS_PYOBJC:
            return False

        atlas_pid = _get_pid_for_app(self.APP_NAME)
        if not atlas_pid:
            return False

        app_element = AXUIElementCreateApplication(atlas_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return False

        sidebar_area = self._find_sidebar_webarea(windows[0])
        if not sidebar_area:
            return False

        area_pos = _get_position(sidebar_area)
        area_size = _get_size(sidebar_area)
        if not area_pos or not area_size:
            return False

        # Quick clipboard read to check generating status
        old_clipboard = pyperclip.paste()
        try:
            _activate_app(self.APP_NAME)
            time.sleep(0.1)
            sidebar_x = int(area_pos[0] + area_size[0] / 2)
            sidebar_y = int(area_pos[1] + area_size[1] * 0.4)
            pyautogui.click(sidebar_x, sidebar_y)
            time.sleep(0.1)
            pyautogui.hotkey('command', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('command', 'c')
            time.sleep(0.1)
            content = pyperclip.paste()
            pyautogui.click(sidebar_x, sidebar_y)  # Deselect
            return self._is_generating_from_clipboard(content)
        finally:
            pyperclip.copy(old_clipboard)

    def read_atlas_response(
        self,
        timeout: float = 30.0,
        stability_count: int = 3,
        previous_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read the latest AI response from ChatGPT Atlas sidebar.

        This uses a clipboard-based approach since Atlas (Electron) doesn't
        support AppleScript JavaScript execution. It uses a WaitIdle pattern:

        1. Focuses the sidebar
        2. Selects all (Cmd+A) and copies (Cmd+C)
        3. Checks for "generating" indicators (WaitIdle)
        4. Parses the clipboard for the last ChatGPT response
        5. Polls until the response stabilizes

        Args:
            timeout: Maximum time to wait for response (seconds)
            stability_count: Number of identical reads required for stability
            previous_response: If provided, wait for response to be different
                from this value before starting stability checks.

        Returns:
            Dict with keys:
                - success: bool indicating if response was read
                - response: The AI's response text (on success)
                - was_generating: (on success) True if WaitIdle was triggered
                - error: (on failure) description of the error

        Example:
            >>> atlas = Atlas()
            >>> atlas.ask_atlas("What is 2+2?")
            >>> result = atlas.read_atlas_response()
            >>> print(result)
            {'success': True, 'response': '4', 'was_generating': True}
        """
        if not HAS_PYAUTOGUI:
            return {
                "success": False,
                "error": "PyAutoGUI not installed. Install with: pip install pyautogui pyperclip",
            }
        if not HAS_PYOBJC:
            return {
                "success": False,
                "error": "PyObjC not installed. Install with: pip install pyobjc",
            }

        atlas_pid = _get_pid_for_app(self.APP_NAME)
        if not atlas_pid:
            return {"success": False, "error": "ChatGPT Atlas is not running"}

        app_element = AXUIElementCreateApplication(atlas_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return {"success": False, "error": "No Atlas windows found"}

        sidebar_area = self._find_sidebar_webarea(windows[0])
        if not sidebar_area:
            return {
                "success": False,
                "error": "ChatGPT sidebar not visible - click the toggle button to show it.",
            }

        area_pos = _get_position(sidebar_area)
        area_size = _get_size(sidebar_area)
        if not area_pos or not area_size:
            return {"success": False, "error": "Could not get sidebar position"}

        # Calculate click position in the CONVERSATION area (upper portion)
        # The input field is at the bottom, so we click in the upper 40%
        # This ensures Cmd+A selects the conversation, not other content
        sidebar_x = int(area_pos[0] + area_size[0] / 2)
        sidebar_y = int(area_pos[1] + area_size[1] * 0.4)  # 40% from top

        # Save current clipboard
        old_clipboard = pyperclip.paste()

        start_time = time.time()
        last_response = None
        stable_count = 0
        found_new_response = previous_response is None
        was_generating = False

        try:
            # Activate Atlas
            if not _activate_app(self.APP_NAME):
                return {"success": False, "error": "Could not activate Atlas"}
            time.sleep(0.2)

            pyautogui.PAUSE = 0.05

            while (time.time() - start_time) < timeout:
                # Click to focus sidebar
                pyautogui.click(sidebar_x, sidebar_y)
                time.sleep(0.15)

                # Select all and copy
                pyautogui.hotkey('command', 'a')
                time.sleep(0.15)
                pyautogui.hotkey('command', 'c')
                time.sleep(0.2)

                # Parse clipboard for last response
                content = pyperclip.paste()

                # WaitIdle: Check if still generating
                if self._is_generating_from_clipboard(content):
                    was_generating = True
                    # Click to deselect and wait
                    pyautogui.click(sidebar_x, sidebar_y)
                    time.sleep(0.3)  # Poll faster when generating
                    continue

                response = self._parse_chatgpt_response(content)

                # Click to deselect
                pyautogui.click(sidebar_x, sidebar_y)

                if response:
                    # If waiting for new response, check if different
                    if not found_new_response:
                        if response != previous_response:
                            found_new_response = True
                            last_response = response
                            stable_count = 1
                        time.sleep(0.5)
                        continue

                    # Stability check
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

        finally:
            # Restore clipboard
            pyperclip.copy(old_clipboard)

    def _is_generating_from_clipboard(self, clipboard_content: str) -> bool:
        """Check if the clipboard content indicates ChatGPT is still generating.

        Returns True if any generating indicator is found.
        """
        if not clipboard_content:
            return False

        generating_indicators = [
            "ChatGPT is still generating",
            "Stop generating",
            "ChatGPT is thinking",
        ]

        content_lower = clipboard_content.lower()
        for indicator in generating_indicators:
            if indicator.lower() in content_lower:
                return True

        return False

    def _parse_chatgpt_response(self, clipboard_content: str) -> Optional[str]:
        """Parse the last ChatGPT response from clipboard content.

        The clipboard format from Atlas sidebar is:
            Skip to content
            You said:
            <user message>
            ChatGPT said:
            <AI response>
            You said:
            ...

        The clipboard often contains junk from the main browser area appended
        at the end (tab titles, email content, file inputs, etc). We strip that.

        Returns the text after the last "ChatGPT said:" marker, or None if
        no response found or response is empty (still generating/hung).
        """
        if not clipboard_content:
            return None

        content = clipboard_content

        # Check if ChatGPT is still generating - if so, return None to keep polling
        if self._is_generating_from_clipboard(clipboard_content):
            return None

        # First, strip obvious junk from main browser that gets appended
        # These patterns indicate we've left the ChatGPT sidebar content
        junk_indicators = [
            " - Gmail",
            " - Google Search",
            " - YouTube",
            "No file chosen",
            "You have authorized a payment",
        ]

        for indicator in junk_indicators:
            if indicator in content:
                content = content.split(indicator)[0]

        # Split by "ChatGPT said:" to find responses
        marker = "ChatGPT said:"
        parts = content.split(marker)

        if len(parts) < 2:
            return None

        # Get the last response (after the last marker)
        last_response_section = parts[-1]

        # The response ends at the next "You said:" or end of content
        end_marker = "You said:"
        if end_marker in last_response_section:
            last_response_section = last_response_section.split(end_marker)[0]

        # Clean up the response
        response = last_response_section.strip()

        # If response is empty, ChatGPT may still be generating or hung
        if not response:
            return None

        # Remove trailing button/action text
        cleanup_suffixes = ["Copy", "Regenerate", "4o", "Edit"]

        lines = response.split('\n')
        while lines and lines[-1].strip() in cleanup_suffixes:
            lines.pop()
        response = '\n'.join(lines).strip()

        return response if response else None

    def ask_atlas_and_wait(
        self,
        question: str,
        timeout: float = 30.0,
        stability_count: int = 3,
    ) -> Dict[str, Any]:
        """Send a question to ChatGPT Atlas and wait for the response.

        This is a convenience method that combines ask_atlas() and read_atlas_response().
        It captures the current response before sending, then waits for a new one.

        Args:
            question: The question to send to ChatGPT
            timeout: Maximum time to wait for response (seconds)
            stability_count: Number of identical reads required for stability

        Returns:
            Dict with keys:
                - success: bool indicating if message was sent and response received
                - response: The AI's response text (on success)
                - error: (on failure) description of the error

        Example:
            >>> atlas = Atlas()
            >>> result = atlas.ask_atlas_and_wait("What is 2+2?")
            >>> print(result)
            {'success': True, 'response': '4'}
        """
        if not HAS_PYAUTOGUI or not HAS_PYOBJC:
            return {
                "success": False,
                "error": "PyAutoGUI and PyObjC required.",
            }

        # Capture current response before sending
        atlas_pid = _get_pid_for_app(self.APP_NAME)
        if not atlas_pid:
            return {"success": False, "error": "ChatGPT Atlas is not running"}

        app_element = AXUIElementCreateApplication(atlas_pid)
        windows = _get_ax_attribute(app_element, "AXWindows")
        if not windows:
            return {"success": False, "error": "No Atlas windows found"}

        sidebar_area = self._find_sidebar_webarea(windows[0])
        previous_response = None

        if sidebar_area:
            # Try to get current response via quick clipboard read
            area_pos = _get_position(sidebar_area)
            area_size = _get_size(sidebar_area)
            if area_pos and area_size:
                old_clipboard = pyperclip.paste()
                try:
                    _activate_app(self.APP_NAME)
                    time.sleep(0.2)
                    # Click in conversation area (upper 40%) for clean Cmd+A selection
                    sidebar_x = int(area_pos[0] + area_size[0] / 2)
                    sidebar_y = int(area_pos[1] + area_size[1] * 0.4)
                    pyautogui.click(sidebar_x, sidebar_y)
                    time.sleep(0.1)
                    pyautogui.hotkey('command', 'a')
                    time.sleep(0.1)
                    pyautogui.hotkey('command', 'c')
                    time.sleep(0.15)
                    content = pyperclip.paste()
                    previous_response = self._parse_chatgpt_response(content)
                    pyautogui.click(sidebar_x, sidebar_y)  # Deselect
                finally:
                    pyperclip.copy(old_clipboard)

        # Send the question
        send_result = self.ask_atlas(question)
        if not send_result.get("success"):
            return send_result

        # Give ChatGPT a moment to start processing before we poll
        time.sleep(1.0)

        # Wait for new response
        return self.read_atlas_response(
            timeout=timeout,
            stability_count=stability_count,
            previous_response=previous_response,
        )
