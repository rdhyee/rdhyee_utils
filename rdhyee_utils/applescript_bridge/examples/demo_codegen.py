#!/usr/bin/env python3
"""
Demo: Code Generation from SDEF

Shows how to generate Python bindings from SDEF dictionaries:
1. Dynamic runtime generation
2. Static code generation (.py files)
"""

from rdhyee_utils.applescript_bridge import (
    SDEFParser,
    generate_bindings,
    generate_static_module,
)


def main():
    # =========================================
    # Part 1: Dynamic Binding Generation
    # =========================================
    print("=" * 60)
    print("Dynamic Binding Generation")
    print("=" * 60)

    try:
        # Generate bindings at runtime
        Dia = generate_bindings("Dia")
        print(f"\nGenerated class: {Dia}")
        print(f"Docstring: {Dia.__doc__}")

        # Use the generated class
        dia = Dia()
        print(f"\nInstance: {dia}")
        print(f"Name: {dia.name}")

    except Exception as e:
        print(f"Dynamic generation error: {e}")

    # =========================================
    # Part 2: Static Code Generation
    # =========================================
    print("\n" + "=" * 60)
    print("Static Code Generation")
    print("=" * 60)

    try:
        # Generate static Python code
        code = generate_static_module("/Applications/Dia.app")

        # Show first 50 lines
        lines = code.split("\n")
        print(f"\nGenerated {len(lines)} lines of code")
        print("\nFirst 50 lines:")
        print("-" * 40)
        for line in lines[:50]:
            print(line)
        print("-" * 40)
        print(f"... and {len(lines) - 50} more lines")

        # Optionally write to file
        # generate_static_module(
        #     "/Applications/Dia.app",
        #     output_path="./generated_dia.py"
        # )
        # print("\nWritten to ./generated_dia.py")

    except Exception as e:
        print(f"Static generation error: {e}")

    # =========================================
    # Part 3: Compare with Comet (more complex)
    # =========================================
    print("\n" + "=" * 60)
    print("Comet Static Generation Preview")
    print("=" * 60)

    try:
        code = generate_static_module("/Applications/Comet.app")
        lines = code.split("\n")
        print(f"\nGenerated {len(lines)} lines of code for Comet")

        # Count classes and methods
        class_count = sum(1 for line in lines if line.startswith("class "))
        method_count = sum(1 for line in lines if "    def " in line)
        property_count = sum(1 for line in lines if "@property" in line)

        print(f"Classes: {class_count}")
        print(f"Methods: {method_count}")
        print(f"Properties: {property_count}")

    except Exception as e:
        print(f"Comet generation error: {e}")


if __name__ == "__main__":
    main()
