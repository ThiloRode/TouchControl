"""``build_root`` - baut die komplette Oberflaeche aus Screens + Wisch-Streifen.

Aufbau (horizontal):

    +-------------------------------+------+
    |                               |  o   |
    |         ScreenManager         |  *   |  <- SwipeStrip (rechts, frei)
    |   (Mixer / Settings / ...)    |  o   |
    |                               |      |
    +-------------------------------+------+

Der :class:`~kivy.uix.screenmanager.ScreenManager` fuellt die Hauptflaeche, der
schmale :class:`~touchcontrol.ui.swipe_strip.SwipeStrip` bleibt rechts als freie
Wischflaeche stehen. Die KV-Styling-Datei wird einmalig geladen.
"""

from __future__ import annotations

from pathlib import Path

from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition

from touchcontrol.midi import MidiBackend
from touchcontrol.mcu import McuEncoder
from touchcontrol.model import MixerState

from .mixer_view import MixerView
from .settings_view import SettingsView
from .swipe_strip import SwipeStrip

# Breite des freien Wisch-Streifens am rechten Rand (Pixel).
STRIP_WIDTH = 34

# KV-Styling nur einmal pro Prozess laden.
_KV_LOADED = False


def _ensure_kv_loaded() -> None:
    global _KV_LOADED
    if not _KV_LOADED:
        Builder.load_file(str(Path(__file__).with_name("touchcontrol.kv")))
        _KV_LOADED = True


def build_root(
    mixer_state: MixerState,
    backend: MidiBackend,
    encoder: McuEncoder,
) -> BoxLayout:
    """Erzeugt das Wurzel-Widget mit Mixer-/Settings-Screen und Wisch-Streifen.

    :param mixer_state: Gesamt-Mixer-Zustand (alle ChannelStates).
    :param backend: MIDI-Backend.
    :param encoder: MCU-Encoder.
    :returns: Ein horizontales :class:`~kivy.uix.boxlayout.BoxLayout`.
    """
    _ensure_kv_loaded()

    manager = ScreenManager(transition=SlideTransition(duration=0.22))

    mixer_screen = Screen(name="mixer")
    mixer_screen.add_widget(
        MixerView(mixer_state=mixer_state, backend=backend, encoder=encoder)
    )
    manager.add_widget(mixer_screen)

    settings_screen = Screen(name="settings")
    settings_screen.add_widget(SettingsView())
    manager.add_widget(settings_screen)

    screen_order = ["mixer", "settings"]

    root = BoxLayout(orientation="horizontal")
    root.add_widget(manager)
    root.add_widget(
        SwipeStrip(
            manager=manager,
            screen_order=screen_order,
            size_hint=(None, 1),
            width=STRIP_WIDTH,
        )
    )
    return root
