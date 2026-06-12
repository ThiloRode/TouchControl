import json
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import NumericProperty, ListProperty, StringProperty, ObjectProperty
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
from kivy.clock import Clock

# Setzen einer fixen Fenstergröße für die App, damit das Dashboard mit 1050px Höhe
# auf allen Displays ohne Skalierungsverlust sauber dargestellt wird.
Window.size = (800, 1050)

# --- 2-3 Farben Darkmode Themes Definition ---
# Jedes Theme besteht aus harmonisch aufeinander abgestimmten HSL/RGB Farbwerten.
# Neben dem Akzent, Hintergrund und Widget-Hintergrund sind auch die Pegelanzeigen-Farben
# (meter_low, meter_mid, meter_high) theme-spezifisch hinterlegt, um ein homogenes
# visuelles Erscheinungsbild zu gewährleisten.
THEMES = {
    "neon_ocean": {
        "name": "Neon Ocean",
        "bg": [0.05, 0.05, 0.07, 1.0],         # Tiefes Dunkelblau-Grau
        "widget_bg": [0.08, 0.08, 0.11, 1.0],  # Etwas helleres Blaugrau (Kanalzug, Panels)
        "accent": [0.0, 0.67, 1.0, 1.0],       # Neon-Blau/Cyan für aktive Elemente
        "secondary": [0.48, 0.17, 0.75, 1.0],  # Deep Purple / Indigo (Bogen-Silhouette)
        "meter_low": [0.0, 0.67, 1.0, 0.85],   # Pegelmesser unten: Cyan
        "meter_mid": [0.2, 0.4, 0.9, 0.85],    # Pegelmesser Mitte: Indigo
        "meter_high": [0.48, 0.17, 0.75, 0.85] # Pegelmesser Peak: Deep Purple
    },
    "cyberpunk": {
        "name": "Cyberpunk 2077",
        "bg": [0.05, 0.03, 0.05, 1.0],         # Dunkles Violettschwarz
        "widget_bg": [0.09, 0.05, 0.09, 1.0],  # Tiefes Violett
        "accent": [1.0, 0.0, 0.5, 1.0],        # Neon-Magenta für Akzente
        "secondary": [1.0, 0.67, 0.0, 1.0],    # Electric Orange
        "meter_low": [1.0, 0.0, 0.5, 0.85],    # Pegelmesser unten: Neon-Magenta
        "meter_mid": [1.0, 0.35, 0.25, 0.85],  # Pegelmesser Mitte: Orange-Rot
        "meter_high": [1.0, 0.67, 0.0, 0.85]   # Pegelmesser Peak: Gelb/Orange
    },
    "forest_emerald": {
        "name": "Forest Emerald",
        "bg": [0.04, 0.05, 0.04, 1.0],         # Tiefes Waldschwarz
        "widget_bg": [0.07, 0.09, 0.07, 1.0],  # Schiefergrün
        "accent": [0.0, 0.9, 0.46, 1.0],       # Minzgrün
        "secondary": [1.0, 0.8, 0.0, 1.0],      # Soft-Gold
        "meter_low": [0.0, 0.7, 0.35, 0.85],   # Pegelmesser unten: Dunkelgrün
        "meter_mid": [0.0, 0.9, 0.46, 0.85],   # Pegelmesser Mitte: Minzgrün
        "meter_high": [1.0, 0.8, 0.0, 0.85]    # Pegelmesser Peak: Gold
    },
    "obsidian": {
        "name": "Obsidian Slate",
        "bg": [0.04, 0.04, 0.04, 1.0],         # Obsidian-Schwarz
        "widget_bg": [0.08, 0.08, 0.08, 1.0],  # Dunkelgrau
        "accent": [0.9, 0.9, 0.9, 1.0],        # Klares Reinweiß
        "secondary": [0.4, 0.4, 0.4, 1.0],      # Abgedunkeltes Grau
        "meter_low": [0.35, 0.35, 0.35, 0.85], # Pegelmesser unten: Dunkelgrau
        "meter_mid": [0.6, 0.6, 0.6, 0.85],    # Pegelmesser Mitte: Mittelgrau
        "meter_high": [0.9, 0.9, 0.9, 0.85]    # Pegelmesser Peak: Off-White
    }
}

