import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import Base, SessionLocal, engine, get_session
from .domain import RecommendationStatus
from .ingestion_service import ingest_reading, mqtt_worker
from .models import AuditLog, ExcursionEvent, Hub, Product, Recommendation, Shipment, ShelfLifeState, Telemetry
from .routing import RouteClient
from .schemas import HubIn, ProductIn, ProductRead, ScenarioIn, ShipmentIn, TelemetryIn
from .websocket_manager import manager, websocket_sender

logging.basicConfig(level=logging.INFO)
structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level, structlog.processors.JSONRenderer()])
logger = structlog.get_logger()
settings = get_settings()
redis_client: Redis | None = None
mqtt_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, mqtt_task
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
    except Exception:
        logger.warning("redis_unavailable_using_in_process_fanout")
        if redis_client:
            await redis_client.aclose()
        redis_client = None
    if settings.mqtt_enabled:
        mqtt_task = asyncio.create_task(mqtt_worker(SessionLocal), name="supplyzero-mqtt")
    try:
        yield
    finally:
        if mqtt_task:
            mqtt_task.cancel()
            try:
                await mqtt_task
            except asyncio.CancelledError:
                pass
        if redis_client:
            await redis_client.aclose()
        await engine.dispose()


app = FastAPI(title="SupplyZero API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "mqtt_enabled": settings.mqtt_enabled, "redis": redis_client is not None}


@app.post("/api/products", response_model=ProductRead, status_code=201)
async def create_product(body: ProductIn, session: AsyncSession = Depends(get_session)):
    product = Product(**body.model_dump(mode="json"))
    product.category, product.model_type = body.category.value, body.model_type.value
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@app.get("/api/products", response_model=list[ProductRead])
async def list_products(session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(Product).order_by(Product.name))).all()


@app.post("/api/shipments", status_code=201)
async def create_shipment(body: ShipmentIn, session: AsyncSession = Depends(get_session)):
    if not await session.get(Product, body.product_id):
        raise HTTPException(404, "Product not found")
    if await session.get(Shipment, body.id):
        raise HTTPException(409, "Shipment already exists")
    shipment = Shipment(**body.model_dump())
    session.add(shipment)
    session.add(AuditLog(event_type="shipment_created", payload={"shipment_id": shipment.id}))
    await session.commit()
    return {"id": shipment.id, "status": shipment.status}


@app.get("/api/shipments")
async def list_shipments(session: AsyncSession = Depends(get_session)):
    shipments = (await session.scalars(select(Shipment).order_by(Shipment.id))).all()
    result = []
    for shipment in shipments:
        state = await session.scalar(select(ShelfLifeState).where(
            ShelfLifeState.shipment_id == shipment.id).order_by(ShelfLifeState.ts.desc(),
            ShelfLifeState.id.desc()).limit(1))
        product = await session.get(Product, shipment.product_id)
        latest_reading = await session.scalar(select(Telemetry).where(
            Telemetry.shipment_id == shipment.id).order_by(Telemetry.ts.desc()).limit(1))
        result.append({"id": shipment.id, "product": product.name, "product_id": product.id,
            "category": product.category, "status": shipment.status, "current_temp": latest_reading.temp_c if latest_reading else None,
            "current_lat": shipment.current_lat,
            "current_lon": shipment.current_lon, "quantity_kg": shipment.quantity_kg,
            "state": state})
    return result


@app.get("/api/shipments/{shipment_id}")
async def shipment_detail(shipment_id: str, session: AsyncSession = Depends(get_session)):
    shipment = await session.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    state = await session.scalar(select(ShelfLifeState).where(
        ShelfLifeState.shipment_id == shipment_id).order_by(ShelfLifeState.ts.desc(),
        ShelfLifeState.id.desc()).limit(1))
    excursions = (await session.scalars(select(ExcursionEvent).where(
        ExcursionEvent.shipment_id == shipment_id).order_by(ExcursionEvent.start_ts))).all()
    product = await session.get(Product, shipment.product_id)
    first_reading_ts = await session.scalar(select(Telemetry.ts).where(
        Telemetry.shipment_id == shipment_id).order_by(Telemetry.ts).limit(1))
    nominal_expiry_ts = (first_reading_ts + timedelta(hours=product.l0_hours)
                         if first_reading_ts and product else None)
    return {"shipment": shipment, "state": state, "excursions": excursions,
            "nominal_expiry_ts": nominal_expiry_ts}


