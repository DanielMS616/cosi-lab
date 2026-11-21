"""Stellt das gemeinsame E5-Modell für Import und Suche bereit."""

from sentence_transformers import SentenceTransformer


# Dokumente und Fragen brauchen dasselbe Modell, damit ihre Vektoren
# im selben Raum liegen und sich miteinander vergleichen lassen.
E5_MODELL = "intfloat/multilingual-e5-small"


def lade_e5_modell():
    """Lädt das gemeinsame E5-Modell für die CPU."""
    return SentenceTransformer(E5_MODELL, device="cpu")