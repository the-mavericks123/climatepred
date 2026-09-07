"""
Baseline vs. Simulated state comparison and delta generation for Phase 7.
Computes deterministic numerical deltas, status transitions, newly avoided corridors,
and executive summary metrics.
"""

from typing import Dict, List, Set, Tuple
from intelligence.evacuation.types import EvacuationRecommendation, RoadNetwork
from intelligence.hazards.types import HazardResult
from intelligence.simulation.types import (
    ComponentDelta,
    DigitalTwinState,
    SimulationComparison,
    SimulationSummary,
)
from intelligence.vulnerability.types import VulnerabilityZoneAssessment


class SimulationComparator:
    """
    Computes exact, reproducible deltas comparing baseline operational state to simulated state.
    """

    @classmethod
    def compare(
        cls,
        baseline: DigitalTwinState,
        simulated_hazards: List[HazardResult],
        simulated_vulns: List[VulnerabilityZoneAssessment],
        simulated_evacs: List[EvacuationRecommendation],
        simulated_road_network: RoadNetwork,
    ) -> Tuple[SimulationSummary, SimulationComparison]:
        """
        Calculates all component-level metric deltas and high-level executive summaries.
        """
        metrics: List[ComponentDelta] = []

        # 1. Hazard Severity Deltas
        base_haz_by_type: Dict[str, float] = {h.hazard.value: h.severity for h in baseline.hazards}
        sim_haz_by_type: Dict[str, float] = {h.hazard.value: h.severity for h in simulated_hazards}

        all_haz_types = sorted(list(set(base_haz_by_type.keys()) | set(sim_haz_by_type.keys())))
        max_haz_delta = 0.0
        primary_haz = "none"

        for ht in all_haz_types:
            b_val = base_haz_by_type.get(ht, 0.0)
            s_val = sim_haz_by_type.get(ht, 0.0)
            d_val = round(s_val - b_val, 4)
            rel_val = round(d_val / b_val, 4) if b_val > 0.0 else None
            metrics.append(
                ComponentDelta(
                    name=f"{ht}_severity",
                    baseline=round(b_val, 4),
                    simulated=round(s_val, 4),
                    delta=d_val,
                    relative_delta=rel_val,
                    units="severity_index",
                )
            )
            if abs(d_val) >= abs(max_haz_delta):
                max_haz_delta = d_val
                primary_haz = ht

        # 2. Demographic & Human Impact Deltas
        base_exp = sum(v.population_exposed for v in baseline.vulnerability_zones)
        sim_exp = sum(v.population_exposed for v in simulated_vulns)
        exp_delta = sim_exp - base_exp
        exp_rel = round(exp_delta / base_exp, 4) if base_exp > 0 else None
        metrics.append(
            ComponentDelta(
                name="population_exposed",
                baseline=float(base_exp),
                simulated=float(sim_exp),
                delta=float(exp_delta),
                relative_delta=exp_rel,
                units="residents",
            )
        )

        base_mean_impact = (
            sum(v.human_impact for v in baseline.vulnerability_zones) / len(baseline.vulnerability_zones)
            if baseline.vulnerability_zones else 0.0
        )
        sim_mean_impact = (
            sum(v.human_impact for v in simulated_vulns) / len(simulated_vulns)
            if simulated_vulns else 0.0
        )
        impact_delta = round(sim_mean_impact - base_mean_impact, 4)
        metrics.append(
            ComponentDelta(
                name="mean_human_impact",
                baseline=round(base_mean_impact, 4),
                simulated=round(sim_mean_impact, 4),
                delta=impact_delta,
                units="impact_score",
            )
        )

        # 3. Evacuation Demand Deltas
        base_evac_pop = sum(e.population_to_evacuate for e in baseline.evacuation_routes)
        sim_evac_pop = sum(e.population_to_evacuate for e in simulated_evacs)
        evac_pop_delta = sim_evac_pop - base_evac_pop
        metrics.append(
            ComponentDelta(
                name="population_to_evacuate",
                baseline=float(base_evac_pop),
                simulated=float(sim_evac_pop),
                delta=float(evac_pop_delta),
                units="residents",
            )
        )

        # 4. Route Status Transitions
        base_evac_by_zone: Dict[str, EvacuationRecommendation] = {e.zone_id: e for e in baseline.evacuation_routes}
        sim_evac_by_zone: Dict[str, EvacuationRecommendation] = {e.zone_id: e for e in simulated_evacs}

        transitions: Dict[str, Dict[str, str]] = {}
        routes_severed = 0
        routes_altered = 0

        for zid in sorted(list(set(base_evac_by_zone.keys()) | set(sim_evac_by_zone.keys()))):
            b_rec = base_evac_by_zone.get(zid)
            s_rec = sim_evac_by_zone.get(zid)
            b_status = b_rec.status.value if b_rec else "NONE"
            s_status = s_rec.status.value if s_rec else "NONE"

            if b_status != s_status:
                transitions[zid] = {"baseline": b_status, "simulated": s_status}
                routes_altered += 1
                if s_status in ("NO_ROUTE", "UNSAFE"):
                    routes_severed += 1

        # 5. Newly Impassable / Avoided Edges
        base_avoids: Set[str] = set()
        for e in baseline.evacuation_routes:
            base_avoids.update(e.avoid_edges)

        sim_avoids: Set[str] = set()
        for e in simulated_evacs:
            sim_avoids.update(e.avoid_edges)

        new_avoids = sorted(list(sim_avoids - base_avoids))

        # 6. Shelter Occupancy Shift Deltas
        base_occ_by_shelter: Dict[str, int] = {}
        for r in baseline.evacuation_routes:
            if r.destination:
                base_occ_by_shelter[r.destination.shelter_id] = (
                    base_occ_by_shelter.get(r.destination.shelter_id, 0) + r.destination.assigned_population
                )

        sim_occ_by_shelter: Dict[str, int] = {}
        for r in simulated_evacs:
            if r.destination:
                sim_occ_by_shelter[r.destination.shelter_id] = (
                    sim_occ_by_shelter.get(r.destination.shelter_id, 0) + r.destination.assigned_population
                )

        shelter_deltas: Dict[str, int] = {}
        all_shelters = sorted(list(set(base_occ_by_shelter.keys()) | set(sim_occ_by_shelter.keys())))
        for sid in all_shelters:
            b_occ = base_occ_by_shelter.get(sid, 0)
            s_occ = sim_occ_by_shelter.get(sid, 0)
            if s_occ != b_occ:
                shelter_deltas[sid] = s_occ - b_occ

        # 7. Assemble Comparison & Summary
        comparison = SimulationComparison(
            metrics=metrics,
            route_status_transitions=transitions,
            new_avoid_edges=new_avoids,
            shelter_occupancy_deltas=shelter_deltas,
        )

        summary = SimulationSummary(
            hazard_change={
                "primary_hazard": primary_haz,
                "max_severity_delta": max_haz_delta,
                "status": "ESCALATED" if max_haz_delta > 0 else ("MITIGATED" if max_haz_delta < 0 else "STABLE"),
            },
            population_change={
                "newly_exposed_population": max(0, exp_delta),
                "total_simulated_exposed": sim_exp,
                "evacuation_demand_shift": evac_pop_delta,
            },
            route_change={
                "routes_severed": routes_severed,
                "routes_modified": routes_altered,
                "status_transitions_count": len(transitions),
            },
            infrastructure_change={
                "newly_avoided_edges_count": len(new_avoids),
                "shelters_with_demand_shift": len(shelter_deltas),
            },
        )

        return summary, comparison
