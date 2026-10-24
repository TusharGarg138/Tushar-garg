"""
Tests for technician visit prioritization scoring.
"""

from src.models import QualityFlag, StationMetadata
from src.scoring import score_stations_for_technician_visit
from src.pipeline import run_pipeline


def test_scoring_prioritizes_active_unrecoverable_hardware():
    flags = [
        # S01 has software-correctable pressure offset
        QualityFlag(
            station_id="S01",
            channel="pressure_hpa",
            start_utc="2025-03-21 00:00",
            end_utc="2025-04-11 23:50",
            issue="uncalibrated sensor replacement",
            action="correct",
            note="Offset +5.6 hPa"
        ),
        # S02 has active digital sensor communication faults recurring in late April
        QualityFlag(
            station_id="S02",
            channel="temp_c",
            start_utc="2025-04-08 09:50",
            end_utc="2025-04-08 09:50",
            issue="hardware error code spike",
            action="exclude",
            note="Fault code 85.0C"
        ),
        QualityFlag(
            station_id="S02",
            channel="temp_c",
            start_utc="2025-03-18 06:00",
            end_utc="2025-03-21 14:00",
            issue="stuck sensor",
            action="exclude",
            note="Frozen at 6.5C"
        )
    ]
    
    meta = {
        "S01": StationMetadata(station_id="S01", name="Station 1"),
        "S02": StationMetadata(station_id="S02", name="Station 2"),
    }
    
    rec = score_stations_for_technician_visit(flags, meta)
    assert rec.top_station == "S02"
    assert rec.second_station == "S01"
    assert "S02" in rec.top_evidence


def test_ridgeline_dataset_technician_ranking():
    """Verify that on the actual Ridgeline dataset, S03 is rank #1 and S05 is rank #2."""
    res = run_pipeline("ridgeline_data_pack", generate_reports=False)
    assert res.recommendation.top_station == "S03"
    assert res.recommendation.second_station == "S05"
    assert res.recommendation.top_score > res.recommendation.second_score
    assert len(res.recommendation.all_rankings) == 8
