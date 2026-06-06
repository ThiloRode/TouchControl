"""Demo: 8 Kanalzuege mit vollstaendiger MIDI-Anbindung an Cubase.

Verbindet alle bisher gebauten Bausteine zu einer lauffaehigen App:

    DAW (Cubase)
      |  MIDI (TouchControl-Port)
      v
    MidiBackend.poll()          -- holt Bytes aus der thread-sicheren Queue
      |
      v
    McuDecoder.decode_many()    -- Bytes -> semantische Events
      |
      +-- HostConnectionQueryEvent -> McuEncoder.host_connection_reply() -> senden
      |
      +-- FaderEvent -> MixerState.apply_event()
                           |
                           v
                        ChannelState.update()
                           |
                           v
                        ChannelStripWidget._on_state_changed()  (Observer)
                           |
                           v
                        Slider / Label / Meter werden aktualisiert

Ausserdem: Benutzer zieht Fader in der UI -> ChannelStripWidget sendet
MCU-Pitch-Bend -> Cubase bewegt den Kanal-Fader.

Start (im Projektordner):
    .venv/bin/python scripts/mixer_demo.py

Voraussetzung: In Cubase Studio-Setup -> Mackie Control ->
MIDI-Eingang und -Ausgang: "TouchControl".
Beenden mit Fenster schliessen oder Strg+C.
"""

from kivy.app import App
from kivy.clock import Clock

from touchcontrol.midi import MidiBackend
from touchcontrol.mcu import McuDecoder, McuEncoder
from touchcontrol.mcu.events import HostConnectionQueryEvent, LcdEvent
from touchcontrol.model import MixerState
from touchcontrol.ui import MixerView

# Name des virtuellen Ports, den Cubase als MCU-Ein-/Ausgang sieht.
PORT_NAME = "TouchControl"
# Geraete-ID: 0x14 = Mackie Control (Main).
DEVICE_ID = 0x14
# Wie oft pro Sekunde MIDI abholen.
POLL_HZ = 60


class MixerDemoApp(App):
    """Haupt-App: oeffnet den MIDI-Port und zeigt 8 Kanalzuege."""

    def build(self):
        # Alle Bausteine anlegen.
        self._backend = MidiBackend()
        self._decoder = McuDecoder()
        self._encoder = McuEncoder()
        self._mixer = MixerState()

        # Virtuellen MIDI-Port oeffnen (Cubase sieht ihn als Geraet).
        self._backend.open_virtual(PORT_NAME)
        print(f"Virtueller Port '{PORT_NAME}' geoeffnet.")

        # Regelmaessig MIDI-Nachrichten abholen (im Kivy-Hauptthread!).
        Clock.schedule_interval(self._poll_midi, 1.0 / POLL_HZ)

        # Vollbild fuer den 10.1"-Touchscreen (1280x800).
        # Auf dem Mac im Entwicklungsmodus als normales Fenster.
        return MixerView(
            mixer_state=self._mixer,
            backend=self._backend,
            encoder=self._encoder,
        )

    def _poll_midi(self, _dt: float) -> None:
        """Im Kivy-Takt MIDI abholen und als Events in den State einspeisen."""
        for message in self._backend.poll():
            event = self._decoder.decode(message)
            if event is None:
                continue

            if isinstance(event, HostConnectionQueryEvent):
                # Handshake beantworten, damit Cubase das Geraet akzeptiert.
                if event.device_id == DEVICE_ID:
                    reply = self._encoder.host_connection_reply(event.device_id)
                    self._backend.send(reply)
            elif isinstance(event, LcdEvent):
                self._mixer.apply_event(event)
            else:
                # Alle anderen bekannten Events (FaderEvent, ...) in den State.
                self._mixer.apply_event(event)

    def on_stop(self) -> None:
        """MIDI-Port beim Beenden sauber schliessen."""
        self._backend.close()


if __name__ == "__main__":
    MixerDemoApp().run()
