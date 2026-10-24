"""
Data loader and dynamic file discovery for weather station data packs.
"""

import os
import glob
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.models import StationMetadata, MaintenanceEvent, GPSRecord
from src.validation import normalize_column_names, ValidationError
from src.utils import verify_nmea_checksum, parse_nmea_coordinates


class DataPack:
    """Encapsulates all loaded data and metadata for a weather network."""
    def __init__(self, pack_dir: str):
        self.pack_dir = os.path.abspath(pack_dir)
        self.metadata: Dict[str, StationMetadata] = {}
        self.weather_data: Dict[str, pd.DataFrame] = {}
        self.gps_records: Dict[str, List[GPSRecord]] = {}
        self.maintenance_events: List[MaintenanceEvent] = []
        self.warnings: List[str] = []


def discover_and_load_datapack(pack_dir: str) -> DataPack:
    """
    Dynamically discover and load weather data pack files.
    Works with variations in folder structure, station IDs, and optional files.
    """
    if not os.path.exists(pack_dir):
        raise FileNotFoundError(f"Data pack directory not found: {pack_dir}")
    if not os.path.isdir(pack_dir):
        raise NotADirectoryError(f"Provided path is not a directory: {pack_dir}")

    pack = DataPack(pack_dir)

    # 1. Discover stations metadata
    stations_file = None
    for candidate in ["stations.csv", "metadata.csv", "station_list.csv"]:
        path = os.path.join(pack.pack_dir, candidate)
        if os.path.exists(path):
            stations_file = path
            break
            
    if stations_file:
        pack.metadata = load_stations_metadata(stations_file)
    else:
        pack.warnings.append("No stations.csv found. Station metadata will be inferred from data files.")

    # 2. Discover weather CSV files
    # Check data/ subdirectory first, then root directory
    weather_files = glob.glob(os.path.join(pack.pack_dir, "data", "*.csv"))
    if not weather_files:
        weather_files = [
            f for f in glob.glob(os.path.join(pack.pack_dir, "*.csv"))
            if os.path.basename(f).lower() not in ["stations.csv", "metadata.csv", "station_list.csv", "flags.csv"]
        ]
        
    if not weather_files:
        raise ValidationError(f"No weather CSV data files found in {pack_dir} or {os.path.join(pack_dir, 'data')}")

    for file_path in sorted(weather_files):
        station_id = os.path.splitext(os.path.basename(file_path))[0]
        # Clean station ID if needed
        df = load_weather_csv(file_path, station_id)
        if df is not None and not df.empty:
            pack.weather_data[station_id] = df
            # Ensure station exists in metadata
            if station_id not in pack.metadata:
                pack.metadata[station_id] = StationMetadata(station_id=station_id, name=station_id)

    # 3. Discover GPS NMEA files (optional)
    gps_files = glob.glob(os.path.join(pack.pack_dir, "gps", "*.nmea"))
    if not gps_files:
        gps_files = glob.glob(os.path.join(pack.pack_dir, "*.nmea"))

    for file_path in sorted(gps_files):
        station_id = os.path.splitext(os.path.basename(file_path))[0]
        records = load_gps_file(file_path)
        if records:
            pack.gps_records[station_id] = records

    # 4. Discover maintenance log (optional)
    log_candidates = [
        "maintenance_log.md",
        "maintenance.md",
        "maintenance_log.txt",
        "maintenance.txt",
        "notes.md",
        "notes.txt"
    ]
    for candidate in log_candidates:
        path = os.path.join(pack.pack_dir, candidate)
        if os.path.exists(path):
            pack.maintenance_events = load_maintenance_log(path)
            break

    return pack


def load_stations_metadata(file_path: str) -> Dict[str, StationMetadata]:
    """Parse stations.csv into StationMetadata objects."""
    metadata = {}
    try:
        df = pd.read_csv(file_path)
        # Normalize column names
        df.columns = [c.strip().lower() for c in df.columns]
        id_col = next((c for c in df.columns if "id" in c or "station" in c), None)
        if not id_col:
            id_col = df.columns[0]
            
        for _, row in df.iterrows():
            st_id = str(row[id_col]).strip()
            name = str(row.get("name", st_id)).strip()
            lat = float(row.get("lat", row.get("latitude", 0.0)))
            lon = float(row.get("lon", row.get("longitude", 0.0)))
            elevation = float(row.get("elevation_m", row.get("elevation", 0.0)))
            installed = str(row.get("installed", row.get("install_date", ""))).strip()
            interval = int(row.get("logger_interval_min", row.get("interval_min", 10)))
            
            metadata[st_id] = StationMetadata(
                station_id=st_id,
                name=name,
                lat=lat,
                lon=lon,
                elevation_m=elevation,
                installed=installed,
                logger_interval_min=interval
            )
    except Exception as e:
        # If parsing stations metadata fails, continue with empty metadata
        pass
    return metadata


