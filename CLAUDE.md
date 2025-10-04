# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`rdhyee_utils` is a personal Python utilities library containing platform-specific and API-specific helpers for macOS automation, Google APIs, and general development tasks. Current version: 0.1.15.

## Development Commands

### Installation and Setup
```bash
# Install in development mode
pip install -e .

# Build distribution
python setup.py sdist bdist_wheel
```

### Testing
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_base.py

# Run specific test module
python -m pytest tests/pandoc/test_pandoc.py
python -m pytest tests/google_apis/test_google_apis.py
```

### Running Examples
```bash
# Gmail examples require Google API credentials in ~/.credentials/
op run -- python examples/gmail_demo.py
op run -- python examples/simple_email_reader.py

# Use 1Password for secret management when running examples
```

## Architecture

### Module Organization

The codebase is organized as a collection of independent utility modules:

```
rdhyee_utils/
├── __init__.py              # Core utilities: grouper, singleton, nowish_tz, execute_command
├── google_apis/             # Google API wrappers
│   ├── __init__.py          # Credentials, DriveService, SheetsService, A1Utils
│   └── gmail.py             # GmailService for email operations
├── mail/                    # Gmail convenience wrapper
│   └── __init__.py          # get_gmail_service() helper
├── bike/                    # Bike outliner automation (macOS)
│   └── __init__.py          # Bike class, BikeDocument, BikeRow wrappers
├── clipboard/               # Clipboard utilities (macOS)
├── pandoc/                  # Pandoc conversion utilities
├── safari/                  # Safari browser automation (macOS)
├── google_chrome/           # Chrome automation utilities (macOS)
├── selenium/                # Selenium helpers
├── aws/                     # AWS utilities
└── tail_recurse/            # Tail recursion utilities
```

### Key Architectural Patterns

**1. Google API Authentication**
- Centralized credential management via `google_apis.get_credentials()`
- Credentials stored in `~/.credentials/` directory
- OAuth flow with automatic token refresh
- Client secrets expected at `~/.credentials/client_secret.json`

**2. Service Wrapper Pattern**
- Each Google API has a service class (DriveService, SheetsService, GmailService)
- Services initialized with credentials: `service = GmailService(credentials)`
- Convenience functions provided in specialized modules (e.g., `mail.get_gmail_service()`)

**3. macOS Automation via AppleScript/appscript**
- Bike module uses `appscript` library for macOS automation
- BikeDocument/BikeRow wrappers provide Pythonic interface to raw appscript objects
- Pattern: Wrapper classes hold both the parent app reference and raw objects

**4. Platform-Specific Code**
- Clipboard, Safari, Chrome, and Bike modules are macOS-specific
- Use conditional imports or platform checks when needed

## Critical Implementation Details

### Google API Services

**GmailService** (`google_apis/gmail.py`):
- Full-featured Gmail API wrapper with HTML email support
- `send_html_email()`: Send HTML emails with embedded images and attachments
- `create_professional_html_template()`: Pre-built professional email templates
- `create_test_image()`: Generate test images programmatically
- Images embedded using Content-ID (cid:) references
- Proper RFC-compliant headers to reduce authentication warnings

**SheetsService** (`google_apis/__init__.py`):
- `get_values()`: Retrieve cell values with flexible rendering options
- `get_values_as_dict()`: Parse sheets with headers into OrderedDict
- A1Utils: Convert between column letters and numbers

**DriveService** (`google_apis/__init__.py`):
- `folders_by_name()`, `item_by_name()`: Search for items
- `move_file_to_folder()`, `create_folder()`, `delete_file()`: File operations

### Bike Outliner Integration

The Bike module provides Python control of the Bike outliner app:
- `Bike()`: Main app controller
- `BikeDocument`: Document wrapper with export capabilities
- `BikeRow`: Row wrapper with hierarchy access
- `lxml_html()` / `lxml_etree()`: Export to parsed XML/HTML structures
- `sort_rows()`: Sort child rows by custom functions

### Core Utilities

`execute_command()` (`__init__.py`):
- Safely execute shell commands with proper error handling
- Accepts string or list commands
- Returns (stdout, stderr) tuple
- Use `check=True` to raise exceptions on failure

## Testing Strategy

- Tests located in `tests/` directory mirroring package structure
- Use pytest for all testing
- Test files follow `test_*.py` naming convention
- Some tests may require credentials/API access (google_apis tests)

## Common Development Patterns

### Using Gmail Service
```python
from rdhyee_utils.mail import get_gmail_service

gmail = get_gmail_service()
result = gmail.send_html_email(
    to_email="user@example.com",
    subject="Subject",
    html_content="<h1>Content</h1>"
)
```

### Using Google Sheets
```python
from rdhyee_utils.google_apis import get_credentials, SheetsService

creds = get_credentials('sheets.json', scopes=['...'])
sheets = SheetsService(creds)
data = sheets.get_values_as_dict(spreadsheet_id, 'Sheet1!A1:Z')
```

### Using Bike Outliner
```python
from rdhyee_utils.bike import Bike

bike = Bike()
doc = bike.documents[0]
root = doc.root_row
for row in root.rows:
    print(row.name, row.level)
```

## Credential Management

- **ALWAYS** use `op run --` prefix when running scripts requiring API keys
- Credentials stored in `~/.credentials/` by default
- Gmail requires `gmail.json`, Sheets requires appropriate scope credentials
- Never commit credentials to repository
