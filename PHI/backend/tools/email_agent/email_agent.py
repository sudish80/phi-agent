"""Email Agent — Intelligent email & calendar management with HITL, MCP, and semantic search.

Adapted from: github.com/microsoft/local-email-agent
Architecture: Supervisor + Sub-agents with Human-in-the-Loop approvals.
"""

import asyncio
import datetime
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

logger = logging.getLogger(__name__)

_EMAILS_DIR = Path(__file__).resolve().parent / "email_data"
_EMAILS_DIR.mkdir(parents=True, exist_ok=True)

CURRENT_DATE = datetime.datetime.now(datetime.UTC).date().isoformat()

# ---------------------------------------------------------------------------
# HITL Schemas (Human-in-the-Loop)
# ---------------------------------------------------------------------------

class ActionRequest:
    def __init__(self, action: str, args: Dict[str, Any]):
        self.action = action
        self.args = args

class HumanInterrupt:
    def __init__(self, action: str, args: Dict[str, Any],
                 description: str = None,
                 allow_ignore: bool = True, allow_respond: bool = True,
                 allow_edit: bool = True, allow_accept: bool = True):
        self.action_request = ActionRequest(action, args)
        self.description = description or self._gen_description(action, args)
        self.config = {"allow_ignore": allow_ignore, "allow_respond": allow_respond,
                       "allow_edit": allow_edit, "allow_accept": allow_accept}

    def _gen_description(self, action: str, args: Dict) -> str:
        if action == "send_email":
            to = args.get("to", "?")
            subj = args.get("subject", "no subject")
            return f"Send email to {to}: \"{subj}\""
        if action in ("create_event", "update_event"):
            subj = args.get("subject", "Untitled")
            return f"Calendar: {action.replace('_',' ')} \"{subj}\""
        return f"{action}: {json.dumps(args)[:100]}"

    def to_dict(self) -> dict:
        return {
            "action_request": {"action": self.action_request.action, "args": self.action_request.args},
            "description": self.description,
            "config": self.config,
        }

HITL_ACTIONS = {"send_email", "create_event", "update_event", "delete_event", "reply_email"}

# ---------------------------------------------------------------------------
# Email Storage (SQLite + optional vector search)
# ---------------------------------------------------------------------------

_EMAIL_DB_PATH = _EMAILS_DIR / "emails.db"
_EMAIL_BLOBS_DIR = _EMAILS_DIR / "blobs"
_EMAIL_BLOBS_DIR.mkdir(parents=True, exist_ok=True)

_EMAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    recipient TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    received_at TEXT DEFAULT '',
    folder TEXT DEFAULT 'inbox',
    is_read INTEGER DEFAULT 0,
    is_starred INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_emails_author ON emails(author);