class ModernFader(Widget):
    """
    Ein hochgradig anpassbarer Fader-Kanalzug. Er berechnet echte, nicht-lineare dB-Werte
    und visualisiert ein Echtzeit-Pegelmeter (Fast Attack, Slow Release), das
    sich exakt an den Stützpunkten der Ticks ausrichtet.
    """
    value = NumericProperty(0.5)         # Aktueller Schieberegler-Wert (0.0 - 1.0)
    cap_y = NumericProperty(0)           # Berechnete Y-Position der Faderkappe
    scale_config = ListProperty([])      # Die aus der JSON geladene Skalierungskonfiguration
    daw_name = StringProperty("LogicPro")# Aktuell geladener Name der DAW-Anwendung
    db_text = StringProperty("0.0")      # Der berechnete dB-String für das Fader-Label
    meter_db = NumericProperty(-96.0)    # Der aktuelle dB-Pegel des Animationsmeters

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 1. Standardkonfiguration aus der externen JSON-Datei laden
        self.load_daw_config()
        
        # 2. Bindung an das Theme-Hintergrund-Farben-Update erstellen,
        # damit bei einem Theme-Wechsel die Leinwand (draw_scale) sofort neu gezeichnet wird.
        app = App.get_running_app()
        app.bind(widget_bg_color=self.redraw, accent_color=self.redraw)
        
        # 3. Kivy-Property Bindings zur automatischen Layout- und Pegelaktualisierung
        self.bind(pos=self.redraw, size=self.redraw, value=self.update_geometry, meter_db=self.redraw)
        self.redraw()
        
        # 4. Timer für die Echtzeit-Pegelmeter-Simulation (30 FPS für flüssiges Rendering)
        self.sim_time = 0.0
        Clock.schedule_interval(self.simulate_audio_level, 1.0 / 30.0)

    def on_daw_name(self, instance, value):
        """Callback, wenn die DAW-Auswahl geändert wird."""
        self.load_daw_config()
        self.redraw()

    def load_daw_config(self):
        """
        Lädt die Skalierungswerte aus der externen `daw_scales.json` Datei.
        Berechnet dynamisch die db_points und identifiziert die Null-Linie.
        """
        try:
            with open("daw_scales.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            self.scale_config = data.get(self.daw_name, data.get("LogicPro"))
        except Exception as e:
            # Fallback, falls Datei nicht existiert oder fehlerhaft ist
            print(f"Error loading daw_scales.json: {e}")
            self.scale_config = [
                {"pos": 1.00, "width": 44, "label": "6"},
                {"pos": 0.74, "width": 64, "label": "0"},
                {"pos": 0.51, "width": 44, "label": "5"},
                {"pos": 0.38, "width": 44, "label": "10"},
                {"pos": 0.28, "width": 44, "label": "15"},
                {"pos": 0.20, "width": 44, "label": "20"},
                {"pos": 0.10, "width": 44, "label": "30"},
                {"pos": 0.05, "width": 44, "label": "40"},
                {"pos": 0.00, "width": 44, "label": "00"}
            ]

        # 1. Finde dynamisch den Stützpunkt für 0 dB.
        # Dies ist kritisch, um Vorzeichen für die dB-Berechnung korrekt zu bestimmen:
        # Alles unterhalb der 0-dB-Linie erhält ein negatives Vorzeichen.
        zero_pos = 0.74
        for tick in self.scale_config:
            if tick["label"] == "0":
                zero_pos = tick["pos"]
                break

        # 2. Berechne Stützpunkte (pos, db_val) zur linearen Interpolation
        self.db_points = []
        for tick in self.scale_config:
            pos = tick["pos"]
            lbl = tick["label"]
            if lbl == "00":
                db_val = -96.0  # Mute-Schwelle (Minus unendlich)
            else:
                val = float(lbl)
                db_val = -val if pos < zero_pos else val
            self.db_points.append((pos, db_val))
            
        # Stützpunkte absteigend nach relativer Position sortieren für korrekte Segmentfindung
        self.db_points.sort(key=lambda x: x[0], reverse=True)

    def redraw(self, *args):
        """Löscht und zeichnet die Hintergrundkomponenten und Ticks neu."""
        self.draw_scale()
        self.update_geometry()

    def get_pos_from_db(self, db_val):
        """
        Hilfsfunktion (Inverse Interpolation):
        Berechnet die relative Y-Position (0.0 bis 1.0) auf dem Fader aus einem dB-Wert.
        Wichtig, um den simulierten Audiopegel exakt an den Ticks auszurichten.
        """
        if not self.db_points:
            return 0.0
        
        # Obergrenze abfangen
        if db_val >= self.db_points[0][1]:
            return 1.0
        # Untergrenze abfangen
        if db_val <= self.db_points[-1][1]:
            return 0.0
            
        # Lineare Interpolation innerhalb des passenden Segments
        for i in range(len(self.db_points) - 1):
            p1, db1 = self.db_points[i]
            p2, db2 = self.db_points[i+1]
            if db2 <= db_val <= db1:
                ratio = (db_val - db2) / (db1 - db2)
                return p2 + ratio * (p1 - p2)
                
        return 0.0

    def draw_scale(self, *args):
        """
        Zeichnet das Fader-Widget. Da diese Methode im `canvas.before` aufgerufen wird,
        liegen Pegelmeter und Skalenstriche im Hintergrund, während die Schieberkappe
        darüber gleiten kann.
        """
        self.canvas.before.clear()
        with self.canvas.before:
            app = App.get_running_app()
            
            # 1. Widget-Hintergrund zeichnen
            Color(*app.widget_bg_color)
            Rectangle(pos=self.pos, size=self.size)

            # Regelweg-Grenzen definieren (50px Puffer oben und unten)
            track_bottom = self.y + 50
            track_height = self.height - 100
            
            # 2. Pegelmeter berechnen und zeichnen
            pos_meter = self.get_pos_from_db(self.meter_db)
            y_meter = track_bottom + (track_height * pos_meter)
            
            # Schwellenwerte für Farbgrenzen berechnen
            y_minus_10 = track_bottom + (track_height * self.get_pos_from_db(-10.0))
            y_zero = track_bottom + (track_height * self.get_pos_from_db(0.0))
            
            meter_w = 12
            meter_x = self.center_x - meter_w / 2
            
            # Pegelbalken stufenweise zeichnen (Farben stammen aus dem aktiven Theme)
            if self.meter_db > -90.0 and y_meter > track_bottom:
                # Bereich A: Leise bis moderat (bis -10 dB) -> meter_low_color
                h_low = min(y_meter, y_minus_10) - track_bottom
                if h_low > 0:
                    Color(*app.meter_low_color)
                    Rectangle(pos=(meter_x, track_bottom), size=(meter_w, h_low))
                
                # Bereich B: Laut/Nominal (-10 dB bis 0 dB) -> meter_mid_color
                if y_meter > y_minus_10:
                    h_mid = min(y_meter, y_zero) - y_minus_10
                    if h_mid > 0:
                        Color(*app.meter_mid_color)
                        Rectangle(pos=(meter_x, y_minus_10), size=(meter_w, h_mid))
                
                # Bereich C: Peak/Clipping (über 0 dB) -> meter_high_color
                if y_meter > y_zero:
                    h_high = y_meter - y_zero
                    if h_high > 0:
                        Color(*app.meter_high_color)
                        Rectangle(pos=(meter_x, y_zero), size=(meter_w, h_high))

            # 3. Skalenstriche (werden über den Pegelbalken gezeichnet, um die Lesbarkeit zu sichern)
            Color(1, 1, 1, 0.8)
            for tick in self.scale_config:
                y_pos = track_bottom + (track_height * tick['pos'])
                w = tick['width']
                Rectangle(pos=(self.center_x - w/2, y_pos), size=(w, 3))

    def get_db_value(self, pos):
        """
        Berechnet den decibel-Wert (dB) aus der relativen Position des Faders.
        Nutzt abschnittsweise lineare Interpolation anhand der geladenen JSON-Punkte.
        """
        if not self.db_points:
            return 0.0
            
        if pos >= 1.00:
            return self.db_points[0][1]
        if pos <= 0.00:
            return float('-inf')
            
        # Suche das passende Intervall
        for i in range(len(self.db_points) - 1):
            p1, db1 = self.db_points[i]
            p2, db2 = self.db_points[i+1]
            if p2 <= pos <= p1:
                ratio = (pos - p2) / (p1 - p2)
                return db2 + ratio * (db1 - db2)
                
        return float('-inf')

    def update_geometry(self, *args):
        """Berechnet die y-Position der Kappe neu und aktualisiert den db-Text."""
        track_bottom = self.y + 50
        track_height = self.height - 100
        self.cap_y = track_bottom + (track_height * self.value)
        
        # Berechne dB-Wert und formatiere die Ausgabe
        db_val = self.get_db_value(self.value)
        if db_val < -80:
            self.db_text = "-∞"
        elif db_val > 0.01:
            self.db_text = f"+{db_val:.1f}"
        else:
            self.db_text = f"{db_val:.1f}"

    def simulate_audio_level(self, dt):
        """
        Simuliert ein dynamisches Audio-Signal.
        Rechnet die Wellenform in dB um und wendet eine Hüllkurve an (Attack/Release).
        Der Pegel wird direkt durch die Stellung des Faders gedämpft.
        """
        import math
        import random
        
        self.sim_time += dt
        
        # Synthetischer Sound: Rhythmischer Impuls (1.3 Hz) gemischt mit Melodie und Rauschen
        beat = math.pow(max(0, math.sin(self.sim_time * 2.0 * math.pi * 1.3)), 5)
        melody = 0.3 * math.sin(self.sim_time * 2.0 * math.pi * 0.18) + 0.3
        noise = 0.08 * random.uniform(-1, 1)
        
        signal = 0.65 * beat + 0.25 * melody + 0.05 + noise
        signal = max(0.0, min(1.0, signal))
        
        # Berechnung der Gain-Dämpfung basierend auf der aktuellen Fader-Position
        fader_gain = self.get_db_value(self.value)
        if fader_gain < -80:
            target_db = -96.0  # Fader auf Minimum -> Lautlos
        else:
            # Pegel des Rohsignals liegt typischerweise zwischen -45 dBFS und -2 dBFS
            input_db = -45.0 + (signal * 43.0)
            target_db = input_db + fader_gain  # Signal + Dämpfung
            target_db = max(-96.0, min(6.0, target_db))
            
        # Dynamik-Filter (Fast Attack, Slow Release)
        current_db = self.meter_db
        if target_db > current_db:
            # Schnelle Reaktion auf Lautstärkespitzen (Attack)
            self.meter_db = current_db + (target_db - current_db) * 0.75
        else:
            # Langsames Abfallen des Pegels (Release)
            self.meter_db = max(-96.0, current_db - 1.8)

    # --- Touch-Gesten: Relative Steuerung & Doppelklick-Reset ---
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                # Doppelklick -> Schnappt zurück auf 0.0 dB (Unity Gain)
                zero_db_pos = 0.74
                for pos, db_val in self.db_points:
                    if abs(db_val) < 0.01:
                        zero_db_pos = pos
                        break
                self.value = zero_db_pos
                return True
            
            # Start des relativen Drags. Kivy speichert den Startpunkt,
            # um sprunghafte Wertänderungen bei der ersten Berührung zu verhindern.
            touch.grab(self)
            touch.ud['start_y'] = touch.y
            touch.ud['start_value'] = self.value
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            track_height = self.height - 100
            if track_height <= 0:
                return True
            # Delta relativ zur ersten Berührung berechnen und anwenden
            delta_y = touch.y - touch.ud['start_y']
            delta_value = delta_y / track_height
            self.value = max(0.0, min(1.0, touch.ud['start_value'] + delta_value))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)

