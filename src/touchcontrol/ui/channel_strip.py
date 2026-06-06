"""``ChannelStripWidget`` - ein einzelner Kanalzug in der Kivy-Oberflaeche.

Zeigt alle Informationen eines Kanals:

* **Kanalname** (oben, kommt spaeter per LCD-SysEx von der DAW)
* **Meter** (VU-Balken, Platzhalter bis MeterEvent implementiert ist)
* **Fader** (vertikaler Slider, bidirektional: DAW <-> UI)
* **Taster** REC / SOLO / MUTE / SELECT (Zustand kommt von der DAW)

Das Widget registriert sich als Observer auf dem uebergebenen
:class:`~touchcontrol.model.ChannelState`. Wenn die DAW den Fader bewegt,
aktualisiert sich der Slider automatisch. Umgekehrt sendet der Slider
bei Benutzereingabe sofort eine MCU-Pitch-Bend-Nachricht.

Die Threading-Sicherheit ergibt sich aus der Architektur: Der
:class:`~touchcontrol.midi.MidiBackend` legt eingehende Bytes in eine
Queue, und das Demo-Script leert diese Queue im Kivy-Hauptthread
(``Clock.schedule_interval``). Deshalb werden die Observer-Callbacks
immer aus dem Hauptthread gerufen - Kivy-Zugriffe sind sicher.
"""

from __future__ import annotations

from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget

from touchcontrol.midi import MidiBackend
from touchcontrol.mcu import McuEncoder
from touchcontrol.mcu.constants import (
    MUTE_BASE,
    READ,
    REC_BASE,
    SELECT_BASE,
    SOLO_BASE,
    WRITE,
)
from touchcontrol.model import ChannelState


