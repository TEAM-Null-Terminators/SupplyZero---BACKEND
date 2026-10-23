"""Pure deterministic kinetic equations and replayable shipment calculations."""

from dataclasses import dataclass
from datetime import datetime
from math import exp, isfinite, log
from typing import Iterable

from .domain import Health, ModelType
from .schemas import ProductIn

GAS_CONSTANT_J_MOL_K = 8.314
DEFAULT_MKT_ACTIVATION_ENERGY_J_MOL = 83_144.0


def rate_factor(temp_c: float, *, model_type: ModelType, t_ref_c: float,
                ea_kj_mol: float | None = None, q10: float | None = None) -> float:
    """Return a dimensionless rate relative to reference temperature."""
    if not all(isfinite(v) for v in (temp_c, t_ref_c)):
        raise ValueError("temperatures must be finite")
    if model_type == ModelType.Q10:
        if q10 is None or q10 <= 0 or not isfinite(q10):
            raise ValueError("q10 must be finite and positive")
        value = q10 ** ((temp_c - t_ref_c) / 10.0)
    else:
        if ea_kj_mol is None or ea_kj_mol <= 0 or not isfinite(ea_kj_mol):
            raise ValueError("ea_kj_mol must be finite and positive")
        tref_k, temp_k = t_ref_c + 273.15, temp_c + 273.15
        if min(tref_k, temp_k) <= 0:
            raise ValueError("temperature must be above absolute zero")
        value = exp((ea_kj_mol * 1000.0 / GAS_CONSTANT_J_MOL_K) *
                    (1.0 / tref_k - 1.0 / temp_k))
    if not isfinite(value):
        raise ValueError("rate factor overflow")
    return value


def mean_kinetic_temperature(temperatures_c: Iterable[float], *,
                            activation_energy_j_mol: float = DEFAULT_MKT_ACTIVATION_ENERGY_J_MOL) -> float | None:
    values = tuple(temperatures_c)
    if not values:
        return None
    if activation_energy_j_mol <= 0 or not isfinite(activation_energy_j_mol):
        raise ValueError("activation energy must be finite and positive")
    kelvin = [t + 273.15 for t in values]
    if any(t <= 0 or not isfinite(t) for t in kelvin):
        raise ValueError("temperatures must be finite and above absolute zero")
    mean_exp = sum(exp(-activation_energy_j_mol / (GAS_CONSTANT_J_MOL_K * t))
                   for t in kelvin) / len(kelvin)
    return (activation_energy_j_mol / GAS_CONSTANT_J_MOL_K) / -log(mean_exp) - 273.15


@dataclass(frozen=True)
class DecayResult:
    life_consumed_h: float
    rsl_h: float
    rsl_pct: float
    mkt_c: float | None
    tts_expected_h: float
    tts_optimistic_h: float
    tts_pessimistic_h: float
    health: Health
    hard_stop: bool


def evaluate_history(readings: Iterable[tuple[datetime, float]], product: ProductIn,
                     *, gap_threshold_seconds: int = 300,
                     gap_factor: float = 3.0,
                     conservative_rate_cap: float = 1000.0) -> DecayResult:
    """Replay readings in timestamp order; gaps consume life at a bounded conservative rate."""
    ordered = sorted(readings, key=lambda row: row[0])
    consumed = 0.0
    temps: list[float] = []
    freeze_minutes = 0.0
    over_limit_minutes = 0.0
    hard_stop = False
    prev: tuple[datetime, float] | None = None
    for ts, temp in ordered:
        temps.append(temp)
        if prev:
            seconds = max(0.0, (ts - prev[0]).total_seconds())
            hours = seconds / 3600.0
            interval_rate = rate_factor((prev[1] + temp) / 2,
                model_type=product.model_type, t_ref_c=product.t_ref_c,
                ea_kj_mol=product.ea_kj_mol, q10=product.q10)
            consumed += hours * interval_rate
            if seconds > gap_threshold_seconds:
                gap_hours = (seconds - gap_threshold_seconds) / 3600.0
                gap_rate = min(rate_factor(prev[1], model_type=product.model_type,
                    t_ref_c=product.t_ref_c, ea_kj_mol=product.ea_kj_mol, q10=product.q10)
                    * gap_factor, conservative_rate_cap)
                consumed += gap_hours * max(0.0, gap_rate - interval_rate)
                temps.append(prev[1])
            freeze_cutoff = float(product.hard_stop_rules.get("freeze_cutoff_c", 0.0))
            freeze_minutes += seconds / 60 if min(prev[1], temp) < freeze_cutoff else 0
            outside = max(prev[1], temp) > product.max_temp_c or min(prev[1], temp) < product.min_temp_c
            over_limit_minutes += seconds / 60 if outside else 0
        prev = (ts, temp)
        rules = product.hard_stop_rules
        freeze_duration_limit = float(rules.get("freeze_cutoff_mins", 0.0))
        if temp < rules.get("freeze_cutoff_c", float("-inf")) and freeze_duration_limit <= 0:
            hard_stop = True
        if temp > rules.get("ceiling_temp_c", float("inf")):
            hard_stop = True
    rules = product.hard_stop_rules
    if freeze_minutes > float(rules.get("freeze_cutoff_mins", float("inf"))):
        hard_stop = True
    if over_limit_minutes > float(rules.get("max_excursion_mins", float("inf"))):
        hard_stop = True
    rsl = max(0.0, product.l0_hours - consumed)
    current = ordered[-1][1] if ordered else product.t_ref_c
    expected_rate = rate_factor(current, model_type=product.model_type,
        t_ref_c=product.t_ref_c, ea_kj_mol=product.ea_kj_mol, q10=product.q10)
    optimistic_rate = rate_factor(current - 2.0, model_type=product.model_type,
        t_ref_c=product.t_ref_c, ea_kj_mol=product.ea_kj_mol, q10=product.q10)
    pessimistic_rate = rate_factor(current + 2.0, model_type=product.model_type,
        t_ref_c=product.t_ref_c, ea_kj_mol=product.ea_kj_mol, q10=product.q10)
    pct = max(0.0, min(100.0, rsl / product.l0_hours * 100.0))
    health = Health.RED if hard_stop or pct < 30 else Health.AMBER if pct < 60 else Health.GREEN
    return DecayResult(consumed, rsl, pct, mean_kinetic_temperature(temps),
        rsl / expected_rate, rsl / optimistic_rate, rsl / pessimistic_rate, health, hard_stop)
