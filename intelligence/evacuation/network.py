"""
Road network graph management for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Maintains graph adjacency, edge attributes, dynamic cascade updates, and closed-road filtering.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Set
from intelligence.compound.types import CompoundEvent
from intelligence.evacuation.types import RoadEdge, RoadNetwork


class RoadNetworkGraph:
    """
    In-memory graph representation of an evacuation road network.
    Provides deterministic adjacency queries, edge lookups, and dynamic condition updating.
    """

    def __init__(self, network: RoadNetwork):
        self.network_id = network.network_id
        self._nodes: Set[str] = set(network.nodes)
        self._edges_by_id: Dict[str, RoadEdge] = {}
        self._adjacency: Dict[str, List[RoadEdge]] = defaultdict(list)

        for edge in network.edges:
            self.add_edge(edge)

    def add_edge(self, edge: RoadEdge) -> None:
        """Adds an edge to the graph and registers endpoints."""
        self._edges_by_id[edge.edge_id] = edge
        self._nodes.add(edge.from_node)
        self._nodes.add(edge.to_node)
        self._adjacency[edge.from_node].append(edge)

    @property
    def nodes(self) -> Set[str]:
        return set(self._nodes)

    @property
    def edges(self) -> List[RoadEdge]:
        return list(self._edges_by_id.values())

    def get_edge(self, edge_id: str) -> Optional[RoadEdge]:
        return self._edges_by_id.get(edge_id)

    def get_outbound_edges(
        self,
        node: str,
        include_closed: bool = False,
        min_accessibility: Optional[float] = None,
    ) -> List[RoadEdge]:
        """Returns outbound edges from a node, sorted deterministically by edge_id."""
        edges = self._adjacency.get(node, [])
        if not include_closed:
            edges = [e for e in edges if not e.closed]
        if min_accessibility is not None:
            edges = [e for e in edges if e.accessibility >= min_accessibility]
        return sorted(edges, key=lambda e: e.edge_id)

    def apply_cascade_disruptions(self, compound_events: Optional[List[CompoundEvent]]) -> List[str]:
        """
        Dynamically applies Phase 4 cascading infrastructure disruptions to network edges.
        Maintains strict distinction between physical closure (closed=True) and inferred
        degradations (which update inferred_failure_risk and accessibility without closing the road).
        Returns a list of edge IDs that were closed or degraded.
        """
        if not compound_events:
            return []

        affected_edges: List[str] = []
        for ce in compound_events:
            # Check for road infrastructure disruption states
            has_road_failure = any(
                state in ce.chain
                for state in [
                    "inferred_road_failure_risk",
                    "inferred_access_loss",
                    "predicted_access_loss",
                    "road_failure",
                    "bridge_washout",
                ]
            )
            if not has_road_failure:
                continue

            is_confirmed_physical_failure = any(
                state in ce.chain for state in ["road_failure", "bridge_washout"]
            )

            # Identify target edges from event metadata or apply general penalty to fragile bridges
            target_edge_ids = ce.relationships[0].explanation if ce.relationships else ""
            for edge_id, edge in self._edges_by_id.items():
                is_target = (
                    edge_id in target_edge_ids
                    or edge.features.get("bridge", False)
                    or edge.features.get("flood_vulnerable", False)
                )
                if is_target:
                    edge.inferred_failure_risk = round(ce.severity, 4)
                    if is_confirmed_physical_failure and ce.severity >= 0.85:
                        # Only confirmed physical destruction triggers explicit closure
                        edge.closed = True
                        edge.closure_reason = f"Confirmed physical failure: {ce.event_id} ({ce.event_type.value})"
                        affected_edges.append(edge_id)
                    else:
                        # Inferred cascade failure degrades accessibility; closed remains False!
                        edge.accessibility = round(max(0.05, edge.accessibility * (1.0 - 0.80 * ce.severity)), 4)
                        affected_edges.append(edge_id)

        return affected_edges

    def get_closed_edge_ids(self) -> List[str]:
        """Returns sorted list of all closed edge IDs."""
        return sorted([e.edge_id for e in self._edges_by_id.values() if e.closed])
