"""Email reader module for J.A.R.V.I.S.

Reads emails from IMAP inbox.
"""

import asyncio
import email
import logging
import os
from email.header import decode_header
from typing import Optional, List

from backend.shared.config import settings

logger = logging.getLogger(__name__)


async def read_inbox(max_emails: int = 10, folder: str = "INBOX",
                     mark_seen: bool = False) -> str:
    """Read recent emails from the IMAP inbox."""
    address = settings.email_address
    password = settings.email_password
    if not address or not password:
        return "Email not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD in .env"

    loop = asyncio.get_event_loop()

    def _fetch():
        import imaplib
        server = "imap.gmail.com" if "gmail" in address else settings.smtp_server
        server = server.replace("smtp", "imap")

        try:
            mail = imaplib.IMAP4_SSL(server)
            mail.login(address, password)
            mail.select(folder)
            _, data = mail.search(None, "ALL")
            ids = data[0].split()
            recent = ids[-max_emails:] if ids else []
            out_lines = [f"**Inbox — {folder}** ({len(recent)} emails)"]

            for mid in reversed(recent):
                _, msg_data = mail.fetch(mid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject, sender = "", ""
                for part in decode_header(msg["Subject"] or ""):
                    if isinstance(part[0], bytes):
                        subject += part[0].decode(part[1] or "utf-8", errors="replace")
                    else:
                        subject += str(part[0])
                for part in decode_header(msg["From"] or ""):
                    if isinstance(part[0], bytes):
                        sender += part[0].decode(part[1] or "utf-8", errors="replace")
                    else:
                        sender += str(part[0])
                date = msg["Date"] or ""
                body = ""
                if msg.is_multipart():
                    for p in msg.walk():
                        if p.get_content_type() == "text/plain":
                            body = p.get_payload(decode=True).decode(
                                "utf-8", errors="replace")[:300]
                            break
                else:
                    body = msg.get_payload(decode=True).decode(
                        "utf-8", errors="replace")[:300]
                out_lines.append(
                    f"\n  From: {sender}\n  Subject: {subject}\n  Date: {date}"
                    f"\n  {body[:200]}"
                )
                if not mark_seen:
                    mail.store(mid, "-FLAGS", "\\Seen")
            mail.logout()
            return "\n".join(out_lines)
        except Exception as e:
            return f"IMAP error: {e}"

    return await loop.run_in_executor(None, _fetch)


async def search_emails(query: str, max_emails: int = 10) -> str:
    """Search emails by subject or sender."""
    address = settings.email_address
    password = settings.email_password
    if not address or not password:
        return "Email not configured."

    loop = asyncio.get_event_loop()

    def _search():
        import imaplib
        server = "imap.gmail.com" if "gmail" in address else settings.smtp_server.replace("smtp", "imap")
        try:
            mail = imaplib.IMAP4_SSL(server)
            mail.login(address, password)
            mail.select("INBOX")
            _, data = mail.search(None, f'SUBJECT "{query}"')
            if not data[0]:
                _, data = mail.search(None, f'FROM "{query}"')
            ids = data[0].split()
            recent = ids[-max_emails:] if ids else []
            if not recent:
                mail.logout()
                return f"No emails found matching '{query}'."
            out_lines = [f"**Search results for '{query}'** ({len(recent)} emails)"]
            for mid in reversed(recent):
                _, msg_data = mail.fetch(mid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                out_lines.append(f"  - {msg['Subject']} | {msg['From']} | {msg['Date']}")
            mail.logout()
            return "\n".join(out_lines)
        except Exception as e:
            return f"Email search error: {e}"

    return await loop.run_in_executor(None, _search)
