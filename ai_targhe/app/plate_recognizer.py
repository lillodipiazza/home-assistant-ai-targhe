"""License plate recognition engine using YOLO + EasyOCR."""

import warnings
warnings.filterwarnings("ignore", message=".*pin_memory.*")

import logging
import os
import re

import cv2
import easyocr
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# --- Constants ---
OCR_CONFIDENCE_THRESHOLD = 0.3
OCR_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ITALIAN_PLATE_REGEX = re.compile(r"^[A-Z]{2}\d{3}[A-Z]{2}$")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "best.pt")


def _recognize_plate(reader, frame, x1, y1, x2, y2):
    """Run OCR on a plate region and validate Italian format.

    Identical logic to the standalone script: margin expansion, scaling,
    multi-strategy preprocessing (Otsu, adaptive threshold, raw grayscale).

    Returns:
        tuple: (plate_text: str | None, confidence: float)
    """
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

    # Upscale small plates for better OCR
    scale = max(1, 200 // plate_roi.shape[0])
    if scale > 1:
        plate_roi = cv2.resize(
            plate_roi, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

    plate_gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)

    # Try multiple preprocessing strategies
    preprocessed = [
        cv2.threshold(
            plate_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1],
        cv2.adaptiveThreshold(
            plate_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2,
        ),
        plate_gray,  # Raw grayscale as fallback
    ]

    best_text = None
    best_conf = 0.0

    for img in preprocessed:
        results = reader.readtext(
            img,
            allowlist=OCR_ALLOWLIST,
            detail=1,
            paragraph=False,
        )

        # Try concatenating all detected text fragments
        all_text = "".join(
            text.upper().replace(" ", "").replace("-", "")
            for _, text, _ in results
        )
        avg_conf = (
            np.mean([conf for _, _, conf in results]) if results else 0.0
        )

        if (avg_conf >= OCR_CONFIDENCE_THRESHOLD
                and ITALIAN_PLATE_REGEX.match(all_text)):
            if avg_conf > best_conf:
                best_text = all_text
                best_conf = avg_conf

        # Also try individual fragments
        for _, text, confidence in results:
            text_clean = text.upper().replace(" ", "").replace("-", "")
            if (confidence >= OCR_CONFIDENCE_THRESHOLD
                    and ITALIAN_PLATE_REGEX.match(text_clean)):
                if confidence > best_conf:
                    best_text = text_clean
                    best_conf = confidence

        if best_text:
            return best_text, best_conf

    return None, 0.0


class PlateRecognizer:
    """High-level orchestrator: takes a frame, returns all detected plates."""

    def __init__(self, confidence_threshold: float = 0.5):
        # Load YOLO model (pre-bundled in Docker image)
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"YOLO model not found at {MODEL_PATH}. "
                "The model should be pre-bundled in the Docker image."
            )
        logger.info("Loading YOLO model from %s", MODEL_PATH)
        self.yolo_model = YOLO(MODEL_PATH)

        # Initialize EasyOCR (downloads models to EASYOCR_MODULE_PATH on first run)
        logger.info(
            "Initializing EasyOCR (first run downloads models to /data)..."
        )
        self.reader = easyocr.Reader(["en"], gpu=False)
        logger.info("EasyOCR ready.")

        self.confidence_threshold = confidence_threshold

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Detect all plates in a frame.

        Args:
            frame: BGR image as numpy array (from cv2.imdecode).

        Returns:
            List of dicts, each with keys:
                plate (str): Recognized plate text, e.g. "AB123CD"
                confidence (float): OCR confidence 0-1
                yolo_confidence (float): YOLO detection confidence 0-1
                bbox (list[int]): [x1, y1, x2, y2]
        """
        results = self.yolo_model(
            frame, conf=self.confidence_threshold, verbose=False
        )
        plates = []

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                yolo_conf = float(box.conf[0])

                plate_text, ocr_conf = _recognize_plate(
                    self.reader, frame, x1, y1, x2, y2
                )

                if plate_text:
                    plates.append({
                        "plate": plate_text,
                        "confidence": round(ocr_conf, 3),
                        "yolo_confidence": round(yolo_conf, 3),
                        "bbox": [x1, y1, x2, y2],
                    })
                    logger.info(
                        "Plate detected: %s (OCR: %.0f%%, YOLO: %.0f%%)",
                        plate_text, ocr_conf * 100, yolo_conf * 100,
                    )

        return plates
