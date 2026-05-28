"""Lip sync viseme generation for avatar mouth animation.

Maps phonemes to mouth shapes for real-time avatar lip sync.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class LipSyncFrame:
    shape: str
    start_ms: float
    end_ms: float
    intensity: float = 1.0

    MOUTH_SHAPES = {
        "rest": {"jaw": 0, "lips": "closed", "tongue": "down"},
        "A": {"jaw": 8, "lips": "open", "tongue": "down"},
        "E": {"jaw": 6, "lips": "wide", "tongue": "mid"},
        "I": {"jaw": 5, "lips": "slight_open", "tongue": "up"},
        "O": {"jaw": 7, "lips": "rounded", "tongue": "down"},
        "U": {"jaw": 4, "lips": "pursed", "tongue": "up"},
        "M": {"jaw": 0, "lips": "closed", "tongue": "down"},
        "F": {"jaw": 1, "lips": "bite", "tongue": "down"},
        "L": {"jaw": 3, "lips": "slight_open", "tongue": "up"},
    }


class LipSyncGenerator:
    """Generates lip sync data for the 3D avatar."""

    def __init__(self):
        self._visemes: List[LipSyncFrame] = []

    def from_tts_visemes(self, viseme_data: List[Dict]) -> List[LipSyncFrame]:
        """Convert TTS viseme data to lip sync frames."""
        frames = []
        for v in viseme_data:
            shape = v.get("shape", "rest")
            mouth_data = LipSyncFrame.MOUTH_SHAPES.get(shape, LipSyncFrame.MOUTH_SHAPES["rest"])
            frame = LipSyncFrame(
                shape=shape,
                start_ms=v.get("start_ms", 0),
                end_ms=v.get("end_ms", 100),
                intensity=max(0.1, min(1.0, (v.get("end_ms", 100) - v.get("start_ms", 0)) / 150)),
            )
            frames.append(frame)
        return frames

    def smooth_frames(self, frames: List[LipSyncFrame]) -> List[LipSyncFrame]:
        """Apply smoothing between consecutive frames."""
        if len(frames) < 2:
            return frames

        smoothed = [frames[0]]
        for i in range(1, len(frames)):
            prev = frames[i - 1]
            curr = frames[i]

            gap = curr.start_ms - prev.end_ms
            if gap > 20:
                smoothed.append(LipSyncFrame(
                    shape="rest",
                    start_ms=prev.end_ms,
                    end_ms=curr.start_ms,
                    intensity=0.1,
                ))

            t = curr.start_ms
            while t < curr.end_ms:
                blend = (t - curr.start_ms) / max(curr.end_ms - curr.start_ms, 1)
                shape = curr.shape if blend > 0.3 else prev.shape
                intensity = prev.intensity * (1 - blend) + curr.intensity * blend
                smoothed.append(LipSyncFrame(
                    shape=shape,
                    start_ms=t,
                    end_ms=min(t + 30, curr.end_ms),
                    intensity=intensity,
                ))
                t += 30

        return smoothed

    def to_animation_data(self, frames: List[LipSyncFrame]) -> Dict:
        """Convert frames to frontend-compatible animation data."""
        return {
            "frames": [
                {
                    "shape": f.shape,
                    "mouth": LipSyncFrame.MOUTH_SHAPES.get(f.shape, LipSyncFrame.MOUTH_SHAPES["rest"]),
                    "start_ms": f.start_ms,
                    "end_ms": f.end_ms,
                    "intensity": f.intensity,
                }
                for f in frames
            ],
            "total_duration_ms": frames[-1].end_ms if frames else 0,
            "fps": 30,
        }


lip_sync_gen = LipSyncGenerator()
