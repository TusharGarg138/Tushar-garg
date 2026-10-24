"""
Utility functions for timestamp formatting, NMEA parsing, and flag serialization.
"""

import csv
import io
import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from src.models import QualityFlag


def format_utc_timestamp(dt: datetime) -> str:
    """Format datetime to required 'YYYY-MM-DD HH:MM' format."""
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_timestamp_flexible(ts_str: Any) -> Optional[datetime]:
    """Parse a timestamp string in multiple common formats to datetime."""
    if ts_str is None:
        return None
    s = str(ts_str).strip()
    if not s or s.lower() in ("nan", "null", "none", "na", "n/a"):
        return None

    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Try pandas parsing if needed
    try:
        import pandas as pd
        pdt = pd.to_datetime(s)
        if not pd.isna(pdt):
            return pdt.to_pydatetime()
    except Exception:
        pass
    return None


def verify_nmea_checksum(sentence: str) -> bool:
    """
    Verify NMEA 0183 sentence checksum.
    The checksum is XOR of all characters between '$' and '*' (exclusive).
    """
    s = sentence.strip()
    if not s or "*" not in s:
        return False
    parts = s.split("*")
    if len(parts) != 2:
        return False
    body, expected_chk_str = parts[0], parts[1][:2]
    if body.startswith("$"):
        body = body[1:]
    
    calculated_chk = 0
    for char in body:
        calculated_chk ^= ord(char)
    
    try:
        expected_chk = int(expected_chk_str, 16)
        return calculated_chk == expected_chk
    except ValueError:
        return False


def parse_nmea_coordinates(lat_str: str, lat_dir: str, lon_str: str, lon_dir: str) -> Tuple[Optional[float], Optional[float]]:
    """Convert NMEA format coordinates (ddmm.mmmm) to signed decimal degrees."""
    lat = None
    lon = None
    try:
        if lat_str and lat_dir and len(lat_str) >= 4:
            # First 2 digits are degrees
            deg = float(lat_str[:2])
            minutes = float(lat_str[2:])
            lat = deg + (minutes / 60.0)
            if lat_dir.upper() == "S":
                lat = -lat
        
        if lon_str and lon_dir and len(lon_str) >= 5:
            # First 3 digits are degrees
            deg = float(lon_str[:3])
            minutes = float(lon_str[3:])
            lon = deg + (minutes / 60.0)
            if lon_dir.upper() == "W":
                lon = -lon
    except (ValueError, IndexError):
        pass
    return lat, lon


def write_flags_csv(flags: List[QualityFlag], output_path: str) -> None:
    """
    Write flags to CSV with exact schema and deterministic sorting.
    Schema: station_id,channel,start_utc,end_utc,issue,action,note
    """
    # Deterministic sort
    sorted_flags = sorted(
        flags,
        key=lambda f: (f.station_id, f.start_utc, f.channel, f.issue)
    )
    
    fieldnames = [
        "station_id",
        "channel",
        "start_utc",
        "end_utc",
        "issue",
        "action",
        "note"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for flag in sorted_flags:
            # Ensure no accidental newlines in notes
            row = flag.to_csv_dict()
            row["note"] = row["note"].replace("\n", " ").replace("\r", " ").strip()
            row["issue"] = row["issue"].replace("\n", " ").replace("\r", " ").strip()
            writer.writerow(row)
