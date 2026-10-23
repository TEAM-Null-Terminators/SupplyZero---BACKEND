"""Publish repeatable demo telemetry scenarios to SupplyZero's MQTT topic."""
import argparse
import asyncio
import json
import math
import random
from datetime import datetime, timezone

import aiomqtt

from .config import get_settings


async def run(shipment_id: str, scenario: str, count: int, interval: float,
              lat: float, lon: float, seed: int = 7):
    settings = get_settings()
    rng = random.Random(seed)
    setpoint = 5.0
    if scenario not in {"normal", "compressor_failure", "door_open", "heatwave", "freeze", "sensor_dropout"}:
        raise ValueError(f"Unknown scenario: {scenario}")
    async with aiomqtt.Client(hostname=settings.mqtt_host, port=settings.mqtt_port,
        username=settings.mqtt_username, password=settings.mqtt_password) as client:
        for i in range(count):
            effect = {"normal": 0, "compressor_failure": min(i, 8) * 1.2,
                      "door_open": 13 if i % 5 < 2 else 0,
                      "heatwave": min(i, 10) * 0.6, "freeze": -7,
                      "sensor_dropout": 0}[scenario]
            temp = setpoint + effect + rng.uniform(-0.25, 0.25)
            if scenario != "sensor_dropout":
                payload = {"shipment_id": shipment_id, "ts": datetime.now(timezone.utc).isoformat(),
                    "temp_c": round(temp, 3), "humidity": round(65 + rng.uniform(-2, 2), 2),
                    "lat": lat + math.sin(i / 10) * 0.01, "lon": lon + i * 0.001,
                    "door_open": scenario == "door_open" and i % 5 < 2, "battery_pct": 95}
                await client.publish(f"supplyzero/shipments/{shipment_id}/telemetry",
                    json.dumps(payload), qos=1)
            await asyncio.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shipment", default="SZ-DEMO-001")
    parser.add_argument("--scenario", choices=["normal", "compressor_failure", "door_open",
        "heatwave", "freeze", "sensor_dropout"], default="normal")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--lat", type=float, default=26.4499)
    parser.add_argument("--lon", type=float, default=80.3319)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    asyncio.run(run(args.shipment, args.scenario, args.count, args.interval,
                    args.lat, args.lon, args.seed))


if __name__ == "__main__":
    main()
