"""``ChannelStripWidget`` - ein einzelner Kanalzug im modernen Design.

Verbindet die optisch aufwendigen Controls aus :mod:`touchcontrol.ui.controls`
(:class:`ModernFader`, :class:`ModernPanner`, :class:`ChannelToggleButton`) mit
der bestehenden bidirektionalen MIDI-Anbindung:

* **Kanalname** (oben, kommt per LCD-SysEx von der DAW)
* **Panner** (V-Pot, relative MCU-Schritte)
* **Fader** mit integriertem Pegelmeter (Pitch-Bend, dB-Skala)
* **Taster** M / S / R / SEL (feedback-gesteuert)

Das Widget registriert sich als Observer auf dem uebergebenen
:class:`~touchcontrol.model.ChannelState`. Bewegt die DAW den Fader, folgt der
Regler automatisch; umgekehrt sendet eine Benutzergeste sofort die passende
MCU-Nachricht. Ein Touch-Latch verhindert, dass das leicht verzoegerte
DAW-Echo den gerade beruehrten Regler zurueckspringen laesst.
"""

from __future__ import annotations

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label

from touchcontrol.midi import MidiBackend
from touchcontrol.mcu import McuEncoder
from touchcontrol.mcu.constants import (
    MUTE_BASE,
    REC_BASE,
    SELECT_BASE,
    SOLO_BASE,
)
from touchcontrol.model import ChannelState

from .controls import ChannelToggleButton, ModernFader, ModernPanner

# Wie viele relative V-Pot-Schritte entsprechen einem vollen Pan-Weg (0.0->1.0)?
# MCU-V-Pots sind relative Encoder; Cubase rechnet Schritte in Pan-Bewegung um.
# Etwas ueber dem theoretischen Minimum, damit der volle Reglerweg die
# Endanschlaege (L100/R100) sicher erreicht - Cubase begrenzt selbst.
PAN_SWEEP_TICKS = 132

# Maximaler Pegel eines MCU-MeterEvents (0-15) -> normiert auf 0.0-1.0.
_METER_MAX = 15.0


