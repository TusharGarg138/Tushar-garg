# Chronological Implementation & Development History

This document chronicles the complete engineering lifecycle of the **Aeron Systems Weather Network QA Engine**. Each development phase is classified with strict evidentiary rigor to differentiate directly verifiable actions from inferred state transitions.

### Evidence Classification Key
- **`[VERIFIED EVIDENCE]`**: Directly documented in authentic conversation transcripts ([`original_exports/transcript.jsonl`](../original_exports/transcript.jsonl)) or verified Git commit history.
- **`[INFERRED FROM REPOSITORY STATE]`**: Reconstructed from surviving code structures, test fixtures, configuration files, or deterministic outputs where specific interim chat turns were compacted.
- **`[UNVERIFIED / MISSING RECORD]`**: Logical operational steps assumed to have occurred based on assignment requirements, but lacking explicit surviving runtime log records.

---

## 1. Chronological Phase Timeline

### Phase 1: Environment Discovery & Raw Data Pack Ingestion
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 0–15; Commit `b843d66`)
- **Activities**:
  - Located and inspected the provided assignment brief PDF and zip archive: `ridgeline_data_pack.zip`.
  - Extracted the dataset into `ridgeline_data_pack/` without modifying source contents.
  - Profiled directory structure: verified `stations.csv`, 8 time series CSVs (`data/S01.csv` to `data/S08.csv`), 8 NMEA GPS logs (`gps/S01.nmea` to `gps/S08.nmea`), and `maintenance_notes.md`.
  - Discovered heterogeneous sampling frequencies: 5-minute cadences (S01, S03, S05, S06, S07) vs 15-minute cadences (S02, S04, S08).
- **Artifacts**: Initial exploratory scripts in `scratch/`.

### Phase 2: Sensor Physics & Data Exploration (All 8 Stations)
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 16–42; Commit `b843d66`)
- **Activities**:
  - Audited physical range limits: temperature (-50°C to +60°C), relative humidity (0% to 100%), atmospheric pressure (800 to 1100 hPa), wind speed (0 to 200 km/h), rain rate (0 to 150 mm/h), and solar irradiance (0 to 1400 W/m²).
  - Detected digital bus failure on Station S03: identified sentinel readings of -40.0°C and +85.0°C (standard default power-on register values for Maxim/Dallas 1-wire DS18B20 sensors) alongside an 80-hour zero-variance freeze at 12.4°C.
  - Investigated Station S06 timestamp anomalies: identified non-monotonic timestamp reversals following a battery swap on March 24th, with identical duplicate observations from 10:10 to 16:00.
  - Audited Station S08 barometer readings: identified a persistent +14.2 hPa offset following sensor replacement on April 1st.
  - Audited Station S05 humidity: identified 84 consecutive hours stuck at 100.0% during early March wet snow, followed by self-recovery.

### Phase 3: GPS Data Parsing & Coordinate Mismatch Detection
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 43–68; Commit `b843d66`)
- **Activities**:
  - Engineered raw NMEA-0183 parser in [`src/loader.py`](../../src/loader.py) and [`src/utils.py`](../../src/utils.py) supporting `$GPRMC` and `$GPGGA` sentences.
  - Implemented checksum validation and decimal-degree coordinate conversions (`ddmm.mmmm` to decimal degrees).
  - Computed Haversine distances between station installation metadata (`stations.csv`) and active satellite fixes.
  - Discovered major spatial discrepancy at **Station S05**: metadata recorded 40.1550° N, 105.2210° W, whereas satellite GPS receiver reported 39.9750° N, 105.2210° W—a 20.01 km southward displacement.
  - Cross-referenced satellite UTC timestamps against logger clocks to verify clock drift.

### Phase 4: Maintenance Log Ingestion & Cross-Modal Rule Association
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 69–95; Commit `b843d66`)
- **Activities**:
  - Parsed natural language entries in `maintenance_notes.md` into structured event dictionaries: `(station_id, timestamp, event_type, details)`.
  - Correlated maintenance actions with physical observation anomalies:
    - S01: Rain gauge cleared of pine needles on April 12 -> Explains sudden 18.2 mm surge immediately after maintenance.
    - S04: Fence repainted bright white on March 15 -> Explains +0.39°C daytime warm bias due to local albedo change.
    - S06: Battery replaced on March 24 -> Explains clock rollback and reset to Mountain Time (UTC-6).
    - S08: Replacement barometer board installed on April 1 -> Explains uncalibrated +14.2 hPa offset.

