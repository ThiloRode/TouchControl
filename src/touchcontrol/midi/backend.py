"""``MidiBackend`` - die Transportschicht von TouchControl.

Diese Klasse kapselt ``python-rtmidi`` und bietet dem Rest der App eine
einfache, thread-sichere Schnittstelle:

* Ports **auflisten** (Namen statt Indizes nach aussen),
* Ports per **Namensteil oeffnen** (z. B. ``"IAC"``),
* einen eigenen **virtuellen Port** anbieten (die App wird selbst zum MIDI-Geraet),
* rohe Bytes **senden**,
* eingehende Nachrichten thread-sicher ueber eine Queue **abholen** (``poll``).

Der Empfang laeuft bei ``python-rtmidi`` in einem internen MIDI-Thread. Damit die
(spaetere) Kivy-UI - die nur im Hauptthread angefasst werden darf - nicht in
Gefahr geraet, schreibt der Callback eingehende Nachrichten ausschliesslich in
eine ``queue.Queue``. Der Hauptthread holt sie spaeter mit ``poll()`` heraus.
"""

from __future__ import annotations

import queue
from typing import List, Optional, Sequence

import rtmidi


class MidiBackend:
    """Duenne, thread-sichere Huelle um ``python-rtmidi``.

    Typische Nutzung::

        backend = MidiBackend()
        backend.open(input_name="IAC", output_name="IAC")
        backend.send([0xE0, 0x00, 0x40])     # rohe MIDI-Bytes
        for nachricht in backend.poll():     # eingegangene Nachrichten
            ...
        backend.close()
    """

    def __init__(self) -> None:
        # Zwei getrennte rtmidi-Objekte: eines fuer Eingaenge, eines fuer Ausgaenge.
        self._midi_in = rtmidi.MidiIn()
        self._midi_out = rtmidi.MidiOut()

        # Der "Briefkasten": der MIDI-Thread legt hier eingehende Nachrichten ab,
        # der Hauptthread holt sie via poll() wieder heraus. queue.Queue ist
        # von Haus aus thread-sicher - genau dafuer gemacht.
        self._queue: "queue.Queue[List[int]]" = queue.Queue()

        # Merker, ob wir Ports tatsaechlich geoeffnet haben (fuer close/send).
        self._input_open = False
        self._output_open = False

    # ------------------------------------------------------------------
    # Ports auflisten
    # ------------------------------------------------------------------
    def available_inputs(self) -> List[str]:
        """Namen aller verfuegbaren MIDI-Eingaenge."""
        return self._midi_in.get_ports()

    def available_outputs(self) -> List[str]:
        """Namen aller verfuegbaren MIDI-Ausgaenge."""
        return self._midi_out.get_ports()

    # ------------------------------------------------------------------
    # Hilfsfunktion: Port per Namensteil finden
    # ------------------------------------------------------------------
    @staticmethod
    def _find_port(ports: Sequence[str], name_part: str) -> Optional[int]:
        """Index des ersten Ports, dessen Name ``name_part`` enthaelt (ohne Gross/Klein).

        Gibt ``None`` zurueck, wenn nichts passt. So koennen wir Ports robust
        per Teilstring oeffnen ("IAC" findet "IAC Driver Bus 1"), auch wenn der
        genaue Portname auf Mac und Pi leicht abweicht.
        """
        ziel = name_part.lower()
        for index, name in enumerate(ports):
            if ziel in name.lower():
                return index
        return None

    # ------------------------------------------------------------------
    # Ports oeffnen
    # ------------------------------------------------------------------
    def open(
        self,
        input_name: Optional[str] = None,
        output_name: Optional[str] = None,
    ) -> None:
        """Vorhandene Ports per Namensteil oeffnen.

        ``input_name`` und/oder ``output_name`` sind jeweils ein Teilstring des
        gewuenschten Portnamens. Mindestens einer sollte angegeben werden.
        Wirft ``ValueError``, wenn kein passender Port existiert.
        """
        if input_name is not None:
            index = self._find_port(self._midi_in.get_ports(), input_name)
            if index is None:
                raise ValueError(
                    f"Kein MIDI-Eingang gefunden, der '{input_name}' enthaelt"
                )
            self._midi_in.open_port(index)
            self._setup_input_callback()
            self._input_open = True

        if output_name is not None:
            index = self._find_port(self._midi_out.get_ports(), output_name)
            if index is None:
                raise ValueError(
                    f"Kein MIDI-Ausgang gefunden, der '{output_name}' enthaelt"
                )
            self._midi_out.open_port(index)
            self._output_open = True

    def open_virtual(self, name: str) -> None:
        """Einen eigenen virtuellen Ein- und Ausgang anbieten.

        Damit erscheint TouchControl selbst als MIDI-Geraet (Ein- und Ausgang) im
        System - genau das, was wir spaeter wollen: Die DAW "sieht" uns als
        Mackie-Control-Geraet.

        Hinweis: Virtuelle Ports werden unter Windows von rtmidi nicht
        unterstuetzt; auf macOS (CoreMIDI) und Linux (ALSA) funktionieren sie.
        """
        self._midi_in.open_virtual_port(name)
        self._setup_input_callback()
        self._input_open = True

        self._midi_out.open_virtual_port(name)
        self._output_open = True

    def _setup_input_callback(self) -> None:
        """Eingang fuer den Empfang vorbereiten (SysEx zulassen, Callback setzen)."""
        # Standardmaessig ignoriert rtmidi SysEx-Nachrichten. Wir brauchen sie
        # aber spaeter fuer die LCD-Anzeige (Kanalnamen). Timing-Clock und
        # Active-Sensing dagegen sind nur "Rauschen" und bleiben ignoriert.
        self._midi_in.ignore_types(sysex=False, timing=True, active_sense=True)
        # Ab jetzt ruft rtmidi bei jeder Nachricht self._on_message auf -
        # im internen MIDI-Thread.
        self._midi_in.set_callback(self._on_message)

    # ------------------------------------------------------------------
    # Empfang (laeuft im rtmidi-MIDI-Thread!)
    # ------------------------------------------------------------------
    def _on_message(self, event, _data=None) -> None:
        """Callback von rtmidi. ACHTUNG: laeuft im fremden MIDI-Thread.

        rtmidi uebergibt ``event`` als Tupel ``(bytes, zeitstempel)``. Das
        zweite Argument ``_data`` ist ein optionaler Nutzkontext, den wir nicht
        verwenden. Wir interessieren uns nur fuer die Bytes und legen sie als
        Liste in die Queue. Hier wird bewusst NICHTS an der UI gemacht.
        """
        message, _timestamp = event
        self._queue.put(list(message))

    def poll(self) -> List[List[int]]:
        """Alle seit dem letzten Aufruf eingegangenen Nachrichten zurueckgeben.

        Wird vom Hauptthread (spaeter im Kivy-Takt) aufgerufen und leert den
        "Briefkasten". Jede Nachricht ist eine Liste von Byte-Werten.
        """
        nachrichten: List[List[int]] = []
        while True:
            try:
                nachrichten.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return nachrichten

    # ------------------------------------------------------------------
    # Senden
    # ------------------------------------------------------------------
    def send(self, message: Sequence[int]) -> None:
        """Rohe MIDI-Bytes senden.

        Wirft ``RuntimeError``, wenn kein Ausgang geoeffnet ist - das deutet
        fast immer auf einen Programmierfehler hin (senden ohne Verbindung).
        """
        if not self._output_open:
            raise RuntimeError("Kein MIDI-Ausgang geoeffnet - zuerst open()/open_virtual() aufrufen")
        self._midi_out.send_message(list(message))

    # ------------------------------------------------------------------
    # Aufraeumen
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Ports schliessen und Ressourcen freigeben. Mehrfach aufrufbar."""
        if self._input_open:
            self._midi_in.cancel_callback()
            self._midi_in.close_port()
            self._input_open = False
        if self._output_open:
            self._midi_out.close_port()
            self._output_open = False

    # Als Kontextmanager nutzbar: "with MidiBackend() as backend: ..."
    def __enter__(self) -> "MidiBackend":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
