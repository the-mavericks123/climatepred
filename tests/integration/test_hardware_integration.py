"""
Climate Eye View S2 — Final Hardware + System Integration Test Suite
Post-Phase-12 Verification.
Tests hardware calibration, LoRa gateway packet decoding, MQTT ingestion,
epistemic status tagging, water-level absence in FloodModel, and multi-node support.
"""
import struct
import pytest
from datetime import datetime, timezone

from intelligence.calibration.hardware import (
    HardwareSensorCalibrator,
    HardwarePayloadProcessor,
    CalibrationStatus,
)
from intelligence.ingestion.lora_gateway import (
    LoRaGatewayBridge,
    LORA_PACKET_STRUCT,
    LORA_MAGIC,
)
from intelligence.core.contracts.telemetry import NormalizedTelemetry, SensorMeasurements
from intelligence.hazards.flood import FloodModel
from intelligence.hazards.types import HazardStatus
from intelligence.hazards.features import HazardFeatures
from intelligence.hazards.quality_gate import QualityGateVerdict


# =====================================================================
# 1. UNIT TESTS: Sensor Conversions & Calibration
# =====================================================================

class TestSensorCalibration:
    def setup_method(self):
        self.calibrator = HardwareSensorCalibrator()

    def test_dht11_validation_valid(self):
        temp_c, hum_pct, status, meta = self.calibrator.process_dht11(25.4, 60.0)
        assert temp_c == 25.4
        assert hum_pct == 60.0
        assert status == CalibrationStatus.UNVERIFIED

    def test_dht11_validation_out_of_range(self):
        temp_c, hum_pct, status, meta = self.calibrator.process_dht11(85.0, 150.0)
        assert temp_c is None
        assert hum_pct is None
        assert status == CalibrationStatus.FAILED

    def test_bmp280_pressure_validation(self):
        press_hpa, sec_temp, status, meta = self.calibrator.process_bmp280(1013.25, 25.1)
        assert press_hpa == 1013.25
        assert sec_temp == 25.1
        assert status == CalibrationStatus.CALIBRATED

        # Impossible atmospheric pressure
        press_hpa_bad, _, status_bad, _ = self.calibrator.process_bmp280(200.0)
        assert press_hpa_bad is None
        assert status_bad == CalibrationStatus.FAILED

    def test_gps_validation_valid(self):
        lat, lon, ele, status, meta = self.calibrator.process_gps(17.385044, 78.486671, 540.0, has_fix=True)
        assert lat == 17.385044
        assert lon == 78.486671
        assert ele == 540.0
        assert status == CalibrationStatus.CALIBRATED

    def test_gps_validation_null_island(self):
        # Coordinates (0.0, 0.0) must be rejected
        lat, lon, ele, status, meta = self.calibrator.process_gps(0.0, 0.0, has_fix=True)
        assert lat is None
        assert lon is None
        assert status == CalibrationStatus.FAILED

    def test_gps_validation_no_fix(self):
        lat, lon, ele, status, meta = self.calibrator.process_gps(17.385, 78.486, has_fix=False)
        assert lat is None
        assert lon is None
        assert status == CalibrationStatus.UNAVAILABLE

    def test_raindrop_conversion_dry(self):
        # Raw ADC ~4095 is dry
        rate, status, meta = self.calibrator.process_raindrop(4095)
        assert rate == 0.0
        assert status == CalibrationStatus.UNVERIFIED

    def test_raindrop_conversion_wet(self):
        # Raw ADC ~1500 indicates rain
        rate, status, meta = self.calibrator.process_raindrop(1500)
        assert rate > 0.0
        assert status == CalibrationStatus.UNVERIFIED

    def test_soil_moisture_calibration_dry_wet(self):
        # 3400 is dry -> 0%
        pct_dry, status_dry, _ = self.calibrator.process_soil_moisture(3400, adc_dry=3400, adc_wet=1400)
        assert pct_dry == 0.0
        assert status_dry == CalibrationStatus.UNVERIFIED

        # 1400 is wet -> 100%
        pct_wet, status_wet, _ = self.calibrator.process_soil_moisture(1400, adc_dry=3400, adc_wet=1400)
        assert pct_wet == 100.0
        assert status_wet == CalibrationStatus.UNVERIFIED

        # Midpoint ~2400 -> 50%
        pct_mid, status_mid, _ = self.calibrator.process_soil_moisture(2400, adc_dry=3400, adc_wet=1400)
        assert 45.0 <= pct_mid <= 55.0

    def test_optical_dust_conversion(self):
        # Voltage 0.65V is clean air -> low ug/m3 -> low AQI
        density, aqi, status, meta = self.calibrator.process_optical_dust(0.65)
        assert density > 0.0
        assert aqi is not None
        assert aqi <= 50.0
        assert status == CalibrationStatus.UNVERIFIED

    def test_bh1750_lux_validation(self):
        lux, status, meta = self.calibrator.process_bh1750(540.5)
        assert lux == 540.5
        assert status == CalibrationStatus.CALIBRATED

        # Impossible lux
        lux_bad, status_bad, _ = self.calibrator.process_bh1750(-10.0)
        assert lux_bad is None
        assert status_bad == CalibrationStatus.FAILED


