# CLAUDE.md - AI Targhe

## Project Overview

AI Targhe is a **Home Assistant add-on** for automatic Italian license plate recognition. It uses YOLO (exported to ONNX) for plate localization and Tesseract OCR for character reading. The add-on runs as a Docker container inside the Home Assistant Supervisor ecosystem, continuously scanning camera snapshots and reporting detected plates via HA sensors and events.

**Key facts:**
- Detects Italian plates matching format `AA000AA` (e.g., `AB123CD`)
- No PyTorch at runtime — uses OpenCV DNN to run the ONNX model
- Targets Alpine Linux (lightweight container for amd64 and aarch64)

## Repository Structure

```
home-assistant-ai-targhe/
├── CLAUDE.md               # This file
├── README.md               # User-facing documentation (Italian)
├── LICENSE                  # MIT License
├── repository.yaml          # HA add-on repository metadata
├── ai_targhe/               # The add-on package
│   ├── config.yaml          # HA add-on manifest (name, options schema, arch)
│   ├── build.yaml           # Multi-arch Docker base images
│   ├── Dockerfile           # Alpine-based container definition
│   ├── requirements.txt     # Python dependencies (4 packages)
│   ├── run.sh               # Container entrypoint (bashio → python3)
│   ├── app/                 # Python application source
│   │   ├── __init__.py
│   │   ├── main.py          # Main loop: snapshot → detect → report
│   │   ├── config.py        # Loads /data/options.json into typed config
│   │   ├── ha_client.py     # Home Assistant Supervisor REST API client
│   │   └── plate_recognizer.py  # YOLO ONNX inference + Tesseract OCR
│   ├── models/              # ML model files
│   │   ├── best.onnx        # Production ONNX model (~12 MB)
│   │   └── best.pt          # Source PyTorch model (~6 MB, dev only)
│   └── translations/        # HA UI labels
│       ├── en.yaml
│       └── it.yaml
└── scripts/
    └── export_onnx.py       # PyTorch → ONNX export utility
```

## Architecture

```
run.sh (entrypoint)
  └── main.py (orchestration loop)
        ├── config.py        → AddonConfig: reads /data/options.json
        ├── ha_client.py     → HAClient: REST API calls to HA Supervisor
        └── plate_recognizer.py → PlateRecognizer: YOLO + Tesseract pipeline
```

**Application flow (main.py):**
1. Load config from `/data/options.json`
2. Initialize `HAClient` (authenticates via `SUPERVISOR_TOKEN` env var)
3. Initialize `PlateRecognizer` (loads ONNX model via `cv2.dnn`)
4. Set HA sensors to initial state
5. Enter main loop:
   - Fetch camera JPEG snapshot via HA API
   - Decode to OpenCV frame
   - Run `PlateRecognizer.detect()` → list of `{plate, confidence, yolo_confidence, bbox}`
   - For each plate, call `HAClient.report_plate()` to update sensors and fire events
   - Check binary sensor timeout expiration
   - Sleep for `scan_interval` (in 0.5s increments for graceful SIGTERM handling)

**ML pipeline (plate_recognizer.py):**
1. Letterbox resize to 640×640 preserving aspect ratio
2. Blob normalization and YOLO ONNX forward pass
3. Filter detections by confidence threshold
4. Non-Maximum Suppression (NMS) to deduplicate
5. Map bounding boxes back to original image coordinates
6. For each detection, run Tesseract OCR with multiple preprocessing strategies (Otsu, adaptive threshold, raw grayscale)
7. Validate OCR output against Italian plate regex `^[A-Z]{2}\d{3}[A-Z]{2}$`

## Tech Stack

- **Language:** Python 3.13
- **Container:** Alpine Linux 3.21 (Home Assistant base image)
- **ML inference:** OpenCV DNN (ONNX runtime, no PyTorch)
- **OCR:** Tesseract with Italian + English language packs
- **Image processing:** OpenCV (`opencv-python-headless`), NumPy
- **HTTP client:** `requests` (HA Supervisor REST API)
- **Architectures:** amd64, aarch64

## Dependencies

Python packages (`ai_targhe/requirements.txt`):
```
opencv-python-headless>=4.8.0
pytesseract>=0.3.10
numpy>=1.24.0
requests>=2.28.0
```

System packages are installed via `apk` in the Dockerfile (Tesseract OCR, OpenCV native deps, build tools).

## Home Assistant Integration

