"""Quality gate and confidence assessment for Climate Eye View S2 hazard intelligence.
Verifies data prerequisites per hazard type and computes honest confidence scores.
"""

from datetime import datetime, timezone
from typing import List, Optional
from intelligence.app.config import settings
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.types import HazardType


class QualityGateVerdict:
    """Outcome of quality gate evaluation for a specific hazard model."""

    def __init__(
        self,
        is_admissible: bool,
        confidence: float = 1.0,
        reason: Optional[str] = None,
        penalties: Optional[List[str]] = None,
        missing_fields: Optional[List[str]] = None,
        is_stale: bool = False,
        anomaly_flags: Optional[List[str]] = None,
    ) -> None:
        self.is_admissible = is_admissible
        self.confidence = max(0.0, min(1.0, confidence))
        self.reason = reason
        self.penalties = penalties or []
        self.missing_fields = missing_fields or []
        self.is_stale = is_stale
        self.anomaly_flags = anomaly_flags or []

    @property
    def passed(self) -> bool:
        """Alias for is_admissible."""
        return self.is_admissible

    @property
    def confidence_factor(self) -> float:
        """Alias for confidence."""
        return self.confidence


class HazardQualityGate:
    """Enforces prerequisite checks and confidence calculations prior to model evaluation."""

    REQUIRED_INPUTS = {
        HazardType.HEAT: ["temperature_c", "humidity_pct"],
        HazardType.FLOOD: ["rainfall_mmhr", "soil_moisture_pct", "water_level_m"],
        HazardType.DROUGHT: ["soil_moisture_pct", "temperature_c", "humidity_pct"],
    }

    def __init__(self, stale_threshold_seconds: Optional[int] = None) -> None:
        self.stale_threshold_seconds = (
            stale_threshold_seconds
            if stale_threshold_seconds is not None
            else getattr(settings, "stale_data_threshold_seconds", 300)
        )

    def verify(
        self,
        features: HazardFeatures,
        hazard_type: HazardType,
        now: Optional[datetime] = None,
    ) -> QualityGateVerdict:
        """Instance method for evaluating quality gate against features."""
        return self.evaluate_gate(
            hazard_type=hazard_type,
            features=features,
            freshness_threshold_sec=self.stale_threshold_seconds,
            now=now,
        )

    @classmethod
    def evaluate(
        cls,
        hazard_type: HazardType,
        features: HazardFeatures,
        freshness_threshold_sec: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> QualityGateVerdict:
        """Class method for evaluating quality gate against features."""
        threshold = (
            freshness_threshold_sec
            if freshness_threshold_sec is not None
            else getattr(settings, "stale_data_threshold_seconds", 300)
        )
        return cls.evaluate_gate(
            hazard_type=hazard_type,
            features=features,
            freshness_threshold_sec=threshold,
            now=now,
        )

    @classmethod
    def evaluate_gate(
        cls,
        hazard_type: HazardType,
        features: HazardFeatures,
        freshness_threshold_sec: int,
        now: Optional[datetime] = None,
    ) -> QualityGateVerdict:
        required_fields = cls.REQUIRED_INPUTS.get(hazard_type, [])
        missing_fields = []

        for field in required_fields:
            if getattr(features, field, None) is None:
                missing_fields.append(field)

        if missing_fields:
            return QualityGateVerdict(
                is_admissible=False,
                confidence=0.0,
                reason=f"Required sensor measurement(s) unavailable for {hazard_type.value}: {', '.join(missing_fields)}",
                missing_fields=missing_fields,
            )

        # Baseline confidence starts from source quality confidence
        conf = features.confidence_base
        penalties: List[str] = []
        is_stale = False

        # 1. Invalid telemetry flag penalty
        if not features.valid:
            conf *= 0.50
            penalties.append("telemetry marked invalid by quality adapter (-50%)")

        # 2. Age and freshness check
        current_time = now or datetime.now(timezone.utc)
        obs_time = features.timestamp if features.timestamp.tzinfo else features.timestamp.replace(tzinfo=timezone.utc)
        current_time_aware = current_time if current_time.tzinfo else current_time.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (current_time_aware - obs_time).total_seconds())

        if age_seconds > freshness_threshold_sec:
            is_stale = True
            staleness_factor = min(0.60, (age_seconds - freshness_threshold_sec) / (freshness_threshold_sec * 4))
            conf *= (1.0 - staleness_factor)
            penalties.append(f"data staleness age={age_seconds:.0f}s exceeds threshold={freshness_threshold_sec}s (-{staleness_factor*100:.0f}%)")

        # 3. Anomaly score degradation
        if features.anomaly_score > 0.0:
            anomaly_penalty = min(0.40, features.anomaly_score * 0.5)
            conf *= (1.0 - anomaly_penalty)
            penalties.append(f"sensor anomaly score {features.anomaly_score:.2f} (-{anomaly_penalty*100:.0f}%)")

        # 4. Explicit quality flags
        anomaly_flags = []
        for flag in features.flags:
            anomaly_flags.append(flag)
            if "STALE" in flag:
                conf *= 0.70
                penalties.append(f"flag {flag} (-30%)")
            elif "UNRELIABLE" in flag or "FAULT" in flag:
                conf *= 0.50
                penalties.append(f"flag {flag} (-50%)")

        # Clamp confidence to [0.05, 1.0] for admissible packets
        final_confidence = max(0.05, min(1.0, conf))

        return QualityGateVerdict(
            is_admissible=True,
            confidence=round(final_confidence, 4),
            penalties=penalties,
            missing_fields=[],
            is_stale=is_stale,
            anomaly_flags=anomaly_flags,
        )
