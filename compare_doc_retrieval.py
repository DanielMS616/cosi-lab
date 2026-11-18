import re

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


def main():
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
            # Übernimm vollständige Abschnitte oder ihre passenden Teilstücke.
            chunks.extend(
                split_chunk_by_lines(
                    chunk,
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
        [f"query: {question}" for question in QUESTIONS],
        normalize_embeddings=True,
    )

    # Zunächst zeigen wir nur den ersten Treffer jedes Verfahrens.
    top_k = 1

    for question, question_vector in zip(
        QUESTIONS, question_vectors, strict=True
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
            for index in ranked_indices[:top_k]
        ]

        # Verwende für beide Verfahren dieselbe Darstellung.
        for title, hits in (
            ("WORTSUCHE – Anzahl Suchworttreffer", keyword_hits),
            ("EMBEDDINGS – Kosinusähnlichkeit", embedding_hits),
        ):
            print(f"\n{title}")

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
    main()