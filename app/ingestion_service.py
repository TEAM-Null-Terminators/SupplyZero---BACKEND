import asyncio
import json
import logging
import weakref
from datetime import datetime, timedelta, timezone

import aiomqtt
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .decision_engine import choose_action
from .decay_engine import evaluate_history
from .domain import ProductCategory
from .models import AuditLog, ExcursionEvent, Hub, Product, Recommendation, Shipment, ShelfLifeState, Telemetry
from .routing import RouteClient
from .schemas import ProductIn, TelemetryIn
from .websocket_manager import manager

logger = logging.getLogger(__name__)
_shipment_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
_redis_client = None
route_client = RouteClient(get_settings().osrm_base_url,
    get_settings().osrm_timeout_seconds, cache_ttl=get_settings().route_cache_ttl_seconds)


def set_route_cache(redis_client) -> None:
    global _redis_client
    _redis_client = redis_client
    route_client.redis = redis_client


def _as_product_input(product: Product) -> ProductIn:
    return ProductIn(name=product.name, category=product.category, model_type=product.model_type,
        ea_kj_mol=product.ea_kj_mol, q10=product.q10, t_ref_c=product.t_ref_c,
        l0_hours=product.l0_hours, min_temp_c=product.min_temp_c, max_temp_c=product.max_temp_c,
        hard_stop_rules=product.hard_stop_rules, unit_value=product.unit_value,
        co2e_per_kg=product.co2e_per_kg)


