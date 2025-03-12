import json
import random
import requests
import feedparser
from datetime import datetime
from croniter import croniter
import time
import logging
from typing import Optional, Dict, List

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RSSBot:
    def __init__(self, config_file: str):
        try:
            # Carica il file di configurazione
            with open(config_file, 'r') as file:
                self.config = json.load(file)
            self.token = self.config.get('token')
            self.url_synapse = self.config.get('url_synapse')
            self.port_synapse = self.config.get('port_synapse')
            self.id_room = self.config.get('id_room')
            self.rss_feeds = self.config.get('rss', [])
            self.cron = self.config.get('cron')
            self.mute_from = self.config.get('mute', {}).get('from')
            self.mute_to = self.config.get('mute', {}).get('to')

            # Verifica che tutti i campi necessari siano presenti
            if not all([self.token, self.url_synapse, self.port_synapse, self.id_room, self.rss_feeds, self.cron, self.mute_from, self.mute_to]):
                raise ValueError("Configurazione incompleta o errata nel file JSON.")
        except FileNotFoundError:
            logger.error(f"File di configurazione '{config_file}' non trovato.")
            raise
        except json.JSONDecodeError:
            logger.error(f"Errore nel parsing del file JSON '{config_file}'. Verifica la sintassi.")
            raise
        except Exception as e:
            logger.error(f"Errore durante l'inizializzazione del bot: {e}")
            raise

    def fetch_random_article(self) -> Optional[Dict[str, str]]:
        articles = []
        for feed_url in self.rss_feeds:
            try:
                # Parsing del feed RSS
                feed = feedparser.parse(feed_url)
                if feed.bozo:  # Controlla se ci sono errori nel parsing del feed
                    logger.warning(f"Errore nel parsing del feed RSS: {feed_url}. Errore: {feed.bozo_exception}")
                    continue
                for entry in feed.entries:
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.summary if hasattr(entry, 'summary') else "Nessun sommario disponibile."
                    })
            except Exception as e:
                logger.error(f"Errore durante il fetching del feed {feed_url}: {e}")
                continue

        # Restituisce un articolo casuale se disponibile
        return random.choice(articles) if articles else None

    def send_message(self, message: str) -> bool:
        # Assicurati che l'URL includa il protocollo http://
        url_synapse = self.url_synapse
        if not url_synapse.startswith("http://") and not url_synapse.startswith("https://"):
            url_synapse = "http://" + url_synapse

        # Costruisce l'URL per l'invio del messaggio utilizzando la porta configurata
        url = f"{url_synapse}:{self.port_synapse}/_matrix/client/r0/rooms/{self.id_room}/send/m.room.message"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "msgtype": "m.text",
            "body": message
        }
        try:
            # Invia il messaggio
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()  # Solleva un'eccezione per codici di stato HTTP non riusciti
            logger.info(f"Messaggio inviato con successo: {message}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore durante l'invio del messaggio: {e}")
            return False

    def is_mute_time(self) -> bool:
        try:
            now = datetime.now().time()
            mute_from = datetime.strptime(self.mute_from, "%H:%M").time()
            mute_to = datetime.strptime(self.mute_to, "%H:%M").time()

            # Controlla se l'orario corrente è all'interno dell'intervallo di silenzio
            if mute_from < mute_to:
                return mute_from <= now <= mute_to
            else:  # Intervallo che attraversa la mezzanotte
                return now >= mute_from or now <= mute_to
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
            base_time = datetime.now()
            cron = self.cron

            while True:
                # Calcola il prossimo orario di esecuzione
                iter_cron = croniter(cron, base_time)
                next_run = iter_cron.get_next(datetime)

                sleep_time = (next_run - datetime.now()).total_seconds()
                logger.info(f"Prossima esecuzione alle {next_run}. Dormirò per {sleep_time} secondi.")

                if sleep_time > 0:
                    time.sleep(sleep_time)

                self.job()
                base_time = datetime.now()
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