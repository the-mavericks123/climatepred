"""
Main orchestrator for Phase 7: Digital Twin + Scenario Simulation Engine.
Coordinates base state isolation, deterministic parameter transformation, multi-phase model
propagation, delta comparison, confidence evaluation, and provenance hashing.
"""

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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
        region: Optional[str] = None,
        current_telemetry: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        """
        Executes an end-to-end scenario simulation:
          1. Resolves scenario definition and effective parameters.
          2. Clones base state to ensure strict isolation.
          3. Validates base state freshness.
          4. Applies deterministic mathematical transformations.
          5. Propagates changes across Phase 2-10 intelligence models.
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
        raw_base = base_state or self.build_base_state_for_region(
            region=region,
            now=eval_time_utc,
            telemetry_override=current_telemetry,
        )
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

        # 5. Propagate across Phase 2-10 models
        (
            sim_hazards,
            sim_predictions,
            sim_compounds,
            sim_vulns,
            sim_evacs,
            sim_response_plan,
            sim_explanation,
        ) = self.propagator.propagate(
            simulated_telemetry=sim_telemetry,
            simulated_history=sim_history,
            simulated_road_network=sim_network,
            population_zones=base_clone.population_zones,
            shelters=base_clone.shelters,
            now=base_clone.timestamp,
            scenario_id=scenario_id,
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
            response_plan=sim_response_plan,
            explanation=sim_explanation,
            confidence=confidence,
            provenance_hash=prov_hash,
        )

        # Cache result
        self._cache[sim_id] = result
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

        return result

    @classmethod
    def build_base_state_for_region(
        cls,
        region: Optional[str] = None,
        now: Optional[datetime] = None,
        telemetry_override: Optional[Dict[str, Any]] = None,
    ) -> DigitalTwinState:
        """
        Dynamically assembles a DigitalTwinState snapshot for the requested geographical region.
        Strictly complies with the Phase 10 Invariant: water_level is None (UNAVAILABLE)
        unless explicitly perturbed during simulation.
        """
        eval_time = now or datetime.now(timezone.utc)
        eval_time_utc = eval_time if eval_time.tzinfo else eval_time.replace(tzinfo=timezone.utc)

        KNOWN_REGIONS = {
            "hyderabad": (17.3850, 78.4867, "Hyderabad Metropolitan Catchment"),
            "mumbai": (19.0760, 72.8777, "Mumbai Coastal Zone"),
            "delhi": (28.6139, 77.2090, "Delhi NCR Basin"),
            "bengaluru": (12.9716, 77.5946, "Bengaluru Urban Corridor"),
            "tokyo": (35.6762, 139.6503, "Greater Tokyo Bay"),
            "california": (36.7783, -119.4179, "California Central Valley"),
            "london": (51.5074, -0.1278, "Greater London Thames Catchment"),
            "new york": (40.7128, -74.0060, "New York Metropolitan Estuary"),
        }

        key = (region or "hyderabad").strip().lower()
        lat, lon, region_name = KNOWN_REGIONS.get(key, (17.3850, 78.4867, f"{(region or 'Hyderabad').title()} Urban Zone"))

        # Baseline telemetry: default observations without water_level (Phase 10 Invariant)
        temp = 29.5
        hum = 68.0
        rain = 22.0
        soil = 46.0

        if telemetry_override:
            temp = float(telemetry_override.get("temperature", temp))
            hum = float(telemetry_override.get("humidity", hum))
            rain = float(telemetry_override.get("rainfall", rain))
            soil = float(telemetry_override.get("soil_moisture", soil))

        telemetry = NormalizedTelemetry(
            node_id=f"TEL-{key.upper()[:6]}-BASE-01",
            timestamp=eval_time_utc,
            location=LocationCoordinate(lat=lat, lon=lon),
            measurements=SensorMeasurements(
                temperature=temp,
                humidity=hum,
                rainfall=rain,
                soil_moisture=soil,
                water_level=None,  # Invariant: water_level must be null/UNAVAILABLE in live mode
            ),
            quality=QualityMetadata(
                source="sim_digital_twin_baseline",
                confidence=0.95,
                received_at=eval_time_utc,
            ),
        )

        zones = [
            PopulationZone(
                zone_id=f"ZONE-{key.upper()[:6]}-01",
                name=region_name,
                population=25000,
                age_0_14_ratio=0.22,
                age_65_plus_ratio=0.16,
                socioeconomic_vulnerability=0.30,
                disability_ratio=0.07,
                healthcare_access=0.80,
                road_accessibility=0.85,
                critical_facility_access=0.75,
                simulated=True,
            )
        ]

        shelters = [
            Shelter(
                shelter_id=f"SHELTER-{key.upper()[:6]}-NORTH",
                name=f"{region_name} North Refuge Center",
                latitude=round(lat + 0.025, 4),
                longitude=round(lon + 0.012, 4),
                capacity=15000,
                current_occupancy=2500,
                accessibility=0.95,
                safe=True,
                hazard_risk=0.04,
                node_id=f"SHELTER-{key.upper()[:6]}-NORTH",
                simulated=True,
            ),
            Shelter(
                shelter_id=f"SHELTER-{key.upper()[:6]}-EAST",
                name=f"{region_name} East Regional Safe Complex",
                latitude=round(lat - 0.020, 4),
                longitude=round(lon + 0.028, 4),
                capacity=18000,
                current_occupancy=3000,
                accessibility=0.90,
                safe=True,
                hazard_risk=0.06,
                node_id=f"SHELTER-{key.upper()[:6]}-EAST",
                simulated=True,
            ),
        ]

        edges = [
            RoadEdge(
                edge_id=f"ROAD-{key.upper()[:6]}-Z-N1",
                from_node=zones[0].zone_id,
                to_node=f"INT-{key.upper()[:6]}-1",
                distance_km=2.8,
                travel_time_minutes=5.5,
                accessibility=0.88,
                hazard_risk=0.08,
                closed=False,
                simulated=True,
            ),
            RoadEdge(
                edge_id=f"ROAD-{key.upper()[:6]}-N1-NORTH",
                from_node=f"INT-{key.upper()[:6]}-1",
                to_node=shelters[0].shelter_id,
                distance_km=3.2,
                travel_time_minutes=6.2,
                accessibility=0.95,
                hazard_risk=0.04,
                closed=False,
                simulated=True,
            ),
            RoadEdge(
                edge_id=f"ROAD-{key.upper()[:6]}-Z-E1",
                from_node=zones[0].zone_id,
                to_node=f"INT-{key.upper()[:6]}-2",
                distance_km=3.1,
                travel_time_minutes=6.0,
                accessibility=0.85,
                hazard_risk=0.09,
                closed=False,
                simulated=True,
            ),
            RoadEdge(
                edge_id=f"ROAD-{key.upper()[:6]}-E1-EAST",
                from_node=f"INT-{key.upper()[:6]}-2",
                to_node=shelters[1].shelter_id,
                distance_km=4.1,
                travel_time_minutes=7.8,
                accessibility=0.90,
                hazard_risk=0.05,
                closed=False,
                simulated=True,
            ),
        ]

        network = RoadNetwork(
            network_id=f"NET-{key.upper()[:6]}-BASE-01",
            nodes=[zones[0].zone_id, f"INT-{key.upper()[:6]}-1", f"INT-{key.upper()[:6]}-2", shelters[0].shelter_id, shelters[1].shelter_id],
            edges=edges,
        )

        state = DigitalTwinState(
            base_state_id=f"STATE-{key.upper()[:6]}-BASELINE",
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

    @classmethod
    def build_default_base_state(cls, now: Optional[datetime] = None) -> DigitalTwinState:
        """
        Assembles a canonical default DigitalTwinState snapshot for standard scenario runs.
        """
        return cls.build_base_state_for_region(region="hyderabad", now=now)

