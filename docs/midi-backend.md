# `MidiBackend` – die MIDI-Transportschicht

`MidiBackend` ist die **unterste Schicht** von TouchControl. Sie kapselt die
Bibliothek `python-rtmidi` und gibt dem Rest der Anwendung eine einfache,
**thread-sichere** Schnittstelle zum Senden und Empfangen roher MIDI-Bytes.

- **Quelltext:** [`src/touchcontrol/midi/backend.py`](../src/touchcontrol/midi/backend.py)
- **Tests:** [`tests/test_midi_backend.py`](../tests/test_midi_backend.py)

---

## 1. Warum diese Schicht?

`python-rtmidi` ist mächtig, aber „roh":

- Man arbeitet mit **zwei** Objekten (`MidiIn`, `MidiOut`).
- Ports werden über **Indizes** geöffnet, nicht über Namen.
- Nachrichten sind nackte **Byte-Listen**.
- Der Empfang läuft über einen **Callback in einem fremden Thread**.

`MidiBackend` versteckt all das hinter wenigen, klaren Methoden. Der Rest der
App muss nie wieder direkt mit `rtmidi` reden.

---

## 2. Das Thread-Problem und die Queue

`python-rtmidi` ruft eingehende MIDI-Nachrichten in einem **eigenen, internen
Thread** auf (nicht im Programm-Hauptthread). Die spätere Kivy-Oberfläche darf
aber **nur aus dem Hauptthread** angefasst werden. Würden wir im Callback direkt
die UI verändern, drohen Abstürze und Race-Conditions.

**Lösung – die Queue als „Briefkasten":**

```
   rtmidi-Thread                      Hauptthread (später Kivy)
 ┌───────────────┐   put()       ┌──────────┐   poll()       ┌──────────────┐
 │  _on_message  │ ────────────► │  Queue   │ ◄───────────── │ AppController │
 │  (fremd)      │               │(thread-  │                │ (regelmäßig)  │
 └───────────────┘               │  sicher) │                └──────────────┘
                                 └──────────┘
```

Der Callback `_on_message` legt eingehende Nachrichten **nur** in eine
`queue.Queue`. Diese Klasse aus der Standardbibliothek ist von Haus aus
thread-sicher. Der Hauptthread holt die Nachrichten später mit `poll()` heraus.

---

## 3. Die öffentliche Schnittstelle

| Methode | Zweck |
|---|---|
| `available_inputs()` / `available_outputs()` | Liste der Portnamen (Ein-/Ausgänge) |
| `open(input_name=None, output_name=None)` | vorhandene Ports per **Namensteil** öffnen |
| `open_virtual(name)` | eigenen **virtuellen** Ein-/Ausgang anbieten (App wird zum MIDI-Gerät) |
| `send(message)` | rohe MIDI-Bytes senden |
| `poll()` | alle seit dem letzten Aufruf eingegangenen Nachrichten holen |
| `close()` | Ports schließen, mehrfach aufrufbar |

Zusätzlich ist die Klasse als **Kontextmanager** nutzbar
(`with MidiBackend() as backend: ...`), wodurch `close()` automatisch läuft.

### Beispiel

```python
from touchcontrol.midi import MidiBackend

backend = MidiBackend()
backend.open(input_name="IAC", output_name="IAC")

backend.send([0xE0, 0x00, 0x40])      # Pitch-Bend (Fader) senden

for nachricht in backend.poll():       # eingegangene Nachrichten
    print(nachricht)

backend.close()
```

---

## 4. Der Code im Detail

### `__init__` – die Bausteine

```python
self._midi_in  = rtmidi.MidiIn()
self._midi_out = rtmidi.MidiOut()
self._queue    = queue.Queue()
self._input_open  = False
self._output_open = False
```

Zwei getrennte rtmidi-Objekte (Ein-/Ausgang), die thread-sichere Queue als
Briefkasten und zwei Merker, ob die Ports offen sind (für `send`/`close`).

