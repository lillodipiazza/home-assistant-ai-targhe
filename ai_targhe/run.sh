#!/usr/bin/with-bashio

bashio::log.info "=== AI Targhe Add-on ==="
bashio::log.info "Starting license plate recognition..."

# Avvia lo script principale
exec python3 /app/main.py