async def ingest_reading(session: AsyncSession, payload: TelemetryIn) -> bool:
    """Persist once, replay sorted history, and append a snapshot; duplicates are no-ops."""
    lock = _shipment_locks.setdefault(payload.shipment_id, asyncio.Lock())
    async with lock:
        if session.get_bind().dialect.name == "postgresql":
            # Serialize workers handling this shipment through replay and snapshot commit.
            await session.execute(text(
                "SELECT pg_advisory_xact_lock(hashtextextended(:shipment_id, 0))"),
                {"shipment_id": payload.shipment_id})
        shipment = await session.get(Shipment, payload.shipment_id)
        if not shipment:
            logger.warning("telemetry_dead_letter", reason="unknown shipment", shipment_id=payload.shipment_id)
            await session.rollback()
            return False
        existing = await session.scalar(select(Telemetry.ts).where(
            Telemetry.shipment_id == payload.shipment_id, Telemetry.ts == payload.ts))
        if existing is not None:
            return False
        reading = Telemetry(**payload.model_dump())
        session.add(reading)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return False
        readings = (await session.scalars(select(Telemetry).where(
            Telemetry.shipment_id == payload.shipment_id).order_by(Telemetry.ts))).all()
        product = await session.get(Product, shipment.product_id)
        result = evaluate_history(((r.ts, r.temp_c) for r in readings), _as_product_input(product),
            gap_threshold_seconds=get_settings().telemetry_gap_seconds,
            gap_factor=get_settings().gap_degradation_factor)
        latest = readings[-1]
        state = ShelfLifeState(shipment_id=shipment.id, ts=latest.ts,
            life_consumed_h=result.life_consumed_h, rsl_h=result.rsl_h, rsl_pct=result.rsl_pct,
            mkt_c=result.mkt_c, tts_expected_h=result.tts_expected_h,
            tts_optimistic_h=result.tts_optimistic_h, tts_pessimistic_h=result.tts_pessimistic_h,
            health=result.health.value, hard_stop=result.hard_stop)
        session.add(state)
        if product.category == ProductCategory.PHARMA.value and result.hard_stop:
            existing_quarantine = await session.scalar(select(Recommendation.id).where(
                Recommendation.shipment_id == shipment.id, Recommendation.action == "QUARANTINE",
                Recommendation.status == "PENDING").limit(1))
            if existing_quarantine is None:
                rec = Recommendation(shipment_id=shipment.id, action="QUARANTINE", status="PENDING",
                    net_value=0, baseline_value=shipment.value, saving=-shipment.value, co2e_avoided=0,
                    rationale="Pharma hard-stop breached; quarantine for QA review.",
                    scoring_breakdown={"hard_stop": True, "pharma_override": True})
                session.add(rec)
        # Write each closed excursion window once; an active excursion is finalized on recovery.
        excursion_start = None
        excursion_peak = float("-inf")
        excursion_end = None
        closed_excursions = []
        for item in readings:
            outside = item.temp_c < product.min_temp_c or item.temp_c > product.max_temp_c
            if outside:
                if excursion_start is None:
                    excursion_start = item.ts
                    excursion_peak = item.temp_c
                else:
                    excursion_peak = max(excursion_peak, item.temp_c)
                excursion_end = item.ts
            elif excursion_start is not None:
                closed_excursions.append((excursion_start, excursion_end, excursion_peak))
                excursion_start = None
                excursion_peak = float("-inf")
        for excursion_start, excursion_end, excursion_peak in closed_excursions:
            exists = await session.scalar(select(ExcursionEvent.id).where(
                ExcursionEvent.shipment_id == shipment.id,
                ExcursionEvent.start_ts == excursion_start,
                ExcursionEvent.end_ts == excursion_end).limit(1))
            if exists is None:
                duration = max(0.0, (excursion_end - excursion_start).total_seconds() / 60)
                session.add(ExcursionEvent(shipment_id=shipment.id, start_ts=excursion_start,
                    end_ts=excursion_end, peak_temp=excursion_peak, duration_min=duration,
                    life_consumed_h=result.life_consumed_h, rule_breached="temperature_range"))
        if latest.lat is not None and latest.lon is not None:
            shipment.current_lat, shipment.current_lon = latest.lat, latest.lon
        planned_eta_h = None
        if shipment.planned_eta:
            planned_eta_h = max(0.0, (shipment.planned_eta - latest.ts).total_seconds() / 3600)
        at_risk = (result.hard_stop or result.tts_expected_h <
                   (planned_eta_h or 0) + get_settings().safety_margin_hours or result.rsl_pct < 30)
        prior = await session.scalar(select(Recommendation.id).where(
            Recommendation.shipment_id == shipment.id,
            Recommendation.status == "PENDING").limit(1))
        latest_decision = await session.scalar(select(Recommendation).where(
            Recommendation.shipment_id == shipment.id).order_by(Recommendation.ts.desc()).limit(1))
        throttled = bool(latest_decision and latest_decision.action in ("REROUTE", "CLEARANCE")
            and not result.hard_stop and latest_decision.ts > latest.ts - timedelta(minutes=15))
        if at_risk and prior is None and not throttled:
            hubs = (await session.scalars(select(Hub))).all()
            decision = await choose_action(shipment, product, state, list(hubs), route_client,
                safety_margin_h=get_settings().safety_margin_hours,
                planned_eta_h=planned_eta_h, hard_stop=result.hard_stop)
            rec = Recommendation(shipment_id=shipment.id, action=decision.action.value,
                target_hub_id=decision.target_hub_id, rsl_at_arrival=decision.rsl_at_arrival,
                score=decision.score, net_value=decision.net_value,
                baseline_value=decision.baseline_value, saving=decision.saving,
                co2e_avoided=decision.co2e_avoided, rationale=decision.rationale,
                scoring_breakdown=decision.scoring_breakdown,
                status="AUTO_EXECUTED" if get_settings().auto_execute and
                    product.category != ProductCategory.PHARMA.value and
                    decision.action.value in ("REROUTE", "CLEARANCE") else "PENDING")
            session.add(rec)
            session.add(AuditLog(event_type="recommendation_created", payload={
                "recommendation_id": str(rec.id), "shipment_id": shipment.id,
                "action": decision.action.value, "decision": decision.scoring_breakdown}))
        session.add(AuditLog(event_type="telemetry_ingested", payload={"shipment_id": shipment.id,
            "ts": latest.ts.isoformat(), "temperature_c": latest.temp_c,
            "state_rsl_h": result.rsl_h, "health": result.health.value}))
        await session.commit()
        await manager.publish({"type": "state_update", "shipment_id": shipment.id,
            "ts": latest.ts.isoformat(), "rsl_h": result.rsl_h, "rsl_pct": result.rsl_pct,
            "health": result.health.value, "hard_stop": result.hard_stop,
            "temp_c": latest.temp_c, "lat": latest.lat, "lon": latest.lon})
        if result.hard_stop:
            await manager.publish({"type": "risk_alert", "shipment_id": shipment.id,
                                   "reason": "hard_stop", "health": "RED"})
        if at_risk:
            await manager.publish({"type": "risk_alert", "shipment_id": shipment.id,
                                   "reason": "risk_threshold", "health": result.health.value})
        return True


async def mqtt_worker(session_factory, *, stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    stop_event = stop_event or asyncio.Event()
    while not stop_event.is_set():
        try:
            async with aiomqtt.Client(hostname=settings.mqtt_host, port=settings.mqtt_port,
                username=settings.mqtt_username, password=settings.mqtt_password) as client:
                await client.subscribe("supplyzero/shipments/+/telemetry", qos=1)
                async for message in client.messages:
                    try:
                        body = json.loads(message.payload)
                        shipment_from_topic = str(message.topic).split("/")[-2]
                        body.setdefault("shipment_id", shipment_from_topic)
                        payload = TelemetryIn.model_validate(body)
                        async with session_factory() as session:
                            await ingest_reading(session, payload)
                    except Exception as exc:
                        logger.error("telemetry_dead_letter", reason=str(exc), topic=str(message.topic))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mqtt_worker_disconnected")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2)
            except TimeoutError:
                pass
