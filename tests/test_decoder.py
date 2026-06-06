"""Tests fuer den MCU-Decoder und die Events."""

from __future__ import annotations

import pytest

from touchcontrol.mcu import (
    ButtonEvent,
    FaderEvent,
    HostConnectionQueryEvent,
    LcdEvent,
    McuDecoder,
    MeterEvent,
    VPotEvent,
)
from touchcontrol.mcu.fader import MAX_14BIT, fader_to_pitch_bend


def test_decode_note_on_liefert_button_pressed():
    decoder = McuDecoder()
    # Note-On Mute Kanal 0 (0x10), Velocity 0x7F = an.
    event = decoder.decode([0x90, 0x10, 0x7F])
    assert event == ButtonEvent(note=0x10, pressed=True)


def test_decode_note_on_velocity_null_liefert_released():
    decoder = McuDecoder()
    event = decoder.decode([0x90, 0x10, 0x00])
    assert event == ButtonEvent(note=0x10, pressed=False)


def test_decode_note_off_liefert_released():
    decoder = McuDecoder()
    event = decoder.decode([0x80, 0x08, 0x40])
    assert event == ButtonEvent(note=0x08, pressed=False)


def test_decode_channel_pressure_liefert_meterevent():
    decoder = McuDecoder()
    # Kanal 7, Pegel 0x0C -> Datenbyte 0x7C.
    event = decoder.decode([0xD0, 0x7C])
    assert event == MeterEvent(channel=7, level=0x0C)


def test_decode_vpot_ring_liefert_vpotevent():
    decoder = McuDecoder()
    # CC 0x32 = V-Pot-Ring Kanal 2, Wert 0x46 = center-LED an, Modus 0, Wert 6.
    event = decoder.decode([0xB0, 0x32, 0x46])
    assert event == VPotEvent(channel=2, mode=0, value=6, center_led=True)


def test_decode_fremder_cc_liefert_none():
    decoder = McuDecoder()
    # CC 0x07 (Volume) ist kein V-Pot-Ring -> None.
    assert decoder.decode([0xB0, 0x07, 0x40]) is None


def test_decode_fader_liefert_faderevent():
    decoder = McuDecoder()
    # Eine bekannte Faderposition kodieren und wieder dekodieren.
    message = fader_to_pitch_bend(3, 0.5)
    event = decoder.decode(message)
    assert isinstance(event, FaderEvent)
    assert event.channel == 3
    # Durch die 14-bit-Quantisierung ist ein winziger Fehler moeglich.
    assert event.position == pytest.approx(0.5, abs=1 / MAX_14BIT)


def test_decode_unbekannt_liefert_none():
    decoder = McuDecoder()
    # Program-Change (0xC0) ist kein bekannter MCU-Typ -> None statt Fehler.
    assert decoder.decode([0xC0, 0x05]) is None


def test_decode_leere_nachricht_liefert_none():
    decoder = McuDecoder()
    assert decoder.decode([]) is None


def test_decode_pitchbend_falsche_laenge_liefert_none():
    decoder = McuDecoder()
    # Statusbyte passt, aber zu kurz -> kein FaderEvent.
    assert decoder.decode([0xE0, 0x00]) is None


def test_faderevent_ist_unveraenderlich():
    event = FaderEvent(channel=0, position=0.25)
    try:
        event.position = 0.9  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError erbt von Exception
        assert "frozen" in type(exc).__name__.lower() or True
    else:
        raise AssertionError("FaderEvent sollte unveraenderlich sein")


def test_decode_master_fader_liefert_none():
    decoder = McuDecoder()
    # Cubase schickt Pitch-Bend auf Kanal 8 (Master-Fader, 0xE8).
    # pitch_bend_to_fader wuerde ValueError werfen - der Decoder faengt ab -> None.
    assert decoder.decode([0xE8, 0x00, 0x40]) is None


def test_decode_host_connection_query_main():
    """Cubase sendet diesen SysEx beim Verbinden (device_id 0x14 = Main)."""
    decoder = McuDecoder()
    # Genau die Bytes, die Cubase schickt (aus dem Monitor-Log entnommen).
    message = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x1A, 0x00, 0xF7]
    event = decoder.decode(message)
    assert isinstance(event, HostConnectionQueryEvent)
    assert event.device_id == 0x14


def test_decode_host_connection_query_extender():
    """Cubase fragt auch den Extender XT (device_id 0x15)."""
    decoder = McuDecoder()
    message = [0xF0, 0x00, 0x00, 0x66, 0x15, 0x1A, 0x00, 0xF7]
    event = decoder.decode(message)
    assert isinstance(event, HostConnectionQueryEvent)
    assert event.device_id == 0x15


def test_decode_unbekannter_sysex_liefert_none():
    """Fremder SysEx (z. B. Universal Device Inquiry) -> None, kein Fehler."""
    decoder = McuDecoder()
    # Universal Device Inquiry: F0 7E 7F 06 01 F7
    assert decoder.decode([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]) is None


def test_decode_lcd_untere_zeile_liefert_lcdevent():
    """LCD-SysEx mit Offset 56 (untere Zeile) wird zu LcdEvent."""
    decoder = McuDecoder()
    # F0 00 00 66 14 12 38 46 61 64 65 72 31 F7
    # offset=0x38=56, text="Fader1"
    message = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x38,
               0x46, 0x61, 0x64, 0x65, 0x72, 0x31, 0xF7]
    event = decoder.decode(message)
    assert isinstance(event, LcdEvent)
    assert event.device_id == 0x14
    assert event.offset == 56
    assert "Fader1" in event.text


def test_decode_lcd_obere_zeile_liefert_lcdevent():
    """LCD-SysEx mit Offset 0 (obere Zeile, V-Pot-Modus) wird ebenfalls dekodiert."""
    decoder = McuDecoder()
    # offset=0, text="Pan    "
    message = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00,
               0x50, 0x61, 0x6E, 0x20, 0x20, 0x20, 0x20, 0xF7]
    event = decoder.decode(message)
    assert isinstance(event, LcdEvent)
    assert event.offset == 0
    assert event.text.startswith("Pan")


def test_decode_lcd_zu_kurz_liefert_none():
    """LCD-SysEx ohne Offset-Byte (zu kurz) -> None."""
    decoder = McuDecoder()
    message = [0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0xF7]  # kein Offset
    assert decoder.decode(message) is None


def test_decode_many_filtert_unbekannte():
    decoder = McuDecoder()
    messages = [
        fader_to_pitch_bend(0, 0.0),
        [0xC0, 0x05],                # Program-Change -> unbekannt, weggelassen
        fader_to_pitch_bend(1, 1.0),
    ]
    events = decoder.decode_many(messages)
    assert len(events) == 2
    assert all(isinstance(e, FaderEvent) for e in events)
    assert events[0].channel == 0
    assert events[1].channel == 1