class ModernPanner(Widget):
    """
    Ein rotierbarer Panning-Regler. Zeichnet einen dynamischen Ringbogen,
    welcher die Balance zwischen Links (L) und Rechts (R) darstellt.
    """
    pan_value = NumericProperty(0.0)      # Pan-Wert von -1.0 (Links) bis +1.0 (Rechts)
    pan_text = StringProperty("C")        # Die textuelle Repräsentation (L, R, C, 1-99)
    active_angle_start = NumericProperty(90)
    active_angle_end = NumericProperty(90)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw, pan_value=self.update_pan)
        self.redraw()

    def redraw(self, *args):
        self.update_pan()

    def update_pan(self, *args):
        """Aktualisiert die Gradzahlen des Bogens und die Beschriftung."""
        val = self.pan_value
        pct = int(round(abs(val) * 100))
        
        # Bestimme Text für das Label
        if pct == 0:
            self.pan_text = "C" # Center
        elif val < 0:
            self.pan_text = "L" if pct >= 100 else f"{pct}"
        else:
            self.pan_text = "R" if pct >= 100 else f"{pct}"

        # Bogen-Gradzahlen berechnen.
        # Da Kivy Winkel normalisiert, wird in der KV-Datei eine Rotation von 135 Grad
        # auf das Koordinatensystem angewandt, damit die Lücke immer genau unten bleibt.
        if pct == 0:
            self.active_angle_start = 134
            self.active_angle_end = 136
        elif val < 0:
            self.active_angle_start = 135 + val * 135
            self.active_angle_end = 135
        else:
            self.active_angle_start = 135
            self.active_angle_end = 135 + val * 135

    # --- Panner-Gesten ---
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if touch.is_double_tap:
                # Doppelklick -> Snap zurück in die Mitte (Center)
                self.pan_value = 0.0
                return True
            touch.grab(self)
            touch.ud['start_y'] = touch.y
            touch.ud['start_pan'] = self.pan_value
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            # Ein vertikaler Regelweg von 150 Pixeln entspricht dem vollen Regelbereich
            delta_y = touch.y - touch.ud['start_y']
            delta_pan = (delta_y / 150.0) * 2.0
            new_pan = touch.ud['start_pan'] + delta_pan
            self.pan_value = max(-1.0, min(1.0, new_pan))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)

