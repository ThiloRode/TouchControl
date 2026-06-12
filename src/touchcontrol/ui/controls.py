"""Moderne Touch-Controls fuer den Kanalzug (Design aus der Channelstrip Study).

Enthaelt drei wiederverwendbare Widgets, die in :mod:`touchcontrol.ui` und der
KV-Datei ``touchcontrol.kv`` verwendet werden:

* :class:`ModernFader` - vertikaler Fader mit nicht-linearer dB-Skala,
  offener U-Klammer-Kappe und integriertem dreistufigem Pegelmeter.
* :class:`ModernPanner` - runder Panorama-Regler mit Akzent-Bogen.
* :class:`ChannelToggleButton` - im Theme eingefaerbter Umschalt-Taster.

Anders als in der Study erzeugen diese Widgets **kein** simuliertes Audio.
Der Pegel (:attr:`ModernFader.meter_frac`) und die Reglerwerte werden von der
echten MIDI-Anbindung (``ChannelStripWidget``) gesetzt bzw. ausgelesen. Die
Widgets melden Benutzergesten ueber das jeweilige Wert-Property; der Kanalzug
bindet sich daran und sendet MCU-Nachrichten.
"""

from __future__ import annotations

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.button import Button
from kivy.uix.widget import Widget

from .theme import DEFAULT_DAW, load_daw_scales

# Fallback-Farben, falls die laufende App (noch) keine Theme-Properties hat.
_FALLBACK_WIDGET_BG = [0.08, 0.08, 0.11, 1.0]
_FALLBACK_METER = [
    [0.0, 0.67, 1.0, 0.85],
    [0.2, 0.4, 0.9, 0.85],
    [0.48, 0.17, 0.75, 0.85],
]

# Pegel-Schwellen (Anteil des Reglerwegs) fuer den Farbwechsel des Meters.
_METER_LOW_END = 0.60   # bis hier "leise" (meter_low)
_METER_MID_END = 0.85   # bis hier "nominal" (meter_mid), darueber "peak"


def _app_color(prop: str, fallback: list) -> list:
    """Theme-Farbe der laufenden App lesen, sonst Fallback."""
    app = App.get_running_app()
    if app is not None and hasattr(app, prop):
        return getattr(app, prop)
    return fallback


