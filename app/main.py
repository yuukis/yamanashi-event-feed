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

lambda_handler = Mangum(app)
