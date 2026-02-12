"""Home Assistant Supervisor REST API client."""

import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor/core/api"


def _first_jpeg_from_mjpeg_stream(stream, timeout: float = 20.0) -> bytes | None:
    """Read the first JPEG frame from an MJPEG (multipart) stream.

    HA uses multipart/x-mixed-replace; each part is a JPEG with
    Content-Length. We read until we have one full frame then stop.
    """
    deadline = time.monotonic() + timeout
    content_type = stream.headers.get("Content-Type", "")
    boundary_match = re.search(r"boundary=(\S+)", content_type)
    if not boundary_match:
        logger.debug("No boundary in MJPEG Content-Type: %s", content_type)
        return None
    boundary = boundary_match.group(1).strip().encode("ascii")
    if not boundary.startswith(b"--"):
        boundary = b"--" + boundary

    buf = b""
    state = "find_boundary"
    content_length = 0

    for chunk in stream.iter_content(chunk_size=8192):
        if time.monotonic() > deadline:
            logger.warning("Timeout reading first frame from MJPEG stream")
            return None
        if not chunk:
            continue
        buf += chunk

        if state == "find_boundary":
            idx = buf.find(b"\r\n\r\n")
            if idx == -1:
                if len(buf) > 8192:
                    buf = buf[-2048:]
                continue
            headers_block = buf[:idx]
            buf = buf[idx + 4:]
            state = "body"
            for line in headers_block.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    try:
                        content_length = int(line.split(b":", 1)[1].strip())
                    except (ValueError, IndexError):
                        pass
                    break
            if content_length <= 0:
                logger.debug("No Content-Length in MJPEG part headers")
                return None

        if state == "body":
            if len(buf) >= content_length:
                return buf[:content_length]
            if len(buf) > 2 * 1024 * 1024:
                logger.warning("MJPEG part too large, aborting")
                return None

    return None


