"""
SDEF Parser - Extract and parse macOS Scripting Definition files.

Provides structured access to AppleScript dictionaries for any macOS application.
"""

import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def to_snake_case(name: str) -> str:
    """Convert AppleScript name to Python snake_case.

    Examples:
        "active tab" -> "active_tab"
        "isPinned" -> "is_pinned"
        "URL" -> "url"
        "go back" -> "go_back"
    """
    # Replace spaces with underscores
    name = name.replace(" ", "_").replace("-", "_")

    # Handle camelCase -> snake_case
    # Insert underscore before uppercase letters
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)

    # Handle consecutive uppercase (e.g., URL -> url, not u_r_l)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)

    return name.lower()


def sdef_type_to_python(sdef_type: str) -> str:
    """Map SDEF types to Python type hints.

    Args:
        sdef_type: SDEF type string (e.g., "text", "integer", "boolean")

    Returns:
        Python type hint string
    """
    type_map = {
        "text": "str",
        "string": "str",
        "integer": "int",
        "number": "float",
        "real": "float",
        "boolean": "bool",
        "list": "list",
        "record": "dict",
        "file": "Path",
        "specifier": "Any",
        "type": "type",
        "any": "Any",
        "rectangle": "tuple[int, int, int, int]",
        "location specifier": "Any",
    }
    return type_map.get(sdef_type.lower(), "Any")


@dataclass
class SDEFProperty:
    """Represents a property in an SDEF class."""

    name: str
    code: str
    type: str
    access: str  # "r", "rw", or "w"
    description: str
    cocoa_key: Optional[str] = None

    @property
    def python_name(self) -> str:
        return to_snake_case(self.name)

    @property
    def python_type(self) -> str:
        return sdef_type_to_python(self.type)

    @property
    def is_readonly(self) -> bool:
        return self.access == "r"


@dataclass
class SDEFElement:
    """Represents an element (child collection) in an SDEF class."""

    type: str
    description: str
    access: str
    cocoa_key: Optional[str] = None

    @property
    def python_name(self) -> str:
        # Elements are typically plural, keep as-is
        return to_snake_case(self.type)


@dataclass
class SDEFParameter:
    """Represents a parameter in an SDEF command."""

    name: str
    code: str
    type: str
    description: str
    optional: bool = False
    cocoa_key: Optional[str] = None

    @property
    def python_name(self) -> str:
        return to_snake_case(self.name)

    @property
    def python_type(self) -> str:
        return sdef_type_to_python(self.type)


@dataclass
class SDEFCommand:
    """Represents a command in an SDEF dictionary."""

    name: str
    code: str
    description: str
    suite: str
    direct_parameter: Optional[SDEFParameter] = None
    parameters: list[SDEFParameter] = field(default_factory=list)
    result_type: Optional[str] = None
    cocoa_class: Optional[str] = None

    @property
    def python_name(self) -> str:
        return to_snake_case(self.name)

    @property
    def python_result_type(self) -> str:
        if self.result_type:
            return sdef_type_to_python(self.result_type)
        return "None"


@dataclass
class SDEFClass:
    """Represents a class in an SDEF dictionary."""

    name: str
    code: str
    description: str
    suite: str
    plural: Optional[str] = None
    extends: Optional[str] = None
    properties: list[SDEFProperty] = field(default_factory=list)
    elements: list[SDEFElement] = field(default_factory=list)
    responds_to: list[str] = field(default_factory=list)
    cocoa_class: Optional[str] = None

    @property
    def python_name(self) -> str:
        # Class names should be PascalCase
        words = self.name.replace("-", " ").split()
        return "".join(word.capitalize() for word in words)


