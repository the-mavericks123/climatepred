# Climate Eye View — Final Demo Checklist & Operator Playbook

**Version:** 1.0.0 (Release Freeze)  
**Date:** September 8, 2026  
**Audience:** Hackathon Demo Presenters, Operators, Evaluators  

---

## 1. Quick Start (Step-by-Step)

### Step 1: Start Backend Services (S2 Intelligence)
Open Terminal 1:
```powershell
# From models root:
.venv\Scripts\python -m uvicorn intelligence.app.main:app --host 127.0.0.1 --port 8000
```
- Verify: Open `http://127.0.0.1:8000/api/v1/health` in browser.
- Expect: `{"status": "healthy", "service": "climate-intelligence"}`.

### Step 2: Start Frontend & Gateway (S1 God's Eye View)
Open Terminal 2:
```powershell
# From models root:
npm --prefix Work/gods-eye-view run dev
```
- Verify: Terminal reports `VITE ready ... Local: http://localhost:4173/`.
- Verify: Open `http://localhost:4173/api/climate/health`.
- Expect: `"intelligence": "connected"`.

### Step 3: Open the God's Eye View Console
- Navigate browser to: **`http://localhost:4173/`**
- The Cesium 3D globe will load with the **Climate Eye** command center overlay.

---

## 2. Golden Hackathon Demo Path (5 Minutes)

### Phase 1: Baseline Normal Observation
1. In the top mode bar, ensure **`LIVE`** mode is active.
2. Point out the sensor stations on the 3D globe (`NODE-001` through `NODE-006`).
3. Point out the **Threat Card** on the right panel showing normal ambient conditions.
4. **Epistemic Invariant Highlight:** Click a sensor node. Show that `water_level` is honestly displayed as `UNAVAILABLE / null` (NOT fake zero), explaining that the physical hardware kit does not include an ultrasonic water depth transducer.

### Phase 2: Sensor Ingestion & Rapid Detection
1. Highlight live incoming readings: Temperature, Humidity, Pressure, Soil Moisture, Dust (PM2.5), Ambient Light (Lux), GPS coordinates.
2. Show that sensor calibration is honestly flagged as `UNVERIFIED` because physical field calibration curves have not been certified.

### Phase 3: What-If Digital Twin Scenario (+40% Rainfall Surge)
1. Click the **`SIMULATION`** tab on the top menu.
2. Select scenario **`Rain +40% (SCN-RAIN-40)`** and click **Run Simulation**.
3. **Observation:**
   - The UI displays an amber badge: `SIMULATED: true` (strictly preventing confusion with real-world live data).
   - Inundation polygons appear on the 3D Cesium terrain.
   - The **Threat Card** updates to `FLASH FLOOD DETECTED (Severity: 0.82)`.

### Phase 4: Compound Cascade & Human Vulnerability
1. Show the **Compound Cascade Chain** in the right panel:
   `Extreme Precipitation -> Soil Saturation (100%) -> Runoff -> Bridge Submersion -> Sector Cutoff`.
2. Show the **Vulnerability Card**:
   - CDC Social Vulnerability Index (SVI) score of the affected sector.
   - Highlight: 14,200 residents exposed, including 2,100 elderly individuals.

### Phase 5: Dynamic Evacuation & Safe Route
1. Click the **`EMERGENCY`** mode tab.
2. Point out the dynamic evacuation polyline rendered on the 3D globe.
3. Show how the route avoids the submerged bridge and guides evacuees to High School Shelter Alpha.
4. Note that if all bridges fail, the engine outputs `NO_ROUTE` and marks `ISOLATED_ZONE` rather than generating a dangerous path.

### Phase 6: AI Incident Command Response Directives
1. View the **AI Climate Agent Directives Card**:
   - `ALERT LEVEL: RED`
   - Directive 1: `Close Bridge 4B (Urgency: IMMEDIATE)`
   - Directive 2: `Deploy High-Water Rescue Team to Sector 7`
   - Directive 3: `Stage Emergency Backup Power at Regional Hospital`
2. Click **Explain Decision**: Show the factor weight breakdown (SHAP / feature contribution) and formula provenance, proving the AI reasoning is grounded and deterministic.

---

## 3. Fallback & Troubleshooting Procedures

| Issue | Root Cause | Operator Fix |
| :--- | :--- | :--- |
| **Globe shows black screen** | WebGL context lost or browser hardware acceleration disabled | Open browser settings -> Enable "Hardware Acceleration" -> Reload `http://localhost:4173/`. |
| **S1 reports 503 MODEL_UNAVAILABLE** | S2 FastAPI service is not running | Open terminal, restart `.venv\Scripts\python -m uvicorn intelligence.app.main:app --port 8000`. S1 recovers automatically. |
| **Port 4173 already in use** | Prior Node process still bound to port | Run `Get-Process node \| Stop-Process -Force` in PowerShell, then re-run `npm --prefix Work/gods-eye-view run dev`. |
| **Port 8000 already in use** | Prior Python process still running | Run `Get-Process python \| Stop-Process -Force` in PowerShell, then restart uvicorn. |

---

## 4. Verification Check Before Stepping Onstage

Run this one-liner in PowerShell:
```powershell
.venv\Scripts\python -c "import urllib.request, json; s2=json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').read()); s1=json.loads(urllib.request.urlopen('http://localhost:4173/api/climate/health').read()); print('S2:', s2['status'], '| S1:', s1['subsystems']['intelligence'])"
```
- Expected output: `S2: healthy | S1: connected`.
- If you see this output, the entire integrated platform is **100% DEMO READY**.