class ModernFader(Widget):
    """Vertikaler Fader mit dB-Skala, U-Klammer-Kappe und Pegelmeter.

    Der Wert :attr:`value` (0.0 unten .. 1.0 oben) entspricht direkt der
    linearen Faderposition, die per MCU-Pitch-Bend uebertragen wird. Die
    dB-Beschriftung dient nur der Anzeige (DAW legt die echte Kennlinie fest).
    """

    value = NumericProperty(0.0)          # Faderposition 0.0 - 1.0
    cap_y = NumericProperty(0)            # berechnete Y-Position der Kappe
    cap_w = NumericProperty(46)           # halbe Kappenbreite (groessenabhaengig)
    cap_h = NumericProperty(30)           # halbe Kappenhoehe
    scale_config = ListProperty([])       # geladene Skalen-Stuetzpunkte
    db_text = StringProperty("-\u221e")   # dB-Anzeige der Kappe
    meter_frac = NumericProperty(0.0)     # aktueller Pegel 0.0 - 1.0
    touch_active = BooleanProperty(False)  # True solange der Benutzer zieht

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scales = load_daw_scales()
        self.db_points: list[tuple[float, float]] = []

        # DAW-Profil von der App uebernehmen und auf Wechsel reagieren.
        app = App.get_running_app()
        self._daw = getattr(app, "fader_daw", DEFAULT_DAW) if app else DEFAULT_DAW
        if app is not None:
            for prop in (
                "widget_bg_color",
                "accent_color",
                "meter_low_color",
                "meter_mid_color",
                "meter_high_color",
            ):
                if hasattr(app, prop):
                    app.bind(**{prop: self.redraw})
            if hasattr(app, "fader_daw"):
                app.bind(fader_daw=self._on_daw_changed)

        self.load_daw_config()
        self.bind(
            pos=self.redraw,
            size=self._on_size,
            value=self.update_geometry,
            meter_frac=self.redraw,
        )
        self._on_size()

    # ------------------------------------------------------------------
    # DAW-Skala
    # ------------------------------------------------------------------

    def _on_daw_changed(self, _app, daw_name: str) -> None:
        self._daw = daw_name
        self.load_daw_config()
        self.redraw()

    def load_daw_config(self) -> None:
        """Tick-Stuetzpunkte des aktuellen DAW-Profils laden und db_points bauen."""
        self.scale_config = self._scales.get(
            self._daw, next(iter(self._scales.values()), [])
        )

        # 0-dB-Stuetzpunkt finden (alles darunter wird negativ).
        zero_pos = 0.74
        for tick in self.scale_config:
            if tick["label"] == "0":
                zero_pos = tick["pos"]
                break

        points: list[tuple[float, float]] = []
        for tick in self.scale_config:
            pos = tick["pos"]
            lbl = tick["label"]
            if lbl == "00":
                db_val = -96.0  # Mute-Schwelle (-unendlich)
            else:
                val = float(lbl)
                db_val = -val if pos < zero_pos else val
            points.append((pos, db_val))
        points.sort(key=lambda p: p[0], reverse=True)
        self.db_points = points

    # ------------------------------------------------------------------
    # Geometrie / Zeichnen
    # ------------------------------------------------------------------

    def _on_size(self, *_args) -> None:
        # Kappenbreite an die Kanalbreite koppeln (schmaler Kanal -> schmale Kappe).
        self.cap_w = max(28.0, self.width * 0.30)
        self.redraw()

    def redraw(self, *_args) -> None:
        self.draw_scale()
        self.update_geometry()

    def get_pos_from_db(self, db_val: float) -> float:
        """Inverse Interpolation: dB-Wert -> relative Y-Position (0.0 - 1.0)."""
        if not self.db_points:
            return 0.0
        if db_val >= self.db_points[0][1]:
            return 1.0
        if db_val <= self.db_points[-1][1]:
            return 0.0
        for i in range(len(self.db_points) - 1):
            p1, db1 = self.db_points[i]
            p2, db2 = self.db_points[i + 1]
            if db2 <= db_val <= db1:
                ratio = (db_val - db2) / (db1 - db2)
                return p2 + ratio * (p1 - p2)
        return 0.0

    def get_db_value(self, pos: float) -> float:
        """Relative Position (0.0 - 1.0) -> dB-Wert (abschnittsweise linear)."""
        if not self.db_points:
            return 0.0
        if pos >= 1.0:
            return self.db_points[0][1]
        if pos <= 0.0:
            return float("-inf")
        for i in range(len(self.db_points) - 1):
            p1, db1 = self.db_points[i]
            p2, db2 = self.db_points[i + 1]
            if p2 <= pos <= p1:
                ratio = (pos - p2) / (p1 - p2)
                return db2 + ratio * (db1 - db2)
        return float("-inf")

    def draw_scale(self, *_args) -> None:
        """Hintergrund, Pegelmeter und Skalenstriche in ``canvas.before`` zeichnen."""
        self.canvas.before.clear()
        with self.canvas.before:
            # 1. Widget-Hintergrund.
            Color(*_app_color("widget_bg_color", _FALLBACK_WIDGET_BG))
            Rectangle(pos=self.pos, size=self.size)

            track_bottom = self.y + 50
            track_height = self.height - 100
            if track_height <= 0:
                return

            # 2. Dreistufiges Pegelmeter (Farben aus dem aktiven Theme).
            if self.meter_frac > 0.0:
                y_meter = track_bottom + track_height * self.meter_frac
                y_low_end = track_bottom + track_height * _METER_LOW_END
                y_mid_end = track_bottom + track_height * _METER_MID_END
                meter_w = 12
                meter_x = self.center_x - meter_w / 2

                low = _app_color("meter_low_color", _FALLBACK_METER[0])
                mid = _app_color("meter_mid_color", _FALLBACK_METER[1])
                high = _app_color("meter_high_color", _FALLBACK_METER[2])

                h_low = min(y_meter, y_low_end) - track_bottom
                if h_low > 0:
                    Color(*low)
                    Rectangle(pos=(meter_x, track_bottom), size=(meter_w, h_low))
                if y_meter > y_low_end:
                    h_mid = min(y_meter, y_mid_end) - y_low_end
                    if h_mid > 0:
                        Color(*mid)
                        Rectangle(pos=(meter_x, y_low_end), size=(meter_w, h_mid))
                if y_meter > y_mid_end:
                    h_high = y_meter - y_mid_end
                    if h_high > 0:
                        Color(*high)
                        Rectangle(pos=(meter_x, y_mid_end), size=(meter_w, h_high))

            # 3. Skalenstriche ueber dem Pegelbalken (Lesbarkeit).
            Color(1, 1, 1, 0.8)
            for tick in self.scale_config:
                y_pos = track_bottom + track_height * tick["pos"]
                w = tick["width"]
                Rectangle(pos=(self.center_x - w / 2, y_pos), size=(w, 3))

    def update_geometry(self, *_args) -> None:
        """Kappenposition und dB-Text aus dem aktuellen Wert berechnen."""
        track_bottom = self.y + 50
        track_height = self.height - 100
        self.cap_y = track_bottom + track_height * self.value

        db_val = self.get_db_value(self.value)
        if db_val < -80:
            self.db_text = "-\u221e"
        elif db_val > 0.01:
            self.db_text = f"+{db_val:.1f}"
        else:
            self.db_text = f"{db_val:.1f}"

    # ------------------------------------------------------------------
    # Touch-Gesten (relatives Ziehen, Doppelklick -> 0 dB)
    # ------------------------------------------------------------------

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                # Doppelklick -> auf 0.0 dB (Unity Gain) schnappen.
                for pos, db_val in self.db_points:
                    if abs(db_val) < 0.01:
                        self.value = pos
                        break
                return True
            touch.grab(self)
            touch.ud["start_y"] = touch.y
            touch.ud["start_value"] = self.value
            self.touch_active = True
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            track_height = self.height - 100
            if track_height <= 0:
                return True
            delta_value = (touch.y - touch.ud["start_y"]) / track_height
            self.value = max(0.0, min(1.0, touch.ud["start_value"] + delta_value))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.touch_active = False
            return True
        return super().on_touch_up(touch)


