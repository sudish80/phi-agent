"""2D Equalizer visualizer — provides frequency band data for the frontend.

Replaces the 3D avatar system with real-time audio visualization data:
  - Equalizer frequency bands (24 bands)
  - Amplitude envelope
  - Mode (speaking/listening/idle) transitions
  - Emotion color mapping
"""

import logging
import math
import random
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Emotion → color mapping for the 2D equalizer
EMOTION_COLORS = {
    "neutral":  {"primary": "#00d4ff", "secondary": "#004466", "accent": "#0077aa"},
    "happy":    {"primary": "#00ff88", "secondary": "#006633", "accent": "#00cc66"},
    "serious":  {"primary": "#4488ff", "secondary": "#003366", "accent": "#2266cc"},
    "excited":  {"primary": "#ff6600", "secondary": "#663300", "accent": "#cc5500"},
    "calm":     {"primary": "#88ddff", "secondary": "#224466", "accent": "#5599bb"},
    "angry":    {"primary": "#ff2244", "secondary": "#660011", "accent": "#cc1133"},
    "sad":      {"primary": "#6688cc", "secondary": "#223366", "accent": "#4466aa"},
    "whisper":  {"primary": "#aabbdd", "secondary": "#334466", "accent": "#7788aa"},
}

BAR_COUNT = 24


def get_equalizer_data(audio_level: float = 0.5,
                       is_speaking: bool = False,
                       is_listening: bool = False) -> Dict[str, Any]:
    """Generate simulated frequency band data for the equalizer display.

    Args:
        audio_level: Base amplitude (0.0-1.0)
        is_speaking: Whether the agent is producing audio
        is_listening: Whether the agent is receiving audio

    Returns:
        Dict with 'bands' (list of 24 float 0-255), 'amplitude' (float),
        'mode' (string), and 'timestamp'
    """
    now = time.time()
    mode = "speaking" if is_speaking else ("listening" if is_listening else "idle")
    intensity = audio_level if (is_speaking or is_listening) else 0.05

    bands = []
    for i in range(BAR_COUNT):
        freq = (i / BAR_COUNT) * math.pi * 4
        envelope = math.exp(-i * 0.08)
        wave = math.sin(now * (3 + i * 1.5) + freq) * 0.5 + 0.5
        noise = random.random() * 0.15
        val = (wave * envelope * 0.8 + noise) * intensity * 255
        bands.append(min(255, max(0, int(val))))

    return {
        "bands": bands,
        "amplitude": round(intensity, 3),
        "mode": mode,
        "timestamp": now,
        "bar_count": BAR_COUNT,
    }


def get_equalizer_color(emotion: str) -> Dict[str, str]:
    """Get the color palette for an emotion."""
    return EMOTION_COLORS.get(emotion, EMOTION_COLORS["neutral"])


def interpolate_equalizer(from_bands: List[int],
                          to_bands: List[int],
                          progress: float) -> List[int]:
    """Interpolate between two equalizer band states."""
    result = []
    for i in range(max(len(from_bands), len(to_bands))):
        fv = from_bands[i] if i < len(from_bands) else 0
        tv = to_bands[i] if i < len(to_bands) else 0
        result.append(int(fv + (tv - fv) * progress))
    return result
