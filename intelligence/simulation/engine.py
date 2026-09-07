"""
Main orchestrator for Phase 7: Digital Twin + Scenario Simulation Engine.
Coordinates base state isolation, deterministic parameter transformation, multi-phase model
propagation, delta comparison, confidence evaluation, and provenance hashing.
"""

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from intelligence.app.config import settings
from intelligence.compound.engine import CompoundDisasterEngine
from intelligence.core.contracts.telemetry import (
    LocationCoordinate,
    NormalizedTelemetry,
    QualityMetadata,
    SensorMeasurements,
)
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.evacuation.types import (
    RoadEdge,
    RoadNetwork,
    Shelter,
)
from intelligence.hazards.engine import HazardEngine
from intelligence.prediction.engine import PredictionEngine
from intelligence.simulation.confidence import SimulationConfidenceCalculator
from intelligence.simulation.outputs import SimulationComparator
from intelligence.simulation.propagation import ModelPropagator
from intelligence.simulation.provenance import SimulationProvenanceTracker
from intelligence.simulation.scenarios import ScenarioCatalog
from intelligence.simulation.state import DigitalTwinStateManager
from intelligence.simulation.transforms import ScenarioTransformer
from intelligence.simulation.types import (
    DigitalTwinState,
    ScenarioDefinition,
    ScenarioParameters,
    SimulationResult,
)
from intelligence.vulnerability.engine import VulnerabilityEngine
from intelligence.vulnerability.types import PopulationZone