class ModernPanner(Widget):
    """Runder Panorama-Regler mit Akzent-Bogen.

    :attr:`pan_value` reicht von ``-1.0`` (ganz links) ueber ``0.0`` (Mitte)
    bis ``+1.0`` (ganz rechts). Der Kanalzug rechnet diesen Bereich in die
    relativen MCU-V-Pot-Schritte um.
    """

    pan_value = NumericProperty(0.0)          # -1.0 .. +1.0
    pan_text = StringProperty("C")
    radius = NumericProperty(48)              # Bogenradius (groessenabhaengig)
    active_angle_start = NumericProperty(134)
    active_angle_end = NumericProperty(136)
    touch_active = BooleanProperty(False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.bind(pos=self._on_size, size=self._on_size, pan_value=self.update_pan)
        self.update_pan()

    def _on_size(self, *_args) -> None:
        # Bogen an die kleinste Kante koppeln, damit er immer ins Widget passt.
        self.radius = max(24.0, min(self.width, self.height) * 0.42)
        self.update_pan()

    def update_pan(self, *_args) -> None:
        """Bogen-Winkel und Beschriftung aus dem Pan-Wert ableiten."""
        val = self.pan_value
        pct = int(round(abs(val) * 100))
        if pct == 0:
            self.pan_text = "C"
        elif val < 0:
            self.pan_text = "L" if pct >= 100 else f"{pct}"
        else:
            self.pan_text = "R" if pct >= 100 else f"{pct}"

        # Winkel relativ zur unten liegenden Luecke (KV rotiert um 135 Grad).
        if pct == 0:
            self.active_angle_start = 134
            self.active_angle_end = 136
        elif val < 0:
            self.active_angle_start = 135 + val * 135
            self.active_angle_end = 135
        else:
            self.active_angle_start = 135
            self.active_angle_end = 135 + val * 135

    # ------------------------------------------------------------------
    # Touch-Gesten
    # ------------------------------------------------------------------

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                self.pan_value = 0.0  # zurueck in die Mitte (Center)
                return True
            touch.grab(self)
            touch.ud["start_y"] = touch.y
            touch.ud["start_pan"] = self.pan_value
            self.touch_active = True
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            # 150 px vertikaler Weg entsprechen dem vollen Regelbereich.
            delta_pan = ((touch.y - touch.ud["start_y"]) / 150.0) * 2.0
            self.pan_value = max(-1.0, min(1.0, touch.ud["start_pan"] + delta_pan))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.touch_active = False
            return True
        return super().on_touch_up(touch)


class ChannelToggleButton(Button):
    """LED-Taster fuer M/S/R/SEL.

    Der Zustand (an/aus) wird ausschliesslich ueber :attr:`active` gesteuert,
    das vom ChannelStripWidget gemaess DAW-Feedback gesetzt wird. Das Widget
    leitet Beruehrungen als ``on_press``-Event weiter (identisch zu Button),
    laesst aber kein lokales Toggle zu - die DAW liefert den echten LED-Zustand.
    """

    active = BooleanProperty(False)
