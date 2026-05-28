"""Color detection + Face & Emotion detection tools.

Adapted patterns from:
  - Chromalyze / ColorSense / Color Thief for color extraction
  - face_classification / DeepFace / YOLOv8 + HuggingFace for emotion/face analysis
"""

import json
import math
import logging
from typing import Optional
from collections import Counter

logger = logging.getLogger(__name__)

# ======================================================================
# COLOR DETECTION TOOLS
# ======================================================================

_NAMED_COLORS = {
    "red": (255,0,0), "green": (0,255,0), "blue": (0,0,255),
    "yellow": (255,255,0), "cyan": (0,255,255), "magenta": (255,0,255),
    "white": (255,255,255), "black": (0,0,0), "gray": (128,128,128),
    "orange": (255,165,0), "purple": (128,0,128), "pink": (255,192,203),
    "brown": (165,42,42), "navy": (0,0,128), "teal": (0,128,128),
    "maroon": (128,0,0), "olive": (128,128,0), "lime": (0,255,0),
    "aqua": (0,255,255), "silver": (192,192,192), "indigo": (75,0,130),
    "violet": (238,130,238), "gold": (255,215,0), "coral": (255,127,80),
    "salmon": (250,128,114), "tan": (210,180,140), "plum": (221,160,221),
    "orchid": (218,112,214), "chocolate": (210,105,30), "crimson": (220,20,60),
}

def _rgb_distance(a, b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))

def _nearest_named_color(r, g, b):
    best, best_name = float("inf"), "unknown"
    for name, rgb in _NAMED_COLORS.items():
        d = _rgb_distance((r,g,b), rgb)
        if d < best:
            best, best_name = d, name
    return best_name

