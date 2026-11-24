"""Stellt das gemeinsame E5-Modell für den Import und die Suche bereit."""

# Dokumente und Fragen brauchen dasselbe Modell, damit ihre Vektoren
# im selben Raum liegen und sich miteinander vergleichen lassen.
E5_MODELL = "intfloat/multilingual-e5-small"


def lade_e5_modell():
    """Lädt das gemeinsame E5-Modell für die CPU."""
    # Wer nur E5_MODELL liest, braucht das Suchpaket noch nicht.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(E5_MODELL, device="cpu")
