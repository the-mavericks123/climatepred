---
name: Orbital Precision HUD
colors:
  surface: '#0e131f'
  surface-dim: '#0e131f'
  surface-bright: '#343946'
  surface-container-lowest: '#080e1a'
  surface-container-low: '#161c28'
  surface-container: '#1a202c'
  surface-container-high: '#242a36'
  surface-container-highest: '#2f3542'
  on-surface: '#dde2f3'
  on-surface-variant: '#bcc9cd'
  inverse-surface: '#dde2f3'
  inverse-on-surface: '#2b303d'
  outline: '#869397'
  outline-variant: '#3d494c'
  surface-tint: '#4cd7f6'
  primary: '#4cd7f6'
  on-primary: '#003640'
  primary-container: '#06b6d4'
  on-primary-container: '#00424f'
  inverse-primary: '#00687a'
  secondary: '#7bd0ff'
  on-secondary: '#00354a'
  secondary-container: '#00a6e0'
  on-secondary-container: '#00374d'
  tertiary: '#ddb7ff'
  on-tertiary: '#490080'
  tertiary-container: '#c78dff'
  on-tertiary-container: '#5a009b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#acedff'
  primary-fixed-dim: '#4cd7f6'
  on-primary-fixed: '#001f26'
  on-primary-fixed-variant: '#004e5c'
  secondary-fixed: '#c4e7ff'
  secondary-fixed-dim: '#7bd0ff'
  on-secondary-fixed: '#001e2c'
  on-secondary-fixed-variant: '#004c69'
  tertiary-fixed: '#f0dbff'
  tertiary-fixed-dim: '#ddb7ff'
  on-tertiary-fixed: '#2c0051'
  on-tertiary-fixed-variant: '#6900b3'
  background: '#0e131f'
  on-background: '#dde2f3'
  surface-variant: '#2f3542'
typography:
  headline-2xl:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-2xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.015em
  headline-xl-mobile:
    fontFamily: Space Grotesk
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-telemetry-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-telemetry-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.08em
  label-telemetry-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.12em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-base: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  gutter-hud: 0.75rem
  margin-screen: 1.5rem
  panel-inset: 1rem
---

## Brand & Style

This design system embodies the high-stakes discipline of aerospace engineering merged with cutting-edge planetary climatology. Designed for mission controllers, catastrophe modelers, and emergency command teams, the interface projects unquestioned authority, immediate clarity, and cinematic gravitas. It rejects the visual noise of legacy telemetry dashboards in favor of an ultra-clean, information-dense HUD (Heads-Up Display) aesthetic.

The visual style unites **Technical Glassmorphism** with **Futuristic Telemetry Minimalism**:
- **Atmospheric Void:** Deep abyssal space backdrops ground the user in high-contrast optical focus, directing attention to real-time Earth telemetry and spatial hazard polygons.
- **Glass Optics & Razor Borders:** Sub-millimeter, translucent layered panels suspend contextual data over interactive 3D globe feeds without obscuring terrain dynamics.
- **Epistemic Certainty:** UI components systematically reflect the epistemic confidence of telemetry—distinguishing direct orbital observation from algorithmic simulation with tactical legibility.
- **High-Acuity Tactility:** Fine-line reticles, coordinate ticks, micro-grids, and controlled cyan luminescence evoke advanced orbital instrumentation.

## Colors

The palette establishes an optical hierarchy engineered for long-duration operation under low-ambient-light command environments.

### Base Spectrum
- **Deep Space Void (Canvas):** `#030712` anchors the global viewport. Panel backings step up subtly into `#060d1a` and `#0b1528` to construct optical stratification.
- **Atmospheric Cyan (Primary):** `#06b6d4` functions as the operational baseline—denoting active instruments, navigational telemetry, and active target locks.
- **Orbital Sky (Secondary):** `#38bdf8` serves as an elevated hover state, optical reticle accent, and razor-thin glass border baseline (`rgba(56, 189, 248, 0.2)`).
- **Compound Threat (Tertiary):** `#a855f7` handles compounding multi-hazard intersections (e.g., simultaneous tropical cyclone landfall with seismic shockwaves).

### Tactical Severity Spectrum
Hazard status tokens operate on absolute semantic anchors and must never be co-opted for decorative treatment:
- **Nominal / Safe:** `#10b981` (Telemetry synced, atmospheric pressure within expected standard deviations).
- **Advisory / Warning:** `#f59e0b` (Elevated convective energy, anomalous thermal signatures).
- **Severe Threat:** `#f97316` (Rapid intensification, wildfire perimeter breach).
- **Critical / Catastrophic:** `#ef4444` (Immediate life safety risk, category 5 trajectory, orbital anomaly).

### Neutral & Surface Transparency
All surfaces maintain high optical purity using neutral blue-shifted slates (`#94a3b8` body content, `#475569` structural borders and micro-ticks, and `#020617` underlying glass backplates).

## Typography

The typographic hierarchy enforces immediate distinction between situational narratives, system commands, and raw metric streams.

- **Primary Display (Space Grotesk):** Provides structured geometric confidence for module titles, operational sector headings, and primary threat summaries. Maintains aerodynamic curves paired with rigid technical baseline discipline.
- **Narrative & UI (Inter):** Maximizes screen legibility across multi-paragraph threat briefings, advisory protocols, and dense parametric lists.
- **Instrument Data & Micro-Labels (JetBrains Mono):** Drives all mission-critical numerical feeds, GPS coordinates, timestamps, UTC sync markers, sensor IDs, and epistemic classification tags. Ensures constant glyph width to prevent layout jitter during live data mutations.

## Layout & Spacing

