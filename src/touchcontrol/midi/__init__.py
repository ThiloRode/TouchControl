"""MIDI-Transportschicht von TouchControl.

Enthaelt ``MidiBackend`` - die duenne Huelle um ``python-rtmidi``.
"""

from .backend import MidiBackend

__all__ = ["MidiBackend"]
