"""
Authoritative multi-phase model propagation pipeline for Phase 7: Digital Twin + Scenario Simulation Engine.
Propagates transformed digital twin perturbations sequentially across Phase 2, 3, 4, 5, and 6 engines.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.compound.types import CompoundEvent
from intelligence.core.contracts.telemetry import NormalizedTelemetry
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.evacuation.types import (
    EvacuationRecommendation,
    RoadNetwork,
    Shelter,
)
from intelligence.hazards.engine import HazardEngine
from intelligence.hazards.types import HazardResult
from intelligence.prediction.engine import PredictionEngine
from intelligence.prediction.types import PredictionResult
from intelligence.vulnerability.engine import VulnerabilityEngine
from intelligence.vulnerability.types import (
    PopulationZone,
    VulnerabilityZoneAssessment,
)


class ModelPropagator:
    """
    Executes sequential model propagation through authoritative upstream intelligence engines.
    Reuses existing deterministic formulas and rules, ensuring all outputs carry simulated = True.
    """

    def __init__(
        self,
        hazard_engine: Optional[HazardEngine] = None,
        prediction_engine: Optional[PredictionEngine] = None,
        compound_engine: Optional[CompoundDisasterEngine] = None,
        vulnerability_engine: Optional[VulnerabilityEngine] = None,
        evacuation_engine: Optional[EvacuationEngine] = None,
    ):
        self.hazard_engine = hazard_engine or HazardEngine()
        self.prediction_engine = prediction_engine or PredictionEngine()
        self.compound_engine = compound_engine or CompoundDisasterEngine()
        self.vulnerability_engine = vulnerability_engine or VulnerabilityEngine()
        self.evacuation_engine = evacuation_engine or EvacuationEngine()

    def propagate(
        self,
        simulated_telemetry: NormalizedTelemetry,
        simulated_history: List[NormalizedTelemetry],
        simulated_road_network: RoadNetwork,
        population_zones: List[PopulationZone],
        shelters: List[Shelter],
        now: Optional[datetime] = None,
    ) -> Tuple[
        List[HazardResult],
        List[PredictionResult],
        List[CompoundEvent],
        List[VulnerabilityZoneAssessment],
        List[EvacuationRecommendation],
    ]:
        """
        Executes end-to-end model propagation:
          1. Phase 2: Hazard Evaluation
          2. Phase 3: Prediction Evaluation
          3. Phase 4: Compound & Cascading Evaluation
          4. Phase 5: Human Vulnerability & Impact
          5. Phase 6: Evacuation & Adaptive Routing
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        # 1. Phase 2: Current-State Hazard Evaluation
        sim_hazards = self.hazard_engine.evaluate_telemetry(
            telemetry=simulated_telemetry,
            now=eval_time_utc,
        )

        # 2. Phase 3: Deterministic Trend Forecasting
        sim_predictions: List[PredictionResult] = []
        try:
            sim_predictions = self.prediction_engine.evaluate_predictions(
                current_telemetry=simulated_telemetry,
                history=simulated_history,
                now=eval_time_utc,
            )
        except Exception:
            sim_predictions = []

        # 3. Phase 4: Compound & Cascading Infrastructure Consequence Evaluation
        sim_compounds = self.compound_engine.evaluate(
            hazards=sim_hazards,
            predictions=sim_predictions,
            now=eval_time_utc,
        )

        # 4. Phase 5: Human Vulnerability & Impact Evaluation
        sim_zones = [z.model_copy(update={"simulated": True}) for z in population_zones]
        sim_vulns = self.vulnerability_engine.evaluate(
            zones=sim_zones,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            now=eval_time_utc,
        )
        for v in sim_vulns:
            v.simulated = True

        # 5. Phase 6: Evacuation Routing & Refuge Capacity Allocation
        sim_shelters = [s.model_copy(update={"simulated": True}) for s in shelters]
        sim_evacs = self.evacuation_engine.evaluate(
            zones=sim_zones,
            shelters=sim_shelters,
            road_network=simulated_road_network,
            vulnerabilities=sim_vulns,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            now=eval_time_utc,
        )
        for r in sim_evacs:
            r.simulated = True

        return sim_hazards, sim_predictions, sim_compounds, sim_vulns, sim_evacs
