"""Demo: ein einzelner Fader, der echtes MCU-MIDI sendet UND empfaengt.

Dies ist ein *Test-/Demo-Skript* (kein Teil der App-Architektur). Es verbindet
die bisher gebauten Bausteine zu einem erlebbaren, **bidirektionalen** Ganzen:

    Hinweg:   Kivy-Slider -> fader_to_pitch_bend() -> MidiBackend.send() -> DAW
    Rueckweg: DAW -> MidiBackend.poll() -> pitch_bend_to_fader() -> Slider folgt

So testest du:

* **Ohne DAW:** Slider ziehen - die gesendeten Bytes und die Position werden
  unten im Fenster angezeigt. Das beweist UI -> MCU-Kodierung -> Senden.
* **Mit DAW:** In Cubase/Ableton ein Mackie-Control-Geraet anlegen und als
  Ein- und Ausgang den Port "TouchControl" waehlen. Beim Ziehen bewegt sich der
  Kanal-Fader in der DAW - und wenn du den Fader in der DAW bewegst (oder
  Automation abspielst), folgt der Slider hier.

Start (im Projektordner):
    .venv/bin/python scripts/fader_demo.py
"""

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider

from touchcontrol.mcu import fader_to_pitch_bend, pitch_bend_to_fader
from touchcontrol.midi import MidiBackend

# Auf welchem Kanal (0-7) sendet/empfaengt dieser Demo-Fader?
DEMO_CHANNEL = 0
# Name des virtuellen Ports, den die DAW als MCU-Ein-/Ausgang waehlen kann.
PORT_NAME = "TouchControl"
# Wie oft pro Sekunde holen wir eingehende MIDI-Nachrichten ab?
POLL_HZ = 60


class FaderDemo(BoxLayout):
    """Ein vertikaler Slider plus Status-Anzeige."""

    def __init__(self, backend: MidiBackend, **kwargs):
        super().__init__(orientation="vertical", padding=20, spacing=10, **kwargs)
        self._backend = backend

        # Sperre gegen Rueckkopplung: Wenn wir den Slider aufgrund einer
        # DAW-Nachricht setzen, soll das NICHT erneut ein Senden ausloesen.
        # Sonst entstuende eine Endlosschleife DAW -> Slider -> DAW -> ...
        self._updating_from_daw = False

        # Vertikaler Slider, Wertebereich 0.0-1.0 (genau unsere Faderposition).
        self._slider = Slider(
            min=0.0, max=1.0, value=0.0, orientation="vertical"
        )
        # Bei jeder Wertaenderung _on_value aufrufen.
        self._slider.bind(value=self._on_value)

        self._status = Label(
            text="Slider bewegen ...", size_hint=(1, None), height=80
        )

        self.add_widget(self._slider)
        self.add_widget(self._status)

        # Rueckweg: regelmaessig (POLL_HZ-mal pro Sekunde) eingehende
        # MIDI-Nachrichten abholen. Laeuft im Kivy-Hauptthread - daher duerfen
        # wir hier gefahrlos die UI (den Slider) anfassen.
        Clock.schedule_interval(self._poll_midi, 1.0 / POLL_HZ)

    def _on_value(self, _instance, position: float) -> None:
        """Callback bei Slider-Bewegung: kodieren, senden, anzeigen.

        Wird die Aenderung durch eine DAW-Nachricht ausgeloest, ueberspringen
        wir das Senden (Rueckkopplungs-Sperre).
        """
        if self._updating_from_daw:
            return
        # 1) Position in MCU-Pitch-Bend-Bytes umwandeln.
        message = fader_to_pitch_bend(DEMO_CHANNEL, position)
        # 2) Ueber den virtuellen Port senden.
        self._backend.send(message)
        # 3) Anzeigen, was passiert ist (Bytes hex + Position).
        hex_bytes = " ".join(f"{b:02X}" for b in message)
        self._status.text = f"Gesendet  Position {position:.3f}  [{hex_bytes}]"

    def _poll_midi(self, _dt: float) -> None:
        """Vom Clock-Timer aufgerufen: eingehende Nachrichten verarbeiten."""
        for message in self._backend.poll():
            # Uns interessieren hier nur Pitch-Bends (Fader). Andere Nachrichten
            # (z. B. der Verbindungs-Ping der DAW) ignorieren wir vorerst.
            if len(message) != 3 or message[0] & 0xF0 != 0xE0:
                continue
            channel, position = pitch_bend_to_fader(message)
            if channel != DEMO_CHANNEL:
                continue
            # Slider setzen, ohne dadurch erneut zu senden.
            self._updating_from_daw = True
            self._slider.value = position
            self._updating_from_daw = False

            hex_bytes = " ".join(f"{b:02X}" for b in message)
            self._status.text = f"Empfangen  Position {position:.3f}  [{hex_bytes}]"


class FaderDemoApp(App):
    def build(self):
        # Virtuellen Ausgang anbieten, damit die DAW uns als MCU sehen kann.
        self._backend = MidiBackend()
        self._backend.open_virtual(PORT_NAME)
        self.title = "TouchControl - Fader-Demo"
        return FaderDemo(self._backend)

    def on_stop(self):
        # Beim Schliessen den MIDI-Port sauber freigeben.
        self._backend.close()


if __name__ == "__main__":
    FaderDemoApp().run()
