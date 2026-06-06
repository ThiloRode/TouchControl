"""Smoke-Test: prueft, dass die Test-Infrastruktur das Paket aus src/ findet."""

import touchhui


def test_paket_importierbar():
    # Wenn dieser Import klappt, ist pythonpath=["src"] korrekt konfiguriert.
    assert touchhui.__version__
