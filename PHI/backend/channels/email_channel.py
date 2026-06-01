"""Email channel — two-way email conversation via IMAP/SMTP."""

import logging
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from dataclasses import dataclass, field

from backend.channels.base import BaseChannel, ChannelConfig

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_address: str = ""
    email_password: str = ""
    check_interval: int = 60


class EmailChannel(BaseChannel):
    """Two-way email conversation channel."""

    name = "email"

    def __init__(self, config: Optional[EmailConfig] = None):
        self.email_config = config or EmailConfig()
        self.config = ChannelConfig(enabled=False, dm_policy="pairing")

    async def start(self) -> None:
        if not self.email_config.email_address:
            logger.warning("Email channel not configured")
            return
        logger.info("Email channel ready: %s", self.email_config.email_address)

    async def stop(self) -> None:
        logger.info("Email channel stopped")

    async def send_message(self, channel_id: str, content: str,
                            reply_to: Optional[str] = None) -> str:
        to_addr = channel_id
        msg = MIMEText(content, "plain")
        msg["Subject"] = f"Re: {reply_to or 'PHI Agent'}"
        msg["From"] = self.email_config.email_address
        msg["To"] = to_addr

        try:
            with smtplib.SMTP(self.email_config.smtp_server, self.email_config.smtp_port) as server:
                server.starttls()
                server.login(self.email_config.email_address, self.email_config.email_password)
                server.send_message(msg)
            return f"Email sent to {to_addr}"
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return f"Error: {e}"

    async def check_inbox(self) -> List[dict]:
        """Poll for new emails (called by cron)."""
        try:
            with imaplib.IMAP4_SSL(self.email_config.imap_server) as conn:
                conn.login(self.email_config.email_address, self.email_config.email_password)
                conn.select("INBOX")
                _, data = conn.search(None, "UNSEEN")
                messages = []
                for num in data[0].split():
                    _, msg_data = conn.fetch(num, "(RFC822)")
                    raw = email.message_from_bytes(msg_data[0][1])
                    messages.append({
                        "from": raw["From"],
                        "subject": raw["Subject"],
                        "body": self._get_body(raw),
                    })
                return messages
        except Exception as e:
            logger.error("Inbox check failed: %s", e)
            return []

    def _get_body(self, msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode()
        return msg.get_payload(decode=True).decode() if msg.get_payload(decode=True) else ""