class ChannelStripWidget(BoxLayout):
    """Ein einzelner Kanalzug im modernen Design.

    :param channel_state: Der Zustand dieses Kanals (Model).
    :param backend: MIDI-Backend fuer das Senden von Faderbewegungen.
    :param encoder: Encoder, der Reglerwerte in Bytes umwandelt.
    """

    def __init__(
        self,
        channel_state: ChannelState,
        backend: MidiBackend,
        encoder: McuEncoder,
        **kwargs,
    ) -> None:
        super().__init__(orientation="vertical", spacing=10, padding=4, **kwargs)

        self._state = channel_state
        self._backend = backend
        self._encoder = encoder

        # Guard: verhindert Rueckkopplung DAW -> Regler -> Senden -> DAW -> ...
        self._updating_from_daw = False

        # Letzter bekannter Pan-Wert (0.0-1.0) fuer relative V-Pot-Schritte.
        self._pan_value = 0.5
        # Bruchteil-Akkumulator: sammelt nicht ganzzahlige Schrittanteile, damit
        # auch langsame Bewegungen nicht durch Rundung auf 0 verloren gehen.
        self._pan_tick_accum = 0.0

        self._build_ui()

        # Observer registrieren (wird immer im Kivy-Hauptthread aufgerufen).
        channel_state.add_listener(self._on_state_changed)

    # ------------------------------------------------------------------
    # UI aufbauen
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        ch = self._state.channel

        # Hintergrund des Kanalschachts (Theme-Widget-Hintergrund).
        with self.canvas.before:
            self._bg_color = Color(0.08, 0.08, 0.11, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Auf Theme-Wechsel reagieren (App liefert widget_bg_color).
        app = App.get_running_app()
        if app is not None and hasattr(app, "widget_bg_color"):
            app.bind(widget_bg_color=self._apply_bg_color)
            self._apply_bg_color(app, app.widget_bg_color)

        # --- Kanalname (oben, theme-reaktiv) ---
        accent = list(app.accent_color) if app is not None and hasattr(app, "accent_color") else [0.0, 0.67, 1.0, 1.0]
        self._name_label = Label(
            text=f"CH {ch + 1}",
            size_hint=(1, None),
            height=88,
            font_size=36,
            bold=True,
            color=accent,
        )
        if app is not None and hasattr(app, "accent_color"):
            app.bind(accent_color=lambda _i, c: setattr(self._name_label, "color", c))
        self.add_widget(self._name_label)

        # --- Panner (V-Pot) ---
        self._panner = ModernPanner(size_hint=(1, None), height=160)
        self._panner.bind(pan_value=self._on_pan_value)
        self.add_widget(self._panner)

        # --- Fader mit integriertem Pegelmeter ---
        self._fader = ModernFader(size_hint=(1, 1))
        self._fader.bind(value=self._on_fader_value)
        self.add_widget(self._fader)

        # --- Taster M / S / R / SEL (2x2) ---
        # Die Grid-Hoehe wird reaktiv aus der tatsaechlichen Breite berechnet,
        # damit die Zellen unabhaengig von der Kanalbreite immer quadratisch
        # bleiben (siehe _square_button_grid).
        btn_grid = GridLayout(
            cols=2,
            rows=2,
            size_hint=(1, None),
            spacing=6,
            padding=[10, 0, 10, 8],
        )
        btn_grid.bind(width=self._square_button_grid)
        self._btn_mute = ChannelToggleButton(text="M", font_size=22)
        self._btn_solo = ChannelToggleButton(text="S", font_size=22)
        self._btn_rec = ChannelToggleButton(text="R", font_size=22)
        self._btn_select = ChannelToggleButton(text="SEL", font_size=18)
        # Taster sind feedback-gesteuert: Druck sendet nur, der LED-Zustand
        # kommt von der DAW zurueck (siehe _on_button_press).
        self._btn_mute.bind(on_press=lambda *_a: self._on_button_press(MUTE_BASE))
        self._btn_solo.bind(on_press=lambda *_a: self._on_button_press(SOLO_BASE))
        self._btn_rec.bind(on_press=lambda *_a: self._on_button_press(REC_BASE))
        self._btn_select.bind(on_press=lambda *_a: self._on_button_press(SELECT_BASE))
        btn_grid.add_widget(self._btn_mute)
        btn_grid.add_widget(self._btn_solo)
        btn_grid.add_widget(self._btn_rec)
        btn_grid.add_widget(self._btn_select)
        self.add_widget(btn_grid)

    def _square_button_grid(self, grid, width: float) -> None:
        """Grid-Hoehe so setzen, dass jede Zelle das Verhaeltnis 2:3 (H:B) hat.

        Zellbreite = (Breite - horizontales Padding - Spalten-Spacing) / 2,
        Zellhoehe  = Zellbreite * 2/3 (flachere Taster). Die Gesamthoehe ergibt
        sich aus zwei Zeilen plus Zeilen-Spacing und oberem/unterem Padding.
        """
        pad_l, pad_t, pad_r, pad_b = grid.padding
        spacing_x, spacing_y = grid.spacing
        cell_w = max(0.0, (width - pad_l - pad_r - spacing_x) / 2.0)
        cell_h = cell_w * 2.0 / 3.0
        grid.height = cell_h * 2 + spacing_y + pad_t + pad_b

    # ------------------------------------------------------------------
    # Hintergrund / Theme

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _apply_bg_color(self, _app, rgba) -> None:
        self._bg_color.rgba = rgba

    # ------------------------------------------------------------------
    # Fader-Callbacks
    # ------------------------------------------------------------------

    def _on_fader_value(self, _instance, value: float) -> None:
        """Benutzer hat den Fader gezogen -> MCU-Pitch-Bend senden."""
        if not self._updating_from_daw:
            # Modell mit der UI synchron halten (sonst setzt ein spaeteres
            # State-Update wegen eines anderen Feldes den Fader zurueck).
            self._state.fader_position = value
            msg = self._encoder.fader_position(self._state.channel, value)
            self._backend.send(msg)

    # ------------------------------------------------------------------
    # Pan-Callbacks (relative V-Pot-Schritte)
    # ------------------------------------------------------------------

    def _on_pan_value(self, _instance, pan_value: float) -> None:
        """Benutzer hat den Panner bewegt -> relative V-Pot-Schritte senden.

        Der Panner liefert ``-1.0 .. +1.0``; das Modell speichert ``0.0 .. 1.0``.
        """
        if self._updating_from_daw:
            return
        value01 = (pan_value + 1.0) / 2.0
        # Bewegung seit dem letzten Event in (Bruchteil-)Schritte umrechnen und
        # akkumulieren, damit auch viele kleine Bewegungen korrekt aufsummieren.
        self._pan_tick_accum += (value01 - self._pan_value) * PAN_SWEEP_TICKS
        self._pan_value = value01
        # Modell synchron halten.
        self._state.pan = value01
        ticks = int(self._pan_tick_accum)  # schneidet Richtung 0 ab
        if ticks != 0:
            self._pan_tick_accum -= ticks
            self._send_vpot_ticks(ticks)

    def _send_vpot_ticks(self, ticks: int) -> None:
        """V-Pot-Schritte senden, bei Bedarf in 6-bit-Haeppchen aufgeteilt.

        Eine einzelne V-Pot-Nachricht kann nur bis zu 0x3F (63) Schritte
        tragen. Groessere Bewegungen werden auf mehrere Nachrichten verteilt.
        """
        channel = self._state.channel
        schritt = 0x3F if ticks > 0 else -0x3F
        rest = ticks
        while abs(rest) > 0x3F:
            self._backend.send(self._encoder.vpot_rotate(channel, schritt))
            rest -= schritt
        if rest != 0:
            self._backend.send(self._encoder.vpot_rotate(channel, rest))

    # ------------------------------------------------------------------
    # Taster
    # ------------------------------------------------------------------

    def _send_bang(self, note: int) -> None:
        """Note-Bang (Press + Release) ueber das Backend senden."""
        for msg in self._encoder.button_bang(note):
            self._backend.send(msg)

    def _on_button_press(self, base_note: int) -> None:
        """Pro-Kanal-Taster gedrueckt -> Note-Bang fuer diesen Kanal senden."""
        if self._updating_from_daw:
            return
        self._send_bang(base_note + self._state.channel)
        # Lokales Toggle rueckgaengig machen - die DAW liefert den echten Zustand.
        self._sync_buttons_from_state()

    def _sync_buttons_from_state(self) -> None:
        """Alle Taster-LEDs aus dem aktuellen ChannelState setzen."""
        s = self._state
        self._btn_rec.active = s.rec
        self._btn_solo.active = s.solo
        self._btn_mute.active = s.mute
        self._btn_select.active = s.select

    # ------------------------------------------------------------------
    # Observer-Callback
    # ------------------------------------------------------------------

    def _on_state_changed(self, state: ChannelState) -> None:
        """ChannelState hat sich geaendert -> UI aktualisieren.

        Wird immer aus dem Kivy-Hauptthread aufgerufen (via Clock), deshalb
        sind alle Kivy-Operationen hier sicher.
        """
        self._updating_from_daw = True
        try:
            # Fader/Pan nur nachfuehren, wenn der Benutzer sie gerade NICHT
            # haelt (Touch-Latch verhindert Zittern/Springen durch DAW-Echo).
            if not self._fader.touch_active:
                self._fader.value = state.fader_position
            if not self._panner.touch_active:
                self._panner.pan_value = state.pan * 2.0 - 1.0
                self._pan_value = state.pan
            self._name_label.text = (
                state.name if state.name else f"CH {state.channel + 1}"
            )
            self._fader.meter_frac = max(
                0.0, min(1.0, state.meter_level / _METER_MAX)
            )
            self._sync_buttons_from_state()
        finally:
            self._updating_from_daw = False
