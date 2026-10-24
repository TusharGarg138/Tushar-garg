"""
Schema validation, column aliasing, and sampling interval inference.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


STANDARD_COLUMNS = {
    "timestamp_utc": ["timestamp_utc", "timestamp", "time", "datetime", "date_time", "utc_time"],
    "temp_c": ["temp_c", "temp", "temperature", "temperature_c", "air_temp", "air_temperature"],
    "rh_pct": ["rh_pct", "rh", "humidity", "relative_humidity", "rel_humidity", "humidity_pct"],
    "pressure_hpa": ["pressure_hpa", "pressure", "baro", "barometer", "pres_hpa", "station_pressure"],
    "wind_kmh": ["wind_kmh", "wind", "wind_speed", "speed_kmh", "wind_speed_kmh"],
    "wind_dir_deg": ["wind_dir_deg", "wind_dir", "wind_direction", "direction_deg", "dir_deg"],
    "rain_mm": ["rain_mm", "rain", "precipitation", "precip_mm", "rainfall"],
    "ghi_wm2": ["ghi_wm2", "ghi", "solar", "radiation", "solar_wm2", "solar_radiation"],
}

PHYSICAL_LIMITS = {
    "temp_c": (-50.0, 60.0),       # °C
    "rh_pct": (0.0, 100.0),        # %
    "pressure_hpa": (600.0, 1100.0), # hPa (for Colorado 1400-3000m, 680-870 hPa typical)
    "wind_kmh": (0.0, 150.0),      # km/h
    "wind_dir_deg": (0.0, 360.0),  # degrees
    "rain_mm": (0.0, 50.0),        # mm in single interval
    "ghi_wm2": (0.0, 1500.0),      # W/m²
}


class ValidationError(Exception):
    """Raised when data fails basic schema validation requirements."""
    pass


def normalize_column_names(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Map DataFrame column names to standard canonical names based on known aliases.
    Case-insensitive and whitespace-stripped.
    """
    col_mapping = {}
    normalized_df = df.copy()
    
    clean_cols = {col.strip().lower(): col for col in df.columns}
    
    for canon, aliases in STANDARD_COLUMNS.items():
        found = False
        for alias in aliases:
            if alias in clean_cols:
                original_col = clean_cols[alias]
                col_mapping[original_col] = canon
                found = True
                break
                
    normalized_df = normalized_df.rename(columns=col_mapping)
    return normalized_df, col_mapping


def infer_sampling_interval_minutes(dt_series: pd.Series) -> Optional[int]:
    """
    Robustly infer the expected logging cadence from a timestamp series.
    Returns the cadence in minutes, or None if cadence cannot be reliably established.
    """
    if len(dt_series) < 5:
        return None
    
    # Calculate positive time differences
    diffs = dt_series.diff().dropna()
    positive_diffs = diffs[diffs > pd.Timedelta(seconds=0)]
    if positive_diffs.empty:
        return None
    
    # Convert to minutes
    diff_minutes = positive_diffs.dt.total_seconds() / 60.0
    
    # Mode of the diffs
    counts = diff_minutes.value_counts()
    if counts.empty:
        return None
    
    most_common_diff = counts.index[0]
    frequency_share = counts.iloc[0] / len(diff_minutes)
    
    # If the most common interval accounts for at least 40% of observations
    if frequency_share >= 0.40 and most_common_diff > 0:
        return int(round(most_common_diff))
    
    # Fallback: check median
    med = positive_diffs.median().total_seconds() / 60.0
    if med > 0:
        return int(round(med))
        
    return None
