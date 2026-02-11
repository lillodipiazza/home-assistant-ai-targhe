"""Home Assistant Supervisor REST API client."""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor/core/api"


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

        Args:
            entity_id: Camera entity, e.g. 'camera.ingresso'

        Returns:
            Raw JPEG bytes, or None on error.
        """
        url = f"{SUPERVISOR_URL}/camera_proxy/{entity_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            logger.error("Failed to get snapshot from %s: %s", entity_id, e)
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
