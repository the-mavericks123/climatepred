"""
Feature extraction and state normalization for Phase 4: Compound & Cascading Disaster Engine.
Converts Phase 2 HazardResult, Phase 3 PredictionResult, and external environmental records
into normalized ContributingState instances.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from intelligence.compound.types import ContributingState, StateEvidenceType
from intelligence.hazards.types import HazardClassification, HazardResult, HazardStatus, HazardType
from intelligence.prediction.types import PredictionResult


class StateFeatureExtractor:
    """
    Transforms diverse input payloads into normalized ContributingState records,
    classifying their evidence type (OBSERVED vs PREDICTED vs INFERRED) and preserving provenance.
    """

    @staticmethod
    def from_hazard_result(hazard_res: HazardResult) -> Optional[ContributingState]:
        """Converts an observed Phase 2 HazardResult into a ContributingState."""
        # Only detected hazards with positive severity are active candidates
        if hazard_res.status != HazardStatus.DETECTED or hazard_res.severity <= 0.0:
            return None

        state_id = hazard_res.hazard.value
        return ContributingState(
            state_id=state_id,
            evidence_type=StateEvidenceType.OBSERVED,
            severity=round(hazard_res.severity, 4),
            confidence=round(hazard_res.confidence, 4),
            timestamp=hazard_res.timestamp,
            forecast_horizon_minutes=0,
            source_ref_id=hazard_res.hazard_id,
            provenance_hash=hazard_res.provenance_hash,
            metadata={
                "features": hazard_res.features,
                "drivers": hazard_res.drivers,
                "model_version": hazard_res.model_version,
            },
        )

    @staticmethod
    def from_prediction_result(pred_res: PredictionResult) -> Optional[ContributingState]:
        """Converts an extrapolated Phase 3 PredictionResult into a ContributingState."""
        if pred_res.status != HazardStatus.DETECTED or pred_res.severity <= 0.0:
            return None

        state_id = pred_res.hazard.value
        return ContributingState(
            state_id=state_id,
            evidence_type=StateEvidenceType.PREDICTED,
            severity=round(pred_res.severity, 4),
            confidence=round(pred_res.confidence, 4),
            timestamp=pred_res.forecast_time,
            forecast_horizon_minutes=pred_res.forecast_horizon_minutes,
            source_ref_id=pred_res.prediction_id,
            provenance_hash=pred_res.provenance_hash,
            metadata={
                "predicted_features": pred_res.predicted_features,
                "drivers": pred_res.drivers,
                "model_version": pred_res.model_version,
            },
        )

    @staticmethod
    def from_raw_dict(data: Dict[str, Any], default_timestamp: datetime) -> Optional[ContributingState]:
        """Converts an explicit environmental or inferred state dictionary into a ContributingState."""
        state_id = data.get("state_id") or data.get("hazard") or data.get("name")
        if not state_id:
            return None

        severity = float(data.get("severity", 0.0))
        if severity <= 0.0:
            return None

        conf = float(data.get("confidence", 1.0))
        ev_type_str = data.get("evidence_type", "OBSERVED").upper()
        try:
            ev_type = StateEvidenceType(ev_type_str)
        except ValueError:
            ev_type = StateEvidenceType.INFERRED

        ts_raw = data.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                ts = default_timestamp
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            ts = default_timestamp

        ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        horizon = int(data.get("forecast_horizon_minutes", 0))

        return ContributingState(
            state_id=str(state_id),
            evidence_type=ev_type,
            severity=max(0.0, min(1.0, severity)),
            confidence=max(0.0, min(1.0, conf)),
            timestamp=ts_utc,
            forecast_horizon_minutes=horizon,
            source_ref_id=data.get("source_ref_id"),
            provenance_hash=data.get("provenance_hash"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def extract_environmental_substates(cls, state: ContributingState) -> List[ContributingState]:
        """
        Derives explicit sub-states from physical measurements if present (e.g. soil_moisture >= 80% -> soil_saturation).
        Maintains distinct INFERRED status for all derived states.
        """
        substates: List[ContributingState] = []
        meta_feats = state.metadata.get("features") or state.metadata.get("predicted_features") or {}

        # 1. Soil saturation sub-state
        soil_m = meta_feats.get("soil_moisture") or meta_feats.get("soil_moisture_pct")
        if soil_m is not None and float(soil_m) >= 70.0:
            sat_sev = min(1.0, (float(soil_m) - 60.0) / 40.0)
            substates.append(
                ContributingState(
                    state_id="soil_saturation",
                    evidence_type=StateEvidenceType.INFERRED,
                    severity=round(sat_sev, 4),
                    confidence=round(state.confidence * 0.95, 4),
                    timestamp=state.timestamp,
                    forecast_horizon_minutes=state.forecast_horizon_minutes,
                    source_ref_id=f"INFER-SAT-{state.state_id}",
                    metadata={"derived_from": state.state_id, "soil_moisture": soil_m},
                )
            )

        # 2. Heavy rainfall sub-state
        rain = meta_feats.get("rainfall") or meta_feats.get("rainfall_mmhr")
        if rain is not None and float(rain) >= 25.0:
            rain_sev = min(1.0, float(rain) / 100.0)
            substates.append(
                ContributingState(
                    state_id="heavy_rain",
                    evidence_type=StateEvidenceType.INFERRED,
                    severity=round(rain_sev, 4),
                    confidence=round(state.confidence * 0.95, 4),
                    timestamp=state.timestamp,
                    forecast_horizon_minutes=state.forecast_horizon_minutes,
                    source_ref_id=f"INFER-RAIN-{state.state_id}",
                    metadata={"derived_from": state.state_id, "rainfall": rain},
                )
            )

        return substates
