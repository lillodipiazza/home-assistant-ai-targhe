#!/usr/bin/with-contenv bashio

bashio::log.info "=== AI Targhe Add-on ==="
bashio::log.info "Starting license plate recognition..."

# Output non bufferizzato così i log Python compaiono subito
export PYTHONUNBUFFERED=1

# Avvia lo script principale
exec python3 /app/main.py
