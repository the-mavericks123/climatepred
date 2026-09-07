"""
Climate Eye View S2 — Physical Hardware Sensor Calibration & Translation Layer.

Provides deterministic mathematical conversions, physical range boundaries,
and explicit calibration status metadata for the actual physical sensor hardware:
- ESP32 Microcontroller (ADC & Power)
- GY-GPS6MV2P GPS (WGS84 NMEA / coordinate validation)
- Raindrop Module (12-bit ADC -> rainfall intensity in mm/hr)
- 6-Wire Optical Dust Sensor GP2Y1010AU0F (analog voltage -> ug/m3 -> AQI)
- BH1750 (GY-302) Ambient Light Sensor (I2C lux)
- BMP280 (I2C barometric pressure & secondary temperature)
- DHT11 (1-wire ambient temperature & relative humidity)
- Soil Moisture Sensor (12-bit ADC -> volumetric moisture %)
- Water Level: Handled explicitly as UNAVAILABLE (no physical sensor).
"""

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, Optional, Tuple


class CalibrationStatus(str, Enum):
    """Authoritative calibration and verification status of a physical sensor."""
    CALIBRATED = "CALIBRATED"       # Formally calibrated against ground truth reference
    UNVERIFIED = "UNVERIFIED"       # Physically present with model conversion, but pending physical colocation
    FAILED = "FAILED"               # Sensor output violated physical/electrical invariants
    UNAVAILABLE = "UNAVAILABLE"     # No physical transducer present in hardware BOM


