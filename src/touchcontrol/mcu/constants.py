"""Zentrale MCU-Protokoll-Konstanten (Note-Nummern und CC-Nummern).

Damit Decoder, Encoder und State dieselben Werte benutzen und nicht jeder
seine eigenen "magischen Zahlen" definiert, stehen alle MCU-Adressen hier an
einer Stelle. Quelle: offizielle Mackie-Control-/Logic-Control-Referenz.

Jeder Kanalzug (0-7) hat eigene Note-Nummern fuer seine Taster. Die Basis-Note
ist die des ersten Kanals; Kanal *n* liegt bei ``BASE + n``.
"""

from __future__ import annotations

# --- Pro-Kanal-Taster (Note Bang: Note-On velocity 0x7F = an, 0x00 = aus) ---
REC_BASE = 0x00      # REC/Arm: 0x00-0x07
SOLO_BASE = 0x08     # SOLO:    0x08-0x0F
MUTE_BASE = 0x10     # MUTE:    0x10-0x17
SELECT_BASE = 0x18   # SELECT:  0x18-0x1F
VPOT_SWITCH_BASE = 0x20  # V-Pot-Klick: 0x20-0x27

# --- V-Pot (Pan) ueber Control-Change ---
VPOT_ROTATE_BASE = 0x10  # Controller -> DAW: Drehung, CC 0x10-0x17
VPOT_RING_BASE = 0x30    # DAW -> Controller: LED-Ring, CC 0x30-0x37

# Anzahl Kanaele einer Surface.
CHANNEL_COUNT = 8
