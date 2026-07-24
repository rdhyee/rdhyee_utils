#!/usr/bin/env python3
"""
Demo: Dia Application Control

Shows how to interact with OpenAI's Dia macOS app via Python.
"""

from rdhyee_utils.applescript_bridge import Dia


def main():
    print("=" * 60)
    print("Dia Application Demo")
    print("=" * 60)

    try:
        # Connect to Dia
        dia = Dia()
        print(f"\nConnected to: {dia}")
        print(f"Name: {dia.name}")
        print(f"Version: {dia.version}")

        # List windows
        windows = dia.windows
        print(f"\nWindows ({len(windows)}):")

        for window in windows:
            print(f"\n  Window: {window.name}")
            print(f"  ID: {window.id}")

            # List tabs in window
            tabs = window.tabs
            print(f"  Tabs ({len(tabs)}):")

            for tab in tabs:
                focused = " (focused)" if tab.is_focused else ""
                pinned = " [pinned]" if tab.is_pinned else ""
                print(f"    - {tab.title}{focused}{pinned}")
                print(f"      URL: {tab.url}")

        # Get all tabs across windows
        all_tabs = dia.get_all_tabs()
        print(f"\nTotal tabs: {len(all_tabs)}")

        # Focus first tab (if any)
        if all_tabs:
            print(f"\nFocusing first tab: {all_tabs[0].title}")
            # Uncomment to actually focus:
            # all_tabs[0].focus()

    except ImportError as e:
        print(f"\nError: {e}")
        print("Install appscript: pip install appscript")
    except Exception as e:
        print(f"\nError: {e}")
        print("Is Dia running?")


if __name__ == "__main__":
    main()
