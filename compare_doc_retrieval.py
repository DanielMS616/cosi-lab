from pathlib import Path

from sentence_transformers import SentenceTransformer

from doc_search import PROJECT_DOCS


QUESTIONS = (
    "Welche CPU hat Cosi-Lab?",
    "Wie viele Speicherriegel sind verbaut?",
    "Auf welchem Laufwerk liegt das Betriebssystem und wie groß ist es?",
    "Was muss ich eintippen, damit der vorgeschlagene Bericht wirklich geschrieben wird?",
    "Wie viel RAM kann ich maximal einbauen?",
)


def collect_excerpts(paths):
    """Baut dieselben Textfenster wie die Wortsuche."""
    excerpts = []
    for path in paths:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        for end_line in range(1, len(lines) + 1):
            start_line = max(1, end_line - 2)
            text = "\n".join(lines[start_line - 1 : end_line])
            excerpts.append((path, start_line, end_line, text))
    return excerpts


def main():
    excerpts = collect_excerpts(PROJECT_DOCS)
    model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")

    # Dokumentausschnitte nur einmal berechnen und für alle Fragen verwenden.
    passage_vectors = model.encode(
        [f"passage: {text}" for _, _, _, text in excerpts],
        normalize_embeddings=True,
    )
    question_vectors = model.encode(
        [f"query: {question}" for question in QUESTIONS],
        normalize_embeddings=True,
    )

    for question, question_vector in zip(QUESTIONS, question_vectors, strict=True):
        # Berechne für jeden Ausschnitt seine Ähnlichkeit mit dieser Frage.
        scores = passage_vectors @ question_vector

        # Sortiere die Positionen der Ausschnitte nach ihrem Ähnlichkeitswert.
        # reverse=True bedeutet: Der höchste Wert steht zuerst.
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        print(f"\n--- {question} ---")

        # Zeige die ersten drei Positionen der sortierten Liste.
        # enumerate nummeriert die Treffer für die Ausgabe ab 1.
        for rank, index in enumerate(ranked_indices[:3], start=1):
            path, start, end, text = excerpts[index]

            print(
                f"\nPlatz {rank}: {path}:{start}-{end}"
                f" | Ähnlichkeit: {scores[index]:.3f}"
            )
            print(text)


if __name__ == "__main__":
    main()