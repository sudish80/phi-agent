"""Vision Service — object detection, face recognition, QR/barcode, frame capture.

FastAPI endpoints:
  - POST /detect: image → detected objects, colors, scene
  - POST /recognize: image → faces, QR codes
  - POST /process: image → full vision pipeline (detect + recognize)
  - GET /camera/start: start camera capture
  - GET /camera/frame: get latest camera frame as base64
  - GET /camera/stop: stop camera capture
  - GET /health: service health
"""

import asyncio
import base64
import json
import logging
import time
from typing import Optional

import uvicorn
import numpy as np
import cv2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.shared.config import settings
from backend.vision.detector import pipeline as detector_pipeline
from backend.vision.frame_capture import capture as frame_capture
from backend.vision.recognizer import pipeline as vision_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="J.A.R.V.I.S. Vision Service", version="1.0.0")


class ImageRequest(BaseModel):
    image: str  # base64-encoded JPEG
    conf_threshold: float = 0.4


class DetectResponse(BaseModel):
    objects: list
    labels: list
    dominant_colors: list
    scene_type: str
    anomalies: list
    detection_time_ms: float
    object_count: int


class RecognizeResponse(BaseModel):
    faces: list
    qr_codes: list
    face_count: int
    qr_count: int


class ProcessResponse(BaseModel):
    detection: dict
    recognition: dict
    processed_at: float


@app.post("/detect", response_model=DetectResponse)
async def detect_objects(req: ImageRequest):
    """Detect objects, colors, and scene type in an image."""
    try:
        frame = _decode_image(req.image)
        result = detector_pipeline.process(frame)
        return result
    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/recognize", response_model=RecognizeResponse)
async def recognize_faces(req: ImageRequest):
    """Recognize faces and detect QR/barcodes in an image."""
    try:
        frame = _decode_image(req.image)
        result = vision_pipeline.process(frame)
        return result
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/process", response_model=ProcessResponse)
async def process_scene(req: ImageRequest):
    """Full vision pipeline: detect + recognize."""
    try:
        frame = _decode_image(req.image)
        detection = detector_pipeline.process(frame)
        recognition = vision_pipeline.process(frame)
        return {
            "detection": detection,
            "recognition": recognition,
            "processed_at": time.time(),
        }
    except Exception as e:
        logger.error(f"Process error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/camera/start")
async def start_camera(source: Optional[str] = None):
    """Start camera capture (webcam, rtsp://, or screen)."""
    ok = frame_capture.start(source)
    if ok:
        return {"status": "started", "source": source or "webcam", "fps": 0}
    raise HTTPException(status_code=500, detail="Failed to start camera")


@app.get("/camera/frame")
async def get_camera_frame():
    """Get latest camera frame as base64 JPEG."""
    b64 = frame_capture.get_frame_base64()
    if b64:
        return {"image": b64, "fps": frame_capture.get_fps(), "frames": frame_capture.get_frame_count()}
    raise HTTPException(status_code=404, detail="No frame available")


@app.get("/camera/stop")
async def stop_camera():
    """Stop camera capture."""
    frame_capture.stop()
    return {"status": "stopped"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "vision",
        "version": "1.0.0",
        "camera_running": frame_capture._running if hasattr(frame_capture, "_running") else False,
    }


def _decode_image(b64: str) -> np.ndarray:
    """Decode a base64 JPEG string to a numpy array (BGR)."""
    img_bytes = base64.b64decode(b64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Failed to decode image")
    return frame


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    uvicorn.run(
        "backend.vision.service:app",
        host="0.0.0.0",
        port=settings.vision_port,
        reload=True,
    )