CREATE INDEX IF NOT EXISTS idx_emails_subject ON emails(subject);
CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails(folder);
"""

_SAMPLE_EMAILS = [
    ("em001", "alice@example.com", "user@jarvis.ai", "Project Update - Q2 Review",
     "Hi, please review the Q2 project metrics attached. We need feedback by Friday. -Alice"),
    ("em002", "bob@company.com", "user@jarvis.ai", "Meeting Tomorrow 10AM",
     "Reminder: Team sync tomorrow at 10 AM in Conference Room B. Bring your progress reports."),
    ("em003", "hr@company.com", "user@jarvis.ai", "Health Insurance Open Enrollment",
     "Open enrollment for 2026 health benefits ends Nov 30. Visit the HR portal to make your selections."),
    ("em004", "carol@partner.org", "user@jarvis.ai", "Partnership Agreement Draft",
     "Please find the draft partnership agreement attached. Key terms are on pages 3-5. -Carol"),
    ("em005", "noreply@calendar.com", "user@jarvis.ai", "Invoice #INV-2026-0042",
     "Your invoice for $1,250.00 is now available. Payment due within 30 days."),
    ("em006", "dave@team.io", "user@jarvis.ai", "Sprint Retrospective Notes",
     "Here are the notes from today's sprint retro. Action items are highlighted in yellow. -Dave"),
    ("em007", "eve@consulting.net", "user@jarvis.ai", "Proposal for AI Integration",
     "Thank you for the opportunity. Our proposal for the AI integration project is attached. Budget estimate: $45k."),
    ("em008", "support@saas-app.com", "user@jarvis.ai", "Your Subscription Renewal",
     "Your Premium subscription renews on Dec 15, 2026. Price: $299/year. Login to manage."),
    ("em009", "frank@design.studio", "user@jarvis.ai", "Brand Refresh - Mockups v2",
     "Updated brand mockups attached based on your feedback. We love direction B! -Frank"),
    ("em010", "grace@academic.edu", "user@jarvis.ai", "Conference Paper Deadline Extension",
     "The submission deadline for the AI Conference has been extended to Jan 15, 2027. -Dr. Grace"),
]

def _init_email_db():
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        conn.executescript(_EMAIL_SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT OR REPLACE INTO emails VALUES (?,?,?,?,?,?,?,?,?)",
                _SAMPLE_EMAILS
            )
            conn.commit()
            logger.info(f"Initialized email DB with {len(_SAMPLE_EMAILS)} emails")
        conn.close()
    except Exception as e:
        logger.error(f"Email DB init error: {e}")

def _init_vector_store():
    """Initialize lightweight vector store for semantic email search."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _init_email_db()
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        rows = conn.execute("SELECT id, author, subject, body FROM emails").fetchall()
        conn.close()
        vectors = {}
        for row in rows:
            text = f"{row[1]} {row[2]} {row[3]}"
            vec = model.encode(text).tolist()
            vectors[row[0]] = {"vec": vec, "author": row[1], "subject": row[2], "snippet": row[3][:200]}
        db_path = str(_EMAILS_DIR / "email_vectors.json")
        with open(db_path, "w") as f:
            json.dump(vectors, f)
        logger.info(f"Indexed {len(vectors)} email vectors")
        return vectors
    except ImportError:
        logger.info("Vector search unavailable (install sentence-transformers)")
        return {}