class MixerChannelStrip(BoxLayout):
    """Der vertikale Kanalzug, welcher Panner, Fader und die Knöpfe bündelt."""
    fader_daw = StringProperty("LogicPro")

class MixerDashboard(FloatLayout):
    """Das Haupt-Dashboard der App, das Info-Panel, Kanalkonsole und Settings bündelt."""
    pass

class MixerLabApp(App):
    # App-weite Properties zur reaktiven Theme-Steuerung.
    # Änderungen an diesen Listen triggern sofort automatische Repaints in KV.
    accent_color = ListProperty([0.0, 0.67, 1.0, 1.0])
    secondary_color = ListProperty([0.48, 0.17, 0.75, 1.0])
    bg_color = ListProperty([0.05, 0.05, 0.07, 1.0])
    widget_bg_color = ListProperty([0.08, 0.08, 0.11, 1.0])
    current_theme_name = StringProperty("neon_ocean")
    
    # Theme-spezifische Pegelanzeigen-Farben
    meter_low_color = ListProperty([0.0, 0.67, 1.0, 0.85])
    meter_mid_color = ListProperty([0.2, 0.4, 0.9, 0.85])
    meter_high_color = ListProperty([0.48, 0.17, 0.75, 0.85])

    def build(self):
        # Initiales Setzen des Standard-Themes 'Neon Ocean'
        self.set_theme("neon_ocean")
        return MixerDashboard()

    def set_theme(self, theme_name):
        """Setzt die Farbvariablen der App auf das ausgewählte Theme."""
        if theme_name in THEMES:
            t = THEMES[theme_name]
            self.current_theme_name = theme_name
            self.accent_color = t["accent"]
            self.secondary_color = t["secondary"]
            self.bg_color = t["bg"]
            self.widget_bg_color = t["widget_bg"]
            self.meter_low_color = t["meter_low"]
            self.meter_mid_color = t["meter_mid"]
            self.meter_high_color = t["meter_high"]

if __name__ == '__main__':
    # Startet die Kivy Applikationsschleife
    MixerLabApp().run()