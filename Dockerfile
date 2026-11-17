# Verwende dieselbe Python-Hauptversion wie auf Cosi-Lab.
FROM python:3.14-slim

WORKDIR /app

# Installiere zuerst die Abhängigkeiten. Bei reinen Codeänderungen
# kann Docker diesen Schritt beim nächsten Build wiederverwenden.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Kopiere den Python-Code, die Projektquellen und die Weboberfläche.
COPY *.py ./
COPY docs/ ./docs/
COPY web/ ./web/

# Uvicorn läuft im Container ohne Root-Rechte.
USER 10001:10001

# Docker muss Uvicorn über die Netzwerkschnittstelle des Containers erreichen.
CMD ["python", "-m", "uvicorn", "doc_api:app", "--host", "0.0.0.0", "--port", "8000"]
