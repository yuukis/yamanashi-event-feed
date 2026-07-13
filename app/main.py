from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(
    title="Yamanashi Event Feed",
    description="RSS feed of new and updated tech events for Yamanashi Developer Hub",
)

# Imported for its side effect: registers routes onto `app`. Must come
# after `app` is constructed above, since routes.py imports `app` back
# from this module.
from . import routes  # noqa: E402

# Mangum's default text-mime allowlist doesn't include application/rss+xml,
# so without this it base64-encodes the feed body and marks the response
# isBase64Encoded=True. Our API Gateway REST API has no binary media types
# configured, so it would forward that base64 string as literal body text
# to clients instead of decoding it. Listing our content type as text here
# keeps the body as plain text end-to-end, avoiding any API Gateway config.
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
