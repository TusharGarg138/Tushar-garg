Full name: [YOUR FULL NAME]
Email: [YOUR EMAIL]
Video: [YOUR VIDEO LINK]
Run: python checker.py ridgeline_data_pack

# Ridgeline Weather Station Network: Automated Quality Assurance Engine

A robust, explainable, and generalizable Python data-quality framework designed for weather station networks. Built for the Aeron Systems AI Research Engineer Intern Assignment, the system audits raw weather station observations, correlates multi-channel time series with GPS receiver sentences and volunteer maintenance notebooks, produces schema-compliant quality flags, prioritizes technician field visits, and compiles printable executive health reports for nontechnical coordinators.

---

## 1. Project Purpose & Architecture

In community and school weather station networks, data loggers frequently encounter environmental and operational faults:
* Dead batteries causing real-time clock rollbacks and local timezone confusion (e.g. UTC vs MDT).
* Sensor failures and digital communication timeouts (e.g. 1-wire bus errors outputting -40.0°C and +85.0°C).
* Replacement hardware installed without calibration (e.g. uncalibrated barometer boards, anemometers outputting m/s instead of km/h).
* Environmental obstructions (e.g. leaf-clogged rain funnels that dump trapped precipitation when cleaned).
* Metadata errors (e.g. station installation sheet coordinates disagreeing with active GPS fixes).

This framework provides an end-to-end data screening and decision-support engine that distinguishes genuine extreme weather from hardware failure and transmission anomalies.

### Repository Layout

```text
├── checker.py                 # Main CLI data-quality checker
├── app.py                     # Interactive Streamlit exploration dashboard
├── flags.csv                  # Final quality flags for provided data pack
├── report.pdf                 # Printable 1-page A4 executive health report (PyMuPDF)
├── report.html                # Responsive, styled HTML executive report
├── DECISIONS.md               # 1.5-page reflection answering all 5 core questions
├── README.md                  # Complete setup, execution, and architecture guide
├── VIDEO_SCRIPT.md            # 3-minute video presentation outline
├── requirements.txt           # Project dependencies
├── pytest.ini                 # Pytest configuration
├── .gitignore                 # Exclusion rules (data packs, virtual environments)
├── src/                       # Modular source package
│   ├── __init__.py
│   ├── models.py              # Data structures (QualityFlag, StationMetadata, GPSRecord)
│   ├── loader.py              # Dynamic discovery & ingestion for CSVs, NMEA, and Markdown logs
│   ├── validation.py          # Schema validation, column aliasing, and cadence inference
│   ├── detectors.py           # Specialized data-quality detection algorithms
│   ├── consolidation.py       # Conflict resolution, suppression rules, deterministic sort
│   ├── scoring.py             # Technician visit prioritization engine
│   ├── reporting.py           # HTML and PDF report generation
│   ├── pipeline.py            # Shared analysis execution pipeline
│   └── utils.py               # Checksums, coordinate parsing, timestamp formatting
├── tests/                     # Automated test suite (28 passing tests)
│   ├── test_cli.py
│   ├── test_detectors.py
│   ├── test_flags_schema.py
│   ├── test_gps.py
│   ├── test_scoring.py
│   ├── test_synthetic_generalization.py
│   └── test_validation.py
└── ai_logs/                   # Authentic AI conversation logs & prompts
```

---

## 2. Prerequisites & Environment Setup

* **Python Version:** Python 3.9+ (tested on Python 3.11.0 on Windows and Linux).
* **Virtual Environment (Recommended):**

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 3. Execution & CLI Usage

### Basic CLI Command (Required Deliverable)

The main checker accepts a path to any data pack folder and outputs `flags.csv`, `report.html`, and `report.pdf` into the current working directory:

```bash
python checker.py ridgeline_data_pack
```

### CLI Arguments & Options

```text
usage: checker.py [-h] [--output-dir OUTPUT_DIR] [--no-report] datapack

positional arguments:
  datapack              Path to weather data pack directory containing stations.csv, data/, etc.

options:
  -h, --help            Show this help message and exit
  --output-dir OUTPUT_DIR
                        Directory where flags.csv and reports will be saved (default: .)
  --no-report           Skip generating report.html and report.pdf
```

The CLI works seamlessly regardless of where it is executed from (relative or absolute paths, paths containing spaces or non-ASCII characters).

---

## 4. Interactive Streamlit Dashboard

To launch the graphical exploration interface:

```bash
streamlit run app.py
```

The Streamlit UI provides:
1. Dynamic folder selection and validation.
2. Summary metrics and breakdown of `exclude`, `correct`, and `keep` actions.
3. Interactive filtering of `flags.csv` by station, channel, action, and text search.
4. Deep-dive inspection of evidence and sensor values for each finding.
5. Technician recommendation with 1-hour inspection protocols.
6. Embedded preview and download buttons for `flags.csv`, `report.html`, and `report.pdf`.

---

## 5. Input Schema & Data Format Expectations

The system does not hardcode station IDs, dates, or expected row counts. It dynamically discovers files based on flexible conventions:

### Supported Directory Layouts

