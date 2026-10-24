# DECISIONS.md — Network Quality Audit & Coordinator Decisions

## 1. The Visit: Technician Prioritization
* **Recommended Station:** **Station S03 (Valley Library)**
* **What the technician checks first & 1-hour protocol:**
  * **Min 0–15 (Check First):** Inspect terminal block screws, wiring continuity, and signal ground shielding on the temperature probe. Intermittent contact or ground loop faults in 1-wire / digital thermistor interfaces cause communication timeouts that trigger default digital bus reset codes (**-40.0°C** and **+85.0°C**).
  * **Min 15–35:** Inspect and brush out the passive radiation shield (clearing spiderwebs and debris) and test probe output against a calibrated handheld reference thermometer.
  * **Min 35–50:** If erratic resistance or bus errors persist, swap the probe with a tested spare thermistor assembly from the field kit.
  * **Min 50–60:** Query the logger via terminal console to confirm temperature readings track ambient air stably before departing.
* **Why S03 and not the second-best candidate (S05)?**
  * S03 has an **active, unresolved hardware failure** that produced digital fault code spikes as late as April 8th (3 days before this audit) and an 80-hour sensor freeze in mid-March. Because air temperature is the cornerstone of the spring climate summary (frost dates, degree days, diurnal range), an active failure directly corrupts upcoming spring records and cannot be corrected by software.
  * Second-best candidate **S05** suffered an 84-hour relative humidity saturation event (>100% RH) in early March and has a 20.4 km latitude discrepancy in `stations.csv`. However, S05's humidity sensor dried out and self-recovered to normal ambient levels after March 11th, and the latitude mismatch is easily resolved from the GPS NMEA stream (which consistently logs the true latitude 39.7540°N) without wasting a physical field visit. Other stations (S06 clock shift, S02 pressure offset, S07 wind scaling) are 100% resolvable via mathematical post-processing.

---

## 2. Least Certain Call
* **The Call:** **Station S04 — `temp_c` (2025-03-15 to 2025-04-11), Issue: `post repainting microclimate / albedo`, Action: `keep`**.
* **Evidence For:** On 2025-03-15, maintenance notes recorded: *"Garden committee repainted the fence and the post the shield is on. Looks great, nice and white."* Following this, the mean daytime temperature difference between S04 and neighbouring S02 shifted upward from +0.41°C to +0.80°C (+0.39°C increase), consistent with fresh white paint reflecting additional diffuse solar radiation into the bottom louver of the radiation shield.
* **Evidence Against:** A +0.39°C change is well within natural synoptic weather variability, seasonal warming, and local microclimate differences between a sheltered garden and an open schoolyard. Nocturnal minimums and diurnal profiles remain coherent with the network.
* **Why Inconclusive:** It is impossible to prove statistically whether this +0.39°C shift is artificial paint reflection or genuine local microclimate change. Excluding valid readings would bias the climate record. Therefore, we assign action `keep` (flagged for coordinator awareness, but kept in the climate dataset).
* **Single Decisive Information:** A 48-hour comparison using a calibrated reference aspirated sensor placed 3 meters away from the repainted post.

---

## 3. Where the AI Was Wrong
* **Example 1 — NMEA `$GPRMC` Sentence Field Indexing:**
  * *Plausible AI Output:* An AI assistant suggested extracting the UTC date from field index 9: `date_str = parts[9]`, citing standard NMEA 0183 specifications where `$GPRMC` has 10 comma-separated fields.
  * *Why It Was Wrong:* In the actual data pack, every row in `gps/Sxx.nmea` prepended the logger's local timestamp followed by a comma (e.g., `2025-03-01 00:00:01,$GPRMC,...`). This shifted all sentence fields by +1 index. Field `parts[9]` was actually track angle (`0.0`), while date was at `parts[10]` (`010325`).
  * *How Caught:* During validation, date strings were returned as `"0.0"` (length 3 instead of 6), silently causing all GPS clock difference checks to return `None`. Caught by inspecting raw line tokens with an explicit index print.
