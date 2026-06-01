import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_FRAME_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "workspace",
    "frames",
)


def extract_frames(video_path: str, output_dir: Optional[str] = None, fps: int = 1) -> list[str]:
    logger.info("Extracting frames from: %s (fps=%d)", video_path, fps)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    frame_dir = output_dir or os.path.join(DEFAULT_FRAME_DIR, uuid.uuid4().hex[:12])
    os.makedirs(frame_dir, exist_ok=True)

    frame_paths = []
    for i in range(3):
        frame_name = f"frame_{i:04d}.jpg"
        frame_path = os.path.join(frame_dir, frame_name)
        with open(frame_path, "w") as f:
            f.write(f"DUMMY_FRAME:{video_path}:{i}")
        frame_paths.append(frame_path)

    logger.info("Extracted %d frames to %s", len(frame_paths), frame_dir)
    return frame_paths


def combine_frames(frame_paths: list[str], output_path: Optional[str] = None, fps: int = 24) -> str:
    logger.info("Combining %d frames (fps=%d)", len(frame_paths), fps)
    for fp in frame_paths:
        if not os.path.exists(fp):
            raise FileNotFoundError(f"Frame not found: {fp}")

    out = output_path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "workspace",
        f"output_{uuid.uuid4().hex[:12]}.mp4",
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)

    with open(out, "w") as f:
        f.write(f"DUMMY_VIDEO:{len(frame_paths)}_frames")
    logger.info("Combined video written to: %s", out)
    return out


def video_to_text(video_path: str) -> str:
    logger.info("Transcribing video: %s", video_path)
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        with open(video_path, "r") as f:
            content = f.read()
        if content.startswith("DUMMY_VIDEO:"):
            parts = content.split(":", 1)
            if len(parts) > 1:
                return f"[Video description: combined video with {parts[1]}]"
        elif content.startswith("DUMMY_FRAME:"):
            parts = content.split(":", 2)
            source = parts[1] if len(parts) > 1 else "unknown"
            return f"[Video description: single frame from {os.path.basename(source)}]"
    except (OSError, UnicodeDecodeError):
        pass

    return f"[Dummy video description for {os.path.basename(video_path)}]"
