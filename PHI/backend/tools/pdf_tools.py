"""PDF Enhancement Tools — wraps pdf_enhancer (ItsSp00ky/pdf_enhancer) for scanned PDF/image cleanup.

Dependencies: PyMuPDF, opencv-python, numpy
"""

import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports for optional heavy deps
_cv2 = None
_fitz = None
_PIL_Image = None

def _ensure_deps():
    global _cv2, _fitz, _PIL_Image
    if _cv2 is None:
        import cv2 as _cv2_mod
        _cv2 = _cv2_mod
    if _fitz is None:
        import fitz as _fitz_mod
        _fitz = _fitz_mod
    if _PIL_Image is None:
        from PIL import Image as _PIL_Image_mod
        _PIL_Image = _PIL_Image_mod


def _save_as_pdf(pil_images, output_path):
    _ensure_deps()
    doc = _fitz.open()
    for pil_img in pil_images:
        arr = np.array(pil_img)
        ret, buf = _cv2.imencode('.png', arr)
        if not ret:
            raise RuntimeError("Failed to encode image as PNG via OpenCV")
        rect = _fitz.Rect(0, 0, pil_img.width, pil_img.height)
        page = doc.new_page(width=pil_img.width, height=pil_img.height)
        page.insert_image(rect, stream=buf.tobytes())
    doc.save(output_path)
    doc.close()


def _order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _four_point_transform(image, pts):
    _ensure_deps()
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(max(widthA, widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(max(heightA, heightB))
    dst = np.array([
        [0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]
    ], dtype="float32")
    M = _cv2.getPerspectiveTransform(rect, dst)
    return _cv2.warpPerspective(image, M, (maxWidth, maxHeight))


def enhance_page(image_bgr):
    _ensure_deps()
    orig_h, orig_w = image_bgr.shape[:2]
    ratio = 800.0 / orig_h
    small = _cv2.resize(image_bgr, (int(orig_w * ratio), 800))

    mask = _cv2.inRange(_cv2.cvtColor(small, _cv2.COLOR_BGR2HSV), np.array([0, 0, 100]), np.array([180, 60, 255]))
    kernel = np.ones((5, 5), np.uint8)
    mask = _cv2.morphologyEx(_cv2.morphologyEx(mask, _cv2.MORPH_OPEN, kernel), _cv2.MORPH_CLOSE, kernel)

    contours = sorted(_cv2.findContours(mask, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)[0], key=_cv2.contourArea, reverse=True)[:1]
    screenCnt = None
    if contours:
        peri = _cv2.arcLength(contours[0], True)
        approx = _cv2.approxPolyDP(contours[0], 0.02 * peri, True)
        if len(approx) == 4 and _cv2.contourArea(approx) > 0.15 * 800 * int(orig_w * ratio):
            screenCnt = approx.reshape(4, 2) * (1.0 / ratio)

    warped = _four_point_transform(image_bgr, screenCnt) if screenCnt is not None else image_bgr
    return _cv2.medianBlur(_cv2.adaptiveThreshold(_cv2.cvtColor(warped, _cv2.COLOR_BGR2GRAY), 255, _cv2.ADAPTIVE_THRESH_GAUSSIAN_C, _cv2.THRESH_BINARY, 21, 10), 3)


def _load_to_bgr(path):
    _ensure_deps()
    pil_img = _PIL_Image.open(path)
    if pil_img.mode == 'RGBA':
        bg = _PIL_Image.new('RGB', pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        return _cv2.cvtColor(np.array(bg), _cv2.COLOR_RGB2BGR)
    if pil_img.mode != 'RGB':
        pil_img = pil_img.convert('RGB')
    return _cv2.cvtColor(np.array(pil_img), _cv2.COLOR_RGB2BGR)


def pdf_enhance_file(file_path: str, output_path: str = "", dpi: int = 200) -> str:
    try:
        _ensure_deps()
        if not os.path.isfile(file_path):
            return f"Error: file not found: {file_path}"
        if not file_path.lower().endswith('.pdf'):
            return f"Error: not a PDF file: {file_path}"

        doc = _fitz.open(file_path)
        processed = []
        total = len(doc)
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = _cv2.cvtColor(img, _cv2.COLOR_BGRA2BGR)
            elif pix.n == 3:
                img = _cv2.cvtColor(img, _cv2.COLOR_RGB2BGR)
            processed.append(_PIL_Image.fromarray(enhance_page(img)))
        doc.close()

        if not processed:
            return "Error: no pages processed"
        out = output_path or file_path.replace('.pdf', '_enhanced.pdf')
        _save_as_pdf(processed, out)
        return f"Enhanced PDF saved to: {out} ({total} pages, {dpi} DPI)"
    except ImportError:
        return "Error: PDF enhancement requires opencv-python, PyMuPDF, and Pillow. Install them first."
    except Exception as e:
        logger.exception("pdf_enhance_file failed")
        return f"Error: {e}"


def pdf_enhance_images(image_paths: list, output_path: str = "", dpi: int = 200) -> str:
    try:
        _ensure_deps()
        valid = [p for p in image_paths if os.path.isfile(p)]
        if not valid:
            return "Error: no valid image files provided"
        processed = []
        for path in valid:
            processed.append(_PIL_Image.fromarray(enhance_page(_load_to_bgr(path))))
        if not processed:
            return "Error: no images could be processed"
        out = output_path or "enhanced_output.pdf"
        _save_as_pdf(processed, out)
        return f"Enhanced images saved to: {out} ({len(valid)} images combined into 1 PDF)"
    except ImportError:
        return "Error: PDF enhancement requires opencv-python, PyMuPDF, and Pillow. Install them first."
    except Exception as e:
        logger.exception("pdf_enhance_images failed")
        return f"Error: {e}"
