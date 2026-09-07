"""
Digital Twin state capture, validation, freshness gating, and immutability management for Phase 7.
Guarantees that baseline operational state is never mutated during scenario execution.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Optional

from intelligence.core.errors.exceptions import StaleDataException
from intelligence.core.provenance.tracker import ProvenanceTracker
from intelligence.simulation.types import DigitalTwinState


class DigitalTwinStateManager:
    """
    Manages base state validation, immutable cloning, and freshness verification.
    """

    @classmethod
    def compute_state_hash(cls, state: DigitalTwinState) -> str:
        """
        Computes a deterministic SHA-256 fingerprint of the base digital twin state.
        """
        fingerprint_dict = {
            "base_state_id": state.base_state_id,
            "timestamp": state.timestamp.isoformat(),
            "telemetry_node_id": state.telemetry.node_id,
            "telemetry_timestamp": state.telemetry.timestamp.isoformat(),
            "telemetry_source": state.telemetry.quality.source,
            "telemetry_measurements": {
                k: round(v, 4) if isinstance(v, (int, float)) else v
                for k, v in state.telemetry.measurements.model_dump().items()
                if v is not None
            },
            "hazard_count": len(state.hazards),
            "hazard_severities": [round(h.severity, 4) for h in sorted(state.hazards, key=lambda h: h.hazard_id)],
            "prediction_count": len(state.predictions),
            "compound_count": len(state.compound_events),
            "zone_count": len(state.population_zones),
            "total_population": sum(z.population for z in state.population_zones),
            "edge_count": len(state.road_network.edges),
            "shelter_count": len(state.shelters),
            "simulated": state.simulated,
        }
        serialized = json.dumps(fingerprint_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def validate_freshness(
        cls,
        state: DigitalTwinState,
        max_stale_seconds: int = 300,
        now: Optional[datetime] = None,
    ) -> None:
        """
        Validates whether base state telemetry satisfies freshness gates.
        Raises StaleDataException if telemetry age exceeds max_stale_seconds.
        """
        curr_time = now or datetime.now(timezone.utc)
        curr_time_utc = curr_time if curr_time.tzinfo else curr_time.replace(tzinfo=timezone.utc)
        t_ts = state.telemetry.timestamp
        t_ts_utc = t_ts if t_ts.tzinfo else t_ts.replace(tzinfo=timezone.utc)

        age_seconds = (curr_time_utc - t_ts_utc).total_seconds()
        if age_seconds > max_stale_seconds:
            raise StaleDataException(
                f"Base state telemetry '{state.telemetry.node_id}' is STALE (age {age_seconds:.1f}s > {max_stale_seconds}s limit). Simulation rejected."
            )

    @classmethod
    def clone_state(cls, state: DigitalTwinState) -> DigitalTwinState:
        """
        Creates an independent deep copy of the digital twin state.
        Ensures strict isolation so live/observed objects are never modified.
        """
        cloned = state.model_copy(deep=True)
        if not cloned.provenance_hash:
            cloned.provenance_hash = cls.compute_state_hash(cloned)
        return cloned
