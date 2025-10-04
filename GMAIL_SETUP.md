# Gmail Module Setup Guide

## Quick Start

The Gmail functionality has been packaged into the `rdhyee_utils` library. Here's how to use it:

### 1. Basic Import and Usage

```python
# Add rdhyee_utils to your Python path (if not installed)
import sys
sys.path.insert(0, '/path/to/rdhyee_utils/parent/directory')

# Import the Gmail service
from rdhyee_utils.mail import get_gmail_service

# Initialize Gmail service (uses existing credentials)
gmail = get_gmail_service()

# Send a simple email
result = gmail.send_html_email(
    to_email="recipient@example.com",
    subject="Hello from rdhyee_utils!",
    html_content="<h1>Hello!</h1><p>This email was sent using rdhyee_utils!</p>"
)

print(f"Email sent! Message ID: {result['id']}")
```

### 2. Professional Email with Images

```python
from rdhyee_utils.google_apis.gmail import GmailService

# Create a test image
test_image = GmailService.create_test_image(
    width=250, height=120, 
    text="Welcome!", 
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
    primary_color='#3498db'
)

# Send with embedded image
result = gmail.send_html_email(
    to_email="recipient@example.com",
    subject="Welcome!",
    html_content=html_email,
    images={'welcome_image': test_image}
)
```

## File Structure

The Gmail functionality is organized as follows:

```
rdhyee_utils/
├── google_apis/
│   ├── __init__.py          # Core Google API utilities
│   └── gmail.py             # GmailService class (main functionality)
├── mail/
│   └── __init__.py          # Convenience wrapper (get_gmail_service)
├── examples/
│   ├── gmail_demo.py        # Complete demo script
│   ├── test_imports.py      # Import verification
│   └── minimal_test.py      # Basic functionality test
└── docs/
    └── gmail_integration.md # Complete documentation
```

## Key Features

- ✅ **Easy Authentication**: Reuses existing Gmail credentials
- ✅ **HTML Email Support**: Rich emails with embedded CSS
- ✅ **Embedded Images**: Content-ID based image embedding
- ✅ **Professional Templates**: Built-in styling and layouts
- ✅ **Improved Headers**: Reduced Gmail authentication warnings
- ✅ **File Attachments**: Support for email attachments
- ✅ **Message Management**: List, search, and retrieve emails
- ✅ **Type Safety**: Full type annotations
- ✅ **Error Handling**: Comprehensive error management

## Common Use Cases

### Send Notification Emails
```python
gmail = get_gmail_service()
gmail.send_html_email(
    to_email="admin@example.com",
    subject="System Alert",
    html_content="<h2>Alert</h2><p>System status update...</p>"
)
```

### Send Reports with Charts
```python
# Generate chart/image data
chart_data = create_chart()  # Your chart generation code

gmail.send_html_email(
    to_email="manager@example.com",
    subject="Weekly Report",
    html_content=report_html,
    images={'chart': chart_data}
)
```

### Automated Newsletters
```python
newsletter_html = GmailService.create_professional_html_template(
    title="Weekly Newsletter",
    content=newsletter_content,
    primary_color='#2c3e50'
)

for subscriber in subscribers:
    gmail.send_html_email(
        to_email=subscriber['email'],
        subject="Weekly Newsletter",
        html_content=newsletter_html
    )
```

## Dependencies

- `google-auth`
- `google-auth-oauthlib`
- `google-auth-httplib2`
- `google-api-python-client`
- `Pillow` (for image generation)

## Troubleshooting

### Import Errors
- Ensure `rdhyee_utils` is in your Python path
- Check that all dependencies are installed

### Authentication Issues
- Verify Gmail API credentials are set up
- Check that required scopes are enabled
- Ensure credentials file exists in `~/.credentials/`

### API Quota Issues
- Gmail API has daily quotas and rate limits
- Consider implementing retry logic for production use

## Next Steps

1. **Install in Development Environment**: Add to your project's requirements
2. **Production Deployment**: Set up proper credential management
3. **Testing**: Use the provided test scripts to verify functionality
4. **Documentation**: Reference `docs/gmail_integration.md` for complete API docs

---

**Ready to use!** The Gmail module is now a complete, production-ready package! 🚀
