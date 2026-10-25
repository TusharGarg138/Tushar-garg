# Automated Testing & Verification History

This document details the test strategy, automated test suite catalog, synthetic validation packs, and execution history for the **Aeron Systems Weather Network QA Engine**.

---

## 1. Test Strategy & Architectural Principles

The test suite was designed according to four key principles required by the Aeron Systems engineering brief:

1. **Schema & Contract Compliance**: Ensure output artifacts (`flags.csv`, `report.pdf`, `report.html`) strictly adhere to specified columns, types, formatting rules, and sort orders.
2. **Physical Anomaly Sensitivity & Specificity**: Verify that detection algorithms catch subtle sensor failures (e.g. 1-wire bus resets, trapped rain funnels, clock rollbacks) while avoiding false positives on natural physical phenomena (e.g., zero rainfall during dry spells, high-altitude blizzards).
3. **Generalization Across Unseen Networks**: Ensure the engine does not overfit to the provided 8-station data pack by validating against three dynamically generated synthetic datasets.
4. **Data Pack Immutability**: Guarantee that running the checker leaves raw input datasets completely untouched, verifying MD5 checksum consistency before and after execution.

---

## 2. Complete Test Catalog (29 Tests)

The test suite comprises 29 automated test cases organized across 7 specialized test modules under [`tests/`](../../tests/):

### Module 1: CLI Interface & Invocation (`tests/test_cli.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_cli_help` | Verifies `--help` and `-h` display valid usage instructions, arguments, and exit code 0. | PASS |
| `test_cli_invalid_path` | Verifies passing a nonexistent data pack path produces an informative error and exits with code 1. | PASS |
| `test_cli_execution_from_different_working_directory` | Verifies `checker.py` executes reliably when invoked from an arbitrary working directory using relative paths. | PASS |
| `test_source_data_immutability` | Computes MD5 checksums of all raw files in `ridgeline_data_pack/` before and after execution to guarantee zero modification. | PASS |

### Module 2: Anomaly Detectors (`tests/test_detectors.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_detect_hardware_error_codes` | Asserts detection of digital 1-wire bus power-on register spikes (-40.0°C and +85.0°C) on temperature channels. | PASS |
| `test_detect_stuck_sensor` | Validates detection of zero-variance sensor flatlines exceeding threshold durations (e.g. 80 hours). | PASS |
| `test_false_positive_control_zero_rain_not_stuck` | Proves specificity: ensures consecutive 0.0 mm rain readings during extended dry spells are NOT falsely flagged as stuck. | PASS |
| `test_detect_physical_bounds_humidity` | Validates detection of impossible physical values (e.g. relative humidity > 100% or < 0%). | PASS |
| `test_detect_data_gap` | Asserts detection of unexpected sampling dropouts exceeding 3x the nominal station cadence. | PASS |
| `test_detect_clock_rollback` | Asserts detection of non-monotonic timestamp regressions and duplicate observation periods. | PASS |
| `test_detect_rain_clog_and_flush` | Validates detection of rain funnels blocked by debris (zero rain despite 95% humidity) followed by false surge flushes upon cleaning. | PASS |

### Module 3: Flag Schema Compliance (`tests/test_flags_schema.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_flags_csv_exact_schema` | Validates `flags.csv` against the 6 mandatory columns (`station_id`, `channel`, `start_time`, `end_time`, `action`, `evidence`) and verifies valid action values (`exclude`, `correct`, `keep`). | PASS |
| `test_flags_deterministic_sorting` | Asserts strict deterministic ordering: primary sort by `station_id` ascending, secondary sort by `start_time` ascending. | PASS |

### Module 4: GPS & Geodesic Validation (`tests/test_gps.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_verify_nmea_checksum_valid` | Asserts bitwise XOR checksum validation accepts standard valid NMEA-0183 sentences. | PASS |
| `test_verify_nmea_checksum_invalid` | Asserts checksum validator rejects corrupted or tampered NMEA sentences. | PASS |
| `test_parse_nmea_coordinates` | Validates accurate coordinate parsing from `ddmm.mmmm` notation into signed decimal degrees. | PASS |
| `test_detect_gps_clock_offset` | Detects persistent timezone offsets by correlating satellite UTC records against logger timestamps. | PASS |
| `test_detect_gps_metadata_mismatch` | Computes Haversine distance and flags station coordinate discrepancies exceeding 500 meters (e.g. S05 20 km displacement). | PASS |

