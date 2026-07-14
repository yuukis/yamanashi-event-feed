from datetime import datetime, timedelta, timezone

import pytest

from app import config, upstream


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data or []
        self.headers = headers or {}
        self.ok = status_code < 400

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"status {self.status_code}")


SAMPLE_EVENT = {
    "uid": "1",
    "title": "Event",
    "event_url": "https://connpass.com/event/1/",
    "updated_at": "2026-07-10T10:00:00+09:00",
}


@pytest.fixture(autouse=True)
def reset_cache():
    upstream._cache["events"] = None
    upstream._cache["last_modified"] = None
    upstream._cache["fetched_at"] = None
    yield
    upstream._cache["events"] = None
    upstream._cache["last_modified"] = None
    upstream._cache["fetched_at"] = None


def test_fetches_from_upstream_when_cache_empty(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return FakeResponse(200, [SAMPLE_EVENT],
                           {"Last-Modified": "Fri, 10 Jul 2026 01:00:00 GMT"})

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    events, last_modified = upstream.fetch_events()

    assert len(calls) == 1
    assert len(events) == 1
    assert events[0].uid == "1"
    assert last_modified == datetime(2026, 7, 10, 1, 0, 0, tzinfo=timezone.utc)


def test_does_not_refetch_within_ttl(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(1)
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    upstream.fetch_events()
    upstream.fetch_events()

    assert len(calls) == 1


def test_refetches_after_ttl_expires(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(1)
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    upstream.fetch_events()
    upstream._cache["fetched_at"] -= 301

    upstream.fetch_events()

    assert len(calls) == 2


def test_keeps_cached_data_on_304(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return FakeResponse(200, [SAMPLE_EVENT],
                               {"Last-Modified": "Fri, 10 Jul 2026 01:00:00 GMT"})
        return FakeResponse(304)

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    events1, lm1 = upstream.fetch_events()
    upstream._cache["fetched_at"] -= 301
    events2, lm2 = upstream.fetch_events()

    assert call_count["n"] == 2
    assert events1 == events2
    assert lm1 == lm2


def test_serves_stale_cache_on_upstream_error(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return FakeResponse(200, [SAMPLE_EVENT])
        raise upstream.requests.RequestException("boom")

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    events1, _ = upstream.fetch_events()
    upstream._cache["fetched_at"] -= 301
    events2, _ = upstream.fetch_events()

    assert call_count["n"] == 2
    assert events1 == events2


SAMPLE_GROUP = {
    "key": "example-group",
    "title": "サンプル勉強会",
    "url": "https://connpass.com/group/example/",
    "description": "サンプルの説明",
}


@pytest.fixture(autouse=True)
def reset_group_caches():
    upstream._group_meta_caches.clear()
    upstream._group_event_caches.clear()
    yield
    upstream._group_meta_caches.clear()
    upstream._group_event_caches.clear()


def test_fetch_group_fetches_from_upstream(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return FakeResponse(200, SAMPLE_GROUP,
                           {"Last-Modified": "Fri, 10 Jul 2026 01:00:00 GMT"})

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    group, last_modified = upstream.fetch_group("example-group")

    assert len(calls) == 1
    assert calls[0][0] == f"{config.UPSTREAM_API_URL}/groups/example-group"
    assert calls[0][1] == {"fields": upstream.GROUP_FIELDS}
    assert group.key == "example-group"
    assert group.title == "サンプル勉強会"
    assert last_modified == datetime(2026, 7, 10, 1, 0, 0, tzinfo=timezone.utc)


def test_fetch_group_raises_not_found_on_404(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(404)

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    with pytest.raises(upstream.GroupNotFoundError):
        upstream.fetch_group("does-not-exist")


def test_fetch_group_does_not_refetch_within_ttl(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(1)
        return FakeResponse(200, SAMPLE_GROUP)

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    upstream.fetch_group("example-group")
    upstream.fetch_group("example-group")

    assert len(calls) == 1


def test_fetch_group_events_fetches_from_upstream(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    events, _ = upstream.fetch_group_events("example-group")

    assert len(calls) == 1
    assert calls[0][0] == f"{config.UPSTREAM_API_URL}/groups/example-group/events"
    assert calls[0][1] == {
        "fields": upstream.FIELDS,
        "per_page": min(config.MAX_ITEMS, upstream.GROUP_EVENTS_PAGE_SIZE_LIMIT),
        "order": "desc",
    }
    assert len(events) == 1


def test_fetch_group_events_per_page_matches_max_items(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "MAX_ITEMS", 10)

    upstream.fetch_group_events("example-group")

    assert calls[0]["per_page"] == 10


def test_fetch_group_events_per_page_capped_at_upstream_limit(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "MAX_ITEMS", 500)

    upstream.fetch_group_events("example-group")

    assert calls[0]["per_page"] == upstream.GROUP_EVENTS_PAGE_SIZE_LIMIT


def test_group_key_is_url_encoded_in_upstream_requests(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(200, SAMPLE_GROUP)

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    upstream.fetch_group("weird?group&key")

    assert calls[0] == f"{config.UPSTREAM_API_URL}/groups/weird%3Fgroup%26key"


def test_group_caches_are_bounded(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    for i in range(upstream.MAX_GROUP_CACHE_ENTRIES + 50):
        upstream.fetch_group_events(f"group-{i}")

    assert len(upstream._group_event_caches) == upstream.MAX_GROUP_CACHE_ENTRIES
    # Oldest entries were evicted, most recent ones remain.
    assert "group-0" not in upstream._group_event_caches
    assert f"group-{upstream.MAX_GROUP_CACHE_ENTRIES + 49}" in upstream._group_event_caches


def test_fetch_group_events_raises_not_found_on_404(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(404)

    monkeypatch.setattr(upstream.requests, "get", fake_get)

    with pytest.raises(upstream.GroupNotFoundError):
        upstream.fetch_group_events("does-not-exist")


def test_fetch_group_events_cache_independent_from_main_feed_and_other_groups(monkeypatch):
    calls = {"events": 0, "group_events": {"example-group": 0, "other-group": 0}}

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == f"{config.UPSTREAM_API_URL}/events":
            calls["events"] += 1
        elif url == f"{config.UPSTREAM_API_URL}/groups/example-group/events":
            calls["group_events"]["example-group"] += 1
        elif url == f"{config.UPSTREAM_API_URL}/groups/other-group/events":
            calls["group_events"]["other-group"] += 1
        return FakeResponse(200, [SAMPLE_EVENT])

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    upstream.fetch_events()
    upstream.fetch_group_events("example-group")
    upstream.fetch_group_events("other-group")
    upstream.fetch_events()
    upstream.fetch_group_events("example-group")
    upstream.fetch_group_events("other-group")

    assert calls["events"] == 1
    assert calls["group_events"]["example-group"] == 1
    assert calls["group_events"]["other-group"] == 1


def test_fetch_group_events_serves_stale_cache_on_upstream_error(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return FakeResponse(200, [SAMPLE_EVENT])
        raise upstream.requests.RequestException("boom")

    monkeypatch.setattr(upstream.requests, "get", fake_get)
    monkeypatch.setattr(config, "CACHE_TTL_SECONDS", 300)

    events1, _ = upstream.fetch_group_events("example-group")
    upstream._group_event_caches["example-group"]["fetched_at"] -= 301
    events2, _ = upstream.fetch_group_events("example-group")

    assert call_count["n"] == 2
    assert events1 == events2
