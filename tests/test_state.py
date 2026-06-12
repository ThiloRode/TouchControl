"""Tests fuer das State-Modell (ChannelState und MixerState)."""

from __future__ import annotations

import pytest

from touchcontrol.model import ChannelState, MixerState
from touchcontrol.mcu import ButtonEvent, FaderEvent, LcdEvent, MeterEvent, VPotEvent
from touchcontrol.mcu.constants import (
    MUTE_BASE,
    REC_BASE,
    SELECT_BASE,
    SOLO_BASE,
)


# ======================================================================
# ChannelState
# ======================================================================

def test_channel_state_standardwerte():
    """Alle Felder haben sinnvolle Anfangswerte."""
    kanal = ChannelState(channel=0)
    assert kanal.channel == 0
    assert kanal.fader_position == 0.0
    assert kanal.meter_level == 0
    assert kanal.mute is False
    assert kanal.solo is False
    assert kanal.select is False
    assert kanal.rec is False
    assert kanal.name == ""


def test_channel_state_update_aendert_feld():
    kanal = ChannelState(channel=0)
    kanal.update(fader_position=0.75)
    assert kanal.fader_position == pytest.approx(0.75)


def test_channel_state_update_mehrere_felder():
    kanal = ChannelState(channel=0)
    kanal.update(mute=True, name="Bass")
    assert kanal.mute is True
    assert kanal.name == "Bass"


def test_channel_state_update_unbekanntes_feld_wirft():
    kanal = ChannelState(channel=0)
    with pytest.raises(AttributeError):
        kanal.update(gibt_es_nicht=True)


def test_channel_state_listener_wird_aufgerufen():
    """Observer-Callback bekommt den ChannelState uebergeben."""
    kanal = ChannelState(channel=2)
    empfangen: list[ChannelState] = []

    kanal.add_listener(empfangen.append)
    kanal.update(fader_position=0.5)

    assert len(empfangen) == 1
    assert empfangen[0] is kanal
    assert empfangen[0].fader_position == pytest.approx(0.5)


def test_channel_state_mehrere_listener():
    kanal = ChannelState(channel=0)
    zaehler = [0]

    kanal.add_listener(lambda _: zaehler.__setitem__(0, zaehler[0] + 1))
    kanal.add_listener(lambda _: zaehler.__setitem__(0, zaehler[0] + 1))
    kanal.update(mute=True)

    assert zaehler[0] == 2


def test_channel_state_listener_abmelden():
    kanal = ChannelState(channel=0)
    aufrufe: list = []

    kanal.add_listener(aufrufe.append)
    kanal.remove_listener(aufrufe.append)
    kanal.update(mute=True)

    assert aufrufe == []


def test_channel_state_remove_nicht_registrierter_listener():
    """Abmelden eines unbekannten Listeners darf nicht werfen."""
    kanal = ChannelState(channel=0)
    kanal.remove_listener(lambda _: None)  # kein Fehler erwartet


# ======================================================================
# MixerState
# ======================================================================

def test_mixer_state_acht_kanaele_standard():
    mixer = MixerState()
    assert mixer.channel_count == 8
    assert len(mixer.channels) == 8


def test_mixer_state_kanalzugriff():
    mixer = MixerState()
    kanal = mixer.channel(3)
    assert kanal.channel == 3


def test_mixer_state_kanalzugriff_ausserhalb_wirft():
    mixer = MixerState()
    with pytest.raises(IndexError):
        mixer.channel(8)
    with pytest.raises(IndexError):
        mixer.channel(-1)


def test_mixer_state_apply_fader_event():
    """FaderEvent wird korrekt in den Kanal-State uebernommen."""
    mixer = MixerState()
    event = FaderEvent(channel=2, position=0.8)
    mixer.apply_event(event)
    assert mixer.channel(2).fader_position == pytest.approx(0.8)


def test_mixer_state_apply_events_mehrere():
    mixer = MixerState()
    events = [
        FaderEvent(channel=0, position=0.0),
        FaderEvent(channel=1, position=0.5),
        FaderEvent(channel=7, position=1.0),
    ]
    mixer.apply_events(events)
    assert mixer.channel(0).fader_position == pytest.approx(0.0)
    assert mixer.channel(1).fader_position == pytest.approx(0.5)
    assert mixer.channel(7).fader_position == pytest.approx(1.0)


def test_mixer_state_fader_event_loest_listener_aus():
    """apply_event soll den Observer des ChannelState ausloesen."""
    mixer = MixerState()
    empfangen: list[ChannelState] = []
    mixer.channel(0).add_listener(empfangen.append)

    mixer.apply_event(FaderEvent(channel=0, position=0.3))

    assert len(empfangen) == 1
    assert empfangen[0].fader_position == pytest.approx(0.3)


def test_mixer_state_unbekanntes_event_wird_ignoriert():
    """Unbekannte Events duerfen nicht werfen."""
    from touchcontrol.mcu.events import McuEvent

    @__import__("dataclasses").dataclass(frozen=True)
    class UnbekanntesEvent(McuEvent):
        pass

    mixer = MixerState()
    mixer.apply_event(UnbekanntesEvent())  # kein Fehler erwartet


def test_mixer_state_bank_offset_start_null():
    mixer = MixerState()
    assert mixer.bank_offset == 0


def test_mixer_state_bank_right():
    mixer = MixerState()
    mixer.bank_right()
    assert mixer.bank_offset == 8


def test_mixer_state_bank_left_nicht_unter_null():
    mixer = MixerState()
    mixer.bank_left()
    assert mixer.bank_offset == 0