class EmailStorage:
    """Email storage with SQLite, filesystem, and optional vector search."""

    def __init__(self):
        self._vectors = None

    def _load_vectors(self) -> dict:
        if self._vectors is None:
            try:
                db_path = _EMAILS_DIR / "email_vectors.json"
                if db_path.exists():
                    with open(db_path) as f:
                        self._vectors = json.load(f)
                else:
                    self._vectors = _init_vector_store() or {}
            except Exception:
                self._vectors = {}
        return self._vectors

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search emails by semantic similarity, falling back to text search."""
        vectors = self._load_vectors()
        if vectors:
            try:
                from sentence_transformers import SentenceTransformer
                import numpy as np
                model = SentenceTransformer("all-MiniLM-L6-v2")
                q_vec = np.array(model.encode(query))
                scored = []
                for eid, data in vectors.items():
                    ev = np.array(data["vec"])
                    sim = np.dot(q_vec, ev) / (np.linalg.norm(q_vec) * np.linalg.norm(ev) + 1e-10)
                    scored.append((sim, eid, data))
                scored.sort(key=lambda x: -x[0])
                return [
                    {"email_id": eid, "score": float(sim), "author": d["author"],
                     "subject": d["subject"], "snippet": d["snippet"]}
                    for sim, eid, d in scored[:top_k]
                ]
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        return self._text_search(query, top_k)

    def _text_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        _init_email_db()
        try:
            import sqlite3
            conn = sqlite3.connect(str(_EMAIL_DB_PATH))
            conn.row_factory = sqlite3.Row
            like = f"%{query}%"
            rows = conn.execute(
                "SELECT * FROM emails WHERE author LIKE ? OR subject LIKE ? OR body LIKE ? LIMIT ?",
                (like, like, like, top_k)
            ).fetchall()
            conn.close()
            return [{"email_id": r["id"], "author": r["author"], "subject": r["subject"],
                     "snippet": r["body"][:200], "folder": r["folder"],
                     "is_read": bool(r["is_read"]), "received_at": r["received_at"]}
                    for r in rows]
        except Exception as e:
            logger.warning(f"Text search failed: {e}")
            return []

    def list_inbox(self, folder: str = "inbox", limit: int = 20) -> List[Dict]:
        _init_email_db()
        try:
            import sqlite3
            conn = sqlite3.connect(str(_EMAIL_DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM emails WHERE folder = ? ORDER BY received_at DESC LIMIT ?",
                (folder, limit)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]

    def mark_read(self, email_id: str) -> str:
        try:
            import sqlite3
            conn = sqlite3.connect(str(_EMAIL_DB_PATH))
            conn.execute("UPDATE emails SET is_read = 1 WHERE id = ?", (email_id,))
            conn.commit(); conn.close()
            return f"Marked {email_id} as read"
        except Exception as e:
            return f"Error: {e}"

    def get_email(self, email_id: str) -> Optional[Dict]:
        try:
            import sqlite3
            conn = sqlite3.connect(str(_EMAIL_DB_PATH))
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
            conn.close()
            return dict(r) if r else None
        except Exception:
            return None

# ---------------------------------------------------------------------------
# Calendar Manager (simulated)
# ---------------------------------------------------------------------------

_CALENDAR_EVENTS = [
    {"id": "cal001", "title": "Team Standup", "date": "2026-05-28", "time": "09:00",
     "duration": 30, "attendees": ["team@jarvis.ai"], "location": "Zoom"},
    {"id": "cal002", "title": "Client Presentation", "date": "2026-05-28", "time": "14:00",
     "duration": 60, "attendees": ["client@example.com", "sales@jarvis.ai"], "location": "Conference A"},
    {"id": "cal003", "title": "Sprint Planning", "date": "2026-05-29", "time": "10:00",
     "duration": 90, "attendees": ["dev-team@jarvis.ai"], "location": "Room 301"},
    {"id": "cal004", "title": "Lunch with Partners", "date": "2026-05-30", "time": "12:00",
     "duration": 60, "attendees": ["partner@acme.com"], "location": "Downtown Bistro"},
    {"id": "cal005", "title": "Quarterly Review", "date": "2026-06-02", "time": "13:00",
     "duration": 120, "attendees": ["all-hands@jarvis.ai"], "location": "Main Auditorium"},
]

_calendar_lock = asyncio.Lock()

def _get_date_range(query: str) -> tuple:
    today = datetime.date.today()
    q = query.lower()
    if "today" in q:
        return today.isoformat(), today.isoformat()
    if "tomorrow" in q:
        t = today + datetime.timedelta(days=1)
        return t.isoformat(), t.isoformat()
    if "this week" in q:
        start = today - datetime.timedelta(days=today.weekday())
        return start.isoformat(), (start + datetime.timedelta(days=6)).isoformat()
    if "next week" in q:
        start = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=7)
        return start.isoformat(), (start + datetime.timedelta(days=6)).isoformat()
    if "month" in q:
        return today.replace(day=1).isoformat(), (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1).isoformat()
    return today.isoformat(), (today + datetime.timedelta(days=7)).isoformat()

# ---------------------------------------------------------------------------
# Core Agent Functions
# ---------------------------------------------------------------------------

_storage = None
def _get_storage() -> EmailStorage:
    global _storage
    if _storage is None:
        _storage = EmailStorage()
    return _storage

_VECTOR_INIT = False
def _ensure_index():
    global _VECTOR_INIT
    if not _VECTOR_INIT:
        _init_email_db()
        try:
            _init_vector_store()
        except Exception:
            pass
        _VECTOR_INIT = True

async def email_search(query: str, top_k: int = 5) -> str:
    """Search emails by semantic similarity or text match."""
    _ensure_index()
    results = _get_storage().search(query, top_k)
    if not results:
        return "No emails found matching your query."
    return json.dumps(results, indent=2, default=str)

async def email_list_inbox(folder: str = "inbox", limit: int = 20) -> str:
    """List emails in a folder."""
    _ensure_index()
    results = _get_storage().list_inbox(folder, limit)
    if not results:
        return "No emails in this folder."
    return json.dumps(results, indent=2, default=str)

async def email_get_message(email_id: str) -> str:
    """Get a specific email by ID."""
    _ensure_index()
    email = _get_storage().get_email(email_id)
    if email:
        return json.dumps(email, indent=2, default=str)
    return f"Email {email_id} not found."

async def email_mark_read(email_id: str) -> str:
    """Mark an email as read."""
    _ensure_index()
    return _get_storage().mark_read(email_id)

async def email_send(to: str, subject: str, body: str, cc: str = "") -> str:
    """Send an email."""
    _ensure_index()
    try:
        import sqlite3, uuid
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        eid = f"em{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now().isoformat()
        conn.execute(
            "INSERT INTO emails (id, author, recipient, subject, body, received_at, folder) VALUES (?,?,?,?,?,?,?)",
            (eid, "user@jarvis.ai", to, subject, body, now, "sent")
        )
        conn.commit(); conn.close()
        return f"Email sent to {to} with subject \"{subject}\" (ID: {eid})"
    except Exception as e:
        return f"Error sending email: {e}"

async def email_draft(to: str, subject: str, body: str) -> str:
    """Create an email draft without sending."""
    try:
        import sqlite3, uuid
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        eid = f"em{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now().isoformat()
        conn.execute(
            "INSERT INTO emails (id, author, recipient, subject, body, received_at, folder) VALUES (?,?,?,?,?,?,?)",
            (eid, "user@jarvis.ai", to, subject, body, now, "drafts")
        )
        conn.commit(); conn.close()
        return f"Draft created for {to}: \"{subject}\" (ID: {eid})"
    except Exception as e:
        return f"Error: {e}"

async def email_reply(email_id: str, body: str) -> str:
    """Reply to an email. Requires human approval for sending."""
    _ensure_index()
    original = _get_storage().get_email(email_id)
    if not original:
        return f"Email {email_id} not found."
    try:
        import sqlite3, uuid
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        eid = f"em{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now().isoformat()
        conn.execute(
            "INSERT INTO emails (id, author, recipient, subject, body, received_at, folder) VALUES (?,?,?,?,?,?,?)",
            (eid, "user@jarvis.ai", original["author"], f"Re: {original['subject']}", body, now, "sent")
        )
        conn.commit(); conn.close()
        return f"Reply sent to {original['author']} (ID: {eid})"
    except Exception as e:
        return f"Error: {e}"

async def calendar_list(date_range: str = "this week") -> str:
    """List calendar events in a date range."""
    start, end = _get_date_range(date_range)
    filtered = [e for e in _CALENDAR_EVENTS if start <= e["date"] <= end]
    if not filtered:
        return f"No events found for {date_range}."
    return json.dumps(filtered, indent=2)

async def calendar_create(subject: str, date: str, time: str = "10:00",
                           duration: int = 60, attendees: str = "",
                           location: str = "") -> str:
    """Create a calendar event."""
    _ensure_index()
    async with _calendar_lock:
        eid = f"cal{uuid.uuid4().hex[:6]}"
        _CALENDAR_EVENTS.append({
            "id": eid, "title": subject, "date": date, "time": time,
            "duration": duration,
            "attendees": [a.strip() for a in attendees.split(",") if a.strip()],
            "location": location or "TBD"
        })
    return f"Event created: \"{subject}\" on {date} at {time} (ID: {eid})"

async def calendar_update(event_id: str, subject: str = None, date: str = None,
                           time: str = None, duration: int = None) -> str:
    """Update a calendar event."""
    _ensure_index()
    async with _calendar_lock:
        for e in _CALENDAR_EVENTS:
            if e["id"] == event_id:
                if subject: e["title"] = subject
                if date: e["date"] = date
                if time: e["time"] = time
                if duration: e["duration"] = duration
                return f"Event {event_id} updated."
        return f"Event {event_id} not found."

async def calendar_delete(event_id: str) -> str:
    """Delete a calendar event. Requires human approval."""
    async with _calendar_lock:
        for i, e in enumerate(_CALENDAR_EVENTS):
            if e["id"] == event_id:
                _CALENDAR_EVENTS.pop(i)
                return f"Event {event_id} deleted."
        return f"Event {event_id} not found."

async def calendar_find_slots(duration: int = 30, date: str = "") -> str:
    """Find available time slots on a given date."""
    if not date:
        date = datetime.date.today().isoformat()
    day_events = [e for e in _CALENDAR_EVENTS if e["date"] == date]
    busy = [(int(e["time"].split(":")[0])*60 + int(e["time"].split(":")[1]),
             int(e["time"].split(":")[0])*60 + int(e["time"].split(":")[1]) + e["duration"])
            for e in day_events]
    slots = []
    for start in range(480, 1080, 30):  # 8AM to 6PM
        end = start + duration
        if not any(s < end and e > start for s, e in busy):
            h, m = start // 60, start % 60
            slots.append(f"{h:02d}:{m:02d}")
        if len(slots) >= 5:
            break
    if not slots:
        return "No available slots found for this date."
    return f"Available slots on {date}: {', '.join(slots)}"

async def email_get_attachment(email_id: str) -> str:
    """Get attachment info for an email (simulated)."""
    _ensure_index()
    email = _get_storage().get_email(email_id)
    if not email:
        return f"Email {email_id} not found."
    return json.dumps({
        "email_id": email_id,
        "subject": email.get("subject"),
        "has_attachment": email_id in ("em001", "em004", "em007", "em009"),
        "attachment_types": ["pdf", "docx"] if email_id in ("em001", "em004") else ["png", "pdf"] if email_id == "em009" else []
    }, indent=2)

async def email_star(email_id: str) -> str:
    """Star or unstar an email."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        current = conn.execute("SELECT is_starred FROM emails WHERE id = ?", (email_id,)).fetchone()
        if current is None:
            return f"Email {email_id} not found."
        new_star = 0 if current[0] else 1
        conn.execute("UPDATE emails SET is_starred = ? WHERE id = ?", (new_star, email_id))
        conn.commit(); conn.close()
        return f"Email {email_id} {'starred' if new_star else 'unstarred'}."
    except Exception as e:
        return f"Error: {e}"

