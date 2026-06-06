"""Tests fuer die MCU-Fader-Kodierung (Pitch-Bend, 14-bit)."""

from __future__ import annotations

import pytest

from touchcontrol.mcu import fader_to_pitch_bend, pitch_bend_to_fader
from touchcontrol.mcu.fader import CHANNEL_COUNT, MAX_14BIT, PITCH_BEND_STATUS


# ----------------------------------------------------------------------
# fader_to_pitch_bend
# ----------------------------------------------------------------------
def test_unten_ist_null():
    # Position 0.0 -> Wert 0 -> beide Datenbytes 0.
    assert fader_to_pitch_bend(0, 0.0) == [0xE0, 0x00, 0x00]


def test_oben_ist_maximum():
    # Position 1.0 -> MAX_14BIT (0x3BB1 = 15281) -> LSB=0x31, MSB=0x77.
    assert fader_to_pitch_bend(0, 1.0) == [0xE0, 0x31, 0x77]


def test_statusbyte_enthaelt_kanal():
    # Kanal landet im unteren Nibble des Statusbytes.
    for channel in range(CHANNEL_COUNT):
        status = fader_to_pitch_bend(channel, 0.5)[0]
        assert status == PITCH_BEND_STATUS + channel


def test_position_wird_geclamped():
    # Werte ausserhalb 0..1 werden begrenzt, nicht abgelehnt.
    assert fader_to_pitch_bend(0, -1.0) == [0xE0, 0x00, 0x00]
    assert fader_to_pitch_bend(0, 2.0) == [0xE0, 0x31, 0x77]


def test_ungueltiger_kanal_wirft():
    with pytest.raises(ValueError):
        fader_to_pitch_bend(8, 0.5)
    with pytest.raises(ValueError):
        fader_to_pitch_bend(-1, 0.5)


def test_datenbytes_immer_7bit():
    # Egal welche Position: LSB und MSB duerfen nie das oberste Bit setzen.
    for i in range(0, 101):
        _, lsb, msb = fader_to_pitch_bend(0, i / 100)
        assert 0 <= lsb <= 0x7F
        assert 0 <= msb <= 0x7F


# ----------------------------------------------------------------------
# pitch_bend_to_fader
# ----------------------------------------------------------------------
def test_decode_minimum_und_maximum():
    assert pitch_bend_to_fader([0xE0, 0x00, 0x00]) == (0, 0.0)
    # MAX_14BIT (0x3BB1) dekodiert exakt zu 1.0.
    assert pitch_bend_to_fader([0xE0, 0x31, 0x77]) == (0, 1.0)
    # Werte ueber MAX_14BIT (alter MIDI-Max 0x3FFF) werden auf 1.0 begrenzt.
    assert pitch_bend_to_fader([0xE0, 0x7F, 0x7F]) == (0, 1.0)


def test_decode_liest_kanal():
    channel, _ = pitch_bend_to_fader([0xE5, 0x00, 0x40])
    assert channel == 5


def test_decode_falsche_laenge_wirft():
    with pytest.raises(ValueError):
        pitch_bend_to_fader([0xE0, 0x00])


def test_decode_kein_pitchbend_wirft():
    # 0x90 = Note-On, kein Pitch-Bend.
    with pytest.raises(ValueError):
        pitch_bend_to_fader([0x90, 0x00, 0x00])


# ----------------------------------------------------------------------
# Round-Trip: encode -> decode ergibt wieder den Startwert
# ----------------------------------------------------------------------
@pytest.mark.parametrize("channel", list(range(CHANNEL_COUNT)))
@pytest.mark.parametrize("position", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_round_trip(channel, position):
    message = fader_to_pitch_bend(channel, position)
    decoded_channel, decoded_position = pitch_bend_to_fader(message)
    assert decoded_channel == channel
    # Durch die 14-bit-Quantisierung ist ein winziger Fehler moeglich.
    assert decoded_position == pytest.approx(position, abs=1 / MAX_14BIT)
