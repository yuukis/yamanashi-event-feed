import logging
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import List, Optional, Tuple

import requests

from . import config
from .models import FeedEvent

logger = logging.getLogger(__name__)

FIELDS = "uid,title,event_url,updated_at,group_name,description,catch,keywords"

# Single-entry, process-local cache. The upstream API has no filtering
# query params today, so there is only ever one thing to cache: the full
# event list. Kept as a plain dict (rather than a generic keyed cache)
# since there is nothing to key on yet.
_cache = {
    "events": None,       # List[FeedEvent] | None
    "last_modified": None,  # datetime | None (upstream's Last-Modified)
    "fetched_at": None,     # float epoch seconds | None
}


def fetch_events() -> Tuple[List[FeedEvent], Optional[datetime]]:
    """Return the full upstream event list and its Last-Modified time,
    using a short-TTL in-memory cache to avoid hitting the upstream API
    on every request."""
    now = datetime.now(timezone.utc).timestamp()

    if (_cache["events"] is not None and _cache["fetched_at"] is not None
            and now - _cache["fetched_at"] < config.CACHE_TTL_SECONDS):
        return _cache["events"], _cache["last_modified"]

    headers = {}
    if _cache["last_modified"] is not None:
        headers["If-Modified-Since"] = format_datetime(
            _cache["last_modified"].astimezone(timezone.utc), usegmt=True)

    try:
        response = requests.get(
            f"{config.UPSTREAM_API_URL}/events",
            params={"fields": FIELDS},
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as e:
        logger.warning("Failed to reach upstream API: %s", e)
        if _cache["events"] is not None:
            return _cache["events"], _cache["last_modified"]
        raise

    if response.status_code == 304:
        _cache["fetched_at"] = now
        return _cache["events"], _cache["last_modified"]

    if not response.ok:
        logger.warning("Upstream API returned status %s", response.status_code)
        if _cache["events"] is not None:
            return _cache["events"], _cache["last_modified"]
        response.raise_for_status()

    events = FeedEvent.from_json(response.json())
    last_modified = _parse_last_modified_header(response.headers.get("Last-Modified"))

    _cache["events"] = events
    _cache["last_modified"] = last_modified
    _cache["fetched_at"] = now

    return events, last_modified


def _parse_last_modified_header(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
