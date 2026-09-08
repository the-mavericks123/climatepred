"""
NASA FIRMS Active Wildfire Hotspot Feed Provider.
Ingests VIIRS and MODIS satellite observations, filters by confidence,
and performs spatial clustering into bounded wildfire hazard zones.
"""

import csv
from datetime import datetime, timezone
import io
import math
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from intelligence.core.logging import get_logger
from intelligence.external_data.cache import ExternalDataCache
from intelligence.external_data.types import (
    EpistemicStatus,
    ExternalLocation,
    GlobalDisasterEvent,
    GlobalHazardZone,
)

logger = get_logger("nasa_firms_provider")


class NasaFirmsProvider:
    """
    Ingests global 24-hour fire hotspots from NASA FIRMS.
    Clusters adjacent fire detections into active wildfire hazard zones.
    """
    PROVIDER_NAME = "NASA FIRMS"
    MODIS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv"
    VIIRS_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv"

    def __init__(self, cache: Optional[ExternalDataCache] = None, timeout_sec: float = 15.0):
        self.cache = cache or ExternalDataCache()
        self.timeout_sec = timeout_sec
        self.cache_ttl_sec = 900.0  # 15 minutes

    def fetch_active_fires(self, force_refresh: bool = False, max_points: int = 500) -> List[Dict[str, Any]]:
        """Fetches normalized active fire detection points."""
        cache_key = "firms_active_points"
        breaker = self.cache.get_breaker("nasa_firms")

        if not force_refresh:
            cached, is_fresh = self.cache.get(cache_key)
            if cached is not None and is_fresh:
                return cached
            if not breaker.can_attempt() and cached is not None:
                return cached

        if not breaker.can_attempt():
            cached, _ = self.cache.get(cache_key)
            return cached or []

        points = []
        try:
            req = urllib.request.Request(
                self.MODIS_URL,
                headers={"User-Agent": "ClimateEyeView/2.0 (Active Fire Detection)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status == 200:
                    csv_text = resp.read().decode("utf-8")
                    reader = csv.DictReader(io.StringIO(csv_text))
                    for row in reader:
                        try:
                            lat = float(row.get("latitude", 0))
                            lon = float(row.get("longitude", 0))
                            brightness = float(row.get("brightness", 0))
                            confidence_str = row.get("confidence", "50")
                            try:
                                confidence = float(confidence_str) / 100.0
                            except ValueError:
                                confidence = 0.5 if confidence_str == "nominal" else (0.9 if confidence_str == "high" else 0.3)
                            
                            # Filter low-confidence or negligible brightness
                            if confidence < 0.3 or brightness < 300.0:
                                continue

                            acq_date = row.get("acq_date", "")
                            acq_time = row.get("acq_time", "0000").zfill(4)
                            try:
                                dt_str = f"{acq_date} {acq_time[:2]}:{acq_time[2:]}:00"
                                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            except Exception:
                                dt = datetime.now(timezone.utc)

                            points.append({
                                "lat": lat,
                                "lon": lon,
                                "brightness_k": brightness,
                                "confidence": confidence,
                                "satellite": row.get("satellite", "Terra/Aqua"),
                                "timestamp": dt.isoformat(),
                                "source": "MODIS_C6_1",
                            })
                            if len(points) >= max_points:
                                break
                        except Exception:
                            continue

            breaker.record_success()
            self.cache.set(cache_key, points, self.cache_ttl_sec)
            return points

        except Exception as exc:
            breaker.record_failure()
            logger.warning(f"NASA FIRMS fetch failed: {exc}")
            cached, _ = self.cache.get(cache_key)
            return cached or []

    def cluster_fires(self, points: List[Dict[str, Any]], cluster_radius_km: float = 25.0) -> List[GlobalHazardZone]:
        """
        Clusters individual fire detection points into bounded wildfire hazard zones.
        Uses distance-based connected component grouping.
        """
        if not points:
            return []

        def haversine(lat1, lon1, lat2, lon2):
            r = 6371.0
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlam = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
            return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        visited = [False] * len(points)
        clusters: List[List[Dict[str, Any]]] = []

        for i in range(len(points)):
            if visited[i]:
                continue
            visited[i] = True
            current_cluster = [points[i]]
            queue = [points[i]]

            while queue:
                curr = queue.pop(0)
                for j in range(len(points)):
                    if not visited[j]:
                        d = haversine(curr["lat"], curr["lon"], points[j]["lat"], points[j]["lon"])
                        if d <= cluster_radius_km:
                            visited[j] = True
                            current_cluster.append(points[j])
                            queue.append(points[j])

            clusters.append(current_cluster)

        hazard_zones: List[GlobalHazardZone] = []
        now_utc = datetime.now(timezone.utc)

        for cluster in clusters:
            if not cluster:
                continue

            avg_lat = sum(p["lat"] for p in cluster) / len(cluster)
            avg_lon = sum(p["lon"] for p in cluster) / len(cluster)
            max_brightness = max(p["brightness_k"] for p in cluster)
            avg_confidence = sum(p["confidence"] for p in cluster) / len(cluster)

            # Severity heuristic: combination of cluster density and peak thermal brightness (300K - 500K)
            norm_brightness = min(1.0, max(0.0, (max_brightness - 310.0) / 150.0))
            density_factor = min(1.0, len(cluster) / 15.0)
            severity = round(0.5 * norm_brightness + 0.5 * density_factor, 2)
            severity = max(0.2, min(0.98, severity))

            radius_km = min(100.0, max(10.0, len(cluster) * 3.5))
            zone_id = f"ZONE-FIRE-{abs(hash(f'{avg_lat:.2f}_{avg_lon:.2f}')) % 100000:05d}"

            hazard_zones.append(
                GlobalHazardZone(
                    zone_id=zone_id,
                    hazard_type="WILDFIRE",
                    severity=severity,
                    confidence=round(avg_confidence, 2),
                    epistemic_status=EpistemicStatus.OBSERVED,
                    geometry={
                        "type": "Point",
                        "coordinates": [round(avg_lon, 4), round(avg_lat, 4)],
                    },
                    center=ExternalLocation(
                        lat=round(avg_lat, 4),
                        lon=round(avg_lon, 4),
                        name=f"Active Fire Cluster ({len(cluster)} hotspots)",
                    ),
                    radius_km=radius_km,
                    metrics={
                        "hotspot_count": len(cluster),
                        "peak_brightness_k": max_brightness,
                        "satellite": cluster[0]["satellite"],
                    },
                    drivers=[
                        f"NASA FIRMS thermal detection: {len(cluster)} active hotspots",
                        f"Peak brightness: {max_brightness:.1f} K",
                    ],
                    source="NASA FIRMS",
                    timestamp=now_utc,
                    simulated=False,
                    recommended_action="Deploy aerial thermal surveillance; issue localized wildfire alert.",
                )
            )

        return hazard_zones
