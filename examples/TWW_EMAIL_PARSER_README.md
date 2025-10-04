# TWW Albany Berkeley Email Parser

This script extracts sign-up information from emails sent by the TWW Albany Berkeley contact form (`twwalbanyberkeley@gmail.com`).

## What it does

The script searches your Gmail inbox for emails from `twwalbanyberkeley@gmail.com` and extracts structured sign-up information in this format:

```
Submitted Information:

Name
[Person's Name]

Your Email Address
[person@email.com]

Your Message
[Their message content]
```

## Usage

### 1. Run the standalone script

```bash
cd /Users/raymondyee/C/src/rdhyee_utils/examples
python tww_email_parser.py
```

The script will:
1. Test the parsing logic with a sample email
2. Ask if you want to process real emails
3. Search your Gmail for TWW emails
4. Extract sign-up information from each email
5. Save results to a CSV file named `tww_signups_YYYYMMDD_HHMMSS.csv`

### 2. Use in your own code

```python
from rdhyee_utils.mail import get_gmail_service

# Initialize Gmail service
gmail = get_gmail_service()

# Search for TWW emails
messages = gmail.list_messages(query='from:twwalbanyberkeley@gmail.com', max_results=50)

# Process and extract sign-ups (see script for full implementation)
```

## Output

The script creates a CSV file with these columns:
- `name` - Person's name
- `email` - Their email address  
- `message` - Their message/comment
- `subject` - Email subject line
- `date` - When the email was sent
- `message_id` - Gmail message ID (for reference)

## Example Output

```csv
name,email,message,subject,date,message_id
Carolyn Said,carolynsaid@gmail.com,"I support everything you're doing. I've come to some of the postcard parties and happy to do more.",Contact Form Submission,Wed 18 Dec 2024 14:30:15 -0800,abc123def456
```

## Features

- ✅ **Automated Extraction**: Finds and processes all TWW emails automatically
- ✅ **Structured Parsing**: Extracts name, email, and message using regex patterns
- ✅ **CSV Export**: Saves results in a spreadsheet-friendly format
- ✅ **Error Handling**: Continues processing even if some emails can't be parsed
- ✅ **Sample Testing**: Tests parsing logic before processing real emails
- ✅ **Gmail Integration**: Uses the rdhyee_utils Gmail module for authentication

## Prerequisites

1. **Gmail API Access**: You need Gmail API credentials set up (should already be working if you've used the other Gmail examples)
2. **TWW Emails**: Have emails from `twwalbanyberkeley@gmail.com` in your Gmail inbox
3. **Dependencies**: The rdhyee_utils package with Gmail support

## Customization

You can modify the script to:
- Change the search query (different sender, date range, etc.)
- Adjust the parsing patterns for different email formats
- Add additional data extraction fields
- Change the output format (JSON, database, etc.)

## Troubleshooting

### No emails found
- Check that you have emails from `twwalbanyberkeley@gmail.com`
- Verify Gmail API credentials are working
- Check your Gmail search manually: `from:twwalbanyberkeley@gmail.com`

### Parsing failures
- Run the script to see the sample parsing test
- If the email format has changed, update the regex patterns in `parse_email_content()`
- Check a few emails manually to see the exact format

### Permission errors
- Ensure Gmail API has the required scopes (readonly, send, modify)
- Re-authenticate if needed

## Integration

This script demonstrates how to use the rdhyee_utils Gmail module for practical email processing tasks. You can use similar patterns for:
- Processing other contact form emails
- Extracting data from newsletters
- Analyzing email patterns
- Automated email management

---

**Ready to extract your TWW sign-ups!** 📧➡️📊
