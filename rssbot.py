import json
import random
import requests
import feedparser
from datetime import datetime
from croniter import croniter
import time
import logging
from typing import Optional, Dict, List

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RSSBot:
    def __init__(self, config_file: str):
        try:
            # Load the configuration file
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

            # Check that all necessary fields are present
            if not all([self.token, self.url_synapse, self.port_synapse, self.id_room, self.rss_feeds, self.cron, self.mute_from, self.mute_to]):
                raise ValueError("Incomplete or incorrect configuration in the JSON file.")
        except FileNotFoundError:
            logger.error(f"Configuration file '{config_file}' not found.")
            raise
        except json.JSONDecodeError:
            logger.error(f"Error parsing the JSON file '{config_file}'. Check the syntax.")
            raise
        except Exception as e:
            logger.error(f"Error during bot initialization: {e}")
            raise

    def fetch_random_article(self) -> Optional[Dict[str, str]]:
        articles = []
        for feed_url in self.rss_feeds:
            try:
                # Parse the RSS feed
                feed = feedparser.parse(feed_url)
                if feed.bozo:  # Check for errors in parsing the feed
                    logger.warning(f"Error parsing the RSS feed: {feed_url}. Error: {feed.bozo_exception}")
                    continue
                for entry in feed.entries:
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.summary if hasattr(entry, 'summary') else "No summary available."
                    })
            except Exception as e:
                logger.error(f"Error fetching the feed {feed_url}: {e}")
                continue

        # Return a random article if available
        return random.choice(articles) if articles else None

    def send_message(self, message: str) -> bool:
        # Ensure the URL includes the http:// protocol
        url_synapse = self.url_synapse
        if not url_synapse.startswith("http://") and not url_synapse.startswith("https://"):
            url_synapse = "http://" + url_synapse

        # Construct the URL for sending the message using the configured port
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
            # Send the message
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()  # Raise an exception for unsuccessful HTTP status codes
            logger.info(f"Message sent successfully: {message}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending the message: {e}")
            return False

    def is_mute_time(self) -> bool:
        try:
            now = datetime.now().time()
            mute_from = datetime.strptime(self.mute_from, "%H:%M").time()
            mute_to = datetime.strptime(self.mute_to, "%H:%M").time()

            # Check if the current time is within the mute interval
            if mute_from < mute_to:
                return mute_from <= now <= mute_to
            else:  # Interval that crosses midnight
                return now >= mute_from or now <= mute_to
        except ValueError as e:
            logger.error(f"Error parsing mute times: {e}")
            return False

    def job(self):
        if not self.is_mute_time():
            article = self.fetch_random_article()
            if article:
                message = f"New article: {article['title']}\n{article['link']}"
                if not self.send_message(message):
                    logger.warning("Message sending failed.")
            else:
                logger.info("No articles found.")
        else:
            logger.info("Mute time active, no message sent.")

    def run(self):
        try:
            base_time = datetime.now()
            cron = self.cron

            while True:
                # Calculate the next execution time
                iter_cron = croniter(cron, base_time)
                next_run = iter_cron.get_next(datetime)

                sleep_time = (next_run - datetime.now()).total_seconds()
                logger.info(f"Next execution at {next_run}. Sleeping for {sleep_time} seconds.")

                if sleep_time > 0:
                    time.sleep(sleep_time)

                self.job()
                base_time = datetime.now()
        except KeyboardInterrupt:
            logger.info("Bot manually interrupted.")
        except Exception as e:
            logger.error(f"Error during bot execution: {e}")

if __name__ == "__main__":
    try:
        bot = RSSBot('/app/setting.json')
        bot.run()
    except Exception as e:
        logger.error(f"Critical error during bot startup: {e}")