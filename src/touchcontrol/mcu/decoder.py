"""``McuDecoder`` - uebersetzt rohe MIDI-Nachrichten in semantische Events.

Der Decoder ist das Gegenstueck zum (spaeteren) Encoder. Er bekommt eine rohe
MIDI-Nachricht (Liste von Byte-Werten) und gibt das passende
:class:`~touchcontrol.mcu.events.McuEvent` zurueck - oder ``None``, wenn die
Nachricht zu keinem bekannten Typ gehoert (z. B. der Verbindungs-Ping der DAW).

Bewusst **reine Logik**: kein MIDI-I/O, keine UI. Dadurch vollstaendig mit
pytest testbar.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from .constants import VPOT_RING_BASE
from .events import (
    ButtonEvent,
    FaderEvent,
    HostConnectionQueryEvent,
    LcdEvent,
    McuEvent,
    MeterEvent,
    VPotEvent,
)
from .fader import pitch_bend_to_fader

# Oberes Nibble eines Pitch-Bend-Statusbytes (Fader).
_PITCH_BEND = 0xE0

# Weitere Status-Nibbles (Kanal steht im unteren Nibble, hier irrelevant).
_NOTE_ON = 0x90          # Taster/LED (Note Bang).
_NOTE_OFF = 0x80         # Manche Geraete senden echtes Note-Off.
_CONTROL_CHANGE = 0xB0   # V-Pot-Ring (Pan-Anzeige).
_CHANNEL_PRESSURE = 0xD0  # VU-Meter.

# SysEx-Kennung: Mackie-Hersteller-ID (drei Bytes nach dem 0xF0).
_SYSEX_START = 0xF0
_MACKIE_MFR = (0x00, 0x00, 0x66)
# MCU-Befehle im SysEx (Byte[5]).
_CMD_HOST_QUERY = 0x1A  # DAW fragt: "Bist du da?"
_CMD_LCD_WRITE = 0x12   # DAW schreibt Text ins Display.


class McuDecoder:
    """Wandelt rohe MIDI-Nachrichten in :class:`McuEvent`-Objekte um."""

    def decode(self, message: Sequence[int]) -> Optional[McuEvent]:
        """Eine einzelne MIDI-Nachricht dekodieren.

        :param message: Rohe MIDI-Bytes (z. B. ``[0xE0, 0x6C, 0x5E]``).
        :returns: Passendes Event oder ``None``, wenn unbekannt/uninteressant.
        """
        if not message:
            return None

        status = message[0]
        high_nibble = status & 0xF0

        # --- Fader (Pitch-Bend) -------------------------------------------
        # Kanal 8 (0xE8) ist der Master-Fader – wir ignorieren ihn vorerst.
        # ValueError aus pitch_bend_to_fader (ungültiger Kanal o.ä.) → None.
        if high_nibble == _PITCH_BEND and len(message) == 3:
            try:
                channel, position = pitch_bend_to_fader(message)
                return FaderEvent(channel=channel, position=position)
            except ValueError:
                return None

        # --- Taster / LED (Note Bang) -------------------------------------
        # Note-On mit Velocity 0x7F = an, 0x00 = aus. Manche senden Note-Off.
        if high_nibble == _NOTE_ON and len(message) == 3:
            note, velocity = message[1], message[2]
            return ButtonEvent(note=note, pressed=velocity != 0)
        if high_nibble == _NOTE_OFF and len(message) == 3:
            return ButtonEvent(note=message[1], pressed=False)

        # --- VU-Meter (Channel Pressure) ----------------------------------
        # Datenbyte: oberes Nibble = Kanal, unteres Nibble = Pegel 0-15.
        if high_nibble == _CHANNEL_PRESSURE and len(message) == 2:
            value = message[1]
            return MeterEvent(channel=value >> 4, level=value & 0x0F)

        # --- V-Pot-LED-Ring (Control Change, Pan-Anzeige) -----------------
        if high_nibble == _CONTROL_CHANGE and len(message) == 3:
            cc, value = message[1], message[2]
            if VPOT_RING_BASE <= cc < VPOT_RING_BASE + 8:
                return VPotEvent(
                    channel=cc - VPOT_RING_BASE,
                    mode=(value >> 4) & 0x03,
                    value=value & 0x0F,
                    center_led=bool(value & 0x40),
                )
            return None  # Andere CCs interessieren uns nicht.

        # --- Mackie-SysEx -------------------------------------------------
        # Mindestlaenge: F0 + 3 Hersteller + device_id + Befehl = 6 Bytes.
        if status == _SYSEX_START and len(message) >= 6:
            if tuple(message[1:4]) == _MACKIE_MFR:
                device_id = message[4]
                command = message[5]
                if command == _CMD_HOST_QUERY:
                    return HostConnectionQueryEvent(device_id=device_id)

                # --- LCD-Schreib-Befehl (Kanalname / V-Pot-Anzeige) --------
                # Mindestlaenge: F0 + 3 Hersteller + device_id + Befehl + offset + F7 = 8.
                if command == _CMD_LCD_WRITE and len(message) >= 8:
                    offset = message[6]
                    # Bytes 7 bis vorletztes Byte sind ASCII-Zeichen.
                    # Nicht-druckbare Bytes werden als Leerzeichen behandelt,
                    # damit die Textlaenge mit dem Byte-Offset uebereinstimmt.
                    text_bytes = message[7:-1]  # ohne abschliessendes F7
                    text = "".join(
                        chr(b) if 0x20 <= b <= 0x7E else " " for b in text_bytes
                    )
                    return LcdEvent(device_id=device_id, offset=offset, text=text)

        # Unbekannt/uninteressant -> bewusst None (kein Fehler).
        return None

    def decode_many(self, messages: Sequence[Sequence[int]]) -> List[McuEvent]:
        """Mehrere Nachrichten dekodieren; unbekannte werden weggelassen.

        Praktisch fuer ``decoder.decode_many(backend.poll())``.
        """
        events: List[McuEvent] = []
        for message in messages:
            event = self.decode(message)
            if event is not None:
                events.append(event)
        return events
