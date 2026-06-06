"""Tests fuer ``MidiBackend``.

Der wichtigste Test (``test_loopback_*``) prueft echtes Senden/Empfangen:
Ein "Geraet"-Backend bietet einen virtuellen Port an, ein zweites Backend
verbindet sich per Namen damit. So koennen wir ohne externe Hardware und ohne
DAW pruefen, dass Bytes wirklich ankommen.
"""

from __future__ import annotations

import os
import time

import pytest

from touchcontrol.midi import MidiBackend

# Eindeutiger Portname je Prozess: enthaelt die PID, damit parallele oder
# uebrig gebliebene Testlaeufe nicht denselben virtuellen Port erzeugen. Genau
# solche Namenskollisionen fuehren sonst zu spurious Fehlern oder CoreMIDI-Haengern.
PORT_NAME = f"TouchControl PyTest {os.getpid()}"


def warte_auf_nachricht(backend: MidiBackend, timeout: float = 2.0):
    """Pollt wiederholt, bis Nachrichten ankommen oder die Zeit ablaeuft.

    Noetig, weil der Empfang asynchron im MIDI-Thread passiert - wir koennen
    nicht erwarten, dass die Nachricht im selben Sekundenbruchteil schon da ist.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        nachrichten = backend.poll()
        if nachrichten:
            return nachrichten
        time.sleep(0.01)
    return []


def test_available_inputs_outputs_geben_listen():
    backend = MidiBackend()
    assert isinstance(backend.available_inputs(), list)
    assert isinstance(backend.available_outputs(), list)
    backend.close()


def test_find_port_per_teilstring():
    ports = ["IAC Driver Bus 1", "Mackie Control", "TouchControl PyTest"]
    assert MidiBackend._find_port(ports, "iac") == 0
    assert MidiBackend._find_port(ports, "Mackie") == 1
    assert MidiBackend._find_port(ports, "gibt-es-nicht") is None


def test_open_unbekannter_port_wirft():
    backend = MidiBackend()
    with pytest.raises(ValueError):
        backend.open(input_name="diesen-port-gibt-es-sicher-nicht-123")
    backend.close()


def test_send_ohne_ausgang_wirft():
    backend = MidiBackend()
    with pytest.raises(RuntimeError):
        backend.send([0x90, 60, 100])
    backend.close()


def test_poll_ohne_nachrichten_ist_leer():
    backend = MidiBackend()
    assert backend.poll() == []
    backend.close()


def test_close_ist_mehrfach_aufrufbar():
    backend = MidiBackend()
    backend.close()
    backend.close()  # darf nicht abstuerzen


def test_loopback_senden_und_empfangen():
    """Zwei Backends: eines bietet einen virtuellen Port an, das andere sendet."""
    geraet = MidiBackend()       # spielt das "Geraet" (bietet Port an)
    gegenstelle = MidiBackend()  # spielt die "DAW" (verbindet sich, sendet)

    try:
        geraet.open_virtual(PORT_NAME)
        # Kurze Pause, damit der virtuelle Port im System sichtbar wird.
        time.sleep(0.2)

        # Die Gegenstelle sendet an den virtuellen Eingang des Geraets.
        gegenstelle.open(output_name=PORT_NAME)

        testnachricht = [0xE0, 0x00, 0x40]  # Pitch-Bend (Fader) als Beispiel
        gegenstelle.send(testnachricht)

        empfangen = warte_auf_nachricht(geraet)
        assert testnachricht in empfangen
    finally:
        geraet.close()
        gegenstelle.close()


def test_loopback_sysex_wird_empfangen():
    """SysEx (fuer LCD/Kanalnamen) muss durchkommen - rtmidi ignoriert es sonst."""
    geraet = MidiBackend()
    gegenstelle = MidiBackend()

    try:
        geraet.open_virtual(PORT_NAME)
        time.sleep(0.2)
        gegenstelle.open(output_name=PORT_NAME)

        # Verkuerzter MCU-LCD-SysEx-Rahmen als Beispiel.
        sysex = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00, 0x41, 0xF7]
        gegenstelle.send(sysex)

        empfangen = warte_auf_nachricht(geraet)
        assert sysex in empfangen
    finally:
        geraet.close()
        gegenstelle.close()
