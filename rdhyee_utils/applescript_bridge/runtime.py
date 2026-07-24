"""
AppleScript Runtime - Unified execution layer for AppleScript commands.

Provides three execution backends:
- osascript: Shell out to osascript -e (most compatible)
- py-applescript: Use the applescript package
- appscript: Use appscript for rich AppleEvent control

The runtime automatically selects the best available backend.
"""

import json
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, Type

# Try to import optional dependencies
try:
    import applescript

    HAS_APPLESCRIPT = True
except ImportError:
    HAS_APPLESCRIPT = False

try:
    from appscript import app as appscript_app
    from appscript import k as appscript_k

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False


class RuntimeBackend(Enum):
    """Available AppleScript execution backends."""

    OSASCRIPT = "osascript"  # Shell to osascript -e
    PY_APPLESCRIPT = "py_applescript"  # applescript package
    APPSCRIPT = "appscript"  # appscript package


class AppleScriptExecutor(ABC):
    """Abstract base for AppleScript executors."""

    @abstractmethod
    def execute(self, script: str) -> Any:
        """Execute AppleScript code and return result."""
        pass

    @abstractmethod
    def get_app(self, app_name: str) -> Any:
        """Get an application reference for direct manipulation."""
        pass


class OSAScriptExecutor(AppleScriptExecutor):
    """Execute AppleScript via osascript command."""

    def execute(self, script: str) -> Any:
        """Execute AppleScript via osascript -e.

        Args:
            script: AppleScript code to execute

        Returns:
            String output from the script
        """
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"AppleScript error: {e.stderr}") from e

    def execute_json(self, script: str) -> Any:
        """Execute AppleScript and parse JSON result.

        Wraps the script to return JSON for complex types.
        """
        result = self.execute(script)
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return None

    def get_app(self, app_name: str) -> "OSAScriptApp":
        """Get an application wrapper for osascript."""
        return OSAScriptApp(app_name, self)


class OSAScriptApp:
    """Wrapper for application control via osascript."""

    def __init__(self, app_name: str, executor: OSAScriptExecutor):
        self.app_name = app_name
        self.executor = executor

    def tell(self, command: str) -> Any:
        """Execute a command in tell application block."""
        script = f'tell application "{self.app_name}"\n{command}\nend tell'
        return self.executor.execute(script)

    def get_property(self, prop: str) -> Any:
        """Get an application property."""
        return self.tell(f"get {prop}")

    def __repr__(self) -> str:
        return f"OSAScriptApp({self.app_name!r})"


class PyAppleScriptExecutor(AppleScriptExecutor):
    """Execute AppleScript via py-applescript package."""

    def __init__(self):
        if not HAS_APPLESCRIPT:
            raise ImportError("applescript package not installed")

    def execute(self, script: str) -> Any:
        """Execute AppleScript via applescript package."""
        scpt = applescript.AppleScript(script)
        result = scpt.run()
        return result

    def get_app(self, app_name: str) -> Any:
        """Get an application reference."""
        # py-applescript doesn't have persistent app refs
        return PyAppleScriptApp(app_name, self)


class PyAppleScriptApp:
    """Wrapper for application control via py-applescript."""

    def __init__(self, app_name: str, executor: PyAppleScriptExecutor):
        self.app_name = app_name
        self.executor = executor

    def tell(self, command: str) -> Any:
        """Execute a command in tell application block."""
        script = f'tell application "{self.app_name}"\n{command}\nend tell'
        return self.executor.execute(script)

    def __repr__(self) -> str:
        return f"PyAppleScriptApp({self.app_name!r})"


class AppScriptExecutor(AppleScriptExecutor):
    """Execute via appscript for rich AppleEvent control."""

    def __init__(self):
        if not HAS_APPSCRIPT:
            raise ImportError("appscript package not installed")

    def execute(self, script: str) -> Any:
        """Execute raw AppleScript - falls back to osascript."""
        # appscript doesn't execute raw AppleScript, use osascript
        return OSAScriptExecutor().execute(script)

    def get_app(self, app_name: str) -> Any:
        """Get a native appscript application reference."""
        return appscript_app(app_name)


class AppleScriptRuntime:
    """Unified runtime for AppleScript execution.

    Automatically selects the best available backend:
    1. appscript (richest API, best for complex interactions)
    2. py-applescript (good middle ground)
    3. osascript (most compatible, always available)

    Example:
        >>> runtime = AppleScriptRuntime()
        >>> runtime.execute('tell application "Finder" to get name')
        'Finder'

        >>> app = runtime.app("Dia")
        >>> app.windows()  # If using appscript backend
    """

    def __init__(self, backend: Optional[RuntimeBackend] = None):
        """Initialize runtime with optional backend preference.

        Args:
            backend: Specific backend to use, or None for auto-select
        """
        self.backend = backend or self._auto_select_backend()
        self._executor = self._create_executor()

    def _auto_select_backend(self) -> RuntimeBackend:
        """Auto-select the best available backend."""
        if HAS_APPSCRIPT:
            return RuntimeBackend.APPSCRIPT
        elif HAS_APPLESCRIPT:
            return RuntimeBackend.PY_APPLESCRIPT
        else:
            return RuntimeBackend.OSASCRIPT

    def _create_executor(self) -> AppleScriptExecutor:
        """Create executor for the selected backend."""
        if self.backend == RuntimeBackend.APPSCRIPT:
            return AppScriptExecutor()
        elif self.backend == RuntimeBackend.PY_APPLESCRIPT:
            return PyAppleScriptExecutor()
        else:
            return OSAScriptExecutor()

    def execute(self, script: str) -> Any:
        """Execute raw AppleScript code.

        Args:
            script: AppleScript code to execute

        Returns:
            Result from the script execution
        """
        return self._executor.execute(script)

    def app(self, app_name: str) -> Any:
        """Get an application reference.

        The return type depends on the backend:
        - appscript: Native appscript Application object
        - py-applescript: PyAppleScriptApp wrapper
        - osascript: OSAScriptApp wrapper

        Args:
            app_name: Application name (e.g., "Dia", "Google Chrome")

        Returns:
            Application reference for the selected backend
        """
        return self._executor.get_app(app_name)

    @property
    def available_backends(self) -> list[RuntimeBackend]:
        """List of available backends on this system."""
        backends = [RuntimeBackend.OSASCRIPT]  # Always available
        if HAS_APPLESCRIPT:
            backends.append(RuntimeBackend.PY_APPLESCRIPT)
        if HAS_APPSCRIPT:
            backends.append(RuntimeBackend.APPSCRIPT)
        return backends

    def __repr__(self) -> str:
        return f"AppleScriptRuntime(backend={self.backend.value})"


# Convenience function for quick script execution
def execute_applescript(script: str, backend: Optional[RuntimeBackend] = None) -> Any:
    """Execute AppleScript code with the best available backend.

    Args:
        script: AppleScript code to execute
        backend: Optional specific backend to use

    Returns:
        Result from script execution

    Example:
        >>> execute_applescript('tell application "Finder" to get name')
        'Finder'
    """
    runtime = AppleScriptRuntime(backend=backend)
    return runtime.execute(script)


# Helper for common tell blocks
def tell_app(app_name: str, command: str) -> Any:
    """Execute a command in a tell application block.

    Args:
        app_name: Application name
        command: Command to execute

    Returns:
        Result from command execution

    Example:
        >>> tell_app("Dia", "get name of every window")
        ['Chat 1', 'Chat 2']
    """
    script = f'tell application "{app_name}"\n{command}\nend tell'
    return execute_applescript(script)
