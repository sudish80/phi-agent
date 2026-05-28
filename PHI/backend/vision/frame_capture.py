"""Frame capture from webcam, IP camera (RTSP), or screen.

Supports multiple sources with background capture thread.
"""

import cv2
import numpy as np
import logging
import asyncio
import threading
import time
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

from backend.shared.config import settings

logger = logging.getLogger(__name__)


class CaptureSource(Enum):
    WEBCAM = "webcam"
    RTSP = "rtsp"
    SCREEN = "screen"


@dataclass
class Frame:
    data: np.ndarray
    timestamp: float
    source: CaptureSource
    width: int = 0
    height: int = 0
    channels: int = 3


class FrameCapture:
    """Background frame capture from multiple sources."""

    def __init__(self):
        self._capture: Optional[cv2.VideoCapture] = None
        self._source: CaptureSource = CaptureSource.WEBCAM
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[Frame] = None
        self._frame_history: deque = deque(maxlen=100)
        self._fps = 0.0
        self._frame_count = 0
        self._last_frame_time = 0.0

    def start(self, source: Optional[str] = None) -> bool:
        """Start capturing from the specified source."""
        if self._running:
            return True

        if source and source.startswith("rtsp://"):
            self._source = CaptureSource.RTSP
            self._capture = cv2.VideoCapture(source)
        elif source == "screen":
            self._source = CaptureSource.SCREEN
            try:
                import pyautogui
                self._capture = None
            except ImportError:
                logger.warning("pyautogui not installed, falling back to webcam")
                self._source = CaptureSource.WEBCAM
                self._capture = cv2.VideoCapture(settings.camera_index)
        else:
            self._source = CaptureSource.WEBCAM
            self._capture = cv2.VideoCapture(settings.camera_index)

        if self._source != CaptureSource.SCREEN and self._capture and not self._capture.isOpened():
            logger.error("Failed to open camera")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"Frame capture started: {self._source.value}")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._capture:
            self._capture.release()
        logger.info("Frame capture stopped")

    def _capture_loop(self):
        """Background capture loop running at max FPS."""
        while self._running:
            frame = self._grab_frame()
            if frame is not None:
                with self._lock:
                    self._latest_frame = frame
                    self._frame_history.append(frame)
                    self._frame_count += 1

                    now = time.time()
                    if self._last_frame_time > 0:
                        self._fps = 0.9 * self._fps + 0.1 / (now - self._last_frame_time)
                    self._last_frame_time = now

            time.sleep(0.01)

    def _grab_frame(self) -> Optional[Frame]:
        """Grab a single frame from the active source."""
        try:
            if self._source == CaptureSource.SCREEN:
                import pyautogui
                screenshot = pyautogui.screenshot()
                frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            else:
                ret, frame = self._capture.read()
                if not ret:
                    return None

            h, w = frame.shape[:2]
            c = frame.shape[2] if len(frame.shape) > 2 else 1

            return Frame(
                data=frame,
                timestamp=time.time(),
                source=self._source,
                width=w,
                height=h,
                channels=c,
            )
        except Exception as e:
            logger.error(f"Frame grab error: {e}")
            return None

    def get_latest_frame(self) -> Optional[Frame]:
        """Get the most recent frame."""
        with self._lock:
            if self._latest_frame is not None:
                return Frame(
                    data=self._latest_frame.data.copy(),
                    timestamp=self._latest_frame.timestamp,
                    source=self._latest_frame.source,
                    width=self._latest_frame.width,
                    height=self._latest_frame.height,
                )
            return None

    def get_frame_base64(self) -> Optional[str]:
        """Get the latest frame as a base64-encoded JPEG string."""
        frame = self.get_latest_frame()
        if frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame.data, [cv2.IMWRITE_JPEG_QUALITY, 85])
        import base64
        return base64.b64encode(buffer).decode("utf-8")

    def get_fps(self) -> float:
        return self._fps

    def get_frame_count(self) -> int:
        return self._frame_count

    def get_history_length(self) -> int:
        return len(self._frame_history)


capture = FrameCapture()
