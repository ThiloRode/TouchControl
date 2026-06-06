"""Smoke-Test: prueft, dass die Test-Infrastruktur das Paket aus src/ findet."""

import touchcontrol


def test_paket_importierbar():
    # Wenn dieser Import klappt, ist pythonpath=["src"] korrekt konfiguriert.
    assert touchcontrol.__version__
