"""Create an idempotent illustrative catalog and live-dashboard demo dataset."""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .ingestion_service import ingest_reading
from .models import AuditLog, Hub, Product, Recommendation, Shipment, Telemetry
from .schemas import TelemetryIn

PRODUCTS = [
    dict(name="Illustrative cold vaccine", category="PHARMA", model_type="ARRHENIUS",
         ea_kj_mol=80, t_ref_c=5, l0_hours=720, min_temp_c=2, max_temp_c=8,
         hard_stop_rules={"freeze_cutoff_c": 0, "max_excursion_mins": 30,
                          "ceiling_temp_c": 25}, unit_value=18, co2e_per_kg=4.2),
    dict(name="Illustrative insulin", category="PHARMA", model_type="ARRHENIUS",
         ea_kj_mol=70, t_ref_c=5, l0_hours=1000, min_temp_c=2, max_temp_c=8,
         hard_stop_rules={"freeze_cutoff_c": 0}, unit_value=25, co2e_per_kg=5.0),
    dict(name="Leafy greens", category="PRODUCE", model_type="Q10", q10=2.5,
         t_ref_c=2, l0_hours=168, min_temp_c=0, max_temp_c=5,
         hard_stop_rules={}, unit_value=3, co2e_per_kg=2.0),
    dict(name="Berries", category="PRODUCE", model_type="Q10", q10=3.0,
         t_ref_c=1, l0_hours=120, min_temp_c=0, max_temp_c=4,
         hard_stop_rules={}, unit_value=5, co2e_per_kg=1.8),
    dict(name="Dairy", category="DAIRY", model_type="ARRHENIUS", ea_kj_mol=60,
         t_ref_c=4, l0_hours=336, min_temp_c=1, max_temp_c=6,
         hard_stop_rules={"freeze_cutoff_c": 0}, unit_value=2, co2e_per_kg=1.4),
]

HUBS = [
    dict(name="Kanpur Cold Hub", type="DISTRIBUTION", lat=26.4499, lon=80.3319,
         capacity_kg=12000, accepted_categories=["PHARMA", "PRODUCE", "DAIRY", "BIOLOGIC"],
         demand_index=.8, price_ratio=1.0, min_sellable_life_pct=10),
    dict(name="Lucknow Retail Hub", type="RETAIL", lat=26.8467, lon=80.9462,
         capacity_kg=8000, accepted_categories=["PRODUCE", "DAIRY"], demand_index=.92,
         price_ratio=1.08, min_sellable_life_pct=15),
    dict(name="Unnao Clearance Hub", type="CLEARANCE", lat=26.5471, lon=80.4878,
         capacity_kg=3000, accepted_categories=["PRODUCE", "DAIRY"], demand_index=.6,
         price_ratio=.7, min_sellable_life_pct=3),
]

DEMO_SHIPMENTS = [
    {"id": "SZ-DEMO-1042", "product": "Illustrative cold vaccine", "kg": 420,
     "value": 7560, "lat": 26.4499, "lon": 80.3319, "temp": 5.1, "hub": "Kanpur Cold Hub"},
    {"id": "SZ-DEMO-1058", "product": "Berries", "kg": 860,
     "value": 4300, "lat": 26.6200, "lon": 80.4900, "temp": 3.2, "hub": "Lucknow Retail Hub"},
    {"id": "SZ-DEMO-1081", "product": "Illustrative insulin", "kg": 240,
     "value": 6000, "lat": 26.7300, "lon": 80.6600, "temp": 5.0, "hub": "Kanpur Cold Hub"},
    {"id": "SZ-DEMO-1093", "product": "Leafy greens", "kg": 620,
     "value": 1860, "lat": 26.5400, "lon": 80.2900, "temp": 3.0, "hub": "Unnao Clearance Hub"},
    {"id": "SZ-DEMO-1106", "product": "Dairy", "kg": 510,
     "value": 1020, "lat": 26.5700, "lon": 80.5300, "temp": 4.1, "hub": "Kanpur Cold Hub"},
]


