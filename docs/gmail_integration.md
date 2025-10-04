# Gmail API Integration for rdhyee_utils

This module provides a comprehensive Gmail API wrapper that makes it easy to send professional HTML emails with embedded images and attachments.

## Features

- ✅ **Easy Authentication**: Automatic credential management
- ✅ **HTML Email Support**: Rich HTML emails with embedded CSS
- ✅ **Embedded Images**: Support for inline images with Content-ID references
- ✅ **File Attachments**: Easy attachment handling
- ✅ **Professional Templates**: Built-in professional email templates
- ✅ **Improved Headers**: Reduced Gmail authentication warnings
- ✅ **Type Hints**: Full type annotation support
- ✅ **Message Management**: List, search, and retrieve emails

## Quick Start

### Basic Setup

```python
from rdhyee_utils.mail import get_gmail_service

# Initialize Gmail service with default scopes
gmail = get_gmail_service()

# Get profile information
profile = gmail.get_profile()
print(f"Connected as: {profile['emailAddress']}")
```

### Send Simple HTML Email

```python
# Send a basic HTML email
result = gmail.send_html_email(
    to_email="recipient@example.com",
    subject="Hello from rdhyee_utils!",
    html_content="<h1>Hello!</h1><p>This is a test email.</p>"
)

print(f"Email sent! Message ID: {result['id']}")
```

### Send Professional Email with Images

```python
from rdhyee_utils.google_apis.gmail import GmailService

# Create a test image
test_image = GmailService.create_test_image(
    width=300, 
    height=150, 
    text="Hello World!",
    background_color='lightblue'
)

# Create professional HTML content
content = """
<p>Welcome to our service!</p>
<div class="highlight">
    <h3>Features:</h3>
    <ul>
        <li>Professional styling</li>
        <li>Embedded images</li>
        <li>Custom templates</li>
    </ul>
</div>
<div class="image-container">
    <img src="cid:welcome_image" alt="Welcome">
</div>
"""

# Create professional template
html_email = GmailService.create_professional_html_template(
    title="Welcome!",
    content=content,
    primary_color='#3498db',
    accent_color='#e74c3c'
)

# Send email with embedded image
result = gmail.send_html_email(
    to_email="recipient@example.com",
    subject="Welcome to Our Service!",
    html_content=html_email,
    images={'welcome_image': test_image}
)
```

### Advanced Features

```python
# List recent messages
messages = gmail.list_messages(max_results=10)

# Search for specific emails
search_results = gmail.list_messages(
    query="from:example@gmail.com subject:important"
)

# Get message details
message = gmail.get_message(messages[0]['id'])

# List all labels
labels = gmail.list_labels()
```

## API Reference

### GmailService Class

#### Core Methods

- `get_profile()` - Get Gmail profile information
- `list_labels()` - Get all Gmail labels
- `list_messages(query=None, max_results=100)` - List messages
- `get_message(message_id, format='full')` - Get specific message
- `send_email(raw_message)` - Send raw email
- `send_html_email(...)` - Send HTML email (recommended)

#### Email Creation Methods

- `create_html_email(...)` - Create HTML email with attachments
- `create_professional_html_template(...)` - Professional email template
- `create_test_image(...)` - Generate test images programmatically

### Convenience Functions

- `get_gmail_service(credentials_file='gmail.json')` - Get configured Gmail service

## Configuration

### Default Scopes

The module uses these Gmail API scopes by default:
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/gmail.send` - Send emails  
- `https://www.googleapis.com/auth/gmail.modify` - Modify emails (labels, etc.)

### Custom Scopes

```python
custom_scopes = [
    'https://www.googleapis.com/auth/gmail.send'  # Send-only
]

gmail = get_gmail_service(
    credentials_file_name='gmail_send_only.json',
    scopes=custom_scopes
)
```

## Dependencies

- `google-auth`
- `google-auth-oauthlib` 
- `google-auth-httplib2`
- `google-api-python-client`
- `Pillow` (for image generation)

## Setup

1. **Create Google Cloud Project**: Set up a project in Google Cloud Console
2. **Enable Gmail API**: Enable the Gmail API for your project
3. **Create Credentials**: Download OAuth2 credentials as `client_secret.json`
4. **Place Credentials**: Put the file in `~/.credentials/client_secret.json`
5. **First Run**: The module will guide you through OAuth flow on first use

## Examples

See `examples/gmail_demo.py` for a complete demonstration of all features.

## Error Handling

The module includes proper error handling and informative error messages. Common issues:

- **Authentication**: Ensure credentials are properly set up
- **Scopes**: Make sure you have the required scopes enabled
- **Quotas**: Gmail API has rate limits and daily quotas
- **Large Attachments**: Gmail has size limits for attachments

## Contributing

This is part of the larger `rdhyee_utils` package. For issues and contributions, please use the main repository.
