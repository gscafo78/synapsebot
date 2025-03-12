# Usa un'immagine di base ufficiale di Python
FROM python:3.9-slim

# Imposta la directory di lavoro
WORKDIR /app

# Copia i file requirements.txt nella directory di lavoro
COPY ../requirements.txt .

# Installa le dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto del codice dell'applicazione nella directory di lavoro
COPY ../setting_example.json .
COPY ../rssbot_stable.py ./main.py

# Specifica il comando per eseguire l'applicazione
CMD ["python", "main.py"]