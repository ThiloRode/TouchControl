"""``ThemedAppMixin`` - macht eine Kivy-:class:`~kivy.app.App` theme-faehig.

Die moderne Oberflaeche (Fader, Panner, Buttons, Panels) referenziert in der
KV-Datei reaktive Farb-Properties wie ``app.accent_color``. Damit jede App,
die diese UI nutzt, diese Properties besitzt, werden sie hier gebuendelt.

Verwendung::

    class MeineApp(ThemedAppMixin, App):
        ...

Beim Wechsel von Theme oder DAW-Profil (Settings-Screen) werden lediglich die
Properties dieser Mixin-Klasse aktualisiert - alle KV-Bindungen und die
Canvas-Anweisungen der Widgets zeichnen sich daraufhin automatisch neu.
"""

from __future__ import annotations

from kivy.properties import ListProperty, StringProperty

from .theme import DEFAULT_DAW, DEFAULT_THEME, THEMES


class ThemedAppMixin:
    """Stellt reaktive Theme-Properties und Umschalt-Methoden bereit.

    Muss zusammen mit :class:`kivy.app.App` (einem ``EventDispatcher``)
    verwendet werden, damit die Kivy-Properties funktionieren.
    """

    # Farb-Properties (RGBA). Defaults stammen aus dem Standard-Theme.
    accent_color = ListProperty(THEMES[DEFAULT_THEME]["accent"])
    secondary_color = ListProperty(THEMES[DEFAULT_THEME]["secondary"])
    bg_color = ListProperty(THEMES[DEFAULT_THEME]["bg"])
    widget_bg_color = ListProperty(THEMES[DEFAULT_THEME]["widget_bg"])
    meter_low_color = ListProperty(THEMES[DEFAULT_THEME]["meter_low"])
    meter_mid_color = ListProperty(THEMES[DEFAULT_THEME]["meter_mid"])
    meter_high_color = ListProperty(THEMES[DEFAULT_THEME]["meter_high"])

    # Aktuell gewaehltes Theme bzw. DAW-Skalierungsprofil.
    current_theme_name = StringProperty(DEFAULT_THEME)
    fader_daw = StringProperty(DEFAULT_DAW)

    def set_theme(self, theme_name: str) -> None:
        """Alle Farb-Properties auf das gewaehlte Theme setzen.

        :param theme_name: Schluessel aus :data:`touchcontrol.ui.theme.THEMES`.
            Unbekannte Namen werden ignoriert.
        """
        theme = THEMES.get(theme_name)
        if theme is None:
            return
        self.current_theme_name = theme_name
        self.accent_color = theme["accent"]
        self.secondary_color = theme["secondary"]
        self.bg_color = theme["bg"]
        self.widget_bg_color = theme["widget_bg"]
        self.meter_low_color = theme["meter_low"]
        self.meter_mid_color = theme["meter_mid"]
        self.meter_high_color = theme["meter_high"]

    def set_fader_daw(self, daw_name: str) -> None:
        """DAW-Skalierungsprofil fuer alle Fader umschalten.

        :param daw_name: Schluessel aus ``daw_scales.json``
            (z. B. ``"LogicPro"``).
        """
        self.fader_daw = daw_name
