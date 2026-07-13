from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(
    title="Yamanashi Event Feed",
    description="RSS feed of new and updated tech events for Yamanashi Developer Hub",
)

# routes.py imports `app` back, so it must come after `app` is constructed.
from . import routes  # noqa: E402

# Without this, Mangum would base64-encode the RSS body (not text by
# default) and our API Gateway (no binary media types) would forward it as-is.
TEXT_MIME_TYPES = [
    "text/",
    "application/json",
    "application/javascript",
    "application/xml",
    "application/vnd.api+json",
    "application/vnd.oai.openapi",
    "application/rss+xml",
]

lambda_handler = Mangum(app, text_mime_types=TEXT_MIME_TYPES)
