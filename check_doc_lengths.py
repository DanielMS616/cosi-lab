from transformers import AutoTokenizer

from doc_chunks import split_document
from doc_search import PROJECT_DOCS


MODEL_NAME = "intfloat/multilingual-e5-small"
MAX_INPUT_TOKENS = 512


def main():
    """Prüft die vollständige Tokenlänge der vorbereiteten Abschnitte."""
    # Verwende den bereits heruntergeladenen Tokenizer.
    # Die Modellgewichte werden zum Zählen nicht benötigt.
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        local_files_only=True,
    )

    total = 0
    too_long = 0
    longest = 0

    for path in PROJECT_DOCS:
        for chunk in split_document(path):
            # Messe denselben Text, den wir später einbetten möchten.
            # Die separat gespeicherte Überschrift fügen wir hier nicht hinzu.
            input_text = f"passage: {chunk['text']}"

            encoded = tokenizer(
                input_text,
                add_special_tokens=True,
                truncation=False,
                # Überlängen melden wir unten selbst.
                verbose=False,
            )

            # input_ids enthält eine Token-ID pro Token.
            # Die Länge dieser Liste ist die gesuchte Tokenzahl.
            token_count = len(encoded["input_ids"])

            total += 1
            longest = max(longest, token_count)

            if token_count > MAX_INPUT_TOKENS:
                too_long += 1

                print(
                    f"ZU LANG: {chunk['path']}:"
                    f"{chunk['start_line']}-{chunk['end_line']}"
                )
                print(
                    f"  {token_count} Tokens"
                    f" bei einem Limit von {MAX_INPUT_TOKENS}"
                )
                print(
                    "  Überschrift:",
                    chunk["heading"] or "(ohne Überschrift)",
                )

    print(f"\nGeprüfte Abschnitte: {total}")
    print(f"Davon zu lang: {too_long}")
    print(f"Längster Abschnitt: {longest} Tokens")


if __name__ == "__main__":
    main()