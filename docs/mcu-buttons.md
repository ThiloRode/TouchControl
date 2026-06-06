# MCU – Tasten, Meter, Pan & Automation

Dieser Schritt ergänzt den reinen Fader-Betrieb um die restlichen
Kanal­funktionen eines Mackie-Control-Streifens:

- **Rec, Solo, Mute, Select** – pro Kanal
- **Read, Write** (Automations­modus) – global, wirken aber auf den
  aktuell selektierten Kanal
- **Meter** – Pegelanzeige pro Kanal
- **Pan** – V-Pot (Endlos-Drehgeber) pro Kanal

> Hinweis: **Monitor** existiert im MCU-Protokoll nicht und wurde bewusst
> ausgelassen.

## 1. MIDI-Abbildung

Alle Konstanten stehen zentral in
[`mcu/constants.py`](../src/touchcontrol/mcu/constants.py).

### Tasten (Note Bang)

Tasten werden als **Note-On** gesendet und empfangen. Die DAW schickt
Feedback ebenfalls als Note-On:

- `Velocity 0x7F` = Taste/LED **an**
- `Velocity 0x00` = Taste/LED **aus**

| Funktion | Basis-Note | Kanäle      |
| -------- | ---------- | ----------- |
| Rec      | `0x00`     | `+0 … +7`   |
| Solo     | `0x08`     | `+0 … +7`   |
| Mute     | `0x10`     | `+0 … +7`   |
| Select   | `0x18`     | `+0 … +7`   |
| Read     | `0x4A`     | global      |
| Write    | `0x4B`     | global      |

Die Note für „Mute Kanal 3" ist also `MUTE_BASE + 3 = 0x13`.

#### Bang = zwei Nachrichten

Reale Hardware sendet beim Tastendruck einen kurzen Impuls: erst „an",
dann sofort „aus". Genau das macht
[`McuEncoder.button_bang(note)`](../src/touchcontrol/mcu/encoder.py) – es
liefert **zwei** Nachrichten:

```python
[[0x90, note, 0x7F], [0x90, note, 0x00]]
```

Die DAW interpretiert das als Tastendruck und schickt anschließend das
tatsächliche LED-Feedback zurück. Die App richtet ihren Tastenzustand
**immer nach diesem Feedback** aus – nie nach dem eigenen Druck. So
stimmen UI und DAW garantiert überein.

### Read / Write – erst selektieren, dann umschalten

Read und Write sind im MCU-Protokoll **globale** Tasten (eine Note für
alle Kanäle). Damit sie sich trotzdem pro Kanal bedienen lassen, macht
die App genau das, was die Hardware auch tut:

1. **Select** des Kanals senden (`button_bang(SELECT_BASE + ch)`)
2. danach **Read** bzw. **Write** senden (`button_bang(READ/WRITE)`)

Im Modell landet das Read/Write-Feedback deshalb beim aktuell
selektierten Kanal (`MixerState.selected_channel`).

### Meter (Channel Pressure)

Pegel kommen als **Channel Pressure** (`0xD0`). Das einzelne Datenbyte
kodiert Kanal und Pegel zusammen:

```
Datenbyte = (Kanal << 4) | Pegel      # Kanal 0–7, Pegel 0–15
```

→ [`MeterEvent(channel, level)`](../src/touchcontrol/mcu/events.py)

### Pan (V-Pot)

Der Pan-Regler ist ein **Endlos-Drehgeber** (V-Pot):

- **Senden** (App → DAW): relative Bewegung als Control Change
  `CC 0x10+ch`. Wert = Anzahl Schritte, Bit 6 (`0x40`) gesetzt = gegen
  den Uhrzeigersinn.
  → [`McuEncoder.vpot_rotate(channel, ticks)`](../src/touchcontrol/mcu/encoder.py)
- **Empfangen** (DAW → App): Ring-Position als CC `0x30+ch`.
  → [`VPotEvent(channel, mode, value, center_led)`](../src/touchcontrol/mcu/events.py)

Der Ringwert (1…11) wird im Modell auf `pan` 0.0…1.0 abgebildet
(0.5 = Mitte).

## 2. Zustand (Model)

[`ChannelState`](../src/touchcontrol/model/channel_state.py) hat dafür die
Felder `rec`, `solo`, `mute`, `select`, `read`, `write`, `meter_level`
und `pan`.

[`MixerState.apply_event`](../src/touchcontrol/model/mixer_state.py)
verteilt die Events:

- `ButtonEvent` → Rec/Solo/Mute/Select am passenden Kanal; Select merkt
  zusätzlich den `selected_channel`; Read/Write am selektierten Kanal.
- `MeterEvent` → `meter_level`.
- `VPotEvent` → `pan`.

## 3. UI

[`ChannelStripWidget`](../src/touchcontrol/ui/channel_strip.py) zeigt je
Streifen: Name, Pan-Slider, Meter-Balken, Fader und sechs Tasten
(Rec, Solo, Mute, Sel, Read, Write).

- Tastendruck sendet einen Bang und setzt die optische Darstellung
  **aus dem Modellzustand** zurück (Feedback-getrieben).
- DAW-Feedback aktualisiert Slider, Pan, Name, Meter und Tasten,
  ohne erneut zu senden (`_updating_from_daw`-Guard verhindert
  Rückkopplung).

## 4. Tests

- [`tests/test_decoder.py`](../tests/test_decoder.py) – Note/Pressure/CC
  → Button/Meter/VPot-Events.
- [`tests/test_encoder.py`](../tests/test_encoder.py) – `button_bang`,
  `vpot_rotate` (Richtung & 6-Bit-Begrenzung).
- [`tests/test_state.py`](../tests/test_state.py) – Event-Anwendung auf
  Kanäle, Select/Read/Write-Logik, Meter und Pan-Abbildung.