The layout model implements a floating **HUD-Instrument Grid System**. The planetary viewport remains persistent in the z-plane, while modular panels anchor contextually to edges or float as configurable cards.

### Layout Mechanics
- **Grid Structure:** 12-column dynamic fluid workspace on desktop with explicit `12px` (`0.75rem`) internal micro-gutters and `24px` (`1.5rem`) outer safe bounds.
- **Instrument Alignment:** All panels align vertically and horizontally to a continuous 4px optical baseline grid. Dense telemetry stacks use 2px micro-separators.
- **Viewport Scaffolding:** 
  - **Desktop (1440px+):** Tri-panel cockpit layout. Left dock reserves 320px for telemetry trees and disaster feeds; right dock reserves 380px for epistemic modeling and predictive timelines; center field remains clear for orbital focus.
  - **Tablet (768px - 1439px):** Collapsible side rails transform into floating overlay drawers with semi-translucent glass backdrops, preserving at least 60% of the active map view.
  - **Mobile (<768px):** Bottom-sheet HUD cards stack vertically with single-column cards, collapsing telemetry lines into horizontal sliding strips.

## Elevation & Depth

Depth is conveyed through optical luminescence, translucency, and razor-sharp perimeter lines rather than heavy drop shadows.

- **Layer 0 (Cosmic Floor):** `#030712` non-reflective deep space surface housing planetary projection textures.
- **Layer 1 (Telemetry Panels):** `rgba(6, 13, 26, 0.65)` backplate combined with `backdrop-filter: blur(16px)` and a precision border of `1px solid rgba(56, 189, 248, 0.15)`.
- **Layer 2 (Overlays & Reticles):** `rgba(11, 21, 40, 0.85)` with `backdrop-filter: blur(24px)` and a primary border of `1px solid rgba(56, 189, 248, 0.35)`. Soft ambient glow: `box-shadow: 0 0 20px rgba(6, 182, 212, 0.08)`.
- **Layer 3 (Modal Alerts & Critical Vectors):** High-density glass (`rgba(15, 23, 42, 0.95)`), perimeter outline illuminated according to threat severity (e.g., `1px solid rgba(239, 68, 68, 0.5)` for critical events), cast with a diffused directional aura: `box-shadow: 0 0 32px rgba(239, 68, 68, 0.25)`.

## Shapes

The interface embraces a surgical, engineered profile. Roundedness is strictly restrained to level `1` (`0.25rem` / `4px`) for primary panels, cards, inputs, and chips.

- **Angular Precision:** The 4px standard radius softens micro-corners to prevent pixel clipping on high-DPI displays while retaining a machined, tactical aerospace silhouette.
- **Chamfered Elements:** Specialized command headers, epistemic badges, and mission alert cards may utilize 45-degree cut corners (chamfers) of 6px via clip-path mechanics to reflect hardware avionics styling.
- **Circular Instrument Reticles:** Reticles, target indicators, circular compass arrays, and coordinate radar tracks maintain pure geometric circular forms (50% border radius) to juxtapose fluid spatial data against the rigid grid of data panels.

## Components

### Buttons & Tactical Triggers
- **Primary Execution:** Machined cyan fill (`#06b6d4`) with black typography (`#030712`, `JetBrains Mono`, bold). Upper-case tracking (`0.1em`). Hover state increases brightness and casts an active cyan corona (`0 0 16px rgba(6, 182, 212, 0.4)`).
- **Secondary Telemetry Trigger:** Dark glass (`rgba(6, 13, 26, 0.7)`), 1px cyan perimeter (`rgba(56, 189, 248, 0.3)`), cyan text (`#38bdf8`). Micro-bracket glyphs (`[ ]`) on edges.
- **Danger Override:** Crimson fill (`#ef4444`) with high-contrast text and a pulsing halo for mission-critical actions (e.g., EVACUATION ORDER DISPATCH).

### Epistemic Status Badges
Engineered micro-components positioned at data origins to communicate epistemic confidence:
- **OBSERVED:** Border `1px solid #10b981`, background `rgba(16, 185, 129, 0.12)`, text `#10b981`. Includes a solid green target icon representing real-time orbital sensor validation.
- **PREDICTED:** Border `1px solid #38bdf8`, background `rgba(56, 189, 248, 0.12)`, text `#38bdf8`. Accompanied by a vector arrow glyph indicating temporal modeling.
- **SIMULATED:** Border `1px dashed #a855f7`, background `rgba(168, 85, 247, 0.12)`, text `#c084fc`. Signifies computational catastrophe scenario modeling.

### Telemetry Cards & HUD Panels
Constructed with Layer 1 glassmorphism, razor-thin borders, and decorative corner tick-marks (crosshairs on top-left and bottom-right). Header bands integrate tracking metrics in `JetBrains Mono` sm alongside uppercase module designations.

### Data Inputs & Filter Strips
- **Search & Telemetry Coordinate Entry:** Recessed dark surfaces (`#030712`) bordered by `rgba(56, 189, 248, 0.2)`. Focus transition activates an acute cyan neon border with zero outer offset blur.
- **Toggles & Segmented Selectors:** Monospaced pill-tabs within a rigid rectangular housing; active selection shifts from flat glass to luminous cyan framing.

### Specialized Domain Indicators
- **Spatial Polygon Hazard Overlays:** Semi-transparent vector surfaces draped directly over spatial maps. Outlines are calibrated at 1.5px with glowing stroke paths matched to severity tokens (e.g., `#ef4444` perimeter with `rgba(239, 68, 68, 0.15)` internal raster fill).
- **Holographic Reticles:** Multi-ring targeting vectors displaying live azimuth, elevation, and ground speed in real-time monospaced micro-type.