### `_find_port` – Port per Namensteil

```python
for index, name in enumerate(ports):
    if name_part.lower() in name.lower():
        return index
return None
```

Sucht den **Index** zum ersten Port, dessen Name den gesuchten Teilstring
enthält (Groß/Kleinschreibung egal). So öffnen wir robust per Name: `"IAC"`
findet `"IAC Driver Bus 1"`. Wichtig, weil Portnamen auf Mac und Pi leicht
abweichen.

### `open` – vorhandene Ports öffnen

Sucht für Ein- und/oder Ausgang den Index und öffnet ihn. Existiert kein
passender Port, wird ein `ValueError` geworfen (klarer Fehler statt stiller
Fehlfunktion). Beim Eingang wird zusätzlich der Empfang vorbereitet
(`_setup_input_callback`).

### `open_virtual` – selbst zum MIDI-Gerät werden

Erzeugt je einen virtuellen **Ein-** und **Ausgang** mit demselben Namen. So
erscheint TouchControl im System als eigenständiges MIDI-Gerät – genau das wollen
wir später, damit die DAW uns als Mackie-Control-Gerät sieht.

> Hinweis: Virtuelle Ports unterstützt `rtmidi` auf **macOS** und **Linux**,
> aber **nicht** unter Windows. Für uns (Mac + Pi) ist das ideal.

### `_setup_input_callback` – SysEx zulassen, Callback setzen

```python
self._midi_in.ignore_types(sysex=False, timing=True, active_sense=True)
self._midi_in.set_callback(self._on_message)
```

**Sehr wichtig:** Standardmäßig **ignoriert** `rtmidi` SysEx-Nachrichten. Die
brauchen wir aber später für die **LCD-Anzeige (Kanalnamen)**. Deshalb
`sysex=False` (= nicht ignorieren). Timing-Clock und Active-Sensing sind nur
Rauschen und bleiben ignoriert.

### `_on_message` – der Callback (im fremden Thread!)

```python
message, _timestamp = event
self._queue.put(list(message))
```

`rtmidi` übergibt `event` als Tupel `(bytes, zeitstempel)`. Wir nehmen nur die
Bytes und legen sie in die Queue. **Hier wird bewusst nichts an der UI gemacht**
– nur „Brief einwerfen".

### `poll` – den Briefkasten leeren

```python
while True:
    try:
        nachrichten.append(self._queue.get_nowait())
    except queue.Empty:
        break
```

Holt alle wartenden Nachrichten heraus und gibt sie als Liste zurück. Läuft im
Hauptthread; `get_nowait()` blockiert nie.

### `send` – Bytes senden

Wirft `RuntimeError`, wenn kein Ausgang offen ist – das deutet fast immer auf
einen Programmierfehler hin (Senden ohne Verbindung).

### `close` – aufräumen

Beendet Callback und schließt offene Ports. Dank der Merker mehrfach gefahrlos
aufrufbar (wichtig z. B. in Tests und beim Beenden der App).

---

## 5. Die Tests

Ausgeführt mit `pytest`. Die spannendsten:

| Test | prüft |
|---|---|
| `test_find_port_per_teilstring` | Namens-Suche (auch „nicht gefunden") |
| `test_open_unbekannter_port_wirft` | klarer `ValueError` bei falschem Namen |
| `test_send_ohne_ausgang_wirft` | `RuntimeError` bei Senden ohne Verbindung |
| `test_loopback_senden_und_empfangen` | **echtes** Senden/Empfangen über zwei virtuelle Ports |
| `test_loopback_sysex_wird_empfangen` | SysEx kommt wirklich an (für LCD später) |

**Loopback-Idee:** Ein Backend bietet einen virtuellen Port an („Gerät"), ein
zweites verbindet sich per Namen damit („DAW") und sendet. So testen wir den
echten MIDI-Weg ganz ohne Hardware oder DAW.

### Ausführen

```bash
.venv/bin/python -m pytest tests/test_midi_backend.py
```
