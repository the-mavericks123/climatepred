"""
Deterministic provenance tracker for Phase 10 Evaluation.
Generates reproducible SHA-256 digests over evaluation inputs and results.
"""

import hashlib
import json
from typing import Any, Dict, Optional
from intelligence.evaluation.types import EvaluationMetrics


class EvaluationProvenanceTracker:
    """
    Computes deterministic SHA-256 provenance hashes for evaluation reports.
    """

    PROVENANCE_VERSION = "evaluation-prov-v1"

    @classmethod
    def build_canonical_payload(
        cls,
        model_version: str,
        dataset_id: str,
        dataset_version: str,
        status: str,
        sample_count: int,
        metrics: EvaluationMetrics,
    ) -> Dict[str, Any]:
        """Constructs canonical material payload for hashing."""
        metrics_dict = {
            k: round(v, 4) if isinstance(v, (int, float)) else v
            for k, v in metrics.model_dump().items()
            if v is not None
        }

        return {
            "model_version": str(model_version),
            "dataset_id": str(dataset_id),
            "dataset_version": str(dataset_version),
            "status": str(status),
            "sample_count": int(sample_count),
            "metrics": metrics_dict,
            "provenance_version": cls.PROVENANCE_VERSION,
        }

    @classmethod
    def compute_provenance_hash(
        cls,
        model_version: str,
        dataset_id: str,
        dataset_version: str,
        status: str,
        sample_count: int,
        metrics: EvaluationMetrics,
    ) -> str:
        """Generates SHA-256 digest from canonical material payload."""
        payload = cls.build_canonical_payload(
            model_version=model_version,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            status=status,
            sample_count=sample_count,
            metrics=metrics,
        )
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
