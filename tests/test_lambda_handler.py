from app import upstream
from app.main import lambda_handler
from app.models import FeedEvent


class FakeContext:
    function_name = "eventfeed-lambda"
    memory_limit_in_mb = 256
    invoked_function_arn = (
        "arn:aws:lambda:ap-northeast-1:123456789012:function:eventfeed-lambda"
    )
    aws_request_id = "test-request-id"


def make_api_gateway_event(path="/feed.xml"):
    return {
        "version": "1.0",
        "resource": "/{proxy+}",
        "path": path,
        "httpMethod": "GET",
        "headers": {"Host": "example.execute-api.ap-northeast-1.amazonaws.com"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": {"proxy": path.lstrip("/")},
        "stageVariables": None,
        "requestContext": {
            "resourceId": "abc123",
            "resourcePath": "/{proxy+}",
            "httpMethod": "GET",
            "path": "/Prod" + path,
            "stage": "Prod",
            "identity": {"sourceIp": "127.0.0.1"},
            "requestId": "test-request-id",
            "protocol": "HTTP/1.1",
        },
        "body": None,
        "isBase64Encoded": False,
    }


def test_lambda_handler_does_not_base64_encode_rss_body(monkeypatch):
    # API Gateway only decodes a base64 Lambda response body for binary
    # media types, which our template doesn't configure -- this reproduces
    # a bug where clients got the literal base64 string instead of XML.
    monkeypatch.setattr(
        upstream, "fetch_events",
        lambda: ([FeedEvent(uid="1", title="Event",
                            event_url="https://connpass.com/event/1/",
                            updated_at="2026-07-10T10:00:00+09:00")], None),
    )

    result = lambda_handler(make_api_gateway_event(), FakeContext())

    assert result["statusCode"] == 200
    assert result["isBase64Encoded"] is False
    assert result["body"].startswith("<?xml")
