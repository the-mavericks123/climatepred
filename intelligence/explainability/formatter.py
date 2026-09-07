"""
Multi-tier explanation formatter for Phase 10 Explainability.
Renders SUMMARY, STANDARD, and DETAILED textual and structured presentations,
with an optional non-blocking LLM summary layer.
"""

from typing import Any, Dict, List, Optional
from intelligence.explainability.types import (
    ExplanationContract,
    ExplanationLevel,
    FactorAttribution,
)


class ExplanationFormatter:
    """
    Renders structured explanations at requested detail levels.
    """

    @classmethod
    def generate_summary_text(
        cls,
        target_type: str,
        target_id: str,
        classification: str,
        factors: List[FactorAttribution],
        custom_note: Optional[str] = None,
    ) -> str:
        """Renders a concise 1-2 sentence summary."""
        if custom_note:
            return custom_note

        top_factors = sorted(factors, key=lambda f: f.contribution, reverse=True)[:2]
        if top_factors:
            f_str = " and ".join(f"{f.display_name.lower()} (contribution {f.contribution:.2f})" for f in top_factors)
            return f"{classification} {target_type} '{target_id}' is primarily driven by {f_str}."
        return f"{classification} {target_type} '{target_id}' evaluated within nominal parameters."

    @classmethod
    def format_detailed_view(cls, explanation: ExplanationContract) -> Dict[str, Any]:
        """Returns the complete detailed view including all mathematical attribution and counterfactuals."""
        return explanation.model_dump()

    @classmethod
    def apply_optional_llm_summary(
        cls,
        structured_summary: str,
        llm_client: Optional[Any] = None,
    ) -> str:
        """
        Optional language layer. If an LLM is provided, generates an operator narrative.
        If LLM is absent or errors, cleanly defaults to the deterministic structured summary.
        """
        if llm_client is None:
            return structured_summary

        try:
            # Safe call if an LLM client adapter is injected
            narrative = llm_client.summarize(structured_summary)
            return narrative or structured_summary
        except Exception:
            # Fallback guarantee: deterministic response planner and explainability continue working
            return structured_summary
