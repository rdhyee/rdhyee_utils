"""
Convenience module for email functionality using Gmail API.

This module provides easy access to Gmail functionality from rdhyee_utils.
"""

from ..google_apis import get_credentials, GmailService, CLIENT_SECRET_FILE


def get_gmail_service(
    credentials_file_name='gmail.json',
    scopes=None,
    client_secret_file=CLIENT_SECRET_FILE
):
    """
    Create a Gmail service with default scopes for common operations.
    
    Args:
        credentials_file_name (str): Name of the credentials file
        scopes (list, optional): Gmail API scopes. Defaults to read, send, and modify
        client_secret_file (str): Path to client secret file
        
    Returns:
        GmailService: Configured Gmail service instance
    """
    if scopes is None:
        scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
    
    credentials = get_credentials(
        credentials_file_name=credentials_file_name,
        application_name='gmail',
        scopes=scopes,
        client_secret_file=client_secret_file
    )
    
    return GmailService(credentials)


# Re-export the GmailService for convenience
__all__ = ['get_gmail_service', 'GmailService']
