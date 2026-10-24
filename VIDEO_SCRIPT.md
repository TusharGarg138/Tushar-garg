# VIDEO_SCRIPT.md — 3-Minute Walkthrough Outline

## Video Details
* **Topic:** Ridgeline Schools Weather Network: Automated Data Quality Audit & Coordinator Decisions
* **Target Audience:** Technical Evaluation Committee / Network Coordinator
* **Duration:** Exactly 3 minutes (180 seconds)
* **Tone:** Professional, evidence-based, confident, and pragmatic

---

## Timed Walkthrough Script

### 0:00 – 0:25 (25s) | Introduction & Coordinator Objective
* **Screen:** Open assignment brief / network overview.
* **Speaker:**
  > "Hello! Today we are solving a real-world data quality challenge for the Ridgeline Schools Weather Network.
  > On Monday, the network coordinator has two decisions to make:
  > First, which station data is reliable enough to include in the spring climate summary?
  > Second, where to deploy the one volunteer technician for a high-impact, one-hour visit next week.
  > Our solution is built for explainability, defensibility, and generalization across unseen datasets."

### 0:25 – 0:50 (25s) | Repository Structure & Single Execution Command
* **Screen:** Terminal / IDE terminal view.
* **Action:** Run `python checker.py ridgeline_data_pack`.
* **Speaker:**
  > "The solution is organized cleanly into modular components under `src/` for ingestion, validation, detection, scoring, and reporting.
  > The primary deliverable is the CLI checker. With one single command, `python checker.py ridgeline_data_pack`, the pipeline dynamically discovers stations, validates schemas, cross-references GPS sentences and maintenance notes, and produces `flags.csv`, `report.html`, and `report.pdf` in the current working directory."

### 0:50 – 1:20 (30s) | The Strongest Flag: Evidence & Discovery
* **Screen:** Open `flags.csv` and show Station S06 and S08.
* **Speaker:**
  > "Here is our strongest finding: Station S06 on channel `all`.
  > On March 24th, after a battery replacement, logger timestamps jumped backward by nearly 6 hours, logging duplicate intervals from 10:10 to 16:00, followed by a persistent -6 hour offset.
  > By cross-referencing logger time against GPS UTC sentences, we confirmed the volunteer left the logger set to local Mountain Time (UTC-6) rather than UTC. Peak solar radiation shifted by exactly 6 hours.
  > Because the offset is known and constant, we assigned action `correct`, shifting timestamps by +6 hours to completely restore the data."

### 1:20 – 1:45 (25s) | The Least Certain Call: Microclimate vs Sensor Bias
* **Screen:** Highlight row S04 (`temp_c`, action `keep`).
* **Speaker:**
  > "Our least certain call is on Station S04 temperature from March 15th onward, where the garden committee repainted the fence and radiation shield post bright white.
  > Mean daytime temperature shifted upward by +0.39°C compared to neighbouring stations, likely due to increased surface albedo.
  > However, +0.39°C is well within natural spring temperature variance and microclimate differences. Because there is insufficient evidence to prove sensor corruption, we assigned the action `keep`—retaining the data for the climate summary while alerting the coordinator. A 48-hour comparison with an aspirated reference probe would settle it definitively."

### 1:45 – 2:15 (30s) | Technician Recommendation & Decision Rationale
* **Screen:** Open `report.pdf` (or `report.html`) and show the Technician section.
* **Speaker:**
  > "For the one-hour technician visit, our data-driven prioritization engine selects **Station S03 (Valley Library)** as Rank #1.
  > S03 has an active, recurring digital sensor communication fault, suffering an 80-hour freeze in mid-March and digital reset spikes (-40°C and 85°C) continuing as late as April 8th. Because temperature is the core spring climate variable and this hardware fault is active, a technician must inspect wiring terminals and swap the probe.
  > Our second-best candidate is Station S05. While S05 had an 84-hour humidity saturation event in early March, it dried out and self-recovered after March 11th, and its 20 km latitude mismatch is already documented in the GPS stream. S03 represents an active, unrecoverable threat that takes clear priority."

### 2:15 – 2:40 (25s) | Generalization & Automated Test Suite
* **Screen:** Terminal running `python -m pytest -v`.
* **Speaker:**
  > "Our checker is not hardcoded to this dataset. It dynamically infers cadences, handles arbitrary station IDs, and maps schema aliases.
  > In our automated test suite of 28 passing tests, we test three completely synthetic datasets:
  > A clean synthetic pack with 15-minute sampling that correctly produces zero exclusion flags;
  > A multi-fault pack with 5-minute sampling that detects planted anomalies while leaving control stations unflagged;
  > And a pack with missing optional files and alias columns."

### 2:40 – 3:00 (20s) | Summary Dashboard & Key Limitation
* **Screen:** Quick view of the interactive Streamlit UI (`streamlit run app.py`).
* **Speaker:**
  > "We also provide an interactive Streamlit UI for filtering flags and viewing evidence.
  > Our primary limitation: automated checks cannot distinguish between microclimate changes and subtle radiation shield albedo shifts without on-site reference sensors.
  > All deliverables, decision rationale, and reproducible commands are complete and ready in the repository. Thank you!"
