"""Eigene Fehler für den Aufruf der Modellanbieter."""


class ModellschluesselFehlt(RuntimeError):
    """Der gewählte Anbieter hat keinen API-Schlüssel in der Umgebung."""
