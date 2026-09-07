"""
Deterministic hazard-aware routing using Dijkstra shortest-path algorithms.
Computes optimal evacuation routes considering distance, travel time, hazard exposure,
road accessibility, and dynamic closures.
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple
from intelligence.evacuation.network import RoadNetworkGraph
from intelligence.evacuation.types import EvacuationRoute, RoadEdge


class HazardAwareRouter:
    """
    Computes deterministic, hazard-weighted evacuation paths over a road network.
    Guarantees:
      - Closed edges are never traversed (cost = infinity).
      - Degraded edges below accessibility_threshold are rejected (cost = infinity).
      - Safer routes with low hazard exposure are prioritized over shorter, hazardous corridors.
      - Fully deterministic tie-breaking ensures identical inputs yield identical routes.
    """

    ALGORITHM_VERSION = "dijkstra-hazard-v1"
    COST_FORMULA_VERSION = "cost-v1"
    HAZARD_MULTIPLIER_VERSION = "hazard-mult-v1"
    ACCESSIBILITY_MULTIPLIER_VERSION = "access-mult-v1"
    ROUTE_SAFETY_FORMULA_VERSION = "safety-v1"

    @classmethod
    def calculate_edge_cost(cls, edge: RoadEdge, accessibility_threshold: Optional[float] = None) -> float:
        """
        Calculates composite edge traversal cost.
        Formula:
            hazard_multiplier = 1.0 + (2.5 * hazard_risk)
            accessibility_multiplier = 1.0 + (2.0 * (1.0 - accessibility))
            cost = travel_time_minutes * hazard_multiplier * accessibility_multiplier
        Rejection criteria:
            - edge.closed is True -> cost = infinity
            - edge.accessibility < accessibility_threshold -> cost = infinity
        """
        if edge.closed:
            return float("inf")

        if accessibility_threshold is None:
            from intelligence.app.config import settings
            accessibility_threshold = getattr(settings, "edge_accessibility_threshold", 0.40)

        # Accessibility threshold gate: edge is unusable if accessibility is strictly below threshold
        if edge.accessibility < accessibility_threshold:
            return float("inf")

        clamped_hazard = max(0.0, min(1.0, edge.hazard_risk))
        clamped_access = max(0.0, min(1.0, edge.accessibility))

        hazard_mult = 1.0 + (2.5 * clamped_hazard)
        access_mult = 1.0 + (2.0 * (1.0 - clamped_access))

        return round(edge.travel_time_minutes * hazard_mult * access_mult, 4)

    @classmethod
    def find_route(
        cls,
        graph: RoadNetworkGraph,
        origin_node: str,
        destination_node: str,
        max_allowed_hazard: Optional[float] = None,
        accessibility_threshold: Optional[float] = None,
    ) -> Optional[EvacuationRoute]:
        """
        Executes Dijkstra shortest path from origin to destination using hazard-aware edge costs.
        Enforces both max hazard limit and minimum accessibility threshold.
        Returns EvacuationRoute if a feasible path exists, or None if unreachable.
        """
        if origin_node not in graph.nodes or destination_node not in graph.nodes:
            return None

        if accessibility_threshold is None:
            from intelligence.app.config import settings
            accessibility_threshold = getattr(settings, "edge_accessibility_threshold", 0.40)

        if max_allowed_hazard is None:
            from intelligence.app.config import settings
            max_allowed_hazard = getattr(settings, "max_route_hazard_limit", 0.95)

        if origin_node == destination_node:
            return EvacuationRoute(
                route_id=f"ROUTE-{origin_node}-{destination_node}",
                origin_node=origin_node,
                destination_node=destination_node,
                nodes=[origin_node],
                edge_ids=[],
                distance_km=0.0,
                estimated_travel_minutes=0.0,
                hazard_exposure=0.0,
                accessibility=1.0,
                safety_score=1.0,
                total_cost=0.0,
            )

        # Priority queue entries: (cost, node_id, path_nodes, path_edges)
        # Using node_id in tuple ensures deterministic tie-breaking without comparing lists
        pq: List[Tuple[float, str, List[str], List[RoadEdge]]] = [(0.0, origin_node, [origin_node], [])]
        best_cost: Dict[str, float] = {origin_node: 0.0}

        while pq:
            curr_cost, curr_node, path_nodes, path_edges = heapq.heappop(pq)

            if curr_node == destination_node:
                # Target reached! Construct and return route
                return cls._build_route(path_nodes, path_edges, curr_cost)

            if curr_cost > best_cost.get(curr_node, float("inf")):
                continue

            for edge in graph.get_outbound_edges(curr_node, include_closed=False, min_accessibility=accessibility_threshold):
                # Hard hazard threshold rejection
                if edge.hazard_risk > max_allowed_hazard:
                    continue

                # Hard accessibility threshold rejection
                if edge.accessibility < accessibility_threshold:
                    continue

                edge_cost = cls.calculate_edge_cost(edge, accessibility_threshold=accessibility_threshold)
                if edge_cost == float("inf"):
                    continue

                new_cost = round(curr_cost + edge_cost, 4)
                next_node = edge.to_node

                if new_cost < best_cost.get(next_node, float("inf")):
                    best_cost[next_node] = new_cost
                    heapq.heappush(
                        pq,
                        (
                            new_cost,
                            next_node,
                            path_nodes + [next_node],
                            path_edges + [edge],
                        ),
                    )

        return None

    @classmethod
    def _build_route(
        cls,
        nodes: List[str],
        edges: List[RoadEdge],
        total_cost: float,
    ) -> EvacuationRoute:
        """Assembles and scores the resulting route."""
        dist = sum(e.distance_km for e in edges)
        tt = sum(e.travel_time_minutes for e in edges)
        hazards = [e.hazard_risk for e in edges]
        accessibilities = [e.accessibility for e in edges]

        mean_hazard = sum(hazards) / len(hazards) if hazards else 0.0
        mean_access = sum(accessibilities) / len(accessibilities) if accessibilities else 1.0

        # Safety score: 1.0 = safest, penalized by hazard exposure and lack of accessibility
        safety = max(0.0, min(1.0, 1.0 - (0.60 * mean_hazard) - (0.40 * (1.0 - mean_access))))

        route_id = f"ROUTE-{nodes[0]}-{nodes[-1]}-{len(edges)}E"
        return EvacuationRoute(
            route_id=route_id,
            origin_node=nodes[0],
            destination_node=nodes[-1],
            nodes=nodes,
            edge_ids=[e.edge_id for e in edges],
            distance_km=round(dist, 2),
            estimated_travel_minutes=round(tt, 1),
            hazard_exposure=round(mean_hazard, 4),
            accessibility=round(mean_access, 4),
            safety_score=round(safety, 4),
            total_cost=round(total_cost, 4),
        )

    @classmethod
    def identify_avoid_edges(
        cls,
        graph: RoadNetworkGraph,
        chosen_route: Optional[EvacuationRoute],
        hazard_threshold: float = 0.70,
        accessibility_threshold: Optional[float] = None,
    ) -> List[str]:
        """
        Identifies closed, severed, or hazardous roadway segments that evacuees should explicitly avoid.
        Includes physically closed edges and edges with accessibility degraded below the threshold.
        """
        if accessibility_threshold is None:
            from intelligence.app.config import settings
            accessibility_threshold = getattr(settings, "edge_accessibility_threshold", 0.40)

        avoid: Set[str] = set()
        # All closed edges must be avoided
        for edge_id in graph.get_closed_edge_ids():
            avoid.add(edge_id)

        # Edges below accessibility threshold or with high hazard risk
        route_nodes = set(chosen_route.nodes) if chosen_route else set()
        for edge in graph.edges:
            if edge.accessibility < accessibility_threshold:
                avoid.add(edge.edge_id)
            elif edge.hazard_risk >= hazard_threshold:
                avoid.add(edge.edge_id)
            elif edge.inferred_failure_risk is not None and edge.inferred_failure_risk >= hazard_threshold:
                avoid.add(edge.edge_id)
            elif edge.from_node in route_nodes and edge.closed:
                avoid.add(edge.edge_id)

        return sorted(list(avoid))
