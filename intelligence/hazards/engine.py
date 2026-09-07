"""Hazard evaluation engine orchestrating quality gating, feature extraction, and models.

Phase 2: Deterministic current-state hazard detection.
forecast_horizon_minutes = 0.
"""

from typing import List, Optional, Dict
from datetime import datetime

from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.hazards.types import (
    HazardType,
    HazardResult,
)
from intelligence.hazards.features import FeatureExtractor, HazardFeatures
from intelligence.hazards.quality_gate import HazardQualityGate
from intelligence.hazards.base import BaseHazardModel
from intelligence.hazards.heat import HeatModel
from intelligence.hazards.flood import FloodModel
from intelligence.hazards.drought import DroughtModel
from intelligence.hazards.thresholds import (
    ClassificationThresholds,
    HeatModelConfig,
    FloodModelConfig,
    DroughtModelConfig,
    DEFAULT_CLASSIFICATION_THRESHOLDS,
    DEFAULT_HEAT_CONFIG,
    DEFAULT_FLOOD_CONFIG,
    DEFAULT_DROUGHT_CONFIG,
)
from intelligence.core.provenance.tracker import ProvenanceTracker
from intelligence.core.logging import get_logger

logger = get_logger(__name__)


class HazardEngine:
    """Orchestrator for deterministic hazard detection in Climate Eye View.

    Pipeline:
      NormalizedTelemetry
              ↓
        Feature Extraction
              ↓
         Quality Gate
              ↓
      Hazard Models (Heat, Flood, Drought)
              ↓
      List of HazardResults
    """

    def __init__(
        self,
        stale_threshold_seconds: int = 300,
        classification_thresholds: ClassificationThresholds = DEFAULT_CLASSIFICATION_THRESHOLDS,
        heat_config: HeatModelConfig = DEFAULT_HEAT_CONFIG,
        flood_config: FloodModelConfig = DEFAULT_FLOOD_CONFIG,
        drought_config: DroughtModelConfig = DEFAULT_DROUGHT_CONFIG,
    ):
        self.quality_gate = HazardQualityGate(stale_threshold_seconds=stale_threshold_seconds)
        self.feature_extractor = FeatureExtractor()

        # Initialize independent hazard models
        self.models: Dict[HazardType, BaseHazardModel] = {
            HazardType.HEAT: HeatModel(
                config=heat_config,
            ),
            HazardType.FLOOD: FloodModel(
                config=flood_config,
                classification_thresholds=classification_thresholds,
            ),
            HazardType.DROUGHT: DroughtModel(
                config=drought_config,
                classification_thresholds=classification_thresholds,
            ),
        }

    def evaluate_telemetry(
        self,
        telemetry: NormalizedTelemetry,
        hazard_types: Optional[List[HazardType]] = None,
        now: Optional[datetime] = None,
    ) -> List[HazardResult]:
        """Evaluate a NormalizedTelemetry record against requested or all hazard models.

        Args:
            telemetry: Canonical NormalizedTelemetry instance.
            hazard_types: Optional filter of hazard types to evaluate. If None, evaluates all.
            now: Current time for freshness check. Defaults to utcnow().

        Returns:
            List of deterministic HazardResult instances.
        """
        # 1. Compute verifiable provenance fingerprint
        provenance_hash = ProvenanceTracker.compute_record_hash(telemetry)

        # 2. Feature Extraction
        features = self.feature_extractor.extract(telemetry, provenance_hash=provenance_hash)

        # Targets to evaluate
        targets = hazard_types if hazard_types is not None else list(self.models.keys())
        results: List[HazardResult] = []

        for h_type in targets:
            model = self.models.get(h_type)
            if not model:
                logger.warning(f"unsupported_hazard_type: {h_type.value}")
                continue

            # 3. Quality Gate Verification
            verdict = self.quality_gate.verify(features, h_type, now=now)

            # 4. Model Evaluation
            result = model.evaluate(features, verdict)
            results.append(result)

            logger.info(
                f"hazard_evaluated: hazard={result.hazard.value} status={result.status.value} "
                f"severity={result.severity:.2f} confidence={result.confidence:.2f} "
                f"node_id={telemetry.node_id}",
                extra={
                    "extra_data": {
                        "hazard": result.hazard.value,
                        "status": result.status.value,
                        "severity": result.severity,
                        "confidence": result.confidence,
                        "classification": result.classification.value if result.classification else None,
                        "model_version": result.model_version,
                        "node_id": telemetry.node_id,
                        "telemetry_fingerprint": provenance_hash,
                    }
                },
            )

        return results
