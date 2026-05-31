"""Tests for the Streamlit API client helper."""

import pandas as pd

from app import api_client


def test_run_query_normalizes_numeric_params(monkeypatch):
    captured = {}

    def fake_request(method, url, timeout, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["timeout"] = timeout
        captured["params"] = kwargs.get("params")

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [{"community_id": 1}]

        return FakeResponse()

    monkeypatch.setattr(api_client.requests, "request", fake_request)
    monkeypatch.setattr(api_client, "API_BASE_URL", "http://example.com")

    frame = api_client.run_query(
        "q5_high_demand_efficient",
        {"max_avg_hours": "720", "unused": pd.Series([1]).iloc[0]},
    )

    assert captured["method"] == "GET"
    assert captured["url"] == "http://example.com/api/queries/q5_high_demand_efficient"
    assert captured["params"]["max_avg_hours"] == 720
    assert isinstance(captured["params"]["unused"], int)
    assert frame.to_dict(orient="records") == [{"community_id": 1}]
