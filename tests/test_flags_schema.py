"""
Validation tests for the exact flags.csv schema and serialization.
"""

import os
import csv
import re
from src.models import QualityFlag
from src.utils import write_flags_csv

SCHEMA_COLUMNS = [
    "station_id",
    "channel",
    "start_utc",
    "end_utc",
    "issue",
    "action",
    "note"
]

TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


def test_flags_csv_exact_schema(tmp_path):
    out_file = str(tmp_path / "test_flags.csv")
    flags = [
        QualityFlag(
            station_id="STATION_A",
            channel="temp_c",
            start_utc="2025-05-01 12:00",
            end_utc="2025-05-01 12:00",
            issue="hardware error code spike",
            action="exclude",
            note="Spike to -40C."
        ),
        QualityFlag(
            station_id="STATION_B",
            channel="pressure_hpa",
            start_utc="2025-05-02 08:00",
            end_utc="2025-05-10 18:00",
            issue="uncalibrated sensor replacement",
            action="correct",
            note="Shift by -5.0 hPa."
        )
    ]
    
    write_flags_csv(flags, out_file)
    assert os.path.exists(out_file)

    with open(out_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == SCHEMA_COLUMNS, f"Expected {SCHEMA_COLUMNS}, got {header}"
        
        rows = list(reader)
        assert len(rows) == 2
        for r in rows:
            assert len(r) == 7
            # start_utc and end_utc format
            assert TIMESTAMP_REGEX.match(r[2]), f"Invalid start_utc: {r[2]}"
            assert TIMESTAMP_REGEX.match(r[3]), f"Invalid end_utc: {r[3]}"
            # action
            assert r[5] in ("exclude", "correct", "keep")
            # note contains no newlines
            assert "\n" not in r[6]
            assert "\r" not in r[6]


def test_flags_deterministic_sorting(tmp_path):
    out_file = str(tmp_path / "sorted_flags.csv")
    f1 = QualityFlag(station_id="S02", channel="all", start_utc="2025-03-05 10:00", end_utc="2025-03-05 11:00", issue="gap", action="exclude", note="gap")
    f2 = QualityFlag(station_id="S01", channel="temp_c", start_utc="2025-03-02 04:00", end_utc="2025-03-02 04:00", issue="spike", action="exclude", note="spike")
    f3 = QualityFlag(station_id="S01", channel="rh_pct", start_utc="2025-03-01 12:00", end_utc="2025-03-01 13:00", issue="high", action="exclude", note="high")

    write_flags_csv([f1, f2, f3], out_file)

    with open(out_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        # Should be sorted: S01 first (2025-03-01 then 2025-03-02), then S02
        assert rows[0]["station_id"] == "S01" and rows[0]["channel"] == "rh_pct"
        assert rows[1]["station_id"] == "S01" and rows[1]["channel"] == "temp_c"
        assert rows[2]["station_id"] == "S02"
