"""``MixerState`` - Gesamtzustand des Mischers (eine Surface = 8 Kanaele).

Haelt eine Liste von :class:`~touchcontrol.model.channel_state.ChannelState`-
Objekten und den aktuellen Bank-Offset. Ausserdem routet er eingehende
:class:`~touchcontrol.mcu.events.McuEvent`-Objekte an den richtigen Kanal.

Das Routing laeuft so::

    backend.poll()
    -> McuDecoder.decode_many()
    -> MixerState.apply_event(event)   <-- hier landen wir
    -> ChannelState.update(...)
    -> Listener (UI) wird benachrichtigt

Warum ``apply_event`` statt einzelner Methoden pro Event-Typ?
Weil der Aufrufer (spaeter ``SurfaceController``) nur eine Methode aufrufen
soll - er muss nicht wissen, welches Event welchen State aendert. Das ist
die Aufgabe des ``MixerState``.
"""

from __future__ import annotations

from typing import Callable, List

from touchcontrol.mcu.constants import (
    MUTE_BASE,
    READ,
    REC_BASE,
    SELECT_BASE,
    SOLO_BASE,
    WRITE,
)
from touchcontrol.mcu.events import (
    ButtonEvent,
    FaderEvent,
    LcdEvent,
    McuEvent,
    MeterEvent,
    VPotEvent,
)

from .channel_state import ChannelState

# Standard-Kanalzahl einer MCU-Surface (ein Geraet = 8 Kanalzuege).
_DEFAULT_CHANNEL_COUNT = 8


