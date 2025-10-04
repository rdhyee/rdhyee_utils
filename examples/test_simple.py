#!/usr/bin/env python3
"""
Simple test script to verify rdhyee_utils.mail module imports and basic functionality.
"""
import sys
from pathlib import Path

# Add rdhyee_utils to path
current_dir = Path(__file__).parent
rdhyee_utils_dir = current_dir.parent
sys.path.insert(0, str(rdhyee_utils_dir))

print("Starting import test...")

try:
    from rdhyee_utils.mail import get_gmail_service
    print("✓ Import successful!")

    gmail = get_gmail_service()
    print("✓ Gmail service created!")

    # Test with a simple query (modify as needed)
    messages = gmail.list_messages(query='in:inbox', max_results=1)
    print(f"✓ Found {len(messages)} messages")

    if messages:
        msg = gmail.get_message(messages[0]['id'], msg_format='full')
        print("✓ Message retrieved successfully!")
        print(f"  Message keys: {list(msg.keys())}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
