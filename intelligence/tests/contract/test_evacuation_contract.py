"""
Contract tests for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Validates Pydantic schemas, physical bounds, capacity constraints, and error rejection gates.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from intelligence.evacuation.types import (
    EvacuationDemand,
    EvacuationEvaluationRequest,
    EvacuationRecommendation,
    EvacuationRoute,
    EvacuationStatus,
    RoadEdge,
    RoadNetwork,
    Shelter,
)

T_NOW = datetime.now(timezone.utc)


class TestEvacuationContracts:
    def test_shelter_occupancy_exceeding_capacity_rejected(self):
        with pytest.raises(ValidationError):
            Shelter(
                shelter_id="S1",
                name="Overflow Shelter",
                latitude=37.77,
                longitude=-122.41,
                capacity=1000,
                current_occupancy=1500,  # Invalid: > capacity
            )

    def test_shelter_negative_capacity_rejected(self):
        with pytest.raises(ValidationError):
            Shelter(
                shelter_id="S1",
                name="Invalid Capacity",
                latitude=37.77,
                longitude=-122.41,
                capacity=-100,
            )

    def test_road_edge_negative_distance_rejected(self):
        with pytest.raises(ValidationError):
            RoadEdge(
                edge_id="E1",
                from_node="A",
                to_node="B",
                distance_km=-5.0,  # Invalid
                travel_time_minutes=10.0,
            )

    def test_road_edge_hazard_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            RoadEdge(
                edge_id="E1",
                from_node="A",
                to_node="B",
                distance_km=5.0,
                travel_time_minutes=10.0,
                hazard_risk=1.50,  # Invalid: > 1.0
            )

    def test_evacuation_demand_evacuees_exceeding_exposed_rejected(self):
        with pytest.raises(ValidationError):
            EvacuationDemand(
                zone_id="Z1",
                evacuation_required=True,
                population_exposed=5000,
                population_to_evacuate=6000,  # Invalid: > exposed
                priority=0.80,
                human_impact=0.85,
                vulnerability=0.70,
                hazard_risk=0.90,
                accessibility_risk=0.20,
                urgency=1.0,
            )

    def test_evacuation_demand_priority_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            EvacuationDemand(
                zone_id="Z1",
                evacuation_required=True,
                population_exposed=5000,
                population_to_evacuate=4000,
                priority=1.5,  # Invalid: > 1.0
                human_impact=0.85,
                vulnerability=0.70,
                hazard_risk=0.90,
                accessibility_risk=0.20,
                urgency=1.0,
            )

    def test_evacuation_evaluation_request_empty_shelters_rejected(self):
        with pytest.raises(ValidationError):
            EvacuationEvaluationRequest(
                zones=[{"zone_id": "Z1", "population": 1000}],
                shelters=[],  # Invalid: min_length=1
                road_network={"network_id": "N1", "nodes": ["Z1"], "edges": []},
            )
