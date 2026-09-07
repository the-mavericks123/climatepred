"""
Directed Acyclic Graph (DAG) representation of cascading disasters and compound hazards.
Builds nodes, directed edges, prevents cycles, and performs bounded topological traversal
to discover active causal chains.
"""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from intelligence.compound.types import (
    ContributingState,
    RelationshipEdge,
    RelationshipType,
)


class CascadeGraph:
    """
    Graph data structure representing causal cascade links and compound interactions.
    Maintains active states as nodes and evaluated rule triggers as directed edges.
    """

    def __init__(self, max_depth: int = 6):
        self.max_depth = max_depth
        self.nodes: Dict[str, ContributingState] = {}
        self.adj_list: Dict[str, List[RelationshipEdge]] = defaultdict(list)
        self.in_degree: Dict[str, int] = defaultdict(int)

    def add_node(self, state: ContributingState) -> None:
        """Registers a contributing state in the graph."""
        self.nodes[state.state_id] = state

    def add_edge(self, edge: RelationshipEdge) -> bool:
        """
        Adds a directed edge from edge.from_state to edge.to_state.
        Includes cycle detection to ensure the cascade remains a Directed Acyclic Graph (DAG).
        Returns True if edge added, False if adding it would introduce a cycle.
        """
        # Ensure nodes exist or register minimal references
        if edge.from_state not in self.nodes or edge.to_state not in self.nodes:
            pass

        # Cycle check: would reaching from_state from to_state be possible?
        if self._path_exists(src=edge.to_state, dst=edge.from_state):
            return False  # Cycle detected, reject edge to prevent infinite recursion

        # Avoid duplicate edges for the same rule
        for existing in self.adj_list[edge.from_state]:
            if existing.to_state == edge.to_state and existing.rule_id == edge.rule_id:
                return True

        self.adj_list[edge.from_state].append(edge)
        self.in_degree[edge.to_state] += 1
        return True

    def _path_exists(self, src: str, dst: str) -> bool:
        """Breadth-first search to check if a directed path already exists from src to dst."""
        if src == dst:
            return True
        visited: Set[str] = set()
        queue = deque([src])

        while queue:
            curr = queue.popleft()
            if curr == dst:
                return True
            if curr in visited:
                continue
            visited.add(curr)
            for edge in self.adj_list[curr]:
                if edge.to_state not in visited:
                    queue.append(edge.to_state)
        return False

    def find_all_chains(self) -> List[List[str]]:
        """
        Finds all maximal valid cascade chains (paths of length >= 2) starting from root nodes.
        Bounded by max_depth to prevent combinatorial explosion.
        """
        roots = [node_id for node_id in self.nodes if self.in_degree[node_id] == 0]
        # If no root with in_degree 0 (or disconnected subgraphs), use all nodes with outgoing edges
        if not roots:
            roots = [node_id for node_id, edges in self.adj_list.items() if edges]

        all_chains: List[List[str]] = []

        def dfs(current: str, current_path: List[str], depth: int):
            if depth >= self.max_depth:
                if len(current_path) >= 2:
                    all_chains.append(list(current_path))
                return

            outgoing = self.adj_list[current]
            if not outgoing:
                if len(current_path) >= 2:
                    all_chains.append(list(current_path))
                return

            for edge in outgoing:
                target = edge.to_state
                if target not in current_path:  # Prevent visiting nodes already in current path
                    current_path.append(target)
                    dfs(target, current_path, depth + 1)
                    current_path.pop()

        for root in roots:
            dfs(root, [root], 1)

        return all_chains