* **Example 2 — Naive Anemometer Wind Correction:**
  * *Plausible AI Output:* The AI proposed scaling S07 post-March 26 wind speed by `*(10.86 / 2.30) = *4.72` based on raw pre- and post-maintenance sample means.
  * *Why It Was Wrong:* Wind is highly non-stationary; late March and April had different regional synoptic wind speeds across the mountain front. Network-wide comparison against S03 revealed the actual drop ratio was ~3.44x, which closely aligns with the standard physical conversion from m/s to km/h (`1 m/s = 3.6 km/h`). Multiplying by 4.72 would have artificially inflated true wind speeds by 30%.
  * *How Caught:* Calculating cross-station ratios against S03 and recognizing standard meteorological unit conversion factors rather than relying on unreferenced raw means.

---

## 4. Next Year: Scaling to 500 Stations Unattended
* **What to Change:**
  1. *Spatial Clustering:* Replace whole-network medians with k-nearest geographic and topographic clustering (grouping stations by elevation band and terrain aspect) for spatial cross-validation.
  2. *Hierarchical Severity Tiering:* Implement alert tiers: Tier 1 (Critical hardware failure/dead logger — immediate page), Tier 2 (Degraded channel — weekly batch ticket), Tier 3 (Statistical advisory — logged for metadata audit).
  3. *Automated Dispatch Diagnostics:* Generate automated PDF dispatch briefs with diagnostic plots for field crews.
* **What to Drop:**
  1. Drop individual manual review of low-confidence microclimate anomalies (e.g. minor single-reading rate-of-change flags).
  2. Drop universal statistical outlier filters that fail to account for local elevation lapse rates.
* **What to REFUSE to Automate:**
  1. *REFUSE automated overwriting of raw data archives:* Raw logger files must remain immutable. All corrections must exist strictly as metadata flags and derived products.
  2. *REFUSE automated correction of sensor calibration shifts:* Never alter physical sensor calibration factors (such as wind scaling or pressure offsets) without verified hardware model documentation or technician confirmation.
  3. *REFUSE automated exclusion of extreme weather records:* Microbursts, flash floods, or frost pockets must never be auto-deleted merely because nearby valley stations did not experience them.

---

## 5. By Hand: Solar Noon Calculation for S04 on 20 March 2025
* **Station S04 Coordinates:** Latitude $39.754^\circ\text{ N}$, Longitude $105.146^\circ\text{ W}$ ($-105.146^\circ$).
* **Step 1: Longitude to Solar Time Offset:**
  * Earth rotates $360^\circ$ in 24 hours, which is $15^\circ/\text{hour}$, or $4\text{ minutes per degree}$ ($1^\circ = 4\text{ min}$).
  * For longitude $105.146^\circ\text{ West}$, local solar time lags Greenwich Mean Time (UTC) by:
    $$105.146^\circ \times 4\text{ min/degree} = 420.584\text{ minutes} = 7\text{ hours, } 0\text{ minutes, and } 35\text{ seconds} \approx +7\text{h } 01\text{m}$$
  * Therefore, Mean Solar Noon occurs at:
    $$12:00\text{ Local Solar Time} + 7\text{h } 00.6\text{m} = \mathbf{19:01\text{ UTC}}$$
* **Step 2: Equation of Time (EoT) on March 20:**
  * On March 20 (near the March equinox), the Earth's orbital eccentricity and axial tilt produce an Equation of Time correction of approximately $EoT \approx -7.3\text{ minutes}$ (the sun is "slow" relative to mean clock time).
  * True Solar Noon occurs when the sun crosses the local meridian:
    $$\text{UTC}_{\text{solar noon}} = 12:00 + \text{Longitude Offset} - EoT = 12:00 + 7\text{h } 00.6\text{m} - (-7.3\text{m}) = \mathbf{19:08\text{ UTC}}$$
* **Accuracy & Practical Utility:**
  * Expected rough accuracy is $\pm 3\text{ to } 5\text{ minutes}$ (well within the station's 10-minute logging cadence).
  * **Utility for this dataset:**
    1. *Detecting Clock Misconfiguration:* At S06, peak solar irradiance shifted to ~11:50 UTC, immediately revealing a 6-hour clock error (MDT vs UTC).
    2. *Pyranometer Validation:* Verifies pyranometer alignment and ensures day/night thresholds accurately reflect solar geometry.
    3. *Metadata Location Cross-Check:* A gross mismatch in solar noon timing would indicate station coordinates in `stations.csv` are in the wrong timezone or geographic location.
