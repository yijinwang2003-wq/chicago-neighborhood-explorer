"""Pydantic response schemas for the FastAPI backend."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ApiModel(BaseModel):
    """Base schema that accepts MySQL Decimal values without pre-conversion."""

    class Config:
        json_encoders = {Decimal: float}


class HealthResponse(ApiModel):
    status: str
    database: str


class NeighborhoodSummary(ApiModel):
    community_id: int
    community_name: str
    population: int | None = None
    median_household_income: Decimal | None = None
    crime_incidents_2025: int
    crime_incidents_per_1000_population_estimate_2025: Decimal | None = None
    reported_city_supported_units_snapshot: Decimal | int
    rail_station_count_snapshot: int
    rail_station_density_snapshot: Decimal | None = None
    rail_entries_2025: Decimal | int
    avg_closed_311_response_hours_2025: Decimal | None = None


class NeighborhoodDetail(NeighborhoodSummary):
    cmap_release_year: int | None = None
    acs_estimate_period: str | None = None
    unemployment_rate: Decimal | None = None
    pct_bachelors: Decimal | None = None
    housing_cost_burden_30plus_pct: Decimal | None = None


class CrimeBreakdown(ApiModel):
    crime_month: int
    crime_type: str | None = None
    crime_count: int


class NeighborhoodCrime(ApiModel):
    community_id: int
    community_name: str
    total_crimes_2025: int
    breakdown: list[CrimeBreakdown]


class TransitStation(ApiModel):
    station_id: int
    station_name: str
    ada_accessible: bool | None = None
    rail_lines: str | None = None
    total_entries_2025: Decimal | int | None = None
    avg_weekday_rides_2025: Decimal | None = None


class NeighborhoodTransit(ApiModel):
    community_id: int
    community_name: str
    station_count: int
    total_entries_2025: Decimal | int
    stations: list[TransitStation]


class CompareResponse(ApiModel):
    ids: list[int]
    neighborhoods: list[NeighborhoodSummary]


class Ward(ApiModel):
    ward_id: int


class ServiceRequestCreate(ApiModel):
    request_type: str
    community_id: int
    status: str = "Open"
    street_address: str | None = None
    zip_code: str | None = None


class ServiceRequestCreateResponse(ApiModel):
    status: str


class ErrorResponse(ApiModel):
    detail: str | dict[str, Any]