async def email_search_by_sender(sender: str) -> str:
    """Search emails from a specific sender."""
    _ensure_index()
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        conn.row_factory = sqlite3.Row
        like = f"%{sender}%"
        rows = conn.execute(
            "SELECT * FROM emails WHERE author LIKE ? ORDER BY received_at DESC LIMIT 20",
            (like,)
        ).fetchall()
        conn.close()
        if not rows:
            return f"No emails from {sender}."
        return json.dumps([dict(r) for r in rows], indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"

async def email_get_unread_count() -> str:
    """Get count of unread emails."""
    _ensure_index()
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM emails WHERE is_read = 0 AND folder = 'inbox'").fetchone()[0]
        conn.close()
        return json.dumps({"unread_count": count}, indent=2)
    except Exception as e:
        return f"Error: {e}"

async def email_forward(email_id: str, to: str, note: str = "") -> str:
    """Forward an email to another recipient."""
    _ensure_index()
    original = _get_storage().get_email(email_id)
    if not original:
        return f"Email {email_id} not found."
    body = f"---------- Forwarded message ---------\nFrom: {original['author']}\nSubject: {original['subject']}\n\n{original['body']}"
    if note:
        body = f"{note}\n\n{body}"
    return await email_send(to, f"Fwd: {original['subject']}", body)

async def email_create_folder(folder_name: str) -> str:
    """Create a new email folder/label."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        conn.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS label TEXT DEFAULT ''")
        conn.close()
        return f"Folder '{folder_name}' is ready for use."
    except Exception as e:
        return f"Error: {e}"

async def email_archive(email_id: str) -> str:
    """Move an email to archive."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        conn.execute("UPDATE emails SET folder = 'archive' WHERE id = ?", (email_id,))
        conn.commit(); conn.close()
        return f"Email {email_id} archived."
    except Exception as e:
        return f"Error: {e}"

async def email_trash(email_id: str) -> str:
    """Move an email to trash."""
    try:
        import sqlite3
        conn = sqlite3.connect(str(_EMAIL_DB_PATH))
        conn.execute("UPDATE emails SET folder = 'trash' WHERE id = ?", (email_id,))
        conn.commit(); conn.close()
        return f"Email {email_id} moved to trash."
    except Exception as e:
        return f"Error: {e}"
