import json
import random
import feedparser
from datetime import datetime
from croniter import croniter
import time
import logging
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, ValidationError
import asyncio
import aiohttp
import signal

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ConfigModel(BaseModel):
    url_synapse: str  # No longer HttpUrl, accepts any string
    port_synapse: int
    id_room: str
    rss: List[str]  # No longer HttpUrl, accepts any string
    cron: str
    mute: Dict[str, str]

class RSSBot:
    def __init__(self, config_file: str):
        self.config_file = config_file  # Store the configuration file path
        try:
            # Load the configuration file
            with open(config_file, 'r') as file:
                config_data = json.load(file)
            
            # Validate configuration (excluding the token from validation)
            self.config = ConfigModel(**{k: v for k, v in config_data.items() if k != 'token'})
            self.url_synapse = self.config.url_synapse
            self.port_synapse = self.config.port_synapse
            self.id_room = self.config.id_room
            self.rss_feeds = self.config.rss
            self.cron = self.config.cron
            self.mute_from = self.config.mute.get('from')
            self.mute_to = self.config.mute.get('to')

        except FileNotFoundError:
            logger.error(f"Configuration file '{config_file}' not found.")
            raise
        except json.JSONDecodeError:
            logger.error(f"Error parsing the JSON file '{config_file}'. Check the syntax.")
            raise
        except ValidationError as e:
            logger.error(f"Configuration validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during bot initialization: {e}")
            raise

    def _read_token(self) -> Optional[str]:
        """Reads the token from the JSON file."""
        try:
            with open(self.config_file, 'r') as file:
                config_data = json.load(file)
                return config_data.get('token')
        except Exception as e:
            logger.error(f"Error reading token from config file: {e}")
            return None

    async def fetch_random_article(self) -> Optional[Dict[str, str]]:
        articles = []
        async with aiohttp.ClientSession() as session:
            for feed_url in self.rss_feeds:
                try:
                    async with session.get(feed_url) as response:
                        if response.status == 200:
                            feed = feedparser.parse(await response.text())
                            if feed.bozo:
                                logger.warning(f"Error parsing the RSS feed: {feed_url}. Error: {feed.bozo_exception}")
                                continue
                            for entry in feed.entries:
                                articles.append({
                                    'title': entry.title,
                                    'link': entry.link,
                                    'summary': entry.summary if hasattr(entry, 'summary') else "No summary available."
                                })
                        else:
                            logger.warning(f"Failed to fetch {feed_url}: {response.status}")
                except Exception as e:
                    logger.error(f"Error fetching the feed {feed_url}: {e}")
                    continue

        return random.choice(articles) if articles else None

    async def send_message(self, message: str) -> bool:
        # Read the token from the JSON file
        token = self._read_token()
        if not token:
            logger.error("Token not found in config file.")
            return False

        # Explicitly construct the HTTP URL
        url = f"http://{self.url_synapse}:{self.port_synapse}/_matrix/client/r0/rooms/{self.id_room}/send/m.room.message"
        headers = {
            "Authorization": f"Bearer {token}",  # Use the token read from the file
            "Content-Type": "application/json"
        }
        data = {
            "msgtype": "m.text",
            "body": message
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    logger.info(f"Message sent successfully: {message}")
                    return True
        except aiohttp.ClientError as e:
            logger.error(f"Error sending the message: {e}")
            return False

    async def mark_message_as_read(self, event_id: str) -> bool:
        """Marks a message as read."""
        token = self._read_token()
        if not token:
            logger.error("Token not found in config file.")
            return False

        # Construct the URL to mark the message as read
        url = f"http://{self.url_synapse}:{self.port_synapse}/_matrix/client/r0/rooms/{self.id_room}/receipt/m.read/{event_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        # Request body
        data = {
            "m.read": {
                "event_id": event_id
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    logger.info(f"Message {event_id} marked as read.")
                    return True
        except aiohttp.ClientError as e:
            logger.error(f"Error marking message as read: {e}")
            return False

    async def listen_for_events(self):
        """Listens for events in the room and handles messages and user entries."""
        token = self._read_token()
        if not token:
            logger.error("Token not found in config file.")
            return

        # URL for the /sync request
        url = f"http://{self.url_synapse}:{self.port_synapse}/_matrix/client/r0/sync"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        filter = json.dumps({
            "room": {
                "timeline": {
                    "limit": 10
                }
            }
        })
        params = {
            "filter": filter  # The value must be a valid JSON string
        }

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        response.raise_for_status()
                        data = await response.json()

                        # Update the since token for the next request
                        next_batch = data.get("next_batch")
                        if next_batch:
                            params["since"] = next_batch

                        # Handle room events
                        if "rooms" in data and "join" in data["rooms"]:
                            room_events = data["rooms"]["join"].get(self.id_room, {}).get("timeline", {}).get("events", [])
                            for event in room_events:
                                if event["type"] == "m.room.message":
                                    # Mark the message as read
                                    await self.mark_message_as_read(event["event_id"])
                                elif event["type"] == "m.room.member" and event["content"]["membership"] == "join":
                                    # Send a welcome message
                                    user_id = event["state_key"]
                                    welcome_message = f"Welcome to the room, {user_id}!"
                                    await self.send_message(welcome_message)

            except aiohttp.ClientError as e:
                logger.error(f"Error listening for events: {e}")
                await asyncio.sleep(10)  # Wait 10 seconds before retrying
                
                        
    def is_mute_time(self) -> bool:
        try:
            now = datetime.now().time()
            mute_from = datetime.strptime(self.mute_from, "%H:%M").time()
            mute_to = datetime.strptime(self.mute_to, "%H:%M").time()

            if mute_from < mute_to:
                return mute_from <= now <= mute_to
            else:
                return now >= mute_from or now <= mute_to
        except ValueError as e:
            logger.error(f"Error parsing mute times: {e}")
            return False

    async def job(self):
        if not self.is_mute_time():
            article = await self.fetch_random_article()
            if article:
                message = f"New article: {article['title']}\n{article['link']}"
                if not await self.send_message(message):
                    logger.warning("Message sending failed.")
            else:
                logger.info("No articles found.")
        else:
            logger.info("Mute time active, no message sent.")

    async def run(self):
        try:
            base_time = datetime.now()
            cron = self.cron

            # Start the listener for room events
            task_listen = asyncio.create_task(self.listen_for_events())

            while True:
                iter_cron = croniter(cron, base_time)
                next_run = iter_cron.get_next(datetime)

                sleep_time = (next_run - datetime.now()).total_seconds()
                logger.info(f"Next execution at {next_run}. Sleeping for {sleep_time} seconds.")

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                await self.job()
                base_time = datetime.now()
        except KeyboardInterrupt:
            logger.info("Bot manually interrupted. Cleaning up...")
        except Exception as e:
            logger.error(f"Unexpected error during bot execution: {e}")
        finally:
            logger.info("Cancelling all running tasks...")
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            [task.cancel() for task in tasks]  # Cancel all running tasks

            logger.info("Bot stopped.")



def handle_sigint(signal, frame):
    logger.info("SIGINT received, shutting down gracefully.")
    raise KeyboardInterrupt  # Do not raise CancelledError

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    try:
        bot = RSSBot('./settings.json')
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot terminated by user.")
    except Exception as e:
        logger.error(f"Critical error during bot startup: {e}")
