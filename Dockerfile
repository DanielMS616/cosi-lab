FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY temperature*.py show_temperature_run.py model_gpt.py model_gemini.py modell_fehler.py ./
COPY examples/ ./examples/

USER 10001:10001

# Ohne weiteren Befehl wertet der Container die Beispiel-CSV aus.
CMD ["python", "temperature_cli.py", "examples/temperature_sample.csv"]
