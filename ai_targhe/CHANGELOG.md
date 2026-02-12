# Changelog

## 1.0.1

- Fix avvio addon: corretto `init: true` in config.yaml per compatibilità con s6-overlay
- Aggiornata descrizione: EasyOCR sostituito con Tesseract OCR

## 1.0.0

- Prima release
- Riconoscimento targhe italiane con YOLO (ONNX) + Tesseract OCR
- Sensore `sensor.ai_targhe_last_plate` con ultima targa rilevata
- Sensore binario `binary_sensor.ai_targhe_target_detected` per targhe autorizzate
- Evento `ai_targhe_plate_detected` per automazioni avanzate
- Configurazione: camera, intervallo scansione, lista targhe, soglia confidenza, timeout
