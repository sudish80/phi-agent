"""Object detection using YOLOv8 with color detection.

Detects objects, people, animals, and extracts dominant colors.
"""

import cv2
import numpy as np
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from backend.shared.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    color: Optional[str] = None
    dominant_colors: List[Dict] = field(default_factory=list)


@dataclass
class DetectionResult:
    objects: List[DetectedObject] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    detection_time_ms: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    dominant_colors: List[Dict] = field(default_factory=list)


class YOLODetector:
    """YOLOv8 object detector with fallback to lightweight detector."""

    def __init__(self):
        self._model = None
        self._model_loaded = False
        self._use_haar = False
        self._haar_cascade = None

    def load_model(self):
        """Load YOLOv8 model, with fallback to Haar cascades."""
        try:
            from ultralytics import YOLO
            self._model = YOLO("yolov8n.pt")
            self._model_loaded = True
            logger.info("YOLOv8 nano model loaded")
        except ImportError:
            logger.warning("ultralytics not installed, using Haar cascade fallback")
            self._use_haar = True
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar_cascade = cv2.CascadeClassifier(cascade_path)
            self._model_loaded = True

    def detect(self, frame: np.ndarray, conf_threshold: float = 0.4) -> DetectionResult:
        """Run detection on a frame."""
        if not self._model_loaded:
            self.load_model()

        start = time.time()
        result = DetectionResult(
            frame_width=frame.shape[1],
            frame_height=frame.shape[0],
        )

        if self._use_haar:
            result = self._detect_haar(frame, result)
        else:
            result = self._detect_yolo(frame, result, conf_threshold)

        result.dominant_colors = self._extract_dominant_colors(frame, n_colors=5)
        result.detection_time_ms = (time.time() - start) * 1000

        return result

    def _detect_yolo(self, frame: np.ndarray, result: DetectionResult,
                     conf_threshold: float) -> DetectionResult:
        try:
            predictions = self._model(frame, verbose=False)
            for pred in predictions:
                boxes = pred.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        label = pred.names[cls_id]

                        if conf < conf_threshold:
                            continue

                        obj_color = self._get_object_color(frame, x1, y1, x2, y2)
                        detected = DetectedObject(
                            label=label,
                            confidence=conf,
                            bbox=(x1, y1, x2, y2),
                            color=obj_color,
                            dominant_colors=self._extract_dominant_colors(
                                frame[y1:y2, x1:x2], 3
                            ),
                        )
                        result.objects.append(detected)
                        if label not in result.labels:
                            result.labels.append(label)
        except Exception as e:
            logger.error(f"YOLO detection error: {e}")
        return result

    def _detect_haar(self, frame: np.ndarray, result: DetectionResult) -> DetectionResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._haar_cascade.detectMultiScale(gray, 1.1, 4)
        for x, y, w, h in faces:
            detected = DetectedObject(
                label="face",
                confidence=0.8,
                bbox=(x, y, x + w, y + h),
                color=self._get_object_color(frame, x, y, x + w, y + h),
            )
            result.objects.append(detected)
        if faces:
            result.labels.append("face")
        return result

    def _get_object_color(self, frame: np.ndarray, x1: int, y1: int,
                          x2: int, y2: int) -> str:
        """Get the dominant color name of a detected object."""
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return "unknown"
        avg_color = roi.mean(axis=0).mean(axis=0)
        b, g, r = avg_color
        return self._color_name(r, g, b)

    def _extract_dominant_colors(self, frame: np.ndarray,
                                  n_colors: int = 5) -> List[Dict]:
        """Extract dominant colors using K-means clustering."""
        if frame.size == 0:
            return []
        try:
            pixels = frame.reshape(-1, 3)
            pixels = pixels[::10]

            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=min(n_colors, len(pixels)), random_state=0, n_init=1)
            kmeans.fit(pixels)

            colors = []
            total = len(pixels)
            for center, count in zip(kmeans.cluster_centers_,
                                      np.bincount(kmeans.labels_, minlength=n_colors)):
                b, g, r = center
                name = self._color_name(r, g, b)
                colors.append({
                    "color": name,
                    "rgb": f"rgb({int(r)},{int(g)},{int(b)})",
                    "hex": f"#{int(r):02x}{int(g):02x}{int(b):02x}",
                    "percentage": float(count / total * 100),
                })
            return sorted(colors, key=lambda x: x["percentage"], reverse=True)
        except Exception as e:
            logger.error(f"Color extraction error: {e}")
            return []

    def _color_name(self, r: float, g: float, b: float) -> str:
        """Map RGB values to named colors."""
        colors = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "cyan": (0, 255, 255),
            "magenta": (255, 0, 255),
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "gray": (128, 128, 128),
            "orange": (255, 165, 0),
            "purple": (128, 0, 128),
            "pink": (255, 192, 203),
            "brown": (165, 42, 42),
            "navy": (0, 0, 128),
            "teal": (0, 128, 128),
            "maroon": (128, 0, 0),
            "olive": (128, 128, 0),
            "coral": (255, 127, 80),
            "indigo": (75, 0, 130),
            "gold": (255, 215, 0),
            "silver": (192, 192, 192),
            "beige": (245, 245, 220),
            "ivory": (255, 255, 240),
            "lavender": (230, 230, 250),
        }

        min_dist = float("inf")
        best_name = "unknown"
        for name, (cr, cg, cb) in colors.items():
            dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
            if dist < min_dist:
                min_dist = dist
                best_name = name
        return best_name

    def detect_anomaly(self, result: DetectionResult) -> List[str]:
        """Flag unexpected objects that could be anomalies."""
        anomalies = []
        expected_indoor = {"person", "chair", "table", "tv", "book", "bottle",
                           "cup", "laptop", "cell phone", "remote"}
        expected_outdoor = {"person", "car", "truck", "bicycle", "dog", "cat",
                            "tree", "bird"}

        for obj in result.objects:
            if obj.label not in expected_indoor and obj.label not in expected_outdoor:
                if obj.confidence > 0.7:
                    anomalies.append(f"Unexpected object: {obj.label} "
                                     f"({obj.confidence:.1%})")
        return anomalies


