"""
Contract tests for Phase 10 Calibration schemas.
"""

import pytest
from intelligence.calibration.types import (
    CalibratedOutput,
    CalibrationMethod,
    CalibrationReport,
    CalibrationRunRequest,
    ReliabilityBin,
)


def test_calibration_method_enum():
    assert CalibrationMethod.PLATT_SCALING.value == "platt_scaling"
    assert CalibrationMethod.ISOTONIC.value == "isotonic"


def test_reliability_bin_schema():
    bin_obj = ReliabilityBin(
        bin_index=0,
        lower_bound=0.0,
        upper_bound=0.1,
        mean_predicted_prob=0.05,
        empirical_accuracy=0.04,
        sample_count=25,
        calibration_gap=0.01,
    )
    assert bin_obj.bin_index == 0
    assert bin_obj.calibration_gap == 0.01
    assert bin_obj.sample_count == 25


def test_calibration_report_schema():
    rep = CalibrationReport(
        calibration_id="CAL-001",
        model_version="flood-v1",
        method=CalibrationMethod.ISOTONIC,
        dataset_id="DATA-CAL-001",
        sample_count=80,
        status="CALIBRATED",
        brier_score_before=0.15,
        brier_score_after=0.08,
        ece_before=0.12,
        ece_after=0.03,
        provenance_hash="d" * 64,
    )
    assert rep.status == "CALIBRATED"
    assert rep.brier_score_after < rep.brier_score_before


def test_calibrated_output_preserves_raw_value():
    out = CalibratedOutput(
        calibration_id="CAL-001",
        model_version="flood-v1",
        method=CalibrationMethod.ISOTONIC,
        raw_value=0.82,
        calibrated_value=0.74,
        calibration_dataset="DATA-CAL-001",
        provenance_hash="e" * 64,
    )
    # RAW VALUE MUST NOT BE LOST
    assert out.raw_value == 0.82
    assert out.calibrated_value == 0.74


def test_calibrated_output_bounds():
    with pytest.raises(ValueError):
        CalibratedOutput(
            calibration_id="CAL-001",
            model_version="flood-v1",
            method=CalibrationMethod.ISOTONIC,
            raw_value=0.82,
            calibrated_value=1.50,  # Invalid probability > 1.0
            calibration_dataset="DATA-CAL-001",
            provenance_hash="e" * 64,
        )


def test_calibration_run_request():
    req = CalibrationRunRequest(
        model_version="heat-v1",
        dataset_id="EVAL-HEAT-SYNTHETIC-001",
    )
    assert req.method == CalibrationMethod.ISOTONIC
    assert req.dataset_id == "EVAL-HEAT-SYNTHETIC-001"
