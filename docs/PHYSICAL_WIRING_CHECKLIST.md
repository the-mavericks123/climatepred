# Climate Eye View — Physical Wiring Checklist & Pinout Mapping

**Document Version:** 1.0.0  
**Phase:** Physical Demo Readiness  
**Target Hardware:** ESP32 DevKit V1 (30-pin / 36-pin WROOM-32)  

---

## 1. Authoritative GPIO & Bus Pinout Table

> [!CAUTION]
> **Brownout & Voltage Warning:**
> 1. The **LoRa RA-02 (SX1278)** module must **NEVER** be powered by 5.0V. Connecting 5.0V to VCC will destroy the RF transceiver. Connect exclusively to regulated **3.3V**.
> 2. The **GP2Y1010AU0F Dust Sensor** requires **5.0V** for its internal infrared LED driver, but its analog output $V_o$ must not exceed 3.3V into the ESP32 ADC pin.
> 3. Verify the **LM2596 output voltage with a digital multimeter** to ensure it outputs exactly 5.0V DC before plugging into the breadboard rails!

| ESP32 Pin | Function / Mode | Connected Device | Signal Name | Operating Voltage | Notes / Pullups |
|:---|:---|:---|:---|:---:|:---|
| **3.3V** | Power Out | BMP280, BH1750, DHT11, LoRa RA-02, Soil, GPS | VCC / 3V3 | 3.3V DC | Total current must not exceed 500mA |
| **GND** | Ground Rail | ALL PERIPHERALS | Common GND | 0V | **Common ground mandatory across all boards** |
| **VIN / 5V** | Power In / Out | LM2596 VOUT (+5V) / Dust Sensor Pin 6 | +5V Rail | 5.0V DC | Powers internal ESP32 AMS1117 LDO |
| **GPIO 4** | Digital Input | DHT11 Sensor | DATA | 3.3V | External 10kΩ pull-up resistor to 3.3V |
| **GPIO 14** | Digital Output | GP2Y1010 Dust Sensor | ILED (Pin 3) | 3.3V / 5.0V | Drives external PNP/NPN transistor pulse |
| **GPIO 16** | UART2 RX | GY-GPS6MV2P (NEO-6M) | TXD | 3.3V | Receives NMEA stream at 9600 baud |
| **GPIO 17** | UART2 TX | GY-GPS6MV2P (NEO-6M) | RXD | 3.3V | Transmits configuration commands |
| **GPIO 18** | VSPI SCK | LoRa RA-02 (SX1278) | SCK | 3.3V | Hardware SPI Clock |
| **GPIO 19** | VSPI MISO | LoRa RA-02 (SX1278) | MISO | 3.3V | Hardware SPI Master In |
| **GPIO 21** | I2C SDA | BMP280 & BH1750 (GY-302)| SDA | 3.3V | Shared I2C Bus (Addresses: 0x76 & 0x23) |
| **GPIO 22** | I2C SCL | BMP280 & BH1750 (GY-302)| SCL | 3.3V | Shared I2C Bus Clock |
| **GPIO 23** | VSPI MOSI | LoRa RA-02 (SX1278) | MOSI | 3.3V | Hardware SPI Master Out |
| **GPIO 5** | Digital Output | LoRa RA-02 (SX1278) | NSS (CS) | 3.3V | SPI Chip Select |
| **GPIO 2** | Digital Input | LoRa RA-02 (SX1278) | DIO0 | 3.3V | Packet RX Done Interrupt |
| **GPIO 32** | ADC1_CH4 | Raindrop Module (LM393) | AO (Analog Out) | 3.3V | ADC1 channel (works with Wi-Fi/BT) |
| **GPIO 33** | ADC1_CH5 | Soil Moisture Probe | AO (Analog Out) | 3.3V | ADC1 channel (works with Wi-Fi/BT) |
| **GPIO 34** | ADC1_CH6 | GP2Y1010 Dust Sensor | Vo (Pin 5) | 3.3V | Analog Input Only (no internal pullups) |

---

## 2. Bus Conflict & Safety Audit Verdict

- **SPI Bus:** GPIO 18 (SCK), 19 (MISO), 23 (MOSI), 5 (NSS) dedicated to LoRa RA-02. **No conflicts.**
- **I2C Bus:** GPIO 21 (SDA) and 22 (SCL) shared cleanly by BMP280 (`0x76`) and BH1750 (`0x23`). **Addresses do not collide.**
- **UART Bus:** GPIO 16 (RX2) and 17 (TX2) dedicated to GPS NEO-6M. Leaves default UART0 (GPIO 1 & 3) free for USB serial flashing and debugging. **No conflicts.**
- **ADC Channels:** All analog sensors (Raindrop: GPIO 32, Soil: GPIO 33, Dust: GPIO 34) mapped exclusively to **ADC1**. Avoids ESP32 ADC2 limitations that break when Wi-Fi is active. **No ADC conflicts.**
- **Power Safety:** LM2596 outputs 5.0V into VIN; ESP32 onboard LDO supplies 3.3V bus. **Safe common ground topology verified.**
