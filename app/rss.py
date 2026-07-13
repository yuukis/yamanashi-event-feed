from datetime import datetime, timezone
from email.utils import format_datetime
from typing import List, Optional
from xml.sax.saxutils import escape

from .models import FeedEvent


def parse_iso8601(value: str) -> datetime:
    # fromisoformat() only accepts a trailing 'Z' from Python 3.11+; this app targets 3.10.
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_rfc822(dt: datetime) -> str:
    return format_datetime(dt.astimezone(timezone.utc), usegmt=True)


def build_item(event: FeedEvent) -> str:
    title = event.title
    if event.group_name:
        title = f"{title}({event.group_name})"

    description = event.description or event.catch or ""
    pub_date = format_rfc822(parse_iso8601(event.updated_at))

    parts = [
        "<item>",
        f"<title>{escape(title)}</title>",
        f"<link>{escape(event.event_url)}</link>",
        f'<guid isPermaLink="false">{escape(event.uid)}</guid>',
        f"<pubDate>{pub_date}</pubDate>",
        f"<description>{escape(description)}</description>",
    ]

    for keyword in (event.keywords or []):
        parts.append(f"<category>{escape(keyword)}</category>")

    parts.append("</item>")
    return "".join(parts)


def build_rss(
    events: List[FeedEvent],
    channel_title: str,
    channel_link: str,
    channel_description: str,
    generated_at: Optional[datetime] = None,
    language: str = "ja",
) -> str:
    # Channel metadata is parameterized (not hardcoded) so a future
    # per-community feed can reuse this with its own title/link/description.
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    items = "".join(build_item(event) for event in events)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel>"
        f"<title>{escape(channel_title)}</title>"
        f"<link>{escape(channel_link)}</link>"
        f"<description>{escape(channel_description)}</description>"
        f"<language>{escape(language)}</language>"
        f"<lastBuildDate>{format_rfc822(generated_at)}</lastBuildDate>"
        f"{items}"
        "</channel>"
        "</rss>"
    )
