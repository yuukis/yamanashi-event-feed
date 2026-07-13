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
