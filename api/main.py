"""FastAPI application for the Chicago Neighborhood Explorer backend."""

import os
from typing import Callable

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from mysql.connector import Error as MySQLError
from mysql.connector import MySQLConnection

from app import queries as legacy_queries
from api import queries
from api.database import get_db
from api.schemas import (
    CompareResponse,
    HealthResponse,
    NeighborhoodCrime,
    NeighborhoodDetail,
    NeighborhoodSummary,
    NeighborhoodTransit,
    ServiceRequestCreate,
    ServiceRequestCreateResponse,
    Ward,
)

app = FastAPI(
    title="Chicago Neighborhood Explorer API",
    version="0.1.0",
    description="Read-only API backed by the existing MySQL neighborhood database.",
)

QUERY_FUNCTIONS: dict[str, Callable] = {
    "q1_affordable_safe": legacy_queries.query_affordable_safe,
    "q2_housing_near_transit": legacy_queries.query_housing_near_transit,
    "q3_transit_usage": legacy_queries.query_transit_usage,
    "q5_high_demand_efficient": legacy_queries.query_high_demand_efficient,
    "q6_most_accessible": legacy_queries.query_most_accessible,
    "q7_crime_near_housing": legacy_queries.query_crime_near_housing,
    "q8_transit_popularity": legacy_queries.query_transit_popularity,
    "q9_service_delays": legacy_queries.query_service_delays,
    "q10_demographics_vs_crime": legacy_queries.query_demographics_vs_crime,
    "q11_neighborhood_ranking": legacy_queries.query_neighborhood_ranking,
    "q12_housing_availability": legacy_queries.query_housing_availability,
    "q14_ward_overlap": legacy_queries.query_ward_overlap,
}

QUERY_PARAM_TYPES: dict[str, dict[str, Callable[[str], object]]] = {
    "q1_affordable_safe": {"min_units": int},
    "q2_housing_near_transit": {"max_distance_meters": int, "top_n": int},
    "q5_high_demand_efficient": {"max_avg_hours": int},
    "q6_most_accessible": {"top_n": int},
    "q7_crime_near_housing": {"min_housing_units": int},
    "q8_transit_popularity": {"top_n": int},
    "q9_service_delays": {"top_n": int},
    "q11_neighborhood_ranking": {"top_n": int},
    "q14_ward_overlap": {"ward_id": int},
}


def dataframe_records(dataframe: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to JSON-safe records."""
    return dataframe.astype(object).where(pd.notnull(dataframe), None).to_dict(orient="records")


@app.get("/health", response_model=HealthResponse)
def health(db: MySQLConnection = Depends(get_db)) -> HealthResponse:
    try:
        row = queries.fetch_one(db, "SELECT DATABASE() AS database_name")
    except MySQLError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return HealthResponse(
        status="ok",
        database=row["database_name"] if row else os.getenv("MYSQL_DATABASE", "unknown"),
    )


@app.get("/api/neighborhoods", response_model=list[NeighborhoodSummary])
def list_neighborhoods(db: MySQLConnection = Depends(get_db)) -> list[dict]:
    return queries.list_neighborhoods(db)


@app.get("/api/neighborhoods/{community_id}", response_model=NeighborhoodDetail)
def get_neighborhood(community_id: int, db: MySQLConnection = Depends(get_db)) -> dict:
    neighborhood = queries.get_neighborhood(db, community_id)
    if neighborhood is None:
        raise HTTPException(status_code=404, detail="Neighborhood not found")
    return neighborhood


@app.get("/api/neighborhoods/{community_id}/crime", response_model=NeighborhoodCrime)
def get_neighborhood_crime(community_id: int, db: MySQLConnection = Depends(get_db)) -> NeighborhoodCrime:
    neighborhood = queries.get_neighborhood(db, community_id)
    if neighborhood is None:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    breakdown = queries.get_crime_breakdown(db, community_id)
    total = sum(row["crime_count"] for row in breakdown)
    return NeighborhoodCrime(
        community_id=neighborhood["community_id"],
        community_name=neighborhood["community_name"],
        total_crimes_2025=total,
        breakdown=breakdown,
    )


@app.get("/api/neighborhoods/{community_id}/transit", response_model=NeighborhoodTransit)
def get_neighborhood_transit(
    community_id: int,
    db: MySQLConnection = Depends(get_db),
) -> NeighborhoodTransit:
    neighborhood = queries.get_neighborhood(db, community_id)
    if neighborhood is None:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    stations = queries.get_transit_stations(db, community_id)
    return NeighborhoodTransit(
        community_id=neighborhood["community_id"],
        community_name=neighborhood["community_name"],
        station_count=neighborhood["rail_station_count_snapshot"],
        total_entries_2025=neighborhood["rail_entries_2025"],
        stations=stations,
    )


@app.get("/api/compare", response_model=CompareResponse)
def compare_neighborhoods(
    ids: str = Query(..., description="Comma-separated community IDs, for example: 1,2,3"),
    db: MySQLConnection = Depends(get_db),
) -> CompareResponse:
    try:
        community_ids = [int(value.strip()) for value in ids.split(",") if value.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ids must be comma-separated integers") from exc

    if not community_ids:
        raise HTTPException(status_code=422, detail="ids must include at least one community ID")

    if len(set(community_ids)) != len(community_ids):
        raise HTTPException(status_code=422, detail="ids must not include duplicates")

    neighborhoods = queries.compare_neighborhoods(db, community_ids)
    found_ids = {row["community_id"] for row in neighborhoods}
    missing_ids = [community_id for community_id in community_ids if community_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail={"missing_ids": missing_ids})

    return CompareResponse(ids=community_ids, neighborhoods=neighborhoods)


@app.get("/api/wards", response_model=list[Ward])
def list_wards(db: MySQLConnection = Depends(get_db)) -> list[dict]:
    dataframe = legacy_queries.get_wards(db)
    return dataframe_records(dataframe)


@app.get("/api/queries/{query_key}")
def run_query(
    query_key: str,
    request: Request,
    db: MySQLConnection = Depends(get_db),
) -> list[dict]:
    query_function = QUERY_FUNCTIONS.get(query_key)
    if query_function is None:
        raise HTTPException(status_code=404, detail="Query not found")

    params = {}
    for name, converter in QUERY_PARAM_TYPES.get(query_key, {}).items():
        value = request.query_params.get(name)
        if value is not None:
            try:
                params[name] = converter(value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"{name} has an invalid value") from exc

    dataframe = query_function(db, **params)
    return dataframe_records(dataframe)


@app.post("/api/service-requests", response_model=ServiceRequestCreateResponse)
def create_service_request(
    service_request: ServiceRequestCreate,
    db: MySQLConnection = Depends(get_db),
) -> ServiceRequestCreateResponse:
    legacy_queries.insert_service_request(
        db,
        request_type=service_request.request_type,
        community_id=service_request.community_id,
        street_address=service_request.street_address,
        zip_code=service_request.zip_code,
        status=service_request.status,
    )
    return ServiceRequestCreateResponse(status="ok")
