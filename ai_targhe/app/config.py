"""Configuration loader for the AI Targhe HA add-on."""

import json
import logging
import os

OPTIONS_PATH = "/data/options.json"


class AddonConfig:
    """Typed configuration loaded from HA add-on options."""

    def __init__(self):
        if not os.path.exists(OPTIONS_PATH):
            raise FileNotFoundError(
                f"Options file not found: {OPTIONS_PATH}. "
                "Ensure the add-on is running inside Home Assistant."
            )

        with open(OPTIONS_PATH) as f:
            opts = json.load(f)

        self.camera_entity: str = opts["camera_entity"]
        self.scan_interval: int = opts.get("scan_interval", 5)
        self.target_plates: list[str] = [
            p.upper().replace(" ", "").replace("-", "")
            for p in opts.get("target_plates", [])
        ]
        self.confidence_threshold: float = opts.get("confidence_threshold", 0.5)
        self.target_detected_timeout: int = opts.get("target_detected_timeout", 30)
        self.log_level: str = opts.get("log_level", "info").upper()

    def get_numeric_log_level(self) -> int:
        """Convert string log level to logging constant."""
        return getattr(logging, self.log_level, logging.INFO)
