"""State-Modell von TouchControl.

Enthaelt die Datenklassen, die den aktuellen Mixer-Zustand speichern.
Das Modell ist bewusst Kivy-frei und vollstaendig mit pytest testbar.
"""

from .channel_state import ChannelState
from .mixer_state import MixerState

__all__ = ["ChannelState", "MixerState"]
