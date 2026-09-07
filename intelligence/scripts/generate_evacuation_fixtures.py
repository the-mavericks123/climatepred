"""
Fixture generator for Phase 6: Dynamic Evacuation & Adaptive Route Intelligence.
Generates 16 deterministic benchmark scenario fixtures into shared/fixtures/ and intelligence/tests/fixtures/.
"""

from datetime import datetime, timezone
import json
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SHARED_FIXTURES_DIR = WORKSPACE_ROOT / "shared" / "fixtures"
TEST_FIXTURES_DIR = WORKSPACE_ROOT / "intelligence" / "tests" / "fixtures"

SHARED_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
TEST_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

T_NOW = "2026-09-07T14:30:00Z"


def _make_base_network():
    return {
        "network_id": "NET-METRO-01",
        "nodes": ["ZONE-A", "INT-1", "INT-2", "INT-3", "SHELTER-NORTH", "SHELTER-EAST"],
        "edges": [
            {
                "edge_id": "ROAD-A-1",
                "from_node": "ZONE-A",
                "to_node": "INT-1",
                "distance_km": 3.0,
                "travel_time_minutes": 6.0,
                "accessibility": 0.90,
                "hazard_risk": 0.05,
                "closed": False,
                "features": {"lanes": 2},
                "simulated": True,
            },
            {
                "edge_id": "ROAD-1-NORTH",
                "from_node": "INT-1",
                "to_node": "SHELTER-NORTH",
                "distance_km": 4.0,
                "travel_time_minutes": 8.0,
                "accessibility": 0.95,
                "hazard_risk": 0.05,
                "closed": False,
                "features": {"lanes": 4},
                "simulated": True,
            },
            {
                "edge_id": "ROAD-A-2",
                "from_node": "ZONE-A",
                "to_node": "INT-2",
                "distance_km": 2.5,
                "travel_time_minutes": 5.0,
                "accessibility": 0.85,
                "hazard_risk": 0.10,
                "closed": False,
                "features": {"lanes": 2},
                "simulated": True,
            },
            {
                "edge_id": "ROAD-2-EAST",
                "from_node": "INT-2",
                "to_node": "SHELTER-EAST",
                "distance_km": 5.0,
                "travel_time_minutes": 10.0,
                "accessibility": 0.90,
                "hazard_risk": 0.10,
                "closed": False,
                "features": {"lanes": 2},
                "simulated": True,
            },
        ],
    }


