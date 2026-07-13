from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import List, Optional

from fastapi import Header
from fastapi.responses import Response

from . import config, upstream
from .models import FeedEvent
from .rss import build_rss, parse_iso8601

from .main import app

RSS_MEDIA_TYPE = "application/rss+xml; charset=utf-8"

CHANNEL_TITLE = "Yamanashi Developer Hub - 新着・更新イベント"
CHANNEL_LINK = config.HUB_BASE_URL
CHANNEL_DESCRIPTION = (
    "山梨県内のIT勉強会・イベントの新着・更新情報を配信するフィードです。"
)


def format_last_modified(dt: datetime) -> str:
    return format_datetime(dt.astimezone(timezone.utc), usegmt=True)


def is_not_modified(if_modified_since: Optional[str],
                    last_modified: Optional[datetime]) -> bool:
    if last_modified is None or if_modified_since is None:
        return False
    try:
        since = parsedate_to_datetime(if_modified_since)
    except (TypeError, ValueError):
        return False
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return last_modified.replace(microsecond=0) <= since


def latest_updated_at(events: List[FeedEvent]) -> Optional[datetime]:
    if not events:
        return None
    return max(parse_iso8601(event.updated_at) for event in events)


def build_feed_response(
    if_modified_since: Optional[str],
    events: List[FeedEvent],
    channel_title: str = CHANNEL_TITLE,
    channel_link: str = CHANNEL_LINK,
    channel_description: str = CHANNEL_DESCRIPTION,
) -> Response:
    """Sort/truncate `events` and render them as an RSS document, honoring
    conditional GET. This is the shared pipeline for any feed variant: the
    top-level feed today, and potentially per-community feeds later, which
    would just pre-filter `events` and pass a different channel title."""
    top_events = sorted(events, key=lambda e: e.updated_at, reverse=True)[:config.MAX_ITEMS]

    last_modified = latest_updated_at(top_events)
    headers = {}
    if last_modified is not None:
        headers["Last-Modified"] = format_last_modified(last_modified)

    if is_not_modified(if_modified_since, last_modified):
        return Response(status_code=304, headers=headers)

    xml = build_rss(top_events, channel_title, channel_link, channel_description)
    return Response(content=xml, media_type=RSS_MEDIA_TYPE, headers=headers)


@app.get("/feed.xml", include_in_schema=False)
def get_feed(if_modified_since: str = Header(None)):
    events, _ = upstream.fetch_events()
    return build_feed_response(if_modified_since, events)


@app.get("/", include_in_schema=False)
def get_feed_root(if_modified_since: str = Header(None)):
    return get_feed(if_modified_since)
