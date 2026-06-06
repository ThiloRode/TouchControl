"""``MixerView`` - die vollstaendige Mixer-Oberflaeche mit 8 Kanalzuegen.

Legt alle :class:`~touchcontrol.ui.channel_strip.ChannelStripWidget`
nebeneinander in einer horizontalen Box. Jeder Kanalzug bekommt gleich
viel Platz (``size_hint_x=1``), sodass sie sich gleichmaessig auf die
Bildschirmbreite verteilen.

Bei 1280 x 800 Pixeln und 8 Kanaelen ergibt das 160 px pro Kanalzug.
"""

from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout

from touchcontrol.midi import MidiBackend
from touchcontrol.mcu import McuEncoder
from touchcontrol.model import MixerState

from .channel_strip import ChannelStripWidget


class MixerView(BoxLayout):
    """Horizontale Zeile aller Kanalzuege.

    :param mixer_state: Der Gesamt-Mixer-Zustand (haelt alle ChannelStates).
    :param backend: MIDI-Backend fuer das Senden von Faderbewegungen.
    :param encoder: Encoder fuer die MIDI-Kodierung.
    """

    def __init__(
        self,
        mixer_state: MixerState,
        backend: MidiBackend,
        encoder: McuEncoder,
        **kwargs,
    ) -> None:
        super().__init__(orientation="horizontal", spacing=1, **kwargs)

        for ch_state in mixer_state.channels:
            self.add_widget(
                ChannelStripWidget(
                    channel_state=ch_state,
                    backend=backend,
                    encoder=encoder,
                )
            )
