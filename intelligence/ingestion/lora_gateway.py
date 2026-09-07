"""
Climate Eye View S2 — LoRa RA-02 Gateway Bridge.

Represents the physical and logical gateway bridging the 433 MHz LoRa radio link
(SX1278 transceiver on the sensor node) to the IP MQTT network.

Architecture:
  [ESP32 + Sensors]
         ↓ (SPI)
  [LoRa RA-02 Transmitter (433 MHz)]
         ↓ (RF Air Interface)
  [LoRa RA-02 Receiver (433 MHz)]
         ↓ (SPI / UART)
  [Gateway ESP32 / Host Microservice]
         ↓ (Wi-Fi / Ethernet / TCP)
  [Eclipse Mosquitto MQTT Broker (Port 1883)]
         ↓ (MQTT Topic: climate/nodes/{node_id}/telemetry)
  [Climate Eye S2 Ingestion Pipeline]

This gateway bridge decodes both binary and JSON LoRa radio packets, applies hardware
calibrations, and publishes canonical payloads onto the MQTT broker.
"""

from datetime import datetime, timezone
import json
import logging
import struct
from typing import Any, Callable, Dict, Optional, Tuple

import paho.mqtt.client as mqtt

from intelligence.app.config import settings
from intelligence.calibration.hardware import HardwarePayloadProcessor
from intelligence.core.logging import get_logger

logger = get_logger("lora_gateway")

# Binary LoRa Packet Format (28 bytes):
# Magic (2B: 'CE') | NodeID (8B ASCII) | Seq (uint16) | Lat (int32 / 1e6) | Lon (int32 / 1e6)
# Temp (int16 / 10) | Hum (uint16 / 10) | Press (uint16 / 10 + 800) | RainADC (uint16)
# SoilADC (uint16) | DustMV (uint16) | Lux (uint16) | Battery (uint8) | StatusFlags (uint8)
LORA_PACKET_STRUCT = struct.Struct("!2s8sHiiHhHHHHHBB")
LORA_MAGIC = b"CE"


class LoRaGatewayBridge:
    """
    Decodes LoRa RA-02 radio packets and bridges them to the local/remote MQTT broker.
    """

    def __init__(
        self,
        broker_host: Optional[str] = None,
        broker_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: str = "lora-gateway-bridge-01",
    ) -> None:
        self.broker_host = broker_host or settings.mqtt_broker_host
        self.broker_port = broker_port or settings.mqtt_broker_port
        self.username = username or settings.mqtt_username
        self.password = password or settings.mqtt_password
        self.client_id = client_id
        self._mqtt_client: Optional[mqtt.Client] = None
        self._is_connected = False

    def connect(self) -> bool:
        """Initializes MQTT connection for the gateway bridge."""
        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
                clean_session=True,
            )
        except AttributeError:
            client = mqtt.Client(client_id=self.client_id, clean_session=True)

        if self.username:
            client.username_pw_set(self.username, self.password)

        try:
            client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            client.loop_start()
            self._mqtt_client = client
            self._is_connected = True
            logger.info(f"LoRa Gateway Bridge connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            return True
        except Exception as exc:
            logger.warning(f"LoRa Gateway Bridge failed to connect to MQTT broker: {exc}")
            return False

    def disconnect(self) -> None:
        """Cleanly disconnects the gateway bridge."""
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._is_connected = False
            logger.info("LoRa Gateway Bridge disconnected from MQTT broker.")

    @staticmethod
    def decode_lora_packet(packet_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Decodes raw RF payload received from RA-02 transceiver.
        Supports both binary packed format (28 bytes) and UTF-8 JSON text.
        """
        if not packet_bytes:
            return None

        # 1. Check if UTF-8 JSON text
        try:
            text = packet_bytes.decode("utf-8").strip()
            if text.startswith("{") and text.endswith("}"):
                data = json.loads(text)
                if isinstance(data, dict):
                    return HardwarePayloadProcessor.process_raw_hardware_packet(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

        # 2. Decode Binary Struct if matches size
        if len(packet_bytes) >= LORA_PACKET_STRUCT.size:
            try:
                (
                    magic,
                    node_raw,
                    seq,
                    lat_i,
                    lon_i,
                    temp_i,
                    hum_i,
                    press_i,
                    rain_adc,
                    soil_adc,
                    dust_mv,
                    lux_i,
                    battery,
                    flags,
                ) = LORA_PACKET_STRUCT.unpack_from(packet_bytes)

                if magic != LORA_MAGIC:
                    logger.warning(f"Invalid LoRa packet magic bytes: {magic}")
                    return None

                node_id = node_raw.decode("ascii", errors="ignore").rstrip("\x00").strip()
                if not node_id:
                    node_id = "NODE-001"

                raw_dict = {
                    "node_id": node_id,
                    "sequence": seq,
                    "raw_gps_lat": lat_i / 1e6 if lat_i != 0 else None,
                    "raw_gps_lon": lon_i / 1e6 if lon_i != 0 else None,
                    "gps_fix": bool(flags & 0x01),
                    "raw_dht_temp": temp_i / 10.0,
                    "raw_dht_hum": hum_i / 10.0,
                    "raw_bmp_press": (press_i / 10.0) + 800.0 if press_i > 0 else None,
                    "raw_raindrop_adc": rain_adc,
                    "raw_soil_adc": soil_adc,
                    "raw_dust_volts": dust_mv / 1000.0,
                    "raw_bh1750_lux": float(lux_i),
                    "battery_pct": float(battery),
                    "water_level": None,  # Explicitly absent
                }
                return HardwarePayloadProcessor.process_raw_hardware_packet(raw_dict)
            except Exception as exc:
                logger.warning(f"Failed to unpack binary LoRa struct: {exc}")
                return None

        logger.warning(f"Unrecognized LoRa packet format (len={len(packet_bytes)})")
        return None

    def publish_lora_telemetry(
        self,
        packet_bytes: bytes,
        rssi_dbm: float = -75.0,
        snr_db: float = 8.5,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Ingests a LoRa packet from the radio receiver, calibrates it,
        attaches radio link metrics (RSSI, SNR), and publishes to MQTT.
        """
        payload = self.decode_lora_packet(packet_bytes)
        if not payload:
            return False, None, "Failed to decode LoRa packet"

        node_id = payload.get("node_id", "NODE-001")
        # Attach radio link metadata to quality block
        if "quality" in payload and isinstance(payload["quality"], dict):
            payload["quality"]["lora_rssi_dbm"] = round(rssi_dbm, 1)
            payload["quality"]["lora_snr_db"] = round(snr_db, 1)

        topic = f"climate/nodes/{node_id}/telemetry"

        if self._mqtt_client and self._is_connected:
            try:
                payload_str = json.dumps(payload)
                self._mqtt_client.publish(topic, payload_str, qos=1)
                logger.info(f"Bridged LoRa packet from node '{node_id}' to MQTT topic '{topic}' (RSSI: {rssi_dbm} dBm)")
                return True, payload, f"Bridged to {topic}"
            except Exception as exc:
                logger.error(f"Failed to publish to MQTT topic {topic}: {exc}")
                return False, payload, f"MQTT publish failed: {exc}"

        return True, payload, "Decoded successfully (MQTT client offline)"
