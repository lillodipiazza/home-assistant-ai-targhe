"""License plate recognition: YOLO (ONNX) + Tesseract OCR. No PyTorch."""

import logging
import os
import re

import cv2
import numpy as np
import pytesseract

logger = logging.getLogger(__name__)

# --- Constants ---
INPUT_SIZE = 640
OCR_CONFIDENCE_THRESHOLD = 0.3
OCR_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ITALIAN_PLATE_REGEX = re.compile(r"^[A-Z]{2}\d{3}[A-Z]{2}$")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_ONNX = os.path.join(MODEL_DIR, "best.onnx")


def _letterbox(img: np.ndarray, target_size: int = INPUT_SIZE) -> tuple[np.ndarray, float, float, int, int]:
    """Letterbox resize; returns (padded_img, scale, pad_x, pad_y, orig_w, orig_h)."""
    h, w = img.shape[:2]
    scale = min(target_size / h, target_size / w)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2
    padded = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
    padded[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return padded, scale, pad_x, pad_y, w, h


def _xywh2xyxy(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    """Convert center (x,y) + width/height to (x1,y1,x2,y2)."""
    x1 = x - w / 2
    y1 = y - h / 2
    x2 = x + w / 2
    y2 = y + h / 2
    return x1, y1, x2, y2


def _recognize_plate_tesseract(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> tuple[str | None, float]:
    """Run Tesseract OCR on plate region; validate Italian format. Returns (plate_text, confidence)."""
    h_frame, w_frame = frame.shape[:2]
    margin_x = int((x2 - x1) * 0.1)
    margin_y = int((y2 - y1) * 0.15)
    x1m = max(0, x1 - margin_x)
    y1m = max(0, y1 - margin_y)
    x2m = min(w_frame, x2 + margin_x)
    y2m = min(h_frame, y2 + margin_y)

    plate_roi = frame[y1m:y2m, x1m:x2m]
    if plate_roi.size == 0:
        return None, 0.0

    scale = max(1, 200 // plate_roi.shape[0])
    if scale > 1:
        plate_roi = cv2.resize(
            plate_roi, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

    plate_gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
    tess_config = f"--psm 7 -c tessedit_char_whitelist={OCR_ALLOWLIST}"

    preprocessed = [
        cv2.threshold(plate_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        cv2.adaptiveThreshold(
            plate_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2,
        ),
        plate_gray,
    ]

    best_text = None
    best_conf = 0.0

    for img in preprocessed:
        data = pytesseract.image_to_data(img, config=tess_config, output_type=pytesseract.Output.DICT)
        n = len(data["text"])

        for i in range(n):
            text = (data["text"][i] or "").strip().upper().replace(" ", "").replace("-", "")
            if not text:
                continue
            conf = float(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.0

            if conf >= OCR_CONFIDENCE_THRESHOLD and ITALIAN_PLATE_REGEX.match(text):
                if conf > best_conf:
                    best_text = text
                    best_conf = conf

        # Try full line
        full = "".join((data["text"][i] or "").upper().replace(" ", "").replace("-", "") for i in range(n))
        if full and ITALIAN_PLATE_REGEX.match(full):
            avg = np.mean([float(data["conf"][i]) / 100.0 for i in range(n) if data["conf"][i] != "-1"] or [0])
            if avg > best_conf:
                best_text = full
                best_conf = avg

        if best_text:
            return best_text, best_conf

    return None, 0.0


class PlateRecognizer:
    """YOLO (ONNX via OpenCV DNN) + Tesseract OCR. No PyTorch dependency."""

    def __init__(self, confidence_threshold: float = 0.5):
        if not os.path.exists(MODEL_ONNX):
            raise FileNotFoundError(
                f"Modello ONNX non trovato: {MODEL_ONNX}. "
                "Esporta il modello con: python scripts/export_onnx.py (da un ambiente con torch/ultralytics)."
            )
        logger.info("Caricamento modello YOLO ONNX da %s", MODEL_ONNX)
        self._net = cv2.dnn.readNetFromONNX(MODEL_ONNX)
        logger.info("Tesseract OCR disponibile.")
        self.confidence_threshold = confidence_threshold

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect plates in frame. Returns list of {plate, confidence, yolo_confidence, bbox}."""
        padded, scale, pad_x, pad_y, orig_w, orig_h = _letterbox(frame)
        blob = cv2.dnn.blobFromImage(
            padded, 1.0 / 255.0, (INPUT_SIZE, INPUT_SIZE), (0, 0, 0),
            swapRB=True, crop=False,
        )
        self._net.setInput(blob)
        out = self._net.forward()
        # YOLOv8: (1, 4+num_classes, 8400); 1 class -> (1, 5, 8400); oppure (1, 42000)
        if out.size == 42000:  # (1, 42000)
            out = out.reshape(1, 5, 8400)
        elif out.ndim == 2:
            out = out.reshape(out.shape[0], out.shape[1], -1)
        # (1, 5, 8400) -> (8400, 5)
        rows = out[0].T
        boxes_xywh = []
        scores = []
        for row in rows:
            *xywh, score = row
            if score < self.confidence_threshold:
                continue
            boxes_xywh.append([float(x) for x in xywh])
            scores.append(float(score))

        if not boxes_xywh:
            return []

        # Convert to xyxy in 640x640 space
        xyxy_640 = []
        for xc, yc, w, h in boxes_xywh:
            x1, y1, x2, y2 = _xywh2xyxy(xc, yc, w, h)
            xyxy_640.append([x1, y1, x2, y2])

        indices = cv2.dnn.NMSBoxes(
            [[b[0], b[1], b[2] - b[0], b[3] - b[1]] for b in xyxy_640],
            scores,
            self.confidence_threshold,
            0.45,
        )
        if isinstance(indices, np.ndarray):
            indices = indices.flatten()

        plates = []
        for i in indices:
            x1_640, y1_640, x2_640, y2_640 = xyxy_640[i]
            # Map back to original image
            x1 = int((x1_640 - pad_x) / scale)
            y1 = int((y1_640 - pad_y) / scale)
            x2 = int((x2_640 - pad_x) / scale)
            y2 = int((y2_640 - pad_y) / scale)
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))

            plate_text, ocr_conf = _recognize_plate_tesseract(frame, x1, y1, x2, y2)
            if plate_text:
                plates.append({
                    "plate": plate_text,
                    "confidence": round(ocr_conf, 3),
                    "yolo_confidence": round(scores[i], 3),
                    "bbox": [x1, y1, x2, y2],
                })
                logger.info(
                    "Targa rilevata: %s (OCR: %.0f%%, YOLO: %.0f%%)",
                    plate_text, ocr_conf * 100, scores[i] * 100,
                )
        return plates
