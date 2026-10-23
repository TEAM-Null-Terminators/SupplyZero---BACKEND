from dataclasses import dataclass
from typing import Any

from .decay_engine import rate_factor
from .domain import Action, ProductCategory
from .models import Hub, Product, Shipment
from .routing import RouteClient


@dataclass(frozen=True)
class Decision:
    action: Action
    target_hub_id: Any | None
    rsl_at_arrival: float | None
    score: float | None
    net_value: float
    baseline_value: float
    saving: float
    co2e_avoided: float
    rationale: str
    scoring_breakdown: dict[str, Any]


WEIGHTS = {"demand": 0.35, "remaining_life": 0.25, "price": 0.20,
           "extra_cost": 0.10, "extra_emissions": 0.10}


async def choose_action(shipment: Shipment, product: Product, state: Any,
                        hubs: list[Hub], route_client: RouteClient, *,
                        safety_margin_h: float = 2.0,
                        planned_eta_h: float | None = None,
                        hard_stop: bool = False) -> Decision:
    """All ranking and value arithmetic is deterministic Python policy logic."""
    if hard_stop and product.category == ProductCategory.PHARMA.value:
        return Decision(Action.QUARANTINE, None, None, None, 0, shipment.value,
                        -shipment.value, 0, "Pharma hard-stop breached; quarantine for QA review.",
                        {"hard_stop": True, "pharma_override": True})
    at_risk = hard_stop or state.tts_expected_h < (planned_eta_h or 0) + safety_margin_h or state.rsl_pct < 30
    if not at_risk:
        return Decision(Action.CONTINUE, None, None, None, shipment.value, shipment.value,
                        0, 0, "Shipment remains within its expected delivery life and safety margin.",
                        {"at_risk": False})
    if shipment.current_lat is None or shipment.current_lon is None:
        return Decision(Action.CLEARANCE, None, None, None, 0, shipment.value, -shipment.value,
                        0, "Shipment is at risk and has no position for hub routing; review clearance options.",
                        {"at_risk": True, "routing_unavailable": True})
    rate = rate_factor(state.mkt_c if state.mkt_c is not None else product.t_ref_c,
        model_type=product.model_type, t_ref_c=product.t_ref_c,
        ea_kj_mol=product.ea_kj_mol, q10=product.q10)
    nearest = [hub for hub in sorted(hubs, key=lambda h: (h.lat - shipment.current_lat) ** 2 +
                      (h.lon - shipment.current_lon) ** 2)[:8]
               if product.category in (hub.accepted_categories or []) and
               hub.capacity_kg >= shipment.quantity_kg]
    routes = await route_client.route_many((shipment.current_lat, shipment.current_lon),
        [(hub.lat, hub.lon) for hub in nearest])
    candidates = []
    for hub, route in zip(nearest, routes, strict=True):
        rsl_arrival = state.rsl_h - route["duration_h"] * rate
        if rsl_arrival < product.l0_hours * hub.min_sellable_life_pct / 100 + safety_margin_h:
            continue
        extra_distance = max(0.0, route["distance_km"] - 1.0)
        extra_cost = extra_distance * 0.08
        extra_emissions = extra_distance * shipment.quantity_kg * 0.00012
        norm_cost, norm_emissions = min(extra_cost / 100.0, 1), min(extra_emissions / 100.0, 1)
        life_score = max(0.0, min(1.0, rsl_arrival / product.l0_hours))
        score = (WEIGHTS["demand"] * hub.demand_index + WEIGHTS["remaining_life"] * life_score
                 + WEIGHTS["price"] * hub.price_ratio - WEIGHTS["extra_cost"] * norm_cost
                 - WEIGHTS["extra_emissions"] * norm_emissions)
        baseline = shipment.value if state.rsl_h > (planned_eta_h or 0) * rate else 0.0
        net = shipment.units * product.unit_value * hub.price_ratio - extra_cost
        candidates.append((score, hub, rsl_arrival, net, baseline, extra_emissions, route,
                           {"demand": hub.demand_index, "remaining_life": life_score,
                            "price_ratio": hub.price_ratio, "extra_cost": extra_cost,
                            "extra_emissions": extra_emissions, "route_fallback": route["fallback"]}))
    if candidates:
        score, hub, arrival, net, baseline, emissions, route, breakdown = max(
            candidates, key=lambda c: (c[0], str(c[1].id)))
        saving = net - baseline
        if saving > 0:
            return Decision(Action.REROUTE, hub.id, arrival, score, net, baseline, saving,
                max(0.0, shipment.quantity_kg * product.co2e_per_kg *
                    (1.0 - arrival / product.l0_hours) - emissions),
                f"Reroute to {hub.name}: it has capacity and demand, with {arrival:.1f} reference-life hours expected on arrival.",
                {"selected": breakdown, "candidate_count": len(candidates), "weights": WEIGHTS})
    return Decision(Action.CLEARANCE, None, None, None, shipment.value * 0.5, shipment.value,
        -shipment.value * 0.5, 0, "No feasible positive-value cold-chain hub; use an approved clearance channel or QA review.",
        {"at_risk": True, "feasible_hubs": len(candidates)})
