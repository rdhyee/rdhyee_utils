#!/usr/bin/env python3
import sys
import base64
import re
from pathlib import Path

# Add rdhyee_utils to path
current_dir = Path(__file__).parent
rdhyee_utils_dir = current_dir.parent / "rdhyee_utils"
if rdhyee_utils_dir.exists():
    sys.path.insert(0, str(rdhyee_utils_dir.parent))

from rdhyee_utils.mail import get_gmail_service

def decode_email_body(msg_payload):
    body = ''
    if 'parts' in msg_payload:
        for part in msg_payload['parts']:
            if part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    body_data = part['body']['data']
                    body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    break
            elif part['mimeType'] == 'text/html' and not body:
                if 'data' in part['body']:
                    body_data = part['body']['data']
                    html_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    body = re.sub(r'<[^>]+>', '', html_body)
    else:
        if msg_payload['mimeType'] in ['text/plain', 'text/html']:
            if 'data' in msg_payload['body']:
                body_data = msg_payload['body']['data']
                body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                if msg_payload['mimeType'] == 'text/html':
                    body = re.sub(r'<[^>]+>', '', body)
    return body

def main():
    try:
        gmail = get_gmail_service()
        messages = gmail.list_messages(query='from:twwalbanyberkeley@gmail.com in:inbox', max_results=4)
        
        with open('email_analysis.txt', 'w', encoding='utf-8') as f:
            f.write(f"Found {len(messages)} messages from twwalbanyberkeley@gmail.com\n")
            f.write("=" * 80 + "\n\n")
            
            for i, message in enumerate(messages):
                msg = gmail.get_message(message['id'], msg_format='full')
                headers = {h['name']: h['value'] for h in msg['payload']['headers']}
                
                f.write(f"MESSAGE {i+1}\n")
                f.write(f"Subject: {headers.get('Subject', 'No Subject')}\n")
                f.write(f"From: {headers.get('From', 'Unknown')}\n")
                f.write(f"Date: {headers.get('Date', 'Unknown')}\n")
                f.write("=" * 60 + "\n")
                
                body = decode_email_body(msg['payload'])
                f.write("EMAIL BODY:\n")
                f.write("-" * 40 + "\n")
                f.write(body)
                f.write("\n" + "-" * 40 + "\n")
                f.write("EMAIL BODY (repr):\n")
                f.write(repr(body))
                f.write("\n\n" + "=" * 80 + "\n\n")
        
        print("Analysis saved to email_analysis.txt")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
