#!/usr/bin/with-bashio

bashio::log.info "=== AI Targhe Add-on ==="
bashio::log.info "Starting license plate recognition..."

# Percorso persistente per i modelli EasyOCR (~100MB, scaricati al primo avvio)
export EASYOCR_MODULE_PATH="/data/easyocr_models"

# Avvia lo script principale
exec python3 /app/main.py
