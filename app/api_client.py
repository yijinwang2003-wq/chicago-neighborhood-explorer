"""HTTP client helpers for the Streamlit frontend."""

import os
from typing import Any

import pandas as pd
import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 15


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, bool):
            normalized[key] = int(value)
        elif isinstance(value, int):
            normalized[key] = int(value)
        elif isinstance(value, float):
            normalized[key] = float(value)
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                normalized[key] = int(stripped)
            else:
                try:
                    normalized[key] = float(stripped)
                except ValueError:
                    normalized[key] = value
        elif hasattr(value, "item"):
            scalar = value.item()
            if isinstance(scalar, (int, float)):
                normalized[key] = scalar
            else:
                normalized[key] = scalar
        else:
            normalized[key] = value
    return normalized


def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    response = requests.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
    response.raise_for_status()
    return response.json()


def health() -> dict[str, Any]:
    return _request("GET", "/health")


def get_neighborhoods() -> list[dict[str, Any]]:
    return _request("GET", "/api/neighborhoods")


def get_neighborhood(community_id: int) -> dict[str, Any]:
    return _request("GET", f"/api/neighborhoods/{community_id}")


def get_crime(community_id: int) -> dict[str, Any]:
    return _request("GET", f"/api/neighborhoods/{community_id}/crime")


def get_transit(community_id: int) -> dict[str, Any]:
    return _request("GET", f"/api/neighborhoods/{community_id}/transit")


def compare(ids: list[int]) -> dict[str, Any]:
    ids_param = ",".join(str(community_id) for community_id in ids)
    return _request("GET", "/api/compare", params={"ids": ids_param})


def run_query(query_key: str, params: dict[str, Any]) -> pd.DataFrame:
    rows = _request("GET", f"/api/queries/{query_key}", params=_normalize_params(params))
    return pd.DataFrame(rows)


def get_wards() -> list[int]:
    rows = _request("GET", "/api/wards")
    return [int(row["ward_id"]) for row in rows]


def create_service_request(
    request_type: str,
    community_id: int,
    status: str = "Open",
    street_address: str | None = None,
    zip_code: str | None = None,
) -> dict[str, Any]:
    return _request(
        "POST",
        "/api/service-requests",
        json={
            "request_type": request_type,
            "community_id": community_id,
            "status": status,
            "street_address": street_address,
            "zip_code": zip_code,
        },
    )
