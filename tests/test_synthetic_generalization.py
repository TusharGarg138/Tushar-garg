"""
Generalization Acceptance Tests across synthetic compatible data packs.
Tests different station IDs, dates, station counts, intervals, and optional files.
"""

import os
import shutil
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.pipeline import run_pipeline
from src.utils import format_utc_timestamp


def create_synthetic_clean_pack(dest_dir: str):
    """
    Synthetic Pack 1: Clean control dataset.
    - Station IDs: ALPHA, BETA, GAMMA (3 stations)
    - Date range: 2026-05-01 to 2026-05-10
    - Sampling interval: 15 minutes
    - Must NOT generate any spurious exclusion flags.
    """
    os.makedirs(os.path.join(dest_dir, "data"), exist_ok=True)
    dates = pd.date_range("2026-05-01 00:00", "2026-05-10 23:45", freq="15min")
    n = len(dates)
    
    # Metadata
    meta_df = pd.DataFrame([
        {"station_id": "ALPHA", "name": "Alpha Hill", "lat": 42.10, "lon": -102.50, "elevation_m": 1200, "logger_interval_min": 15},
        {"station_id": "BETA", "name": "Beta Valley", "lat": 42.20, "lon": -102.40, "elevation_m": 1050, "logger_interval_min": 15},
        {"station_id": "GAMMA", "name": "Gamma Plains", "lat": 42.30, "lon": -102.30, "elevation_m": 980, "logger_interval_min": 15},
    ])
    meta_df.to_csv(os.path.join(dest_dir, "stations.csv"), index=False)

    for st_id, base_temp in [("ALPHA", 15.0), ("BETA", 17.0), ("GAMMA", 18.0)]:
        # Realistic diurnal sine wave
        time_hours = np.array([(d - dates[0]).total_seconds() / 3600.0 for d in dates])
        diurnal = 8.0 * np.sin(2 * np.pi * (time_hours - 6) / 24.0)
        temp = base_temp + diurnal + np.random.normal(0, 0.5, n)
        rh = np.clip(60.0 - 2.5 * diurnal + np.random.normal(0, 1.0, n), 15.0, 95.0)
        pres = 880.0 + 3.0 * np.cos(2 * np.pi * time_hours / 24.0) + np.random.normal(0, 0.3, n)
        wind = np.clip(12.0 + 4.0 * np.sin(2 * np.pi * time_hours / 24.0) + np.random.normal(0, 1.5, n), 1.0, 45.0)
        rain = [0.0] * n  # dry sunny period
        ghi = np.clip(800.0 * np.sin(np.pi * ((dates.hour + dates.minute / 60.0 - 6) / 12.0)), 0, 950)
        
        df = pd.DataFrame({
            "timestamp_utc": dates.strftime("%Y-%m-%d %H:%M"),
            "temp_c": np.round(temp, 1),
            "rh_pct": np.round(rh, 1),
            "pressure_hpa": np.round(pres, 1),
            "wind_kmh": np.round(wind, 1),
            "wind_dir_deg": [180] * n,
            "rain_mm": rain,
            "ghi_wm2": np.round(ghi, 0).astype(int)
        })
        df.to_csv(os.path.join(dest_dir, "data", f"{st_id}.csv"), index=False)


