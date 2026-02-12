# Changelog

## 1.0.7

- 


## 1.0.6

- 


## 1.0.5

- 


## 1.0.4

- 


## 1.0.3

- 


## 1.0.2

- 


## 1.0.1

- Fix avvio addon: corretto shebang in run.sh (`#!/usr/bin/with-contenv bashio`)
- Fix avvio addon: corretto `init: true` in config.yaml per compatibilità con s6-overlay
- Rimosso riferimento a EasyOCR non più utilizzato (run.sh e metadati)
- Aggiornata descrizione: EasyOCR sostituito con Tesseract OCR

## 1.0.0

- Prima release
- Riconoscimento targhe italiane con YOLO (ONNX) + Tesseract OCR
- Sensore `sensor.ai_targhe_last_plate` con ultima targa rilevata
- Sensore binario `binary_sensor.ai_targhe_target_detected` per targhe autorizzate
- Evento `ai_targhe_plate_detected` per automazioni avanzate
- Configurazione: camera, intervallo scansione, lista targhe, soglia confidenza, timeout
