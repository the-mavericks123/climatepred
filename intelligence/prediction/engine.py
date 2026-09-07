"""Prediction Engine orchestrating temporal feature extraction, deterministic trend forecasting,
authoritative Phase 2 hazard model evaluation, and confidence assessment.
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.core.provenance.tracker import ProvenanceTracker
from intelligence.hazards.types import (
    HazardType,
    HazardStatus,
    HazardClassification,
)
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import HazardQualityGate, QualityGateVerdict
from intelligence.hazards.heat import HeatModel
from intelligence.hazards.flood import FloodModel
from intelligence.hazards.drought import DroughtModel
from intelligence.hazards.thresholds import DEFAULT_CLASSIFICATION_THRESHOLDS
from intelligence.prediction.types import (
    PredictionResult,
    ForecastHorizon,
)
from intelligence.prediction.thresholds import (
    VALID_HORIZONS,
    PredictionConfig,
    DEFAULT_PREDICTION_CONFIG,
)
from intelligence.prediction.features import TemporalFeatureExtractor, TemporalTrendSummary
from intelligence.prediction.models import DeterministicTrendForecaster
from intelligence.prediction.confidence import PredictionConfidenceCalculator
from intelligence.core.logging import get_logger

logger = get_logger(__name__)


class PredictionEngine:
    """
    Orchestrates deterministic forecasting of physical hazard states across 30m, 60m, and 360m horizons.
    Uses Phase 2 hazard models as the authoritative calculation foundation.
    """

    HAZARD_REQUIRED_VARS = {
        HazardType.HEAT: ["temperature", "humidity"],
        HazardType.FLOOD: ["rainfall", "water_level", "soil_moisture"],
        HazardType.DROUGHT: ["soil_moisture", "temperature", "humidity"],
    }

    MODEL_VERSIONS = {
        HazardType.HEAT: "heat-pred-v1",
        HazardType.FLOOD: "flood-pred-v1",
        HazardType.DROUGHT: "drought-pred-v1",
    }

    def __init__(self, config: PredictionConfig = DEFAULT_PREDICTION_CONFIG):
        self.config = config
        self.extractor = TemporalFeatureExtractor(
            max_lookback_hours=config.max_lookback_hours,
            min_observations=config.min_observations,
        )
        self.forecaster = DeterministicTrendForecaster(bounds=config.bounds)
        self.confidence_calculator = PredictionConfidenceCalculator(config=config)

        # Authoritative Phase 2 models
        self.heat_model = HeatModel()
        self.flood_model = FloodModel()
        self.drought_model = DroughtModel()
        self.quality_gate = HazardQualityGate()

    def evaluate_predictions(
        self,
        current_telemetry: NormalizedTelemetry,
        history: List[NormalizedTelemetry],
        requested_hazards: Optional[List[HazardType]] = None,
        requested_horizons: Optional[List[int]] = None,
        now: Optional[datetime] = None,
    ) -> List[PredictionResult]:
        """
        Evaluates future hazard states from current telemetry and chronological history.
        """
        pred_time = now or current_telemetry.timestamp
        pred_time_utc = pred_time if pred_time.tzinfo else pred_time.replace(tzinfo=timezone.utc)

        # 1. Validate requested horizons
        horizons_to_run = requested_horizons if requested_horizons is not None else [30, 60, 360]
        for h in horizons_to_run:
            if h not in VALID_HORIZONS:
                raise ValueError(f"Unsupported prediction horizon: {h}m. Must be one of {sorted(list(VALID_HORIZONS))}")

        # 2. Targets to evaluate
        hazards_to_run = requested_hazards if requested_hazards is not None else [
            HazardType.HEAT,
            HazardType.FLOOD,
            HazardType.DROUGHT,
        ]

        # 3. Extract filtered history and temporal series with strict anti-leakage filter
        filtered_history = self.extractor.extract_filtered_history(
            current=current_telemetry,
            history=history,
            prediction_time=pred_time_utc,
        )

        series_map = self.extractor.extract_series(
            current=current_telemetry,
            history=history,
            prediction_time=pred_time_utc,
        )

        # Compute trend summaries per physical variable
        summaries: Dict[str, TemporalTrendSummary] = {
            var: self.extractor.compute_trend(series) for var, series in series_map.items()
        }

        # Provenance of current input packet
        current_fingerprint = ProvenanceTracker.compute_record_hash(current_telemetry)

        # Provenance of filtered historical observations actually consumed
        history_fingerprint = self._compute_history_fingerprint(filtered_history)

        results: List[PredictionResult] = []

        # Run predictions for each hazard across each horizon
        for horizon in horizons_to_run:
            forecast_time = pred_time_utc + timedelta(minutes=horizon)

            for hazard_type in hazards_to_run:
                pred_result = self._predict_single_hazard(
                    hazard_type=hazard_type,
                    horizon_minutes=horizon,
                    current_telemetry=current_telemetry,
                    pred_time_utc=pred_time_utc,
                    forecast_time=forecast_time,
                    summaries=summaries,
                    current_fingerprint=current_fingerprint,
                    history_fingerprint=history_fingerprint,
                    history_count=len(filtered_history),
                )
                results.append(pred_result)

        return results

    def _predict_single_hazard(
        self,
        hazard_type: HazardType,
        horizon_minutes: int,
        current_telemetry: NormalizedTelemetry,
        pred_time_utc: datetime,
        forecast_time: datetime,
        summaries: Dict[str, TemporalTrendSummary],
        current_fingerprint: str,
        history_fingerprint: str,
        history_count: int,
    ) -> PredictionResult:
        """Evaluates a single hazard for a specific future horizon."""
        req_vars = self.HAZARD_REQUIRED_VARS[hazard_type]
        model_version = self.MODEL_VERSIONS[hazard_type]
        hazard_summaries = [summaries[v] for v in req_vars if v in summaries]

        # Check if any required variable is unobserved / None
        missing_vars = [v for v in req_vars if summaries.get(v) is None or summaries[v].current_value is None]
        if missing_vars:
            provenance_hash = self._compute_prediction_provenance(
                current_fingerprint=current_fingerprint,
                history_fingerprint=history_fingerprint,
                hazard=hazard_type.value,
                horizon=horizon_minutes,
                history_count=history_count,
                model_version=model_version,
            )
            reason_msg = f"Cannot predict {hazard_type.value}: required sensor(s) unavailable ({', '.join(missing_vars)})"
            return PredictionResult(
                prediction_id=f"PRED-{hazard_type.value.upper()}-{current_telemetry.node_id}-{horizon_minutes}M-{int(pred_time_utc.timestamp())}",
                hazard=hazard_type,
                prediction_time=pred_time_utc,
                forecast_time=forecast_time,
                forecast_horizon_minutes=horizon_minutes,
                severity=0.0,
                confidence=0.0,
                classification=None,
                status=HazardStatus.UNAVAILABLE,
                model_version=model_version,
                source_hazard_id=f"HAZ-{hazard_type.value.upper()}-{current_telemetry.node_id}-{int(pred_time_utc.timestamp())}",
                provenance_hash=provenance_hash,
                drivers=[reason_msg],
                data_quality={"reason": reason_msg},
                predicted_features={},
                simulated=False,
                reason=reason_msg,
            )

        # Extrapolate physical variables and collect trend drivers
        extrapolated_features: Dict[str, float] = {}
        forecast_drivers: List[str] = []

        for v in req_vars:
            val, v_drivers = self.forecaster.forecast_variable(summaries[v], horizon_minutes)
            if val is not None:
                extrapolated_features[v] = val
            forecast_drivers.extend(v_drivers)

        # Synthesize HazardFeatures with forecasted environmental values
        synthesized = HazardFeatures(
            node_id=current_telemetry.node_id,
            timestamp=forecast_time,
            location=current_telemetry.location,
            source="prediction_engine",
            valid=current_telemetry.quality.valid,
            confidence_base=current_telemetry.quality.confidence or 1.0,
            anomaly_score=current_telemetry.quality.anomaly_score or 0.0,
            flags=list(current_telemetry.quality.flags),
            temperature_c=extrapolated_features.get("temperature"),
            humidity_pct=extrapolated_features.get("humidity"),
            rainfall_mmhr=extrapolated_features.get("rainfall"),
            soil_moisture_pct=extrapolated_features.get("soil_moisture"),
            water_level_m=extrapolated_features.get("water_level"),
            pressure_hpa=extrapolated_features.get("pressure"),
            air_quality_aqi=extrapolated_features.get("air_quality"),
            provenance_hash=current_fingerprint,
        )

        # Quality check on synthesized features
        gate_verdict = self.quality_gate.verify(synthesized, hazard_type, now=forecast_time)

        # Authoritative Phase 2 model execution
        if hazard_type == HazardType.HEAT:
            hazard_res = self.heat_model.evaluate(synthesized, gate_verdict)
        elif hazard_type == HazardType.FLOOD:
            hazard_res = self.flood_model.evaluate(synthesized, gate_verdict)
        else:  # DROUGHT
            hazard_res = self.drought_model.evaluate(synthesized, gate_verdict)

        # Compute forecast confidence
        base_q_conf = current_telemetry.quality.confidence if current_telemetry.quality.confidence is not None else 1.0
        confidence, data_quality_diag = self.confidence_calculator.compute_confidence(
            summaries=hazard_summaries,
            horizon_minutes=horizon_minutes,
            base_quality_confidence=base_q_conf,
            staleness_penalty_factor=1.0 if not gate_verdict.is_stale else 0.60,
        )

        # Combine forecast drivers and Phase 2 physical drivers
        combined_drivers = forecast_drivers + [f"Predicted impact: {d}" for d in hazard_res.drivers]

        # Compute deterministic provenance hash
        provenance_hash = self._compute_prediction_provenance(
            current_fingerprint=current_fingerprint,
            history_fingerprint=history_fingerprint,
            hazard=hazard_type.value,
            horizon=horizon_minutes,
            history_count=history_count,
            model_version=model_version,
        )

        return PredictionResult(
            prediction_id=f"PRED-{hazard_type.value.upper()}-{current_telemetry.node_id}-{horizon_minutes}M-{int(pred_time_utc.timestamp())}",
            hazard=hazard_type,
            prediction_time=pred_time_utc,
            forecast_time=forecast_time,
            forecast_horizon_minutes=horizon_minutes,
            severity=hazard_res.severity,
            confidence=confidence,
            classification=hazard_res.classification,
            status=hazard_res.status,
            model_version=model_version,
            source_hazard_id=f"HAZ-{hazard_type.value.upper()}-{current_telemetry.node_id}-{int(pred_time_utc.timestamp())}",
            provenance_hash=provenance_hash,
            drivers=combined_drivers,
            data_quality=data_quality_diag,
            predicted_features=extrapolated_features,
            simulated=False,
        )

    def _compute_history_fingerprint(self, history_records: List[NormalizedTelemetry]) -> str:
        """
        Computes deterministic SHA-256 fingerprint for the chronological, filtered historical observations.
        Uses ProvenanceTracker.compute_record_hash on each individual normalized record.
        """
        if not history_records:
            return "NO_HISTORY"
        record_hashes = [ProvenanceTracker.compute_record_hash(r) for r in history_records]
        combined = ":".join(record_hashes)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _compute_prediction_provenance(
        self,
        current_fingerprint: str,
        history_fingerprint: str,
        hazard: str,
        horizon: int,
        history_count: int,
        model_version: str,
    ) -> str:
        """Computes deterministic SHA-256 fingerprint for the forecast."""
        payload = {
            "current_fingerprint": current_fingerprint,
            "history_fingerprint": history_fingerprint,
            "hazard": hazard,
            "horizon_minutes": horizon,
            "history_count": history_count,
            "model_version": model_version,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