@app.get("/api/shipments/{shipment_id}/telemetry")
async def shipment_telemetry(shipment_id: str, start: datetime | None = None,
                             end: datetime | None = None, session: AsyncSession = Depends(get_session)):
    query = select(Telemetry).where(Telemetry.shipment_id == shipment_id)
    if start:
        query = query.where(Telemetry.ts >= start)
    if end:
        query = query.where(Telemetry.ts <= end)
    return (await session.scalars(query.order_by(Telemetry.ts))).all()


@app.get("/api/shipments/{shipment_id}/forecast")
async def forecast(shipment_id: str, session: AsyncSession = Depends(get_session)):
    state = await session.scalar(select(ShelfLifeState).where(
        ShelfLifeState.shipment_id == shipment_id).order_by(ShelfLifeState.ts.desc(),
        ShelfLifeState.id.desc()).limit(1))
    if not state:
        if not await session.get(Shipment, shipment_id):
            raise HTTPException(404, "Shipment not found")
        raise HTTPException(409, "No telemetry available")
    return {"shipment_id": shipment_id, "as_of": state.ts, "rsl_h": state.rsl_h,
        "rsl_pct": state.rsl_pct, "tts_expected_h": state.tts_expected_h,
        "tts_optimistic_h": state.tts_optimistic_h, "tts_pessimistic_h": state.tts_pessimistic_h,
        "mkt_c": state.mkt_c, "health": state.health}


@app.post("/api/hubs", status_code=201)
async def create_hub(body: HubIn, session: AsyncSession = Depends(get_session)):
    hub = Hub(**body.model_dump())
    hub.accepted_categories = [c.value for c in body.accepted_categories]
    session.add(hub)
    await session.commit()
    await session.refresh(hub)
    return hub


@app.get("/api/hubs")
async def list_hubs(session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(Hub).order_by(Hub.name))).all()


@app.get("/api/recommendations")
async def list_recommendations(status: str | None = Query(default=None),
                              session: AsyncSession = Depends(get_session)):
    query = select(Recommendation).order_by(Recommendation.ts.desc())
    if status:
        query = query.where(Recommendation.status == status.upper())
    return (await session.scalars(query)).all()


async def set_recommendation_status(recommendation_id: UUID, status: str,
                                    session: AsyncSession, actor: str = "user"):
    rec = await session.get(Recommendation, recommendation_id)
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    if rec.action == "QUARANTINE" and status == "APPROVED":
        # Approval records QA disposition only; this service never releases pharma product.
        rec.status = status
    elif rec.status != RecommendationStatus.PENDING.value:
        raise HTTPException(409, "Recommendation is no longer pending")
    else:
        rec.status = status
    session.add(AuditLog(actor=actor, event_type=f"recommendation_{status.lower()}",
        payload={"recommendation_id": str(rec.id), "shipment_id": rec.shipment_id,
                 "action": rec.action, "status": status}))
    await session.commit()
    await manager.publish({"type": "action_executed" if status == "APPROVED" else "recommendation",
        "recommendation_id": str(rec.id), "shipment_id": rec.shipment_id, "status": status})
    return {"id": str(rec.id), "status": rec.status}


@app.post("/api/recommendations/{recommendation_id}/approve")
async def approve(recommendation_id: UUID, session: AsyncSession = Depends(get_session)):
    return await set_recommendation_status(recommendation_id, "APPROVED", session)


@app.post("/api/recommendations/{recommendation_id}/reject")
async def reject(recommendation_id: UUID, session: AsyncSession = Depends(get_session)):
    return await set_recommendation_status(recommendation_id, "REJECTED", session)


