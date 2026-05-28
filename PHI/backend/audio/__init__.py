from backend.audio.audio_manager import AudioManager
from backend.audio.scheduler import AudioScheduler
from backend.audio.models import AudioEntry, AudioSearchResult, AudioCategory

audio_manager = AudioManager()
audio_scheduler = AudioScheduler(audio_manager)

__all__ = ["AudioManager", "AudioScheduler", "AudioEntry", "AudioSearchResult", "AudioCategory", "audio_manager", "audio_scheduler"]
