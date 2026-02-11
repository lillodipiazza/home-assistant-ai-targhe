#!/usr/bin/env python3
"""
Esporta il modello YOLO best.pt in formato ONNX per l'addon (senza PyTorch in produzione).
Eseguire una sola volta su un ambiente con: pip install ultralytics
"""
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "ai_targhe" / "models"
PT_PATH = MODELS_DIR / "best.pt"
ONNX_PATH = MODELS_DIR / "best.onnx"


def main():
    if not PT_PATH.exists():
        raise FileNotFoundError(f"Modello non trovato: {PT_PATH}")
    print(f"Caricamento {PT_PATH}...")
    model = YOLO(str(PT_PATH))
    print(f"Export ONNX in {MODELS_DIR}...")
    # ultralytics scrive best.onnx nella stessa directory del .pt
    model.export(format="onnx", imgsz=640, simplify=True)
    onnx_path = PT_PATH.with_suffix(".onnx")
    if not onnx_path.exists():
        raise RuntimeError(f"Export non ha creato {onnx_path}")
    print(f"Fatto: {onnx_path}. Includilo nel repository per il build Docker.")


if __name__ == "__main__":
    main()