```text
datapack_directory/
├── stations.csv              # Optional metadata (inferred from data if missing)
├── maintenance_log.md        # Optional volunteer notes (.md or .txt)
├── data/                     # Subfolder or root directory containing CSVs
│   ├── S01.csv
│   └── S02.csv
└── gps/                      # Optional GPS logs (.nmea)
    ├── S01.nmea
    └── S02.nmea
```

### Supported Column Aliases & Units

| Canonical Name | Recognized Aliases (Case-Insensitive) | Expected Physical Unit | Valid Range |
|---|---|---|---|
| `timestamp_utc` | `timestamp`, `time`, `datetime`, `date_time`, `utc_time` | UTC (`YYYY-MM-DD HH:MM`) | Plausible date |
| `temp_c` | `temp`, `temperature`, `temperature_c`, `air_temp` | °C | -50.0 to +60.0 |
| `rh_pct` | `rh`, `humidity`, `relative_humidity`, `humidity_pct` | % | 0.0 to 100.0 |
| `pressure_hpa` | `pressure`, `baro`, `barometer`, `pres_hpa` | hPa (station level) | 600.0 to 1100.0 |
| `wind_kmh` | `wind`, `wind_speed`, `speed_kmh`, `wind_speed_kmh` | km/h | 0.0 to 150.0 |
| `wind_dir_deg` | `wind_dir`, `wind_direction`, `direction_deg` | Degrees | 0 to 360 |
| `rain_mm` | `rain`, `precipitation`, `precip_mm`, `rainfall` | mm | 0.0 to 50.0 / step |
| `ghi_wm2` | `ghi`, `solar`, `radiation`, `solar_wm2` | W/m² | 0 to 1500 |

### Missing-Value Representations

Tolerates empty strings `""`, `"NA"`, `"N/A"`, `"null"`, `"None"`, `"NAN"`, `"-9999"`, and `"-999"`.

---

## 6. Exact `flags.csv` Schema & Action Semantics

The output `flags.csv` adheres strictly to the assignment's seven-column specification:

```csv
station_id,channel,start_utc,end_utc,issue,action,note
```

* `exclude`: Data is demonstrably corrupt, physically impossible, or invalid (e.g. digital fault code spikes, stuck sensor readings, duplicate transmissions, artificial flush dumps).
* `correct`: An objective, defensible, and reproducible adjustment is available (e.g. +6-hour clock timezone offset, -5.6 hPa barometric step offset, x3.6 anemometer multiplier, metadata GPS latitude correction).
* `keep`: Data appears unusual but represents plausible weather or microclimate variation that cannot be proven faulty without on-site reference sensors (e.g. S04 fence post repainting temperature variation).

---

## 7. Automated Testing & Generalization

Run the automated test suite with `pytest`:

```bash
python -m pytest -v
```

### Test Coverage (28 Passing Tests)

* **Generalization Acceptance Tests:**
  1. `test_generalization_clean_pack`: Tests 3 stations (`ALPHA`, `BETA`, `GAMMA`) with a 15-minute cadence. Verifies that 0 exclusion flags are generated on clean data.
  2. `test_generalization_multi_fault_pack`: Tests 4 stations (`STATION_101` to `104`) with a 5-minute cadence and multiple planted faults (stuck sensors, clock rollback, -40°C spikes). Verifies that faults are correctly isolated while control stations remain unflagged.
  3. `test_generalization_schema_variation_pack`: Tests non-standard file names (`NorthMtn_Sensor99.csv`), 30-minute sampling, column aliases, and complete absence of optional files (`stations.csv`, `gps/`).
* **False-Positive Controls:**
  * Confirms 3 consecutive days of 0.0 mm rain during dry spells are NOT falsely flagged as stuck sensors.
  * Confirms 0 W/m² solar radiation at night is NOT flagged as stuck.
* **CLI & Integration Tests:**
  * Executes CLI from temporary working directories and confirms `flags.csv` is written to `cwd`.
  * Verifies source data immutability (byte sizes and timestamps unchanged).
  * Validates exact schema and deterministic sorting.

---

## 8. What the Checker Automates vs Human Judgment

### What Is Fully Automated

* Multi-format data discovery, schema normalization, and sampling interval inference.
* Detection of exact and block transmission duplicates.
* Identification of non-monotonic timestamps, clock rollbacks, and timezone offsets.
* NMEA 0183 checksum verification, coordinate parsing, and GPS vs metadata validation.
* Physical bounds checking, digital bus error code spike detection (-40°C, 85°C), and stuck sensors.
* Correlation of maintenance events with step changes in barometric pressure and wind scaling.
* Cross-station verification of rain funnel clogs and cleaning flushes.
* Prioritization scoring for volunteer technician visits.

### What Requires Human Judgment

* Confirming whether small temperature shifts (+0.39°C at S04 post-painting) represent local microclimate variation or artificial albedo reflection.
* Verifying physical sensor manufacturer model numbers to permanently reconfigure data logger dip-switches on-site.
* Approving official derived climate summary publications.

---

## 9. Reproducing the Main Findings

To reproduce the findings on the provided 6-week dataset:

```bash
# 1. Run the checker
python checker.py ridgeline_data_pack

# 2. Inspect generated flags
head -n 20 flags.csv

# 3. View the generated report
# Open report.html in any web browser, or inspect report.pdf
```