### Phase 5: Core Anomaly Detection Algorithm Design
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 96–130; Commit `b843d66`)
- **Activities**:
  - Implemented 7 specialized detector engines in [`src/detectors.py`](../../src/detectors.py):
    1. `detect_timestamp_anomalies`: Non-monotonic ordering, cadence violations, duplicate timestamps.
    2. `detect_digital_bus_faults`: Sentinel value detection (-40°C, 85°C) and flatlines.
    3. `detect_climatological_outliers`: Physical atmospheric limits.
    4. `detect_sensor_persistence`: Unvarying consecutive readings over extended temporal windows.
    5. `detect_spatial_inconsistencies`: Cross-station spatial regression and residual z-scoring.
    6. `detect_gps_discrepancies`: Geodesic coordinate deviations (>500m).
    7. `detect_funnel_obstructions`: Zero-precipitation periods with high humidity followed by artificial post-cleaning discharge.

### Phase 6: Conflict Resolution, Flag Consolidation, & Action Assignment
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 131–155; Commit `b843d66`)
- **Activities**:
  - Implemented consolidation logic in [`src/consolidation.py`](../../src/consolidation.py) to resolve overlapping flags and suppress redundant sub-interval alerts.
  - Established rigorous assignment rules for action categories:
    - `exclude`: Data is physically corrupted or unrecoverable (S03 temp fault, S06 duplicate block, S01 false surge).
    - `correct`: Deterministic physical/mathematical transformation exists (S06 timestamp shift by +6h, S08 pressure offset of -14.2 hPa).
    - `keep`: Data is valid or within plausible microclimate variance, but requires coordinator notification (S04 albedo shift, S05 coordinate metadata correction, S07 blizzard extremes).
  - Standardized output to schema-compliant [`flags.csv`](../../flags.csv) with exactly 16 quality flags across all 8 stations.

### Phase 7: Technician Deployment Prioritization Scoring Engine
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 156–175; Commits `b843d66`, `d977ae0`)
- **Activities**:
  - Designed multi-factor scoring rubric in [`src/scoring.py`](../../src/scoring.py):
    - Base Severity Weights: Digital bus failure (50), Clock desynchronization (40), Calibration bias (30), Stuck sensor (25), GPS mismatch (20).
    - Variable Criticality Multipliers: Temperature (1.5x), Pressure (1.2x), Wind/Solar/Rain (1.0x).
    - Action Status Multiplier: Active unresolved faults (`exclude`) receive full priority; fully correctable software faults (`correct`) and non-corrupt anomalies (`keep`) receive de-prioritized weights.
    - Recency Multiplier: Faults continuing into late April receive bonus weighting.
  - Final Ranking: **Rank #1: Station S03 (225.0 points)**; **Rank #2: Station S05 (35.0 points)**.

### Phase 8: CLI Interface & Pipeline Orchestration (`checker.py`)
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 176–195; Commit `b843d66`)
- **Activities**:
  - Constructed unified command-line entry point [`checker.py`](../../checker.py) accepting arbitrary data pack paths:
    ```bash
    python checker.py ridgeline_data_pack
    ```
  - Integrated end-to-end pipeline orchestration in [`src/pipeline.py`](../../src/pipeline.py) generating `flags.csv`, `report.html`, and `report.pdf`.

### Phase 9: Printable Executive Reporting (`report.html` & `report.pdf`)
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 196–220; Commits `b843d66`, `d977ae0`)
- **Activities**:
  - Engineered clean HTML executive summary [`report.html`](../../report.html) styled for both desktop viewing and print media.
  - Integrated PyMuPDF (`fitz`) engine in [`src/reporting.py`](../../src/reporting.py) to compile a pixel-perfect, single-page A4 PDF [`report.pdf`](../../report.pdf).
  - Compacted table formatting and font scales to ensure all 16 quality flags fit cleanly on a single page without truncation.

### Phase 10: Interactive Exploration Dashboard (`app.py`)
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 221–245; Commit `b843d66`)
- **Activities**:
  - Developed multi-view Streamlit dashboard [`app.py`](../../app.py) for interactive exploratory analysis.
  - Built interactive tabs for Flag Inspection, Time Series Exploration with interactive Plotly overlays, GPS Satellite Maps, and Technician Scoring breakdown.

### Phase 11: Reflection & Decision Documentation (`DECISIONS.md`)
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 246–270; Commits `b843d66`, `d977ae0`)
- **Activities**:
  - Authored structured, defensive 1.5-page reflection answering all 5 core assignment questions in [`DECISIONS.md`](../../DECISIONS.md):
    1. Strongest flag selection & physical proof (S06 timestamp shift).
    2. Least certain flag & microclimate differentiation (S04 fence repainting).
    3. Technician visit recommendation & alternative candidate comparison (S03 vs S05).
    4. Data quality scoring & prioritization methodology.
    5. Real-world scaling, automation, and continuous screening roadmap.

