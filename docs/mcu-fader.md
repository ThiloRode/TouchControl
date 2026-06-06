# MCU-Fader-Kodierung

Die zwei reinen Funktionen, die einen Fader zwischen **Position (0.0–1.0)** und
der **MCU-Pitch-Bend-Nachricht** übersetzen. Sie sind der Kern, den später
`McuEncoder`/`McuDecoder` verwenden.

- **Quelltext:** [`src/touchcontrol/mcu/fader.py`](../src/touchcontrol/mcu/fader.py)
- **Tests:** [`tests/test_fader.py`](../tests/test_fader.py)

---

## 1. Wie überträgt MCU einen Fader?

Als **Pitch-Bend**-Nachricht, pro Kanal eine eigene, drei Bytes:

```
   Byte 1: 0xE0 + kanal     Statusbyte (0xE0 = Pitch-Bend), kanal 0–7
   Byte 2: LSB              untere 7 Bit des 14-bit-Werts
   Byte 3: MSB              obere 7 Bit des 14-bit-Werts
```

### Warum 14 Bit aus zwei Bytes?

MIDI-Datenbytes haben nur **7 nutzbare Bits** (0–127); das oberste Bit ist
Statusbytes vorbehalten. MCU kombiniert zwei davon zu **14 Bit** (0–16383):

$$\text{wert} = (\text{MSB} \ll 7)\;|\;\text{LSB}$$

Die Reihenfolge ist **LSB zuerst, dann MSB** (Pitch-Bend-Konvention).

### Beispiele

| Position | 14-bit-Wert | Bytes (Kanal 0) |
|---|---|---|
| 0.0 (unten) | 0 | `[0xE0, 0x00, 0x00]` |
| 1.0 (oben) | 16383 | `[0xE0, 0x7F, 0x7F]` |

---

## 2. Wichtig: linear, nicht logarithmisch

Wir übertragen die **Faderposition linear** über den Weg. Die Übersetzung
Position → Dezibel macht die **DAW** anhand ihrer eigenen Kennlinie – genau wie
bei einer echten Motorfader-MCU. Eine spätere dB-**Beschriftung** ist reine
Anzeige und greift nicht in die MIDI-Werte ein.

> **Offen / TODO:** Die dB-Skala und ihre Einteilung bauen wir später und prüfen
> sie **empirisch gegen Cubase und Ableton** (stimmt der Faderweg mit der
> dB-Anzeige der DAW überein?). Vorerst bewusst weggelassen.

---

## 3. Die Funktionen

### `fader_to_pitch_bend(channel, position) -> [status, lsb, msb]`

- `channel`: 0–7. Ungültige Kanäle werfen `ValueError`.
- `position`: 0.0–1.0; Werte außerhalb werden **geclamped** (begrenzt), damit
  UI-Rundungsfehler keine ungültigen MIDI-Werte erzeugen.
- Rechnet linear auf 0–16383 und zerlegt in zwei 7-Bit-Hälften.

### `pitch_bend_to_fader(message) -> (channel, position)`

- Gegenstück: prüft Länge (3 Bytes) und Status (`0xE_`), sonst `ValueError`.
- Setzt die zwei 7-Bit-Hälften zum 14-bit-Wert zusammen und normiert auf 0.0–1.0.

---

## 4. Die Tests

| Test | prüft |
|---|---|
| `test_unten_ist_null` / `test_oben_ist_maximum` | Grenzwerte 0.0 und 1.0 |
| `test_statusbyte_enthaelt_kanal` | Kanal sitzt im Statusbyte |
| `test_position_wird_geclamped` | Werte außerhalb 0–1 werden begrenzt |
| `test_ungueltiger_kanal_wirft` | `ValueError` bei Kanal außerhalb 0–7 |
| `test_datenbytes_immer_7bit` | LSB/MSB nie mit gesetztem obersten Bit |
| `test_decode_*` | Dekodieren von Grenzwerten, Kanal, Fehlerfälle |
| `test_round_trip` | encode → decode ergibt wieder den Startwert (über alle Kanäle/Positionen) |

Der **Round-Trip-Test** ist der wichtigste: Er beweist, dass Kodierung und
Dekodierung exakt zueinander passen – mit Toleranz von einem 14-bit-Schritt
(durch die Quantisierung).

### Ausführen

```bash
.venv/bin/python -m pytest tests/test_fader.py
```
