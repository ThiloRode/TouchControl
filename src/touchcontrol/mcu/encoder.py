"""``McuEncoder`` - baut MIDI-Bytes aus semantischen Absichten.

Der Encoder ist das Gegenstueck zum :class:`~touchcontrol.mcu.decoder.McuDecoder`.
Waehrend der Decoder eingehende Bytes in Events uebersetzt, baut der Encoder aus
einfachen Python-Werten (Floats, Ints, Booleans) die passenden MIDI-Bytes, die
die DAW erwartet.

Auch hier gilt: **reine Logik**, kein I/O, keine UI - vollstaendig mit pytest
testbar. Das eigentliche Senden uebernimmt weiterhin der ``MidiBackend``.

Bisher enthalten:

* :meth:`McuEncoder.host_connection_reply` -- Antwortet auf den Verbindungs-
  Handshake von Cubase/DAW.
* :meth:`McuEncoder.fader_position` -- Kodiert eine Faderposition als
  Pitch-Bend-Nachricht (delegiert an :func:`~touchcontrol.mcu.fader.fader_to_pitch_bend`).
"""

from __future__ import annotations

from typing import List

from .constants import VPOT_ROTATE_BASE
from .fader import fader_to_pitch_bend

# Mackie-Hersteller-ID (drei Bytes nach dem SysEx-Start 0xF0).
_MACKIE_MFR: List[int] = [0x00, 0x00, 0x66]

# MCU-Befehle (Ausgabe-Richtung, App -> DAW).
_CMD_HOST_REPLY = 0x1B  # Antwort auf den Host-Connection-Query der DAW.

# Status-Bytes (immer MIDI-Kanal 0 bei MCU).
_NOTE_ON = 0x90
_CONTROL_CHANGE = 0xB0

# Velocity fuer Note Bangs.
_VELOCITY_ON = 0x7F
_VELOCITY_OFF = 0x00


class McuEncoder:
    """Baut rohe MIDI-Bytes aus semantischen Werten.

    Typische Nutzung::

        encoder = McuEncoder()
        backend.send(encoder.host_connection_reply(device_id=0x14))
        backend.send(encoder.fader_position(channel=0, position=0.75))
    """

    def host_connection_reply(self, device_id: int = 0x14) -> List[int]:
        """Antwortet auf den MCU-Host-Connection-Query der DAW.

        Cubase sendet ``F0 00 00 66 14 1A ... F7`` beim Verbinden und als
        periodischen Heartbeat. Ohne Antwort gilt das Geraet als nicht
        verbunden - Cubase schickt dann immer wieder Resets (alle Fader auf 0,
        alle LEDs aus).

        Die Antwort (``1B``) enthaelt 7 Seriennummer-Bytes und 4 Challenge-
        Response-Bytes. Fuer eine virtuelle Implementierung geniuegen Nullen -
        Cubase prueft die Inhalte nicht, nur das Kommando (``1B``) zaehlt.

        :param device_id: Geraete-ID: ``0x14`` = MCU Main, ``0x15`` = Extender XT.
        :returns: Fertige SysEx-Nachricht als Liste von Byte-Werten.
        """
        seriennummer = [0x00] * 7       # 7 Bytes - beliebig, wir nehmen Nullen.
        challenge_response = [0x00] * 4  # 4 Bytes - wird von Cubase ignoriert.
        return [0xF0, *_MACKIE_MFR, device_id, _CMD_HOST_REPLY,
                *seriennummer, *challenge_response, 0xF7]

    def fader_position(self, channel: int, position: float) -> List[int]:
        """Faderposition als Pitch-Bend-Nachricht kodieren.

        Delegiert an :func:`~touchcontrol.mcu.fader.fader_to_pitch_bend`.

        :param channel: Kanal 0-7.
        :param position: 0.0 (unten) bis 1.0 (oben).
        :returns: Drei Bytes ``[0xE0+kanal, lsb, msb]``.
        """
        return fader_to_pitch_bend(channel, position)

    def button_bang(self, note: int) -> List[List[int]]:
        """Einen Taster-Druck als Note Bang kodieren (Press + Release).

        MCU erwartet pro Tastendruck eine Note-On (Velocity ``0x7F``) direkt
        gefolgt von einer Note-On mit Velocity ``0x00`` (Release). Die DAW
        togglet daraufhin die Funktion und meldet den neuen LED-Zustand zurueck.

        :param note: MIDI-Note des Tasters (siehe :mod:`touchcontrol.mcu.constants`).
        :returns: Liste aus zwei MIDI-Nachrichten (Press, Release).
        """
        return [
            [_NOTE_ON, note, _VELOCITY_ON],
            [_NOTE_ON, note, _VELOCITY_OFF],
        ]

    def vpot_rotate(self, channel: int, ticks: int) -> List[int]:
        """Eine V-Pot-Drehung (Pan) als relative Control-Change-Nachricht kodieren.

        MCU-V-Pots sind **relative** Encoder: Es wird nicht die Position,
        sondern die Drehrichtung und -menge gesendet. Bit 6 des Wert-Bytes ist
        das Vorzeichen (0 = im Uhrzeigersinn, 1 = gegen), Bits 0-5 die Anzahl
        der Schritte.

        :param channel: Kanal 0-7.
        :param ticks: Schritte; positiv = rechts (lauter/rechts), negativ = links.
        :returns: Drei Bytes ``[0xB0, 0x10+kanal, wert]``.
        """
        cc = VPOT_ROTATE_BASE + channel
        anzahl = min(0x3F, abs(int(ticks)))  # auf 6 Bit begrenzen.
        if ticks < 0:
            value = 0x40 | anzahl  # Bit 6 gesetzt = gegen den Uhrzeigersinn.
        else:
            value = anzahl
        return [_CONTROL_CHANGE, cc, value]
