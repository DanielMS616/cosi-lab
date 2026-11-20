"""Baut den PostgreSQL-Bestand für die E5-Dokusuche neu auf."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector import Vector
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from e5_demo import lese_absaetze


PROJEKTORDNER = Path(__file__).resolve().parent
E5_MODELL = "intfloat/multilingual-e5-small"


def lade_abschnitte():
    """Liest dieselben Absätze wie die bisherige CLI."""
    abschnitte = []
    ordner = PROJEKTORDNER / "examples" / "rag"
    for datei in sorted(ordner.glob("*.md")):
        if datei.is_file():
            for abschnitt in lese_absaetze(datei):
                # Ein relativer Pfad funktioniert auch auf einem anderen Rechner.
                abschnitt["dateipfad"] = datei.relative_to(PROJEKTORDNER).as_posix()
                abschnitte.append(abschnitt)
    return abschnitte


def speichere_abschnitte(abschnitte, vektoren, passwort):
    # Ein Datensatz verbindet Absatz, Fundstelle und zugehörigen E5-Vektor.
    zeilen = []
    for abschnitt, vektor in zip(abschnitte, vektoren, strict=True):
        zeilen.append((
            abschnitt["dateipfad"], abschnitt["startzeile"], abschnitt["endzeile"],
            abschnitt["text"], Vector(vektor),
        ))

    with psycopg.connect(
        host="127.0.0.1", port=5433, dbname="cosi_rag",
        user="cosi_rag", password=passwort, connect_timeout=5,
    ) as db:
        db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(db)
        db.execute("""
            CREATE TABLE IF NOT EXISTS rag_abschnitte (
                dateipfad TEXT NOT NULL,
                startzeile INTEGER NOT NULL,
                endzeile INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding vector(384) NOT NULL,
                PRIMARY KEY (dateipfad, startzeile, endzeile)
            )
        """)

        # Löschen und Einfügen bilden eine Transaktion. Bei einem Fehler
        # macht der with-Block beide Änderungen rückgängig.
        db.execute("DELETE FROM rag_abschnitte")
        with db.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO rag_abschnitte (dateipfad, startzeile, endzeile, text, embedding)
                VALUES (%s, %s, %s, %s, %s)
            """, zeilen)


def main():
    load_dotenv(PROJEKTORDNER / ".env")
    passwort = os.getenv("RAG_POSTGRES_PASSWORD")
    if not passwort:
        raise SystemExit("RAG_POSTGRES_PASSWORD fehlt in der lokalen .env.")

    abschnitte = lade_abschnitte()
    if not abschnitte:
        raise SystemExit("Keine Absätze in examples/rag/ gefunden.")

    # Beim Import kodieren wir nur Dokumentabsätze, keine Fragen.
    modell = SentenceTransformer(E5_MODELL, device="cpu")
    passagen = [f"passage: {abschnitt['text']}" for abschnitt in abschnitte]
    vektoren = modell.encode(passagen, normalize_embeddings=True)

    speichere_abschnitte(abschnitte, vektoren, passwort)
    print(f"{len(abschnitte)} Absätze in PostgreSQL gespeichert.")


if __name__ == "__main__":
    main()