@app.post("/api/shipments/{shipment_id}/quarantine")
async def quarantine(shipment_id: str, session: AsyncSession = Depends(get_session)):
    shipment = await session.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    shipment.status = "QUARANTINED"
    rec = Recommendation(shipment_id=shipment_id, action="QUARANTINE", status="PENDING",
        rationale="Manual quarantine requested; QA disposition required.",
        scoring_breakdown={"source": "manual"}, net_value=0, baseline_value=shipment.value,
        saving=-shipment.value, co2e_avoided=0)
    session.add_all([rec, AuditLog(actor="user", event_type="shipment_quarantined",
        payload={"shipment_id": shipment_id})])
    await session.commit()
    return {"shipment_id": shipment_id, "status": "QUARANTINED", "recommendation_id": str(rec.id)}


@app.post("/api/sim/scenario")
async def inject_scenario(body: ScenarioIn, session: AsyncSession = Depends(get_session)):
    shipment = await session.get(Shipment, body.shipment_id)
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    state = await session.scalar(select(Telemetry).where(Telemetry.shipment_id == shipment.id)
        .order_by(Telemetry.ts.desc()).limit(1))
    now = datetime.now(timezone.utc)
    base_temp = state.temp_c if state else 5.0
    delta = {"normal": 0, "compressor_failure": 2, "door_open": 12,
             "heatwave": 8, "freeze": -7, "sensor_dropout": 0}[body.scenario]
    if body.scenario == "sensor_dropout":
        await manager.publish({"type": "telemetry_gap", "shipment_id": shipment.id,
                               "duration_minutes": body.duration_minutes})
        return {"scenario": body.scenario, "injected": False, "note": "No reading emitted; gap handling will apply on next reading."}
    payload = TelemetryIn(shipment_id=shipment.id, ts=now, temp_c=base_temp + delta,
        humidity=70, lat=shipment.current_lat, lon=shipment.current_lon,
        door_open=body.scenario == "door_open", battery_pct=90)
    accepted = await ingest_reading(session, payload)
    session.add(AuditLog(event_type="scenario_injected", payload={"shipment_id": shipment.id,
        "scenario": body.scenario, "duration_minutes": body.duration_minutes}))
    await session.commit()
    return {"scenario": body.scenario, "injected": accepted, "temperature_c": payload.temp_c}


@app.get("/api/impact/summary")
async def impact_summary(session: AsyncSession = Depends(get_session)):
    row = (await session.execute(select(func.coalesce(func.sum(Recommendation.saving), 0),
        func.coalesce(func.sum(Recommendation.co2e_avoided), 0),
        func.coalesce(func.sum(Recommendation.baseline_value), 0),
        func.coalesce(func.sum(Recommendation.net_value), 0)).where(
        Recommendation.status.in_(["APPROVED", "AUTO_EXECUTED"])))).one()
    diverted = await session.scalar(select(func.coalesce(func.sum(Shipment.quantity_kg), 0)).where(
        Shipment.status == "REROUTED"))
    return {"value_saved": row[0], "co2e_avoided_kg": row[1], "baseline_value": row[2],
            "supplyzero_value": row[3], "kg_diverted": diverted,
            "currency": "configured product currency"}


@app.get("/api/audit")
async def audit_log(limit: int = Query(default=200, ge=1, le=2000),
                    session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit))).all()


@app.websocket("/ws/stream")
async def stream(websocket: WebSocket):
    queue = await manager.connect(websocket)
    sender = asyncio.create_task(websocket_sender(websocket, queue))
    try:
        while True:
            message = await websocket.receive_text()
            try:
                payload = json.loads(message) if message != "ping" else {}
                if message == "ping" or (isinstance(payload, dict) and payload.get("type") == "ping"):
                    await websocket.send_text('{"type":"pong"}')
            except (ValueError, TypeError):
                continue
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    finally:
        sender.cancel()