def extract_dominant_colors(pixels: list, num_colors: int = 5) -> str:
    """Extract dominant colors from a list of [r,g,b] pixel arrays."""
    if not pixels:
        return json.dumps({"error": "No pixel data provided"})
    buckets = {}
    for p in pixels:
        if len(p) >= 3:
            r, g, b = int(p[0]), int(p[1]), int(p[2])
            key = (r//16*16, g//16*16, b//16*16)
            buckets[key] = buckets.get(key, 0) + 1
    top = sorted(buckets.items(), key=lambda x: -x[1])[:num_colors]
    results = []
    for (r, g, b), count in top:
        name = _nearest_named_color(r, g, b)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        pct = round(count / len(pixels) * 100, 1)
        results.append({"rgb": [r,g,b], "hex": hex_color, "name": name, "percentage": pct})
    return json.dumps({"dominant_colors": results, "total_pixels": len(pixels)})

def color_name_from_rgb(r: int, g: int, b: int) -> str:
    """Map RGB values to the nearest named color."""
    name = _nearest_named_color(r, g, b)
    hex_color = f"#{r:02x}{g:02x}{b:02x}"
    return json.dumps({"rgb": [r,g,b], "hex": hex_color, "name": name})

def color_name_from_hex(hex_color: str) -> str:
    """Map a hex color string (e.g. #ff5733) to the nearest named color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return json.dumps({"error": "Invalid hex color", "hex": hex_color})
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return color_name_from_rgb(r, g, b)

def color_palette_generate(base_color: str, num_shades: int = 5) -> str:
    """Generate a monochromatic palette from a hex color."""
    h = base_color.lstrip("#")
    if len(h) != 6:
        return json.dumps({"error": "Invalid hex color"})
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    palette = []
    for i in range(num_shades):
        f = (i + 1) / (num_shades + 1)
        nr = int(r * f)
        ng = int(g * f)
        nb = int(b * f)
        palette.append(f"#{nr:02x}{ng:02x}{nb:02x}")
    return json.dumps({"base": base_color, "palette": palette})

def color_analyze_image_url(image_url: str) -> str:
    """Analyze colors in an image from URL and return dominant color palette."""
    try:
        import requests
        from io import BytesIO
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
        from PIL import Image
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = img.resize((64, 64))
        pixels = list(img.getdata())
        return extract_dominant_colors(pixels, 8)
    except Exception as e:
        return json.dumps({"error": f"Failed to analyze image: {str(e)}"})

def color_analyze_local_image(file_path: str) -> str:
    """Analyze colors in a local image file."""
    try:
        from PIL import Image
        img = Image.open(file_path).convert("RGB")
        img = img.resize((64, 64))
        pixels = list(img.getdata())
        return extract_dominant_colors(pixels, 8)
    except Exception as e:
        return json.dumps({"error": f"Failed to analyze image: {str(e)}"})

# ======================================================================
# FACE + EMOTION DETECTION TOOLS
# ======================================================================

_EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

def _simulate_emotion_classify(pixels_description: str = "") -> dict:
    """Fallback emotion classification when no ML model is available."""
    return {
        "emotions": {e: round(1.0/7, 3) for e in _EMOTIONS},
        "dominant_emotion": "neutral",
        "confidence": 0.5,
        "model": "fallback-uniform"
    }

def detect_emotion_face(image_path: str) -> str:
    """Detect faces and classify emotions using DeepFace if available, else fallback."""
    try:
        from deepface import DeepFace
        result = DeepFace.analyze(img_path=image_path, actions=["emotion", "age", "gender", "race"],
                                  enforce_detection=False)
        if isinstance(result, list):
            result = result[0]
        emotions = result.get("emotion", {})
        dominant = result.get("dominant_emotion", "neutral")
        age = result.get("age", 0)
        gender = result.get("dominant_gender", "unknown")
        race = result.get("dominant_race", "unknown")
        region = result.get("region", {})
        return json.dumps({
            "face_detected": True,
            "dominant_emotion": dominant,
            "emotions": emotions,
            "age": age,
            "gender": gender,
            "race": race,
            "face_region": region,
            "model": "DeepFace"
        })
    except ImportError:
        logger.warning("DeepFace not installed; using fallback emotion analysis")
        return json.dumps(_simulate_emotion_classify())
    except Exception as e:
        return json.dumps({"error": f"Face/emotion detection failed: {str(e)}"})

def detect_emotion_text(text: str) -> str:
    """Analyze text for emotional sentiment using Hugging Face transformers if available."""
    try:
        from transformers import pipeline
        classifier = pipeline("text-classification",
                              model="bhadresh-savani/bert-base-uncased-emotion",
                              top_k=None)
        results = classifier(text)[0]
        emotions = {r["label"]: round(r["score"], 4) for r in results}
        dominant = max(emotions, key=emotions.get)
        return json.dumps({
            "text": text,
            "dominant_emotion": dominant,
            "emotions": emotions,
            "model": "bert-base-uncased-emotion"
        })
    except ImportError:
        logger.warning("transformers not installed; using rule-based text emotion")
        return json.dumps(_text_emotion_fallback(text))
    except Exception as e:
        return json.dumps({"error": f"Text emotion detection failed: {str(e)}"})

def _text_emotion_fallback(text: str) -> dict:
    text_lower = text.lower()
    scores = {"anger": 0, "fear": 0, "joy": 0, "sadness": 0, "surprise": 0, "neutral": 0}
    keywords = {
        "anger": ["angry", "furious", "hate", "mad", "annoyed", "frustrated", "rage", "irritated"],
        "fear": ["scared", "afraid", "worried", "anxious", "terrified", "nervous", "panic"],
        "joy": ["happy", "glad", "great", "wonderful", "excellent", "amazing", "love", "fantastic"],
        "sadness": ["sad", "depressed", "unhappy", "miserable", "cry", "disappointed", "down"],
        "surprise": ["wow", "unexpected", "shocked", "amazed", "astonished", "surprising"],
    }
    for emotion, words in keywords.items():
        for w in words:
            if w in text_lower:
                scores[emotion] += 1
    total = sum(scores.values())
    if total == 0:
        scores["neutral"] = 1.0
        dominant = "neutral"
    else:
        scores = {k: round(v/total, 3) for k, v in scores.items()}
        dominant = max(scores, key=scores.get)
    return {
        "text": text, "dominant_emotion": dominant,
        "emotions": scores, "model": "keyword-fallback"
    }

def detect_faces_image(image_path: str) -> str:
    """Detect faces in an image and return count and bounding boxes using YOLO/OpenCV."""
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return json.dumps({"error": f"Cannot read image: {image_path}"})
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        boxes = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                 for (x, y, w, h) in faces]
        return json.dumps({
            "face_count": len(boxes),
            "faces": boxes,
            "model": "OpenCV-HaarCascade"
        })
    except ImportError:
        return json.dumps({"error": "OpenCV (cv2) not installed"})
    except Exception as e:
        return json.dumps({"error": f"Face detection failed: {str(e)}"})

def analyze_face_attributes(image_path: str) -> str:
    """Analyze age, gender, emotion, and race from a face using DeepFace."""
    try:
        from deepface import DeepFace
        result = DeepFace.analyze(img_path=image_path,
                                  actions=["age", "gender", "emotion", "race"],
                                  enforce_detection=False)
        if isinstance(result, list):
            result = result[0]
        return json.dumps({
            "face_detected": True,
            "age": result.get("age"),
            "gender": result.get("dominant_gender"),
            "gender_confidence": result.get("gender", {}).get(result.get("dominant_gender", ""), 0),
            "emotion": result.get("dominant_emotion"),
            "emotion_scores": result.get("emotion", {}),
            "race": result.get("dominant_race"),
            "race_scores": result.get("race", {}),
            "model": "DeepFace"
        })
    except ImportError:
        return json.dumps({"error": "DeepFace not installed. Install with: pip install deepface"})
    except Exception as e:
        return json.dumps({"error": f"Face attribute analysis failed: {str(e)}"})

def compare_faces(image1_path: str, image2_path: str) -> str:
    """Compare two faces and return similarity score using DeepFace."""
    try:
        from deepface import DeepFace
        result = DeepFace.verify(img1_path=image1_path, img2_path=image2_path,
                                 enforce_detection=False)
        return json.dumps({
            "verified": bool(result.get("verified")),
            "distance": round(result.get("distance", 0), 4),
            "threshold": result.get("threshold", 0.68),
            "model": result.get("model", "VGG-Face"),
            "similarity_pct": round((1 - result.get("distance", 1)) * 100, 2)
        })
    except ImportError:
        return json.dumps({"error": "DeepFace not installed. Install with: pip install deepface"})
    except Exception as e:
        return json.dumps({"error": f"Face comparison failed: {str(e)}"})

def analyze_emotion_realtime(face_frame_pixels: str = "") -> str:
    """Placeholder for real-time emotion analysis from camera frame data."""
    return json.dumps({**{"status": "realtime_emotion_capture_ready",
                          "note": "Pass base64-encoded frame pixels for live inference"},
                       **_simulate_emotion_classify()})
