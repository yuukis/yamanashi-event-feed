import xml.etree.ElementTree as ET

from app.models import FeedEvent
from app.rss import build_rss


def make_event(uid, title, updated_at, event_url="https://connpass.com/event/1/",
               group_name=None, description=None, catch=None, keywords=None):
    return FeedEvent(
        uid=uid,
        title=title,
        event_url=event_url,
        updated_at=updated_at,
        group_name=group_name,
        description=description,
        catch=catch,
        keywords=keywords,
    )


def parse(xml_text):
    return ET.fromstring(xml_text)


def test_rss_is_well_formed():
    events = [
        make_event("1", "サンプル勉強会", "2026-07-10T10:00:00+09:00",
                   group_name="やまなしIT部", description="説明文",
                   keywords=["python", "fastapi"]),
        make_event("2", "もくもく会", "2026-07-11T10:00:00+09:00"),
    ]

    xml_text = build_rss(events, "Test Feed", "https://hub.yamanashi.dev",
                         "Test description")

    root = parse(xml_text)
    assert root.tag == "rss"
    channel = root.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == 2


def test_xml_escaping_of_special_characters():
    events = [
        make_event(
            "1",
            "A & B <event> \"quote\"",
            "2026-07-10T10:00:00+09:00",
            description="Tom & Jerry <b>bold</b>",
        )
    ]

    xml_text = build_rss(events, "Test & Feed", "https://hub.yamanashi.dev",
                         "desc")

    # Raw, unescaped special characters must not appear in the serialized
    # XML outside of markup structure.
    assert "<event>" not in xml_text
    assert "A & B" not in xml_text
    assert "Tom & Jerry" not in xml_text

    root = parse(xml_text)
    item = root.find("channel").find("item")
    assert item.find("title").text == "A & B <event> \"quote\""
    assert item.find("description").text == "Tom & Jerry <b>bold</b>"


def test_top_n_and_sort_order():
    events = [
        make_event(str(i), f"Event {i}", f"2026-07-{i:02d}T00:00:00+09:00")
        for i in range(1, 11)
    ]

    xml_text = build_rss(events[:3], "Test Feed", "https://hub.yamanashi.dev",
                         "desc")
    root = parse(xml_text)
    items = root.find("channel").findall("item")
    guids = [item.find("guid").text for item in items]
    assert guids == ["1", "2", "3"]


def test_link_is_event_url_not_hub():
    events = [
        make_event("1", "Event", "2026-07-10T10:00:00+09:00",
                   event_url="https://connpass.com/event/12345/"),
    ]

    xml_text = build_rss(events, "Test Feed", "https://hub.yamanashi.dev",
                         "desc")
    root = parse(xml_text)
    link = root.find("channel").find("item").find("link").text
    assert link == "https://connpass.com/event/12345/"
    assert "hub.yamanashi.dev" not in link


def test_description_falls_back_to_catch_then_empty():
    events = [
        make_event("1", "Event A", "2026-07-10T10:00:00+09:00",
                   description=None, catch="キャッチコピー"),
        make_event("2", "Event B", "2026-07-10T10:00:00+09:00",
                   description=None, catch=None),
    ]

    xml_text = build_rss(events, "Test Feed", "https://hub.yamanashi.dev",
                         "desc")
    root = parse(xml_text)
    items = root.find("channel").findall("item")
    assert items[0].find("description").text == "キャッチコピー"
    assert items[1].find("description").text is None


def test_title_includes_group_name():
    events = [
        make_event("1", "Event A", "2026-07-10T10:00:00+09:00",
                   group_name="やまなしIT部"),
    ]

    xml_text = build_rss(events, "Test Feed", "https://hub.yamanashi.dev",
                         "desc")
    root = parse(xml_text)
    title = root.find("channel").find("item").find("title").text
    assert title == "Event A(やまなしIT部)"


def test_category_emitted_for_each_keyword():
    events = [
        make_event("1", "Event A", "2026-07-10T10:00:00+09:00",
                   keywords=["python", "fastapi"]),
    ]

    xml_text = build_rss(events, "Test Feed", "https://hub.yamanashi.dev",
                         "desc")
    root = parse(xml_text)
    categories = [c.text for c in root.find("channel").find("item").findall("category")]
    assert categories == ["python", "fastapi"]
