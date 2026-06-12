"""``ChannelState`` - Zustand eines einzelnen Kanalzugs.

Haelt alle Werte, die ein Kanalzug haben kann: Faderposition, Pegelwert,
Mute/Solo/Select/Rec-Zustand und den Kanalnamen.

Das Modell ist **Kivy-frei** und damit eigenstaendig testbar. Die Verbindung
zur UI laeuft ueber einfache Observer-Callbacks: Wer ueber Aenderungen
informiert werden will, registriert sich mit :meth:`add_listener`. Sobald
:meth:`update` aufgerufen wird, bekommt jeder Listener den aktuellen
``ChannelState`` uebergeben.

Warum kein Kivy-Property hier? Das Modell soll auch ohne laufende
Kivy-App testbar sein (pytest), und spaeter auf dem Pi auch ohne Anzeige
laufen koennen (headless). Die Kivy-UI liest dann den State und registriert
sich als Listener.
"""

from __future__ import annotations

from typing import Callable, List


class ChannelState:
    """Zustand eines einzelnen Kanalzugs (Kanal 0-7 innerhalb der aktuellen Bank).

    Alle Felder koennen direkt gelesen werden. Aendern sollte man sie
    ausschliesslich ueber :meth:`update`, damit Listener benachrichtigt werden.

    :param channel: Kanalindex 0-7 innerhalb der aktuellen Bank.
    """

    def __init__(self, channel: int) -> None:
        self.channel: int = channel

        # Faderposition 0.0 (unten) bis 1.0 (oben).
        self.fader_position: float = 0.0

        # Pegelwert 0-15 (0 = kein Signal, 15 = Clipping). Kommt als
        # Channel-Pressure-Nachricht von der DAW (D0-Byte).
        self.meter_level: int = 0

        # Taster-Zustaende: True = aktiv/leuchtend.
        self.mute: bool = False
        self.solo: bool = False
        self.select: bool = False
        self.rec: bool = False

        # Pan-/V-Pot-Position 0.0 (ganz links) bis 1.0 (ganz rechts),
        # 0.5 = Mitte. Kommt als V-Pot-LED-Ring (CC) von der DAW.
        self.pan: float = 0.5

        # Kanalname, wie ihn die DAW per LCD-SysEx schickt (max. 7 Zeichen).
        self.name: str = ""

        # Interne Liste der Observer-Callbacks. Nicht direkt ansprechen.
        self._listeners: List[Callable[["ChannelState"], None]] = []

    # ------------------------------------------------------------------
    # Observer-Schnittstelle
    # ------------------------------------------------------------------

    def add_listener(self, callback: Callable[["ChannelState"], None]) -> None:
        """Callback registrieren, der bei jeder Aenderung aufgerufen wird.

        Der Callback bekommt den ``ChannelState`` selbst uebergeben, damit er
        alle aktuellen Werte lesen kann - er muss sich nichts merken.

        :param callback: Aufrufbares Objekt, z. B. eine Methode der UI.
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[["ChannelState"], None]) -> None:
        """Callback wieder abmelden (z. B. wenn ein Widget entfernt wird)."""
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass  # War gar nicht registriert - kein Fehler.

    def _notify(self) -> None:
        """Alle registrierten Listener aufrufen. Nur intern verwenden."""
        for cb in self._listeners:
            cb(self)

    # ------------------------------------------------------------------
    # Zustand aendern
    # ------------------------------------------------------------------

    def update(self, **felder) -> None:
        """Ein oder mehrere Felder setzen und alle Listener benachrichtigen.

        Beispiel::

            kanal.update(fader_position=0.75, mute=True)

        Unbekannte Feldnamen werden als ``AttributeError`` geworfen - das
        schuetzt vor Tippfehlern.

        :param felder: Schluessel-Wert-Paare der zu aendernden Felder.
        :raises AttributeError: Wenn ein Feldname nicht existiert.
        """
        for key, value in felder.items():
            if not hasattr(self, key) or key.startswith("_"):
                raise AttributeError(
                    f"ChannelState hat kein Feld '{key}'"
                )
            setattr(self, key, value)
        self._notify()

    # ------------------------------------------------------------------
    # Darstellung
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ChannelState(channel={self.channel}, "
            f"fader={self.fader_position:.2f}, "
            f"mute={self.mute}, solo={self.solo}, "
            f"select={self.select}, rec={self.rec}, "
            f"name={self.name!r}, meter={self.meter_level})"
        )