# =====================================================================
# 2. HARDWARE PAYLOAD PROCESSOR & SCHEMA CONTRACT TESTS
# =====================================================================

class TestHardwarePayloadProcessing:
    def setup_method(self):
        self.processor = HardwarePayloadProcessor()

    def test_process_raw_hardware_telemetry(self):
        raw_msg = {
            "node_id": "NODE-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_gps_lat": 17.3850,
            "raw_gps_lon": 78.4867,
            "gps_fix": True,
            "raw_dht_temp": 31.4,
            "raw_dht_hum": 68.5,
            "raw_bmp_press": 1008.2,
            "raw_bmp_temp": 31.9,
            "raw_raindrop_adc": 1600,
            "raw_soil_adc": 2200,
            "raw_dust_volts": 0.85,
            "raw_bh1750_lux": 650.0,
            "battery_pct": 85.0,
        }
        normalized = self.processor.process_raw_hardware_packet(raw_msg)

        assert normalized["node_id"] == "NODE-001"
        assert normalized["location"]["lat"] == 17.3850
        assert normalized["location"]["lon"] == 78.4867
        meas = normalized["measurements"]
        assert meas["temperature"] == 31.4
        assert meas["humidity"] == 68.5
        assert meas["pressure"] == 1008.2
        assert meas["rainfall"] > 0.0
        assert meas["soil_moisture"] is not None
        assert meas["air_quality"] is not None
        assert meas["light_intensity"] == 650.0
        assert meas["water_level"] is None  # ABSOLUTE RULE: water_level is NULL
        assert meas["battery"] == 85.0

        # Check sensor status metadata
        status_map = meas["sensor_status"]
        assert status_map["water_level"] == "UNAVAILABLE"
        assert status_map["rainfall"] == "UNVERIFIED"
        assert status_map["soil_moisture"] == "UNVERIFIED"
        assert status_map["dht11"] == "UNVERIFIED"

    def test_telemetry_contract_model_validation(self):
        # Validate that the normalized output conforms to NormalizedTelemetry
        raw_msg = {
            "node_id": "NODE-002",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_gps_lat": 17.4000,
            "raw_gps_lon": 78.5000,
            "gps_fix": True,
            "raw_dht_temp": 29.0,
            "raw_dht_hum": 75.0,
            "raw_bmp_press": 1005.0,
            "raw_bh1750_lux": 120.0,
        }
        normalized_dict = self.processor.process_raw_hardware_packet(raw_msg)
        
        telemetry = NormalizedTelemetry(**normalized_dict)
        assert telemetry.node_id == "NODE-002"
        assert telemetry.measurements.water_level is None
        assert telemetry.measurements.light_intensity == 120.0


# =====================================================================
# 3. LORA GATEWAY BRIDGE TESTS
# =====================================================================

class TestLoRaGatewayBridge:
    def setup_method(self):
        self.bridge = LoRaGatewayBridge(client_id="GW-TEST-01")

    def test_binary_lora_packet_decoding(self):
        # Pack a 28-byte binary packet
        # Format: !2s8sHiiHhHHHHHBB
        # node_id: "NODE-001" (padded to 8 bytes)
        node_bytes = b"NODE-001"
        seq = 101
        lat_int = int(17.3850 * 1e6)
        lon_int = int(78.4867 * 1e6)
        temp_dht = int(28.5 * 10)
        hum_dht = int(70.0 * 10)
        press_hpa = int((1012.3 - 800.0) * 10)
        rain_adc = 4000
        soil_adc = 2000
        dust_mv = 700
        lux_i = 450
        batt = 85
        flags = 0x01  # GPS fix

        packet_bytes = struct.pack(
            LORA_PACKET_STRUCT.format,
            LORA_MAGIC,
            node_bytes,
            seq,
            lat_int,
            lon_int,
            temp_dht,
            hum_dht,
            press_hpa,
            rain_adc,
            soil_adc,
            dust_mv,
            lux_i,
            batt,
            flags,
        )

        assert len(packet_bytes) == 36

        decoded = self.bridge.decode_lora_packet(packet_bytes)
        assert decoded is not None
        assert decoded["node_id"] == "NODE-001"
        assert abs(decoded["location"]["lat"] - 17.3850) < 1e-4
        assert abs(decoded["measurements"]["temperature"] - 28.5) < 0.1
        assert decoded["measurements"]["water_level"] is None

    def test_binary_lora_corrupted_magic_rejected(self):
        corrupted_bytes = b"XX" + b"A" * 34
        decoded = self.bridge.decode_lora_packet(corrupted_bytes)
        assert decoded is None

    def test_json_lora_payload_decoding(self):
        json_payload = (
            b'{"node_id":"NODE-003","seq":42,"raw_gps_lat":17.39,"raw_gps_lon":78.49,"gps_fix":true,'
            b'"raw_dht_temp":30.2,"raw_dht_hum":65.0,"raw_bmp_press":1009.5,"raw_bh1750_lux":800.0,'
            b'"raw_raindrop_adc":3800,"raw_soil_adc":2100}'
        )
        decoded = self.bridge.decode_lora_packet(json_payload)
        assert decoded is not None
        assert decoded["node_id"] == "NODE-003"
        assert decoded["location"]["lat"] == 17.39
        assert decoded["measurements"]["water_level"] is None