class MeterWidget(Widget):
    """Einfacher VU-Meter-Balken.

    Zeigt den Pegel 0-15 als gruener Balken von unten nach oben.
    Wird aktualisiert, sobald MeterEvents vom Decoder ankommen.
    Bis dahin bleibt er dunkel (Pegel 0).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._level: int = 0
        with self.canvas:
            # Dunkler Hintergrund.
            Color(0.12, 0.12, 0.12, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            # Gruen-gelb-roter Pegel-Balken (zunächst hoehe 0).
            Color(0.1, 0.75, 0.2, 1)
            self._bar = Rectangle(pos=self.pos, size=(self.width, 0))
        self.bind(pos=self._redraw, size=self._redraw)

    def set_level(self, level: int) -> None:
        """Pegel setzen (0-15, 0=kein Signal, 15=Clipping)."""
        self._level = max(0, min(15, level))
        self._redraw()

    def _redraw(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size
        bar_h = self.height * (self._level / 15) if self._level > 0 else 0
        self._bar.pos = self.pos
        self._bar.size = (self.width, bar_h)


class ChannelStripWidget(BoxLayout):
    """Ein einzelner Kanalzug (160 x 800 Pixel bei 1280x800 und 8 Kanaelen).

    :param channel_state: Der Zustand dieses Kanals (Model).
    :param backend: MIDI-Backend fuer das Senden von Faderbewegungen.
    :param encoder: Encoder, der Faderposition in Bytes umwandelt.
    """

    def __init__(
        self,
        channel_state: ChannelState,
        backend: MidiBackend,
        encoder: McuEncoder,
        **kwargs,
    ) -> None:
        super().__init__(orientation="vertical", spacing=0, padding=2, **kwargs)

        self._state = channel_state
        self._backend = backend
        self._encoder = encoder

        # Guard: verhindert Rueckkopplung DAW -> Slider -> Senden -> DAW -> ...
        self._updating_from_daw = False

        self._build_ui()

        # Observer registrieren (wird immer im Kivy-Hauptthread aufgerufen).
        channel_state.add_listener(self._on_state_changed)

    # ------------------------------------------------------------------
    # UI aufbauen
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        ch = self._state.channel

        # Hintergrund leicht alternierend fuer bessere Trennung der Kanaele.
        bg = 0.18 if ch % 2 == 0 else 0.22
        with self.canvas.before:
            Color(bg, bg, bg, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # --- Kanalname (oben) ---
        self._name_label = Label(
            text=f"CH {ch + 1}",
            size_hint=(1, None),
            height=40,
            font_size=13,
            bold=True,
            color=(0.9, 0.9, 0.9, 1),
        )
        self.add_widget(self._name_label)

        # --- Pan (V-Pot) als horizontaler Slider ---
        self._pan = Slider(
            min=0.0, max=1.0, value=0.5,
            orientation="horizontal",
            size_hint=(1, None), height=30,
        )
        # Letzter bekannter Pan-Wert (fuer relative V-Pot-Schritte).
        self._pan_value = 0.5
        self._pan.bind(value=self._on_pan_value)
        self.add_widget(self._pan)

        # --- VU-Meter ---
        self._meter = MeterWidget(size_hint=(1, None), height=70)
        self.add_widget(self._meter)

        # --- Vertikaler Fader ---
        self._slider = Slider(
            min=0.0,
            max=1.0,
            value=0.0,
            orientation="vertical",
            size_hint=(1, 1),
        )
        self._slider.bind(value=self._on_slider_value)
        self.add_widget(self._slider)

        # --- Taster REC / SOLO / MUTE / SELECT / READ / WRITE (2x3) ---
        btn_grid = GridLayout(
            cols=2,
            size_hint=(1, None),
            height=126,
            spacing=2,
            padding=[2, 2],
        )
        self._btn_rec = ToggleButton(
            text="REC", font_size=11,
            background_color=(0.65, 0.15, 0.15, 1),
        )
        self._btn_solo = ToggleButton(
            text="SOLO", font_size=11,
            background_color=(0.65, 0.55, 0.05, 1),
        )
        self._btn_mute = ToggleButton(
            text="MUTE", font_size=11,
            background_color=(0.45, 0.45, 0.05, 1),
        )
        self._btn_select = ToggleButton(
            text="SEL", font_size=11,
            background_color=(0.1, 0.35, 0.65, 1),
        )
        self._btn_read = ToggleButton(
            text="READ", font_size=11,
            background_color=(0.15, 0.55, 0.25, 1),
        )
        self._btn_write = ToggleButton(
            text="WRITE", font_size=11,
            background_color=(0.6, 0.2, 0.2, 1),
        )
        # Taster sind feedback-gesteuert: Druck sendet nur, der LED-Zustand
        # kommt von der DAW zurueck (siehe _on_button_press).
        self._btn_rec.bind(on_press=lambda *_a: self._on_button_press(REC_BASE))
        self._btn_solo.bind(on_press=lambda *_a: self._on_button_press(SOLO_BASE))
        self._btn_mute.bind(on_press=lambda *_a: self._on_button_press(MUTE_BASE))
        self._btn_select.bind(on_press=lambda *_a: self._on_button_press(SELECT_BASE))
        self._btn_read.bind(on_press=lambda *_a: self._on_automation_press(READ))
        self._btn_write.bind(on_press=lambda *_a: self._on_automation_press(WRITE))
        btn_grid.add_widget(self._btn_rec)
        btn_grid.add_widget(self._btn_solo)
        btn_grid.add_widget(self._btn_mute)
        btn_grid.add_widget(self._btn_select)
        btn_grid.add_widget(self._btn_read)
        btn_grid.add_widget(self._btn_write)
        self.add_widget(btn_grid)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _on_slider_value(self, _instance, value: float) -> None:
        """Benutzer hat den Fader gezogen -> MCU-MIDI senden."""
        if not self._updating_from_daw:
            msg = self._encoder.fader_position(self._state.channel, value)
            self._backend.send(msg)

    def _on_pan_value(self, _instance, value: float) -> None:
        """Benutzer hat den Pan-Regler bewegt -> relative V-Pot-Schritte senden.

        MCU-V-Pots sind relativ: Wir senden die Differenz seit der letzten
        Position als Anzahl Schritte (im/gegen den Uhrzeigersinn).
        """
        if self._updating_from_daw:
            return
        ticks = round((value - self._pan_value) * 16)
        self._pan_value = value
        if ticks != 0:
            self._backend.send(self._encoder.vpot_rotate(self._state.channel, ticks))

    def _send_bang(self, note: int) -> None:
        """Note-Bang (Press + Release) ueber das Backend senden."""
        for msg in self._encoder.button_bang(note):
            self._backend.send(msg)

    def _restore_button_states(self) -> None:
        """Taster-Optik wieder am Modell ausrichten (Feedback steuert die LED)."""
        self._sync_buttons_from_state()

    def _on_button_press(self, base_note: int) -> None:
        """Pro-Kanal-Taster gedrueckt -> Note-Bang fuer diesen Kanal senden."""
        if self._updating_from_daw:
            return
        self._send_bang(base_note + self._state.channel)
        # Lokales Toggle rueckgaengig machen - die DAW liefert den echten Zustand.
        self._restore_button_states()

    def _on_automation_press(self, note: int) -> None:
        """Read/Write gedrueckt -> erst diesen Kanal selektieren, dann togglen.

        Read/Write sind im MCU globale Tasten und wirken auf den selektierten
        Kanal. Damit der Strip-Button "seinen" Kanal betrifft, selektieren wir
        ihn zuerst.
        """
        if self._updating_from_daw:
            return
        self._send_bang(SELECT_BASE + self._state.channel)
        self._send_bang(note)
        self._restore_button_states()

    def _sync_buttons_from_state(self) -> None:
        """Alle Taster-LEDs aus dem aktuellen ChannelState setzen."""
        s = self._state
        self._btn_rec.state = "down" if s.rec else "normal"
        self._btn_solo.state = "down" if s.solo else "normal"
        self._btn_mute.state = "down" if s.mute else "normal"
        self._btn_select.state = "down" if s.select else "normal"
        self._btn_read.state = "down" if s.read else "normal"
        self._btn_write.state = "down" if s.write else "normal"

    def _on_state_changed(self, state: ChannelState) -> None:
        """Observer-Callback: ChannelState hat sich geaendert -> UI aktualisieren.

        Wird immer aus dem Kivy-Hauptthread aufgerufen (via Clock), deshalb
        sind alle Kivy-Operationen hier sicher.
        """
        self._updating_from_daw = True
        try:
            self._slider.value = state.fader_position
            self._pan.value = state.pan
            self._pan_value = state.pan
            self._name_label.text = state.name if state.name else f"CH {state.channel + 1}"
            self._meter.set_level(state.meter_level)
            self._sync_buttons_from_state()
        finally:
            self._updating_from_daw = False
