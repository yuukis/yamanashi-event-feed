from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class FeedEvent:
    uid: str
    title: str
    event_url: str
    updated_at: str
    group_name: Optional[str] = None
    description: Optional[str] = None
    catch: Optional[str] = None
    keywords: Optional[List[str]] = None

    @staticmethod
    def from_json(data: Any):
        if isinstance(data, list):
            return [FeedEvent.from_json(item) for item in data]

        if isinstance(data, dict):
            return FeedEvent(
                uid=data["uid"],
                title=data["title"],
                event_url=data["event_url"],
                updated_at=data["updated_at"],
                group_name=data.get("group_name"),
                description=data.get("description"),
                catch=data.get("catch"),
                keywords=data.get("keywords"),
            )

        raise ValueError("data must be dict or List[dict]")


@dataclass
class GroupInfo:
    key: str
    title: str
    url: Optional[str] = None
    description: Optional[str] = None

    @staticmethod
    def from_json(data: Any):
        return GroupInfo(
            key=data["key"],
            title=data["title"],
            url=data.get("url"),
            description=data.get("description"),
        )
