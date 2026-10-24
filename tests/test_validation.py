"""
Tests for schema validation, column aliasing, and sampling interval inference.
"""

import pytest
import pandas as pd
from src.validation import (
    normalize_column_names,
    infer_sampling_interval_minutes,
    ValidationError
)


def test_normalize_column_names_standard():
    df = pd.DataFrame(columns=["timestamp_utc", "temp_c", "rh_pct", "pressure_hpa"])
    norm_df, mapping = normalize_column_names(df)
    assert "timestamp_utc" in norm_df.columns
    assert "temp_c" in norm_df.columns


def test_normalize_column_names_aliases():
    df = pd.DataFrame(columns=["Date_Time", "Temperature", "RH", "Barometer", "Rainfall"])
    norm_df, mapping = normalize_column_names(df)
    assert "timestamp_utc" in norm_df.columns
    assert "temp_c" in norm_df.columns
    assert "rh_pct" in norm_df.columns
    assert "pressure_hpa" in norm_df.columns
    assert "rain_mm" in norm_df.columns


def test_infer_sampling_interval_10min():
    dates = pd.date_range("2025-01-01 00:00", periods=50, freq="10min")
    s = pd.Series(dates)
    assert infer_sampling_interval_minutes(s) == 10


def test_infer_sampling_interval_5min():
    dates = pd.date_range("2025-01-01 00:00", periods=50, freq="5min")
    s = pd.Series(dates)
    assert infer_sampling_interval_minutes(s) == 5


def test_infer_sampling_interval_15min():
    dates = pd.date_range("2025-01-01 00:00", periods=50, freq="15min")
    s = pd.Series(dates)
    assert infer_sampling_interval_minutes(s) == 15


def test_infer_sampling_interval_too_few_records():
    dates = pd.date_range("2025-01-01 00:00", periods=3, freq="10min")
    s = pd.Series(dates)
    assert infer_sampling_interval_minutes(s) is None
