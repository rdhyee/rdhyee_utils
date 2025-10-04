#!/usr/bin/env python3
"""
TWW Albany Berkeley Email Parser

This script finds all emails from twwalbanyberkeley@gmail.com and extracts
sign-up information from them.
"""

import sys
import re
import csv
import base64
from datetime import datetime
from pathlib import Path

# Add rdhyee_utils to path if running as standalone script
current_dir = Path(__file__).parent
rdhyee_utils_dir = current_dir.parent / "rdhyee_utils"
if rdhyee_utils_dir.exists():
    sys.path.insert(0, str(rdhyee_utils_dir.parent))

from rdhyee_utils.mail import get_gmail_service


def parse_email_content(email_body):
    """Parse the structured sign-up information from email content."""
    parsed_info = {
        'name': '',
        'email': '',
        'message': ''
    }

    # Clean up the text but preserve line breaks for pattern matching
    cleaned_text = email_body.replace('\r\n', '\n').replace('\r', '\n')
    
    # Try Weebly format first (most likely based on the CSV data)
    # Pattern: *Name*\nActual Name
    name_match = re.search(r'\*Name\*\s*\n\s*([^\n]+)', cleaned_text, re.IGNORECASE)
    if name_match:
        parsed_info['name'] = name_match.group(1).strip()
    
    # Pattern: *Your Email Address*\nemail@domain.com
    email_match = re.search(r'\*Your Email Address\*\s*\n\s*([^\s\n]+@[^\s\n]+)', cleaned_text, re.IGNORECASE)
    if email_match:
        parsed_info['email'] = email_match.group(1).strip()
    
    # Pattern: *Your Message*\nActual message content
    message_match = re.search(r'\*Your Message\*\s*\n\s*(.+?)(?=\n\s*\*|$)', cleaned_text, re.IGNORECASE | re.DOTALL)
    if message_match:
        parsed_info['message'] = message_match.group(1).strip()
    
    # Fallback: Try original format without asterisks
    if not parsed_info['name']:
        name_match = re.search(r'Name\s*\n\s*([^\n]+)', cleaned_text, re.IGNORECASE)
        if name_match:
            parsed_info['name'] = name_match.group(1).strip()
    
    if not parsed_info['email']:
        email_match = re.search(r'(?:Your )?Email(?:\s+Address)?\s*\n?\s*([^\s\n]+@[^\s\n]+)', cleaned_text, re.IGNORECASE)
        if email_match:
            parsed_info['email'] = email_match.group(1).strip()
    
    if not parsed_info['message']:
        message_match = re.search(r'(?:Your )?Message\s*\n?\s*(.+?)(?=\s*$)', cleaned_text, re.IGNORECASE | re.DOTALL)
        if message_match:
            parsed_info['message'] = message_match.group(1).strip()
    
    # Final fallback: look for any email address
    if not parsed_info['email']:
        email_fallback = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', cleaned_text)
        if email_fallback:
            parsed_info['email'] = email_fallback.group(1).strip()
    
    # Final fallback: look for name pattern (First Last)
    if not parsed_info['name']:
        name_fallback = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', cleaned_text)
        if name_fallback:
            parsed_info['name'] = name_fallback.group(1).strip()

    return parsed_info


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
                    body = re.sub(r'<[^>]+>', '', html_body)
    else:
        # Single part message
        if msg_payload['mimeType'] in ['text/plain', 'text/html']:
            if 'data' in msg_payload['body']:
                body_data = msg_payload['body']['data']
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                if msg_payload['mimeType'] == 'text/html':
                    # Simple HTML to text conversion
                    body = re.sub(r'<[^>]+>', '', body)

    return body


def extract_tww_signups():
    """Extract sign-up information from TWW Albany Berkeley emails."""

    print("🔍 TWW Albany Berkeley Email Parser")
    print("=" * 50)

    try:
        # Initialize Gmail service
        print("📧 Initializing Gmail service...")
        gmail = get_gmail_service()

        # Search for emails from twwalbanyberkeley@gmail.com in Inbox only
        search_query = "from:twwalbanyberkeley@gmail.com in:inbox"
        print(f"🔎 Searching for emails with query: {search_query}")

        messages = gmail.list_messages(query=search_query, max_results=100)
        print(f"📨 Found {len(messages)} messages from twwalbanyberkeley@gmail.com in Inbox")

        if not messages:
            print("❌ No messages found. Check that emails exist from this sender.")
            return

        # Process each message
        sign_ups = []
        processed = 0
        parsed_count = 0

        for message in messages:
            try:
                # Get full message content
                msg = gmail.get_message(message['id'], msg_format='full')

                # Extract headers for context
                headers = {h['name']: h['value'] for h in msg['payload']['headers']}
                subject = headers.get('Subject', 'No Subject')
                date = headers.get('Date', 'Unknown Date')

                print(f"\n📄 Processing: {subject[:50]}... ({date})")

                # Decode email body
                body = decode_email_body(msg['payload'])

                if body:
                    # Parse sign-up information
                    parsed_info = parse_email_content(body)

                    # Check if we found any sign-up info
                    if parsed_info['name'] or parsed_info['email']:
                        parsed_info.update({
                            'subject': subject,
                            'date': date,
                            'message_id': message['id']
                        })
                        sign_ups.append(parsed_info)
                        parsed_count += 1

                        print(f"  ✅ Extracted: {parsed_info['name']} ({parsed_info['email']})")
                    else:
                        print("  ⚠️  No sign-up info found in this email")
                else:
                    print("  ❌ Could not decode email body")

                processed += 1

            except Exception as e:
                print(f"  ❌ Error processing message {message['id']}: {e}")
                continue

        print(f"\n📊 Processing Summary:")
        print(f"   Total messages processed: {processed}")
        print(f"   Sign-ups extracted: {parsed_count}")

        if sign_ups:
            # Save to CSV file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"tww_signups_{timestamp}.csv"

            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['name', 'email', 'message', 'subject', 'date', 'message_id']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for signup in sign_ups:
                    writer.writerow(signup)

            print(f"\n💾 Saved {len(sign_ups)} sign-ups to: {csv_filename}")

            # Display sample of results
            print("\n📋 Sample Results:")
            for i, signup in enumerate(sign_ups[:5]):
                print(f"\n{i+1}. Name: {signup['name']}")
                print(f"   Email: {signup['email']}")
                print(f"   Message: {signup['message'][:100]}...")
                print(f"   Date: {signup['date']}")

            if len(sign_ups) > 5:
                print(f"\n   ... and {len(sign_ups) - 5} more entries in CSV file")

            return sign_ups
        else:
            print("❌ No sign-up information could be extracted from any emails.")
            print("   This might mean:")
            print("   - The emails don't contain the expected format")
            print("   - The parsing pattern needs adjustment")
            print("   - The emails are in a different format")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Gmail API credentials set up")
        print("2. Access to the Gmail account")
        print("3. Emails from twwalbanyberkeley@gmail.com in your inbox")


