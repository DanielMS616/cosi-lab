"""Stellt das gemeinsame E5-Modell für den Import und die Suche bereit."""

from threading import Lock


# Dokumente und Fragen brauchen dasselbe Modell, damit ihre Vektoren
# im selben Raum liegen und sich miteinander vergleichen lassen.
E5_MODELL = "intfloat/multilingual-e5-small"

# Nach dem ersten Laden bleibt das Modell in diesem Python-Prozess verfügbar.
_e5_modell = None
_ladesperre = Lock()


def lade_e5_modell():
    """Lädt E5 beim ersten Zugriff und gibt danach dasselbe Modell zurück."""
    global _e5_modell

    # Wenn zwei Anfragen gleichzeitig kommen, darf nur eine das Modell laden.
    with _ladesperre:
        if _e5_modell is None:
            # Wer nur E5_MODELL liest, braucht das Suchpaket noch nicht.
            from sentence_transformers import SentenceTransformer

            _e5_modell = SentenceTransformer(E5_MODELL, device="cpu")

        return _e5_modell
