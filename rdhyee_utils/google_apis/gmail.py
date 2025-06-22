"""
Gmail API wrapper for sending and managing emails.

This module provides a GmailService class that simplifies common Gmail operations
including sending HTML emails with embedded images, managing labels, and retrieving messages.
"""

import base64
import datetime
import io
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Dict, List, Any

from PIL import Image, ImageDraw
from googleapiclient.discovery import build


class GmailService:
    """
    A service class for interacting with the Gmail API.

    This class provides methods for sending emails (including HTML with embedded images),
    retrieving messages, managing labels, and other Gmail operations.
    """

    def __init__(self, credentials, version='v1'):
        """
        Initialize the Gmail service.

        Args:
            credentials: Google API credentials object
            version (str): Gmail API version (default: 'v1')
        """
        self.service = build('gmail', version, credentials=credentials)
        self.user_id = 'me'  # Default to authenticated user

    def get_profile(self) -> Dict[str, Any]:
        """
        Get the Gmail profile information for the authenticated user.

        Returns:
            Dict containing profile information including email address,
            message counts, and history ID.
        """
        return self.service.users().getProfile(userId=self.user_id).execute()

    def list_labels(self) -> List[Dict[str, Any]]:
        """
        Get all Gmail labels for the authenticated user.

        Returns:
            List of label dictionaries containing name and ID.
        """
        result = self.service.users().labels().list(userId=self.user_id).execute()
        return result.get('labels', [])

    def list_messages(
        self,
        query: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, str]]:
        """
        List messages in the user's mailbox.

        Args:
            query (str, optional): Gmail search query (e.g., 'from:example@gmail.com')
            max_results (int): Maximum number of messages to return

        Returns:
            List of message dictionaries with 'id' and 'threadId' keys.
        """
        kwargs = {
            'userId': self.user_id,
            'maxResults': max_results
        }
        if query:
            kwargs['q'] = query

        result = self.service.users().messages().list(**kwargs).execute()
        return result.get('messages', [])

    def get_message(self, message_id: str, msg_format: str = 'full') -> Dict[str, Any]:
        """
        Get a specific message by ID.

        Args:
            message_id (str): The message ID to retrieve
            msg_format (str): Message format ('full', 'metadata', 'minimal', 'raw')

        Returns:
            Message dictionary containing the requested message data.
        """
        return self.service.users().messages().get(
            userId=self.user_id,
            id=message_id,
            format=msg_format
        ).execute()

    def create_html_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
        images: Optional[Dict[str, bytes]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create an HTML email with proper headers and optional embedded images/attachments.

        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            html_content (str): HTML content of the email
            from_email (str, optional): Sender email (defaults to authenticated user)
            images (dict, optional): Dict mapping Content-IDs to image bytes
            attachments (list, optional): List of attachment dicts

        Returns:
            Base64-encoded raw message string ready for Gmail API.
        """
        msg = MIMEMultipart('related')
        msg['To'] = to_email
        msg['From'] = from_email or to_email
        msg['Subject'] = subject

        # Add proper RFC-compliant headers to reduce authentication warnings
        msg['Message-ID'] = f'<{uuid.uuid4()}@gmail.com>'
        msg['Date'] = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        msg['MIME-Version'] = '1.0'
        msg['User-Agent'] = 'Gmail API Python Client via rdhyee_utils'
        msg['X-Mailer'] = 'Gmail API via rdhyee_utils'
        msg['X-Priority'] = '3'

        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        # Attach embedded images
        if images:
            for content_id, image_data in images.items():
                img_part = MIMEImage(image_data)
                img_part.add_header('Content-ID', f'<{content_id}>')
                img_part.add_header('Content-Disposition', 'inline', filename=f'{content_id}.png')
                msg.attach(img_part)

        # Attach files
        if attachments:
            for attachment in attachments:
                filename = attachment['filename']
                content = attachment['content']
                content_type = attachment.get('content_type', 'application/octet-stream')

                attachment_part = MIMEBase(*content_type.split('/'))
                attachment_part.set_payload(content)
                encoders.encode_base64(attachment_part)
                attachment_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                msg.attach(attachment_part)

        return base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

    def send_email(self, raw_message: str) -> Dict[str, str]:
        """
        Send an email using the Gmail API.

        Args:
            raw_message (str): Base64-encoded raw message string

        Returns:
            Dict containing the sent message ID and thread ID.
        """
        message = {'raw': raw_message}
        return self.service.users().messages().send(
            userId=self.user_id,
            body=message
        ).execute()

    def send_html_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
        images: Optional[Dict[str, bytes]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, str]:
        """
        Create and send an HTML email in one step.

        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            html_content (str): HTML content of the email
            from_email (str, optional): Sender email (defaults to authenticated user)
            images (dict, optional): Dict mapping Content-IDs to image bytes
            attachments (list, optional): List of attachment dicts

        Returns:
            Dict containing the sent message ID and thread ID.
        """
        raw_message = self.create_html_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=from_email,
            images=images,
            attachments=attachments
        )
        return self.send_email(raw_message)

    @staticmethod
    def create_test_image(
        width: int = 200,
        height: int = 100,
        background_color: str = 'lightblue',
        text: str = 'Test Image',
        text_color: str = 'darkblue'
    ) -> bytes:
        """
        Create a simple test image programmatically.

        Args:
            width (int): Image width in pixels
            height (int): Image height in pixels
            background_color (str): Background color name or hex
            text (str): Text to display on image
            text_color (str): Text color name or hex

        Returns:
            bytes: PNG image data as bytes
        """
        img = Image.new('RGB', (width, height), color=background_color)
        draw = ImageDraw.Draw(img)

        # Calculate text position (roughly centered)
        text_x = width // 4
        text_y = height // 3

        draw.text((text_x, text_y), text, fill=text_color)
        draw.rectangle([10, 10, width-10, height-10], outline=text_color, width=2)

        # Convert to bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_data = img_buffer.getvalue()
        img_buffer.close()

        return img_data

    @staticmethod
    def create_professional_html_template(
        title: str,
        content: str,
        footer_text: Optional[str] = None,
        primary_color: str = '#3498db',
        accent_color: str = '#f39c12'
    ) -> str:
        """
        Create a professional HTML email template.

        Args:
            title (str): Email title/header
            content (str): Main email content (can include HTML)
            footer_text (str, optional): Footer text
            primary_color (str): Primary theme color (hex)
            accent_color (str): Accent/highlight color (hex)

        Returns:
            str: Complete HTML email content with embedded CSS
        """
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if footer_text is None:
            footer_text = f"Sent via Gmail API • {current_time}"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            background-color: white;
            max-width: 600px;
            margin: 0 auto;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid {primary_color};
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .content {{
            color: #34495e;
        }}
        .highlight {{
            background-color: {accent_color};
            color: white;
            padding: 10px;
            border-radius: 5px;
            display: inline-block;
            margin: 10px 0;
        }}
        .image-container {{
            text-align: center;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            font-size: 12px;
            color: #7f8c8d;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            background-color: {primary_color};
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .btn:hover {{
            background-color: #2980b9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
        </div>

        <div class="content">
            {content}
        </div>

        <div class="footer">
            <p>{footer_text}</p>
        </div>
    </div>
</body>
</html>
"""
