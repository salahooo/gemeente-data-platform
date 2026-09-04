"""Pydantic response contracts for the public, read-only API."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class YearResponse(BaseModel):
    year: int
    has_average_population: bool


class MunicipalityResponse(BaseModel):
    municipality_code: str
    municipality_name: str
    first_observed_year: int
    last_observed_year: int
    active_in_latest_period: bool


class MunicipalityPage(BaseModel):
    items: list[MunicipalityResponse]
    page: int
    page_size: int
    total: int


class PopulationObservation(BaseModel):
    year: int
    population_january_1: int
    average_population: Decimal | None
    previous_population_january_1: int | None
    population_change_absolute: int | None
    population_change_percent: Decimal | None


class PopulationSeries(BaseModel):
    municipality_code: str
    municipality_name: str
    observations: list[PopulationObservation]


class NationalPopulation(BaseModel):
    year: int
    municipality_count: int
    population_january_1: int | None
    average_population: Decimal | None
    missing_average_population_count: int


class RankingItem(BaseModel):
    rank: int
    municipality_code: str
    municipality_name: str
    population_january_1: int


class ErrorResponse(BaseModel):
    error: str
    request_id: str


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    status: str = "ready"
    required_views: list[str] = Field(default_factory=list)
