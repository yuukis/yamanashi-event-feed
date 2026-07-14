import xml.etree.ElementTree as ET

import pytest
from fastapi import HTTPException

from app import config, upstream
from app.models import FeedEvent, GroupInfo
from app.routes import build_feed_response, get_group_feed


def test_sorts_by_actual_time_across_mixed_utc_offsets():
    earlier_but_lexically_larger = FeedEvent(
        uid="A",
        title="Earlier event",
        event_url="https://connpass.com/event/1/",
        updated_at="2026-07-10T23:00:00+09:00",  # 14:00 UTC
    )
    later_but_lexically_smaller = FeedEvent(
        uid="B",
        title="Later event",
        event_url="https://connpass.com/event/2/",
        updated_at="2026-07-10T20:00:00Z",  # 20:00 UTC
    )

    response = build_feed_response(
        None, [earlier_but_lexically_larger, later_but_lexically_smaller],
        "Test Feed", "https://hub.yamanashi.dev", "desc",
    )

    root = ET.fromstring(response.body)
    guids = [item.find("guid").text
            for item in root.find("channel").findall("item")]
    assert guids == ["B", "A"]


def test_truncates_to_max_items(monkeypatch):
    monkeypatch.setattr(config, "MAX_ITEMS", 3)

    events = [
        FeedEvent(
            uid=str(i),
            title=f"Event {i}",
            event_url=f"https://connpass.com/event/{i}/",
            updated_at=f"2026-07-{i:02d}T00:00:00+09:00",
        )
        for i in range(1, 11)
    ]

    response = build_feed_response(
        None, events, "Test Feed", "https://hub.yamanashi.dev", "desc",
    )

    root = ET.fromstring(response.body)
    guids = [item.find("guid").text
            for item in root.find("channel").findall("item")]
    assert guids == ["10", "9", "8"]


def test_group_feed_uses_group_metadata(monkeypatch):
    group = GroupInfo(key="example-group", title="サンプル勉強会",
                      url="https://connpass.com/group/example/",
                      description="サンプルの説明")
    events = [FeedEvent(uid="1", title="Event",
                        event_url="https://connpass.com/event/1/",
                        updated_at="2026-07-10T10:00:00+09:00")]

    monkeypatch.setattr(upstream, "fetch_group", lambda key: (group, None))
    monkeypatch.setattr(upstream, "fetch_group_events", lambda key: (events, None))

    response = get_group_feed("example-group", None)

    root = ET.fromstring(response.body)
    channel = root.find("channel")
    assert channel.find("title").text == "サンプル勉強会 - 新着・更新イベント"
    assert channel.find("link").text == "https://connpass.com/group/example/"
    assert channel.find("description").text == "サンプルの説明"


def test_group_feed_falls_back_to_generated_description_and_hub_link(monkeypatch):
    group = GroupInfo(key="example-group", title="サンプル勉強会", url=None, description=None)

    monkeypatch.setattr(upstream, "fetch_group", lambda key: (group, None))
    monkeypatch.setattr(upstream, "fetch_group_events", lambda key: ([], None))

    response = get_group_feed("example-group", None)

    root = ET.fromstring(response.body)
    channel = root.find("channel")
    assert channel.find("description").text == "サンプル勉強会の新着・更新イベント情報を配信するフィードです。"
    assert channel.find("link").text == config.HUB_BASE_URL


def test_group_feed_returns_404_when_group_not_found(monkeypatch):
    def raise_not_found(key):
        raise upstream.GroupNotFoundError(key)

    monkeypatch.setattr(upstream, "fetch_group", raise_not_found)

    with pytest.raises(HTTPException) as exc_info:
        get_group_feed("does-not-exist", None)

    assert exc_info.value.status_code == 404
