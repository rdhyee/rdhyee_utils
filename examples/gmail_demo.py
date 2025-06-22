#!/usr/bin/env python3
"""
Gmail API Demo Script

This script demonstrates how to use the new Gmail functionality in rdhyee_utils.
It shows how to send HTML emails with embedded images using the GmailService class.

Usage:
    python gmail_demo.py
"""

import sys
from pathlib import Path

# Add rdhyee_utils to path if running as standalone script
current_dir = Path(__file__).parent
rdhyee_utils_dir = current_dir.parent.parent / "rdhyee_utils"
if rdhyee_utils_dir.exists():
    sys.path.insert(0, str(rdhyee_utils_dir.parent))

from rdhyee_utils.mail import get_gmail_service
from rdhyee_utils.google_apis.gmail import GmailService


def demo_gmail_functionality():
    """Demonstrate Gmail API functionality."""
    
    print("🚀 Gmail API Demo - rdhyee_utils")
    print("=" * 50)
    
    try:
        # Get Gmail service with default scopes
        print("📧 Initializing Gmail service...")
        gmail = get_gmail_service()
        
        # Get profile information
        print("\n👤 Getting profile information...")
        profile = gmail.get_profile()
        print(f"Email: {profile['emailAddress']}")
        print(f"Total Messages: {profile['messagesTotal']:,}")
        print(f"Total Threads: {profile['threadsTotal']:,}")
        
        # List labels
        print("\n🏷️  Listing Gmail labels...")
        labels = gmail.list_labels()
        print(f"Found {len(labels)} labels:")
        for label in labels[:10]:  # Show first 10
            print(f"  - {label['name']}")
        if len(labels) > 10:
            print(f"  ... and {len(labels) - 10} more")
        
        # Create a test email
        print("\n✉️  Creating test email...")
        
        # Create test image
        test_image = GmailService.create_test_image(
            width=300, 
            height=150, 
            text="rdhyee_utils Gmail Demo",
            background_color='lightgreen'
        )
        
        # Create professional HTML content
        email_content = """
        <p>Hello! This is a demonstration of the new Gmail functionality in <strong>rdhyee_utils</strong>.</p>
        
        <div class="highlight">
            <h3>✨ Features Demonstrated:</h3>
            <ul>
                <li>✅ Gmail API authentication</li>
                <li>✅ Profile information retrieval</li>
                <li>✅ Label management</li>
                <li>✅ HTML email with embedded CSS</li>
                <li>✅ Embedded images</li>
                <li>✅ Professional email templates</li>
            </ul>
        </div>
        
        <p>Here's a programmatically generated test image:</p>
        
        <div class="image-container">
            <img src="cid:demo_image" alt="Demo Image" style="border: 2px solid #27ae60; border-radius: 5px;">
        </div>
        
        <p>The new <code>rdhyee_utils.mail</code> module makes it easy to send professional emails programmatically!</p>
        """
        
        html_email = GmailService.create_professional_html_template(
            title="rdhyee_utils Gmail Demo",
            content=email_content,
            primary_color='#27ae60',
            accent_color='#e74c3c'
        )
        
        # Prepare email data
        recipient = profile['emailAddress']  # Send to self for demo
        subject = "Gmail API Demo - rdhyee_utils Integration Test"
        images = {'demo_image': test_image}
        
        print(f"📤 Sending test email to {recipient}...")
        
        # Send the email
        result = gmail.send_html_email(
            to_email=recipient,
            subject=subject,
            html_content=html_email,
            images=images
        )
        
        print(f"✅ Email sent successfully!")
        print(f"Message ID: {result['id']}")
        print(f"Thread ID: {result['threadId']}")
        print(f"\n📬 Check your inbox for the demo email!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure you have:")
        print("1. Gmail API credentials set up")
        print("2. The correct scopes enabled")
        print("3. PIL (Pillow) installed for image generation")
        return False
    
    print("\n🎉 Demo completed successfully!")
    return True


def create_simple_email_example():
    """Show a simple email sending example."""
    
    print("\n" + "=" * 50)
    print("📝 Simple Email Example")
    print("=" * 50)
    
    # This is what user code would look like:
    example_code = '''
from rdhyee_utils.mail import get_gmail_service

# Initialize Gmail service
gmail = get_gmail_service()

# Send a simple HTML email
result = gmail.send_html_email(
    to_email="recipient@example.com",
    subject="Hello from rdhyee_utils!",
    html_content="<h1>Hello!</h1><p>This is a test email.</p>"
)

print(f"Email sent! Message ID: {result['id']}")
'''
    
    print("Here's how easy it is to send emails with rdhyee_utils:")
    print(example_code)


if __name__ == "__main__":
    success = demo_gmail_functionality()
    
    if success:
        create_simple_email_example()
    
    print("\n" + "=" * 50)
    print("📚 For more information, see the rdhyee_utils documentation")
    print("🔗 GitHub: https://github.com/rdhyee/rdhyee_utils")
