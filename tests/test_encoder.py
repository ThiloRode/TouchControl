"""Tests fuer den ``McuEncoder``."""

from __future__ import annotations

from touchcontrol.mcu import McuEncoder
from touchcontrol.mcu.fader import fader_to_pitch_bend


def test_button_bang_press_und_release():
    """button_bang liefert Note-On (an) gefolgt von Note-On (aus)."""
    encoder = McuEncoder()
    msgs = encoder.button_bang(0x10)
    assert msgs == [[0x90, 0x10, 0x7F], [0x90, 0x10, 0x00]]


def test_vpot_rotate_im_uhrzeigersinn():
    encoder = McuEncoder()
    # Kanal 0, 3 Schritte rechts -> CC 0x10, Wert 0x03.
    assert encoder.vpot_rotate(0, 3) == [0xB0, 0x10, 0x03]


def test_vpot_rotate_gegen_uhrzeigersinn():
    encoder = McuEncoder()
    # Kanal 1, 2 Schritte links -> CC 0x11, Wert 0x42 (Bit 6 + 2).
    assert encoder.vpot_rotate(1, -2) == [0xB0, 0x11, 0x42]


def test_vpot_rotate_begrenzt_auf_6bit():
    encoder = McuEncoder()
    # Sehr grosse Schrittzahl wird auf 0x3F begrenzt.
    assert encoder.vpot_rotate(0, 1000) == [0xB0, 0x10, 0x3F]


def test_host_connection_reply_format_main():
    """Reply fuer Main-Geraet hat korrekten Aufbau."""
    encoder = McuEncoder()
    reply = encoder.host_connection_reply(device_id=0x14)

    # Rahmen: SysEx-Start und Ende.
    assert reply[0] == 0xF0
    assert reply[-1] == 0xF7

    # Mackie-Hersteller-ID.
    assert reply[1:4] == [0x00, 0x00, 0x66]

    # Geraete-ID und Befehls-Byte.
    assert reply[4] == 0x14  # Main
    assert reply[5] == 0x1B  # Host-Connection-Reply

    # Gesamtlaenge: F0 + 3 Hersteller + device_id + Befehl + 7 Seriennummer + 4 Challenge + F7
    assert len(reply) == 18


def test_host_connection_reply_format_extender():
    """Reply fuer Extender XT verwendet device_id 0x15."""
    encoder = McuEncoder()
    reply = encoder.host_connection_reply(device_id=0x15)
    assert reply[4] == 0x15


def test_host_connection_reply_alle_bytes_gueltig():
    """Alle Bytes muessen MIDI-gueltig sein (0x00-0x7F), ausser dem Rahmen."""
    encoder = McuEncoder()
    reply = encoder.host_connection_reply()
    # Datenbytes (alles zwischen F0 und F7) duerfen kein gesetztes oberste Bit haben.
    for byte in reply[1:-1]:
        assert byte <= 0x7F, f"Ungueltigers Datenbyte: {byte:#04x}"


def test_fader_position_delegiert_korrekt():
    """fader_position() muss dasselbe liefern wie fader_to_pitch_bend()."""
    encoder = McuEncoder()
    assert encoder.fader_position(0, 0.5) == fader_to_pitch_bend(0, 0.5)
    assert encoder.fader_position(7, 1.0) == fader_to_pitch_bend(7, 1.0)
    assert encoder.fader_position(3, 0.0) == fader_to_pitch_bend(3, 0.0)