def test_mixer_state_bank_listener():
    mixer = MixerState()
    empfangen: list[MixerState] = []
    mixer.add_bank_listener(empfangen.append)

    mixer.bank_right()
    assert len(empfangen) == 1
    assert empfangen[0] is mixer


def test_mixer_state_lcd_untere_zeile_setzt_kanalnamen():
    """LcdEvent mit Offset 56 (untere Zeile) aktualisiert Kanal-0-Name."""
    mixer = MixerState()
    # "Fader1 " = 7 Zeichen fuer Kanal 0, beginnt bei Offset 56.
    event = LcdEvent(device_id=0x14, offset=56, text="Fader1 ")
    mixer.apply_event(event)
    assert mixer.channel(0).name == "Fader1"


def test_mixer_state_lcd_mehrere_kanaele_auf_einmal():
    """LcdEvent der ganzen unteren Zeile aktualisiert alle 8 Kanaele."""
    mixer = MixerState()
    # 8 Kanaele x 7 Zeichen = 56 Zeichen, beginnt bei Offset 56.
    namen = ["Bass   ", "Gitarre", "Keys   ", "Vocals ",
             "Drums  ", "FX1    ", "FX2    ", "Master "]
    text = "".join(namen)
    event = LcdEvent(device_id=0x14, offset=56, text=text)
    mixer.apply_event(event)
    assert mixer.channel(0).name == "Bass"
    assert mixer.channel(1).name == "Gitarre"
    assert mixer.channel(7).name == "Master"


def test_mixer_state_lcd_obere_zeile_ignoriert():
    """LcdEvent der oberen Zeile (Offset 0-55) aendert keine Kanalnamen."""
    mixer = MixerState()
    event = LcdEvent(device_id=0x14, offset=0, text="Pan    " * 8)
    mixer.apply_event(event)
    assert mixer.channel(0).name == ""  # unveraendert


def test_mixer_state_lcd_teil_update_ueber_puffer():
    """Mehrere Teil-Updates an beliebigen Offsets ergeben korrekte Namen.

    Cubase sendet Namen oft nicht kanal-ausgerichtet. Der Puffer muss
    Schreibvorgaenge an beliebigen Positionen korrekt zusammensetzen.
    """
    mixer = MixerState()
    # Erst die ganze untere Zeile mit "Audio01" fuer Kanal 0 fuellen.
    mixer.apply_event(LcdEvent(device_id=0x14, offset=56, text="Audio01"))
    assert mixer.channel(0).name == "Audio01"
    # Jetzt ein Teil-Update mitten in Kanal 0 (Offset 61 = 6. Zeichen).
    mixer.apply_event(LcdEvent(device_id=0x14, offset=61, text="X"))
    assert mixer.channel(0).name == "AudioX1"


def test_mixer_state_lcd_update_ueber_kanalgrenze():
    """Ein LCD-Write, der ueber eine Kanalgrenze laeuft, trifft beide Kanaele."""
    mixer = MixerState()
    # Offset 61 schreibt in Kanal 0 (Zeichen 5-6) und Kanal 1 (Zeichen 0-2).
    mixer.apply_event(LcdEvent(device_id=0x14, offset=61, text="ABCDEF"))
    # Kanal 0: Positionen 61-62 = "AB", Rest Leerzeichen -> "AB" (rechtsbuendig getrimmt)
    assert mixer.channel(0).name == "AB"
    # Kanal 1: Positionen 63-66 = "CDEF"
    assert mixer.channel(1).name == "CDEF"


def test_mixer_state_button_rec_solo_mute():
    """ButtonEvents fuer Rec/Solo/Mute landen am richtigen Kanal."""
    mixer = MixerState()
    mixer.apply_event(ButtonEvent(note=REC_BASE + 0, pressed=True))
    mixer.apply_event(ButtonEvent(note=SOLO_BASE + 3, pressed=True))
    mixer.apply_event(ButtonEvent(note=MUTE_BASE + 7, pressed=True))
    assert mixer.channel(0).rec is True
    assert mixer.channel(3).solo is True
    assert mixer.channel(7).mute is True


def test_mixer_state_button_release_setzt_aus():
    mixer = MixerState()
    mixer.apply_event(ButtonEvent(note=MUTE_BASE + 2, pressed=True))
    assert mixer.channel(2).mute is True
    mixer.apply_event(ButtonEvent(note=MUTE_BASE + 2, pressed=False))
    assert mixer.channel(2).mute is False


def test_mixer_state_select_setzt_selected_channel():
    """Select-Feedback merkt den selektierten Kanal."""
    mixer = MixerState()
    mixer.apply_event(ButtonEvent(note=SELECT_BASE + 5, pressed=True))
    assert mixer.channel(5).select is True
    assert mixer.selected_channel == 5


def test_mixer_state_meter_setzt_pegel():
    mixer = MixerState()
    mixer.apply_event(MeterEvent(channel=3, level=12))
    assert mixer.channel(3).meter_level == 12


def test_mixer_state_vpot_setzt_pan_mitte():
    """V-Pot-Ringwert 6 entspricht Pan-Mitte (0.5)."""
    mixer = MixerState()
    mixer.apply_event(VPotEvent(channel=1, mode=0, value=6, center_led=True))
    assert mixer.channel(1).pan == 0.5


def test_mixer_state_vpot_setzt_pan_extreme():
    mixer = MixerState()
    mixer.apply_event(VPotEvent(channel=0, mode=0, value=1, center_led=False))
    assert mixer.channel(0).pan == 0.0
    mixer.apply_event(VPotEvent(channel=0, mode=0, value=11, center_led=False))
    assert mixer.channel(0).pan == 1.0
