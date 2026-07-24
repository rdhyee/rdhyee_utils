#!/usr/bin/env python3
"""
Demo: SDEF Parser Usage

Shows how to parse and introspect macOS application SDEF dictionaries.
"""

from rdhyee_utils.applescript_bridge import SDEFParser


def main():
    # Parse Dia's SDEF
    print("=" * 60)
    print("Parsing Dia SDEF")
    print("=" * 60)

    try:
        dia_parser = SDEFParser("/Applications/Dia.app")

        print(f"\nApp: {dia_parser.app_name}")
        print(f"Suites: {', '.join(dia_parser.suites)}")

        print("\n--- Commands ---")
        for cmd in dia_parser.commands:
            print(f"  {cmd.python_name}() - {cmd.description[:50]}...")

        print("\n--- Classes ---")
        for cls in dia_parser.classes:
            print(f"  {cls.python_name}")
            for prop in cls.properties:
                print(f"    .{prop.python_name}: {prop.python_type}")

        print("\n--- Full Summary ---")
        print(dia_parser.summary())

    except Exception as e:
        print(f"Error parsing Dia: {e}")

    # Parse Comet's SDEF
    print("\n" + "=" * 60)
    print("Parsing Comet SDEF")
    print("=" * 60)

    try:
        comet_parser = SDEFParser("/Applications/Comet.app")

        print(f"\nApp: {comet_parser.app_name}")
        print(f"Suites: {', '.join(comet_parser.suites)}")

        print("\n--- Commands (first 10) ---")
        for cmd in comet_parser.commands[:10]:
            print(f"  {cmd.python_name}() - {cmd.description[:50]}...")

        print(f"\n  ... and {len(comet_parser.commands) - 10} more commands")

        print("\n--- Classes ---")
        for cls in comet_parser.classes[:5]:
            print(f"  {cls.python_name}")

    except Exception as e:
        print(f"Error parsing Comet: {e}")


if __name__ == "__main__":
    main()
