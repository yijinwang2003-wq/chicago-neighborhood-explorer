"""Tests for the public FastAPI endpoints used by the frontend."""

import pytest

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