def load_weather_csv(file_path: str, station_id: str) -> Optional[pd.DataFrame]:
    """Load and normalize a station weather CSV file."""
    try:
        df = pd.read_csv(
            file_path,
            na_values=["", "NA", "N/A", "null", "None", "-9999", "-999", "nan", "NaN"]
        )
        if df.empty:
            return df
            
        df, col_mapping = normalize_column_names(df)
        
        if "timestamp_utc" not in df.columns:
            raise ValidationError(
                f"Station file {file_path} is missing a timestamp column. "
                f"Found columns: {list(df.columns)}"
            )
            
        # Parse timestamp to datetime
        df["dt"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")
        df["station_id"] = station_id
        return df
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Error reading CSV file {file_path}: {e}")


def load_gps_file(file_path: str) -> List[GPSRecord]:
    """Parse NMEA sentences from logger GPS log file."""
    records = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = line_str.split(",")
                if len(parts) < 2:
                    continue
                    
                logger_ts_str = parts[0].strip()
                nmea_sentence = ",".join(parts[1:])
                nmea_type = parts[1].strip()
                
                # Checksum check
                valid_checksum = verify_nmea_checksum(nmea_sentence)
                
                try:
                    logger_dt = datetime.strptime(logger_ts_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        logger_dt = datetime.strptime(logger_ts_str, "%Y-%m-%d %H:%M")
                    except ValueError:
                        continue
                        
                gps_dt = None
                lat = None
                lon = None
                status = None
                altitude_m = None
                diff_sec = None
                
                # Parse GPRMC: logger_ts,$GPRMC,time,status,lat,N/S,lon,E/W,speed,track,date,...
                if nmea_type == "$GPRMC" and len(parts) >= 11:
                    utc_time_str = parts[2].strip()
                    status = parts[3].strip()
                    lat_str, lat_dir = parts[4].strip(), parts[5].strip()
                    lon_str, lon_dir = parts[6].strip(), parts[7].strip()
                    utc_date_str = parts[10].strip()
                    
                    if status == "A" and len(utc_time_str) >= 6 and len(utc_date_str) == 6:
                        try:
                            day = int(utc_date_str[0:2])
                            mon = int(utc_date_str[2:4])
                            yr = 2000 + int(utc_date_str[4:6])
                            hr = int(utc_time_str[0:2])
                            mn = int(utc_time_str[2:4])
                            sc = int(utc_time_str[4:6])
                            gps_dt = datetime(yr, mon, day, hr, mn, sc)
                            diff_sec = (logger_dt - gps_dt).total_seconds()
                        except ValueError:
                            pass
                            
                    lat, lon = parse_nmea_coordinates(lat_str, lat_dir, lon_str, lon_dir)

                # Parse GPGGA: logger_ts,$GPGGA,time,lat,N/S,lon,E/W,fix,sats,hdop,alt,M,...
                elif nmea_type == "$GPGGA" and len(parts) >= 10:
                    lat_str, lat_dir = parts[3].strip(), parts[4].strip()
                    lon_str, lon_dir = parts[5].strip(), parts[6].strip()
                    status = parts[7].strip() # fix quality
                    lat, lon = parse_nmea_coordinates(lat_str, lat_dir, lon_str, lon_dir)
                    try:
                        if len(parts) >= 11 and parts[10].strip() == "M":
                            altitude_m = float(parts[9].strip())
                    except ValueError:
                        pass
                        
                record = GPSRecord(
                    logger_time=logger_dt,
                    sentence_type=nmea_type,
                    gps_time=gps_dt,
                    lat=lat,
                    lon=lon,
                    altitude_m=altitude_m,
                    status=status,
                    diff_sec=diff_sec,
                    is_valid_checksum=valid_checksum
                )
                records.append(record)
    except Exception:
        pass
    return records


def load_maintenance_log(file_path: str) -> List[MaintenanceEvent]:
    """Parse maintenance log entries from markdown or text file."""
    events = []
    # Match patterns like: 2025-03-02  S01  Hiked up after the snow...
    date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+([A-Za-z0-9_-]+)\s+(.+)$")
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                match = date_pattern.match(line_str)
                if match:
                    d_str, st_id, note = match.groups()
                    events.append(MaintenanceEvent(
                        date_str=d_str,
                        station_id=st_id.strip(),
                        note=note.strip()
                    ))
    except Exception:
        pass
    return events