def analyze_real_email():
    """Function to examine the actual structure of TWW emails for debugging."""
    print("\n" + "=" * 50)
    print("🔍 Real Email Analysis")
    print("=" * 50)

    try:
        # Initialize Gmail service
        print("📧 Initializing Gmail service...")
        gmail = get_gmail_service()

        # Search for emails from twwalbanyberkeley@gmail.com
        search_query = "from:twwalbanyberkeley@gmail.com in:inbox"
        print(f"🔎 Searching for emails with query: {search_query}")

        messages = gmail.list_messages(query=search_query, max_results=5)
        print(f"📨 Found {len(messages)} messages")

        if not messages:
            print("❌ No messages found.")
            return

        # Examine the first message in detail
        message = messages[0]
        print(f"\n📄 Examining message ID: {message['id']}")
        
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
        
        print("\n" + "=" * 50)
        print("📧 EMAIL BODY CONTENT:")
        print("=" * 50)
        print(body)
        print("=" * 50)
        
        # Try current parsing
        print("\n🔍 Current Parser Results:")
        parsed = parse_email_content(body)
        print(f"Name: '{parsed['name']}'")
        print(f"Email: '{parsed['email']}'")
        print(f"Message: '{parsed['message']}'")

        # Show raw body for pattern analysis
        print("\n📝 Raw Body Analysis:")
        print("Length:", len(body))
        print("First 500 chars:")
        print(repr(body[:500]))

        return body

    except Exception as e:
        print(f"❌ Error analyzing email: {e}")
        return None


def analyze_sample_email():
    """Function to help analyze the structure of emails for debugging."""
    print("\n" + "=" * 50)
    print("🔍 Sample Email Analysis")
    print("=" * 50)

    # Test with the actual Weebly format found in the CSV
    weebly_sample = """
*Submitted Information:*
*Name*
Carolyn Said

*Your Email Address*
carolynsaid@gmail.com

*Your Message*
I support everything you're doing. I've come to some of the postcard parties and happy to do more.

*Join Our Mailing List?.Yes*
"""

    print("Testing with Weebly format (actual email format):")
    print("-" * 40)
    print(weebly_sample.strip())
    print("-" * 40)

    parsed = parse_email_content(weebly_sample)
    print("\nParsed results:")
    print(f"Name: '{parsed['name']}'")
    print(f"Email: '{parsed['email']}'")
    print(f"Message: '{parsed['message']}'")

    if parsed['name'] and parsed['email']:
        print("✅ Weebly format parsing successful!")
    else:
        print("❌ Weebly format parsing failed")

    # Also test original format for backwards compatibility
    original_sample = """
    Submitted Information:

    Name
    Carolyn Said

    Your Email Address
    carolynsaid@gmail.com

    Your Message
    I support everything you're doing. I've come to some of the postcard parties and happy to do more.
    """

    print("\n" + "-" * 40)
    print("Testing with original expected format:")
    print("-" * 40)
    print(original_sample.strip())
    print("-" * 40)

    parsed_original = parse_email_content(original_sample)
    print("\nParsed results:")
    print(f"Name: '{parsed_original['name']}'")
    print(f"Email: '{parsed_original['email']}'")
    print(f"Message: '{parsed_original['message']}'")

    if parsed_original['name'] and parsed_original['email']:
        print("✅ Original format parsing successful!")
    else:
        print("❌ Original format parsing failed")


if __name__ == "__main__":
    print("TWW Albany Berkeley Email Sign-up Extractor")
    print("=" * 50)

    # First, test the parsing with the sample
    analyze_sample_email()

    # Analyze a real email to see the structure
    print("\n" + "=" * 50)
    print("Analyzing real email structure...")
    analyze_real_email()

    # Run the actual extraction
    print("\n" + "=" * 50)
    print("Running full extraction...")
    extract_tww_signups()

    print("\n🎉 Script completed!")
    print("📁 Check for CSV output file with extracted sign-ups.")
