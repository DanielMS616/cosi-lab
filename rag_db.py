"""PostgreSQL-Verbindung und Vektorsuche für die RAG-Dokumente."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row


def verbinde_rag_db():
    """Öffnet die lokale Datenbank für Import und Suche."""
    load_dotenv(Path(__file__).with_name(".env"))
    passwort = os.getenv("RAG_POSTGRES_PASSWORD")
    if not passwort:
        raise SystemExit("RAG_POSTGRES_PASSWORD fehlt in der lokalen .env.")

    return psycopg.connect(
        host="127.0.0.1", port=5433, dbname="cosi_rag",
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
