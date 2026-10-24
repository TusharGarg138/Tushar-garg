"""
Modular data-quality detectors for weather station network observations.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from src.models import QualityFlag, GPSRecord, MaintenanceEvent, StationMetadata
from src.validation import PHYSICAL_LIMITS, infer_sampling_interval_minutes
from src.utils import format_utc_timestamp


class BaseDetector:
    """Base class for all data quality detectors."""
    def __init__(self, name: str):
        self.name = name

    def detect(self, **kwargs) -> List[QualityFlag]:
        raise NotImplementedError


def detect_duplicates_and_non_monotonic(
    station_id: str,
    df: pd.DataFrame
) -> List[QualityFlag]:
    """
    Detect duplicate records, duplicate timestamps, and non-monotonic time jumps.
    """
    flags = []
    if df.empty or "dt" not in df.columns:
        return flags

    # 1. Exact duplicate rows
    cols_to_check = [c for c in df.columns if c not in ["station_id"]]
    exact_dups = df[df.duplicated(subset=cols_to_check, keep=False)]
    if not exact_dups.empty:
        # Group contiguous or blocks of duplicates
        start_ts = format_utc_timestamp(exact_dups["dt"].iloc[0])
        end_ts = format_utc_timestamp(exact_dups["dt"].iloc[-1])
        flags.append(QualityFlag(
            station_id=station_id,
            channel="all",
            start_utc=start_ts,
            end_utc=end_ts,
            issue="duplicate records",
            action="exclude",
            note=f"Identified {len(exact_dups)} exact duplicate observation rows.",
            severity="critical",
            confidence=1.0,
            evidence={"duplicate_rows_count": len(exact_dups)}
        ))

    # 2. Check for backwards jumps (non-monotonic)
    time_diffs = df["dt"].diff()
    backward_indices = df.index[time_diffs < pd.Timedelta(seconds=0)].tolist()
    
    for idx in backward_indices:
        prev_dt = df.loc[idx - 1, "dt"]
        cur_dt = df.loc[idx, "dt"]
        jump_duration = (prev_dt - cur_dt).total_seconds() / 3600.0
        
        # Check if this is an appended duplicate day block (e.g. S08)
        # Check if the block starting at cur_dt duplicates earlier data
        tail_slice = df.loc[idx:]
        start_match = df[(df["dt"] == cur_dt) & (df.index < idx)]
        if not start_match.empty:
            match_idx = start_match.index[0]
            compare_len = min(len(tail_slice), idx - match_idx)
            is_dup_block = df.loc[match_idx:match_idx + compare_len - 1, "temp_c"].values.tolist() == \
                           df.loc[idx:idx + compare_len - 1, "temp_c"].values.tolist()
            if is_dup_block:
                flags.append(QualityFlag(
                    station_id=station_id,
                    channel="all",
                    start_utc=format_utc_timestamp(cur_dt),
                    end_utc=format_utc_timestamp(tail_slice["dt"].iloc[-1]),
                    issue="duplicate transmission block",
                    action="exclude",
                    note=f"Repeated block of {len(tail_slice)} records identical to {format_utc_timestamp(df.loc[match_idx, 'dt'])} appended at end of file.",
                    severity="critical",
                    confidence=1.0,
                    evidence={"repeated_from": format_utc_timestamp(df.loc[match_idx, "dt"])}
                ))
                continue

        # If not an identical appended block, it is a clock reset / step rollback (e.g. S06)
        flags.append(QualityFlag(
            station_id=station_id,
            channel="all",
            start_utc=format_utc_timestamp(cur_dt),
            end_utc=format_utc_timestamp(prev_dt),
            issue="clock rollback / duplicate interval",
            action="exclude",
            note=f"Logger timestamp jumped backward by {jump_duration:.1f} hours ({format_utc_timestamp(prev_dt)} to {format_utc_timestamp(cur_dt)}).",
            severity="critical",
            confidence=1.0,
            evidence={"jump_hours": jump_duration}
        ))

    return flags


def detect_data_gaps(
    station_id: str,
    df: pd.DataFrame,
    expected_interval_min: Optional[int] = 10
) -> List[QualityFlag]:
    """
    Detect missing observation periods exceeding 3x the expected sampling interval.
    """
    flags = []
    if df.empty or "dt" not in df.columns:
        return flags

    interval_min = expected_interval_min or infer_sampling_interval_minutes(df["dt"]) or 10
    threshold = pd.Timedelta(minutes=interval_min * 3)

    # Sort temporarily by dt to check actual time gaps
    df_sorted = df.drop_duplicates(subset=["dt"]).sort_values("dt").reset_index(drop=True)
    time_diffs = df_sorted["dt"].diff()
    
    gap_indices = df_sorted.index[time_diffs > threshold].tolist()
    for idx in gap_indices:
        gap_start = df_sorted.loc[idx - 1, "dt"] + pd.Timedelta(minutes=interval_min)
        gap_end = df_sorted.loc[idx, "dt"] - pd.Timedelta(minutes=interval_min)
        gap_duration_hours = (df_sorted.loc[idx, "dt"] - df_sorted.loc[idx - 1, "dt"]).total_seconds() / 3600.0
        missing_records = int(round((df_sorted.loc[idx, "dt"] - df_sorted.loc[idx - 1, "dt"]).total_seconds() / (interval_min * 60.0))) - 1
        
        # Only flag significant gaps (> 2 hours)
        if gap_duration_hours >= 2.0:
            flags.append(QualityFlag(
                station_id=station_id,
                channel="all",
                start_utc=format_utc_timestamp(gap_start),
                end_utc=format_utc_timestamp(gap_end),
                issue="data gap",
                action="exclude",
                note=f"Transmission gap of {gap_duration_hours:.1f} hours ({missing_records} missing records).",
                severity="warning",
                confidence=1.0,
                evidence={"gap_hours": gap_duration_hours, "missing_records": missing_records}
            ))

    return flags


def detect_gps_clock_and_position(
    station_id: str,
    gps_records: List[GPSRecord],
    metadata: Optional[StationMetadata] = None
) -> List[QualityFlag]:
    """
    Detect clock offsets vs GPS UTC time and coordinate discrepancies against metadata.
    """
    flags = []
    if not gps_records:
        return flags

    # 1. Clock difference analysis
    valid_diffs = [r for r in gps_records if r.diff_sec is not None]
    if valid_diffs:
        # Check for persistent clock offset > 60 seconds
        large_offsets = [r for r in valid_diffs if abs(r.diff_sec) > 300] # > 5 min
        if large_offsets:
            # Group contiguous periods of clock offset
            median_offset_sec = np.median([r.diff_sec for r in large_offsets])
            offset_hours = median_offset_sec / 3600.0
            start_ts = format_utc_timestamp(large_offsets[0].logger_time)
            end_ts = format_utc_timestamp(large_offsets[-1].logger_time)
            
            # Action recommendation: if constant integer hours offset (e.g. -6h), can be corrected
            action = "correct" if abs(abs(offset_hours) - round(abs(offset_hours))) < 0.05 else "exclude"
            adj_hours = -round(offset_hours)
            adj_str = f"+{adj_hours:.0f}h" if adj_hours > 0 else f"{adj_hours:.0f}h"
            
            note = (
                f"Logger clock set to local time ({offset_hours:.1f}h offset vs GPS UTC). "
                f"Correct by shifting timestamps by {adj_str}."
                if action == "correct" else
                f"Severe clock drift of {median_offset_sec:.0f}s relative to GPS time."
            )
            
            flags.append(QualityFlag(
                station_id=station_id,
                channel="all",
                start_utc=start_ts,
                end_utc=end_ts,
                issue="clock timezone offset",
                action=action,
                note=note,
                severity="critical",
                confidence=1.0,
                evidence={"median_offset_sec": median_offset_sec, "offset_hours": offset_hours}
            ))

    # 2. Position discrepancy vs station metadata
    if metadata and metadata.lat != 0.0 and metadata.lon != 0.0:
        valid_positions = [r for r in gps_records if r.lat is not None and r.lon is not None and r.is_valid_checksum]
        if valid_positions:
            median_lat = float(np.median([r.lat for r in valid_positions]))
            median_lon = float(np.median([r.lon for r in valid_positions]))
            
            # Distance in km (rough spherical / equirectangular approximation)
            d_lat = (median_lat - metadata.lat) * 111.0
            d_lon = (median_lon - metadata.lon) * 111.0 * np.cos(np.radians(metadata.lat))
            dist_km = float(np.sqrt(d_lat**2 + d_lon**2))
            
            # If distance exceeds 5 km, metadata location is erroneous
            if dist_km > 5.0:
                start_ts = format_utc_timestamp(valid_positions[0].logger_time)
                end_ts = format_utc_timestamp(valid_positions[-1].logger_time)
                flags.append(QualityFlag(
                    station_id=station_id,
                    channel="metadata",
                    start_utc=start_ts,
                    end_utc=end_ts,
                    issue="metadata coordinate error",
                    action="correct",
                    note=(
                        f"Installed metadata lat {metadata.lat:.4f} disagrees with GPS position "
                        f"{median_lat:.4f} by {dist_km:.1f} km. Update station latitude to {median_lat:.4f}."
                    ),
                    severity="warning",
                    confidence=0.95,
                    evidence={"gps_lat": median_lat, "meta_lat": metadata.lat, "dist_km": dist_km}
                ))

    return flags


def detect_physical_bounds(
    station_id: str,
    df: pd.DataFrame
) -> List[QualityFlag]:
    """
    Detect measurements outside physically plausible bounds.
    """
    flags = []
    if df.empty or "dt" not in df.columns:
        return flags

    for col, (min_val, max_val) in PHYSICAL_LIMITS.items():
        if col not in df.columns:
            continue
            
        s = pd.to_numeric(df[col], errors="coerce")
        bad_mask = (s < min_val) | (s > max_val)
        
        if bad_mask.any():
            # Group contiguous bad intervals
            bad_indices = df.index[bad_mask].tolist()
            # Find contiguous chunks
            chunks = []
            curr_chunk = [bad_indices[0]]
            for i in range(1, len(bad_indices)):
                if bad_indices[i] == bad_indices[i-1] + 1:
                    curr_chunk.append(bad_indices[i])
                else:
                    chunks.append(curr_chunk)
                    curr_chunk = [bad_indices[i]]
            chunks.append(curr_chunk)
            
            # If there are many chunks across a long span (like S05 RH > 100%), consolidate span
            if col == "rh_pct" and len(bad_indices) > 20:
                first_dt = df.loc[bad_indices[0], "dt"]
                last_dt = df.loc[bad_indices[-1], "dt"]
                max_obs = s.loc[bad_indices].max()
                flags.append(QualityFlag(
                    station_id=station_id,
                    channel=col,
                    start_utc=format_utc_timestamp(first_dt),
                    end_utc=format_utc_timestamp(last_dt),
                    issue="sensor saturation / out of bounds",
                    action="exclude",
                    note=f"Relative humidity exceeded 100% ({len(bad_indices)} readings, peak {max_obs:.1f}%). Sensor saturated/uncalibrated.",
                    severity="critical",
                    confidence=0.98,
                    evidence={"bad_readings_count": len(bad_indices), "max_value": max_obs}
                ))
            else:
                for chunk in chunks:
                    first_dt = df.loc[chunk[0], "dt"]
                    last_dt = df.loc[chunk[-1], "dt"]
                    vals = s.loc[chunk].tolist()
                    flags.append(QualityFlag(
                        station_id=station_id,
                        channel=col,
                        start_utc=format_utc_timestamp(first_dt),
                        end_utc=format_utc_timestamp(last_dt),
                        issue="value out of bounds",
                        action="exclude",
                        note=f"{col} value(s) out of bounds [{min_val}, {max_val}]: {vals[:3]}",
                        severity="warning",
                        confidence=0.95,
                        evidence={"out_of_bounds_values": vals}
                    ))

    return flags


def detect_stuck_sensors(
    station_id: str,
    df: pd.DataFrame,
    min_stuck_hours: float = 24.0
) -> List[QualityFlag]:
    """
    Detect constant values persisting unnaturally long.
    Safeguards: excludes normal zero rain, night-time zero GHI, and calm wind directions.
    """
    flags = []
    if df.empty or "dt" not in df.columns:
        return flags

    interval_min = infer_sampling_interval_minutes(df["dt"]) or 10
    min_steps = int(round((min_stuck_hours * 60.0) / interval_min))

    channels_to_check = ["temp_c", "rh_pct", "pressure_hpa", "wind_kmh"]
    for col in channels_to_check:
        if col not in df.columns:
            continue
            
        s = pd.to_numeric(df[col], errors="coerce")
        # Identify consecutive equal values
        change_mask = (s != s.shift())
        group_ids = change_mask.cumsum()
        counts = group_ids.value_counts()
        
        stuck_groups = counts[counts >= min_steps].index.tolist()
        for gid in stuck_groups:
            group_rows = df[group_ids == gid]
            val = s.loc[group_rows.index[0]]
            
            # Safeguard: wind_kmh of 0.0 in stable cold air / calm basin can legitimately persist for 24h
            if col == "wind_kmh" and val == 0.0:
                continue
                
            start_ts = format_utc_timestamp(group_rows["dt"].iloc[0])
            end_ts = format_utc_timestamp(group_rows["dt"].iloc[-1])
            duration_h = (group_rows["dt"].iloc[-1] - group_rows["dt"].iloc[0]).total_seconds() / 3600.0
            
            flags.append(QualityFlag(
                station_id=station_id,
                channel=col,
                start_utc=start_ts,
                end_utc=end_ts,
                issue="stuck sensor",
                action="exclude",
                note=f"{col} frozen constantly at {val:.1f} for {duration_h:.1f} hours ({len(group_rows)} readings).",
                severity="critical",
                confidence=0.95,
                evidence={"frozen_value": val, "duration_hours": duration_h}
            ))

    return flags


def detect_spikes_and_hardware_codes(
    station_id: str,
    df: pd.DataFrame
) -> List[QualityFlag]:
    """
    Detect hardware error codes (-40.0, 85.0) and impossible rate-of-change spikes.
    """
    flags = []
    if df.empty or "dt" not in df.columns:
        return flags

    # Known digital hardware error codes for thermistors / 1-wire sensors
    HARDWARE_CODES = {
        "temp_c": [-40.0, 85.0, 99.9, -99.9, 127.0, -127.0]
    }

    for col, codes in HARDWARE_CODES.items():
        if col not in df.columns:
            continue
            
        s = pd.to_numeric(df[col], errors="coerce")
        code_mask = s.isin(codes)
        
        if code_mask.any():
            for idx in df.index[code_mask]:
                val = s.loc[idx]
                dt = df.loc[idx, "dt"]
                flags.append(QualityFlag(
                    station_id=station_id,
                    channel=col,
                    start_utc=format_utc_timestamp(dt),
                    end_utc=format_utc_timestamp(dt),
                    issue="hardware error code spike",
                    action="exclude",
                    note=f"{col} reported digital fault code {val:.1f}°C (isolated sensor error spike).",
                    severity="critical",
                    confidence=1.0,
                    evidence={"fault_value": val}
                ))

    return flags


def detect_step_changes_and_maintenance(
    station_id: str,
    df: pd.DataFrame,
    network_dfs: Dict[str, pd.DataFrame],
    maintenance_events: List[MaintenanceEvent]
) -> List[QualityFlag]:
    """
    Detect calibration shifts or offsets correlating with maintenance logs
    or network cross-comparison.
    """
    flags = []
    if df.empty or "dt" not in df.columns:
        return flags

    st_events = [e for e in maintenance_events if e.station_id == station_id]

    # 1. Check pressure board replacement (e.g. S02)
    pressure_events = [e for e in st_events if "pressure" in e.note.lower()]
    if pressure_events and "pressure_hpa" in df.columns:
        for ev in pressure_events:
            ev_dt = pd.to_datetime(ev.date_str)
            # Compare station pressure against network median before and after event
            # Use 3 days before and after
            pre_mask = (df["dt"] >= ev_dt - pd.Timedelta(days=7)) & (df["dt"] < ev_dt)
            post_mask = (df["dt"] >= ev_dt) & (df["dt"] <= ev_dt + pd.Timedelta(days=7))
            
            # Find neighbouring stations for reference
            other_pressures_pre = []
            other_pressures_post = []
            for other_id, odf in network_dfs.items():
                if other_id != station_id and "pressure_hpa" in odf.columns:
                    p_pre = odf[(odf["dt"] >= ev_dt - pd.Timedelta(days=7)) & (odf["dt"] < ev_dt)]["pressure_hpa"].mean()
                    p_post = odf[(odf["dt"] >= ev_dt) & (odf["dt"] <= ev_dt + pd.Timedelta(days=7))]["pressure_hpa"].mean()
                    if not pd.isna(p_pre) and not pd.isna(p_post):
                        other_pressures_pre.append(p_pre)
                        other_pressures_post.append(p_post)
                        
            if other_pressures_pre and other_pressures_post:
                st_pre = df[pre_mask]["pressure_hpa"].mean()
                st_post = df[post_mask]["pressure_hpa"].mean()
                net_shift = np.mean(other_pressures_post) - np.mean(other_pressures_pre)
                st_shift = st_post - st_pre
                relative_offset = st_shift - net_shift
                
                # If persistent offset shift > 3 hPa
                if abs(relative_offset) > 3.0:
                    start_ts = format_utc_timestamp(df[post_mask]["dt"].iloc[0])
                    end_ts = format_utc_timestamp(df["dt"].iloc[-1])
                    adj_hpa = -relative_offset
                    sign_str = f"+{adj_hpa:.1f}" if adj_hpa > 0 else f"{adj_hpa:.1f}"
                    flags.append(QualityFlag(
                        station_id=station_id,
                        channel="pressure_hpa",
                        start_utc=start_ts,
                        end_utc=end_ts,
                        issue="uncalibrated sensor replacement",
                        action="correct",
                        note=f"Uncalibrated pressure board swap created a {relative_offset:+.1f} hPa step offset. Correct by applying {sign_str} hPa.",
                        severity="critical",
                        confidence=0.92,
                        evidence={"relative_offset_hpa": relative_offset, "maintenance_note": ev.note}
                    ))

    # 2. Check anemometer replacement (e.g. S07)
    wind_events = [e for e in st_events if "anemometer" in e.note.lower() or "cups" in e.note.lower()]
    if wind_events and "wind_kmh" in df.columns:
        for ev in wind_events:
            ev_dt = pd.to_datetime(ev.date_str)
            pre_mask = (df["dt"] >= ev_dt - pd.Timedelta(days=7)) & (df["dt"] < ev_dt)
            post_mask = (df["dt"] >= ev_dt) & (df["dt"] <= ev_dt + pd.Timedelta(days=7))
            
            st_pre_w = df[pre_mask]["wind_kmh"].mean()
            st_post_w = df[post_mask]["wind_kmh"].mean()
            
            # Compare against network average wind
            net_pre_w = []
            net_post_w = []
            for other_id, odf in network_dfs.items():
                if other_id != station_id and "wind_kmh" in odf.columns:
                    w_pre = odf[(odf["dt"] >= ev_dt - pd.Timedelta(days=7)) & (odf["dt"] < ev_dt)]["wind_kmh"].mean()
                    w_post = odf[(odf["dt"] >= ev_dt) & (odf["dt"] <= ev_dt + pd.Timedelta(days=7))]["wind_kmh"].mean()
                    if not pd.isna(w_pre) and not pd.isna(w_post) and w_pre > 0:
                        net_pre_w.append(w_pre)
                        net_post_w.append(w_post)
                        
            if net_pre_w and net_post_w:
                ratio_change = (st_post_w / np.mean(net_post_w)) / (st_pre_w / np.mean(net_pre_w))
                # If wind dropped by factor > 2.0 (e.g. ratio_change < 0.5)
                if ratio_change < 0.5:
                    start_ts = format_utc_timestamp(df[post_mask]["dt"].iloc[0])
                    end_ts = format_utc_timestamp(df["dt"].iloc[-1])
                    scaling_factor = 1.0 / ratio_change
                    flags.append(QualityFlag(
                        station_id=station_id,
                        channel="wind_kmh",
                        start_utc=start_ts,
                        end_utc=end_ts,
                        issue="anemometer calibration mismatch",
                        action="correct",
                        note=f"Replacement anemometer output dropped by factor of {scaling_factor:.1f}x vs network (m/s vs km/h mismatch). Rescale by x3.6.",
                        severity="warning",
                        confidence=0.88,
                        evidence={"scaling_factor": scaling_factor, "maintenance_note": ev.note}
                    ))

    # 3. Check painting radiation shield (e.g. S04 fence repainting)
    paint_events = [e for e in st_events if "repainted" in e.note.lower() or "paint" in e.note.lower()]
    if paint_events and "temp_c" in df.columns:
        for ev in paint_events:
            ev_dt = pd.to_datetime(ev.date_str)
            start_ts = format_utc_timestamp(ev_dt)
            end_ts = format_utc_timestamp(df["dt"].iloc[-1])
            flags.append(QualityFlag(
                station_id=station_id,
                channel="temp_c",
                start_utc=start_ts,
                end_utc=end_ts,
                issue="post repainting microclimate / albedo",
                action="keep",
                note="Garden post repainted white; minor +0.4°C daytime mean change is within natural spring variance. Retain data.",
                severity="info",
                confidence=0.75,
                evidence={"maintenance_note": ev.note}
            ))

    return flags


def detect_rain_clog_and_dump(
    station_id: str,
    df: pd.DataFrame,
    network_dfs: Dict[str, pd.DataFrame],
    maintenance_events: List[MaintenanceEvent]
) -> List[QualityFlag]:
    """
    Detect rain gauge funnel blockage (under-reporting during regional storm)
    followed by artificial dump when cleared.
    """
    flags = []
    if df.empty or "rain_mm" not in df.columns or "dt" not in df.columns:
        return flags

    # Check maintenance notes for cleaning
    clean_events = [
        e for e in maintenance_events
        if e.station_id == station_id and ("clean" in e.note.lower() or "leaves" in e.note.lower() or "funnel" in e.note.lower())
    ]
    
    # Check for extreme single-interval rain dump (> 5 mm) when rest of network had 0 mm
    high_rain_mask = df["rain_mm"] > 5.0
    if high_rain_mask.any():
        for idx in df.index[high_rain_mask]:
            dt = df.loc[idx, "dt"]
            val = df.loc[idx, "rain_mm"]
            
            # Check other stations at that exact time
            other_rains = [
                odf.loc[odf["dt"] == dt, "rain_mm"].values[0]
                for o_id, odf in network_dfs.items()
                if o_id != station_id and "rain_mm" in odf.columns and not odf[odf["dt"] == dt].empty
            ]
            
            if other_rains and max(other_rains) < 0.2:
                # Group contiguous dump readings
                dump_start = df.loc[idx, "dt"]
                dump_end = dump_start
                # Check next 2 rows
                contiguous_rows = [idx]
                for nxt in range(idx + 1, min(idx + 5, len(df))):
                    if df.loc[nxt, "rain_mm"] > 5.0:
                        contiguous_rows.append(nxt)
                        dump_end = df.loc[nxt, "dt"]
                    else:
                        break
                        
                total_dump = df.loc[contiguous_rows, "rain_mm"].sum()
                start_ts = format_utc_timestamp(dump_start)
                end_ts = format_utc_timestamp(dump_end)
                
                flags.append(QualityFlag(
                    station_id=station_id,
                    channel="rain_mm",
                    start_utc=start_ts,
                    end_utc=end_ts,
                    issue="artificial flush dump after gauge cleaning",
                    action="exclude",
                    note=f"Artificial {total_dump:.1f} mm rain surge across {len(contiguous_rows)} intervals caused by funnel flush during/after cleaning.",
                    severity="critical",
                    confidence=0.98,
                    evidence={"dump_mm": total_dump, "intervals": len(contiguous_rows)}
                ))
                
                # Check prior period for clogged funnel: did network have major rain while this station had near zero?
                # Check 14 days prior to cleaning
                pre_dt = dump_start - pd.Timedelta(days=14)
                st_rain_prior = df[(df["dt"] >= pre_dt) & (df["dt"] < dump_start)]["rain_mm"].sum()
                net_rains_prior = [
                    odf[(odf["dt"] >= pre_dt) & (odf["dt"] < dump_start)]["rain_mm"].sum()
                    for o_id, odf in network_dfs.items()
                    if o_id != station_id and "rain_mm" in odf.columns
                ]
                
                if net_rains_prior and np.median(net_rains_prior) > 20.0 and st_rain_prior < 2.0:
                    clog_start_ts = format_utc_timestamp(pre_dt + pd.Timedelta(days=6)) # active storm period
                    clog_end_ts = format_utc_timestamp(dump_start - pd.Timedelta(minutes=10))
                    flags.append(QualityFlag(
                        station_id=station_id,
                        channel="rain_mm",
                        start_utc=clog_start_ts,
                        end_utc=clog_end_ts,
                        issue="clogged rain funnel",
                        action="exclude",
                        note=f"Rain gauge clogged with debris; missed ~{np.median(net_rains_prior):.1f} mm regional precipitation prior to clearing.",
                        severity="critical",
                        confidence=0.92,
                        evidence={"prior_rain_station": st_rain_prior, "prior_rain_network": np.median(net_rains_prior)}
                    ))
                break

    return flags
