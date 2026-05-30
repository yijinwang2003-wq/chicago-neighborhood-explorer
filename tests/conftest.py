"""Shared pytest fixtures for API tests."""

import asyncio
import json
from dataclasses import dataclass
from urllib.parse import urlsplit

import pytest

from api.database import get_db
from api.main import app


class FakeDatabase:
    """Sentinel object used to prove tests do not open MySQL connections."""


@dataclass
class AsgiResponse:
    status_code: int
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class AsgiTestClient:
    """Minimal ASGI client for testing FastAPI without a real socket."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def get(self, url: str) -> AsgiResponse:
        return asyncio.run(self._request("GET", url))

    async def _request(self, method: str, url: str) -> AsgiResponse:
        parsed = urlsplit(url)
        messages = []

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": parsed.path,
            "raw_path": parsed.path.encode("ascii"),
            "query_string": parsed.query.encode("ascii"),
            "headers": [(b"host", b"testserver")],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await self.asgi_app(scope, receive, send)

        status_code = 500
        body_parts = []
        for message in messages:
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))

        return AsgiResponse(status_code=status_code, body=b"".join(body_parts))


@pytest.fixture
def fake_db():
    return FakeDatabase()


@pytest.fixture
def client(fake_db):
    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    yield AsgiTestClient(app)
    app.dependency_overrides.clear()
