"""Eigene Fehler für den Aufruf der Modellanbieter."""


class ModellschluesselFehlt(RuntimeError):
    """Der gewählte Anbieter hat keinen API-Schlüssel in der Umgebung."""


class ModellverbindungFehlgeschlagen(RuntimeError):
    """Der Anbieteraufruf ist an der Netzwerkverbindung gescheitert."""


class ModellzeitUeberschritten(RuntimeError):
    """Beim Anbieteraufruf wurde ein Zeitlimit überschritten."""
