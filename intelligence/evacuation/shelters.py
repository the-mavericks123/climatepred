"""
Shelter capacity management, safety evaluation, and deterministic allocation for Phase 6.
Guarantees available shelter capacity is never exceeded and evacuees are never directed to unsafe refuges.
"""

from typing import Dict, List, Optional, Tuple
from intelligence.evacuation.network import RoadNetworkGraph
from intelligence.evacuation.routing import HazardAwareRouter
from intelligence.evacuation.types import (
    DestinationAssignment,
    EvacuationDemand,
    EvacuationRoute,
    EvacuationStatus,
    NoRouteReason,
    Shelter,
)


class ShelterManager:
    """
    Manages emergency shelter availability, physical safety gates, and deterministic capacity allocation.
    """

    MAX_SHELTER_HAZARD_THRESHOLD = 0.60

    def __init__(self, shelters: List[Shelter]):
        # Copy shelters to allow stateful capacity decrementing during an evaluation session
        self._shelters: Dict[str, Shelter] = {
            s.shelter_id: s.model_copy(deep=True) for s in shelters
        }
        for s in self._shelters.values():
            if s.available_capacity is None:
                s.available_capacity = max(0, s.capacity - s.current_occupancy)

    def get_shelter(self, shelter_id: str) -> Optional[Shelter]:
        return self._shelters.get(shelter_id)

    @property
    def all_shelters(self) -> List[Shelter]:
        return sorted(self._shelters.values(), key=lambda s: s.shelter_id)

    def is_shelter_safe(self, shelter: Shelter) -> bool:
        """Determines if a shelter is structurally and physically safe."""
        if not shelter.safe:
            return False
        if shelter.hazard_risk >= self.MAX_SHELTER_HAZARD_THRESHOLD:
            return False
        return True

    def find_best_shelter_and_route(
        self,
        graph: RoadNetworkGraph,
        origin_node: str,
        demand: EvacuationDemand,
        accessibility_threshold: Optional[float] = None,
        max_allowed_hazard: Optional[float] = None,
    ) -> Tuple[Optional[Shelter], Optional[EvacuationRoute], EvacuationStatus, Optional[NoRouteReason], str]:
        """
        Evaluates candidate safe shelters with available capacity and selects the optimal path.
        Returns:
            (best_shelter, best_route, status, no_route_reason, explanation)
        """
        # 1. Filter safe shelters
        safe_shelters = [s for s in self._shelters.values() if self.is_shelter_safe(s)]
        if not safe_shelters:
            return None, None, EvacuationStatus.UNSAFE, NoRouteReason.DESTINATION_UNSAFE, "No structurally safe shelters available outside active hazard zones"

        # 2. Filter shelters with remaining capacity
        available_shelters = [s for s in safe_shelters if (s.available_capacity or 0) > 0]
        if not available_shelters:
            return None, None, EvacuationStatus.NO_SHELTER, NoRouteReason.INSUFFICIENT_SHELTER_CAPACITY, "All safe emergency shelters have reached maximum certified capacity"

        # 3. Find feasible routes to candidate shelters
        candidate_options: List[Tuple[float, str, Shelter, EvacuationRoute]] = []
        any_route_attempted = False

        for shelter in available_shelters:
            dest_node = shelter.node_id or shelter.shelter_id
            if dest_node not in graph.nodes:
                continue

            any_route_attempted = True
            route = HazardAwareRouter.find_route(
                graph,
                origin_node,
                dest_node,
                max_allowed_hazard=max_allowed_hazard,
                accessibility_threshold=accessibility_threshold,
            )
            if route is not None:
                # Composite score: route cost + shelter accessibility/hazard penalties
                shelter_penalty = (1.0 + 1.5 * shelter.hazard_risk) * (1.0 + 0.5 * (1.0 - shelter.accessibility))
                score = round(route.total_cost * shelter_penalty, 4)
                candidate_options.append((score, shelter.shelter_id, shelter, route))

        if not candidate_options:
            reason = NoRouteReason.ALL_ROADS_CLOSED if not any_route_attempted else NoRouteReason.NO_FEASIBLE_PATH
            return None, None, EvacuationStatus.NO_ROUTE, reason, "No feasible or traversable road route connects the origin zone to available safe shelters"

        # 4. Sort deterministically by lowest score, then stable shelter_id
        candidate_options.sort(key=lambda x: (x[0], x[1]))
        best_score, _, best_shelter, best_route = candidate_options[0]

        # 5. Check capacity matching
        avail = best_shelter.available_capacity or 0
        if avail >= demand.population_to_evacuate:
            status = EvacuationStatus.RECOMMENDED
            explanation = f"Safe evacuation route identified to {best_shelter.name} (sufficient capacity: {avail:,} available for {demand.population_to_evacuate:,} evacuees)"
        else:
            status = EvacuationStatus.PARTIAL_CAPACITY
            explanation = f"Partial capacity allocation: {best_shelter.name} can accommodate {avail:,} of {demand.population_to_evacuate:,} evacuees"

        return best_shelter, best_route, status, None, explanation

    def allocate_capacity(
        self,
        shelter: Shelter,
        requested_population: int,
    ) -> DestinationAssignment:
        """
        Decrements shelter available capacity deterministically and returns DestinationAssignment.
        """
        avail_before = shelter.available_capacity or 0
        assigned = min(avail_before, requested_population)
        avail_after = avail_before - assigned
        shelter.available_capacity = avail_after

        safety_score = round(max(0.0, min(1.0, 1.0 - shelter.hazard_risk)), 4)

        return DestinationAssignment(
            shelter_id=shelter.shelter_id,
            shelter_name=shelter.name,
            assigned_population=assigned,
            available_capacity_before=avail_before,
            available_capacity_after=avail_after,
            shelter_safety_score=safety_score,
        )