async def seed() -> None:
    """Initialize catalog, demo shipments, sensor history and one approved decision.

    Every record is keyed or checked before insertion, so the command is safe to rerun.
    Demo values are illustrative and must not be used for real product quality decisions.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Demo seed: database tables ready", flush=True)

    async with SessionLocal() as session:
        for payload in PRODUCTS:
            exists = await session.scalar(select(Product.id).where(Product.name == payload["name"]))
            if not exists:
                session.add(Product(**payload))
        for payload in HUBS:
            exists = await session.scalar(select(Hub.id).where(Hub.name == payload["name"]))
            if not exists:
                session.add(Hub(**payload))
        await session.commit()
        print("Demo seed: product catalog and hubs ready", flush=True)

        products = {item.name: item for item in (await session.scalars(select(Product))).all()}
        hubs = {item.name: item for item in (await session.scalars(select(Hub))).all()}
        created_ids: list[str] = []
        for item in DEMO_SHIPMENTS:
            if not await session.get(Shipment, item["id"]):
                product = products[item["product"]]
                destination = hubs[item["hub"]]
                session.add(Shipment(
                    id=item["id"], product_id=product.id, batch_no=f"DEMO-{item['id'][-4:]}",
                    quantity_kg=item["kg"], units=max(1, int(item["kg"])), value=item["value"],
                    planned_eta=datetime.now(timezone.utc) + timedelta(hours=5),
                    destination_id=destination.id, current_lat=item["lat"], current_lon=item["lon"],
                    status="REROUTED" if item["id"] == "SZ-DEMO-1058" else "ACTIVE",
                ))
                created_ids.append(item["id"])
        await session.commit()
        print("Demo seed: shipment records ready", flush=True)

        # Seed a short, ordered sensor history through the real ingestion pipeline so
        # state snapshots, audit events and WebSocket state use production code paths.
        for item in DEMO_SHIPMENTS:
            first_reading = await session.scalar(select(Telemetry.ts).where(
                Telemetry.shipment_id == item["id"]).limit(1))
            if first_reading is not None:
                continue
            product = products[item["product"]]
            now = datetime.now(timezone.utc)
            for point in range(8):
                ts = now - timedelta(minutes=(7 - point) * 5)
                temp = item["temp"] + (0.08 if point % 2 else -0.08)
                await ingest_reading(session, TelemetryIn(
                    shipment_id=item["id"], ts=ts, temp_c=temp,
                    humidity=68 + point % 5, lat=item["lat"], lon=item["lon"],
                    door_open=False, battery_pct=96 - point,
                ))
            print(f"Demo seed: telemetry ready for {item['id']}", flush=True)

        # Populate ROI metrics with one clearly labeled sample decision.
        berry_id = "SZ-DEMO-1058"
        sample_recommendation = await session.scalar(select(Recommendation.id).where(
            Recommendation.shipment_id == berry_id,
            Recommendation.rationale.startswith("Demo record:"),
        ).limit(1))
        if sample_recommendation is None:
            hub = hubs["Lucknow Retail Hub"]
            session.add(Recommendation(
                shipment_id=berry_id, action="REROUTE", target_hub_id=hub.id,
                rsl_at_arrival=112, score=.82, baseline_value=4300, net_value=8500,
                saving=4200, co2e_avoided=38,
                rationale="Demo record: divert 860 kg of berries to Lucknow Retail Hub while the load remains within its modeled sellable life.",
                scoring_breakdown={"demo_seed": True, "demand_score": .92,
                                   "remaining_life_ratio": .93, "price_ratio": 1.08},
                status="APPROVED",
            ))
            session.add(AuditLog(actor="demo_seed", event_type="demo_recommendation_approved",
                payload={"shipment_id": berry_id, "action": "REROUTE", "sample": True}))
            await session.commit()

    await engine.dispose()
    print(f"SupplyZero demo data ready: {len(DEMO_SHIPMENTS)} shipments; added {len(created_ids)} new shipments.")


if __name__ == "__main__":
    asyncio.run(seed())
