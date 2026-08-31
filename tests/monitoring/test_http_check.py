"""
Tests HTTP monitoring behaviour for successful, failed, and timed-out requests.
"""
from typing import cast

import aiohttp
import pytest

from monitoring.checks.http_check import HTTPCheck
from monitoring.models import CheckStatus


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> bool:
        return False


class TimeoutResponse:
    async def __aenter__(self):
        raise TimeoutError()

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> bool:
        return False


class FakeSession:
    def __init__(self, response) -> None:
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_http_200_is_up() -> None:
    fake_session = FakeSession(
        FakeResponse(200)
    )

    session = cast(
        aiohttp.ClientSession,
        fake_session,
    )

    check = HTTPCheck(
        name="test-http",
        url="https://example.com",
        session=session,
        expected_status=200,
    )

    result = await check.run()

    assert result.status is CheckStatus.UP
    assert result.message == "HTTP 200"
    assert result.response_time_ms is not None
    assert result.response_time_ms >= 0


@pytest.mark.asyncio
async def test_http_503_is_down() -> None:
    fake_session = FakeSession(
        FakeResponse(503)
    )

    session = cast(
        aiohttp.ClientSession,
        fake_session,
    )

    check = HTTPCheck(
        name="test-http",
        url="https://example.com",
        session=session,
        expected_status=200,
    )

    result = await check.run()

    assert result.status is CheckStatus.DOWN
    assert result.message == "HTTP 503"


@pytest.mark.asyncio
async def test_expected_non_200_status_can_be_up() -> None:
    fake_session = FakeSession(
        FakeResponse(204)
    )

    session = cast(
        aiohttp.ClientSession,
        fake_session,
    )

    check = HTTPCheck(
        name="test-http",
        url="https://example.com",
        session=session,
        expected_status=204,
    )

    result = await check.run()

    assert result.status is CheckStatus.UP
    assert result.message == "HTTP 204"


@pytest.mark.asyncio
async def test_http_timeout_is_down() -> None:
    fake_session = FakeSession(
        TimeoutResponse()
    )

    session = cast(
        aiohttp.ClientSession,
        fake_session,
    )

    check = HTTPCheck(
        name="test-http",
        url="https://example.com",
        session=session,
        timeout_seconds=1.0,
    )

    result = await check.run()

    assert result.status is CheckStatus.DOWN
    assert result.message == "Request timed out"