class DetectorPipeline:
    """Pipeline combining YOLO detection, color analysis, and anomaly detection."""

    def __init__(self):
        self.yolo = YOLODetector()

    def process(self, frame: np.ndarray) -> Dict[str, Any]:
        detection = self.yolo.detect(frame)
        anomalies = self.yolo.detect_anomaly(detection)

        scene = self._classify_scene(detection)

        return {
            "objects": [
                {
                    "label": obj.label,
                    "confidence": round(obj.confidence, 3),
                    "color": obj.color,
                    "position": {
                        "x": obj.bbox[0],
                        "y": obj.bbox[1],
                        "width": obj.bbox[2] - obj.bbox[0],
                        "height": obj.bbox[3] - obj.bbox[1],
                    },
                }
                for obj in detection.objects
            ],
            "labels": list(set(detection.labels)),
            "dominant_colors": detection.dominant_colors,
            "scene_type": scene,
            "anomalies": anomalies,
            "detection_time_ms": round(detection.detection_time_ms, 2),
            "object_count": len(detection.objects),
        }

    def _classify_scene(self, detection: DetectionResult) -> str:
        labels = set(detection.labels)
        if "tv" in labels or "laptop" in labels:
            return "indoor_entertainment"
        if "car" in labels or "truck" in labels:
            return "outdoor_street"
        if "person" in labels and len(detection.objects) > 2:
            return "social_gathering"
        if "book" in labels:
            return "study"
        if "bed" in labels:
            return "bedroom"
        if labels:
            return "indoor"
        return "empty_or_unrecognized"


pipeline = DetectorPipeline()
