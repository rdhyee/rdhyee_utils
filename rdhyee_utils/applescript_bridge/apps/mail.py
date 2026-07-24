"""
Apple Mail - Python bindings via appscript.

Provides Pythonic access to Apple Mail's AppleScript dictionary for
reading inbox messages, checking reply status, and archiving.

Key properties per message:
- subject, sender, date_received, message_id (RFC822)
- was_replied_to (IMAP \\Answered flag)
- read_status, flag_index, junk_mail_status

For Gmail accounts, archiving requires the Gmail API (removing the INBOX
label). AppleScript's `move to All Mail` is a no-op and `delete` sends
to Trash. See `gmail_batch_archive()`.

Example:
    >>> from rdhyee_utils.applescript_bridge.apps.mail import AppleMail
    >>> mail = AppleMail()
    >>> for msg in mail.inbox_messages(limit=5):
    ...     print(f"[{'R' if msg.was_replied_to else ' '}] {msg.sender[:30]} | {msg.subject[:40]}")

    >>> # Batch fetch (faster via osascript)
    >>> messages = mail.inbox_messages_fast()
    >>> replied = [m for m in messages if m.was_replied_to]

    >>> # Archive via Gmail API
    >>> rfc_ids = [m.message_id for m in messages if should_archive(m)]
    >>> count = AppleMail.gmail_batch_archive(rfc_ids)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

try:
    from appscript import app as appscript_app, k

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False


# Delimiter for batch AppleScript output. Using a sequence unlikely to
# appear in email subjects or sender names. If a field contains this
# delimiter, the record is skipped (len(parts) check catches it).
_FIELD_DELIM = "⏐⏐⏐"


@dataclass
class MailMessage:
    """A single email message from Apple Mail."""

    message_id: str  # RFC822 Message-ID (durable cross-system identifier)
    subject: str
    sender: str
    date_received: Optional[datetime] = None
    date_received_str: str = ""
    was_replied_to: bool = False
    read_status: bool = True
    flag_index: int = -1
    mailbox_name: str = ""
    # Internal Apple Mail ID (for appscript operations — NOT durable across
    # IMAP syncs; use message_id for cross-session references)
    _mail_id: Optional[int] = None


@dataclass
class ArchiveResult:
    """Result of a batch archive operation."""

    archived: int = 0
    not_found: list[str] = field(default_factory=list)  # RFC IDs not found in Gmail
    errors: list[str] = field(default_factory=list)  # Error messages


class AppleMail:
    """Python interface to Apple Mail via appscript."""

    def __init__(self):
        if not HAS_APPSCRIPT:
            raise ImportError("appscript is required: pip install appscript")
        self._app = appscript_app("Mail")

    @property
    def name(self) -> str:
        return self._app.name()

    @property
    def version(self) -> str:
        return self._app.version()

    @property
    def inbox_count(self) -> int:
        return self._app.inbox.messages.count()

    def accounts(self) -> list[dict]:
        """List mail accounts with their email addresses."""
        results = []
        for acct in self._app.accounts():
            results.append({
                "name": acct.name(),
                "emails": acct.email_addresses(),
            })
        return results

    def mailboxes(self, account_name: str) -> list[dict]:
        """List mailboxes for an account with message counts."""
        acct = self._app.accounts[account_name]
        results = []
        for mbox in acct.mailboxes():
            try:
                results.append({
                    "name": mbox.name(),
                    "count": mbox.messages.count(),
                })
            except Exception:
                pass
        return results

    def inbox_messages(self, limit: int = 20, offset: int = 0) -> list[MailMessage]:
        """Fetch inbox messages via appscript (slower, but richer).

        Args:
            limit: Max messages to fetch.
            offset: Skip first N messages (0-based).

        Returns:
            List of MailMessage objects.
        """
        messages = []
        inbox = self._app.inbox
        total = inbox.messages.count()
        start = offset + 1  # appscript is 1-based
        end = min(start + limit - 1, total)

        for i in range(start, end + 1):
            msg = inbox.messages[i]
            try:
                messages.append(MailMessage(
                    message_id=msg.message_id(),
                    subject=msg.subject(),
                    sender=msg.sender(),
                    date_received=msg.date_received(),
                    was_replied_to=msg.was_replied_to(),
                    read_status=msg.read_status(),
                    flag_index=msg.flag_index(),
                    _mail_id=msg.id(),
                ))
            except Exception:
                pass
        return messages

    def inbox_messages_fast(
        self,
        limit: Optional[int] = None,
    ) -> list[MailMessage]:
        """Fetch inbox messages via osascript batch (3-4x faster).

        Uses a single AppleScript call to fetch all messages at once,
        avoiding per-message IPC overhead.

        Args:
            limit: Max messages to fetch. None = all.

        Returns:
            List of MailMessage objects.
        """
        limit = int(limit) if limit is not None else None
        count_clause = f"set endIdx to {limit}" if limit else "set endIdx to msgCount"
        delim = _FIELD_DELIM
        script = f'''
tell application "Mail"
    set msgCount to count of messages of inbox
    {count_clause}
    if endIdx > msgCount then set endIdx to msgCount
    set output to ""
    repeat with i from 1 to endIdx
        set m to message i of inbox
        set mid to message id of m
        set subj to subject of m
        set sndr to sender of m
        set replied to was replied to of m
        set readSt to read status of m
        set flagIdx to flag index of m
        set mailId to id of m
        set output to output & mid & "{delim}" & subj & "{delim}" & sndr & "{delim}" & replied & "{delim}" & readSt & "{delim}" & flagIdx & "{delim}" & mailId & linefeed
    end repeat
    return output
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"AppleScript error: {result.stderr[:500]}")

        messages = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(delim)
            if len(parts) != 7:
                continue  # skip corrupted records (delimiter in field content)
            messages.append(MailMessage(
                message_id=parts[0].strip(),
                subject=parts[1].strip(),
                sender=parts[2].strip(),
                was_replied_to=parts[3].strip().lower() == "true",
                read_status=parts[4].strip().lower() == "true",
                flag_index=int(parts[5].strip()) if parts[5].strip().lstrip("-").isdigit() else -1,
                _mail_id=int(parts[6].strip()) if parts[6].strip().isdigit() else None,
            ))
        return messages

    def get_message_body(self, mail_id: int) -> str:
        """Get the text content of a message by its Apple Mail ID."""
        mail_id = int(mail_id)
        result = subprocess.run(
            ["osascript", "-e", f'''
tell application "Mail"
    set m to (first message of inbox whose id is {mail_id})
    return content of m
end tell
'''],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Could not get message body: {result.stderr[:200]}")
        return result.stdout

    def archive_message(self, mail_id: int, account_name: str = "raymond.yee@gmail.com") -> bool:
        """Archive a message (Gmail: remove INBOX label via Gmail API).

        NOTE: AppleScript `move to All Mail` does NOT work for Gmail archiving
        (messages are already in All Mail; the move is a no-op). Must use Gmail
        API to remove the INBOX label. This method gets the RFC822 Message-ID
        from Apple Mail, then calls Gmail API.

        Args:
            mail_id: Apple Mail internal message ID.
            account_name: Gmail account name (unused, kept for compat).

        Returns:
            True if archived successfully.
        """
        mail_id = int(mail_id)
        # Get RFC822 Message-ID from Apple Mail
        result = subprocess.run(
            ["osascript", "-e", f'''
tell application "Mail"
    set m to (first message of inbox whose id is {mail_id})
    return message id of m
end tell
'''],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return False

        rfc_id = result.stdout.strip()
        return self._gmail_archive_by_rfc_id(rfc_id)

    @staticmethod
    def _get_gmail_service():
        """Get authenticated Gmail API service, with proper token refresh.

        Uses gmail_standalone's credential helper which handles OAuth
        refresh correctly. Falls back to raw credential file if the
        helper is not available.
        """
        from googleapiclient.discovery import build
        try:
            import sys
            import importlib
            # Try importing without sys.path mutation first
            try:
                from tools.gmail_standalone import _get_gmail_credentials
            except ImportError:
                # Fall back to path-based import for standalone use
                integrations_path = "/Users/raymondyee/C/src/python-learning/integrations"
                if integrations_path not in sys.path:
                    sys.path.insert(0, integrations_path)
                from tools.gmail_standalone import _get_gmail_credentials
            creds = _get_gmail_credentials()
        except ImportError:
            # Last resort: raw credentials file
            from pathlib import Path
            from google.oauth2.credentials import Credentials
            token_file = Path.home() / ".credentials" / "gmail.json"
            creds = Credentials.from_authorized_user_file(str(token_file))
        return build("gmail", "v1", credentials=creds)

    @staticmethod
    def _gmail_archive_by_rfc_id(rfc_id: str) -> bool:
        """Remove INBOX label from a Gmail message found by RFC822 Message-ID."""
        try:
            service = AppleMail._get_gmail_service()

            results = service.users().messages().list(
                userId="me", q=f"rfc822msgid:{rfc_id}", maxResults=2
            ).execute()
            msgs = results.get("messages", [])
            if not msgs:
                return False

            # Use first match; multiple matches for same RFC ID is unusual
            service.users().messages().modify(
                userId="me", id=msgs[0]["id"],
                body={"removeLabelIds": ["INBOX"]}
            ).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def gmail_batch_archive(rfc_ids: list[str]) -> ArchiveResult:
        """Batch archive Gmail messages by RFC822 Message-IDs.

        Looks up each RFC822 Message-ID in Gmail, then removes the INBOX
        label in chunks of 1000 (Gmail API limit).

        Args:
            rfc_ids: List of RFC822 Message-ID strings.

        Returns:
            ArchiveResult with counts and details of failures.
        """
        result = ArchiveResult()
        service = AppleMail._get_gmail_service()

        # Look up Gmail IDs
        gmail_ids = []
        for rfc_id in rfc_ids:
            try:
                results = service.users().messages().list(
                    userId="me", q=f"rfc822msgid:{rfc_id}", maxResults=2
                ).execute()
                msgs = results.get("messages", [])
                if msgs:
                    gmail_ids.append(msgs[0]["id"])
                else:
                    result.not_found.append(rfc_id)
            except Exception as e:
                result.errors.append(f"Lookup failed for {rfc_id}: {e}")

        # Archive in chunks of 1000 (Gmail batchModify limit)
        chunk_size = 1000
        for i in range(0, len(gmail_ids), chunk_size):
            chunk = gmail_ids[i:i + chunk_size]
            try:
                service.users().messages().batchModify(
                    userId="me",
                    body={"ids": chunk, "removeLabelIds": ["INBOX"]}
                ).execute()
                result.archived += len(chunk)
            except Exception as e:
                result.errors.append(f"batchModify failed for chunk {i//chunk_size}: {e}")

        return result

    def mark_read(self, mail_id: int) -> bool:
        """Mark a message as read."""
        mail_id = int(mail_id)
        result = subprocess.run(
            ["osascript", "-e", f'''
tell application "Mail"
    set m to (first message of inbox whose id is {mail_id})
    set read status of m to true
end tell
'''],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0

    def mark_flagged(self, mail_id: int, flag_index: int = 0) -> bool:
        """Flag a message (0=red, 1=orange, 2=yellow, 3=green, 4=blue, -1=unflag)."""
        mail_id = int(mail_id)
        flag_index = int(flag_index)
        result = subprocess.run(
            ["osascript", "-e", f'''
tell application "Mail"
    set m to (first message of inbox whose id is {mail_id})
    set flag index of m to {flag_index}
end tell
'''],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0

    def delete_message(self, mail_id: int) -> bool:
        """Move a message to Trash.

        NOTE: For Gmail, this moves to Trash, NOT archive. To archive
        Gmail messages, use gmail_batch_archive() instead.
        """
        mail_id = int(mail_id)
        result = subprocess.run(
            ["osascript", "-e", f'''
tell application "Mail"
    set m to (first message of inbox whose id is {mail_id})
    delete m
end tell
'''],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
