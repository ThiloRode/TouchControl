# TouchControl – Dokumentation

Touchscreen-**Mackie-Control-(MCU)**-Controller. Entwicklung auf dem Mac,
Betrieb auf einem Raspberry Pi 4 mit 10,1"-Touchscreen (1280×800).

## Inhalt

- [Architektur](architecture.md) – Schichten, Klassen, Designentscheidungen.

## Module (wird mit jedem Schritt ergänzt)

- [`MidiBackend`](midi-backend.md) – MIDI-Transportschicht (Ports, Senden, Empfang über Queue).

## Arbeitsweise

- Schritt für Schritt; jeder Schritt wird erklärt.
- Zu jedem Modul gehören **Dokumentation** (hier unter `docs/`) und
  **Tests** (`tests/`, ausgeführt mit `pytest`).
