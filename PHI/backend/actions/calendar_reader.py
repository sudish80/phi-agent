"""Google Calendar reader for J.A.R.V.I.S.

Reads upcoming events from Google Calendar.
"""

import asyncio
import logging
import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from backend.shared.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


async def get_upcoming_events(max_results: int = 10,
                              days_ahead: int = 7) -> str:
    """Get upcoming Google Calendar events."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        return "Calendar requires google-api-python-client"

    loop = asyncio.get_event_loop()

    def _fetch():
        creds = None
        token_file = os.path.expanduser("~/.calendar_token.pickle")
        if os.path.exists(token_file):
            with open(token_file, "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_file = os.path.expanduser("~/.calendar_credentials.json")
                if not os.path.exists(creds_file):
                    return ("Calendar not configured. Place "
                            "calendar_credentials.json in your home directory.")
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, "wb") as f:
                pickle.dump(creds, f)
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc).isoformat() + "Z"
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat() + "Z"
        events = service.events().list(
            calendarId="primary", timeMin=now, timeMax=end,
            maxResults=max_results, singleEvents=True,
            orderBy="startTime",
        ).execute()
        items = events.get("items", [])
        if not items:
            return f"No upcoming events found in the next {days_ahead} days."
        lines = [f"**Upcoming Events** ({len(items)} events)"]
        for ev in items:
            start = ev["start"].get("dateTime", ev["start"].get("date", "N/A"))
            summary = ev.get("summary", "No title")
            lines.append(f"  - {start}: {summary}")
        return "\n".join(lines)

    return await loop.run_in_executor(None, _fetch)
