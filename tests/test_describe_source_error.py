import httpx

from job_hunter.describe_source_error import describe_source_error


def test_describe_source_http_error():
    request = httpx.Request(
        "GET",
        "https://example.com/jobs?token=secret-value",
    )
    response = httpx.Response(503, request=request)

    error = httpx.HTTPStatusError(
        "Request failed with token=secret-value",
        request=request,
        response=response,
    )

    result = describe_source_error("greenhouse", "broken", error)

    assert result == {
        "provider": "greenhouse",
        "board": "broken",
        "error_type": "HTTPStatusError",
        "category": "transient",
        "status_code": 503,
    }

    assert "secret-value" not in str(result)

def test_describe_source_connection_timeout():
    error = httpx.ConnectTimeout("Secret connection details")

    result = describe_source_error("lever", "slow-board", error)

    assert result == {
        "provider": "lever",
        "board": "slow-board",
        "error_type": "ConnectTimeout",
        "category": "transient",
        "status_code": None,
    }

def test_describe_source_unknown_exception():
    result = describe_source_error(
        provider="greenhouse",
        board="broken",
        error=ValueError("secret-value"),
    )

    assert result == {
        "provider": "greenhouse",
        "board": "broken",
        "error_type": "ValueError",
        "category": "permanent",
        "status_code": None,
    }

    assert "secret-value" not in str(result)