"""
Base abstract class for Climate Eye View S2 deterministic hazard models.
"""

from abc import ABC, abstractmethod
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict
from intelligence.hazards.types import HazardResult, HazardStatus, HazardType


class BaseHazardModel(ABC):
    """Abstract base class for all deterministic hazard evaluation models."""

    @property
    @abstractmethod
    def hazard_type(self) -> HazardType:
        """The specific hazard classification evaluated by this model."""
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        """The immutable version string of this model."""
        pass

    @abstractmethod
    def evaluate(self, features: HazardFeatures, verdict: QualityGateVerdict) -> HazardResult:
        """
        Executes deterministic hazard evaluation against extracted features.
        Precondition: verdict.is_admissible is True.
        """
        pass

    def build_unavailable_result(self, features: HazardFeatures, reason: str) -> HazardResult:
        """Constructs standardized UNAVAILABLE result when prerequisites are not met."""
        return HazardResult(
            hazard_id=f"HAZ-{self.hazard_type.value.upper()}-{features.node_id}-{int(features.timestamp.timestamp())}",
            hazard=self.hazard_type,
            severity=0.0,
            confidence=0.0,
            classification=None,  # Handled cleanly in types or set to NORMAL
            status=HazardStatus.UNAVAILABLE,
            timestamp=features.timestamp,
            forecast_horizon_minutes=0,
            location=features.location,
            features=features.as_feature_dict(),
            drivers=[reason] if reason else [],
            source="model",
            model_version=self.model_version,
            simulated=False,
            provenance_hash=features.provenance_hash,
            reason=reason,
        )