**Entities created:**
- `sensor.ai_targhe_last_plate` — last detected plate text with attributes (confidence, is_target, last_seen)
- `binary_sensor.ai_targhe_target_detected` — ON when an authorized plate is seen, OFF after timeout

**Events fired:**
- `ai_targhe_plate_detected` with data: `{plate, confidence, is_target}`

**Configuration options** (defined in `ai_targhe/config.yaml`):
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `camera_entity` | str | `camera.ingresso` | Camera entity ID |
| `scan_interval` | int(1-60) | `5` | Seconds between scans |
| `target_plates` | list[str] | `["AB123CD"]` | Authorized plate list |
| `confidence_threshold` | float(0.1-1.0) | `0.5` | YOLO detection threshold |
| `target_detected_timeout` | int(5-300) | `30` | Seconds binary sensor stays ON |
| `log_level` | enum | `info` | debug/info/warning/error |

## Development

### Prerequisites

- Docker (for building the add-on image)
- Python with PyTorch/Ultralytics (only for re-exporting the ONNX model)

### ONNX Model Export

If you need to regenerate `best.onnx` from the PyTorch model:

```bash
pip install ultralytics
python scripts/export_onnx.py
```

This reads `ai_targhe/models/best.pt` and writes `ai_targhe/models/best.onnx`.

### Building the Docker Image

The image is normally built by the Home Assistant Supervisor, but for local testing:

```bash
docker build -t ai_targhe --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.21 ai_targhe/
```

### Testing

There is no automated test suite. Testing is done manually by running the add-on in a Home Assistant environment with a real camera feed.

## Code Conventions

### Naming
- **snake_case** for functions and variables: `jpeg_to_frame`, `_recognize_plate_tesseract`
- **PascalCase** for classes: `AddonConfig`, `HAClient`, `PlateRecognizer`
- **Leading underscore** for private/internal functions: `_letterbox`, `_xywh2xyxy`, `_shutdown`
- **UPPER_CASE** for module-level constants: `INPUT_SIZE`, `OCR_CONFIDENCE_THRESHOLD`, `ITALIAN_PLATE_REGEX`
- **Entity IDs** use dot-separated snake_case: `sensor.ai_targhe_last_plate`

### Style
- Type hints throughout (PEP 484 style): `np.ndarray | None`, `dict[str, float]`, `list[str]`
- Docstrings on all classes and public functions
- Logging at appropriate levels (debug for routine, info for significant events, warning/error for failures)
- Comments for non-obvious logic (especially ML post-processing)
- Italian used in some log messages, error messages, and the README; English used in code identifiers and CLAUDE.md

### Patterns
- **Separation of concerns:** config, HA communication, and ML inference are in separate modules
- **Graceful shutdown:** SIGTERM/SIGINT handled via global flag; sleep loop uses 0.5s increments
- **Error resilience:** failed snapshots and OCR failures are logged and skipped, not fatal
- **Configuration-driven:** all behavior controlled by HA add-on options (no hardcoded settings beyond ML constants)
- **Stateful timeout tracking:** `HAClient._target_off_at` manages binary sensor auto-off

### Key Constants (plate_recognizer.py)
- `INPUT_SIZE = 640` — YOLO input resolution
- `OCR_CONFIDENCE_THRESHOLD = 0.3` — minimum Tesseract confidence
- `OCR_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"` — allowed OCR characters
- `ITALIAN_PLATE_REGEX = r"^[A-Z]{2}\d{3}[A-Z]{2}$"` — validation pattern
- NMS IoU threshold: `0.45` (hardcoded in `detect()`)

## Important Notes for AI Assistants

1. **No PyTorch in production.** The ONNX model is loaded via `cv2.dnn.readNetFromONNX()`. Do not add PyTorch or Ultralytics as runtime dependencies.
2. **Alpine Linux constraints.** Many Python packages with C extensions need special handling on Alpine (musl libc). The Dockerfile installs build tools explicitly for this reason.
3. **Supervisor environment.** The app expects `SUPERVISOR_TOKEN` in the environment and communicates with Home Assistant via `http://supervisor/core/api`. It will not run outside the HA Supervisor context without mocking these.
4. **Config is read-only at startup.** `AddonConfig` loads `/data/options.json` once. Config changes require an add-on restart.
5. **Model files are large.** `best.onnx` is ~12 MB and `best.pt` is ~6 MB. Be mindful of these in git operations.
6. **Italian plate format only.** The regex `^[A-Z]{2}\d{3}[A-Z]{2}$` is specific to standard Italian plates. Supporting other formats would require changes to `plate_recognizer.py`.
