from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(
    title="Yamanashi Event Feed",
    description="RSS feed of new and updated tech events for Yamanashi Developer Hub",
)

# routes.py imports `app` back from this module, so this must come after
# `app` is constructed.
from . import routes  # noqa: E402

# Mangum doesn't treat application/rss+xml as text by default, so it would
# base64-encode the body; our API Gateway has no binary media types
# configured and would forward that base64 string to clients as-is.
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