class HAClient:
    """Client for Home Assistant REST API via Supervisor."""

    def __init__(self):
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            raise RuntimeError(
                "SUPERVISOR_TOKEN not found in environment. "
                "Ensure 'homeassistant_api: true' is set in config.yaml."
            )
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._target_off_at: float = 0.0

    # --- Low-level API methods ---

    def get_camera_snapshot(self, entity_id: str) -> bytes | None:
        """Fetch a JPEG snapshot from a HA camera entity.

        Tries the still-image API first; if the camera is stream-only (500),
        falls back to the MJPEG stream and uses the first frame.

        Args:
            entity_id: Camera entity, e.g. 'camera.ingresso'

        Returns:
            Raw JPEG bytes, or None on error.
        """
        # 1) Try still-image proxy (works when camera has native snapshot)
        url_still = f"{SUPERVISOR_URL}/camera_proxy/{entity_id}"
        req_headers = {
            **self.headers,
            "Accept": "image/jpeg, image/*, */*",
        }
        try:
            resp = requests.get(url_still, headers=req_headers, timeout=15)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            got_5xx = (
                getattr(e, "response", None) is not None
                and e.response.status_code >= 500
            )
            if got_5xx:
                logger.debug(
                    "Still image failed (%s), trying stream for %s",
                    e.response.status_code,
                    entity_id,
                )
                # 2) Fallback: take first frame from MJPEG stream
                jpeg = self._get_snapshot_from_stream(entity_id)
                if jpeg is not None:
                    return jpeg
            if getattr(e, "response", None) is not None:
                r = e.response
                if r.status_code >= 500 and r.text:
                    logger.error(
                        "Snapshot %s failed (%s). Server response: %s",
                        entity_id,
                        r.status_code,
                        r.text[:500],
                    )
                else:
                    logger.error("Failed to get snapshot from %s: %s", entity_id, e)
            else:
                logger.error("Failed to get snapshot from %s: %s", entity_id, e)
            return None

    def _get_snapshot_from_stream(self, entity_id: str) -> bytes | None:
        """Get one JPEG frame from camera_proxy_stream (for stream-only cameras)."""
        url = f"{SUPERVISOR_URL}/camera_proxy_stream/{entity_id}"
        try:
            resp = requests.get(
                url,
                headers={**self.headers, "Accept": "multipart/x-mixed-replace, */*"},
                stream=True,
                timeout=25,
            )
            resp.raise_for_status()
            return _first_jpeg_from_mjpeg_stream(resp, timeout=20.0)
        except requests.RequestException as e:
            logger.debug("Stream snapshot failed for %s: %s", entity_id, e)
            return None

    def update_sensor(self, entity_id: str, state: str,
                      attributes: dict | None = None):
        """Create or update a sensor/binary_sensor entity in HA."""
        url = f"{SUPERVISOR_URL}/states/{entity_id}"
        payload = {
            "state": state,
            "attributes": attributes or {},
        }
        try:
            resp = requests.post(
                url, json=payload, headers=self.headers, timeout=10
            )
            resp.raise_for_status()
            logger.debug("Updated %s = %s", entity_id, state)
        except requests.RequestException as e:
            logger.error("Failed to update %s: %s", entity_id, e)

    def fire_event(self, event_type: str, event_data: dict):
        """Fire an event in Home Assistant."""
        url = f"{SUPERVISOR_URL}/events/{event_type}"
        try:
            resp = requests.post(
                url, json=event_data, headers=self.headers, timeout=10
            )
            resp.raise_for_status()
            logger.debug("Fired event %s", event_type)
        except requests.RequestException as e:
            logger.error("Failed to fire event %s: %s", event_type, e)

    # --- High-level methods for this add-on ---

    def init_sensors(self):
        """Initialize sensors to a known state on startup."""
        self.update_sensor(
            "sensor.ai_targhe_last_plate",
            state="unknown",
            attributes={
                "friendly_name": "AI Targhe - Ultima Targa",
                "icon": "mdi:car",
            },
        )
        self.update_sensor(
            "binary_sensor.ai_targhe_target_detected",
            state="off",
            attributes={
                "friendly_name": "AI Targhe - Targa Autorizzata",
                "device_class": "occupancy",
                "icon": "mdi:car-off",
            },
        )

    def report_plate(self, plate: str, confidence: float,
                     is_target: bool, target_timeout: int):
        """Report a detected plate: update sensors and fire event."""
        # 1. Update last plate sensor
        self.update_sensor(
            "sensor.ai_targhe_last_plate",
            state=plate,
            attributes={
                "friendly_name": "AI Targhe - Ultima Targa",
                "confidence": round(confidence * 100, 1),
                "is_target": is_target,
                "icon": "mdi:car",
                "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )

        # 2. Update binary_sensor if it's a target plate
        if is_target:
            self._target_off_at = time.time() + target_timeout
            self.update_sensor(
                "binary_sensor.ai_targhe_target_detected",
                state="on",
                attributes={
                    "friendly_name": "AI Targhe - Targa Autorizzata",
                    "device_class": "occupancy",
                    "plate": plate,
                    "icon": "mdi:car-connected",
                },
            )

        # 3. Fire event (for any valid plate)
        self.fire_event("ai_targhe_plate_detected", {
            "plate": plate,
            "confidence": round(confidence * 100, 1),
            "is_target": is_target,
        })

    def check_target_timeout(self):
        """Turn OFF binary_sensor if target timeout has expired."""
        if self._target_off_at > 0 and time.time() > self._target_off_at:
            self._target_off_at = 0.0
            self.update_sensor(
                "binary_sensor.ai_targhe_target_detected",
                state="off",
                attributes={
                    "friendly_name": "AI Targhe - Targa Autorizzata",
                    "device_class": "occupancy",
                    "icon": "mdi:car-off",
                },
            )
            logger.info("Target detection timeout expired, binary_sensor -> OFF")
