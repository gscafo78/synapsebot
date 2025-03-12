# RSS to Element Bot

This project is a bot that reads articles from RSS feeds and sends them to a Synapse (Element) room.

## Project Structure

The project structure is as follows:

```
synapsebot/
    .env
    .gitignore
    LICENSE
    requirements.txt
    rssbot_stable.py
    setting_example.json
    build/
```

## Configuration

1. Copy the `setting_example.json` file and rename it to `settings.json`.
2. Edit `settings.json` with your settings:

```json
{
    "token": "YOUR_ACCESS_TOKEN",
    "url_synapse": "YOUR_SYNAPSE_URL",
    "port_synapse": "YOUR_SYNAPSE_PORT",
    "id_room": "YOUR_ROOM_ID",
    "rss": [
        "https://example.com/rss"
    ],
    "cron": "0 * * * *",
    "mute": {
        "from": "22:00",
        "to": "06:00"
    }
}
```

## Installation

Make sure you have Python 3.7+ installed. Then, install the dependencies:

```sh
pip install -r requirements.txt
```

## Running

To run the bot in stable mode:

```sh
python rssbot_stable.py
```

To run the bot in development mode:

```sh
python rssbot_dev.py
```

## Features

- Reads articles from configured RSS feeds.
- Sends articles to a Synapse (Element) room.
- Supports configuring a mute time interval.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contributing

Contributions are welcome! Feel free to open issues or pull requests.

## Contact

For any questions, you can contact the project maintainer.