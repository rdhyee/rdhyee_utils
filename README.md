# rdhyee_utils

A personal Python utilities library containing platform-specific and API-specific helpers for macOS automation, Google APIs, and general development tasks.

**Version**: 0.1.15

## Features

- **Google APIs Integration**: Gmail, Google Sheets, Google Drive wrappers
- **macOS Automation**: Bike outliner, Safari, Chrome, Clipboard utilities
- **Web Automation**: Selenium helpers
- **Cloud**: AWS EC2 management utilities
- **Core Utilities**: Command execution, iterators, timezone helpers

## Installation

```bash
# Install in development mode
pip install -e .
```

## Quick Start

```python
# Send email via Gmail
from rdhyee_utils.mail import get_gmail_service
gmail = get_gmail_service()
gmail.send_html_email(to_email="user@example.com", subject="Hello", html_content="<h1>Hi!</h1>")

# Access Google Sheets
from rdhyee_utils.google_apis import get_credentials, SheetsService
creds = get_credentials('sheets.json', scopes=['...'])
sheets = SheetsService(creds)
data = sheets.get_values_as_dict(spreadsheet_id, 'Sheet1!A1:Z')
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Development guide and architecture details
- **[GMAIL_SETUP.md](GMAIL_SETUP.md)** - Gmail API setup instructions
- **[MACOS_CLOUD.md](MACOS_CLOUD.md)** - Running macOS utilities in cloud environments

## Platform Support

- **Cross-platform**: Google APIs, core utilities, AWS, Selenium
- **macOS only**: Bike, Safari, Chrome, Clipboard modules

For running macOS-specific utilities in cloud environments, see [MACOS_CLOUD.md](MACOS_CLOUD.md).

## Testing

```bash
# Run all tests
python -m pytest

# Run specific tests
python -m pytest tests/test_base.py
```

## License

Apache 2.0

## Author

Raymond Yee (raymond.yee@gmail.com)
