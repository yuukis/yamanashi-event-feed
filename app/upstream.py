import logging
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from . import config
from .models import FeedEvent, GroupInfo

logger = logging.getLogger(__name__)

FIELDS = "uid,title,event_url,updated_at,group_name,description,catch,keywords"
GROUP_FIELDS = "key,title,url,description"

# Upstream's hard per_page ceiling for /groups/{key}/events; also used to
# bound how many candidates we pull before build_feed_response() re-sorts
# by updated_at and truncates to MAX_ITEMS.
GROUP_EVENTS_PAGE_SIZE_LIMIT = 200

_cache = {
    "events": None,
    "last_modified": None,
    "fetched_at": None,
}


class GroupNotFoundError(Exception):
    def __init__(self, group_key: str):
        self.group_key = group_key
        super().__init__(f"Group '{group_key}' not found")


def fetch_events() -> Tuple[List[FeedEvent], Optional[datetime]]:
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


_group_meta_caches: Dict[str, dict] = {}
_group_event_caches: Dict[str, dict] = {}


def _new_cache() -> dict:
    return {"data": None, "last_modified": None, "fetched_at": None}


def _fetch_group_resource(url: str, params: dict, cache: dict, group_key: str,
                          parse: Callable[[Any], Any]):
    now = datetime.now(timezone.utc).timestamp()

    if (cache["data"] is not None and cache["fetched_at"] is not None
            and now - cache["fetched_at"] < config.CACHE_TTL_SECONDS):
        return cache["data"], cache["last_modified"]

    headers = {}
    if cache["last_modified"] is not None:
        headers["If-Modified-Since"] = format_datetime(
            cache["last_modified"].astimezone(timezone.utc), usegmt=True)

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
    except requests.RequestException as e:
        logger.warning("Failed to reach upstream API: %s", e)
        if cache["data"] is not None:
            return cache["data"], cache["last_modified"]
        raise

    if response.status_code == 304:
        cache["fetched_at"] = now
        return cache["data"], cache["last_modified"]

    if response.status_code == 404:
        raise GroupNotFoundError(group_key)

    if not response.ok:
        logger.warning("Upstream API returned status %s", response.status_code)
        if cache["data"] is not None:
            return cache["data"], cache["last_modified"]
        response.raise_for_status()

    data = parse(response.json())
    last_modified = _parse_last_modified_header(response.headers.get("Last-Modified"))

    cache["data"] = data
    cache["last_modified"] = last_modified
    cache["fetched_at"] = now

    return data, last_modified


def fetch_group(group_key: str) -> Tuple[GroupInfo, Optional[datetime]]:
    cache = _group_meta_caches.setdefault(group_key, _new_cache())
    return _fetch_group_resource(
        f"{config.UPSTREAM_API_URL}/groups/{group_key}",
        {"fields": GROUP_FIELDS}, cache, group_key, GroupInfo.from_json)


def fetch_group_events(group_key: str) -> Tuple[List[FeedEvent], Optional[datetime]]:
    cache = _group_event_caches.setdefault(group_key, _new_cache())
    # Fetch at least MAX_ITEMS candidates (capped at upstream's own limit)
    # so build_feed_response()'s updated_at re-sort has a reasonable pool
    # to pick the true top MAX_ITEMS from -- upstream only sorts by
    # started_at, not updated_at.
    per_page = min(config.MAX_ITEMS, GROUP_EVENTS_PAGE_SIZE_LIMIT)
    return _fetch_group_resource(
        f"{config.UPSTREAM_API_URL}/groups/{group_key}/events",
        {"fields": FIELDS, "per_page": per_page, "order": "desc"},
        cache, group_key, FeedEvent.from_json)
