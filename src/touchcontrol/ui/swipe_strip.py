"""``SwipeStrip`` - schmaler Navigationsstreifen am rechten Bildschirmrand.

Der Streifen bleibt rechts als freie Flaeche stehen. Eine vertikale
Wischgeste darueber blaettert durch die Screens des angebundenen
:class:`~kivy.uix.screenmanager.ScreenManager`:

* Wischen **nach oben** -> naechster Screen
* Wischen **nach unten** -> vorheriger Screen

Kleine Indikatorpunkte zeigen die Anzahl der Screens und den aktuell aktiven
an. Die Punkte werden in der Theme-Akzentfarbe gezeichnet.
"""

from __future__ import annotations

from typing import List

from kivy.app import App
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.uix.widget import Widget

# Ab welcher vertikalen Wischdistanz (Pixel) ein Screen-Wechsel ausgeloest wird.
_SWIPE_THRESHOLD = 40.0


class SwipeStrip(Widget):
    """Vertikaler Wisch-Streifen zur Screen-Navigation.

    :param manager: Der zu steuernde ScreenManager.
    :param screen_order: Reihenfolge der Screen-Namen fuer das Blaettern.
    """

    def __init__(self, manager, screen_order: List[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._manager = manager
        self._order = list(screen_order)

        with self.canvas.before:
            self._bg_color = Color(0.10, 0.10, 0.13, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self._redraw, size=self._redraw)

        # Auf Theme- und Screen-Wechsel reagieren.
        app = App.get_running_app()
        if app is not None and hasattr(app, "widget_bg_color"):
            app.bind(widget_bg_color=self._on_bg_color)
            self._on_bg_color(app, app.widget_bg_color)
        if app is not None and hasattr(app, "accent_color"):
            app.bind(accent_color=self._redraw)
        if manager is not None:
            manager.bind(current=self._redraw)

        self._redraw()

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    def _on_bg_color(self, _app, rgba) -> None:
        # Streifen leicht abgedunkelt gegenueber den Panels.
        self._bg_color.rgba = [rgba[0] * 0.8, rgba[1] * 0.8, rgba[2] * 0.8, 1]

    def _accent(self) -> list:
        app = App.get_running_app()
        if app is not None and hasattr(app, "accent_color"):
            return list(app.accent_color)
        return [0.0, 0.67, 1.0, 1.0]

    def _redraw(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

        self.canvas.after.clear()
        if not self._order:
            return
        current = self._manager.current if self._manager is not None else None
        accent = self._accent()

        dot = 10.0
        gap = 18.0
        total_h = len(self._order) * dot + (len(self._order) - 1) * gap
        start_y = self.center_y + total_h / 2 - dot
        cx = self.center_x

        with self.canvas.after:
            for i, name in enumerate(self._order):
                y = start_y - i * (dot + gap)
                if name == current:
                    Color(accent[0], accent[1], accent[2], 1.0)
                    size = dot + 3
                else:
                    Color(accent[0], accent[1], accent[2], 0.35)
                    size = dot
                Ellipse(pos=(cx - size / 2, y - (size - dot) / 2), size=(size, size))

    # ------------------------------------------------------------------
    # Touch-Gesten
    # ------------------------------------------------------------------

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            touch.ud["swipe_start_y"] = touch.y
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            dy = touch.y - touch.ud.get("swipe_start_y", touch.y)
            if dy >= _SWIPE_THRESHOLD:
                self._go(+1, direction_up=True)
            elif dy <= -_SWIPE_THRESHOLD:
                self._go(-1, direction_up=False)
            return True
        return super().on_touch_up(touch)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go(self, step: int, direction_up: bool) -> None:
        """Um ``step`` Screens weiterblaettern (mit passender Slide-Richtung)."""
        if self._manager is None or not self._order:
            return
        current = self._manager.current
        try:
            idx = self._order.index(current)
        except ValueError:
            idx = 0
        new_idx = (idx + step) % len(self._order)
        if new_idx == idx:
            return
        # Wischen nach oben -> neuer Screen kommt von unten herein.
        self._manager.transition.direction = "up" if direction_up else "down"
        self._manager.current = self._order[new_idx]
