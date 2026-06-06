"""Monitor: zeigt eingehende MIDI-Nachrichten als dekodierte MCU-Events.

Dies ist ein *Test-/Demo-Skript* (kein Teil der App). Es beweist die
**Empfangs-Kette der Protokollschicht**:

    DAW -> MidiBackend.poll() -> McuDecoder.decode_many() -> Event-Ausgabe

So testest du den Decoder live:

1. Skript starten (siehe unten). Es bietet einen virtuellen Port "TouchControl"
   an und wartet auf Nachrichten.
2. In Cubase/Ableton ein **Mackie-Control-Geraet** anlegen und als Ein-/Ausgang
   den Port "TouchControl" waehlen.
3. In der DAW einen **Fader** bewegen (oder Automation abspielen). Im Terminal
   erscheint pro Bewegung ein ``FaderEvent`` mit Kanal und Position.

Unbekannte Nachrichten (z. B. der MCU-Verbindungs-Ping) werden vom Decoder zu
``None`` und hier - falls gewuenscht - als rohe Bytes angezeigt.

Start (im Projektordner):
    .venv/bin/python scripts/decoder_monitor.py

Beenden mit Strg+C.
"""

from __future__ import annotations

import time

from touchcontrol.mcu import McuDecoder, McuEncoder
from touchcontrol.mcu.events import HostConnectionQueryEvent
from touchcontrol.midi import MidiBackend

# Name des virtuellen Ports, den die DAW als MCU-Ausgang waehlen kann.
PORT_NAME = "TouchControl"
# Wie oft pro Sekunde holen wir eingehende MIDI-Nachrichten ab?
POLL_HZ = 60
# Auch rohe, NICHT dekodierte Nachrichten anzeigen? (zum Forschen hilfreich)
ZEIGE_UNBEKANNTE = True
# Geraete-ID, auf die wir antworten: 0x14 = Mackie Control, 0x15 = Mackie Control 2.
# Nur auf die eigene ID antworten - sonst denkt Cubase es haette zwei Geraete
# und resettet, weil der zweite Handshake unvollstaendig bleibt.
ANTWORT_DEVICE_ID = 0x14


def _formatiere_bytes(message: list[int]) -> str:
    """Bytes als Hex-Liste darstellen, z. B. ``E0 6C 5E``."""
    return " ".join(f"{b:02X}" for b in message)


def main() -> None:
    backend = MidiBackend()
    decoder = McuDecoder()
    encoder = McuEncoder()

    backend.open_virtual(PORT_NAME)
    print(f"Virtueller Port '{PORT_NAME}' geoeffnet. Warte auf MIDI ...")
    print("In der DAW einen Fader bewegen. Beenden mit Strg+C.\n")

    pause = 1.0 / POLL_HZ
    try:
        while True:
            rohnachrichten = backend.poll()

            for message in rohnachrichten:
                event = decoder.decode(message)
                if event is not None:
                    print(f"EVENT  {event}")
                    # Host-Connection-Query sofort beantworten, damit Cubase
                    # das Geraet als verbunden akzeptiert und den Reset-Loop stoppt.
                    # Nur auf die konfigurierte device_id antworten - nicht auf beide,
                    # sonst glaubt Cubase es haette zwei Geraete.
                    if isinstance(event, HostConnectionQueryEvent):
                        if event.device_id == ANTWORT_DEVICE_ID:
                            reply = encoder.host_connection_reply(event.device_id)
                            backend.send(reply)
                            print(f"  -> Reply gesendet (device_id={event.device_id:#04x})")
                        else:
                            print(f"  -> ignoriert (nicht unsere device_id)")
                elif ZEIGE_UNBEKANNTE:
                    print(f"roh    [{_formatiere_bytes(message)}]  (unbekannt)")

            time.sleep(pause)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        backend.close()


if __name__ == "__main__":
    main()
