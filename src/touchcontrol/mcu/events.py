"""Semantische Events der MCU-Protokollschicht.

Ein *Event* ist ein kleines, unveraenderliches Datenobjekt, das die
**Bedeutung** einer eingegangenen MIDI-Nachricht ausdrueckt - losgeloest von
den rohen Bytes. Der :class:`~touchcontrol.mcu.decoder.McuDecoder` erzeugt diese
Events; der Rest der App (State, UI) arbeitet nur noch mit ihnen.

Alle Events erben von :class:`McuEvent` und sind ``frozen`` (unveraenderlich):
einmal erzeugt, aendern sie sich nicht mehr. Das macht den Datenfluss
vorhersehbar und schliesst eine ganze Klasse von Fehlern aus.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class McuEvent:
    """Gemeinsame Basis aller MCU-Events.

    Dient nur als gemeinsamer Typ, damit z. B. Listen ``list[McuEvent]`` sauber
    typisiert werden koennen. Enthaelt selbst keine Daten.
    """


@dataclass(frozen=True)
class FaderEvent(McuEvent):
    """Eine Faderbewegung, die von der DAW kam.

    :param channel: Kanal 0-7 (Kanalzug innerhalb der aktuellen Bank).
    :param position: Faderposition 0.0 (unten) bis 1.0 (oben).
    """

    channel: int
    position: float


@dataclass(frozen=True)
class HostConnectionQueryEvent(McuEvent):
    """Die DAW fragt, ob ein MCU-Geraet verbunden ist.

    Cubase sendet diesen SysEx beim Verbinden und periodisch als Heartbeat.
    Der Encoder muss darauf mit einem :meth:`McuEncoder.host_connection_reply`
    antworten, sonst haelt Cubase das Geraet fuer nicht verbunden und schickt
    immer wieder Resets.

    :param device_id: Geraete-ID aus dem SysEx (0x14 = Main, 0x15 = Extender XT).
    """

    device_id: int


@dataclass(frozen=True)
class LcdEvent(McuEvent):
    """Ein LCD-Schreib-Befehl der DAW (Kanalname oder V-Pot-Anzeige).

    Das MCU-LCD hat zwei Zeilen mit je 56 Zeichen (8 Kanaele x 7 Zeichen):

    * **Obere Zeile** (offset 0-55): V-Pot-Modus-Namen ("Pan", "EQ", ...)
    * **Untere Zeile** (offset 56-111): **Kanalnamen** aus der DAW

    :param device_id: Geraete-ID (0x14 = Main, 0x15 = XT).
    :param offset: Startposition im 112-Zeichen-Display (0-111).
    :param text: Dekodierter ASCII-Text ab ``offset``.
    """

    device_id: int
    offset: int
    text: str


@dataclass(frozen=True)
class ButtonEvent(McuEvent):
    """Ein Taster-/LED-Zustand (Note Bang) von der DAW oder zum Senden.

    MCU uebertraegt alle Taster als *Note Bang*: eine Note-On-Nachricht, deren
    Velocity den Zustand kodiert (``0x7F`` = gedrueckt/LED an, ``0x00`` =
    losgelassen/LED aus). Welche Funktion eine Note hat, steht in
    :mod:`touchcontrol.mcu.constants`.

    :param note: MIDI-Note-Nummer (z. B. 0x10 = Mute Kanal 0).
    :param pressed: ``True`` = gedrueckt / LED an, ``False`` = aus.
    """

    note: int
    pressed: bool


@dataclass(frozen=True)
class MeterEvent(McuEvent):
    """Ein Pegel-Update (VU-Meter) der DAW.

    MCU sendet Pegel als Channel-Pressure (``0xD0``). Das Datenbyte teilt sich
    in zwei Nibbles: oberes = Kanal 0-7, unteres = Pegelstufe 0-15.

    :param channel: Kanal 0-7.
    :param level: Pegelstufe 0 (Stille) bis 15 (Clipping/Overload).
    """

    channel: int
    level: int


@dataclass(frozen=True)
class VPotEvent(McuEvent):
    """Ein V-Pot-LED-Ring-Update der DAW (zeigt z. B. die Pan-Position).

    MCU sendet den Ring als Control-Change (CC ``0x30``-``0x37``). Das
    Wert-Byte kodiert: Bit 6 = mittlere LED, Bits 5-4 = Modus, Bits 3-0 = Wert.

    :param channel: Kanal 0-7.
    :param mode: Ring-Darstellungsmodus (0-3).
    :param value: Ring-Wert 0-15 (bei Pan typisch 1-11, 6 = Mitte).
    :param center_led: Ob die kleine LED unter dem Encoder leuchtet.
    """

    channel: int
    mode: int
    value: int
    center_led: bool
