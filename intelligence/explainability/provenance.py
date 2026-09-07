"""
Deterministic cryptographic provenance tracker for Phase 10 Explainability.
Generates reproducible SHA-256 digests over material explanation inputs,
factors, formulas, and evidence references while decoupling volatile metadata.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional
from intelligence.explainability.types import FactorAttribution, EvidenceReference, CounterfactualItem


class ExplanationProvenanceTracker:
    """
    Computes deterministic SHA-256 provenance hashes for explanation contracts.
    """

    PROVENANCE_VERSION = "explainability-prov-v1"

    @classmethod
    def build_canonical_payload(
        cls,
        target_type: str,
        target_id: str,
        model_version: str,
        classification: str,
        formula_name: Optional[str],
        formula_expression: Optional[str],
        factors: List[FactorAttribution],
        evidence: List[EvidenceReference],
        counterfactuals: List[CounterfactualItem],
        simulated: bool,
    ) -> Dict[str, Any]:
        """Constructs canonical material payload for hashing."""
        canon_factors = [
            {
                "factor_name": f.factor_name,
                "input_value": round(float(f.input_value), 4) if isinstance(f.input_value, (int, float)) else str(f.input_value),
                "normalized_value": round(float(f.normalized_value), 4),
                "weight": round(float(f.weight), 4),
                "contribution": round(float(f.contribution), 4),
            }
            for f in sorted(factors, key=lambda x: x.factor_name)
        ]

        canon_evidence = sorted([ref.id for ref in evidence])
        canon_cf = sorted([cf.condition for cf in counterfactuals])

        return {
            "target_type": str(target_type),
            "target_id": str(target_id),
            "model_version": str(model_version),
            "classification": str(classification),
            "formula_name": formula_name or "NONE",
            "formula_expression": formula_expression or "NONE",
            "factors": canon_factors,
            "evidence_ids": canon_evidence,
            "counterfactuals": canon_cf,
            "simulated": bool(simulated),
            "provenance_version": cls.PROVENANCE_VERSION,
        }

    @classmethod
    def compute_provenance_hash(
        cls,
        target_type: str,
        target_id: str,
        model_version: str,
        classification: str,
        formula_name: Optional[str] = None,
        formula_expression: Optional[str] = None,
        factors: Optional[List[FactorAttribution]] = None,
        evidence: Optional[List[EvidenceReference]] = None,
        counterfactuals: Optional[List[CounterfactualItem]] = None,
        simulated: bool = False,
    ) -> str:
        """Generates SHA-256 fingerprint from canonical material payload."""
        payload = cls.build_canonical_payload(
            target_type=target_type,
            target_id=target_id,
            model_version=model_version,
            classification=classification,
            formula_name=formula_name,
            formula_expression=formula_expression,
            factors=factors or [],
            evidence=evidence or [],
            counterfactuals=counterfactuals or [],
            simulated=simulated,
        )
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
