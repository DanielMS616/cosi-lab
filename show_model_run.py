import argparse
import sqlite3

from model_storage import load_model_run


def main():
    parser = argparse.ArgumentParser(description="Zeigt einen gespeicherten Modelllauf an.")
    parser.add_argument("run_id", type=int, help="ID des Modelllaufs")
    parser.add_argument(
        "--database",
        default="data/model_runs.sqlite3",
        help="Pfad zur SQLite-Datei (Standard: %(default)s)",
    )
    args = parser.parse_args()

    try:
        run = load_model_run(args.database, args.run_id)
    except sqlite3.Error as error:
        parser.exit(1, f"Datenbank konnte nicht gelesen werden: {error}\n")
    if run is None:
        parser.exit(1, f"Kein Modelllauf mit ID {args.run_id} gefunden.\n")

    print(f"Modelllauf {run['id']} · {run['model']}")
    print(f"CSV-Datei: {run['csv_path']}")
    print(f"Schwelle: {run['threshold']} °C")

    # NULL wird zu None. Null Token oder null Millisekunden bleiben als 0 sichtbar.
    for key, label, unit in (
        ("requested_at_utc", "Aufrufzeitpunkt (UTC)", ""),
        ("duration_ms", "Vom Anbieter gemeldete Verarbeitungszeit", " ms"),
        ("client_duration_ms", "Lokal gemessene Laufzeit", " ms"),
        ("input_tokens", "Eingabetoken", ""),
        ("output_tokens", "Ausgabetoken", ""),
    ):
        value = run[key]
        display = "nicht erfasst" if value is None else f"{value}{unit}"
        print(f"{label}: {display}")

    print("\nPrompt:")
    print(run["prompt"])
    print("\nAntwort:")
    print(run["response_text"])


if __name__ == "__main__":
    main()
