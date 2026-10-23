from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .domain import Action, Health, ModelType, ProductCategory, RecommendationStatus


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: ProductCategory
    model_type: ModelType
    ea_kj_mol: float | None = Field(default=75.0, gt=0, le=250)
    q10: float | None = Field(default=2.5, gt=0, le=10)
    t_ref_c: float = Field(ge=-80, le=100)
    l0_hours: float = Field(gt=0, le=200_000)
    min_temp_c: float
    max_temp_c: float
    hard_stop_rules: dict[str, Any] = Field(default_factory=dict)
    unit_value: float = Field(default=0, ge=0)
    co2e_per_kg: float = Field(default=0, ge=0)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_model_parameters(self):
        if self.model_type == ModelType.ARRHENIUS and self.ea_kj_mol is None:
            raise ValueError("ea_kj_mol is required for Arrhenius products")
        if self.model_type == ModelType.Q10 and self.q10 is None:
            raise ValueError("q10 is required for Q10 products")
        if self.min_temp_c >= self.max_temp_c:
            raise ValueError("min_temp_c must be less than max_temp_c")
        return self


class ProductRead(ProductIn):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class TelemetryIn(BaseModel):
    shipment_id: str = Field(min_length=1, max_length=100)
    ts: datetime
    temp_c: float = Field(ge=-100, le=150)
    humidity: float | None = Field(default=None, ge=0, le=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    door_open: bool = False
    battery_pct: int | None = Field(default=None, ge=0, le=100)
    model_config = ConfigDict(extra="forbid")

    @field_validator("ts")
    @classmethod
    def require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ts must include a timezone")
        return value.astimezone(timezone.utc)


class ShipmentIn(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    product_id: UUID
    batch_no: str | None = None
    quantity_kg: float = Field(gt=0)
    units: int = Field(default=1, gt=0)
    value: float = Field(default=0, ge=0)
    planned_eta: datetime | None = None
    destination_id: UUID | None = None
    current_lat: float | None = Field(default=None, ge=-90, le=90)
    current_lon: float | None = Field(default=None, ge=-180, le=180)
    model_config = ConfigDict(extra="forbid")


class HubIn(BaseModel):
    name: str
    type: str = "DISTRIBUTION"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    capacity_kg: float = Field(ge=0)
    accepted_categories: list[ProductCategory]
    demand_index: float = Field(default=0.5, ge=0, le=1)
    price_ratio: float = Field(default=1, ge=0)
    min_sellable_life_pct: float = Field(default=0, ge=0, le=100)


class RecommendationRead(BaseModel):
    id: UUID
    shipment_id: str
    ts: datetime
    action: Action
    target_hub_id: UUID | None
    rsl_at_arrival: float | None
    score: float | None
    net_value: float
    baseline_value: float
    saving: float
    co2e_avoided: float
    rationale: str
    scoring_breakdown: dict[str, Any]
    status: RecommendationStatus
    model_config = ConfigDict(from_attributes=True)


class ScenarioIn(BaseModel):
    shipment_id: str
    scenario: str = Field(pattern="^(normal|compressor_failure|door_open|heatwave|freeze|sensor_dropout)$")
    duration_minutes: int = Field(default=10, ge=1, le=1440)


class ForecastRead(BaseModel):
    shipment_id: str
    as_of: datetime
    rsl_h: float
    rsl_pct: float
    tts_optimistic_h: float
    tts_expected_h: float
    tts_pessimistic_h: float
    mkt_c: float | None
    health: Health
