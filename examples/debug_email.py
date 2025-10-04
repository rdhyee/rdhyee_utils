#!/usr/bin/env python3
"""
Simple email debugger to examine TWW email structure
"""

import sys
import base64
from pathlib import Path

# Add rdhyee_utils to path
current_dir = Path(__file__).parent
rdhyee_utils_dir = current_dir.parent / "rdhyee_utils"
if rdhyee_utils_dir.exists():
    sys.path.insert(0, str(rdhyee_utils_dir.parent))

from rdhyee_utils.mail import get_gmail_service

def decode_email_body(msg_payload):
    """Decode email body from Gmail API message payload."""
    body = ""

    if 'parts' in msg_payload:
        # Multi-part message
        for part in msg_payload['parts']:
            if part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    body_data = part['body']['data']
                    body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    break
            elif part['mimeType'] == 'text/html' and not body:
                # Fall back to HTML if no plain text
                if 'data' in part['body']:
                    body_data = part['body']['data']
                    html_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    # Simple HTML to text conversion
                    import re
                    body = re.sub(r'<[^>]+>', '', html_body)
    else:
        # Single part message
        if msg_payload['mimeType'] in ['text/plain', 'text/html']:
            if 'data' in msg_payload['body']:
                body_data = msg_payload['body']['data']
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                if msg_payload['mimeType'] == 'text/html':
                    # Simple HTML to text conversion
                    import re
                    body = re.sub(r'<[^>]+>', '', body)

    return body

def main():
    print("=== Email Structure Debugger ===")
    
    try:
        # Initialize Gmail service
        print("Initializing Gmail service...")
        gmail = get_gmail_service()
        
        # Search for emails
        search_query = "from:twwalbanyberkeley@gmail.com in:inbox"
        print(f"Searching for emails with query: {search_query}")
        
        messages = gmail.list_messages(query=search_query, max_results=5)
        print(f"Found {len(messages)} messages")
        
        if not messages:
            print("No messages found.")
            return
        
        # Examine the first message
        message = messages[0]
        print(f"Examining message ID: {message['id']}")
        
        # Get full message content
        msg = gmail.get_message(message['id'], msg_format='full')
        
        # Extract headers
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        subject = headers.get('Subject', 'No Subject')
        date = headers.get('Date', 'Unknown Date')
        from_addr = headers.get('From', 'Unknown Sender')
        
        print(f"Subject: {subject}")
        print(f"From: {from_addr}")
        print(f"Date: {date}")
        
        # Decode email body
        body = decode_email_body(msg['payload'])
        
        print("\n" + "=" * 60)
        print("EMAIL BODY CONTENT:")
        print("=" * 60)
        print(body)
        print("=" * 60)
        
        print(f"\nBody length: {len(body)} characters")
        print("First 200 characters as repr:")
        print(repr(body[:200]))
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