### Module 5: Technician Prioritization Scoring (`tests/test_scoring.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_scoring_prioritizes_active_unrecoverable_hardware` | Proves the scoring algorithm prioritizes active unresolved hardware failures (`exclude`) over recoverable or non-corrupt anomalies (`correct`, `keep`). | PASS |
| `test_ridgeline_dataset_technician_ranking` | Confirms deterministic scoring for Ridgeline: Station S03 is Rank #1 (225.0 pt) and Station S05 is Rank #2 (35.0 pt). | PASS |

### Module 6: Synthetic Generalization (`tests/test_synthetic_generalization.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_generalization_clean_pack` | Runs pipeline on a synthetic 15-minute 3-station clean network; confirms zero exclusion flags are generated. | PASS |
| `test_generalization_multi_fault_pack` | Runs pipeline on a synthetic 5-minute multi-fault network with planted bus errors, clock drift, and stuck sensors; confirms accurate detection while leaving control stations clean. | PASS |
| `test_generalization_schema_variation_pack` | Validates pipeline resilience against missing optional files (e.g. absent GPS logs) and renamed column headers. | PASS |

### Module 7: Ingestion & Validation (`tests/test_validation.py`)

| Test Function | Verification Scope | Status |
| :--- | :--- | :--- |
| `test_normalize_column_names_standard` | Validates mapping of canonical atmospheric headers. | PASS |
| `test_normalize_column_names_aliases` | Validates robust aliasing (e.g. `AirTemp`, `T_C`, `Temp` -> `temp_c`; `RH`, `Humidity` -> `humidity_pct`). | PASS |
| `test_infer_sampling_interval_10min` | Confirms automatic cadence detection on 10-minute sampling intervals. | PASS |
| `test_infer_sampling_interval_5min` | Confirms automatic cadence detection on 5-minute sampling intervals. | PASS |
| `test_infer_sampling_interval_15min` | Confirms automatic cadence detection on 15-minute sampling intervals. | PASS |
| `test_infer_sampling_interval_too_few_records` | Verifies graceful fallback to default 5-minute cadence when observation sample size is insufficient. | PASS |

---

## 3. Synthetic Test Datasets

To ensure the solution is robust and not overfitted to `ridgeline_data_pack`, the test suite dynamically constructs synthetic data packs in temporary directories:

```text
Synthetic Dataset 1: Clean 15-Minute Baseline Network
├── Stations: 3 stations (SYN01, SYN02, SYN03)
├── Cadence: 15-minute sampling over 14 days
├── Faults: 0 planted faults
└── Outcome: Validates zero false positives and proper baseline pass-through.

Synthetic Dataset 2: Multi-Fault 5-Minute Network
├── Stations: 4 stations (FAULT01 to FAULT04)
├── Cadence: 5-minute sampling over 30 days
├── Planted Faults:
│   ├── FAULT01: 1-wire digital bus spikes (-40°C, 85°C)
│   ├── FAULT02: 4-hour clock rollback
│   ├── FAULT03: 48-hour relative humidity stuck at 82.5%
│   └── FAULT04: Control station (clean)
└── Outcome: Verifies multi-fault detection sensitivity and control isolation.

Synthetic Dataset 3: Schema Variation & Missing Stream Network
├── Stations: 2 stations (VAR01, VAR02)
├── Variations: Renamed headers (AirTemp, Press_hPa), omitted GPS logs, empty notes
└── Outcome: Verifies graceful degradation and resilient aliasing.
```

---

## 4. Execution Record & Environmental Verification

The test suite is regularly verified under Python 3.11:

```bash
# Full test suite execution command
python -m pytest -v
```

### Verified Output Summary
```text
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-8.3.3, pluggy-1.6.0
rootdir: E:\Aeron
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.11.0, hydra-core-1.3.4, langsmith-0.4.37
collected 29 items

tests\test_cli.py ....                                                   [ 13%]
tests\test_detectors.py .......                                          [ 37%]
tests\test_flags_schema.py ..                                            [ 44%]
tests\test_gps.py .....                                                  [ 62%]
tests\test_scoring.py ..                                                 [ 68%]
tests\test_synthetic_generalization.py ...                               [ 79%]
tests\test_validation.py ......                                          [100%]

============================= 29 passed in 8.23s ==============================
```

### Known Environmental Notes
- **Windows PyMuPDF Subprocess Edge Case**: During rapid automated subprocess spawning on Windows, `fitz` (`mupdf.pyd`) can intermittently raise a `MemoryError` if the C-runtime DLL heap encounters contention. In isolated execution and standard CLI runs, the report generation compiles reliably without memory leaks.
