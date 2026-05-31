"""Regression tests for Streamlit result rendering."""

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import app.app as frontend_app


def test_render_query_results_uses_compat_layout(monkeypatch):
    captured = {}

    def fake_markdown(text):
        captured["markdown"] = text

    def fake_dataframe(data, **kwargs):
        captured["data"] = data
        captured["kwargs"] = kwargs

    monkeypatch.setattr(frontend_app.st, "markdown", fake_markdown)
    monkeypatch.setattr(frontend_app.st, "dataframe", fake_dataframe)

    results = pd.DataFrame([{"community_id": 1, "community_name": "ROGERS PARK"}])
    frontend_app.render_query_results(results)

    assert captured["markdown"] == "### Results"
    assert captured["data"].equals(results)
    assert captured["kwargs"] == {"use_container_width": True}
