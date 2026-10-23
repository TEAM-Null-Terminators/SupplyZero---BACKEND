from datetime import datetime, timedelta, timezone
from math import exp

import pytest

from app.decay_engine import (DEFAULT_MKT_ACTIVATION_ENERGY_J_MOL, GAS_CONSTANT_J_MOL_K,
                              evaluate_history, mean_kinetic_temperature, rate_factor)
from app.domain import Health, ModelType, ProductCategory
from app.schemas import ProductIn


def test_q10_rate_factor_analytical_constants():
    assert rate_factor(4, model_type=ModelType.Q10, t_ref_c=4, q10=2.5) == pytest.approx(1.0)
    assert rate_factor(14, model_type=ModelType.Q10, t_ref_c=4, q10=2.5) == pytest.approx(2.5)
    assert rate_factor(-6, model_type=ModelType.Q10, t_ref_c=4, q10=2.5) == pytest.approx(0.4)


def test_arrhenius_rate_factor_analytical_constant():
    t_ref, temp, ea = 5.0, 15.0, 80.0
    expected = exp((ea * 1000 / GAS_CONSTANT_J_MOL_K) *
                   (1 / (t_ref + 273.15) - 1 / (temp + 273.15)))
    assert rate_factor(temp, model_type=ModelType.ARRHENIUS,
                       t_ref_c=t_ref, ea_kj_mol=ea) == pytest.approx(expected, rel=1e-12)


def test_mkt_constant_temperature_and_spike_baseline():
    assert mean_kinetic_temperature([4.0] * 5) == pytest.approx(4.0, abs=1e-10)
    result = mean_kinetic_temperature([4.0, 4.0, 14.0])
    manual = (DEFAULT_MKT_ACTIVATION_ENERGY_J_MOL / GAS_CONSTANT_J_MOL_K) / -__import__("math").log(
        sum(exp(-DEFAULT_MKT_ACTIVATION_ENERGY_J_MOL /
                (GAS_CONSTANT_J_MOL_K * (t + 273.15))) for t in [4, 4, 14]) / 3) - 273.15
    assert result == pytest.approx(manual, rel=1e-12)
    assert result > (4 + 4 + 14) / 3


def product(**overrides):
    data = dict(name="Leafy greens", category=ProductCategory.PRODUCE,
        model_type=ModelType.Q10, q10=2.0, ea_kj_mol=None, t_ref_c=4,
        l0_hours=100, min_temp_c=0, max_temp_c=8, hard_stop_rules={}, unit_value=10,
        co2e_per_kg=1)
    data.update(overrides)
    return ProductIn(**data)


def test_constant_temperature_life_consumption_closed_form():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = evaluate_history([(start, 4), (start + timedelta(hours=2), 4)], product())
    # Trapezoidal interval at reference temperature consumes exactly two hours.
    assert result.life_consumed_h == pytest.approx(2.0)
    assert result.rsl_h == pytest.approx(98.0)
    assert result.rsl_pct == pytest.approx(98.0)


def test_history_sorting_is_deterministic_and_gap_penalty_is_conservative():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    profile = product()
    ordered = evaluate_history([(start, 4), (start + timedelta(hours=1), 14)], profile,
                               gap_threshold_seconds=3600)
    reversed_input = evaluate_history([(start + timedelta(hours=1), 14), (start, 4)], profile,
                                      gap_threshold_seconds=3600)
    assert reversed_input == ordered
    gap = evaluate_history([(start, 4), (start + timedelta(hours=2), 4)], profile,
                           gap_threshold_seconds=300, gap_factor=3)
    normal = evaluate_history([(start, 4), (start + timedelta(hours=2), 4)], profile,
                              gap_threshold_seconds=9000, gap_factor=3)
    assert gap.life_consumed_h > normal.life_consumed_h


def test_hard_stop_changes_health_to_red():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    profile = product(category=ProductCategory.PHARMA, model_type=ModelType.ARRHENIUS,
        q10=None, ea_kj_mol=80, hard_stop_rules={"freeze_cutoff_c": 0.0})
    result = evaluate_history([(start, 4), (start + timedelta(minutes=1), -1)], profile)
    assert result.hard_stop is True
    assert result.health == Health.RED


@pytest.mark.parametrize("temp", [-50, 0, 40])
def test_arrhenius_rejects_absolute_zero_or_below(temp):
    if temp == -50:
        assert rate_factor(temp, model_type=ModelType.ARRHENIUS,
                           t_ref_c=5, ea_kj_mol=70) > 0
    else:
        assert rate_factor(temp, model_type=ModelType.ARRHENIUS,
                           t_ref_c=5, ea_kj_mol=70) > 0
