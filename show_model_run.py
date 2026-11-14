import argparse
import sqlite3

from pathlib import Path
from model_storage import load_model_run


def main():
    parser = argparse.ArgumentParser(description="Zeigt einen gespeicherten Modelllauf an.")
    parser.add_argument("run_id", type=int, help="ID des Modelllaufs")
    parser.add_argument(
        "--database",
        default="data/model_runs.sqlite3",
        help="Pfad zur SQLite-Datei (Standard: %(default)s)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Zeigt das Ziel für den Berichtsexport an.",
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

    # Path("reports") / ... setzt Ordner und Dateinamen zusammen.
    # Die Lauf-ID macht den Namen eindeutig: Für Lauf 12 ergibt sich reports/model-run-12.txt
    if args.export:
        target = Path("reports") / f"model-run-{run['id']}.txt"
        print(f"\nVorgesehenes Exportziel: {target}")

        answer = input("Bericht exportieren? [ja/nein]: ").strip().lower()

        if answer != "ja":
            print("Export abgelehnt.")
            return

        try:
            # Lege den Ordner erst nach der Freigabe an.
            target.parent.mkdir(exist_ok=True)

            # "x" erstellt eine neue Datei und schützt eine vorhandene Datei.
            with target.open("x", encoding="utf-8", newline="") as file:
                file.write(run["response_text"])
        except FileExistsError:
            parser.exit(1, f"Export abgebrochen: Ziel bereits belegt: {target}\n")
            # Zieldatei existiert bereits / reports existiert als Datei statt als Ordner

        print(f"Bericht exportiert: {target}")


if __name__ == "__main__":
    main()
