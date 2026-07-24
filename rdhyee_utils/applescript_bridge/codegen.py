"""
Code Generation - Generate Python bindings from SDEF dictionaries.

Provides:
- Dynamic runtime generation using type() and descriptors
- Static codegen that emits .py files with type hints
"""

from datetime import datetime
from pathlib import Path
from textwrap import dedent, indent
from typing import Any, Optional, Type

from .sdef_parser import SDEFClass, SDEFCommand, SDEFParser, SDEFProperty

# Try to import appscript for the preferred backend
try:
    from appscript import app as appscript_app

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False


class PropertyDescriptor:
    """Descriptor for SDEF properties that delegates to appscript."""

    def __init__(self, prop: SDEFProperty, attr_name: str):
        self.prop = prop
        self.attr_name = attr_name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        # Get the raw appscript object and call the property
        raw = getattr(obj, "_raw")
        return getattr(raw, self.attr_name)()

    def __set__(self, obj, value):
        if self.prop.is_readonly:
            raise AttributeError(f"{self.prop.name} is read-only")
        raw = getattr(obj, "_raw")
        getattr(raw, self.attr_name).set(value)


class ElementDescriptor:
    """Descriptor for SDEF elements (collections) that delegates to appscript."""

    def __init__(self, element_type: str, attr_name: str, wrapper_class: Type):
        self.element_type = element_type
        self.attr_name = attr_name
        self.wrapper_class = wrapper_class

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        raw = getattr(obj, "_raw")
        # Get the collection and wrap each item
        items = getattr(raw, self.attr_name)()
        return [self.wrapper_class(item) for item in items]


def generate_bindings(
    app_name: str,
    app_path: Optional[str] = None,
) -> Type:
    """Dynamically generate Python bindings for an application.

    Creates a class at runtime with properties and methods that
    delegate to appscript for AppleScript execution.

    Args:
        app_name: Application name (e.g., "Dia")
        app_path: Optional full path to .app bundle

    Returns:
        Generated class that wraps the application

    Example:
        >>> Dia = generate_bindings("Dia")
        >>> dia = Dia()
        >>> dia.name
        'Dia'
        >>> dia.windows
        [<DiaWindow: Chat 1>, ...]
    """
    if not HAS_APPSCRIPT:
        raise ImportError("appscript required for dynamic bindings")

    # Determine app path
    if app_path is None:
        app_path = f"/Applications/{app_name}.app"

    # Parse SDEF
    try:
        parser = SDEFParser(app_path)
    except RuntimeError:
        # App might not have SDEF, create minimal binding
        return _create_minimal_binding(app_name)

    # Find the application class
    app_class = parser.get_class("application")

    # Build the class dynamically
    class_dict = {
        "_app_name": app_name,
        "_parser": parser,
        "__doc__": f"Python bindings for {app_name} generated from SDEF.",
    }

    # Add __init__
    def __init__(self):
        self._app = appscript_app(self._app_name)
        self._raw = self._app

    class_dict["__init__"] = __init__

    # Add __repr__
    def __repr__(self):
        return f"<{self._app_name}>"

    class_dict["__repr__"] = __repr__

    # Add properties from application class
    if app_class:
        for prop in app_class.properties:
            attr_name = prop.cocoa_key or prop.python_name
            class_dict[prop.python_name] = PropertyDescriptor(prop, attr_name)

    # Create the main class
    AppClass = type(app_name, (), class_dict)

    return AppClass


def _create_minimal_binding(app_name: str) -> Type:
    """Create minimal binding for apps without SDEF."""

    class MinimalApp:
        def __init__(self):
            self._app = appscript_app(app_name)
            self._raw = self._app
            self._app_name = app_name

        @property
        def name(self) -> str:
            return self._app.name()

        @property
        def version(self) -> str:
            return self._app.version()

        @property
        def frontmost(self) -> bool:
            return self._app.frontmost()

        def __repr__(self):
            return f"<{self._app_name}>"

    MinimalApp.__name__ = app_name
    MinimalApp.__doc__ = f"Minimal Python bindings for {app_name} (no SDEF available)."
    return MinimalApp


def generate_static_module(
    app_path: str,
    output_path: Optional[str] = None,
    module_name: Optional[str] = None,
) -> str:
    """Generate a static Python module file from SDEF.

    Creates a .py file with fully typed classes that can be
    imported and used without runtime generation.

    Args:
        app_path: Path to .app bundle
        output_path: Where to write the .py file (optional)
        module_name: Module name override (defaults to app name lowercase)

    Returns:
        Generated Python code as string

    Example:
        >>> code = generate_static_module("/Applications/Dia.app")
        >>> print(code)
        # Auto-generated bindings for Dia
        ...
    """
    parser = SDEFParser(app_path)
    app_name = parser.app_name

    if module_name is None:
        module_name = app_name.lower().replace(" ", "_")

    # Start building the code
    code_lines = [
        f'"""',
        f"Auto-generated Python bindings for {app_name}.",
        f"",
        f"Generated from SDEF on {datetime.now().isoformat()}",
        f"",
        f"Usage:",
        f"    from {module_name} import {app_name}",
        f"    app = {app_name}()",
        f"    print(app.name)",
        f'"""',
        "",
        "from typing import Any, Optional, List",
        "from pathlib import Path",
        "",
        "try:",
        "    from appscript import app as appscript_app",
        "    HAS_APPSCRIPT = True",
        "except ImportError:",
        "    HAS_APPSCRIPT = False",
        "",
    ]

    # Generate wrapper classes for each SDEF class
    generated_classes = set()

    for sdef_class in parser.classes:
        if sdef_class.name in generated_classes:
            continue
        if sdef_class.name == "application":
            # Application class is special, generate last
            continue

        code_lines.extend(_generate_class_code(sdef_class, parser))
        code_lines.append("")
        generated_classes.add(sdef_class.name)

    # Generate the main application class
    app_class = parser.get_class("application")
    if app_class:
        code_lines.extend(_generate_app_class_code(app_class, parser, app_name))

    code = "\n".join(code_lines)

    # Write to file if output path specified
    if output_path:
        Path(output_path).write_text(code)

    return code


