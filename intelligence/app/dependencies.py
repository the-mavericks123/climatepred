"""
Dependency injection providers for the Climate Eye View FastAPI application.
"""

from functools import lru_cache
from intelligence.app.config import Settings, settings
from intelligence.core.logging import get_logger
from intelligence.ingestion.source_registry import SourceRegistry
from intelligence.core.provenance.tracker import ProvenanceTracker


@lru_cache()
def get_settings() -> Settings:
    return settings


@lru_cache()
def get_source_registry() -> SourceRegistry:
    return SourceRegistry()


def get_provenance_tracker() -> ProvenanceTracker:
    return ProvenanceTracker()


@lru_cache()
def get_hazard_engine():
    from intelligence.hazards.engine import HazardEngine
    return HazardEngine(stale_threshold_seconds=settings.data_freshness_threshold_sec)


@lru_cache()
def get_prediction_engine():
    from intelligence.prediction.engine import PredictionEngine
    return PredictionEngine()


@lru_cache()
def get_compound_engine():
    from intelligence.compound.engine import CompoundDisasterEngine
    return CompoundDisasterEngine()


@lru_cache()
def get_vulnerability_engine():
    from intelligence.vulnerability.engine import VulnerabilityEngine
    return VulnerabilityEngine()


@lru_cache()
def get_evacuation_engine():
    from intelligence.evacuation.engine import EvacuationEngine
    return EvacuationEngine()


@lru_cache()
def get_simulation_engine():
    from intelligence.simulation.engine import SimulationEngine
    return SimulationEngine(
        hazard_engine=get_hazard_engine(),
        prediction_engine=get_prediction_engine(),
        compound_engine=get_compound_engine(),
        vulnerability_engine=get_vulnerability_engine(),
        evacuation_engine=get_evacuation_engine(),
        stale_threshold_seconds=settings.data_freshness_threshold_sec,
    )


@lru_cache()
def get_response_engine():
    from intelligence.response.engine import ResponsePlannerEngine
    return ResponsePlannerEngine(
        hazard_engine=get_hazard_engine(),
        prediction_engine=get_prediction_engine(),
        compound_engine=get_compound_engine(),
        vulnerability_engine=get_vulnerability_engine(),
        evacuation_engine=get_evacuation_engine(),
        simulation_engine=get_simulation_engine(),
        stale_threshold_seconds=settings.response_freshness_threshold_sec,
    )


@lru_cache()
def get_explainability_engine():
    from intelligence.explainability.engine import ExplainabilityEngine
    return ExplainabilityEngine()


@lru_cache()
def get_evaluation_engine():
    from intelligence.evaluation.engine import EvaluationEngine
    return EvaluationEngine()


@lru_cache()
def get_calibration_engine():
    from intelligence.calibration.engine import CalibrationEngine
    return CalibrationEngine(min_samples=settings.calibration_min_samples)





