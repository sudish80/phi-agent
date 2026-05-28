"""Calendar event creation using Google Calendar API or local calendar."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from backend.shared.config import settings

logger = logging.getLogger(__name__)


async def create_event(summary: str, start: str, end: str,
                       description: str = "", location: str = "") -> Optional[str]:
    """Create a calendar event. Returns event ID if successful."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request

        scopes = ["https://www.googleapis.com/auth/calendar"]

        def _create():
            try:
                creds = Credentials.from_authorized_user_file("token.json", scopes)
            except Exception:
                logger.warning("Google Calendar credentials not found")
                return None

            service = build("calendar", "v3", credentials=creds)
            event = {
                "summary": summary,
                "description": description,
                "location": location,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            }
            event_result = service.events().insert(
                calendarId="primary", body=event
            ).execute()
            return event_result.get("id")

        loop = asyncio.get_event_loop()
        event_id = await loop.run_in_executor(None, _create)

        if event_id:
            logger.info(f"Calendar event created: {summary}")
            return event_id
        return None

    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return None
