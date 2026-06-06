"""Schritt 1: MIDI-Ports auflisten.

Dieses kleine Skript zeigt alle MIDI-Eingänge (Inputs) und MIDI-Ausgänge
(Outputs), die das Betriebssystem gerade bereitstellt. Damit prüfen wir,
dass MIDI grundsätzlich funktioniert - die Basis für alles Weitere.

Start (im Projektordner):
    .venv/bin/python scripts/list_midi.py
"""

import rtmidi


def list_ports(label: str, midi: "rtmidi.MidiIn | rtmidi.MidiOut") -> None:
    """Gibt die Namen aller Ports eines MIDI-Objekts nummeriert aus."""
    ports = midi.get_ports()
    print(f"\n{label} ({len(ports)} gefunden):")
    if not ports:
        print("  (keine)")
        return
    for index, name in enumerate(ports):
        print(f"  [{index}] {name}")


def main() -> None:
    # Ein MidiIn-Objekt kennt die verfuegbaren Eingaenge,
    # ein MidiOut-Objekt die verfuegbaren Ausgaenge.
    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    list_ports("MIDI-Eingaenge (Inputs)", midi_in)
    list_ports("MIDI-Ausgaenge (Outputs)", midi_out)

    # Aufraeumen: die zugrunde liegenden MIDI-Ressourcen freigeben.
    del midi_in
    del midi_out


if __name__ == "__main__":
    main()
