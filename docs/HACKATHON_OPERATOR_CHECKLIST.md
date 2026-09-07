# Climate Eye View — Hackathon Operator Checklist & Runbook

**Document Version:** 1.0.0  
**Target:** Live Stage & Demo Operations  

---

## 1. Pre-Event Bench Checklist (2 Hours Before Demo)

- [ ] **Python Environment:** Verify `.venv\Scripts\python.exe --version` outputs Python 3.13.5.
- [ ] **Node Environment:** Verify `node --version` outputs `>= v24.14.0`.
- [ ] **Full Regression Suite:** Run `.venv\Scripts\pytest.exe` to confirm 748/748 tests pass.
- [ ] **GEV Production Build:** Run `npm --prefix gods-eye-view run build` to ensure clean asset bundling.
- [ ] **Hardware Power Rail:** Measure LM2596 output with a multimeter. Ensure it reads **5.00V ± 0.1V**.
- [ ] **Antenna Connection:** Ensure 433 MHz helical or whip antenna is screwed firmly into RA-02 SMA connectors on both the transmitter node and the receiver gateway.
- [ ] **Common Ground:** Confirm all modules share a common 0V ground rail.

---

## 2. Live Demo Startup Sequence (5 Minutes Before Stage)

### Step 1: Start the Intelligence Backend Service
Open Terminal 1:
```powershell
cd c:\Users\yagna\OneDrive\Documents\models
.venv\Scripts\activate
python -m uvicorn intelligence.app.main:app --host 127.0.0.1 --port 8000
```
*Verify output:* `INFO: Uvicorn running on http://127.0.0.1:8000`

### Step 2: Start the GEV 3D Frontend
Open Terminal 2:
```powershell
cd c:\Users\yagna\OneDrive\Documents\models\gods-eye-view
npm run dev
```
*Verify output:* `VITE ready in ~400 ms. Local: http://localhost:4173/`

### Step 3: Open Browser
Navigate to `http://localhost:4173/` in Google Chrome. Confirm the 3D globe initializes.

### Step 4: Power On Physical ESP32 Hardware
Connect the 12V battery or USB-C power rail. Verify:
- ESP32 power LED glows steady RED.
- NEO-6M GPS power LED glows steady GREEN.
- RA-02 LoRa module shows momentary TX LED blinks every 10 seconds.

---

## 3. The 5-Minute Pitch & Demonstration Script

### Act 1: Sense & Geolocation (0:00 – 1:30)
- **Show:** The GEV 3D globe centered over Hyderabad station `NODE-001`.
- **Explain:** *"This station is receiving live environmental telemetry transmitted over long-range 433 MHz LoRa radio packets."*
- **Action:** Click the `NODE-001` marker on the globe to open the live telemetry card.
- **Physical Interaction:** Shine a phone flashlight onto the BH1750 ambient light sensor.
- **Result:** Within 10 seconds, watch the `light_intensity` value on the screen jump from 150 lux to >1200 lux in real time.

### Act 2: Epistemic Honesty & Missing Water Level (1:30 – 2:30)
- **Point out:** The Flood Risk panel on the screen.
- **Explain:** *"Notice that Flood Risk is marked `UNAVAILABLE / INSUFFICIENT EVIDENCE`. Why? Because our physical hardware node lacks a water-level sensor. A real-world emergency system must never invent fake numbers or assume 0.0 water level."*
- **Judge Value:** Demonstrates military-grade data integrity and safety-critical engineering.

### Act 3: Digital Twin & Cascade Hazard Simulation (2:30 – 4:00)
- **Action:** Open the **Digital Twin Scenario** panel in the UI.
- **Select:** `What-If: Heavy Rainfall (+40% Precipitation)`.
- **Explain:** *"While live telemetry reports real current conditions, emergency planners need to stress-test the future. Here we simulate a 40% rainfall surge."*
- **Result:**
  - Simulation badge illuminates in purple: `SIMULATED`.
  - Flood risk vector surges across low-lying terrain zones.
  - Human Vulnerability Index highlights demographic zones at risk.
  - Dynamic Evacuation Engine calculates real-time A* evacuation routes navigating around flooded roads to designated shelters.

### Act 4: LoRa Link Loss & Rapid Reconnect (4:00 – 5:00)
- **Physical Action:** Disconnect the USB power to the ESP32 node.
- **Result:** Within 30 seconds, the station billboard on the GEV globe shifts to `STALE / OFFLINE`.
- **Physical Action:** Plug the power back in.
- **Result:** Within 10 seconds, the billboard shifts back to `LIVE`.

---

## 4. Emergency Stage Protocol (< 60 Seconds Fallback)

If hardware disconnects or a wire comes loose during the presentation:
1. Do not panic or try to rewire on stage.
2. Open a terminal and run the Level 3 Replay script:
   ```powershell
   .venv\Scripts\python.exe -m intelligence.scripts.run_phase11_golden_production_path
   ```
3. Announce confidently to the judges: *"We've transitioned to our deterministic high-fidelity replay pipeline to demonstrate the downstream intelligence cascade."*
