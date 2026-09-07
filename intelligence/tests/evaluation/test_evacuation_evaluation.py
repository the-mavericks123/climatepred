"""
Evaluation benchmark tests for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Executes and validates 16 deterministic benchmark scenarios across normal, flood, high vulnerability,
hazard avoidance, road closures, shelter capacity limits, cascades, and isolated conditions.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from intelligence.compound.types import CompoundEvent, StateEvidenceType
from intelligence.evacuation.engine import EvacuationEngine
from intelligence.evacuation.types import (
    EvacuationStatus,
    NoRouteReason,
    PopulationZone,
    RoadNetwork,
    Shelter,
)
from intelligence.hazards.types import HazardResult
from intelligence.prediction.types import PredictionResult

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(filename: str):
    path = FIXTURES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


class TestEvacuationBenchmarks:
    def setup_method(self):
        self.engine = EvacuationEngine()

    def _run_scenario(self, filename: str):
        data = _load_fixture(filename)
        zones = [PopulationZone(**z) for z in data["zones"]]
        shelters = [Shelter(**s) for s in data["shelters"]]
        road_network = RoadNetwork(**data["road_network"])
        hazards = [HazardResult(**h) for h in data.get("hazards", [])]
        predictions = [PredictionResult(**p) for p in data.get("predictions", [])]
        compound_events = [CompoundEvent(**ce) for ce in data.get("compound_events", [])]

        return self.engine.evaluate(
            zones=zones,
            shelters=shelters,
            road_network=road_network,
            hazards=hazards,
            predictions=predictions,
            compound_events=compound_events,
        )

    def test_scenario_1_normal(self):
        recs = self._run_scenario("evacuation_normal.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        assert rec.population_to_evacuate == 0
        assert rec.destination is None
        assert rec.priority == 0.0

    def test_scenario_2_flood(self):
        recs = self._run_scenario("evacuation_flood.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        assert rec.population_to_evacuate > 0
        assert rec.destination.shelter_id == "SHELTER-NORTH"
        assert rec.route.safety_score >= 0.80

    def test_scenario_3_high_vulnerability(self):
        recs = self._run_scenario("evacuation_high_vulnerability.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        assert rec.priority >= 0.60
        assert rec.destination.shelter_id == "SHELTER-NORTH"

    def test_scenario_4_predicted_flood(self):
        recs = self._run_scenario("evacuation_predicted_flood.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        assert rec.evidence_type == StateEvidenceType.PREDICTED
        assert rec.forecast_horizon_minutes == 60
        assert rec.population_to_evacuate > 0

    def test_scenario_5_hazard_vs_short(self):
        recs = self._run_scenario("evacuation_hazard_vs_short.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        # Algorithm must avoid the short hazardous road and take safe route via INT-SAFE
        assert "INT-SAFE" in rec.route.nodes
        assert "INT-DANGER" not in rec.route.nodes
        assert rec.route.safety_score >= 0.85

    def test_scenario_6_road_closure(self):
        recs = self._run_scenario("evacuation_road_closure.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        # Bridge to North is closed, must route to East shelter
        assert rec.destination.shelter_id == "SHELTER-EAST"
        assert "ROAD-1-NORTH" in rec.avoid_edges

    def test_scenario_7_multiple_shelters(self):
        recs = self._run_scenario("evacuation_multiple_shelters.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        # Should pick the closest / lowest cost shelter (SHELTER-NORTH)
        assert rec.destination.shelter_id == "SHELTER-NORTH"

    def test_scenario_8_capacity_split(self):
        recs = self._run_scenario("evacuation_capacity_split.json")
        assert len(recs) == 1
        rec = recs[0]
        # Only 3000 capacity available for larger population demand
        assert rec.status == EvacuationStatus.PARTIAL_CAPACITY
        assert rec.destination.assigned_population == 3000
        assert rec.destination.available_capacity_after == 0

    def test_scenario_9_multiple_zones(self):
        recs = self._run_scenario("evacuation_multiple_zones.json")
        assert len(recs) == 2
        # Zone A has higher vulnerability and priority -> evaluated and allocated first
        rec_a = next(r for r in recs if r.zone_id == "ZONE-A")
        rec_b = next(r for r in recs if r.zone_id == "ZONE-B")
        assert rec_a.priority > rec_b.priority
        assert rec_a.destination.assigned_population > 0

    def test_scenario_10_no_route(self):
        recs = self._run_scenario("evacuation_no_route.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.NO_ROUTE
        assert rec.destination is None
        assert rec.route is None
        assert rec.no_route_reason in (NoRouteReason.ALL_ROADS_CLOSED, NoRouteReason.NO_FEASIBLE_PATH)

    def test_scenario_11_unsafe_shelter(self):
        recs = self._run_scenario("evacuation_unsafe_shelter.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.UNSAFE
        assert rec.no_route_reason == NoRouteReason.DESTINATION_UNSAFE

    def test_scenario_12_cascade(self):
        recs = self._run_scenario("evacuation_cascade.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.RECOMMENDED
        # Cascade degraded ROAD-A-1, should prioritize SHELTER-EAST
        assert rec.destination.shelter_id == "SHELTER-EAST"

    def test_scenario_13_stale_data(self):
        recs = self._run_scenario("evacuation_stale_data.json")
        assert len(recs) == 1
        rec = recs[0]
        assert 0.0 <= rec.confidence <= 1.0

    def test_scenario_14_no_shelter(self):
        recs = self._run_scenario("evacuation_no_shelter.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.NO_SHELTER
        assert rec.no_route_reason == NoRouteReason.INSUFFICIENT_SHELTER_CAPACITY

    def test_scenario_15_synthetic_demo(self):
        recs = self._run_scenario("evacuation_synthetic_demo.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.simulated is True

    def test_scenario_16_partial_capacity(self):
        recs = self._run_scenario("evacuation_partial_capacity.json")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.status == EvacuationStatus.PARTIAL_CAPACITY
        assert rec.destination.assigned_population == 2500
        assert rec.destination.available_capacity_after == 0
