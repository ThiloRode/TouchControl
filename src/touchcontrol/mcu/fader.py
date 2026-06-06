"""Fader-Kodierung fuer das Mackie-Control-Protokoll.

Ein Fader wird beim MCU als **Pitch-Bend**-Nachricht uebertragen - pro Kanal
eine eigene. Die Nachricht besteht aus drei Bytes::

    Byte 1: 0xE0 + kanal     Statusbyte (0xE0 = Pitch-Bend), kanal 0-7
    Byte 2: LSB              untere 7 Bit des 14-bit-Werts
    Byte 3: MSB              obere 7 Bit des 14-bit-Werts

Hintergrund 14 Bit: MIDI-Datenbytes haben nur 7 nutzbare Bits (0-127). Um
feiner aufzuloesen, kombiniert MCU zwei davon zu einem 14-bit-Wert (0-16383)::

    wert = (MSB << 7) | LSB

Wir uebertragen die **Faderposition linear** ueber den Weg (0.0 = ganz unten,
1.0 = ganz oben). Die Uebersetzung Position -> Dezibel macht die DAW anhand
ihrer eigenen Fader-Kennlinie - genau wie bei einer echten Motorfader-MCU.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

#: Statusbyte fuer Pitch-Bend auf Kanal 0 (Kanaele 1-8 -> 0xE0..0xE7).
PITCH_BEND_STATUS = 0xE0

#: Hoechster 14-bit-Wert, den Cubase als MCU-Fader sendet (+6.02 dB).
#: Cubase benutzt nie den vollen MIDI-Bereich (0x3FFF), sondern stoppt bei
#: 0x3BB1. Diesen Wert als Normierungs-Maximum zu verwenden sorgt dafuer,
#: dass Cubase-Fader-Maximum == Slider-Maximum in der UI.
MAX_14BIT = 0x3BB1  # = 15281

#: Anzahl der Kanaele einer MCU-Einheit (eine Bank).
CHANNEL_COUNT = 8


def fader_to_pitch_bend(channel: int, position: float) -> List[int]:
    """Eine Faderposition in eine MCU-Pitch-Bend-Nachricht umwandeln.

    :param channel: Kanal 0-7 (entspricht den 8 Kanalzuegen einer Bank).
    :param position: Faderposition 0.0 (unten) bis 1.0 (oben).
    :returns: Drei MIDI-Bytes ``[0xE0+channel, lsb, msb]``.
    :raises ValueError: bei ungueltigem Kanal.

    Die Position wird vor der Umrechnung auf den Bereich 0.0-1.0 begrenzt
    (geclamped), damit kleine Rundungsfehler aus der UI nicht zu ungueltigen
    MIDI-Werten fuehren.
    """
    if not 0 <= channel < CHANNEL_COUNT:
        raise ValueError(f"Kanal muss 0..{CHANNEL_COUNT - 1} sein, war {channel}")

    # Position auf [0.0, 1.0] begrenzen.
    position = max(0.0, min(1.0, position))

    # Linear auf den 14-bit-Bereich abbilden; round() fuer faire Rundung.
    value = round(position * MAX_14BIT)

    # In zwei 7-bit-Haelften zerlegen.
    lsb = value & 0x7F          # untere 7 Bit
    msb = (value >> 7) & 0x7F   # obere 7 Bit

    return [PITCH_BEND_STATUS + channel, lsb, msb]


def pitch_bend_to_fader(message: Sequence[int]) -> Tuple[int, float]:
    """Eine MCU-Pitch-Bend-Nachricht in (Kanal, Position) umwandeln.

    Gegenstueck zu :func:`fader_to_pitch_bend`.

    :param message: Drei MIDI-Bytes ``[0xE0+channel, lsb, msb]``.
    :returns: Tupel ``(channel, position)`` mit Position 0.0-1.0.
    :raises ValueError: wenn die Nachricht kein Pitch-Bend ist oder die
        falsche Laenge hat.
    """
    if len(message) != 3:
        raise ValueError(f"Pitch-Bend braucht 3 Bytes, waren {len(message)}")

    status, lsb, msb = message

    # Oberes Nibble des Statusbytes muss 0xE sein (Pitch-Bend).
    if status & 0xF0 != PITCH_BEND_STATUS:
        raise ValueError(f"Kein Pitch-Bend-Status: {status:#04x}")

    channel = status & 0x0F
    if channel >= CHANNEL_COUNT:
        raise ValueError(f"Kanal {channel} ausserhalb 0..{CHANNEL_COUNT - 1}")

    # Zwei 7-bit-Haelften zum 14-bit-Wert zusammensetzen und auf 0.0-1.0 normieren.
    # Werte ueber MAX_14BIT (z. B. von anderer DAW) werden auf 1.0 begrenzt.
    value = (msb << 7) | lsb
    position = min(1.0, value / MAX_14BIT)

    return channel, position
