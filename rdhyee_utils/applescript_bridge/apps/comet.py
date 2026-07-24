"""
Comet - Python bindings for Perplexity's Comet macOS app.

Comet is Perplexity's native macOS application built on Chromium.
It has a rich AppleScript dictionary similar to Google Chrome.

Capabilities:
- Window management (list, create, close, bounds, zoom, minimize)
- Tab management (list, create, close, navigate)
- JavaScript execution in tabs
- Bookmarks access
- Navigation (back, forward, reload, stop)

Example:
    >>> from rdhyee_utils.applescript_bridge import Comet
    >>> comet = Comet()
    >>> comet.name
    'Comet'
    >>> for window in comet.windows:
    ...     print(window.name)
    ...     for tab in window.tabs:
    ...         print(f"  - {tab.title}: {tab.url}")
"""

import json
from typing import Any, Dict, List, Optional

try:
    from appscript import app as appscript_app

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False


class CometTab:
    """A tab in a Comet window.

    Comet tabs support JavaScript execution, navigation controls,
    and full content interaction similar to Chrome.

    Properties:
        id: Unique tab identifier
        title: Tab title
        url: Tab URL (readable and writable)
        loading: Whether tab is currently loading
    """

    def __init__(self, raw_tab, window: "CometWindow"):
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
            'Perplexity AI'
            >>> tab.execute("document.body.innerText")
            'Welcome to Perplexity...'
        """
        return self._raw.execute(javascript=javascript)

    def execute_json(self, javascript: str) -> Any:
        """Execute JavaScript and parse result as JSON.

        Useful for extracting structured data from pages.

        Args:
            javascript: JavaScript that returns a JSON-serializable value

        Returns:
            Parsed Python object

        Example:
            >>> tab.execute_json("JSON.stringify({a: 1, b: 2})")
            {'a': 1, 'b': 2}
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
        return f"<CometTab: {self.title}>"