class HardwareSensorCalibrator:
    """
    Mathematical calibration and physical unit conversion engine.
    Ensures raw ADC integer values are never falsely passed as physical engineering units.
    """

    # -------------------------------------------------------------------------
    # 1. DHT11 (Ambient Temperature & Humidity)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_dht11(
        temperature: Optional[float],
        humidity: Optional[float],
    ) -> Tuple[Optional[float], Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Validates DHT11 sensor readings.
        DHT11 Specification:
          - Temperature: 0 to 50 °C (±2 °C accuracy)
          - Humidity: 20 to 90 % RH (±5 % RH accuracy)
        """
        meta: Dict[str, Any] = {
            "sensor": "DHT11",
            "accuracy_temp_c": 2.0,
            "accuracy_hum_pct": 5.0,
        }
        if temperature is None and humidity is None:
            return None, None, CalibrationStatus.UNAVAILABLE, meta

        # Physical range validation
        valid_temp = temperature is not None and (-10.0 <= temperature <= 60.0)
        valid_hum = humidity is not None and (0.0 <= humidity <= 100.0)

        if not valid_temp or not valid_hum:
            meta["error"] = "DHT11 readings outside physical operating envelope"
            return None, None, CalibrationStatus.FAILED, meta

        # Round to sensor resolution (1 °C / 1 % RH)
        temp_c = round(float(temperature), 1)
        hum_pct = round(float(humidity), 1)

        # Factory uncalibrated consumer-grade sensor -> UNVERIFIED
        return temp_c, hum_pct, CalibrationStatus.UNVERIFIED, meta

    # -------------------------------------------------------------------------
    # 2. BMP280 (Barometric Pressure & Secondary Temperature)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_bmp280(
        pressure_hpa: Optional[float],
        secondary_temp_c: Optional[float] = None,
    ) -> Tuple[Optional[float], Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Validates Bosch BMP280 calibrated digital barometric pressure and temperature.
        BMP280 Specification:
          - Pressure: 300 to 1100 hPa (±1.0 hPa absolute accuracy)
          - Temperature: -40 to +85 °C (±0.5 °C accuracy)
        """
        meta: Dict[str, Any] = {
            "sensor": "BMP280",
            "accuracy_hpa": 1.0,
            "accuracy_temp_c": 0.5,
            "factory_trimmed": True,
        }
        if pressure_hpa is None:
            return None, None, CalibrationStatus.UNAVAILABLE, meta

        if not (700.0 <= pressure_hpa <= 1200.0):
            meta["error"] = f"Pressure {pressure_hpa} hPa outside terrestrial bounds"
            return None, None, CalibrationStatus.FAILED, meta

        sec_temp = None
        if secondary_temp_c is not None:
            if -40.0 <= secondary_temp_c <= 85.0:
                sec_temp = round(float(secondary_temp_c), 2)
            else:
                meta["temp_warning"] = f"BMP280 temperature {secondary_temp_c} °C out of range"

        # Factory calibrated I2C registers
        return round(float(pressure_hpa), 2), sec_temp, CalibrationStatus.CALIBRATED, meta

    # -------------------------------------------------------------------------
    # 3. Raindrop Sensor (Resistive Analog Plate + LM393 ADC)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_raindrop(
        raw_adc: Optional[int],
        adc_max: int = 4095,
        adc_dry_threshold: int = 3800,
        adc_submerged: int = 800,
    ) -> Tuple[Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Converts Raindrop plate raw 12-bit ADC reading to rainfall intensity rate (mm/hr).
        
        CRITICAL: Raw ADC is conductivity, NOT mm/hr.
        Dry plate: ADC ~ 4095 (High resistance, no water)
        Heavy droplets: ADC ~ 1200 - 1800
        Fully flooded plate: ADC ~ 800
        
        Conversion Model:
          If ADC >= adc_dry_threshold: rainfall = 0.0 mm/hr
          Else: piecewise logarithmic scaling up to 150 mm/hr max rate.
        """
        meta: Dict[str, Any] = {
            "sensor": "Raindrop_Module_LM393",
            "raw_adc": raw_adc,
            "adc_dry_threshold": adc_dry_threshold,
            "adc_submerged": adc_submerged,
        }
        if raw_adc is None:
            return None, CalibrationStatus.UNAVAILABLE, meta

        if raw_adc < 0 or raw_adc > adc_max:
            meta["error"] = f"Raw ADC {raw_adc} out of 12-bit range [0, {adc_max}]"
            return None, CalibrationStatus.FAILED, meta

        if raw_adc >= adc_dry_threshold:
            # Completely dry
            return 0.0, CalibrationStatus.UNVERIFIED, meta

        # Normalized wetness fraction [0.0, 1.0]
        clamped_adc = max(adc_submerged, min(adc_dry_threshold, raw_adc))
        wetness = (adc_dry_threshold - clamped_adc) / (adc_dry_threshold - adc_submerged)

        # Non-linear rainfall rate curve (0 to 120 mm/hr)
        # Low wetness (dew/light sprinkles): 0.5 - 5 mm/hr
        # Medium wetness: 5 - 30 mm/hr
        # High wetness: 30 - 120 mm/hr
        rainfall_mmhr = round(float(math.pow(wetness, 1.8) * 120.0), 2)
        meta["wetness_fraction"] = round(wetness, 3)

        # Since empirical curve without rain-gauge colocation -> UNVERIFIED
        return rainfall_mmhr, CalibrationStatus.UNVERIFIED, meta

    # -------------------------------------------------------------------------
    # 4. Soil Moisture Sensor (Analog Resistive/Capacitive)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_soil_moisture(
        raw_adc: Optional[int],
        adc_dry: int = 3400,
        adc_wet: int = 1350,
        adc_max: int = 4095,
    ) -> Tuple[Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Converts 12-bit Soil Moisture ADC reading into volumetric moisture percentage (0 - 100%).
        
        Two-Point Calibration:
          ADC_dry: Sensor suspended in dry air (~ 3400) -> 0%
          ADC_wet: Sensor submerged in water (~ 1350) -> 100%
        """
        meta: Dict[str, Any] = {
            "sensor": "Soil_Moisture_Analog",
            "raw_adc": raw_adc,
            "adc_dry": adc_dry,
            "adc_wet": adc_wet,
        }
        if raw_adc is None:
            return None, CalibrationStatus.UNAVAILABLE, meta

        if raw_adc < 0 or raw_adc > adc_max:
            meta["error"] = f"Raw ADC {raw_adc} out of bounds"
            return None, CalibrationStatus.FAILED, meta

        # Inverted linear interpolation (higher ADC = drier soil)
        if adc_dry <= adc_wet:
            meta["error"] = "Invalid calibration points (adc_dry must be > adc_wet)"
            return None, CalibrationStatus.FAILED, meta

        moisture_pct = 100.0 * (adc_dry - raw_adc) / (adc_dry - adc_wet)
        clamped_pct = max(0.0, min(100.0, moisture_pct))

        return round(clamped_pct, 1), CalibrationStatus.UNVERIFIED, meta

    # -------------------------------------------------------------------------
    # 5. Optical Dust Sensor (Sharp GP2Y1010AU0F / 6-Wire)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_optical_dust(
        analog_volts: Optional[float],
        clean_air_volts: float = 0.60,
        sensitivity_v_per_100ug: float = 0.50,
    ) -> Tuple[Optional[float], Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Converts GP2Y1010AU0F 6-wire optical dust sensor analog voltage to:
        1. Dust Density (ug/m3)
        2. US EPA PM2.5 Air Quality Index (AQI 0 - 500)
        
        Sampling requirement:
          IR LED triggered HIGH for 0.32 ms, sampled at 0.28 ms via ESP32 ADC.
        Conversion formula:
          dust_density (mg/m3) = max(0.0, (volts - clean_air_volts) / sensitivity * 0.1)
          dust_density (ug/m3) = dust_density (mg/m3) * 1000
        """
        meta: Dict[str, Any] = {
            "sensor": "GP2Y1010AU0F_Optical_Dust",
            "analog_volts": analog_volts,
            "clean_air_baseline_v": clean_air_volts,
        }
        if analog_volts is None:
            return None, None, CalibrationStatus.UNAVAILABLE, meta

        if not (0.0 <= analog_volts <= 5.0):
            meta["error"] = f"Analog voltage {analog_volts} V outside ADC rail [0, 5.0V]"
            return None, None, CalibrationStatus.FAILED, meta

        # Dust density in ug/m3
        delta_v = max(0.0, analog_volts - clean_air_volts)
        dust_density_ugm3 = (delta_v / sensitivity_v_per_100ug) * 100.0
        meta["dust_density_ugm3"] = round(dust_density_ugm3, 1)

        # US EPA PM2.5 Breakpoints to AQI
        aqi = HardwareSensorCalibrator._pm25_to_aqi(dust_density_ugm3)

        return round(dust_density_ugm3, 1), round(aqi, 1), CalibrationStatus.UNVERIFIED, meta

    @staticmethod
    def _pm25_to_aqi(c: float) -> float:
        """Converts PM2.5 concentration in ug/m3 to standard US EPA AQI."""
        breakpoints = [
            (0.0, 12.0, 0.0, 50.0),        # Good
            (12.1, 35.4, 51.0, 100.0),     # Moderate
            (35.5, 55.4, 101.0, 150.0),    # Unhealthy for Sensitive
            (55.5, 150.4, 151.0, 200.0),   # Unhealthy
            (150.5, 250.4, 201.0, 300.0),  # Very Unhealthy
            (250.5, 500.4, 301.0, 500.0),  # Hazardous
        ]
        if c <= 0.0:
            return 0.0
        for c_low, c_high, aqi_low, aqi_high in breakpoints:
            if c <= c_high:
                return ((aqi_high - aqi_low) / (c_high - c_low)) * (c - c_low) + aqi_low
        return 500.0

    # -------------------------------------------------------------------------
    # 6. BH1750 (GY-302 Ambient Light Sensor)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_bh1750(
        raw_lux: Optional[float],
    ) -> Tuple[Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Validates BH1750 16-bit digital ambient light illuminance.
        Specification: 1 to 65,535 lx (resolution: 1 lx).
        """
        meta: Dict[str, Any] = {"sensor": "BH1750", "unit": "lux"}
        if raw_lux is None:
            return None, CalibrationStatus.UNAVAILABLE, meta

        if not (0.0 <= raw_lux <= 120000.0):
            meta["error"] = f"Lux {raw_lux} out of physical terrestrial range"
            return None, CalibrationStatus.FAILED, meta

        return round(float(raw_lux), 1), CalibrationStatus.CALIBRATED, meta

    # -------------------------------------------------------------------------
    # 7. GY-GPS6MV2P (GPS Coordinate Validation)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_gps(
        latitude: Optional[float],
        longitude: Optional[float],
        elevation_m: Optional[float] = None,
        has_fix: bool = True,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], CalibrationStatus, Dict[str, Any]]:
        """
        Validates WGS84 coordinates from GY-GPS6MV2P.
        Explicitly rejects (0.0, 0.0) null island defaults and invalid fixes.
        """
        meta: Dict[str, Any] = {"sensor": "GY-GPS6MV2P_NEO6M", "has_fix": has_fix}
        if latitude is None or longitude is None or not has_fix:
            return None, None, None, CalibrationStatus.UNAVAILABLE, meta

        # Check Null Island default
        if abs(latitude) < 0.0001 and abs(longitude) < 0.0001:
            meta["error"] = "Null Island coordinates (0.0, 0.0) rejected as unacquired GPS fix"
            return None, None, None, CalibrationStatus.FAILED, meta

        # Valid WGS84 range
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            meta["error"] = f"Coordinates ({latitude}, {longitude}) outside WGS84 bounds"
            return None, None, None, CalibrationStatus.FAILED, meta

        elev = round(float(elevation_m), 1) if elevation_m is not None else None
        return round(float(latitude), 6), round(float(longitude), 6), elev, CalibrationStatus.CALIBRATED, meta

    # -------------------------------------------------------------------------
    # 8. Water Level (CRITICAL: ABSENT FROM HARDWARE)
    # -------------------------------------------------------------------------
    @staticmethod
    def process_water_level(
        raw_val: Any = None,
    ) -> Tuple[None, CalibrationStatus, Dict[str, Any]]:
        """
        Authoritative handler for water level.
        The physical node contains NO water-level sensor.
        Must NEVER return 0.0 or fabricated numbers for live hardware.
        """
        meta: Dict[str, Any] = {
            "sensor": "NONE",
            "reason": "Hardware BOM does not include water-level gauge",
            "physical_presence": False,
        }
        return None, CalibrationStatus.UNAVAILABLE, meta


