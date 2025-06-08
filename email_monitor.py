import imaplib
import email
import os
from email.header import decode_header
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import logging
from dotenv import load_dotenv
import re
from email.utils import parsedate_to_datetime
from dataclasses import dataclass

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Attachment:
    filename: str
    content: bytes
    content_type: str

@dataclass
class Email:
    id: str
    subject: str
    sender: str
    date: Optional[datetime]
    attachments: List[Attachment]

class EmailMonitor:
    def __init__(self):
        self.email_host = os.getenv('EMAIL_HOST', 'imap.gmail.com')
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        
        if not all([self.email_host, self.email_user, self.email_password]):
            raise ValueError("Missing required email configuration in .env file")

    def connect(self) -> imaplib.IMAP4_SSL:
        """Establish connection to email server"""
        try:
            mail = imaplib.IMAP4_SSL(self.email_host)
            mail.login(self.email_user, self.email_password)
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to email: {str(e)}")
            raise

    def get_attachments(self, msg: email.message.Message) -> List[Attachment]:
        """Extract attachments from email message"""
        attachments = []
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()
            if filename:
                # Decode filename if needed
                filename_tuple = decode_header(filename)[0]
                if isinstance(filename_tuple[0], bytes):
                    filename = filename_tuple[0].decode(filename_tuple[1] or 'utf-8')

                # Check if file type is supported
                if filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.tiff')):
                    attachments.append(Attachment(
                        filename=filename,
                        content=part.get_payload(decode=True),
                        content_type=part.get_content_type()
                    ))
        
        return attachments

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string into datetime object"""
        try:
            # First try email.utils parser which handles most standard email date formats
            return parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            # If that fails, try common date formats
            date_formats = [
                '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822
                '%a, %d %b %Y %H:%M:%S %Z',  # With timezone name
                '%a, %d %b %Y %H:%M:%S',     # Without timezone
                '%d %b %Y %H:%M:%S %z',      # Without weekday
                '%Y-%m-%d %H:%M:%S',         # ISO-like format
                '%d-%m-%Y %H:%M:%S'          # European format
            ]
            
            # Remove timezone abbreviations in parentheses
            date_str = re.sub(r'\([A-Z]{3,4}\)', '', date_str).strip()
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            logger.warning(f"Could not parse date: {date_str}")
            return None

    def process_email(self, email_id: bytes, mail: imaplib.IMAP4_SSL) -> Optional[Email]:
        """Process a single email and extract relevant information"""
        try:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

            # Extract basic email information
            subject_tuple = decode_header(msg["subject"])[0]
            subject = subject_tuple[0]
            if isinstance(subject, bytes):
                subject = subject.decode(subject_tuple[1] or 'utf-8')

            sender = msg.get("from", "")
            date_str = msg.get("date", "")
            date = self.parse_date(date_str) if date_str else None

            # Get attachments
            attachments = self.get_attachments(msg)

            return Email(
                id=email_id.decode(),
                subject=subject,
                sender=sender,
                date=date,
                attachments=attachments
            )

        except Exception as e:
            logger.error(f"Error processing email {email_id}: {str(e)}")
            return None

    def check_new_emails(self, folder: str = 'INBOX') -> List[Email]:
        """Check for new unread emails in specified folder"""
        mail = self.connect()
        try:
            mail.select(folder)
            _, messages = mail.search(None, 'UNSEEN')
            
            email_data = []
            for email_id in messages[0].split():
                processed_email = self.process_email(email_id, mail)
                if processed_email:
                    email_data.append(processed_email)

            return email_data

        except Exception as e:
            logger.error(f"Error checking new emails: {str(e)}")
            return []

        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

    def mark_as_processed(self, email_id: str, folder: str = 'INBOX') -> bool:
        """Mark an email as processed by moving it to a processed folder"""
        mail = self.connect()
        try:
            mail.select(folder)
            
            # Create processed folder if it doesn't exist
            processed_folder = 'Processed'
            if processed_folder not in [f.decode().split('"/')[-1].strip('"') for f in mail.list()[1]]:
                mail.create(processed_folder)
            
            # Move email to processed folder
            mail.copy(email_id.encode(), processed_folder)
            mail.store(email_id.encode(), '+FLAGS', '\\Deleted')
            mail.expunge()
            
            return True

        except Exception as e:
            logger.error(f"Error marking email {email_id} as processed: {str(e)}")
            return False

        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass 