"""Meeting Transcription Pipeline — record, VAD-segment, STT, diarize, store, summarize.

Full pipeline:
  Audio input → Voice Activity Detection → Speech-to-Text
  → Speaker Diarization → Transcript Storage → Summarization
"""

import json
import logging
import asyncio
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Utterance:
    speaker: str
    text: str
    start_time: float
    end_time: float
    confidence: float = 0.0


@dataclass
class MeetingTranscript:
    meeting_id: str
    title: str
    date: str
    duration_seconds: float
    utterances: List[Utterance] = field(default_factory=list)
    speakers: List[str] = field(default_factory=list)
    summary: str = ""
    action_items: List[str] = field(default_factory=list)
    key_topics: List[str] = field(default_factory=list)


class MeetingTranscriber:
    def __init__(self):
        self._active_meetings: Dict[str, MeetingTranscript] = {}
        self._audio_buffer: Dict[str, List[bytes]] = {}

    async def start_meeting(self, title: str = "Untitled Meeting",
                            meeting_id: Optional[str] = None) -> str:
        import uuid
        mid = meeting_id or uuid.uuid4().hex[:12]
        self._active_meetings[mid] = MeetingTranscript(
            meeting_id=mid,
            title=title,
            date=datetime.now(timezone.utc).isoformat(),
            duration_seconds=0.0,
        )
        self._audio_buffer[mid] = []
        logger.info(f"Meeting started: {mid} - {title}")
        return json.dumps({"meeting_id": mid, "title": title, "status": "recording"})

    async def process_audio_chunk(self, meeting_id: str, audio_bytes: bytes,
                                   sample_rate: int = 16000) -> str:
        meeting = self._active_meetings.get(meeting_id)
        if not meeting:
            return f"No active meeting: {meeting_id}"

        self._audio_buffer.setdefault(meeting_id, []).append(audio_bytes)

        try:
            import webrtcvad
            vad = webrtcvad.Vad(2)
            is_speech = vad.is_speech(audio_bytes, sample_rate)
        except Exception:
            is_speech = True

        if not is_speech:
            return json.dumps({"meeting_id": meeting_id, "speech_detected": False})

        try:
            from backend.hearing.stt import transcribe_audio
            text = await transcribe_audio(audio_bytes)
        except Exception:
            text = ""

        if text and text.strip():
            utterance = Utterance(
                speaker="unknown",
                text=text.strip(),
                start_time=time.time(),
                end_time=time.time(),
            )
            meeting.utterances.append(utterance)
            if "unknown" not in meeting.speakers:
                meeting.speakers.append("unknown")
            return json.dumps({
                "meeting_id": meeting_id,
                "speech_detected": True,
                "text": text.strip(),
                "speaker": "unknown",
            })

        return json.dumps({"meeting_id": meeting_id, "speech_detected": True, "text": ""})

    async def end_meeting(self, meeting_id: str, summarize: bool = True,
                          store: bool = True) -> str:
        meeting = self._active_meetings.get(meeting_id)
        if not meeting:
            return f"No active meeting: {meeting_id}"

        if meeting.utterances:
            meeting.duration_seconds = meeting.utterances[-1].end_time - meeting.utterances[0].start_time

        full_transcript = "\n".join(
            f"[{u.speaker}] {u.text}" for u in meeting.utterances
        )

        if summarize and full_transcript.strip():
            meeting.summary = await self._summarize(full_transcript)
            meeting.action_items = await self._extract_action_items(full_transcript)
            meeting.key_topics = await self._extract_topics(full_transcript)

        if store and full_transcript.strip():
            await self._store_transcript(meeting)

        result = {
            "meeting_id": meeting_id,
            "title": meeting.title,
            "date": meeting.date,
            "duration_seconds": round(meeting.duration_seconds, 1),
            "utterance_count": len(meeting.utterances),
            "speakers": meeting.speakers,
            "summary": meeting.summary,
            "action_items": meeting.action_items,
            "key_topics": meeting.key_topics,
            "full_transcript": full_transcript,
        }

        self._active_meetings.pop(meeting_id, None)
        self._audio_buffer.pop(meeting_id, None)

        return json.dumps(result, indent=2, ensure_ascii=False)

    async def meeting_status(self, meeting_id: str) -> str:
        meeting = self._active_meetings.get(meeting_id)
        if not meeting:
            return f"No active meeting: {meeting_id}"
        return json.dumps({
            "meeting_id": meeting_id,
            "title": meeting.title,
            "utterances_so_far": len(meeting.utterances),
            "duration_seconds": round(
                time.time() - (meeting.utterances[0].start_time if meeting.utterances else time.time()), 1
            ),
            "speakers": meeting.speakers,
        }, indent=2)

    async def _summarize(self, transcript: str) -> str:
        try:
            from backend.shared.llm_client import llm_client
            result = await llm_client.generate([
                {"role": "system", "content": "Summarize the following meeting transcript concisely. Focus on key decisions, discussion points, and outcomes."},
                {"role": "user", "content": transcript[:8000]},
            ])
            return result.content if hasattr(result, "content") else str(result)
        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return "Summarization unavailable"

    async def _extract_action_items(self, transcript: str) -> List[str]:
        try:
            from backend.shared.llm_client import llm_client
            result = await llm_client.generate([
                {"role": "system", "content": "Extract action items from this meeting transcript. Return as a JSON list of strings. Each item should be a clear task with owner if mentioned."},
                {"role": "user", "content": transcript[:6000]},
            ])
            text = result.content if hasattr(result, "content") else str(result)
            if "[" in text and "]" in text:
                import re
                match = re.search(r'\[.*?\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            return [line.strip("- ").strip() for line in text.split("\n") if line.strip().startswith("-")]
        except Exception as e:
            logger.warning(f"Action item extraction failed: {e}")
            return []

    async def _extract_topics(self, transcript: str) -> List[str]:
        try:
            from backend.shared.llm_client import llm_client
            result = await llm_client.generate([
                {"role": "system", "content": "Extract 3-5 key topics discussed in this meeting transcript. Return as a JSON list of short topic strings."},
                {"role": "user", "content": transcript[:6000]},
            ])
            text = result.content if hasattr(result, "content") else str(result)
            import re
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return [line.strip("- ").strip() for line in text.split("\n") if line.strip().startswith("-")]
        except Exception as e:
            logger.warning(f"Topic extraction failed: {e}")
            return []

    async def _store_transcript(self, meeting: MeetingTranscript):
        try:
            from backend.audio.audio_manager import AudioManager
            audio_manager = AudioManager()
            await audio_manager.initialize()
            transcript_text = "\n".join(
                f"[{u.speaker}] {u.text}" for u in meeting.utterances
            )
            await audio_manager.store_audio(
                audio_bytes=json.dumps({
                    "meeting_id": meeting.meeting_id,
                    "title": meeting.title,
                    "date": meeting.date,
                    "transcript": transcript_text,
                    "summary": meeting.summary,
                    "action_items": meeting.action_items,
                    "key_topics": meeting.key_topics,
                    "utterances": [(u.speaker, u.text, u.start_time, u.end_time) for u in meeting.utterances],
                }).encode(),
                format="json",
                category="recordings/meetings",
                transcript=transcript_text[:1000],
                speaker=", ".join(meeting.speakers),
                duration_ms=meeting.duration_seconds * 1000,
            )
        except Exception as e:
            logger.warning(f"Failed to store transcript: {e}")


meeting_transcriber = MeetingTranscriber()


async def start_meeting(title: str = "Untitled Meeting") -> str:
    return await meeting_transcriber.start_meeting(title)


async def process_meeting_audio(meeting_id: str, audio_b64: str, sample_rate: int = 16000) -> str:
    import base64
    audio_bytes = base64.b64decode(audio_b64)
    return await meeting_transcriber.process_audio_chunk(meeting_id, audio_bytes, sample_rate)


async def end_meeting(meeting_id: str, summarize: bool = True) -> str:
    return await meeting_transcriber.end_meeting(meeting_id, summarize)


async def meeting_status(meeting_id: str) -> str:
    return await meeting_transcriber.meeting_status(meeting_id)