# =====================================================================
# 4. CRITICAL: WATER LEVEL ABSENCE IN FLOOD MODEL
# =====================================================================

class TestFloodModelWaterLevelAbsence:
    def setup_method(self):
        self.flood_model = FloodModel()

    def test_live_telemetry_missing_water_level_returns_unavailable(self):
        """
        ABSOLUTE RULE 2 & 6:
        When real hardware reports water_level = None (missing), the flood model
        must return HazardStatus.UNAVAILABLE, rather than inventing 0.0 or
        fabricating an alert.
        """
        from intelligence.core.contracts.telemetry import LocationCoordinate

        features_live = HazardFeatures(
            node_id="NODE-001",
            timestamp=datetime.now(timezone.utc),
            location=LocationCoordinate(lat=17.3850, lon=78.4867),
            source="hardware_node",
            valid=True,
            confidence_base=0.9,
            anomaly_score=0.0,
            flags=[],
            rainfall_mmhr=45.0,  # heavy rain
            soil_moisture_pct=85.0,
            water_level_m=None,  # PHYSICAL HARDWARE LACKS WATER SENSOR
        )
        verdict = QualityGateVerdict(is_admissible=True, confidence=1.0)
        result = self.flood_model.evaluate(features_live, verdict)
        assert result.status == HazardStatus.UNAVAILABLE
        assert "Missing" in (result.reason or "")
        assert result.severity == 0.0
        assert result.confidence == 0.0

    def test_simulated_scenario_with_water_level_evaluates(self):
        """
        Simulated demo scenarios with synthetic water level evaluate correctly,
        maintaining strict epistemic separation.
        """
        from intelligence.core.contracts.telemetry import LocationCoordinate

        features_sim = HazardFeatures(
            node_id="NODE-001",
            timestamp=datetime.now(timezone.utc),
            location=LocationCoordinate(lat=17.3850, lon=78.4867),
            source="simulation",
            valid=True,
            confidence_base=0.9,
            anomaly_score=0.0,
            flags=["SIMULATED"],
            rainfall_mmhr=45.0,
            soil_moisture_pct=85.0,
            water_level_m=3.2,  # Simulated/synthetic measurement
        )
        verdict = QualityGateVerdict(is_admissible=True, confidence=1.0)
        result = self.flood_model.evaluate(features_sim, verdict)
        assert result.status != HazardStatus.UNAVAILABLE
        assert result.severity > 0.4


# =====================================================================
# 5. MULTI-NODE READINESS & DEDUPLICATION
# =====================================================================

class TestMultiNodeReadiness:
    def test_multi_node_payload_separation(self):
        processor = HardwarePayloadProcessor()
        node1_payload = {
            "node_id": "NODE-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_gps_lat": 17.3850,
            "raw_gps_lon": 78.4867,
            "gps_fix": True,
            "raw_dht_temp": 32.0,
            "raw_dht_hum": 70.0,
        }
        node2_payload = {
            "node_id": "NODE-002",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_gps_lat": 12.9716,
            "raw_gps_lon": 77.5946,
            "gps_fix": True,
            "raw_dht_temp": 24.0,
            "raw_dht_hum": 80.0,
        }

        norm1 = processor.process_raw_hardware_packet(node1_payload)
        norm2 = processor.process_raw_hardware_packet(node2_payload)

        assert norm1["node_id"] == "NODE-001"
        assert norm2["node_id"] == "NODE-002"
        assert norm1["location"]["lat"] != norm2["location"]["lat"]
        assert norm1["measurements"]["temperature"] != norm2["measurements"]["temperature"]
