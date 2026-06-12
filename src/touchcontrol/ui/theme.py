"""Theme- und DAW-Skalierungs-Definitionen fuer die TouchControl-Oberflaeche.

Uebernommen aus der ``Channelstrip Study`` und fuer den Produktivcode in das
Paket integriert. Enthaelt:

* :data:`THEMES` - mehrere Dark-Mode-Farbschemata (Akzent, Hintergrund,
  Widget-Hintergrund, Sekundaerfarbe sowie die dreistufigen Pegel-Farben).
* :func:`load_daw_scales` - laedt die Fader-Tick-Stuetzpunkte je DAW aus der
  ``daw_scales.json`` neben diesem Modul.

Die Farb- und Skalenauswahl wird zur Laufzeit ueber den Settings-Screen
gewechselt (siehe :class:`~touchcontrol.ui.settings_view.SettingsView`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

# Pfad zur DAW-Skalierungs-Konfiguration (liegt neben diesem Modul).
_SCALES_PATH = Path(__file__).with_name("daw_scales.json")

# Standardwerte, falls die Wahl ungueltig ist.
DEFAULT_THEME = "neon_ocean"
DEFAULT_DAW = "LogicPro"


# --- Dark-Mode-Farbschemata --------------------------------------------------
# Jedes Theme buendelt aufeinander abgestimmte RGBA-Werte. Neben Akzent,
# Hintergrund und Widget-Hintergrund sind die Pegelanzeigen-Farben
# (meter_low/mid/high) theme-spezifisch hinterlegt.
THEMES: Dict[str, Dict[str, object]] = {
    "neon_ocean": {
        "name": "Neon Ocean",
        "bg": [0.05, 0.05, 0.07, 1.0],
        "widget_bg": [0.08, 0.08, 0.11, 1.0],
        "accent": [0.0, 0.67, 1.0, 1.0],
        "secondary": [0.48, 0.17, 0.75, 1.0],
        "meter_low": [0.0, 0.67, 1.0, 0.85],
        "meter_mid": [0.2, 0.4, 0.9, 0.85],
        "meter_high": [0.48, 0.17, 0.75, 0.85],
    },
    "cyberpunk": {
        "name": "Cyberpunk 2077",
        "bg": [0.05, 0.03, 0.05, 1.0],
        "widget_bg": [0.09, 0.05, 0.09, 1.0],
        "accent": [1.0, 0.0, 0.5, 1.0],
        "secondary": [1.0, 0.67, 0.0, 1.0],
        "meter_low": [1.0, 0.0, 0.5, 0.85],
        "meter_mid": [1.0, 0.35, 0.25, 0.85],
        "meter_high": [1.0, 0.67, 0.0, 0.85],
    },
    "forest_emerald": {
        "name": "Forest Emerald",
        "bg": [0.04, 0.05, 0.04, 1.0],
        "widget_bg": [0.07, 0.09, 0.07, 1.0],
        "accent": [0.0, 0.9, 0.46, 1.0],
        "secondary": [1.0, 0.8, 0.0, 1.0],
        "meter_low": [0.0, 0.7, 0.35, 0.85],
        "meter_mid": [0.0, 0.9, 0.46, 0.85],
        "meter_high": [1.0, 0.8, 0.0, 0.85],
    },
    "obsidian": {
        "name": "Obsidian Slate",
        "bg": [0.04, 0.04, 0.04, 1.0],
        "widget_bg": [0.08, 0.08, 0.08, 1.0],
        "accent": [0.9, 0.9, 0.9, 1.0],
        "secondary": [0.4, 0.4, 0.4, 1.0],
        "meter_low": [0.35, 0.35, 0.35, 0.85],
        "meter_mid": [0.6, 0.6, 0.6, 0.85],
        "meter_high": [0.9, 0.9, 0.9, 0.85],
    },
}

# Reihenfolge fuer die Anzeige im Settings-Screen.
THEME_ORDER: List[str] = ["neon_ocean", "cyberpunk", "forest_emerald", "obsidian"]


# --- Fallback-DAW-Skalen -----------------------------------------------------
# Werden genutzt, falls ``daw_scales.json`` fehlt oder fehlerhaft ist.
_FALLBACK_SCALES: Dict[str, List[Dict[str, object]]] = {
    "LogicPro": [
        {"pos": 1.00, "width": 44, "label": "6"},
        {"pos": 0.74, "width": 64, "label": "0"},
        {"pos": 0.51, "width": 44, "label": "5"},
        {"pos": 0.38, "width": 44, "label": "10"},
        {"pos": 0.28, "width": 44, "label": "15"},
        {"pos": 0.20, "width": 44, "label": "20"},
        {"pos": 0.10, "width": 44, "label": "30"},
        {"pos": 0.05, "width": 44, "label": "40"},
        {"pos": 0.00, "width": 44, "label": "00"},
    ],
}


def load_daw_scales() -> Dict[str, List[Dict[str, object]]]:
    """Laedt alle DAW-Skalierungsprofile aus ``daw_scales.json``.

    :returns: Dict ``{daw_name: [tick, ...]}``. Bei Lesefehlern wird das
        eingebaute Fallback-Profil zurueckgegeben.
    """
    try:
        with _SCALES_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:  # Datei fehlt oder ungueltiges JSON
        print(f"Warnung: daw_scales.json konnte nicht geladen werden: {exc}")
        return dict(_FALLBACK_SCALES)
