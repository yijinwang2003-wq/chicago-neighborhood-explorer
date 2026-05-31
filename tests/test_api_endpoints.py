"""Tests for the public FastAPI endpoints used by the frontend."""

import pandas as pd
import pytest

import api.main as api_main
from api.main import queries


def neighborhood_row(community_id: int = 1, community_name: str = "ROGERS PARK") -> dict:
    return {
        "community_id": community_id,
        "community_name": community_name,
        "cmap_release_year": 2025,
        "acs_estimate_period": "2019-2023",
        "population": 55000,
        "median_household_income": 72000,
        "unemployment_rate": 5.2,
        "pct_bachelors": 48.5,
        "housing_cost_burden_30plus_pct": 35.1,
        "crime_incidents_2025": 3757,
        "crime_incidents_per_1000_population_estimate_2025": 68.31,
        "reported_city_supported_units_snapshot": 120,
        "rail_station_count_snapshot": 4,
        "rail_station_density_snapshot": 1.8,
        "rail_entries_2025": 1234567,
        "avg_closed_311_response_hours_2025": 42.5,
    }


def test_health_returns_status_and_database(client, fake_db, monkeypatch):
    def fake_fetch_one(db, sql):
        assert db is fake_db
        assert "DATABASE()" in sql
        return {"database_name": "chicago_neighborhood"}

    monkeypatch.setattr(queries, "fetch_one", fake_fetch_one)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "chicago_neighborhood"}


def test_neighborhoods_returns_list_schema(client, fake_db, monkeypatch):
    def fake_list_neighborhoods(db):
        assert db is fake_db
        return [
            neighborhood_row(1, "ROGERS PARK"),
            neighborhood_row(2, "WEST RIDGE"),
        ]

    monkeypatch.setattr(queries, "list_neighborhoods", fake_list_neighborhoods)

    response = client.get("/api/neighborhoods")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert set(body[0]) == {
        "community_id",
        "community_name",
        "population",
        "median_household_income",
        "crime_incidents_2025",
        "crime_incidents_per_1000_population_estimate_2025",
        "reported_city_supported_units_snapshot",
        "rail_station_count_snapshot",
        "rail_station_density_snapshot",
        "rail_entries_2025",
        "avg_closed_311_response_hours_2025",
    }
    assert body[0]["community_id"] == 1
    assert body[0]["community_name"] == "ROGERS PARK"


def test_neighborhood_detail_returns_detail_schema(client, fake_db, monkeypatch):
    def fake_get_neighborhood(db, community_id):
        assert db is fake_db
        assert community_id == 1
        return neighborhood_row(1, "ROGERS PARK")

    monkeypatch.setattr(queries, "get_neighborhood", fake_get_neighborhood)

    response = client.get("/api/neighborhoods/1")

    assert response.status_code == 200
    body = response.json()
    assert body["community_id"] == 1
    assert body["community_name"] == "ROGERS PARK"
    assert body["cmap_release_year"] == 2025
    assert body["acs_estimate_period"] == "2019-2023"
    assert "unemployment_rate" in body
    assert "pct_bachelors" in body
    assert "housing_cost_burden_30plus_pct" in body


def test_neighborhood_detail_returns_404(client, monkeypatch):
    monkeypatch.setattr(queries, "get_neighborhood", lambda db, community_id: None)

    response = client.get("/api/neighborhoods/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Neighborhood not found"}


def test_compare_returns_requested_ids_and_schema(client, fake_db, monkeypatch):
    def fake_compare_neighborhoods(db, community_ids):
        assert db is fake_db
        assert community_ids == [1, 2, 3]
        return [
            neighborhood_row(1, "ROGERS PARK"),
            neighborhood_row(2, "WEST RIDGE"),
            neighborhood_row(3, "UPTOWN"),
        ]

    monkeypatch.setattr(queries, "compare_neighborhoods", fake_compare_neighborhoods)

    response = client.get("/api/compare?ids=1,2,3")

    assert response.status_code == 200
    body = response.json()
    assert body["ids"] == [1, 2, 3]
    assert len(body["neighborhoods"]) == 3
    assert body["neighborhoods"][2]["community_name"] == "UPTOWN"


@pytest.mark.parametrize(
    "ids, detail",
    [
        ("abc,2", "ids must be comma-separated integers"),
        ("", "ids must include at least one community ID"),
        ("1,1", "ids must not include duplicates"),
    ],
)
def test_compare_rejects_invalid_ids(client, ids, detail):
    response = client.get(f"/api/compare?ids={ids}")

    assert response.status_code == 422
    assert response.json() == {"detail": detail}


def test_compare_returns_404_for_missing_ids(client, monkeypatch):
    monkeypatch.setattr(
        queries,
        "compare_neighborhoods",
        lambda db, community_ids: [neighborhood_row(1, "ROGERS PARK")],
    )

    response = client.get("/api/compare?ids=1,2")

    assert response.status_code == 404
    assert response.json() == {"detail": {"missing_ids": [2]}}


@pytest.mark.parametrize(
    "query_key, query_string, expected_param, expected_value",
    [
        ("q5_high_demand_efficient", "?max_avg_hours=720", "max_avg_hours", 720),
        ("q7_crime_near_housing", "?min_housing_units=10", "min_housing_units", 10),
    ],
)
def test_run_query_coerces_numeric_params(client, fake_db, monkeypatch, query_key, query_string, expected_param, expected_value):
    def fake_query(db, **kwargs):
        assert db is fake_db
        assert kwargs[expected_param] == expected_value
        assert isinstance(kwargs[expected_param], int)
        return pd.DataFrame([{"community_id": 1}])

    monkeypatch.setitem(api_main.QUERY_FUNCTIONS, query_key, fake_query)

    response = client.get(f"/api/queries/{query_key}{query_string}")

    assert response.status_code == 200
    assert response.json() == [{"community_id": 1}]


@pytest.mark.parametrize(
    "query_key, params, expected",
    [
        ("q1_affordable_safe", {"min_units": int}, {"min_units": 10}),
        ("q2_housing_near_transit", {"max_distance_meters": int, "top_n": int}, {"max_distance_meters": 800, "top_n": 100}),
        ("q5_high_demand_efficient", {"max_avg_hours": int}, {"max_avg_hours": 720}),
        ("q6_most_accessible", {"top_n": int}, {"top_n": 15}),
        ("q7_crime_near_housing", {"min_housing_units": int}, {"min_housing_units": 10}),
        ("q8_transit_popularity", {"top_n": int}, {"top_n": 20}),
    ],
)
def test_query_param_coercion_helper(query_key, params, expected):
    request = type(
        "RequestLike",
        (),
        {"query_params": type("QP", (), {"get": lambda self, name: str(expected[name])})()},
    )()

    coerced = api_main.coerce_query_params(query_key, request)

    assert coerced == expected