def generate_all_fixtures():
    fixtures = {}

    # 1. Normal baseline (low hazard, no evacuation required)
    fixtures["evacuation_normal.json"] = {
        "scenario_id": "SCENARIO-1-NORMAL",
        "description": "Normal ambient zone without active hazard -> stand-by status, 0 evacuees",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 8000,
                "population_density": 2000.0,
                "age_0_14_ratio": 0.15,
                "age_65_plus_ratio": 0.10,
                "disability_ratio": 0.03,
                "healthcare_access": 0.85,
                "road_accessibility": 0.90,
                "critical_facility_access": 0.90,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 5000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.02,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [],
    }

    # 2. Critical Flood in Zone A -> Full Evacuation to North Shelter
    fixtures["evacuation_flood.json"] = {
        "scenario_id": "SCENARIO-2-FLOOD",
        "description": "Critical flood in lowland zone -> immediate evacuation to North shelter",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 10000,
                "age_0_14_ratio": 0.20,
                "age_65_plus_ratio": 0.15,
                "disability_ratio": 0.05,
                "healthcare_access": 0.40,
                "road_accessibility": 0.70,
                "critical_facility_access": 0.65,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 12000,
                "current_occupancy": 1000,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-01",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.92,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"water_level_m": 2.9, "zone_id": "ZONE-A"},
                "drivers": ["Severe surface inundation"],
                "model_version": "flood-v1",
                "provenance_hash": "a" * 64,
                "simulated": False,
            }
        ],
    }

    # 3. High Vulnerability Sector (Elderly + Disability concentration)
    fixtures["evacuation_high_vulnerability.json"] = {
        "scenario_id": "SCENARIO-3-HIGH-VULN",
        "description": "Moderate hazard but acute demographic vulnerability elevates priority",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 6000,
                "age_0_14_ratio": 0.25,
                "age_65_plus_ratio": 0.35,
                "disability_ratio": 0.12,
                "socioeconomic_vulnerability": 0.85,
                "healthcare_access": 0.20,
                "road_accessibility": 0.50,
                "critical_facility_access": 0.40,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 8000,
                "current_occupancy": 500,
                "accessibility": 0.90,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-02",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.65,
                "confidence": 0.88,
                "classification": "HIGH",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"water_level_m": 1.6, "zone_id": "ZONE-A"},
                "drivers": ["Rising river level"],
                "model_version": "flood-v1",
                "provenance_hash": "b" * 64,
                "simulated": False,
            }
        ],
    }

    # 4. Predicted Flood +60m Forecast Horizon
    fixtures["evacuation_predicted_flood.json"] = {
        "scenario_id": "SCENARIO-4-PREDICTED",
        "description": "Future flood crest forecast (+60m) initiates anticipatory evacuation directive",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 9000,
                "healthcare_access": 0.50,
                "road_accessibility": 0.75,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 10000,
                "current_occupancy": 1000,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "predictions": [
            {
                "prediction_id": "PRED-FLD-60M-01",
                "hazard": "flood",
                "status": "DETECTED",
                "forecast_horizon_minutes": 60,
                "prediction_time": T_NOW,
                "forecast_time": T_NOW,
                "severity": 0.88,
                "confidence": 0.84,
                "model_version": "prediction-flood-v1",
                "provenance_hash": "p" * 64,
                "simulated": False,
                "predicted_features": {"zone_id": "ZONE-A"},
            }
        ],
    }

    # 5. Short Dangerous Route vs Longer Safe Route
    net_hazard_compare = {
        "network_id": "NET-COMPARE",
        "nodes": ["ZONE-A", "INT-DANGER", "INT-SAFE", "SHELTER-SAFE"],
        "edges": [
            {
                "edge_id": "ROAD-SHORT-DANGEROUS",
                "from_node": "ZONE-A",
                "to_node": "INT-DANGER",
                "distance_km": 2.0,
                "travel_time_minutes": 4.0,
                "accessibility": 0.90,
                "hazard_risk": 0.90,  # Critical hazard!
                "closed": False,
                "simulated": True,
            },
            {
                "edge_id": "ROAD-DANGER-SHELTER",
                "from_node": "INT-DANGER",
                "to_node": "SHELTER-SAFE",
                "distance_km": 2.0,
                "travel_time_minutes": 4.0,
                "accessibility": 0.90,
                "hazard_risk": 0.85,
                "closed": False,
                "simulated": True,
            },
            {
                "edge_id": "ROAD-LONG-SAFE",
                "from_node": "ZONE-A",
                "to_node": "INT-SAFE",
                "distance_km": 5.0,
                "travel_time_minutes": 10.0,
                "accessibility": 0.95,
                "hazard_risk": 0.05,  # Very safe!
                "closed": False,
                "simulated": True,
            },
            {
                "edge_id": "ROAD-SAFE-SHELTER",
                "from_node": "INT-SAFE",
                "to_node": "SHELTER-SAFE",
                "distance_km": 4.0,
                "travel_time_minutes": 8.0,
                "accessibility": 0.95,
                "hazard_risk": 0.05,
                "closed": False,
                "simulated": True,
            },
        ],
    }
    fixtures["evacuation_hazard_vs_short.json"] = {
        "scenario_id": "SCENARIO-5-HAZARD-VS-SHORT",
        "description": "Short route has extreme hazard -> algorithm must choose longer safe route",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 5000,
                "healthcare_access": 0.60,
                "road_accessibility": 0.80,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-SAFE",
                "name": "Highland Safe Refuge",
                "latitude": 37.80,
                "longitude": -122.38,
                "capacity": 8000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-SAFE",
                "simulated": True,
            }
        ],
        "road_network": net_hazard_compare,
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-03",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.85,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["Severe surface inundation"],
                "model_version": "flood-v1",
                "provenance_hash": "c" * 64,
                "simulated": False,
            }
        ],
    }

    # 6. Closed Bridge on Primary Route
    net_closure = _make_base_network()
    # Close ROAD-1-NORTH
    for e in net_closure["edges"]:
        if e["edge_id"] == "ROAD-1-NORTH":
            e["closed"] = True
            e["closure_reason"] = "Structural breach from storm surge"

    fixtures["evacuation_road_closure.json"] = {
        "scenario_id": "SCENARIO-6-CLOSURE",
        "description": "Primary northern arterial bridge closed -> reroutes to Shelter East",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 6000,
                "healthcare_access": 0.50,
                "road_accessibility": 0.70,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 5000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            },
            {
                "shelter_id": "SHELTER-EAST",
                "name": "East Regional Complex",
                "latitude": 37.76,
                "longitude": -122.35,
                "capacity": 7000,
                "current_occupancy": 1000,
                "accessibility": 0.90,
                "safe": True,
                "hazard_risk": 0.08,
                "node_id": "SHELTER-EAST",
                "simulated": True,
            },
        ],
        "road_network": net_closure,
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-04",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.88,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["Flash flood inundation"],
                "model_version": "flood-v1",
                "provenance_hash": "d" * 64,
                "simulated": False,
            }
        ],
    }

    # 7. Multiple candidate shelters available
    fixtures["evacuation_multiple_shelters.json"] = {
        "scenario_id": "SCENARIO-7-MULTI-SHELTER",
        "description": "Multiple safe shelters -> algorithm selects lowest composite route cost",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 5000,
                "healthcare_access": 0.60,
                "road_accessibility": 0.80,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 6000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.04,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            },
            {
                "shelter_id": "SHELTER-EAST",
                "name": "East Regional Complex",
                "latitude": 37.76,
                "longitude": -122.35,
                "capacity": 7000,
                "current_occupancy": 1000,
                "accessibility": 0.90,
                "safe": True,
                "hazard_risk": 0.08,
                "node_id": "SHELTER-EAST",
                "simulated": True,
            },
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-05",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.85,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["River breach"],
                "model_version": "flood-v1",
                "provenance_hash": "e" * 64,
                "simulated": False,
            }
        ],
    }

    # 8. Shelter Capacity Overflow / Split
    fixtures["evacuation_capacity_split.json"] = {
        "scenario_id": "SCENARIO-8-CAPACITY-SPLIT",
        "description": "Preferred shelter has limited capacity -> allocates up to capacity limit",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 12000,
                "healthcare_access": 0.50,
                "road_accessibility": 0.80,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Small Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 4000,
                "current_occupancy": 1000,  # 3000 available
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-06",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.90,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["Widespread inundation"],
                "model_version": "flood-v1",
                "provenance_hash": "f" * 64,
                "simulated": False,
            }
        ],
    }

    # 9. Multiple Evacuation Zones (Greedy Priority Allocation)
    net_multi_zone = {
        "network_id": "NET-MULTI-ZONE",
        "nodes": ["ZONE-A", "ZONE-B", "SHELTER-SHARED"],
        "edges": [
            {
                "edge_id": "ROAD-A-SHARED",
                "from_node": "ZONE-A",
                "to_node": "SHELTER-SHARED",
                "distance_km": 4.0,
                "travel_time_minutes": 8.0,
                "accessibility": 0.90,
                "hazard_risk": 0.05,
                "closed": False,
                "simulated": True,
            },
            {
                "edge_id": "ROAD-B-SHARED",
                "from_node": "ZONE-B",
                "to_node": "SHELTER-SHARED",
                "distance_km": 4.0,
                "travel_time_minutes": 8.0,
                "accessibility": 0.90,
                "hazard_risk": 0.05,
                "closed": False,
                "simulated": True,
            },
        ],
    }
    fixtures["evacuation_multiple_zones.json"] = {
        "scenario_id": "SCENARIO-9-MULTI-ZONE",
        "description": "Two zones competing for shared shelter -> higher priority zone receives full allocation",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 4000,
                "age_65_plus_ratio": 0.30,
                "disability_ratio": 0.10,
                "healthcare_access": 0.30,
                "simulated": True,
            },
            {
                "zone_id": "ZONE-B",
                "population": 4000,
                "age_65_plus_ratio": 0.08,
                "disability_ratio": 0.02,
                "healthcare_access": 0.80,
                "simulated": True,
            },
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-SHARED",
                "name": "Central Shared Facility",
                "latitude": 37.77,
                "longitude": -122.40,
                "capacity": 5000,
                "current_occupancy": 0,  # 5000 available
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-SHARED",
                "simulated": True,
            }
        ],
        "road_network": net_multi_zone,
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-A",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.95,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["High severity flood"],
                "model_version": "flood-v1",
                "provenance_hash": "a" * 64,
                "simulated": False,
            },
            {
                "hazard_id": "HAZ-FLD-B",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.70,
                "confidence": 0.88,
                "classification": "HIGH",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.75, "lon": -122.43},
                "features": {"zone_id": "ZONE-B"},
                "drivers": ["Moderate flood"],
                "model_version": "flood-v1",
                "provenance_hash": "b" * 64,
                "simulated": False,
            },
        ],
    }

    # 10. No Feasible Route (Isolated Island)
    net_isolated = {
        "network_id": "NET-ISOLATED",
        "nodes": ["ZONE-ISOLATED", "SHELTER-NORTH"],
        "edges": [
            {
                "edge_id": "ROAD-COLLAPSED",
                "from_node": "ZONE-ISOLATED",
                "to_node": "SHELTER-NORTH",
                "distance_km": 4.0,
                "travel_time_minutes": 8.0,
                "accessibility": 0.0,
                "hazard_risk": 0.98,
                "closed": True,
                "closure_reason": "Bridge collapse",
                "simulated": True,
            }
        ],
    }
    fixtures["evacuation_no_route.json"] = {
        "scenario_id": "SCENARIO-10-NO-ROUTE",
        "description": "All access routes collapsed/closed -> NO_ROUTE status and ALL_ROADS_CLOSED reason",
        "zones": [
            {
                "zone_id": "ZONE-ISOLATED",
                "population": 5000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 10000,
                "current_occupancy": 0,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": net_isolated,
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-ISO",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.95,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-ISOLATED"},
                "drivers": ["Catastrophic flooding"],
                "model_version": "flood-v1",
                "provenance_hash": "c" * 64,
                "simulated": False,
            }
        ],
    }

    # 11. Unsafe Shelter Destination
    fixtures["evacuation_unsafe_shelter.json"] = {
        "scenario_id": "SCENARIO-11-UNSAFE-SHELTER",
        "description": "Candidate shelter is in direct flood inundation zone -> marked UNSAFE",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 4000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-FLOODED",
                "name": "Flooded Riverside Hall",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 5000,
                "current_occupancy": 0,
                "accessibility": 0.30,
                "safe": False,
                "hazard_risk": 0.85,  # Too dangerous
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-07",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.88,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["High water level"],
                "model_version": "flood-v1",
                "provenance_hash": "g" * 64,
                "simulated": False,
            }
        ],
    }

    # 12. Cascade-Induced Road Degradation
    fixtures["evacuation_cascade.json"] = {
        "scenario_id": "SCENARIO-12-CASCADE",
        "description": "Phase 4 cascading road failure dynamically degrades primary route",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 6000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 8000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            },
            {
                "shelter_id": "SHELTER-EAST",
                "name": "East Regional Complex",
                "latitude": 37.76,
                "longitude": -122.35,
                "capacity": 8000,
                "current_occupancy": 500,
                "accessibility": 0.90,
                "safe": True,
                "hazard_risk": 0.08,
                "node_id": "SHELTER-EAST",
                "simulated": True,
            },
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-08",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.85,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["High flood level"],
                "model_version": "flood-v1",
                "provenance_hash": "h" * 64,
                "simulated": False,
            }
        ],
        "compound_events": [
            {
                "event_id": "COMP-CASCADE-ROAD-01",
                "event_type": "CASCADE",
                "severity": 0.90,
                "confidence": 0.85,
                "timestamp": T_NOW,
                "chain": ["flood", "inferred_road_failure_risk", "inferred_access_loss"],
                "relationships": [
                    {
                        "from_state": "flood",
                        "to_state": "inferred_road_failure_risk",
                        "relationship_type": "CASCADE",
                        "rule_id": "FLOOD-ROAD-001",
                        "explanation": "ROAD-A-1 bridge overtopping risk",
                        "weight": 1.2,
                    }
                ],
                "rule_version": "compound-v1",
                "drivers": ["Cascading road degradation along ROAD-A-1"],
                "simulated": False,
                "provenance_hash": "i" * 64,
            }
        ],
    }

    # 13. Stale Road Network Data
    fixtures["evacuation_stale_data.json"] = {
        "scenario_id": "SCENARIO-13-STALE-DATA",
        "description": "Road telemetry exceeds freshness limits -> confidence discounted",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 5000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 8000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-09",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.85,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["High water level"],
                "model_version": "flood-v1",
                "provenance_hash": "j" * 64,
                "simulated": False,
            }
        ],
    }

    # 14. Missing Shelter Data / No Available Shelters
    fixtures["evacuation_no_shelter.json"] = {
        "scenario_id": "SCENARIO-14-NO-SHELTER",
        "description": "All available shelters have 0 capacity remaining -> NO_SHELTER status",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 5000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-FULL-1",
                "name": "Full Municipal Refuge",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 3000,
                "current_occupancy": 3000,  # 0 available
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-10",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.88,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["Severe surface inundation"],
                "model_version": "flood-v1",
                "provenance_hash": "k" * 64,
                "simulated": False,
            }
        ],
    }

    # 15. Explicit Synthetic Demo Dataset
    fixtures["evacuation_synthetic_demo.json"] = {
        "scenario_id": "SCENARIO-15-SYNTHETIC-DEMO",
        "description": "Explicit synthetic demo flags propagate strictly to recommendation.simulated = True",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 5000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Civic Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 8000,
                "current_occupancy": 500,
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-11",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.85,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["River breach"],
                "model_version": "flood-v1",
                "provenance_hash": "l" * 64,
                "simulated": False,
            }
        ],
    }

    # 16. Partial Capacity Allocation
    fixtures["evacuation_partial_capacity.json"] = {
        "scenario_id": "SCENARIO-16-PARTIAL-CAPACITY",
        "description": "Shelter has capacity for 2,500 but demand is 5,000 -> status PARTIAL_CAPACITY",
        "zones": [
            {
                "zone_id": "ZONE-A",
                "population": 8000,
                "simulated": True,
            }
        ],
        "shelters": [
            {
                "shelter_id": "SHELTER-NORTH",
                "name": "North Intermediate Center",
                "latitude": 37.78,
                "longitude": -122.40,
                "capacity": 3000,
                "current_occupancy": 500,  # 2500 available
                "accessibility": 0.95,
                "safe": True,
                "hazard_risk": 0.05,
                "node_id": "SHELTER-NORTH",
                "simulated": True,
            }
        ],
        "road_network": _make_base_network(),
        "hazards": [
            {
                "hazard_id": "HAZ-FLD-12",
                "hazard": "flood",
                "status": "DETECTED",
                "severity": 0.88,
                "confidence": 0.90,
                "classification": "CRITICAL",
                "timestamp": T_NOW,
                "forecast_horizon_minutes": 0,
                "location": {"lat": 37.77, "lon": -122.41},
                "features": {"zone_id": "ZONE-A"},
                "drivers": ["High water level"],
                "model_version": "flood-v1",
                "provenance_hash": "m" * 64,
                "simulated": False,
            }
        ],
    }

    # Write all fixtures to shared/fixtures/ and intelligence/tests/fixtures/
    for filename, content in fixtures.items():
        shared_path = SHARED_FIXTURES_DIR / filename
        test_path = TEST_FIXTURES_DIR / filename
        shared_path.write_text(json.dumps(content, indent=2), encoding="utf-8")
        test_path.write_text(json.dumps(content, indent=2), encoding="utf-8")
        print(f"Generated {filename}")

    print(f"\nSuccessfully generated {len(fixtures)} benchmark scenario fixtures.")


if __name__ == "__main__":
    generate_all_fixtures()
