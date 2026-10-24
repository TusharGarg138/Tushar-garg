# DECISIONS.md — Network Quality Audit & Coordinator Decisions

> **Candidate Note:** Review this concise draft and confirm it reflects your own reasoning and voice before submitting.

---

### 1. The Visit: Technician Prioritization
* **Station to Visit:** **Station S03 (Valley Library)**.
* **1-Hour Protocol & What to Check First:**
  * **Min 0–15 (Check First):** Inspect terminal block screws and ground shielding on the temperature probe. Intermittent connections or signal ground loops on digital 1-wire interfaces trigger bus timeouts that cause default fault reset codes (**-40.0°C** and **+85.0°C**).
  * **Min 15–35:** Inspect and brush out the passive radiation shield; check live readings against a calibrated reference thermometer.
  * **Min 35–50:** Replace the probe with a tested spare thermistor assembly.
  * **Min 50–60:** Query live logger data via terminal console to confirm stable ambient tracking.
* **Why S03 Over S05 (Second-Best):** S03 suffers an **active, recurring hardware failure** with digital fault spikes persisting through April 8th and an 80-hour sensor freeze in mid-March. Because temperature is the primary parameter for spring climate summaries (frost dates, degree days), active failures directly corrupt upcoming data and cannot be fixed in software. In contrast, second-best candidate **S05** experienced early-March humidity saturation (>100% RH) that self-recovered after March 11th, while its 20.4 km latitude discrepancy in `stations.csv` is already documented in the GPS NMEA stream (39.7540°N). S03 is an active, unrecoverable threat and takes priority.

---

### 2. Least Certain Call
* **Decision:** **Station S04 — `temp_c` (2025-03-15 to 2025-04-11), Issue: `post repainting microclimate / albedo`, Action: `keep`**.
* **Evidence For:** On 2025-03-15, volunteers repainted the fence and shield post white. Daytime temperature difference `(S04 - S02)` shifted upward from +0.41°C to +0.80°C (+0.39°C increase), consistent with increased surface albedo reflecting diffuse solar radiation into the shield.
* **Evidence Against:** A +0.39°C shift is well within natural synoptic weather variability, seasonal warming, and local microclimate differences. Diurnal patterns and nocturnal minimums remain coherent with surrounding stations.
* **Why Inconclusive:** We cannot prove statistically whether this shift is artificial paint reflection or genuine microclimate change without an adjacent reference probe. Excluding valid data would bias the record; hence, action `keep` retains the observations while alerting the coordinator.
* **Decisive Test:** A 48-hour comparison against an aspirated reference sensor placed 3 meters away from the post.

---

### 3. Where the AI Was Wrong
* **Example 1 — NMEA `$GPRMC` Date Indexing:** An AI assistant suggested extracting the UTC date from field index 9: `parts[9]`, citing standard NMEA 0183 specifications (`$GPRMC,time,status,lat,N,lon,W,spd,track,date`). In this data pack, however, every line in `gps/Sxx.nmea` prepended the logger timestamp and a comma (e.g., `2025-03-01 00:00:01,$GPRMC,...`), shifting all indices by +1. Field `parts[9]` was track angle (`0.0`), while the date was at `parts[10]` (`010325`). Parsing returned `"0.0"` (length 3 instead of 6), silently failing all GPS clock checks until caught by inspecting raw line tokens.
* **Example 2 — Naive Anemometer Multiplier:** An AI suggested multiplying S07 post-March 26 wind by `10.86 / 2.30 = 4.72` using raw pre/post means. This failed because spring synoptic wind is non-stationary. Cross-station comparison against S03 revealed the true ratio was ~3.44x, matching the physical unit conversion from m/s to km/h (`1 m/s = 3.6 km/h`). Multiplying by 4.72 would have artificially inflated true wind speeds by 30%.

---

### 4. Next Year: Scaling to 500 Stations Unattended
* **What to Change:** Implement spatial clustering (grouping stations by elevation band and terrain aspect for peer cross-validation), hierarchical severity tiers (P1 critical hardware, P2 degraded channel, P3 advisory), and automated dispatch briefs for field crews.
* **What to Drop:** Drop manual review of low-confidence microclimate anomalies and universal outlier filters that ignore lapse rates.
* **What to REFUSE to Automate:**
  1. *Refuse automated overwriting of raw archives:* Raw logger files must remain immutable; all adjustments must be metadata flags or derived products.
  2. *Refuse automated sensor recalibration without datasheets:* Never alter physical calibration factors without verified hardware documentation.
  3. *Refuse automated deletion of extreme weather:* Microbursts and flash floods must never be auto-deleted merely because nearby valley stations missed them.

---

### 5. By Hand: Solar Noon Calculation for S04 on 20 March 2025
* **Station Coordinates:** Latitude $39.754^\circ\text{ N}$, Longitude $105.146^\circ\text{ W}$ ($-105.146^\circ$).
* **Step 1: Longitude to Solar Time Offset:** Earth rotates $360^\circ$ in 24 hours ($15^\circ/\text{hr}$, or $4\text{ min/degree}$). Local solar time lags UTC by:
  $$105.146^\circ \times 4\text{ min/degree} = 420.584\text{ minutes} \approx +7\text{h } 00.6\text{m}$$
  Mean Solar Noon: $12:00\text{ Solar Time} + 7\text{h } 00.6\text{m} = \mathbf{19:01\text{ UTC}}$.
* **Step 2: Equation of Time (EoT) on March 20:** Near the March equinox, orbital eccentricity and axial tilt produce an Equation of Time correction of approximately $EoT \approx -7.3\text{ minutes}$ (the sun is "slow" relative to mean clock time).
  $$\text{UTC}_{\text{solar noon}} = 12:00 + 7\text{h } 00.6\text{m} - (-7.3\text{m}) = \mathbf{19:08\text{ UTC}}$$
* **Utility for Quality Assurance:**
  1. *Detecting Clock Errors:* At S06, peak solar irradiance shifted to ~11:50 UTC, immediately revealing a 6-hour clock error (MDT vs UTC).
  2. *Pyranometer Verification:* Confirms pyranometer diurnal alignment and ensures day/night thresholds match solar geometry.
