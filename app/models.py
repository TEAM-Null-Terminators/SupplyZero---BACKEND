from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .domain import Action, Health, ModelType, ProductCategory, RecommendationStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    model_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ea_kj_mol: Mapped[float | None] = mapped_column(Float)
    q10: Mapped[float | None] = mapped_column(Float)
    t_ref_c: Mapped[float] = mapped_column(Float, nullable=False)
    l0_hours: Mapped[float] = mapped_column(Float, nullable=False)
    min_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    max_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    hard_stop_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    unit_value: Mapped[float] = mapped_column(Float, default=0)
    co2e_per_kg: Mapped[float] = mapped_column(Float, default=0)


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(100))
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    units: Mapped[int] = mapped_column(Integer, default=1)
    value: Mapped[float] = mapped_column(Float, default=0)
    planned_eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destination_id: Mapped[UUID | None] = mapped_column(ForeignKey("hubs.id"))
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lon: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (UniqueConstraint("shipment_id", "ts", name="uq_telemetry_shipment_ts"),
                      Index("ix_telemetry_shipment_ts", "shipment_id", "ts"))
    # Timescale partition key must be part of every unique key.
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float | None] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    door_open: Mapped[bool] = mapped_column(Boolean, default=False)
    battery_pct: Mapped[int | None] = mapped_column(Integer)


class ShelfLifeState(Base):
    __tablename__ = "shelf_life_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    life_consumed_h: Mapped[float] = mapped_column(Float, nullable=False)
    rsl_h: Mapped[float] = mapped_column(Float, nullable=False)
    rsl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    mkt_c: Mapped[float | None] = mapped_column(Float)
    tts_expected_h: Mapped[float] = mapped_column(Float, nullable=False)
    tts_optimistic_h: Mapped[float] = mapped_column(Float, nullable=False)
    tts_pessimistic_h: Mapped[float] = mapped_column(Float, nullable=False)
    health: Mapped[str] = mapped_column(String(10), nullable=False)
    hard_stop: Mapped[bool] = mapped_column(Boolean, default=False)


class ExcursionEvent(Base):
    __tablename__ = "excursion_events"
    __table_args__ = (UniqueConstraint("shipment_id", "start_ts", "end_ts",
                                      name="uq_excursion_shipment_window"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    peak_temp: Mapped[float] = mapped_column(Float)
    duration_min: Mapped[float] = mapped_column(Float)
    life_consumed_h: Mapped[float] = mapped_column(Float)
    rule_breached: Mapped[str | None] = mapped_column(String(160))


class Hub(Base):
    __tablename__ = "hubs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[str] = mapped_column(String(30), default="DISTRIBUTION")
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    accepted_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    demand_index: Mapped[float] = mapped_column(Float, default=0.5)
    price_ratio: Mapped[float] = mapped_column(Float, default=1)
    min_sellable_life_pct: Mapped[float] = mapped_column(Float, default=0)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    target_hub_id: Mapped[UUID | None] = mapped_column(ForeignKey("hubs.id"))
    rsl_at_arrival: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    net_value: Mapped[float] = mapped_column(Float, default=0)
    baseline_value: Mapped[float] = mapped_column(Float, default=0)
    saving: Mapped[float] = mapped_column(Float, default=0)
    co2e_avoided: Mapped[float] = mapped_column(Float, default=0)
    rationale: Mapped[str] = mapped_column(String(1000))
    scoring_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=RecommendationStatus.PENDING.value)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(100), default="system")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
