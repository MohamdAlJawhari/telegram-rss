from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator


BASE_URL = "https://t.me/s/"
OUTPUT_DIRECTORY = Path("feeds")
CHANNELS_FILE = Path("channels.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TelegramRSS/1.0; "
        "+https://github.com/yourusername/telegram-rss)"
    )
}


def load_channels() -> list[str]:
    if not CHANNELS_FILE.exists():
        raise FileNotFoundError("channels.txt was not found")

    channels = []

    for line in CHANNELS_FILE.read_text(encoding="utf-8").splitlines():
        channel = line.strip().removeprefix("@")

        if channel and not channel.startswith("#"):
            channels.append(channel)

    return channels


def fetch_channel(channel: str) -> str:
    url = f"{BASE_URL}{channel}"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    return response.text


def extract_posts(channel: str, page_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    posts: list[dict[str, str]] = []

    for wrapper in soup.select(".tgme_widget_message_wrap"):
        message = wrapper.select_one(".tgme_widget_message")
        if message is None:
            continue

        data_post = message.get("data-post")
        if not data_post:
            continue

        text_element = message.select_one(".tgme_widget_message_text")
        time_element = message.select_one("time")
        link_element = message.select_one(".tgme_widget_message_date")

        text = (
            text_element.get_text("\n", strip=True)
            if text_element
            else "[Media post]"
        )

        post_url = (
            urljoin("https://t.me", link_element.get("href"))
            if link_element and link_element.get("href")
            else f"https://t.me/{data_post}"
        )

        published_at = (
            time_element.get("datetime")
            if time_element
            else datetime.now(timezone.utc).isoformat()
        )

        posts.append(
            {
                "id": data_post,
                "text": text,
                "url": post_url,
                "published_at": published_at,
            }
        )

    return posts


def create_feed(channel: str, posts: list[dict[str, str]]) -> None:
    feed = FeedGenerator()

    feed.id(f"https://t.me/{channel}")
    feed.title(f"Telegram: @{channel}")
    feed.link(
        href=f"https://t.me/s/{channel}",
        rel="alternate",
    )
    feed.description(f"Public posts from Telegram channel @{channel}")
    feed.language("en")

    for post in reversed(posts):
        entry = feed.add_entry()

        entry.id(post["url"])
        entry.title(post["text"][:100] or "Telegram post")
        entry.link(href=post["url"])
        entry.description(
            f"<p>{html.escape(post['text']).replace(chr(10), '<br>')}</p>"
        )
        entry.published(post["published_at"])

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIRECTORY / f"{channel}.xml"
    feed.rss_file(str(output_file), pretty=True)

    print(f"Created {output_file} with {len(posts)} posts")


def main() -> None:
    for channel in load_channels():
        try:
            page_html = fetch_channel(channel)
            posts = extract_posts(channel, page_html)
            create_feed(channel, posts)
        except requests.RequestException as error:
            print(f"Failed to download @{channel}: {error}")
        except Exception as error:
            print(f"Failed to process @{channel}: {error}")


if __name__ == "__main__":
    main()