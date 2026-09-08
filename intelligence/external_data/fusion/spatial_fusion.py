"""
Global Spatial Grid and Sampling Strategy.
Provides multi-resolution spatial indexing across global climate regions and active hazard hotspots.
"""

import math
from typing import Any, Dict, List, Optional, Tuple
from intelligence.external_data.types import ExternalLocation


class GlobalSpatialGrid:
    """
    Configurable spatial sampling grid.
    Maintains 36 authoritative global climate reference stations spanning all
    major Köppen climate classifications and populated continents.
    Supports dynamic refinement around active disaster locations.
    """

    REFERENCE_STATIONS: List[Dict[str, Any]] = [
        # South Asia & India (Core deployment zone)
        {"id": "EXT-HYD-001", "name": "Hyderabad Station", "lat": 17.3850, "lon": 78.4867, "elevation": 542},
        {"id": "EXT-DEL-002", "name": "New Delhi Station", "lat": 28.6139, "lon": 77.2090, "elevation": 216},
        {"id": "EXT-MUM-003", "name": "Mumbai Coastal Station", "lat": 19.0760, "lon": 72.8777, "elevation": 14},
        {"id": "EXT-BLR-004", "name": "Bengaluru Station", "lat": 12.9716, "lon": 77.5946, "elevation": 920},

        # East & Southeast Asia
        {"id": "EXT-TYO-005", "name": "Tokyo Kanto Station", "lat": 35.6762, "lon": 139.6503, "elevation": 40},
        {"id": "EXT-BJS-006", "name": "Beijing Basin Station", "lat": 39.9042, "lon": 116.4074, "elevation": 43},
        {"id": "EXT-SIN-007", "name": "Singapore Equatorial Station", "lat": 1.3521, "lon": 103.8198, "elevation": 15},
        {"id": "EXT-JKT-008", "name": "Jakarta Java Station", "lat": -6.2088, "lon": 106.8456, "elevation": 8},
        {"id": "EXT-BKK-009", "name": "Bangkok Chao Phraya Station", "lat": 13.7563, "lon": 100.5018, "elevation": 5},

        # Middle East & Central Asia
        {"id": "EXT-DXB-010", "name": "Dubai Arid Station", "lat": 25.2048, "lon": 55.2708, "elevation": 5},
        {"id": "EXT-RUH-011", "name": "Riyadh Desert Station", "lat": 24.7136, "lon": 46.6753, "elevation": 612},
        {"id": "EXT-TAS-012", "name": "Tashkent Oasis Station", "lat": 41.2995, "lon": 69.2401, "elevation": 450},

        # Europe & Mediterranean
        {"id": "EXT-LON-013", "name": "London Maritime Station", "lat": 51.5074, "lon": -0.1278, "elevation": 35},
        {"id": "EXT-PAR-014", "name": "Paris Basin Station", "lat": 48.8566, "lon": 2.3522, "elevation": 35},
        {"id": "EXT-ATH-015", "name": "Athens Aegean Station", "lat": 37.9838, "lon": 23.7275, "elevation": 170},
        {"id": "EXT-MAD-016", "name": "Madrid Meseta Station", "lat": 40.4168, "lon": -3.7038, "elevation": 667},
        {"id": "EXT-OSL-017", "name": "Oslo Fjord Station", "lat": 59.9139, "lon": 10.7522, "elevation": 23},
        {"id": "EXT-IST-018", "name": "Istanbul Bosphorus Station", "lat": 41.0082, "lon": 28.9784, "elevation": 39},

        # North America
        {"id": "EXT-NYC-019", "name": "New York Atlantic Station", "lat": 40.7128, "lon": -74.0060, "elevation": 10},
        {"id": "EXT-LAX-020", "name": "Los Angeles Pacific Station", "lat": 34.0522, "lon": -118.2437, "elevation": 87},
        {"id": "EXT-MIA-021", "name": "Miami Subtropical Station", "lat": 25.7617, "lon": -80.1918, "elevation": 2},
        {"id": "EXT-CHI-022", "name": "Chicago Great Lakes Station", "lat": 41.8781, "lon": -87.6298, "elevation": 181},
        {"id": "EXT-YVR-023", "name": "Vancouver Coastal Station", "lat": 49.2827, "lon": -123.1207, "elevation": 70},
        {"id": "EXT-MEX-024", "name": "Mexico City Highland Station", "lat": 19.4326, "lon": -99.1332, "elevation": 2240},

        # South America
        {"id": "EXT-MAO-025", "name": "Manaus Amazon Rainforest Station", "lat": -3.1190, "lon": -60.0217, "elevation": 92},
        {"id": "EXT-SAO-026", "name": "São Paulo Plateau Station", "lat": -23.5505, "lon": -46.6333, "elevation": 760},
        {"id": "EXT-BUE-027", "name": "Buenos Aires Pampas Station", "lat": -34.6037, "lon": -58.3816, "elevation": 25},
        {"id": "EXT-LIM-028", "name": "Lima Arid Pacific Station", "lat": -12.0464, "lon": -77.0428, "elevation": 161},

        # Africa
        {"id": "EXT-CAI-029", "name": "Cairo Nile Basin Station", "lat": 30.0444, "lon": 31.2357, "elevation": 23},
        {"id": "EXT-NBO-030", "name": "Nairobi Rift Valley Station", "lat": -1.2921, "lon": 36.8219, "elevation": 1661},
        {"id": "EXT-LOS-031", "name": "Lagos Gulf of Guinea Station", "lat": 6.5244, "lon": 3.3792, "elevation": 10},
        {"id": "EXT-JNB-032", "name": "Johannesburg Highveld Station", "lat": -26.2041, "lon": 28.0473, "elevation": 1753},

        # Oceania
        {"id": "EXT-SYD-033", "name": "Sydney Harbour Station", "lat": -33.8688, "lon": 151.2093, "elevation": 19},
        {"id": "EXT-DRW-034", "name": "Darwin Tropical Station", "lat": -12.4634, "lon": 130.8456, "elevation": 31},
        {"id": "EXT-AKL-035", "name": "Auckland Station", "lat": -36.8485, "lon": 174.7633, "elevation": 20},

        # Polar & Cryosphere
        {"id": "EXT-LYR-036", "name": "Svalbard Arctic Cryosphere Station", "lat": 78.2232, "lon": 15.6267, "elevation": 130},
    ]

    @staticmethod
    def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes great-circle distance in kilometers using the Haversine formula."""
        r_earth = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r_earth * c

    @classmethod
    def get_reference_stations(cls) -> List[Dict[str, Any]]:
        return list(cls.REFERENCE_STATIONS)

    @classmethod
    def find_nearest_reference(cls, lat: float, lon: float) -> Tuple[Dict[str, Any], float]:
        """Finds closest reference grid station and distance in km."""
        best_station = cls.REFERENCE_STATIONS[0]
        min_dist = float("inf")

        for station in cls.REFERENCE_STATIONS:
            dist = cls.haversine_distance_km(lat, lon, station["lat"], station["lon"])
            if dist < min_dist:
                min_dist = dist
                best_station = station

        return best_station, round(min_dist, 1)
