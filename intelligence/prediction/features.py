"""Temporal feature extraction for the Phase 3 Prediction Engine.
Extracts chronological time-series features from historical telemetry packets,
enforces strict anti-leakage time filtering, and handles irregular sampling.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

from intelligence.core.contracts.telemetry import NormalizedTelemetry


class SingleVariableSeries(BaseModel):
    """Container for chronological (timestamp, value) observations of one measurement."""
    variable_name: str
    timestamps: List[datetime] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.values)

    def is_empty(self) -> bool:
        return len(self.values) == 0


class TemporalTrendSummary(BaseModel):
    """Statistical summary of temporal evolution for a single physical variable."""
    variable_name: str
    current_value: Optional[float] = None
    sample_count: int = 0
    history_span_minutes: float = 0.0
    rate_of_change_per_minute: float = 0.0
    trend_variance: float = 0.0  # Mean squared residual from linear trend
    is_insufficient: bool = True
    direction: str = "STABLE"  # "RISING", "FALLING", "STABLE"


class TemporalFeatureExtractor:
    """
    Extracts time-indexed variable series from a current NormalizedTelemetry and historical list.
    Strictly filters out any observations with timestamp > prediction_time (anti-leakage guarantee).
    Sorts chronologically and deduplicates observations.
    """

    SUPPORTED_VARIABLES = [
        "temperature",
        "humidity",
        "rainfall",
        "soil_moisture",
        "water_level",
        "pressure",
        "air_quality",
    ]

    def __init__(self, max_lookback_hours: float = 24.0, min_observations: int = 2):
        self.max_lookback_hours = max_lookback_hours
        self.min_observations = min_observations

    def extract_filtered_history(
        self,
        current: NormalizedTelemetry,
        history: List[NormalizedTelemetry],
        prediction_time: Optional[datetime] = None,
    ) -> List[NormalizedTelemetry]:
        """
        Returns chronological, deduplicated history records that fall within the valid lookback window
        and do not leak future information (strictly timestamp <= prediction_time).
        Excludes the current observation so that only pure historical context is returned.
        """
        effective_now = prediction_time or current.timestamp
        effective_now_utc = effective_now if effective_now.tzinfo else effective_now.replace(tzinfo=timezone.utc)
        earliest_allowed = effective_now_utc - timedelta(hours=self.max_lookback_hours)

        # Candidate pool: only historical records
        valid_candidates = []
        for t in history:
            t_utc = t.timestamp if t.timestamp.tzinfo else t.timestamp.replace(tzinfo=timezone.utc)
            if earliest_allowed <= t_utc <= effective_now_utc:
                valid_candidates.append((t_utc, t))

        # Sort chronologically by timestamp
        valid_candidates.sort(key=lambda x: x[0])

        # Deduplicate: if duplicate timestamps exist, keep the latest entry
        deduped: Dict[datetime, NormalizedTelemetry] = {}
        for ts, t in valid_candidates:
            deduped[ts] = t

        return [deduped[ts] for ts in sorted(deduped.keys())]

    def extract_series(
        self,
        current: NormalizedTelemetry,
        history: List[NormalizedTelemetry],
        prediction_time: Optional[datetime] = None,
    ) -> Dict[str, SingleVariableSeries]:
        """
        Builds chronological, deduplicated series for each physical sensor variable.
        Precondition: Only records with timestamp <= effective_prediction_time are included.
        """
        effective_now = prediction_time or current.timestamp
        effective_now_utc = effective_now if effective_now.tzinfo else effective_now.replace(tzinfo=timezone.utc)
        earliest_allowed = effective_now_utc - timedelta(hours=self.max_lookback_hours)

        # Collect all candidates (history + current)
        all_candidates: List[NormalizedTelemetry] = list(history) + [current]

        # 1. Anti-leakage filter: discard any observation with timestamp > prediction_time
        # 2. Window filter: discard observations older than max_lookback_hours
        valid_candidates = []
        for t in all_candidates:
            t_utc = t.timestamp if t.timestamp.tzinfo else t.timestamp.replace(tzinfo=timezone.utc)
            if earliest_allowed <= t_utc <= effective_now_utc:
                valid_candidates.append((t_utc, t))

        # 3. Sort chronologically by timestamp
        valid_candidates.sort(key=lambda x: x[0])

        # 4. Deduplicate: if duplicate timestamps exist, keep the latest entry
        deduped: Dict[datetime, NormalizedTelemetry] = {}
        for ts, t in valid_candidates:
            deduped[ts] = t

        sorted_records = [deduped[ts] for ts in sorted(deduped.keys())]

        # 5. Extract series per variable
        series_map: Dict[str, SingleVariableSeries] = {
            var: SingleVariableSeries(variable_name=var) for var in self.SUPPORTED_VARIABLES
        }

        for record in sorted_records:
            m = record.measurements
            record_ts = record.timestamp if record.timestamp.tzinfo else record.timestamp.replace(tzinfo=timezone.utc)

            for var in self.SUPPORTED_VARIABLES:
                val = getattr(m, var, None)
                if val is not None:
                    series_map[var].timestamps.append(record_ts)
                    series_map[var].values.append(float(val))

        return series_map

    def compute_trend(self, series: SingleVariableSeries) -> TemporalTrendSummary:
        """
        Computes deterministic rate of change and trend stability using ordinary least squares.
        Handles irregular time steps between observations.
        """
        n = series.count
        var_name = series.variable_name

        if n == 0:
            return TemporalTrendSummary(
                variable_name=var_name,
                current_value=None,
                sample_count=0,
                is_insufficient=True,
                direction="STABLE",
            )

        current_val = series.values[-1]

        if n < self.min_observations:
            return TemporalTrendSummary(
                variable_name=var_name,
                current_value=current_val,
                sample_count=n,
                history_span_minutes=0.0,
                rate_of_change_per_minute=0.0,
                trend_variance=0.0,
                is_insufficient=True,
                direction="STABLE",
            )

        # Convert timestamps to elapsed minutes from the first observation
        t0 = series.timestamps[0]
        x_minutes = [(t - t0).total_seconds() / 60.0 for t in series.timestamps]
        y_values = series.values
        span_minutes = x_minutes[-1] - x_minutes[0]

        if span_minutes <= 0.0:
            # All observations share identical timestamp (zero delta t)
            return TemporalTrendSummary(
                variable_name=var_name,
                current_value=current_val,
                sample_count=n,
                history_span_minutes=0.0,
                rate_of_change_per_minute=0.0,
                trend_variance=0.0,
                is_insufficient=True,
                direction="STABLE",
            )

        # OLS Linear Regression: slope = Cov(x, y) / Var(x)
        x_mean = sum(x_minutes) / n
        y_mean = sum(y_values) / n

        numerator = sum((x_minutes[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
        denominator = sum((x_minutes[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0.0:
            slope = 0.0
        else:
            slope = numerator / denominator

        # Intercept
        intercept = y_mean - (slope * x_mean)

        # Residual variance
        residuals = [y_values[i] - (slope * x_minutes[i] + intercept) for i in range(n)]
        trend_variance = sum(r ** 2 for r in residuals) / n

        # Trend direction classification based on relative change rate
        # Threshold: if slope produces > 1% change over 1 hour
        hourly_projected_change = abs(slope * 60.0)
        direction = "STABLE"
        if hourly_projected_change >= 0.1:  # Non-trivial rate
            direction = "RISING" if slope > 0 else "FALLING"

        return TemporalTrendSummary(
            variable_name=var_name,
            current_value=current_val,
            sample_count=n,
            history_span_minutes=round(span_minutes, 2),
            rate_of_change_per_minute=round(slope, 6),
            trend_variance=round(trend_variance, 6),
            is_insufficient=False,
            direction=direction,
        )
