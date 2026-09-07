"""Evaluation Framework: Synthetic & Deterministic Hazard Benchmarks.

STATUS: SYNTHETIC/DETERMINISTIC EVALUATION
This suite evaluates deterministic hazard model outputs against synthetic test fixture ground-truth expectations.
It records:
  - input fixture
  - target hazard
  - expected classification
  - actual classification
  - severity
  - confidence
  - model_version
  - match status

NOTE: These tests do NOT represent real-world empirical validation or historical disaster calibration.
They verify deterministic consistency against engineering scenario specifications.
"""

import json
from pathlib import Path
from typing import NamedTuple, List, Optional
import pytest

from intelligence.core.validation.validator import TelemetryValidator
from intelligence.hazards.engine import HazardEngine
from intelligence.hazards.types import HazardType, HazardClassification, HazardStatus

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class BenchmarkScenario(NamedTuple):
    fixture_name: str
    target_hazard: HazardType
    expected_status: HazardStatus
    expected_classification: Optional[HazardClassification]
    min_severity: float
    max_severity: float


BENCHMARK_SUITE: List[BenchmarkScenario] = [
    # 1. Normal Conditions
    BenchmarkScenario(
        fixture_name="normal_telemetry.json",
        target_hazard=HazardType.HEAT,
        expected_status=HazardStatus.NOT_DETECTED,
        expected_classification=HazardClassification.NORMAL,
        min_severity=0.0,
        max_severity=0.20,
    ),
    BenchmarkScenario(
        fixture_name="normal_telemetry.json",
        target_hazard=HazardType.FLOOD,
        expected_status=HazardStatus.NOT_DETECTED,
        expected_classification=HazardClassification.NORMAL,
        min_severity=0.0,
        max_severity=0.20,
    ),
    BenchmarkScenario(
        fixture_name="normal_telemetry.json",
        target_hazard=HazardType.DROUGHT,
        expected_status=HazardStatus.NOT_DETECTED,
        expected_classification=HazardClassification.NORMAL,
        min_severity=0.0,
        max_severity=0.20,
    ),
    # 2. Heat Scenarios
    BenchmarkScenario(
        fixture_name="heat_moderate_telemetry.json",
        target_hazard=HazardType.HEAT,
        expected_status=HazardStatus.DETECTED,
        expected_classification=HazardClassification.MODERATE,
        min_severity=0.40,
        max_severity=0.60,
    ),
    BenchmarkScenario(
        fixture_name="heat_critical_telemetry.json",
        target_hazard=HazardType.HEAT,
        expected_status=HazardStatus.DETECTED,
        expected_classification=HazardClassification.CRITICAL,
        min_severity=0.80,
        max_severity=1.00,
    ),
    # 3. Flood Scenarios
    BenchmarkScenario(
        fixture_name="flood_moderate_telemetry.json",
        target_hazard=HazardType.FLOOD,
        expected_status=HazardStatus.DETECTED,
        expected_classification=HazardClassification.MODERATE,
        min_severity=0.40,
        max_severity=0.60,
    ),
    BenchmarkScenario(
        fixture_name="flood_critical_telemetry.json",
        target_hazard=HazardType.FLOOD,
        expected_status=HazardStatus.DETECTED,
        expected_classification=HazardClassification.CRITICAL,
        min_severity=0.80,
        max_severity=1.00,
    ),
    # 4. Drought Scenarios
    BenchmarkScenario(
        fixture_name="drought_moderate_telemetry.json",
        target_hazard=HazardType.DROUGHT,
        expected_status=HazardStatus.DETECTED,
        expected_classification=HazardClassification.MODERATE,
        min_severity=0.40,
        max_severity=0.60,
    ),
    BenchmarkScenario(
        fixture_name="drought_critical_telemetry.json",
        target_hazard=HazardType.DROUGHT,
        expected_status=HazardStatus.DETECTED,
        expected_classification=HazardClassification.CRITICAL,
        min_severity=0.80,
        max_severity=1.00,
    ),
    # 5. Missing sensor scenarios
    BenchmarkScenario(
        fixture_name="missing_sensor_telemetry.json",
        target_hazard=HazardType.FLOOD,
        expected_status=HazardStatus.UNAVAILABLE,
        expected_classification=None,
        min_severity=0.0,
        max_severity=0.0,
    ),
]


def load_fixture_telemetry(filename: str):
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    is_valid, telemetry, err = TelemetryValidator.validate_dict(data)
    assert is_valid and telemetry is not None, f"Failed to load fixture {filename}: {err}"
    return telemetry


@pytest.mark.parametrize("scenario", BENCHMARK_SUITE, ids=lambda s: f"{s.fixture_name}_{s.target_hazard.value}")
def test_deterministic_hazard_benchmarks(scenario: BenchmarkScenario):
    engine = HazardEngine()
    telemetry = load_fixture_telemetry(scenario.fixture_name)
    results = engine.evaluate_telemetry(telemetry, hazard_types=[scenario.target_hazard])

    assert len(results) == 1
    res = results[0]

    # Forensic audit record
    audit_record = {
        "fixture": scenario.fixture_name,
        "hazard": scenario.target_hazard.value,
        "expected_status": scenario.expected_status.value,
        "actual_status": res.status.value,
        "expected_classification": scenario.expected_classification.value if scenario.expected_classification else None,
        "actual_classification": res.classification.value if res.classification else None,
        "severity": res.severity,
        "confidence": res.confidence,
        "model_version": res.model_version,
    }

    assert res.status == scenario.expected_status, f"Status mismatch in {audit_record}"
    assert res.classification == scenario.expected_classification, f"Classification mismatch in {audit_record}"
    assert scenario.min_severity <= res.severity <= scenario.max_severity, (
        f"Severity {res.severity} out of expected range [{scenario.min_severity}, {scenario.max_severity}] in {audit_record}"
    )
    assert 0.0 <= res.confidence <= 1.0
    assert res.forecast_horizon_minutes == 0
    assert res.simulated is False