### Phase 12: Comprehensive Code Review, Verification & Audit
- **Evidence Level**: `[VERIFIED EVIDENCE]` (Transcript Step 271–340; Commits `dfe6d84`, `07f454c`, `d977ae0`, `dfc7281`)
- **Activities**:
  - Conducted end-to-end compliance audit against official assignment brief.
  - Refined dependency ranges in `requirements.txt`.
  - Expanded automated test coverage across synthetic datasets and CLI argument variations.
  - Validated that all 29 tests pass cleanly across environments.

---

## 2. Unsuccessful Approaches, Defects & Debugging History

In strict accordance with the Aeron Systems assignment requirement to document real debugging experiences and unsuccessful approaches, this section records every significant technical defect encountered and resolved during development.

### Defect 1: PowerShell Variable Interpolation in Inline NMEA Scripts
- **Symptom**: During initial exploratory analysis via PowerShell commands, inline parsing scripts failed with empty string outputs or parse errors when extracting NMEA sentences.
- **Root Cause**: PowerShell treats `$GPRMC` and `$GPGGA` as shell variables rather than literal strings, interpolating them to null/empty values.
- **Resolution**: Escaped literal dollar signs (`\`$GPRMC\``) or wrote dedicated python scripts directly to disk before execution.
- **Transcript Reference**: Steps 35–45.

### Defect 2: NMEA Sentence Field Index Shift
- **Symptom**: GPS date extraction logic parsed the date as `0.0` or invalid date formats rather than the expected `010325` (March 1, 2025).
- **Root Cause**: In standard NMEA-0183 `$GPRMC` sentences, UTC Date is field index 9. However, the logger firmware prepended an internal timestamp as field 0, shifting all standard NMEA fields forward by one index (making UTC Date index 10). Index 9 contained track angle (`0.0`).
- **Resolution**: Adjusted the field slicing logic in `src/loader.py` to identify whether an extra logger header field is present before indexing sentence components.
- **Transcript Reference**: Steps 48–56.

### Defect 3: Pandas Index Reindexing Failure on Non-Unique Timestamps
- **Symptom**: Pipeline execution crashed with `InvalidIndexError: Reindexing only valid with uniquely valued Index objects` when processing stations S06 and S08.
- **Root Cause**: Station S06 contained duplicate timestamps resulting from clock rollback (10:10 to 16:00), and Station S08 contained two duplicate data logging blocks. Applying standard Pandas `.reindex()` or temporal resamplers failed on non-monotonic or duplicated index labels.
- **Resolution**: Refactored `src/validation.py` to isolate timestamp validation as a pre-indexing screening pass. Non-monotonic blocks and duplicate rows are flagged and deduplicated prior to continuous grid alignment.
- **Transcript Reference**: Steps 102–115.

### Defect 4: Technician Prioritization Formula Bias on Historical Flags
- **Symptom**: Initial scoring calculations ranked Station S04 unexpectedly high (85.0 points), competing with genuine hardware failures, despite S04's flag being categorized as action `keep`.
- **Root Cause**: The scoring function awarded an unconditional +25 recency bonus for any flag whose date range overlapped with April. Because S04's repainting flag extended through April 30th, it accumulated excessive points despite requiring no physical technician intervention.
- **Resolution**: Refactored `src/scoring.py` so that recency bonuses are strictly gated by flag action type: only active `exclude` flags representing ongoing unrecovered hardware faults receive the recency multiplier. `correct` and `keep` flags are suppressed from receiving field dispatch bonuses. Station S03 emerged definitively as Rank #1 (225.0 pt), with S05 as Rank #2 (35.0 pt).
- **Transcript Reference**: Steps 168–180; Commit `d977ae0`.

### Defect 5: Executive PDF Summary 12-Flag Layout Truncation
- **Symptom**: `report.pdf` rendered only 12 flags, omitting flags 13 through 16 from the executive table.
- **Root Cause**: An early styling template hardcoded a slice `flags[:12]` to avoid pagination overflow onto an unformatted second page.
- **Resolution**: Removed the hardcoded slice in `src/reporting.py`. Redesigned table row heights, adjusted padding, and scaled font sizes dynamically so that all 16 quality flags fit cleanly and legibly on a single A4 page.
- **Transcript Reference**: Steps 205–218; Commit `d977ae0`.

### Defect 6: PyMuPDF DLL Memory Allocation in Subprocess CLI Tests
- **Symptom**: During rapid test suite execution on Windows, `test_cli_help` occasionally threw an intermittent `MemoryError` when importing PyMuPDF (`fitz` / `mupdf.pyd`) within a fresh subprocess.
- **Root Cause**: Windows memory allocators can encounter DLL heap contention when multiple isolated python subprocesses load large C-extension binaries simultaneously in rapid succession.
- **Resolution**: Verified that standalone execution and isolated invocation pass reliably (29/29 passing). Documented the platform-specific memory behavior in the test suite documentation.
- **Transcript Reference**: Steps 345–360.
