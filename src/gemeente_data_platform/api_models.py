"""Pydantic response contracts for the public, read-only API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

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


class DatasetLineage(BaseModel):
    """Public-safe provenance for the last successfully loaded dataset."""

    processed_run_id: str
    pipeline_run_id: str | None
    completed_at: datetime


class AgeCategory(BaseModel):
    category: Literal["0-14", "15-24", "25-44", "45-64", "65+"]
    population: int | None = Field(ge=0)
    share_percent: Decimal | None = Field(ge=0, le=100)
    national_share_percent: Decimal | None = Field(ge=0, le=100)


class MunicipalityProfile(BaseModel):
    municipality_code: str = Field(pattern=r"^GM\d{4}$")
    year: int = Field(ge=1995, le=2200)
    dataset_code: Literal["70072ned"] = "70072ned"
    categories: list[AgeCategory] = Field(default_factory=list, max_length=5)


class PublicQuality(BaseModel):
    dataset_code: Literal["03759ned", "70072ned"]
    dataset_name: Literal["Bevolking", "Leeftijdsopbouw"]
    source: Literal["CBS Open Data"]
    first_year: int | None
    last_year: int | None
    completed_at: datetime | None
    record_count: int = Field(ge=0)
    validation_status: Literal["validated", "unavailable"]
    missing_values: int = Field(ge=0)
    warning: str = Field(max_length=160)


class ErrorResponse(BaseModel):
    error: str
    request_id: str


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    status: str = "ready"
    required_views: list[str] = Field(default_factory=list)
