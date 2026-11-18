from transformers import AutoTokenizer

from doc_chunks import split_document, split_chunk_by_lines
from doc_experiment_config import EXPERIMENT_DOCS


MODEL_NAME = "intfloat/multilingual-e5-small"
MAX_INPUT_TOKENS = 512


def main():
    """Prüft die Tokenlängen vor und nach der zeilenweisen Aufteilung."""
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        local_files_only=True,
    )

    def count_tokens(text):
        # Diese Funktion zählt die vollständige spätere Modelleingabe.
        # split_chunk_by_lines() kann sie für jeden Kandidaten aufrufen.
        encoded = tokenizer(
            f"passage: {text}",
            add_special_tokens=True,
            truncation=False,
            verbose=False,
        )
        return len(encoded["input_ids"])

    total_before = 0
    total_after = 0
    too_long_after = 0
    longest_after = 0

    for path in EXPERIMENT_DOCS:
        for chunk in split_document(path):
            total_before += 1
            original_tokens = count_tokens(chunk["text"])

            # Übergib die Zählfunktion selbst, ohne sie hier aufzurufen.
            # Die Aufteilung nutzt sie zum Prüfen möglicher Teilabschnitte.
            parts = split_chunk_by_lines(
                chunk,
                count_tokens,
                max_tokens=MAX_INPUT_TOKENS,
            )

            total_after += len(parts)

            if len(parts) > 1:
                print(
                    f"\nGETEILT: {chunk['path']}:"
                    f"{chunk['start_line']}-{chunk['end_line']}"
                )
                print(
                    f"  Vorher: {original_tokens} Tokens"
                    f" | Danach: {len(parts)} Teile"
                )

            # Messe alle fertigen Teile mit demselben echten Tokenizer.
            for part in parts:
                token_count = count_tokens(part["text"])
                longest_after = max(longest_after, token_count)

                if token_count > MAX_INPUT_TOKENS:
                    too_long_after += 1

                if len(parts) > 1:
                    print(
                        f"  {part['path']}:"
                        f"{part['start_line']}-{part['end_line']}"
                        f" | {token_count} Tokens"
                    )

    print(f"\nAbschnitte vorher: {total_before}")
    print(f"Abschnitte nachher: {total_after}")
    print(f"Davon weiterhin zu lang: {too_long_after}")
    print(f"Längster Abschnitt danach: {longest_after} Tokens")


if __name__ == "__main__":
    main()