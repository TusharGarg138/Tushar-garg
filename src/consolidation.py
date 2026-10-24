"""
Flag consolidation, conflict resolution, and deterministic serialization.
"""

from typing import List, Dict, Any
from src.models import QualityFlag


def consolidate_flags(flags: List[QualityFlag]) -> List[QualityFlag]:
    """
    Consolidate overlapping flags, deduplicate redundant alerts,
    and enforce action precedence rules.
    """
    if not flags:
        return []

    # Filter out empty or duplicate flags
    unique_map: Dict[str, QualityFlag] = {}
    
    for flag in flags:
        key = f"{flag.station_id}|{flag.channel}|{flag.start_utc}|{flag.end_utc}|{flag.issue}"
        if key not in unique_map:
            unique_map[key] = flag
        else:
            existing = unique_map[key]
            if flag.severity == "critical" and existing.severity != "critical":
                unique_map[key] = flag
            elif flag.confidence > existing.confidence:
                unique_map[key] = flag

    consolidated = list(unique_map.values())

    # Suppression Rule 1:
    # If a 'hardware error code spike' exists for (station, channel, timestamp),
    # suppress generic 'value out of bounds' for that exact same timestamp
    hardware_spike_keys = {
        (f.station_id, f.channel, f.start_utc)
        for f in consolidated
        if "hardware error" in f.issue.lower()
    }

    # Suppression Rule 2:
    # If a 'duplicate transmission block' exists, suppress generic 'duplicate records'
    # for the same window
    dup_block_keys = {
        (f.station_id, f.start_utc, f.end_utc)
        for f in consolidated
        if "duplicate transmission block" in f.issue.lower()
    }

    # Suppression Rule 3:
    # If an entire station period is excluded on channel='all',
    # suppress redundant single-channel flags inside that exact window
    all_exclusions = [
        f for f in consolidated
        if f.channel == "all" and f.action == "exclude"
    ]
    
    filtered = []
    for f in consolidated:
        # Check rule 1
        if "out of bounds" in f.issue.lower() and (f.station_id, f.channel, f.start_utc) in hardware_spike_keys:
            continue

        # Check rule 2
        if f.issue == "duplicate records" and (f.station_id, f.start_utc, f.end_utc) in dup_block_keys:
            continue

        # Check rule 3
        if f.channel != "all":
            covered = False
            for ex in all_exclusions:
                if ex.station_id == f.station_id and ex.start_utc <= f.start_utc and ex.end_utc >= f.end_utc:
                    covered = True
                    break
            if covered:
                continue

        filtered.append(f)

    # Deterministic sort
    filtered.sort(key=lambda x: (x.station_id, x.start_utc, x.channel, x.issue))
    return filtered
