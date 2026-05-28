"""Face recognition and QR/barcode detection for J.A.R.V.I.S. vision."""

import cv2
import numpy as np
import logging
import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from backend.shared.config import settings

logger = logging.getLogger(__name__)


@dataclass
class FaceInfo:
    name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    landmarks: Optional[List[Tuple[int, int]]] = None
    encoding: Optional[np.ndarray] = None
    is_known: bool = False


@dataclass
class QRInfo:
    data: str
    type: str
    bbox: Tuple[int, int, int, int]
    text: str = ""


class FaceRecognizer:
    """Face recognition using face_recognition library or OpenCV fallback."""

    def __init__(self):
        self._known_encodings: Dict[str, np.ndarray] = {}
        self._known_names: List[str] = []
        self._known_faces: List[np.ndarray] = []
        self._use_fr = False
        self._fr = None

    def load_known_faces(self, faces_dir: str = "known_faces"):
        """Load known faces from a directory of images."""
        try:
            import face_recognition as fr
            self._fr = fr
            self._use_fr = True

            path = Path(faces_dir)
            if not path.exists():
                logger.info(f"No known_faces directory at {faces_dir}")
                return

            for img_path in path.glob("*"):
                if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue
                try:
                    image = fr.load_image_file(str(img_path))
                    encodings = fr.face_encodings(image)
                    if encodings:
                        name = img_path.stem
                        self._known_encodings[name] = encodings[0]
                        self._known_names.append(name)
                        self._known_faces.append(encodings[0])
                        logger.info(f"Loaded known face: {name}")
                except Exception as e:
                    logger.warning(f"Failed to load {img_path}: {e}")

            logger.info(f"Loaded {len(self._known_names)} known faces")
        except ImportError:
            logger.warning("face_recognition not installed, using OpenCV fallback")
            self._use_fr = False

    def recognize(self, frame: np.ndarray) -> List[FaceInfo]:
        """Detect and recognize faces in a frame."""
        faces = []

        if self._use_fr and self._fr:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = self._fr.face_locations(rgb, model="hog")
                face_encodings = self._fr.face_encodings(rgb, face_locations)

                for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                    name = "Unknown"
                    confidence = 0.0

                    if self._known_faces:
                        matches = self._fr.compare_faces(self._known_faces, encoding, tolerance=0.5)
                        if True in matches:
                            match_idx = matches.index(True)
                            name = self._known_names[match_idx]
                        face_distances = self._fr.face_distance(self._known_faces, encoding)
                        if len(face_distances) > 0:
                            confidence = 1.0 - min(face_distances)

                    faces.append(FaceInfo(
                        name=name,
                        confidence=round(confidence, 3),
                        bbox=(left, top, right, bottom),
                        is_known=name != "Unknown",
                    ))
            except Exception as e:
                logger.error(f"Face recognition error: {e}")

        else:
            # OpenCV Haar cascade fallback
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = cascade.detectMultiScale(gray, 1.1, 4)
            for x, y, w, h in detections:
                faces.append(FaceInfo(
                    name="Unknown",
                    confidence=0.5,
                    bbox=(x, y, x + w, y + h),
                    is_known=False,
                ))

        return faces

    def add_known_face(self, name: str, encoding: np.ndarray):
        self._known_encodings[name] = encoding
        self._known_names.append(name)
        self._known_faces.append(encoding)


class QRDetector:
    """QR code and barcode detection."""

    def __init__(self):
        self._detector = None

    def detect(self, frame: np.ndarray) -> List[QRInfo]:
        """Detect QR codes and barcodes in a frame."""
        results = []

        try:
            from pyzbar.pyzbar import decode as pyzbar_decode
            decoded = pyzbar_decode(frame)
            for obj in decoded:
                results.append(QRInfo(
                    data=obj.data.decode("utf-8", errors="ignore"),
                    type=obj.type,
                    bbox=(obj.rect.left, obj.rect.top,
                          obj.rect.left + obj.rect.width,
                          obj.rect.top + obj.rect.height),
                ))

        except ImportError:
            # OpenCV QR detector fallback
            detector = cv2.QRCodeDetector()
            data, points, _ = detector.detectAndDecode(frame)
            if data:
                if points is not None and len(points) > 0:
                    x, y = int(points[0][0][0]), int(points[0][0][1])
                    w = int(points[1][0][0] - points[0][0][0])
                    h = int(points[2][0][1] - points[0][0][1])
                else:
                    x, y, w, h = 0, 0, 0, 0

                results.append(QRInfo(
                    data=data,
                    type="QRCODE",
                    bbox=(x, y, x + w, y + h),
                ))

        return results


class VisionPipeline:
    """Combined face + QR + object detection pipeline."""

    def __init__(self):
        self.face_recognizer = FaceRecognizer()
        self.qr_detector = QRDetector()

    def process(self, frame: np.ndarray) -> Dict:
        faces = self.face_recognizer.recognize(frame)
        qrs = self.qr_detector.detect(frame)

        return {
            "faces": [
                {
                    "name": f.name,
                    "confidence": f.confidence,
                    "is_known": f.is_known,
                    "bbox": f.bbox,
                }
                for f in faces
            ],
            "qr_codes": [
                {
                    "data": q.data,
                    "type": q.type,
                    "text": q.text or q.data[:100],
                }
                for q in qrs
            ],
            "face_count": len(faces),
            "qr_count": len(qrs),
        }


pipeline = VisionPipeline()
