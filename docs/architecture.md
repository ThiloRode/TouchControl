# Architektur

## Ziel & Rahmen

- Touchscreen-Mackie-Control-(MCU)-Controller.
- Entwicklung auf macOS, Betrieb auf Raspberry Pi 4 (Display 1280×800, Querformat).
- GUI: **Kivy**. MIDI-I/O: **python-rtmidi**.
- Transport: **RTP-MIDI**. Auf dem Pi via McLaren `rtpmidi` bzw. `rtpmidid` (ALSA),
  auf dem Mac zur Entwicklung via **IAC-Treiber** (kein Netzwerk nötig).

## Funktionsumfang

Fader, Meter, Solo, Mute, Select, Pan, Kanalname, Bank links/rechts.
Kein Master-Fader. Mehrere DAWs: Start mit **Cubase** und **Ableton** (+ Generic).

## Schichten

| Schicht | Klassen | Aufgabe |
|---|---|---|
| Transport | `MidiBackend` | python-rtmidi kapseln: Ports öffnen, Bytes senden, eingehende Bytes in eine thread-sichere Queue legen |
| Protokoll | `McuDecoder`, `McuEncoder` | Bytes ↔ semantische Events |
| DAW-Profil | `DawProfile` (+ `Generic`/`Cubase`/`Ableton`) | nur DAW-Eigenheiten (Meter-Skalierung, LCD-Aufteilung, Pan-Anzeige) |
| Model | `ChannelState`, `MixerState` | Kanal-/Mixer-Zustand, Observer-Benachrichtigung |
| UI | `ChannelStripWidget`, `MixerView`, Screens | Touch-Oberfläche (Kivy) |
| Glue | `SurfaceController`, `AppController`, `TouchHUIApp` | verbindet alle Schichten |

## Datenfluss

- **DAW → App:** `MidiBackend` → `McuDecoder` → Event → (`DawProfile`) → `MixerState` → UI.
- **App → DAW:** Touch → `AppController` → (`DawProfile`) → `McuEncoder` → `MidiBackend`.

## Designentscheidungen

1. Fader intern als 14-bit (0–16383); UI-Helfer rechnet nach 0.0–1.0 um.
2. Model → UI über einfachen **Observer-Callback** (Model bleibt Kivy-frei, testbar).
3. Kein Master-Fader.
4. DAW-Profil als **Strategie-Objekt** plus Konfig-Daten für reine Tabellen.

## Erweiterbarkeit (Nähte)

- **Kaskadieren** = MCU-Extender-Prinzip. Main = Geräte-ID `0x14`, Extender = `0x15`.
  Eine Kiste = ein MCU-Gerät = ein MIDI-Portpaar = 8 Kanäle.
- **`Surface`** = ein MCU-Gerät (eigener `MidiBackend` + 8-Kanal-State + Encoder/Decoder/Profil).
  `channel_count` und `device_role` werden **nicht** hartkodiert.
- **Geräte-Rolle** ist eine **Laufzeit-Einstellung** (Settings-Screen), gespeichert in `config.json`
  → ein identisches Image für alle Kisten.
- UI als **`ScreenManager`**: `MixerScreen` + Platzhalter (`EqScreen`, `DynamicsScreen`)
  für spätere EQ-/Kompressor-Oberflächen (anbindbar über MCU-V-Pot-Zuweisungsmodi).

## Threading

`python-rtmidi` ruft eingehende Daten in einem eigenen MIDI-Thread auf.
Kivy darf nur im Hauptthread angefasst werden → eingehende Bytes laufen über eine
**Queue**, die der `AppController` per `Clock.schedule_interval` im Hauptthread leert.