class SDEFParser:
    """Parse and introspect SDEF (Scripting Definition) files.

    Extracts the AppleScript dictionary from a macOS application and
    provides structured access to its commands, classes, and properties.

    Example:
        >>> parser = SDEFParser("/Applications/Dia.app")
        >>> parser.app_name
        'Dia'
        >>> parser.commands
        [SDEFCommand(name='focus', ...), ...]
        >>> parser.classes
        [SDEFClass(name='application', ...), SDEFClass(name='window', ...), ...]
    """

    def __init__(self, app_path: str | Path):
        """Initialize parser for an application.

        Args:
            app_path: Path to the .app bundle (e.g., "/Applications/Dia.app")
        """
        self.app_path = Path(app_path)
        self._sdef_xml: Optional[str] = None
        self._root: Optional[ET.Element] = None
        self._commands: Optional[list[SDEFCommand]] = None
        self._classes: Optional[list[SDEFClass]] = None
        self._suites: Optional[list[str]] = None

    @property
    def app_name(self) -> str:
        """Application name from bundle path."""
        return self.app_path.stem

    @property
    def sdef_xml(self) -> str:
        """Raw SDEF XML content."""
        if self._sdef_xml is None:
            self._sdef_xml = self._extract_sdef()
        return self._sdef_xml

    @property
    def root(self) -> ET.Element:
        """Parsed XML root element."""
        if self._root is None:
            self._root = ET.fromstring(self.sdef_xml)
        return self._root

    def _extract_sdef(self) -> str:
        """Extract SDEF from application using sdef command."""
        try:
            result = subprocess.run(
                ["sdef", str(self.app_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to extract SDEF from {self.app_path}: {e.stderr}"
            ) from e

    @property
    def suites(self) -> list[str]:
        """List of suite names in the dictionary."""
        if self._suites is None:
            self._suites = [
                suite.get("name", "")
                for suite in self.root.findall(".//suite")
            ]
        return self._suites

    @property
    def commands(self) -> list[SDEFCommand]:
        """All commands defined in the SDEF."""
        if self._commands is None:
            self._commands = self._parse_commands()
        return self._commands

    @property
    def classes(self) -> list[SDEFClass]:
        """All classes defined in the SDEF."""
        if self._classes is None:
            self._classes = self._parse_classes()
        return self._classes

    def _parse_commands(self) -> list[SDEFCommand]:
        """Parse all commands from SDEF."""
        commands = []

        for suite in self.root.findall(".//suite"):
            suite_name = suite.get("name", "")

            for cmd in suite.findall("command"):
                command = SDEFCommand(
                    name=cmd.get("name", ""),
                    code=cmd.get("code", ""),
                    description=cmd.get("description", ""),
                    suite=suite_name,
                )

                # Parse cocoa class
                cocoa = cmd.find("cocoa")
                if cocoa is not None:
                    command.cocoa_class = cocoa.get("class")

                # Parse direct parameter
                direct_param = cmd.find("direct-parameter")
                if direct_param is not None:
                    command.direct_parameter = SDEFParameter(
                        name="direct",
                        code="",
                        type=direct_param.get("type", "any"),
                        description=direct_param.get("description", ""),
                    )

                # Parse other parameters
                for param in cmd.findall("parameter"):
                    cocoa_key = None
                    cocoa_elem = param.find("cocoa")
                    if cocoa_elem is not None:
                        cocoa_key = cocoa_elem.get("key")

                    command.parameters.append(
                        SDEFParameter(
                            name=param.get("name", ""),
                            code=param.get("code", ""),
                            type=param.get("type", "any"),
                            description=param.get("description", ""),
                            optional=param.get("optional", "no") == "yes",
                            cocoa_key=cocoa_key,
                        )
                    )

                # Parse result type
                result = cmd.find("result")
                if result is not None:
                    command.result_type = result.get("type")

                commands.append(command)

        return commands

    def _parse_classes(self) -> list[SDEFClass]:
        """Parse all classes from SDEF."""
        classes = []

        for suite in self.root.findall(".//suite"):
            suite_name = suite.get("name", "")

            # Parse regular classes
            for cls in suite.findall("class"):
                classes.append(self._parse_class(cls, suite_name))

            # Parse class extensions
            for ext in suite.findall("class-extension"):
                # Class extensions add to existing classes
                classes.append(self._parse_class(ext, suite_name, is_extension=True))

        return classes

    def _parse_class(
        self, cls: ET.Element, suite_name: str, is_extension: bool = False
    ) -> SDEFClass:
        """Parse a single class element."""
        sdef_class = SDEFClass(
            name=cls.get("name", "") if not is_extension else cls.get("extends", ""),
            code=cls.get("code", ""),
            description=cls.get("description", ""),
            suite=suite_name,
            plural=cls.get("plural"),
            extends=cls.get("extends"),
        )

        # Parse cocoa class
        cocoa = cls.find("cocoa")
        if cocoa is not None:
            sdef_class.cocoa_class = cocoa.get("class")

        # Parse properties
        for prop in cls.findall("property"):
            cocoa_key = None
            cocoa_elem = prop.find("cocoa")
            if cocoa_elem is not None:
                cocoa_key = cocoa_elem.get("key")

            sdef_class.properties.append(
                SDEFProperty(
                    name=prop.get("name", ""),
                    code=prop.get("code", ""),
                    type=prop.get("type", "any"),
                    access=prop.get("access", "rw"),
                    description=prop.get("description", ""),
                    cocoa_key=cocoa_key,
                )
            )

        # Parse elements
        for elem in cls.findall("element"):
            cocoa_key = None
            cocoa_elem = elem.find("cocoa")
            if cocoa_elem is not None:
                cocoa_key = cocoa_elem.get("key")

            sdef_class.elements.append(
                SDEFElement(
                    type=elem.get("type", ""),
                    description=elem.get("description", ""),
                    access=elem.get("access", "rw"),
                    cocoa_key=cocoa_key,
                )
            )

        # Parse responds-to
        for resp in cls.findall("responds-to"):
            sdef_class.responds_to.append(resp.get("command", ""))

        return sdef_class

    def get_command(self, name: str) -> Optional[SDEFCommand]:
        """Get a command by name."""
        for cmd in self.commands:
            if cmd.name == name or cmd.python_name == name:
                return cmd
        return None

    def get_class(self, name: str) -> Optional[SDEFClass]:
        """Get a class by name."""
        for cls in self.classes:
            if cls.name == name or cls.python_name == name:
                return cls
        return None

    def summary(self) -> str:
        """Return a human-readable summary of the SDEF."""
        lines = [
            f"SDEF Summary for {self.app_name}",
            "=" * 50,
            f"Suites: {', '.join(self.suites)}",
            "",
            f"Commands ({len(self.commands)}):",
        ]

        for cmd in self.commands:
            params = ", ".join(
                f"{p.python_name}: {p.python_type}" for p in cmd.parameters
            )
            result = f" -> {cmd.python_result_type}" if cmd.result_type else ""
            lines.append(f"  - {cmd.python_name}({params}){result}")

        lines.append("")
        lines.append(f"Classes ({len(self.classes)}):")

        for cls in self.classes:
            lines.append(f"  - {cls.python_name}")
            for prop in cls.properties:
                ro = " (readonly)" if prop.is_readonly else ""
                lines.append(f"      .{prop.python_name}: {prop.python_type}{ro}")
            for elem in cls.elements:
                lines.append(f"      [{elem.python_name}]  # collection")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"SDEFParser({self.app_path!r})"