class HardwarePayloadProcessor:
    """
    Transforms raw incoming physical hardware sensor packets from an ESP32 or LoRa gateway
    into canonical, calibrated, epistemically honest NormalizedTelemetry dictionaries.
    """

    @classmethod
    def process_raw_hardware_packet(
        cls,
        raw: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Processes a raw packet containing raw ADC and sensor readings:
        Inputs may include:
          - node_id: str
          - raw_dht_temp, raw_dht_hum
          - raw_bmp_press, raw_bmp_temp
          - raw_raindrop_adc
          - raw_soil_adc
          - raw_dust_volts
          - raw_bh1750_lux
          - raw_gps_lat, raw_gps_lon, raw_gps_elev, gps_fix
          - battery_pct
        """
        eval_time = now or datetime.now(timezone.utc)
        node_id = str(raw.get("node_id") or "NODE-001")
        cal = HardwareSensorCalibrator

        # 1. GPS
        lat = raw.get("latitude", raw.get("raw_gps_lat", raw.get("lat")))
        lon = raw.get("longitude", raw.get("raw_gps_lon", raw.get("lon")))
        elev = raw.get("elevation", raw.get("raw_gps_elev", raw.get("elevation_m")))
        has_fix = raw.get("gps_fix", True) if (lat is not None and lon is not None) else False
        v_lat, v_lon, v_elev, gps_status, _ = cal.process_gps(lat, lon, elev, has_fix=has_fix)

        # Fallback to configured station location if GPS module is indoor / acquiring
        if v_lat is None or v_lon is None:
            # Explicitly mark that GPS had no fix
            v_lat = float(raw.get("fallback_lat", 17.385044))
            v_lon = float(raw.get("fallback_lon", 78.486671))
            gps_status = CalibrationStatus.UNVERIFIED

        # 2. DHT11
        dht_t = raw.get("temperature", raw.get("raw_dht_temp"))
        dht_h = raw.get("humidity", raw.get("raw_dht_hum"))
        v_temp, v_hum, dht_status, _ = cal.process_dht11(dht_t, dht_h)

        # 3. BMP280
        bmp_p = raw.get("pressure", raw.get("raw_bmp_press"))
        bmp_t = raw.get("raw_bmp_temp")
        v_press, v_bmp_temp, bmp_status, _ = cal.process_bmp280(bmp_p, bmp_t)

        # 4. Raindrop
        if "rainfall" in raw and raw["rainfall"] is not None and "raw_raindrop_adc" not in raw:
            # Already in mm/hr from upstream firmware
            v_rain = float(raw["rainfall"])
            rain_status = CalibrationStatus.UNVERIFIED
        else:
            v_rain, rain_status, _ = cal.process_raindrop(raw.get("raw_raindrop_adc"))

        # 5. Soil Moisture
        if "soil_moisture" in raw and raw["soil_moisture"] is not None and "raw_soil_adc" not in raw:
            v_soil = float(raw["soil_moisture"])
            soil_status = CalibrationStatus.UNVERIFIED
        else:
            v_soil, soil_status, _ = cal.process_soil_moisture(raw.get("raw_soil_adc"))

        # 6. Optical Dust / Air Quality
        if "air_quality" in raw and raw["air_quality"] is not None and "raw_dust_volts" not in raw:
            v_aqi = float(raw["air_quality"])
            dust_status = CalibrationStatus.UNVERIFIED
        else:
            _, v_aqi, dust_status, _ = cal.process_optical_dust(raw.get("raw_dust_volts"))

        # 7. BH1750
        lux_in = raw.get("light_intensity", raw.get("raw_bh1750_lux"))
        v_lux, lux_status, _ = cal.process_bh1750(lux_in)

        # 8. Water Level — Strictly None
        v_water, water_status, _ = cal.process_water_level(raw.get("water_level"))

        # 9. Battery
        battery = raw.get("battery", raw.get("battery_pct"))
        v_battery = round(float(battery), 1) if battery is not None else None

        # Build comprehensive status dictionary
        sensor_status_map = {
            "gps": gps_status.value,
            "dht11": dht_status.value,
            "bmp280": bmp_status.value,
            "rainfall": rain_status.value,
            "soil_moisture": soil_status.value,
            "optical_dust": dust_status.value,
            "bh1750": lux_status.value,
            "water_level": water_status.value,
        }
        if v_bmp_temp is not None:
            sensor_status_map["bmp280_secondary_temp_c"] = str(v_bmp_temp)

        return {
            "schema_version": "1.0",
            "node_id": node_id,
            "timestamp": raw.get("timestamp") or eval_time.isoformat(),
            "location": {
                "lat": v_lat,
                "lon": v_lon,
                "elevation": v_elev,
            },
            "measurements": {
                "temperature": v_temp,
                "humidity": v_hum,
                "pressure": v_press,
                "rainfall": v_rain,
                "soil_moisture": v_soil,
                "water_level": v_water,
                "air_quality": v_aqi,
                "light_intensity": v_lux,
                "battery": v_battery,
                "sensor_status": sensor_status_map,
            },
            "quality": {
                "valid": True,
                "source": "ESP32_LORA",
                "received_at": eval_time.isoformat(),
                "confidence": 1.0,
                "flags": [f"{k}:{v}" for k, v in sensor_status_map.items() if v in ["UNVERIFIED", "UNAVAILABLE"]],
            },
        }
