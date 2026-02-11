# AI Targhe - Home Assistant Add-on

Riconoscimento automatico di targhe italiane tramite AI (YOLO + EasyOCR).

## Funzionalità

- Rileva targhe italiane (formato AA000AA) da qualsiasi camera di Home Assistant
- Configura una lista di targhe autorizzate ("target")
- Sensore con l'ultima targa rilevata
- Binary sensor ON/OFF quando una targa autorizzata viene riconosciuta
- Evento `ai_targhe_plate_detected` per automazioni avanzate

## Installazione

1. In Home Assistant: **Settings > Add-ons > Add-on Store > ⋮ > Repositories**
2. Aggiungi l'URL di questo repository
3. Cerca "AI Targhe" e clicca **Installa**

## Configurazione

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| `camera_entity` | Entity ID della camera HA | `camera.ingresso` |
| `scan_interval` | Secondi tra ogni scansione (1-60) | `5` |
| `target_plates` | Lista targhe autorizzate | `[]` |
| `confidence_threshold` | Soglia minima YOLO (0.1-1.0) | `0.5` |
| `target_detected_timeout` | Secondi binary_sensor resta ON | `30` |
| `log_level` | Livello log (debug/info/warning/error) | `info` |

## Entità create

- `sensor.ai_targhe_last_plate` - Ultima targa rilevata
- `binary_sensor.ai_targhe_target_detected` - ON se targa autorizzata

## Esempio automazione

```yaml
automation:
  - alias: "Apri cancello per targa autorizzata"
    trigger:
      - platform: state
        entity_id: binary_sensor.ai_targhe_target_detected
        to: "on"
    action:
      - service: switch.turn_on
        entity_id: switch.cancello
```
