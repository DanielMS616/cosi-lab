"""PostgreSQL-Verbindung und Vektorsuche für die RAG-Dokumente."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row


# Jeder Bestand verbindet einen Dokumentordner mit genau einer Datenbank.
RAG_BESTAENDE = {
    "beispiele": ("examples/rag", "cosi_rag"),
    "praxis": ("examples/rag-praxis", "cosi_rag_praxis"),
}


def lade_rag_bestand():
    """Gibt Dokumentordner und Datenbankname für den gewählten Bestand zurück."""
    load_dotenv(Path(__file__).with_name(".env"))
    name = os.getenv("RAG_BESTAND", "beispiele")

    # Bei einem Tippfehler breche ab. Der Import soll dann nichts ersetzen.
    if name not in RAG_BESTAENDE:
        raise SystemExit(f"Unbekannter RAG_BESTAND: {name!r}. Erlaubt: beispiele, praxis.")

    return RAG_BESTAENDE[name]


def verbinde_rag_db():
    """Öffnet die lokale Datenbank für Import und Suche."""

    # Der Unterstrich steht für den Ordner, den die Verbindung hier nicht braucht.
    _, datenbankname = lade_rag_bestand()
    passwort = os.getenv("RAG_POSTGRES_PASSWORD")
    if not passwort:
        raise SystemExit("RAG_POSTGRES_PASSWORD fehlt in der lokalen .env.")

    return psycopg.connect(
        host="127.0.0.1", port=5433, dbname=datenbankname,
        user="cosi_rag", password=passwort, connect_timeout=5,
    )


def suche_abschnitte(fragevektor, top_k):
    """Liefert die nach Kosinusabstand sortierten Absätze."""
    with verbinde_rag_db() as db:
        register_vector(db)
        with db.cursor(row_factory=dict_row) as cursor:
            # Kleinerer Abstand steht zuerst. Als Wert zeigen wir 1 - Abstand.
            # Bei top_k=None erhält LIMIT den SQL-Wert NULL: kein Limit.
            cursor.execute("""
                SELECT dateipfad AS datei, startzeile, endzeile, text,
                       1 - (embedding <=> %(fragevektor)s) AS wert
                FROM public.rag_abschnitte
                ORDER BY embedding <=> %(fragevektor)s, dateipfad, startzeile, endzeile
                LIMIT %(top_k)s
            """, {"fragevektor": Vector(fragevektor), "top_k": top_k})
            return cursor.fetchall()
