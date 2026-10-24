"""
Unit tests for data-quality detectors and false-positive controls.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.detectors import (
    detect_duplicates_and_non_monotonic,
    detect_data_gaps,
    detect_physical_bounds,
    detect_stuck_sensors,
    detect_spikes_and_hardware_codes,
    detect_rain_clog_and_dump
)
from src.models import MaintenanceEvent


def test_detect_hardware_error_codes():
    df = pd.DataFrame({
        "timestamp_utc": ["2025-03-01 10:00", "2025-03-01 10:10", "2025-03-01 10:20"],
        "temp_c": [12.0, -40.0, 12.5]
    })
    df["dt"] = pd.to_datetime(df["timestamp_utc"])
    flags = detect_spikes_and_hardware_codes("S01", df)
    assert len(flags) == 1
    assert flags[0].channel == "temp_c"
    assert flags[0].action == "exclude"
    assert "-40.0" in flags[0].note


def test_detect_stuck_sensor():
    # 200 consecutive identical temperature readings at 10-min interval = ~33 hours
    dates = pd.date_range("2025-03-01 00:00", periods=200, freq="10min")
    df = pd.DataFrame({
        "timestamp_utc": dates.strftime("%Y-%m-%d %H:%M"),
        "temp_c": [5.5] * 200,
        "wind_kmh": [10.0] * 200
    })
    df["dt"] = pd.to_datetime(df["timestamp_utc"])
    flags = detect_stuck_sensors("S01", df, min_stuck_hours=24.0)
    assert any(f.channel == "temp_c" and f.issue == "stuck sensor" for f in flags)


def test_false_positive_control_zero_rain_not_stuck():
    # 3 days of zero rain in dry sunny weather should NEVER be flagged as a stuck sensor!
    dates = pd.date_range("2025-03-01 00:00", periods=432, freq="10min")
    df = pd.DataFrame({
        "timestamp_utc": dates.strftime("%Y-%m-%d %H:%M"),
        "rain_mm": [0.0] * 432
    })
    df["dt"] = pd.to_datetime(df["timestamp_utc"])
    flags = detect_stuck_sensors("S01", df, min_stuck_hours=24.0)
    # Ensure rain_mm is not flagged
    assert not any(f.channel == "rain_mm" for f in flags)


def test_detect_physical_bounds_humidity():
    df = pd.DataFrame({
        "timestamp_utc": ["2025-03-01 10:00", "2025-03-01 10:10"],
        "rh_pct": [95.0, 104.5]
    })
    df["dt"] = pd.to_datetime(df["timestamp_utc"])
    flags = detect_physical_bounds("S01", df)
    assert len(flags) == 1
    assert flags[0].channel == "rh_pct"
    assert flags[0].action == "exclude"


def test_detect_data_gap():
    # 24-hour transmission gap
    dates1 = pd.date_range("2025-03-01 00:00", periods=10, freq="10min")
    dates2 = pd.date_range("2025-03-02 01:00", periods=10, freq="10min")
    all_dates = dates1.append(dates2)
    df = pd.DataFrame({
        "timestamp_utc": all_dates.strftime("%Y-%m-%d %H:%M")
    })
    df["dt"] = pd.to_datetime(df["timestamp_utc"])
    flags = detect_data_gaps("S01", df, expected_interval_min=10)
    assert len(flags) == 1
    assert flags[0].issue == "data gap"
    assert flags[0].action == "exclude"


def test_detect_clock_rollback():
    df = pd.DataFrame({
        "timestamp_utc": [
            "2025-03-01 14:00",
            "2025-03-01 14:10",
            "2025-03-01 10:10", # jumped backward!
            "2025-03-01 10:20"
        ],
        "temp_c": [15.0, 15.5, 12.0, 12.2]
    })
    df["dt"] = pd.to_datetime(df["timestamp_utc"])
    flags = detect_duplicates_and_non_monotonic("S01", df)
    assert any(f.issue == "clock rollback / duplicate interval" for f in flags)


def test_detect_rain_clog_and_flush():
    dates = pd.date_range("2025-04-01 00:00", periods=20, freq="10min")
    df_st = pd.DataFrame({
        "timestamp_utc": dates.strftime("%Y-%m-%d %H:%M"),
        "rain_mm": [0.0]*10 + [11.0, 11.2] + [0.0]*8
    })
    df_st["dt"] = pd.to_datetime(df_st["timestamp_utc"])
    
    # Network station with 0 mm during dump
    df_net = pd.DataFrame({
        "timestamp_utc": dates.strftime("%Y-%m-%d %H:%M"),
        "rain_mm": [0.0]*20
    })
    df_net["dt"] = pd.to_datetime(df_net["timestamp_utc"])
    
    ev = [MaintenanceEvent(date_str="2025-04-01", station_id="S04", note="Cleaned leaves from funnel")]
    flags = detect_rain_clog_and_dump("S04", df_st, {"S02": df_net}, ev)
    assert any("flush dump" in f.issue for f in flags)
    assert any(f.action == "exclude" for f in flags)
