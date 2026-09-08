"""
Open-Meteo External Meteorological Data Provider.
Authoritative source for global temperature, humidity, precipitation, pressure, wind, and forecast.
"""

from datetime import datetime, timezone
import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from intelligence.core.logging import get_logger
from intelligence.external_data.cache import ExternalDataCache
from intelligence.external_data.provenance import ExternalProvenanceTracker
from intelligence.external_data.quality import ObservationQualityGate
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    ExternalMeasurements,
    ExternalObservation,
    SourceType,
)

logger = get_logger("open_meteo_provider")


class OpenMeteoProvider:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    PROVIDER_NAME = "Open-Meteo"

    def __init__(self, cache: Optional[ExternalDataCache] = None, timeout_sec: float = 10.0):
        self.cache = cache or ExternalDataCache()
        self.timeout_sec = timeout_sec
        self.cache_ttl_sec = 600.0  # 10 minutes

    def fetch_point_weather(
        self,
        lat: float,
        lon: float,
        station_name: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[ExternalObservation]:
        """
        Fetches live current weather and hourly forecast from Open-Meteo for a given point.
        Normalizes to canonical ExternalObservation.
        Strictly preserves water_level = None (never 0.0).
        """
        cache_key = f"open_meteo_{lat:.3f}_{lon:.3f}"
        breaker = self.cache.get_breaker("open_meteo")

        if not force_refresh:
            cached_data, is_fresh = self.cache.get(cache_key)
            if cached_data is not None:
                if is_fresh:
                    return cached_data
                # If circuit breaker is open or we want to save bandwidth, can return stale
                if not breaker.can_attempt():
                    cached_copy = cached_data.model_copy()
                    cached_copy.epistemic_status = EpistemicStatus.STALE
                    return cached_copy

        if not breaker.can_attempt():
            logger.warning("Open-Meteo circuit breaker is OPEN. Skipping network fetch.")
            cached_data, _ = self.cache.get(cache_key)
            if cached_data:
                copy_data = cached_data.model_copy()
                copy_data.epistemic_status = EpistemicStatus.STALE
                return copy_data
            return None

        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,surface_pressure,wind_speed_10m,wind_direction_10m",
            "hourly": "temperature_2m,precipitation_probability,precipitation,surface_pressure",
            "forecast_days": 1,
            "timezone": "UTC",
        }
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ClimateEyeView/2.0 (Climate Disaster Early Warning; contact@climateeye.local)",
                "Accept": "application/json",
            },
        )

        try:
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status != 200:
                    raise IOError(f"Open-Meteo returned status {resp.status}")
                raw_json = json.loads(resp.read().decode("utf-8"))

            breaker.record_success()
            obs = self._normalize(raw_json, lat, lon, url, station_name)
            if obs:
                self.cache.set(cache_key, obs, self.cache_ttl_sec)
            return obs

        except Exception as exc:
            breaker.record_failure()
            logger.warning(f"Failed to fetch Open-Meteo data for ({lat}, {lon}): {exc}")
            cached_data, _ = self.cache.get(cache_key)
            if cached_data:
                copy_data = cached_data.model_copy()
                copy_data.epistemic_status = EpistemicStatus.STALE
                return copy_data
            return None

    def _normalize(
        self,
        data: Dict[str, Any],
        req_lat: float,
        req_lon: float,
        source_url: str,
        station_name: Optional[str],
    ) -> Optional[ExternalObservation]:
        current = data.get("current", {})
        if not current:
            return None

        now_utc = datetime.now(timezone.utc)
        raw_time_str = current.get("time")
        if raw_time_str:
            try:
                obs_time = datetime.fromisoformat(raw_time_str).replace(tzinfo=timezone.utc)
            except ValueError:
                obs_time = now_utc
        else:
            obs_time = now_utc

        elevation = data.get("elevation")
        lat = data.get("latitude", req_lat)
        lon = data.get("longitude", req_lon)
        location = ExternalLocation(
            lat=lat,
            lon=lon,
            elevation_m=elevation,
            name=station_name or f"GRID-LAT{lat:.2f}-LON{lon:.2f}",
        )

        temp = current.get("temperature_2m")
        apparent_temp = current.get("apparent_temperature")
        humidity = current.get("relative_humidity_2m")
        pressure = current.get("surface_pressure")
        precipitation = current.get("precipitation") or current.get("rain") or 0.0
        wind_speed_raw = current.get("wind_speed_10m")
        # Convert km/h to m/s if Open-Meteo returns km/h (default is km/h in current)
        wind_speed_ms = round(wind_speed_raw / 3.6, 2) if wind_speed_raw is not None else None
        wind_dir = current.get("wind_direction_10m")

        # CRITICAL PHYSICAL INVARIANT:
        # Open-Meteo provides atmospheric measurements, NOT in-stream hydrological river level.
        # water_level MUST be None, never coerced to 0.0!
        measurements = ExternalMeasurements(
            temperature=temp,
            apparent_temperature=apparent_temp,
            humidity=humidity,
            pressure=pressure,
            precipitation=precipitation,
            wind_speed=wind_speed_ms,
            wind_direction=wind_dir,
            soil_moisture=None,
            air_quality=None,
            water_level=None,  # STRICTLY None
        )

        quality = ObservationQualityGate.evaluate(
            location=location,
            measurements=measurements,
            obs_timestamp=obs_time,
            received_at=now_utc,
        )

        provenance = ExternalProvenanceTracker.create_provenance(
            provider=self.PROVIDER_NAME,
            source_url=source_url,
            retrieved_at=now_utc,
            source_timestamp=obs_time,
            lat=lat,
            lon=lon,
            measurements=measurements.model_dump(),
            version="1.0",
        )

        obs_id = f"OBS-METEO-{int(obs_time.timestamp())}-{abs(hash(f'{lat}_{lon}')) % 10000:04d}"

        return ExternalObservation(
            observation_id=obs_id,
            source="open_meteo",
            source_type=SourceType.WEATHER_API,
            timestamp=obs_time,
            received_at=now_utc,
            location=location,
            measurements=measurements,
            quality=quality,
            epistemic_status=EpistemicStatus.OBSERVED,
            simulated=False,
            provenance=provenance,
        )
