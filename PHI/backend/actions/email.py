"""Email sending via SMTP."""

import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from backend.shared.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str,
                     cc: Optional[List[str]] = None,
                     is_html: bool = False) -> bool:
    if not settings.email_address or not settings.email_password:
        logger.warning("Email not configured")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.email_address
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = ", ".join(cc)
        content = MIMEText(body, "html" if is_html else "plain")
        msg.attach(content)

        def _send():
            with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.email_address, settings.email_password)
                server.send_message(msg)

        await asyncio.get_event_loop().run_in_executor(None, _send)
        logger.info(f"Email sent to {to}: '{subject}'")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
