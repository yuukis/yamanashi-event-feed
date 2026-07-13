import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        if value <= 0:
            return default
        return value
    except ValueError:
        return default


UPSTREAM_API_URL = os.getenv("UPSTREAM_API_URL",
                             "https://api.event.yamanashi.dev").rstrip("/")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "https://hub.yamanashi.dev").rstrip("/")
MAX_ITEMS = _int_env("MAX_ITEMS", 30)
CACHE_TTL_SECONDS = _int_env("CACHE_TTL_SECONDS", 300)
