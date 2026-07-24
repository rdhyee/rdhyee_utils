#!/usr/bin/env python3
"""
Demo: Comet (Perplexity) Application Control

Shows how to interact with Perplexity's Comet macOS app via Python.
Comet has Chromium-based features including JavaScript execution.
"""

import json
from rdhyee_utils.applescript_bridge import Comet


def main():
    print("=" * 60)
    print("Comet (Perplexity) Application Demo")
    print("=" * 60)

    try:
        # Connect to Comet
        comet = Comet()
        print(f"\nConnected to: {comet}")
        print(f"Name: {comet.name}")
        print(f"Version: {comet.version}")
        print(f"Frontmost: {comet.frontmost}")

        # List windows
        windows = comet.windows
        print(f"\nWindows ({len(windows)}):")

        for window in windows:
            print(f"\n  Window: {window.name}")
            print(f"  ID: {window.id}")
            print(f"  Mode: {window.mode}")
            print(f"  Bounds: {window.bounds}")

            # List tabs in window
            tabs = window.tabs
            print(f"  Tabs ({len(tabs)}):")

            for tab in tabs:
                loading = " (loading)" if tab.loading else ""
                print(f"    - {tab.title}{loading}")
                print(f"      URL: {tab.url}")

            # Active tab info
            active = window.active_tab
            print(f"\n  Active tab: {active.title}")

        # Get all tabs across windows
        all_tabs = comet.get_all_tabs()
        print(f"\nTotal tabs: {len(all_tabs)}")

        # JavaScript execution demo
        if windows and windows[0].tabs:
            tab = windows[0].active_tab
            print(f"\n--- JavaScript Demo on '{tab.title}' ---")

            # Get page title
            title = tab.execute("document.title")
            print(f"document.title: {title}")

            # Get URL
            url = tab.execute("window.location.href")
            print(f"window.location.href: {url}")

            # Get visible text (truncated)
            # Uncomment to try:
            # text = tab.execute("document.body.innerText.substring(0, 200)")
            # print(f"Page text (first 200 chars): {text}")

            # Extract structured data
            # Example: get all links
            # links_js = """
            # JSON.stringify(
            #     Array.from(document.querySelectorAll('a'))
            #         .slice(0, 5)
            #         .map(a => ({text: a.textContent.trim(), href: a.href}))
            # )
            # """
            # links = tab.execute_json(links_js)
            # print(f"First 5 links: {json.dumps(links, indent=2)}")

    except ImportError as e:
        print(f"\nError: {e}")
        print("Install appscript: pip install appscript")
    except Exception as e:
        print(f"\nError: {e}")
        print("Is Comet running?")


if __name__ == "__main__":
    main()
