"""AI Targhe - Main add-on loop for Home Assistant."""

import logging
import signal
import time

import cv2
import numpy as np

from config import AddonConfig
from ha_client import HAClient
from plate_recognizer import PlateRecognizer

# --- Graceful shutdown ---
running = True


def _shutdown(signum, _frame):
    global running
    logging.info("Received signal %s, shutting down...", signum)
    running = False


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


def jpeg_to_frame(jpeg_bytes: bytes) -> np.ndarray | None:
    """Convert JPEG bytes from HA camera API to OpenCV BGR frame."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame


def main():
    # 1. Load configuration
    config = AddonConfig()
    logging.basicConfig(
        level=config.get_numeric_log_level(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("ai_targhe")

    logger.info("=== AI Targhe Add-on Starting ===")
    logger.info("Camera: %s", config.camera_entity)
    logger.info("Target plates: %s", config.target_plates)
    logger.info("Scan interval: %ds", config.scan_interval)
    logger.info("Confidence threshold: %.2f", config.confidence_threshold)
    logger.info("Target timeout: %ds", config.target_detected_timeout)

    # 2. Initialize components
    ha = HAClient()
    recognizer = PlateRecognizer(
        confidence_threshold=config.confidence_threshold,
    )

    # 3. Initialize sensors to known state
    ha.init_sensors()

    logger.info("Entering main scan loop...")

    # 4. Main loop
    while running:
        loop_start = time.time()

        # 4a. Get camera snapshot
        jpeg_bytes = ha.get_camera_snapshot(config.camera_entity)
        if jpeg_bytes is None:
            logger.warning(
                "No snapshot received, retrying in %ds...",
                config.scan_interval,
            )
            time.sleep(config.scan_interval)
            continue

        # 4b. Decode JPEG to OpenCV frame
        frame = jpeg_to_frame(jpeg_bytes)
        if frame is None:
            logger.error("Failed to decode JPEG snapshot")
            time.sleep(config.scan_interval)
            continue

        # 4c. Detect plates
        plates = recognizer.detect(frame)

        # 4d. Report each detected plate to HA
        for plate_info in plates:
            plate_text = plate_info["plate"]
            is_target = plate_text in config.target_plates

            ha.report_plate(
                plate=plate_text,
                confidence=plate_info["confidence"],
                is_target=is_target,
                target_timeout=config.target_detected_timeout,
            )

            if is_target:
                logger.info(
                    ">>> TARGET PLATE DETECTED: %s <<<", plate_text
                )

        # 4e. Check if binary_sensor timeout has expired
        ha.check_target_timeout()

        # 4f. Sleep for remaining interval (in small increments for SIGTERM)
        elapsed = time.time() - loop_start
        sleep_time = max(0, config.scan_interval - elapsed)
        end_time = time.time() + sleep_time
        while running and time.time() < end_time:
            time.sleep(0.5)

    logger.info("=== AI Targhe Add-on Stopped ===")


if __name__ == "__main__":
    main()
