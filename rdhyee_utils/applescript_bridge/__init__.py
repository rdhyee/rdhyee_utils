"""
AppleScript Bridge - Generate Python bindings from macOS SDEF dictionaries.

This module provides:
- SDEF parsing and introspection
- Dynamic Python class generation from SDEF
- Static code generation with type hints
- Unified runtime layer for AppleScript execution

Example usage:
    from rdhyee_utils.applescript_bridge import SDEFParser, generate_bindings

    # Parse an app's SDEF
    parser = SDEFParser("/Applications/Dia.app")
    print(parser.commands)
    print(parser.classes)

    # Generate Python bindings dynamically
    Dia = generate_bindings("Dia")
    dia = Dia()
    print(dia.windows)
"""

from .sdef_parser import SDEFParser, SDEFCommand, SDEFClass, SDEFProperty
from .runtime import AppleScriptRuntime, execute_applescript
from .codegen import generate_bindings, generate_static_module
from .apps import Dia, Atlas, Comet

__all__ = [
    # SDEF parsing
    "SDEFParser",
    "SDEFCommand",
    "SDEFClass",
    "SDEFProperty",
    # Runtime
    "AppleScriptRuntime",
    "execute_applescript",
    # Code generation
    "generate_bindings",
    "generate_static_module",
    # Pre-built app bindings
    "Dia",
    "Atlas",
    "Comet",
]
