import json
import random
import requests
import feedparser
import time
import logging
import os
from datetime import datetime
from croniter import croniter
from typing import Optional, Dict, List
from pydantic import BaseModel, HttpUrl, conint
import pytz
from html import escape

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Config(BaseModel):
    token: str
    url_synapse: HttpUrl
    port_synapse: conint(ge=1, le=65535)
    id_room: str
    rss: List[HttpUrl]
    cron: str
    mute: Dict[str, str]

class RSSBot:
    def __init__(self, config_file: str):
        try:
            with open(config_file, 'r') as file:
                raw_config = json.load(file)
            self.config = Config(**raw_config)

            self.token = os.getenv("BOT_TOKEN", self.config.token)
            self.last_sent_time = None
            self.tz = pytz.timezone("Europe/Rome")
        except Exception as e:
            logger.error(f"Errore nella validazione del file JSON: {e}")
            raise

    def fetch_random_article(self) -> Optional[Dict[str, str]]:
        articles = []
        for feed_url in self.config.rss:
            try:
                feed = feedparser.parse(str(feed_url))
                if feed.bozo:
                    logger.warning(f"Errore nel parsing del feed RSS: {feed_url}. Errore: {feed.bozo_exception}")
                    continue
                for entry in feed.entries:
                    articles.append({
                        'title': escape(entry.title),
                        'link': escape(entry.link),
                        'summary': escape(entry.summary if hasattr(entry, 'summary') else "Nessun sommario disponibile.")
                    })
            except Exception as e:
                logger.error(f"Errore durante il fetching del feed {feed_url}: {e}")
                continue
        return random.choice(articles) if articles else None

    def send_message(self, message: str) -> bool:
        # Controlla se è passato abbastanza tempo dall'ultimo invio
        if self.last_sent_time and (time.time() - self.last_sent_time) < 60:
            logger.warning("Rate limit attivo: messaggio non inviato.")
            return False

        # Assicurati che l'URL includa il protocollo http://
        url_synapse = self.config.url_synapse
        if not url_synapse.startswith("http://") and not url_synapse.startswith("https://"):
            url_synapse = "http://" + url_synapse

        # Costruisce l'URL per l'invio del messaggio utilizzando la porta configurata
        url = f"{url_synapse}:{self.config.port_synapse}/_matrix/client/r0/rooms/{self.config.id_room}/send/m.room.message"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {"msgtype": "m.text", "body": message}
        try:
            # Invia la richiesta POST per inviare il messaggio
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()  # Solleva un'eccezione per codici di stato HTTP non riusciti
            logger.info(f"Messaggio inviato con successo: {message}")
            self.last_sent_time = time.time()  # Aggiorna l'ultimo tempo di invio
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore durante l'invio del messaggio: {e}")
            return False

    def is_mute_time(self) -> bool:
        try:
            now = datetime.now(self.tz).time()
            mute_from = datetime.strptime(self.config.mute['from'], "%H:%M").time()
            mute_to = datetime.strptime(self.config.mute['to'], "%H:%M").time()
            return (mute_from < mute_to and mute_from <= now <= mute_to) or (mute_from > mute_to and (now >= mute_from or now <= mute_to))
        except ValueError as e:
            logger.error(f"Errore nel parsing degli orari di mute: {e}")
            return False

    def job(self):
        if not self.is_mute_time():
            article = self.fetch_random_article()
            if article:
                message = f"Nuovo articolo: {article['title']}\n{article['link']}"
                if not self.send_message(message):
                    logger.warning("Invio del messaggio fallito.")
            else:
                logger.info("Nessun articolo trovato.")
        else:
            logger.info("Tempo di silenzio attivo, nessun messaggio inviato.")

    def run(self):
        try:
            base_time = datetime.now(self.tz)
            iter_cron = croniter(self.config.cron, base_time)
            while True:
                next_run = iter_cron.get_next(datetime)
                sleep_time = (next_run - datetime.now(self.tz)).total_seconds()
                logger.info(f"Prossima esecuzione alle {next_run}. Dormirò per {sleep_time} secondi.")
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.job()
        except KeyboardInterrupt:
            logger.info("Bot interrotto manualmente.")
        except Exception as e:
            logger.error(f"Errore durante l'esecuzione del bot: {e}")

if __name__ == "__main__":
    try:
        bot = RSSBot('/opt/rsstoelement/setting.json')
        bot.run()
    except Exception as e:
        logger.error(f"Errore critico durante l'avvio del bot: {e}")