class CometWindow:
    """A Comet browser window.

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

    def __init__(self, raw_window, app: "Comet"):
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
    def active_tab(self) -> CometTab:
        """Returns the currently selected tab."""
        return CometTab(self._raw.active_tab(), self)

    @property
    def active_tab_index(self) -> int:
        """The index of the active tab."""
        return self._raw.active_tab_index()

    @active_tab_index.setter
    def active_tab_index(self, value: int) -> None:
        """Set active tab by index."""
        self._raw.active_tab_index.set(value)

    @property
    def tabs(self) -> List[CometTab]:
        """All tabs in this window."""
        return [CometTab(tab, self) for tab in self._raw.tabs()]

    def close(self) -> None:
        """Close this window."""
        self._raw.close()

    def __repr__(self) -> str:
        return f"<CometWindow: {self.name}>"


class Comet:
    """Perplexity Comet macOS application.

    Provides full access to Comet's Chromium-based browser features
    via AppleScript, including window/tab management, JavaScript
    execution, and navigation.

    Example:
        >>> comet = Comet()
        >>> print(comet.name)
        'Comet'

        >>> # List all tabs
        >>> for tab in comet.get_all_tabs():
        ...     print(f"{tab.title}: {tab.url}")

        >>> # Execute JavaScript
        >>> tab = comet.windows[0].active_tab
        >>> tab.execute("document.title")
        'Perplexity AI'

        >>> # Extract page content
        >>> content = tab.execute("document.body.innerText")
    """

    APP_NAME = "Comet"
    APP_PATH = "/Applications/Comet.app"

    def __init__(self, app_name: str = APP_NAME):
        """Initialize Comet app connection.

        Args:
            app_name: Application name (default: "Comet")
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
    def windows(self) -> List[CometWindow]:
        """All windows in the application, ordered front to back."""
        return [CometWindow(w, self) for w in self._app.windows()]

    def get_window_by_id(self, window_id: str) -> Optional[CometWindow]:
        """Get a window by its ID.

        Args:
            window_id: The unique window identifier

        Returns:
            CometWindow if found, None otherwise
        """
        for window in self.windows:
            if window.id == window_id:
                return window
        return None

    def get_all_tabs(self) -> List[CometTab]:
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

    # =========================================================================
    # Perplexity Chat Integration
    # =========================================================================
    # These methods allow direct interaction with Perplexity's chat interface.
    # Requires: View > Developer > Allow JavaScript from Apple Events
    # =========================================================================

    def ask_perplexity(
        self, question: str, wait_for_response: bool = True, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Send a question to Perplexity and optionally wait for response.

        This method navigates to perplexity.ai (if needed), types your question
        into the chat input, and submits it.

        IMPORTANT: Requires enabling JavaScript from Apple Events in Comet:
        View > Developer > Allow JavaScript from Apple Events

        Args:
            question: The question to ask Perplexity
            wait_for_response: If True, wait for and return the response
            timeout: Maximum seconds to wait for response (default: 30)

        Returns:
            Dictionary with:
                - success: bool
                - question: str (the question asked)
                - response: str (if wait_for_response=True)
                - error: str (if failed)

        Example:
            >>> comet = Comet()
            >>> result = comet.ask_perplexity("What is the capital of France?")
            >>> print(result['response'])
            'The capital of France is Paris...'
        """
        import time

        # Get or create a Perplexity tab
        tab = self._get_or_create_perplexity_tab()
        if tab is None:
            return {"success": False, "error": "Could not access Perplexity tab"}

        # Type and submit the question
        submit_result = self._submit_perplexity_question(tab, question)
        if not submit_result.get("success"):
            return submit_result

        if not wait_for_response:
            return {"success": True, "question": question, "response": None}

        # Wait for and extract the response
        response = self._wait_for_perplexity_response(tab, timeout)
        return {"success": True, "question": question, "response": response}

    def _get_or_create_perplexity_tab(self) -> Optional[CometTab]:
        """Get existing Perplexity tab or navigate to perplexity.ai."""
        if not self.windows:
            return None

        window = self.windows[0]
        tab = window.active_tab

        # Check if already on Perplexity
        current_url = tab.url
        if "perplexity.ai" in current_url:
            return tab

        # Navigate to Perplexity
        tab.url = "https://www.perplexity.ai/"

        # Wait for page to load
        import time

        for _ in range(10):
            time.sleep(0.5)
            if not tab.loading:
                break

        return tab

    def _submit_perplexity_question(
        self, tab: CometTab, question: str
    ) -> Dict[str, Any]:
        """Type question into Perplexity chat and click submit."""
        import time

        # First clear any existing content
        clear_js = """
        (function() {
            var editable = document.querySelector('[contenteditable="true"]');
            if (editable) {
                editable.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
            }
        })()
        """
        try:
            tab.execute(clear_js)
        except Exception:
            pass

        time.sleep(0.2)

        # Type the new question
        type_js = f"""
        (function() {{
            var editable = document.querySelector('[contenteditable="true"]');
            if (!editable) {{
                return JSON.stringify({{success: false, error: 'No chat input found'}});
            }}

            editable.focus();
            document.execCommand('insertText', false, {json.dumps(question)});

            // Trigger events for React
            ['input', 'change', 'keyup'].forEach(function(eventType) {{
                var event = new Event(eventType, {{ bubbles: true, cancelable: true }});
                editable.dispatchEvent(event);
            }});

            return JSON.stringify({{success: true, typed: editable.innerText}});
        }})()
        """

        try:
            result = tab.execute(type_js)
            type_result = json.loads(result) if result else {}
            if not type_result.get("success"):
                return {"success": False, "error": type_result.get("error", "Failed to type")}
        except Exception as e:
            return {"success": False, "error": f"Type error: {e}"}

        time.sleep(0.3)

        # Click submit
        submit_js = """
        (function() {
            var submitBtn = document.querySelector('button[aria-label="Submit"]');
            if (!submitBtn) {
                return JSON.stringify({success: false, error: 'No submit button found'});
            }
            if (submitBtn.disabled) {
                return JSON.stringify({success: false, error: 'Submit button is disabled'});
            }
            submitBtn.click();
            return JSON.stringify({success: true});
        })()
        """

        try:
            result = tab.execute(submit_js)
            return json.loads(result) if result else {"success": False, "error": "No result"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _wait_for_perplexity_response(
        self, tab: CometTab, timeout: float = 30.0
    ) -> Optional[str]:
        """Wait for Perplexity to generate a response and extract it."""
        import time

        start_time = time.time()

        # Wait a moment for the response to start
        time.sleep(2)

        extract_response_js = """
        (function() {
            // Look for prose/markdown content (Perplexity's response format)
            var proseElements = document.querySelectorAll('.prose');
            if (proseElements.length > 0) {
                // Get the last prose element (most recent response)
                var lastProse = proseElements[proseElements.length - 1];
                return lastProse.innerText;
            }

            // Fallback: look for any response-like content
            var main = document.querySelector('main');
            if (main) {
                // Find text that looks like a response
                var paragraphs = main.querySelectorAll('p');
                var text = [];
                for (var i = 0; i < paragraphs.length; i++) {
                    var p = paragraphs[i].innerText.trim();
                    if (p.length > 50) {
                        text.push(p);
                    }
                }
                if (text.length > 0) {
                    return text.join('\\n\\n');
                }
            }

            return null;
        })()
        """

        last_response = None
        stable_count = 0

        while time.time() - start_time < timeout:
            try:
                response = tab.execute(extract_response_js)
                if response and response != last_response:
                    last_response = response
                    stable_count = 0
                elif response == last_response:
                    stable_count += 1
                    # Response is stable for 3 checks = done
                    if stable_count >= 3:
                        return response
            except Exception:
                pass

            time.sleep(1)

        return last_response

    def get_perplexity_chat_input(self) -> Optional[str]:
        """Get the current text in Perplexity's chat input.

        Returns:
            Current input text, or None if not on Perplexity
        """
        if not self.windows:
            return None

        tab = self.windows[0].active_tab
        if "perplexity.ai" not in tab.url:
            return None

        js = """
        (function() {
            var editable = document.querySelector('[contenteditable="true"]');
            return editable ? editable.innerText : null;
        })()
        """

        try:
            return tab.execute(js)
        except Exception:
            return None

    def clear_perplexity_chat_input(self) -> bool:
        """Clear the Perplexity chat input.

        Returns:
            True if successful, False otherwise
        """
        if not self.windows:
            return False

        tab = self.windows[0].active_tab
        if "perplexity.ai" not in tab.url:
            return False

        js = """
        (function() {
            var editable = document.querySelector('[contenteditable="true"]');
            if (editable) {
                editable.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
                return true;
            }
            return false;
        })()
        """

        try:
            result = tab.execute(js)
            return result == "true" or result is True
        except Exception:
            return False

    def __repr__(self) -> str:
        try:
            return f"<Comet: {self.name} v{self.version}>"
        except Exception:
            return "<Comet: (not running)>"
