"""``SettingsView`` - Screen zum Wechseln von Farbschema und DAW-Skalierung.

Bietet zwei Sektionen:

* **DAW-Skalierung** - waehlt das Tick-/dB-Profil der Fader
  (z. B. Logic Pro X oder eine alternative DAW).
* **Dark-Mode-Themes** - waehlt das globale Farbschema.

Die Auswahl ruft :meth:`ThemedAppMixin.set_theme` bzw.
:meth:`ThemedAppMixin.set_fader_daw` der laufenden App auf. Die Buttons
faerben sich reaktiv ein: Der aktive Eintrag wird hervorgehoben, indem die
View an ``app.current_theme_name`` und ``app.fader_daw`` gebunden ist.
"""

from __future__ import annotations

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from .theme import THEME_ORDER, THEMES

# Anzeigetext und Schluessel der waehlbaren DAW-Profile.
_DAW_CHOICES = [
    ("Logic Pro X", "LogicPro"),
    ("Alternative DAW", "AlternativeDAW"),
]

_INACTIVE_BG = [0.15, 0.15, 0.15, 1.0]
_INACTIVE_FG = [0.7, 0.7, 0.7, 1.0]


class SettingsView(BoxLayout):
    """Einstellungs-Oberflaeche fuer Theme- und DAW-Wahl.

    Liest und schreibt direkt die Theme-Properties der laufenden App
    (:class:`~touchcontrol.ui.app_mixin.ThemedAppMixin`).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            orientation="vertical",
            spacing=18,
            padding=[40, 30, 40, 30],
            **kwargs,
        )
        self._app = App.get_running_app()
        # Buttons je Sektion merken, um sie bei Wechsel neu einzufaerben.
        self._daw_buttons: dict[str, Button] = {}
        self._theme_buttons: dict[str, Button] = {}

        self._build_ui()

        # Auf Property-Wechsel reagieren (auch durch andere Stellen ausgeloest).
        if self._app is not None:
            if hasattr(self._app, "fader_daw"):
                self._app.bind(fader_daw=lambda *_a: self._refresh_daw_buttons())
            if hasattr(self._app, "current_theme_name"):
                self._app.bind(
                    current_theme_name=lambda *_a: self._refresh_theme_buttons()
                )
            self._app.bind(bg_color=self._apply_bg_color)

        self._refresh_daw_buttons()
        self._refresh_theme_buttons()

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Hintergrund (Theme-Haupthintergrund).
        with self.canvas.before:
            self._bg_color = Color(0.05, 0.05, 0.07, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)
        if self._app is not None and hasattr(self._app, "bg_color"):
            self._apply_bg_color(self._app, self._app.bg_color)

        # Titel.
        self.add_widget(self._heading("EINSTELLUNGEN", font_size=24, accent=True))

        # --- Sektion: DAW-Skalierung ---
        self.add_widget(self._heading("DAW Skalierung", font_size=16))
        daw_box = BoxLayout(
            orientation="vertical", spacing=10, size_hint=(None, None)
        )
        daw_box.size = (360, 110)
        for label, key in _DAW_CHOICES:
            btn = Button(
                text=label,
                bold=True,
                background_normal="",
                size_hint=(1, None),
                height=48,
            )
            btn.bind(on_release=lambda _b, k=key: self._select_daw(k))
            self._daw_buttons[key] = btn
            daw_box.add_widget(btn)
        self.add_widget(daw_box)

        # --- Sektion: Dark-Mode-Themes ---
        self.add_widget(self._heading("Dark Mode Themes", font_size=16))
        theme_box = BoxLayout(
            orientation="vertical", spacing=10, size_hint=(None, None)
        )
        theme_box.size = (360, len(THEME_ORDER) * 54)
        for key in THEME_ORDER:
            btn = Button(
                text=THEMES[key]["name"],
                bold=True,
                background_normal="",
                size_hint=(1, None),
                height=44,
            )
            btn.bind(on_release=lambda _b, k=key: self._select_theme(k))
            self._theme_buttons[key] = btn
            theme_box.add_widget(btn)
        self.add_widget(theme_box)

        # Fuellt den Rest, damit alles oben buendig sitzt.
        self.add_widget(Label(size_hint=(1, 1)))

    def _heading(self, text: str, font_size: int, accent: bool = False) -> Label:
        lbl = Label(
            text=text,
            font_size=f"{font_size}sp",
            bold=True,
            size_hint=(1, None),
            height=font_size + 16,
            halign="left",
            valign="middle",
            color=(1, 1, 1, 0.9),
        )
        lbl.bind(size=lambda i, *_a: setattr(i, "text_size", i.size))
        if accent and self._app is not None and hasattr(self._app, "accent_color"):
            lbl.color = self._app.accent_color
            self._app.bind(accent_color=lambda _i, c, _l=lbl: setattr(_l, "color", c))
        return lbl

    # ------------------------------------------------------------------
    # Hintergrund
    # ------------------------------------------------------------------

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _apply_bg_color(self, _app, rgba) -> None:
        self._bg_color.rgba = rgba

    # ------------------------------------------------------------------
    # Auswahl
    # ------------------------------------------------------------------

    def _select_daw(self, key: str) -> None:
        if self._app is not None and hasattr(self._app, "set_fader_daw"):
            self._app.set_fader_daw(key)

    def _select_theme(self, key: str) -> None:
        if self._app is not None and hasattr(self._app, "set_theme"):
            self._app.set_theme(key)

    def _refresh_daw_buttons(self) -> None:
        active = getattr(self._app, "fader_daw", None) if self._app else None
        accent = self._accent()
        for key, btn in self._daw_buttons.items():
            is_active = key == active
            btn.background_color = accent if is_active else _INACTIVE_BG
            btn.color = [1, 1, 1, 1] if is_active else _INACTIVE_FG

    def _refresh_theme_buttons(self) -> None:
        active = (
            getattr(self._app, "current_theme_name", None) if self._app else None
        )
        accent = self._accent()
        for key, btn in self._theme_buttons.items():
            is_active = key == active
            # Aktives Theme dezent in seiner eigenen Akzentfarbe markieren.
            theme_accent = THEMES[key]["accent"]
            if is_active:
                btn.background_color = [
                    theme_accent[0],
                    theme_accent[1],
                    theme_accent[2],
                    0.25,
                ]
                btn.color = accent
            else:
                btn.background_color = _INACTIVE_BG
                btn.color = _INACTIVE_FG

    def _accent(self) -> list:
        if self._app is not None and hasattr(self._app, "accent_color"):
            return list(self._app.accent_color)
        return [0.0, 0.67, 1.0, 1.0]
