"""Avatar expression and animation service for the 3D frontend.

Maps emotions and speech to facial expressions, head movements,
and body language for the Three.js avatar.
"""

import logging
import math
import random
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Emotion → facial expression blend shapes
EXPRESSION_MAP = {
    "neutral": {
        "browRaise": 0.0,
        "browFrown": 0.0,
        "mouthSmile": 0.0,
        "mouthOpen": 0.0,
        "eyeSquint": 0.0,
        "lookUp": 0.0,
        "lookDown": 0.0,
        "lookLeft": 0.0,
        "lookRight": 0.0,
        "blink": 0.0,
    },
    "happy": {
        "browRaise": 0.2,
        "browFrown": 0.0,
        "mouthSmile": 0.8,
        "mouthOpen": 0.3,
        "eyeSquint": 0.3,
        "lookUp": 0.0,
        "blink": 0.0,
    },
    "excited": {
        "browRaise": 0.8,
        "browFrown": 0.0,
        "mouthSmile": 1.0,
        "mouthOpen": 0.6,
        "eyeSquint": 0.2,
        "lookUp": 0.1,
        "blink": 0.0,
    },
    "sad": {
        "browRaise": 0.0,
        "browFrown": 0.6,
        "mouthSmile": 0.0,
        "mouthOpen": 0.1,
        "eyeSquint": 0.1,
        "lookDown": 0.3,
        "blink": 0.2,
    },
    "angry": {
        "browRaise": 0.0,
        "browFrown": 0.9,
        "mouthSmile": 0.0,
        "mouthOpen": 0.2,
        "eyeSquint": 0.7,
        "blink": 0.0,
    },
    "calm": {
        "browRaise": 0.0,
        "browFrown": 0.0,
        "mouthSmile": 0.3,
        "mouthOpen": 0.0,
        "eyeSquint": 0.0,
        "blink": 0.1,
    },
    "confused": {
        "browRaise": 0.5,
        "browFrown": 0.3,
        "mouthSmile": 0.0,
        "mouthOpen": 0.2,
        "eyeSquint": 0.4,
        "lookLeft": 0.2,
        "blink": 0.1,
    },
    "thinking": {
        "browRaise": 0.0,
        "browFrown": 0.4,
        "mouthSmile": 0.0,
        "mouthOpen": 0.0,
        "eyeSquint": 0.5,
        "lookUp": 0.2,
        "lookRight": 0.1,
        "blink": 0.05,
    },
}

# Viseme → mouth shape map for lip sync
VISEME_SHAPES = {
    "rest": {"mouthOpen": 0.0, "mouthSmile": 0.0},
    "A": {"mouthOpen": 0.7, "mouthSmile": 0.1},
    "E": {"mouthOpen": 0.3, "mouthSmile": 0.5},
    "I": {"mouthOpen": 0.2, "mouthSmile": 0.6},
    "O": {"mouthOpen": 0.6, "mouthSmile": 0.0},
    "U": {"mouthOpen": 0.4, "mouthSmile": 0.0},
    "M": {"mouthOpen": 0.0, "mouthSmile": 0.2},
    "F": {"mouthOpen": 0.1, "mouthSmile": 0.1},
    "L": {"mouthOpen": 0.0, "mouthSmile": 0.0},
}


def get_expression(emotion: str) -> Dict[str, float]:
    """Get facial expression blend shapes for a given emotion."""
    base = EXPRESSION_MAP.get(emotion, EXPRESSION_MAP["neutral"])
    result = dict(base)
    result["blink"] = result.get("blink", 0.0)
    return result


def get_viseme_shape(viseme: str) -> Dict[str, float]:
    """Get mouth shape values for a viseme."""
    return VISEME_SHAPES.get(viseme, VISEME_SHAPES["rest"])


def animate_expression(from_emotion: str, to_emotion: str,
                       progress: float) -> Dict[str, float]:
    """Interpolate between two expressions by progress (0.0-1.0)."""
    from_expr = get_expression(from_emotion)
    to_expr = get_expression(to_emotion)
    result = {}
    all_keys = set(from_expr.keys()) | set(to_expr.keys())
    for key in all_keys:
        fv = from_expr.get(key, 0.0)
        tv = to_expr.get(key, 0.0)
        result[key] = fv + (tv - fv) * progress
    return result


def get_head_movement(speaking: bool = False) -> Dict[str, float]:
    """Generate subtle head movement for natural appearance."""
    return {
        "rotateX": math.sin(random.random() * math.pi * 2) * (5 if speaking else 2),
        "rotateY": math.sin(random.random() * math.pi * 2) * (3 if speaking else 1),
        "rotateZ": 0.0,
    }


def get_idle_animation() -> Dict[str, float]:
    """Generate idle animation values (blinking, micro-movements)."""
    should_blink = random.random() < 0.02
    return {
        "blink": 1.0 if should_blink else 0.0,
        "scleraX": math.sin(time.time() * 0.3) * 0.05,
        "scleraY": math.sin(time.time() * 0.2) * 0.03,
    }


def get_body_language(emotion: str) -> List[Dict[str, Any]]:
    """Get body language gestures for an emotion."""
    gestures = {
        "happy": [{"type": "nod", "intensity": 0.3, "duration": 0.5}],
        "excited": [
            {"type": "nod", "intensity": 0.6, "duration": 0.8},
            {"type": "hand_gesture", "intensity": 0.5, "duration": 1.0},
        ],
        "sad": [{"type": "shrug", "intensity": 0.2, "duration": 1.0}],
        "angry": [{"type": "lean_forward", "intensity": 0.4, "duration": 0.6}],
        "calm": [{"type": "nod", "intensity": 0.15, "duration": 0.8}],
        "thinking": [{"type": "tilt_head", "intensity": 0.3, "duration": 1.5}],
        "confused": [{"type": "tilt_head", "intensity": 0.5, "duration": 1.2}],
        "neutral": [],
    }
    return gestures.get(emotion, [])


import time  # noqa: E402
