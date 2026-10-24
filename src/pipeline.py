"""
End-to-end data quality analysis pipeline shared between CLI and UI.
"""

import os
import sys
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd

from src.models import QualityFlag, StationMetadata
from src.loader import discover_and_load_datapack, DataPack
from src.detectors import (
    detect_duplicates_and_non_monotonic,
    detect_data_gaps,
    detect_gps_clock_and_position,
    detect_physical_bounds,
    detect_stuck_sensors,
    detect_spikes_and_hardware_codes,
    detect_step_changes_and_maintenance,
    detect_rain_clog_and_dump
)
from src.consolidation import consolidate_flags
from src.scoring import score_stations_for_technician_visit, TechnicianRecommendation
from src.reporting import generate_coordinator_report
from src.utils import write_flags_csv


class PipelineResult:
    """Encapsulates all results from running the QA pipeline."""
    def __init__(
        self,
        datapack: DataPack,
        flags: List[QualityFlag],
        recommendation: TechnicianRecommendation,
        flags_csv_path: str,
        report_html_path: Optional[str] = None,
        report_pdf_path: Optional[str] = None
    ):
        self.datapack = datapack
        self.flags = flags
        self.recommendation = recommendation
        self.flags_csv_path = flags_csv_path
        self.report_html_path = report_html_path
        self.report_pdf_path = report_pdf_path


def run_pipeline(
    data_pack_dir: str,
    output_dir: str = ".",
    generate_reports: bool = True
) -> PipelineResult:
    """
    Execute full data quality analysis on the given data pack directory.
    Writes flags.csv into output_dir.
    """
    # 1. Discover and load data pack
    pack = discover_and_load_datapack(data_pack_dir)

    raw_flags: List[QualityFlag] = []

    # 2. Run station-level checks
    for st_id, df in pack.weather_data.items():
        st_meta = pack.metadata.get(st_id)
        
        # Check duplicates & non-monotonic time steps
        raw_flags.extend(detect_duplicates_and_non_monotonic(st_id, df))
        
        # Check gaps
        expected_interval = st_meta.logger_interval_min if st_meta else 10
        raw_flags.extend(detect_data_gaps(st_id, df, expected_interval))
        
        # Check physical limits
        raw_flags.extend(detect_physical_bounds(st_id, df))
        
        # Check stuck sensors
        raw_flags.extend(detect_stuck_sensors(st_id, df))
        
        # Check hardware code spikes
        raw_flags.extend(detect_spikes_and_hardware_codes(st_id, df))
        
        # Check cross-station / maintenance shifts
        raw_flags.extend(detect_step_changes_and_maintenance(
            st_id, df, pack.weather_data, pack.maintenance_events
        ))
        
        # Check rain funnel clog & dump
        raw_flags.extend(detect_rain_clog_and_dump(
            st_id, df, pack.weather_data, pack.maintenance_events
        ))
        
        # Check GPS records for station
        if st_id in pack.gps_records:
            raw_flags.extend(detect_gps_clock_and_position(
                st_id, pack.gps_records[st_id], st_meta
            ))

    # 3. Consolidate flags
    flags = consolidate_flags(raw_flags)

    # 4. Score stations for technician visit
    recommendation = score_stations_for_technician_visit(flags, pack.metadata)

    # 5. Write flags.csv into output_dir
    os.makedirs(output_dir, exist_ok=True)
    flags_csv_path = os.path.join(output_dir, "flags.csv")
    write_flags_csv(flags, flags_csv_path)

    # 6. Generate reports
    html_path = None
    pdf_path = None
    if generate_reports:
        html_path = os.path.join(output_dir, "report.html")
        pdf_path = os.path.join(output_dir, "report.pdf")
        generate_coordinator_report(
            flags=flags,
            metadata=pack.metadata,
            recommendation=recommendation,
            output_html_path=html_path,
            output_pdf_path=pdf_path
        )

    return PipelineResult(
        datapack=pack,
        flags=flags,
        recommendation=recommendation,
        flags_csv_path=flags_csv_path,
        report_html_path=html_path,
        report_pdf_path=pdf_path
    )