class SimulationEngine:
    """
    Deterministic Digital Twin + Scenario Simulation Engine for Climate Eye View.
    """

    def __init__(
        self,
        hazard_engine: Optional[HazardEngine] = None,
        prediction_engine: Optional[PredictionEngine] = None,
        compound_engine: Optional[CompoundDisasterEngine] = None,
        vulnerability_engine: Optional[VulnerabilityEngine] = None,
        evacuation_engine: Optional[EvacuationEngine] = None,
        stale_threshold_seconds: Optional[int] = None,
    ):
        self.propagator = ModelPropagator(
            hazard_engine=hazard_engine,
            prediction_engine=prediction_engine,
            compound_engine=compound_engine,
            vulnerability_engine=vulnerability_engine,
            evacuation_engine=evacuation_engine,
        )
        self.stale_threshold_seconds = stale_threshold_seconds or settings.data_freshness_threshold_sec
        self._cache: OrderedDict[str, SimulationResult] = OrderedDict()
        self._cache_size = settings.simulation_cache_size

    def get_catalog(self) -> List[ScenarioDefinition]:
        """Returns the list of all authorized scenario definitions."""
        return ScenarioCatalog.list_scenarios()

    def get_supported_scenarios(self) -> List[ScenarioDefinition]:
        """Alias for get_catalog."""
        return self.get_catalog()

    def get_simulation(self, simulation_id: str) -> Optional[SimulationResult]:
        """Retrieves a cached simulation result by simulation_id."""
        return self._cache.get(simulation_id)

    def get_cached_simulation(self, simulation_id: str) -> Optional[SimulationResult]:
        """Alias for get_simulation."""
        return self.get_simulation(simulation_id)

    def run_simulation(
        self,
        scenario_id: str,
        base_state: Optional[DigitalTwinState] = None,
        changes: Optional[ScenarioParameters] = None,
        now: Optional[datetime] = None,
    ) -> SimulationResult:
        """
        Executes an end-to-end scenario simulation:
          1. Resolves scenario definition and effective parameters.
          2. Clones base state to ensure strict isolation.
          3. Validates base state freshness.
          4. Applies deterministic mathematical transformations.
          5. Propagates changes across Phase 2-6 intelligence models.
          6. Computes baseline vs. simulated numerical deltas.
          7. Calculates simulation modeling confidence.
          8. Computes canonical SHA-256 provenance hash.
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        # 1. Resolve Scenario and Parameters
        definition = ScenarioCatalog.get_scenario(scenario_id)
        effective_params = ScenarioCatalog.resolve_parameters(scenario_id, changes)
        scenario_version = definition.version if definition else "1.0"

        # 2. Obtain & Clone Base State
        raw_base = base_state or self.build_default_base_state(eval_time_utc)
        base_clone = DigitalTwinStateManager.clone_state(raw_base)

        # 3. Validate Freshness
        DigitalTwinStateManager.validate_freshness(
            state=base_clone,
            max_stale_seconds=settings.data_freshness_threshold_sec,
            now=eval_time_utc,
        )
        base_state_hash = DigitalTwinStateManager.compute_state_hash(base_clone)

        # 4. Apply Transformations
        sim_telemetry = ScenarioTransformer.transform_telemetry(base_clone.telemetry, effective_params)
        sim_history = ScenarioTransformer.transform_history(base_clone.history, effective_params)
        sim_network = ScenarioTransformer.transform_road_network(base_clone.road_network, effective_params)

        # 5. Propagate across Phase 2-6 models
        sim_hazards, sim_predictions, sim_compounds, sim_vulns, sim_evacs = self.propagator.propagate(
            simulated_telemetry=sim_telemetry,
            simulated_history=sim_history,
            simulated_road_network=sim_network,
            population_zones=base_clone.population_zones,
            shelters=base_clone.shelters,
            now=base_clone.timestamp,
        )

        # 6. Baseline vs. Simulated Comparison
        summary, comparison = SimulationComparator.compare(
            baseline=base_clone,
            simulated_hazards=sim_hazards,
            simulated_vulns=sim_vulns,
            simulated_evacs=sim_evacs,
            simulated_road_network=sim_network,
        )

        # 7. Confidence Evaluation
        confidence = SimulationConfidenceCalculator.calculate_confidence(base_clone, effective_params)

        # 8. Deterministic Provenance Digest
        prov_payload = SimulationProvenanceTracker.build_canonical_payload(
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            base_state_id=base_clone.base_state_id,
            base_state_hash=base_state_hash,
            parameters=effective_params,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            vulnerability_zones=sim_vulns,
            road_edges=sim_network.edges,
            shelters=base_clone.shelters,
            evacuation_routes=sim_evacs,
            confidence=confidence,
            simulated=True,
        )
        prov_hash = SimulationProvenanceTracker.compute_provenance_hash(canonical_payload=prov_payload)

        sim_id = f"SIM-{scenario_id}-{prov_hash[:8].upper()}"

        result = SimulationResult(
            simulation_id=sim_id,
            scenario_id=scenario_id,
            scenario_version=scenario_version,
            timestamp=eval_time_utc,
            simulated=True,
            base_state_id=base_clone.base_state_id,
            base_state_hash=base_state_hash,
            parameters=effective_params,
            summary=summary,
            comparison=comparison,
            hazards=sim_hazards,
            predictions=sim_predictions,
            compound_events=sim_compounds,
            vulnerability_zones=sim_vulns,
            evacuation_routes=sim_evacs,
            confidence=confidence,
            provenance_hash=prov_hash,
        )

        # Cache result
        self._cache[sim_id] = result
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

        return result

    @classmethod
    def build_default_base_state(cls, now: Optional[datetime] = None) -> DigitalTwinState:
        """
        Assembles a canonical default DigitalTwinState snapshot for standard scenario runs.
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        telemetry = NormalizedTelemetry(
            node_id="TEL-SIM-BASE-01",
            timestamp=eval_time_utc,
            location=LocationCoordinate(lat=37.7749, lon=-122.4194),
            measurements=SensorMeasurements(
                temperature=28.0,
                humidity=65.0,
                rainfall=15.0,
                soil_moisture=45.0,
                water_level=12.0,
            ),
            quality=QualityMetadata(
                source="sim_digital_twin",
                confidence=0.95,
                received_at=eval_time_utc,
            ),
        )

        zones = [
            PopulationZone(
                zone_id="ZONE-METRO-01",
                name="Central Metro Valley",
                population=12000,
                age_0_14_ratio=0.20,
                age_65_plus_ratio=0.18,
                socioeconomic_vulnerability=0.22,
                disability_ratio=0.06,
                healthcare_access=0.75,
                road_accessibility=0.85,
                critical_facility_access=0.80,
                simulated=True,
            )
        ]

        shelters = [
            Shelter(
                shelter_id="SHELTER-NORTH-01",
                name="North Valley Refuge Center",
                latitude=37.7850,
                longitude=-122.4100,
                capacity=8000,
                current_occupancy=1000,
                accessibility=0.95,
                safe=True,
                hazard_risk=0.05,
                node_id="SHELTER-NORTH-01",
                simulated=True,
            ),
            Shelter(
                shelter_id="SHELTER-EAST-01",
                name="East Heights Sports Complex",
                latitude=37.7650,
                longitude=-122.3900,
                capacity=10000,
                current_occupancy=1500,
                accessibility=0.90,
                safe=True,
                hazard_risk=0.08,
                node_id="SHELTER-EAST-01",
                simulated=True,
            ),
        ]

        edges = [
            RoadEdge(
                edge_id="ROAD-Z-N1",
                from_node="ZONE-METRO-01",
                to_node="INT-1",
                distance_km=2.5,
                travel_time_minutes=5.0,
                accessibility=0.90,
                hazard_risk=0.10,
                closed=False,
                simulated=True,
            ),
            RoadEdge(
                edge_id="ROAD-N1-NORTH",
                from_node="INT-1",
                to_node="SHELTER-NORTH-01",
                distance_km=3.0,
                travel_time_minutes=6.0,
                accessibility=0.95,
                hazard_risk=0.05,
                closed=False,
                simulated=True,
            ),
            RoadEdge(
                edge_id="ROAD-Z-E1",
                from_node="ZONE-METRO-01",
                to_node="INT-2",
                distance_km=3.0,
                travel_time_minutes=6.0,
                accessibility=0.85,
                hazard_risk=0.08,
                closed=False,
                simulated=True,
            ),
            RoadEdge(
                edge_id="ROAD-E1-EAST",
                from_node="INT-2",
                to_node="SHELTER-EAST-01",
                distance_km=4.0,
                travel_time_minutes=8.0,
                accessibility=0.90,
                hazard_risk=0.05,
                closed=False,
                simulated=True,
            ),
        ]

        network = RoadNetwork(
            network_id="NET-SIM-BASE-01",
            nodes=["ZONE-METRO-01", "INT-1", "INT-2", "SHELTER-NORTH-01", "SHELTER-EAST-01"],
            edges=edges,
        )

        state = DigitalTwinState(
            base_state_id="STATE-BASELINE-DEFAULT",
            timestamp=eval_time_utc,
            telemetry=telemetry,
            history=[],
            hazards=[],
            predictions=[],
            compound_events=[],
            vulnerability_zones=[],
            population_zones=zones,
            road_network=network,
            shelters=shelters,
            evacuation_routes=[],
            simulated=True,
        )
        state.provenance_hash = DigitalTwinStateManager.compute_state_hash(state)
        return state
