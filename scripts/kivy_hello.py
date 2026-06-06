"""Schritt 1: Minimal-Fenster, um zu pruefen, dass Kivy startet.

Zeigt nur ein Fenster mit einem Text. Schliessen mit dem Fenster-Schliessknopf
oder Esc. Wenn dieses Fenster erscheint, funktioniert Kivy auf diesem System.

Start (im Projektordner):
    .venv/bin/python scripts/kivy_hello.py
"""

from kivy.app import App
from kivy.uix.label import Label


class HelloApp(App):
    def build(self):
        # Ein einzelnes Label als Fensterinhalt - mehr braucht der Test nicht.
        return Label(text="TouchControl: Kivy laeuft!", font_size="32sp")


if __name__ == "__main__":
    HelloApp().run()
