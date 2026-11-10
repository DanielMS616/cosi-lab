import argparse

from temperature import count_above_threshold
from temperature import count_missing
from temperature_csv import read_temperatures
from temperature_prompt import build_temperature_prompt


# Der Parser beschreibt, welche Angaben das Programm beim Start erwartet.
parser = argparse.ArgumentParser(description="Zählt Temperaturüberschreitungen.")

# Der Dateipfad ist eine Pflichtangabe und steht direkt hinter main.py.
parser.add_argument("path", help="Pfad zur CSV-Datei")

# Die Schwelle ist optional. argparse wandelt die Eingabe in eine Ganzzahl um.
parser.add_argument("--threshold", type=int, default=60, help="Temperaturschwelle (Standard: 60)")

# action="store_true" macht die Option zu einem Schalter: Mit --show-temperatures ist args.show_temperatures gleich True
parser.add_argument(
    "--show-temperatures",
    action="store_true",
    help="Zeigt die eingelesenen Temperaturwerte an.",
)

parser.add_argument(
    "--show-prompt",
    action="store_true",
)

# Pro Aufruf ist höchstens ein Modell erlaubt.
model_options = parser.add_mutually_exclusive_group()
model_options.add_argument("--gpt", action="store_true", help="Erstellt einen GPT-Bericht.")
model_options.add_argument("--gemini", action="store_true", help="Erstellt einen Gemini-Bericht.")

# Lies die Terminalargumente ein und übernimm den angegebenen Dateipfad.
args = parser.parse_args()
path = args.path

# Die Schwelle kann durch ein Argument vorgegeben werden. Default = 60
threshold = args.threshold

try:
    temperatures = read_temperatures(path)
except ValueError as error:
    # Bei einem ungültigen Messwert zeigen wir nur die Meldung des CSV-Imports.
    print(error)
    raise SystemExit(1)
else:
    # Zeige bei Bedarf, welche Werte aus der CSV eingelesen wurden.
    if args.show_temperatures:
        print(temperatures)

    missing_temperatures = count_missing(temperatures)

    exceedances = count_above_threshold(temperatures, threshold)

    total_temperatures = len(temperatures)

    valid_temperatures = total_temperatures - missing_temperatures

    print(f"Messwerte insgesamt: {total_temperatures}")

    print(f"Fehlende Messwerte: {missing_temperatures}")

    print(f"Gültige Messwerte: {valid_temperatures}")

    print(f"Messwerte über {threshold} °C: {exceedances}")

    # Vorschau und GPT-Aufruf verwenden denselben fertigen Prompt.
    if args.show_prompt or args.gpt or args.gemini:
        prompt = build_temperature_prompt(
            total_count=total_temperatures,
            valid_count=valid_temperatures,
            missing_count=missing_temperatures,
            threshold=threshold,
            exceedances=exceedances,
        )

        if args.show_prompt:
            print("\nPrompt:")
            print(prompt)

        if args.gpt:
            # Lade das SDK erst, wenn der GPT-Aufruf ausdrücklich gewählt wurde.
            from model_gpt import generate_gpt_report
            from model_storage import initialize_database, save_model_run

            result = generate_gpt_report(prompt)
            report = result["text"]

            # Erst nach erfolgreicher GPT-Antwort speichere ich den Lauf.
            database_path = "data/model_runs.sqlite3"
            initialize_database(database_path)

            run_id = save_model_run(
                database_path=database_path,
                model="gpt-4o-mini",
                csv_path=args.path,
                threshold=threshold,
                prompt=prompt,
                response_text=report,
                duration_ms=result["processing_ms"],
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
            )
            print(f"Modelllauf gespeichert: ID {run_id}")

            print("\nGPT-Bericht:")
            print(report)


        elif args.gemini:
            from model_gemini import GEMINI_MODEL, generate_gemini_report
            from model_storage import initialize_database, save_model_run

            result = generate_gemini_report(prompt)
            report = result["text"]

            # Speichere den Lauf erst, wenn ein Bericht vorliegt.
            database_path = "data/model_runs.sqlite3"
            initialize_database(database_path)

            run_id = save_model_run(
                database_path=database_path,
                model=GEMINI_MODEL,
                csv_path=args.path,
                threshold=threshold,
                prompt=prompt,
                response_text=report,
                duration_ms=result["processing_ms"],
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
            )

            print(f"Modelllauf gespeichert: ID {run_id}")

            print("\nGemini-Bericht:")
            print(report)