def create_synthetic_multi_fault_pack(dest_dir: str):
    """
    Synthetic Pack 2: Multiple planted overlapping faults.
    - Station IDs: STATION_101, STATION_102, STATION_103, STATION_104 (4 stations)
    - Date range: 2026-07-01 to 2026-07-15
    - Cadence: 5 minutes
    - STATION_101: Stuck temperature sensor for 36 hours
    - STATION_102: Backward clock rollback
    - STATION_103: Hardware fault code spikes (-40C)
    - STATION_104: Clean control station
    """
    os.makedirs(os.path.join(dest_dir, "data"), exist_ok=True)
    dates = pd.date_range("2026-07-01 00:00", "2026-07-10 23:55", freq="5min")
    n = len(dates)

    meta_df = pd.DataFrame([
        {"station_id": f"STATION_10{i}", "name": f"Station 10{i}", "lat": 40.0 + i*0.1, "lon": -105.0, "elevation_m": 1500, "logger_interval_min": 5}
        for i in range(1, 5)
    ])
    meta_df.to_csv(os.path.join(dest_dir, "stations.csv"), index=False)

    for i in range(1, 5):
        st_id = f"STATION_10{i}"
        time_hours = np.array([(d - dates[0]).total_seconds() / 3600.0 for d in dates])
        temp = 20.0 + 6.0 * np.sin(2 * np.pi * (time_hours - 6) / 24.0) + np.random.normal(0, 0.2, n)
        
        # Add realistic diurnal noise to prevent artificial constant freeze
        rh = np.clip(55.0 - 2.0 * np.sin(2 * np.pi * (time_hours - 6) / 24.0) + np.random.normal(0, 0.5, n), 20.0, 90.0)
        pres = 850.0 + 2.0 * np.cos(2 * np.pi * time_hours / 24.0) + np.random.normal(0, 0.2, n)
        wind = np.clip(10.0 + 3.0 * np.sin(2 * np.pi * time_hours / 24.0) + np.random.normal(0, 0.5, n), 0.5, 30.0)
        
        df = pd.DataFrame({
            "timestamp_utc": dates.strftime("%Y-%m-%d %H:%M"),
            "temp_c": np.round(temp, 1),
            "rh_pct": np.round(rh, 1),
            "pressure_hpa": np.round(pres, 1),
            "wind_kmh": np.round(wind, 1),
            "wind_dir_deg": [90] * n,
            "rain_mm": [0.0] * n,
            "ghi_wm2": [200] * n
        })

        # Plant specific faults
        if st_id == "STATION_101":
            # Stuck temperature sensor from row 200 to 700 (500 steps * 5min = ~41 hours)
            df.loc[200:700, "temp_c"] = 18.2
        elif st_id == "STATION_102":
            # Backward jump: row 400 jumps back 3 hours
            orig_ts = pd.to_datetime(df.loc[400, "timestamp_utc"])
            rolled_ts = orig_ts - timedelta(hours=3)
            df.loc[400, "timestamp_utc"] = rolled_ts.strftime("%Y-%m-%d %H:%M")
        elif st_id == "STATION_103":
            # Hardware fault code spikes
            df.loc[150, "temp_c"] = -40.0
            df.loc[450, "temp_c"] = 85.0

        df.to_csv(os.path.join(dest_dir, "data", f"{st_id}.csv"), index=False)


def create_synthetic_schema_variation_pack(dest_dir: str):
    """
    Synthetic Pack 3: Schema variations & missing optional files.
    - No stations.csv, no GPS folder, no maintenance log
    - Column aliases: Date_Time, Temperature, Barometer, RH
    - Sampling interval: 30 minutes
    """
    os.makedirs(os.path.join(dest_dir, "data"), exist_ok=True)
    dates = pd.date_range("2026-08-01 00:00", "2026-08-05 23:30", freq="30min")
    n = len(dates)

    df = pd.DataFrame({
        "Date_Time": dates.strftime("%Y/%m/%d %H:%M"),
        "Temperature": np.round(22.0 + np.random.normal(0, 1.0, n), 1),
        "RH": [55.0] * n,
        "Barometer": [840.0] * n,
        "Wind_Speed": [15.0] * n
    })
    df.to_csv(os.path.join(dest_dir, "data", "NorthMtn_Sensor99.csv"), index=False)


def test_generalization_clean_pack(tmp_path):
    pack_dir = str(tmp_path / "clean_pack")
    create_synthetic_clean_pack(pack_dir)

    out_dir = str(tmp_path / "out_clean")
    res = run_pipeline(data_pack_dir=pack_dir, output_dir=out_dir)

    # Clean dataset should have 0 exclusion flags!
    exclude_flags = [f for f in res.flags if f.action == "exclude"]
    assert len(exclude_flags) == 0, f"Expected 0 exclude flags on clean dataset, got: {exclude_flags}"
    assert len(res.datapack.metadata) == 3


def test_generalization_multi_fault_pack(tmp_path):
    pack_dir = str(tmp_path / "fault_pack")
    create_synthetic_multi_fault_pack(pack_dir)

    out_dir = str(tmp_path / "out_fault")
    res = run_pipeline(data_pack_dir=pack_dir, output_dir=out_dir)

    # Should detect stuck sensor on STATION_101
    stuck_flags = [f for f in res.flags if f.station_id == "STATION_101" and f.issue == "stuck sensor"]
    assert len(stuck_flags) >= 1

    # Should detect clock rollback on STATION_102
    rollback_flags = [f for f in res.flags if f.station_id == "STATION_102" and "rollback" in f.issue]
    assert len(rollback_flags) >= 1

    # Should detect hardware spikes on STATION_103
    spike_flags = [f for f in res.flags if f.station_id == "STATION_103" and "hardware error" in f.issue]
    assert len(spike_flags) >= 1

    # Control station STATION_104 should have ZERO flags
    st104_flags = [f for f in res.flags if f.station_id == "STATION_104"]
    assert len(st104_flags) == 0


def test_generalization_schema_variation_pack(tmp_path):
    pack_dir = str(tmp_path / "schema_var_pack")
    create_synthetic_schema_variation_pack(pack_dir)

    out_dir = str(tmp_path / "out_schema_var")
    # Should run smoothly without stations.csv or gps
    res = run_pipeline(data_pack_dir=pack_dir, output_dir=out_dir)
    assert len(res.datapack.weather_data) == 1
    assert "NorthMtn_Sensor99" in res.datapack.weather_data
    assert os.path.exists(res.flags_csv_path)
