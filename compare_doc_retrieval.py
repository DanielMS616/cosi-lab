import re
import argparse

from sentence_transformers import SentenceTransformer

from doc_chunks import split_document, split_chunk_by_lines
from doc_experiment_config import EXPERIMENT_DOCS
from doc_search import question_to_terms


MODEL_NAME = "intfloat/multilingual-e5-small"

QUESTIONS = (
    "Welche CPU hat Cosi-Lab?",
    "Wie viele Speicherriegel sind verbaut?",
    "Auf welchem Laufwerk liegt das Betriebssystem und wie groß ist es?",
    "Was muss ich eintippen, damit der vorgeschlagene Bericht wirklich geschrieben wird?",
    "Wie viel RAM kann ich maximal einbauen?",
)

FRESH_QUESTIONS = (
    "Welche Taste muss ich vor Ort drücken, damit der Rechner weiter startet?",
    "Über welche beiden Internetzugänge wurde der Fernzugriff von unterwegs getestet?",
    "Was passiert beim Export, wenn am Ziel schon eine Datei liegt?",
    "Wofür stehen die Ports 8001 und 8000 beim SSH-Tunnel?",
    "Welches Laufwerk ist in der Hardware-Doku mit auffälligen SMART-Werten markiert?",
    "Welchen konkreten SMART-Wert meldet die Intel-NVMe für Medienfehler?",
)

HARDWARE_EVIDENCE = {
    "Welche CPU hat Cosi-Lab?": 'CPU["Intel Core i5-8500 (6 Kerne)"]',
    "Wie viele Speicherriegel sind verbaut?": 'RAM["16 GB DDR4 (2 Module)"]',
    "Auf welchem Laufwerk liegt das Betriebssystem und wie groß ist es?": (
        'HDD["Toshiba-HDD (320 GB, Ubuntu-Systemdisk)"]'
    ),
}


def rank_keyword_chunks(chunks, question):
    """Sortiert Abschnitte nach der Anzahl unterschiedlicher Suchworttreffer."""
    terms = set(question_to_terms(question))
    ranked = []

    for index, chunk in enumerate(chunks):
        words = set(re.findall(r"\w+", chunk["text"].casefold()))
        score = len(terms & words)

        # Abschnitte ohne gemeinsames Suchwort zählen nicht als Treffer.
        if score > 0:
            ranked.append((index, score))

    # Höchster Wert zuerst. Bei Gleichstand bleibt die Reihenfolge erhalten.
    ranked.sort(key=lambda hit: hit[1], reverse=True)
    return ranked


def split_hardware_nodes(chunk):
    """Macht einzelne Einträge des Hardware-Diagramms durchsuchbar."""
    if chunk["path"] != "docs/aufbau-hardware.md":
        return [chunk]

    lines = chunk["text"].split("\n")
    if lines[0].strip() != "```mermaid":
        return [chunk]

    nodes = []
    for line_number, line in enumerate(lines, start=chunk["start_line"]):
        # Erkenne Einträge wie RAM["16 GB DDR4 (2 Module)"].
        # Verbindungen wie Board --- RAM sind keine eigenen Einträge.
        if re.fullmatch(r'[A-Za-z_]\w*\["[^"]+"\]', line.strip()):
            nodes.append(
                {
                    **chunk,
                    "start_line": line_number,
                    "end_line": line_number,
                    "text": line,
                }
            )

    return nodes or [chunk]


def show_evidence_rank(question, chunks, hits):
    """Zeigt den ersten Rang, auf dem die bekannte Belegzeile vorkommt."""
    evidence = HARDWARE_EVIDENCE.get(question)
    if evidence is None:
        return

    for rank, (index, score) in enumerate(hits, start=1):
        chunk = chunks[index]
        if (
            chunk["path"] == "docs/aufbau-hardware.md"
            and evidence in chunk["text"]
        ):
            print(
                f"Belegrang: Platz {rank} von {len(hits)} | Wert: {score}"
                f" | {chunk['path']}:{chunk['start_line']}-{chunk['end_line']}"
            )
            return

    print("Belegrang: Der bekannte Beleg ist nicht unter den Treffern.")


def main(*, hardware_nodes=False, top_k=1, evidence_ranks=False, questions=QUESTIONS):
    """Vergleicht Wortsuche und Embeddings auf denselben Textabschnitten."""
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    def count_tokens(text):
        # Zähle einschließlich Präfix und Spezialtokens, ohne Text abzuschneiden.
        encoded = model.tokenizer(
            f"passage: {text}",
            add_special_tokens=True,
            truncation=False,
            verbose=False,
        )
        return len(encoded["input_ids"])

    chunks = []

    for path in EXPERIMENT_DOCS:
        for chunk in split_document(path):
            candidates = split_hardware_nodes(chunk) if hardware_nodes else [chunk]
            for candidate in candidates:
                chunks.extend(
                    split_chunk_by_lines(
                        candidate,
                        count_tokens,
                        max_tokens=model.max_seq_length,
                    )
                )

    if not chunks:
        print("Keine Dokumentabschnitte vorhanden.")
        return

    print(f"Suchabschnitte: {len(chunks)}")
    print(f"Tokenlimit: {model.max_seq_length}")

    # Berechne die Dokumentvektoren einmal für alle Fragen.
    passage_vectors = model.encode(
        [f"passage: {chunk['text']}" for chunk in chunks],
        normalize_embeddings=True,
    )

    question_vectors = model.encode(
        [f"query: {question}" for question in questions],
        normalize_embeddings=True,
    )

    for question, question_vector in zip(
        questions, question_vectors, strict=True
    ):
        print(f"\n--- {question} ---")

        keyword_hits = rank_keyword_chunks(chunks, question)

        # Vergleiche den Fragevektor mit sämtlichen Dokumentvektoren.
        scores = passage_vectors @ question_vector
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )
        embedding_hits = [
            (index, round(float(scores[index]), 3))
            for index in ranked_indices
        ]

        # Verwende für beide Verfahren dieselbe Darstellung.
        for title, hits in (
            ("WORTSUCHE – Anzahl Suchworttreffer", keyword_hits),
            ("EMBEDDINGS – Kosinusähnlichkeit", embedding_hits),
        ):
            print(f"\n{title}")

            if evidence_ranks:
                show_evidence_rank(question, chunks, hits)

            if not hits:
                print("Kein Treffer.")
                continue

            for rank, (index, score) in enumerate(hits[:top_k], start=1):
                chunk = chunks[index]
                print(
                    f"Platz {rank}: {chunk['path']}:"
                    f"{chunk['start_line']}-{chunk['end_line']}"
                    f" | Wert: {score}"
                )
                print(chunk["text"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vergleicht zwei Dokussuchen.")
    parser.add_argument(
        "--hardware-nodes",
        action="store_true",
        help="Bewertet die Einträge des Hardware-Diagramms einzeln.",
    )
    parser.add_argument(
        "--evidence-ranks",
        action="store_true",
        help="Zeigt den Rang der bekannten CPU-, RAM- und HDD-Belege.",
    )
    parser.add_argument(
        "--fresh-questions",
        action="store_true",
        help="Verwendet den neuen Fragensatz für den Vergleich.",
    )
    parser.add_argument("--top-k", type=int, choices=(1, 3), default=1)
    args = parser.parse_args()
    main(
        hardware_nodes=args.hardware_nodes,
        evidence_ranks=args.evidence_ranks,
        questions=FRESH_QUESTIONS if args.fresh_questions else QUESTIONS,
        top_k=args.top_k,
    )