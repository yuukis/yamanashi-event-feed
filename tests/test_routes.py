import xml.etree.ElementTree as ET

from app.models import FeedEvent
from app.routes import build_feed_response


def test_sorts_by_actual_time_across_mixed_utc_offsets():
    """Regression test: sorting by the raw ISO8601 string (instead of a
    parsed datetime) misorders events whose updated_at strings use
    different UTC offset notations, even when one is chronologically
    later than the other."""
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
