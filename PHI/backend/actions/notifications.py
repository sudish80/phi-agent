"""Notification module for J.A.R.V.I.S.

Desktop push notifications and message sending.
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def notify_desktop(title: str, message: str) -> str:
    """Send a desktop notification."""
    loop = asyncio.get_event_loop()

    def _notify():
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=10,
                app_name="J.A.R.V.I.S.",
            )
            return f"Notification sent: {title}"
        except ImportError:
            return "Desktop notifications require plyer"
        except Exception as e:
            return f"Notification error: {e}"

    return await loop.run_in_executor(None, _notify)


async def notify_sound(message: str) -> str:
    """Play a text-to-speech notification sound (uses TTS engine)."""
    try:
        from backend.speech.tts_engine import JarvisTTS
        tts = JarvisTTS()
        await tts.synthesize(message)
        return f"Spoken notification: {message}"
    except Exception as e:
        return f"Sound notification error: {e}"