class MixerState:
    """Zustand einer kompletten MCU-Surface (8 Kanaele + Bank-Offset).

    :param channel_count: Anzahl Kanalzuege dieser Surface (Standard: 8).
    """

    def __init__(self, channel_count: int = _DEFAULT_CHANNEL_COUNT) -> None:
        self.channel_count: int = channel_count

        # Ein ChannelState pro Kanalzug, Index 0 bis channel_count-1.
        self.channels: List[ChannelState] = [
            ChannelState(i) for i in range(channel_count)
        ]

        # Bank-Offset: wie viele Kanaele wurde die Bank nach rechts geschoben?
        # 0 = Kanaele 1-8, 8 = Kanaele 9-16 usw.
        self.bank_offset: int = 0

        # LCD-Puffer: 112 Zeichen wie das echte MCU-Display.
        # Obere Zeile = Index 0-55 (V-Pot-Modus), untere Zeile = 56-111
        # (Kanalnamen). Cubase schreibt an beliebige Offsets - der Puffer
        # haelt den Gesamtzustand, daraus leiten wir die Kanalnamen ab.
        self._lcd: List[str] = [" "] * 112

        # Welcher Kanal ist gerade selektiert? Wird aus dem Select-LED-
        # Feedback abgeleitet. Read/Write (global) gelten fuer diesen Kanal.
        self.selected_channel: int = 0

        # Listener, die bei einer Bank-Aenderung informiert werden.
        self._bank_listeners: List[Callable[["MixerState"], None]] = []

    # ------------------------------------------------------------------
    # Kanalzugriff
    # ------------------------------------------------------------------

    def channel(self, index: int) -> ChannelState:
        """Einen Kanalzug per Index zurueckgeben.

        :param index: Kanalindex 0 bis channel_count-1.
        :raises IndexError: Wenn der Index ausserhalb des gueltigen Bereichs.
        """
        if not (0 <= index < self.channel_count):
            raise IndexError(
                f"Kanal {index} ausserhalb 0..{self.channel_count - 1}"
            )
        return self.channels[index]

    # ------------------------------------------------------------------
    # Event-Routing
    # ------------------------------------------------------------------

    def apply_event(self, event: McuEvent) -> None:
        """Ein MCU-Event in den State uebernehmen.

        Unbekannte Event-Typen werden schweigend ignoriert - das erlaubt,
        neue Events schrittweise hinzuzufuegen, ohne bestehenden Code
        anpassen zu muessen.

        :param event: Ein beliebiges :class:`~touchcontrol.mcu.events.McuEvent`.
        """
        if isinstance(event, FaderEvent):
            self._apply_fader(event)
        elif isinstance(event, LcdEvent):
            self._apply_lcd(event)
        elif isinstance(event, ButtonEvent):
            self._apply_button(event)
        elif isinstance(event, MeterEvent):
            self._apply_meter(event)
        elif isinstance(event, VPotEvent):
            self._apply_vpot(event)
        # Weitere Event-Typen folgen schrittweise.

    def apply_events(self, events: List[McuEvent]) -> None:
        """Mehrere Events der Reihe nach in den State uebernehmen.

        Bequeme Abkuerzung fuer ``for e in events: apply_event(e)``.
        Typische Nutzung::

            state.apply_events(decoder.decode_many(backend.poll()))
        """
        for event in events:
            self.apply_event(event)

    # ------------------------------------------------------------------
    # Bank-Navigation
    # ------------------------------------------------------------------

    def add_bank_listener(self, callback: Callable[["MixerState"], None]) -> None:
        """Callback registrieren, der bei Bank-Aenderung aufgerufen wird."""
        self._bank_listeners.append(callback)

    def bank_left(self, schritte: int = 8) -> None:
        """Bank um ``schritte`` nach links schieben (Minimum: Offset 0)."""
        self.bank_offset = max(0, self.bank_offset - schritte)
        self._notify_bank()

    def bank_right(self, schritte: int = 8) -> None:
        """Bank um ``schritte`` nach rechts schieben."""
        self.bank_offset += schritte
        self._notify_bank()

    def _notify_bank(self) -> None:
        for cb in self._bank_listeners:
            cb(self)

    # ------------------------------------------------------------------
    # Interne Routing-Methoden
    # ------------------------------------------------------------------

    def _apply_fader(self, event: FaderEvent) -> None:
        """Fader-Event in den Kanal-State schreiben."""
        if 0 <= event.channel < self.channel_count:
            self.channels[event.channel].update(fader_position=event.position)

    def _apply_button(self, event: ButtonEvent) -> None:
        """Taster-/LED-Event auswerten und in den passenden State schreiben.

        Pro-Kanal-Taster (Rec/Solo/Mute/Select) gehen direkt an ihren Kanal.
        Die globalen Automations-LEDs (Read/Write) gelten fuer den aktuell
        selektierten Kanal.
        """
        note = event.note

        if REC_BASE <= note < REC_BASE + self.channel_count:
            self.channels[note - REC_BASE].update(rec=event.pressed)
        elif SOLO_BASE <= note < SOLO_BASE + self.channel_count:
            self.channels[note - SOLO_BASE].update(solo=event.pressed)
        elif MUTE_BASE <= note < MUTE_BASE + self.channel_count:
            self.channels[note - MUTE_BASE].update(mute=event.pressed)
        elif SELECT_BASE <= note < SELECT_BASE + self.channel_count:
            ch = note - SELECT_BASE
            self.channels[ch].update(select=event.pressed)
            if event.pressed:
                # Neuer selektierter Kanal merken (fuer Read/Write).
                self.selected_channel = ch
        elif note == READ:
            self.channels[self.selected_channel].update(read=event.pressed)
        elif note == WRITE:
            self.channels[self.selected_channel].update(write=event.pressed)
        # Andere Noten (Transport, Funktionstasten) ignorieren wir hier.

    def _apply_meter(self, event: MeterEvent) -> None:
        """Pegel-Event in den Kanal-State schreiben."""
        if 0 <= event.channel < self.channel_count:
            self.channels[event.channel].update(meter_level=event.level)

    def _apply_vpot(self, event: VPotEvent) -> None:
        """V-Pot-Ring-Event in eine Pan-Position 0.0-1.0 umrechnen.

        Der Ring-Wert 1-11 entspricht der LED-Position; 6 = Mitte. Wert 0
        bedeutet "keine LED" und wird als Mitte interpretiert.
        """
        if not (0 <= event.channel < self.channel_count):
            return
        if event.value <= 0:
            pan = 0.5
        else:
            pan = max(0.0, min(1.0, (event.value - 1) / 10.0))
        self.channels[event.channel].update(pan=pan)

    # LCD: 112 Zeichen, untere Zeile (Kanalnamen) beginnt bei Offset 56,
    # jeder Kanal belegt 7 Zeichen.
    _LCD_SIZE = 112
    _LCD_LOWER_ROW = 56
    _LCD_CHARS_PER_CH = 7

    def _apply_lcd(self, event: LcdEvent) -> None:
        """LCD-Event in den Puffer schreiben und Kanalnamen neu ableiten.

        Cubase schreibt an beliebige Offsets (auch mitten in einen Kanal oder
        ueber Kanalgrenzen hinweg). Deshalb halten wir wie die echte Hardware
        einen 112-Zeichen-Puffer und leiten danach die Namen daraus ab.

        Nur die **untere Zeile** (Offset 56-111) enthaelt die Kanalnamen.
        """
        # 1. Eingehenden Text an seine exakte Position in den Puffer schreiben.
        for i, zeichen in enumerate(event.text):
            pos = event.offset + i
            if 0 <= pos < self._LCD_SIZE:
                self._lcd[pos] = zeichen

        # 2. Pruefen, ob die untere Zeile (Kanalnamen) betroffen war.
        text_end = event.offset + len(event.text)
        if text_end <= self._LCD_LOWER_ROW:
            return  # Nur obere Zeile geaendert - keine Namen betroffen.

        # 3. Alle 8 Kanalnamen frisch aus dem Puffer ableiten.
        lo = self._LCD_LOWER_ROW
        chars = self._LCD_CHARS_PER_CH
        for ch in range(self.channel_count):
            start = lo + ch * chars
            name = "".join(self._lcd[start: start + chars]).strip()
            self.channels[ch].update(name=name)

    # ------------------------------------------------------------------
    # Darstellung
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"MixerState(channels={self.channel_count}, "
            f"bank_offset={self.bank_offset})"
        )