def _generate_class_code(sdef_class: SDEFClass, parser: SDEFParser) -> list[str]:
    """Generate code for a single SDEF class."""
    class_name = sdef_class.python_name
    lines = [
        f"class {class_name}:",
        f'    """',
        f"    {sdef_class.description or f'{class_name} wrapper.'}",
        f'    """',
        "",
        f"    def __init__(self, raw_obj):",
        f"        self._raw = raw_obj",
        "",
    ]

    # Generate properties
    for prop in sdef_class.properties:
        lines.extend(_generate_property_code(prop))

    # Generate __repr__
    # Try to use 'name' or 'title' property for repr
    repr_prop = None
    for p in sdef_class.properties:
        if p.name in ("name", "title"):
            repr_prop = p.python_name
            break

    if repr_prop:
        lines.extend([
            f"    def __repr__(self) -> str:",
            f"        try:",
            f"            return f'<{class_name}: {{self.{repr_prop}}}>'"
            ,
            f"        except Exception:",
            f"            return f'<{class_name}>'",
            "",
        ])
    else:
        lines.extend([
            f"    def __repr__(self) -> str:",
            f"        return f'<{class_name}>'",
            "",
        ])

    return lines


def _generate_property_code(prop: SDEFProperty) -> list[str]:
    """Generate property code for a single SDEF property."""
    attr_name = prop.cocoa_key or prop.python_name
    py_type = prop.python_type

    lines = [
        f"    @property",
        f"    def {prop.python_name}(self) -> {py_type}:",
        f'        """{prop.description or prop.name}"""',
        f"        return self._raw.{attr_name}()",
        "",
    ]

    # Add setter if not readonly
    if not prop.is_readonly:
        lines.extend([
            f"    @{prop.python_name}.setter",
            f"    def {prop.python_name}(self, value: {py_type}) -> None:",
            f"        self._raw.{attr_name}.set(value)",
            "",
        ])

    return lines


def _generate_app_class_code(
    app_class: SDEFClass,
    parser: SDEFParser,
    app_name: str,
) -> list[str]:
    """Generate the main application class code."""
    lines = [
        f"class {app_name}:",
        f'    """',
        f"    {app_class.description or f'{app_name} application wrapper.'}",
        f"",
        f"    Example:",
        f"        >>> app = {app_name}()",
        f"        >>> print(app.name)",
        f"        '{app_name}'",
        f'    """',
        "",
        f"    def __init__(self, app_name: str = '{app_name}'):",
        f"        if not HAS_APPSCRIPT:",
        f"            raise ImportError('appscript package required')",
        f"        self._app = appscript_app(app_name)",
        f"        self._raw = self._app",
        "",
    ]

    # Generate properties
    for prop in app_class.properties:
        lines.extend(_generate_property_code(prop))

    # Generate element accessors (e.g., windows, tabs)
    for elem in app_class.elements:
        elem_type = elem.type
        wrapper_class = parser.get_class(elem_type)
        wrapper_name = wrapper_class.python_name if wrapper_class else "dict"
        attr_name = elem.cocoa_key or elem.python_name

        lines.extend([
            f"    @property",
            f"    def {elem.python_name}(self) -> List[{wrapper_name}]:",
            f'        """{elem.description}"""',
            f"        raw_items = self._raw.{attr_name}()",
            f"        return [{wrapper_name}(item) for item in raw_items]",
            "",
        ])

    # Add __repr__
    lines.extend([
        f"    def __repr__(self) -> str:",
        f"        return f'<{app_name}: {{self.name}}>'",
        "",
    ])

    return lines


def generate_command_function(cmd: SDEFCommand) -> str:
    """Generate a standalone function for an SDEF command.

    Returns Python code for a function that executes the command.
    """
    # Build parameter list
    params = []
    if cmd.direct_parameter:
        params.append(f"target: {cmd.direct_parameter.python_type}")

    for param in cmd.parameters:
        default = " = None" if param.optional else ""
        params.append(f"{param.python_name}: {param.python_type}{default}")

    params_str = ", ".join(params)
    result_type = cmd.python_result_type

    # Build docstring
    doc_lines = [
        f'    """{cmd.description}',
        "",
    ]
    if cmd.direct_parameter:
        doc_lines.append(f"    Args:")
        doc_lines.append(f"        target: {cmd.direct_parameter.description}")
    for param in cmd.parameters:
        doc_lines.append(f"        {param.python_name}: {param.description}")

    if cmd.result_type:
        doc_lines.append("")
        doc_lines.append(f"    Returns:")
        doc_lines.append(f"        {result_type}")

    doc_lines.append('    """')

    # Build function
    lines = [
        f"def {cmd.python_name}({params_str}) -> {result_type}:",
        "\n".join(doc_lines),
        f"    # Implementation would call AppleScript",
        f"    pass",
    ]

    return "\n".join(lines)
