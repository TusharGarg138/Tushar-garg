"""
Tests for NMEA sentence checksum verification and GPS coordinate parsing.
"""

from src.utils import verify_nmea_checksum, parse_nmea_coordinates
from src.loader import load_gps_file
from src.detectors import detect_gps_clock_and_position
from src.models import StationMetadata, GPSRecord
from datetime import datetime


def test_verify_nmea_checksum_valid():
    sentence = "$GPRMC,000000.00,A,3953.6752,N,10533.8904,W,0.0,0.0,010325,,,A*42"
    assert verify_nmea_checksum(sentence) is True


def test_verify_nmea_checksum_invalid():
    sentence = "$GPRMC,000000.00,A,3953.6752,N,10533.8904,W,0.0,0.0,010325,,,A*99"
    assert verify_nmea_checksum(sentence) is False


def test_parse_nmea_coordinates():
    # 3953.6752,N -> 39 deg 53.6752 min = 39 + 53.6752/60 = 39.8945866
    # 10533.8904,W -> -(105 + 33.8904/60) = -105.56484
    lat, lon = parse_nmea_coordinates("3953.6752", "N", "10533.8904", "W")
    assert abs(lat - 39.89458) < 0.001
    assert abs(lon - (-105.56484)) < 0.001


def test_detect_gps_clock_offset():
    rec = GPSRecord(
        logger_time=datetime(2025, 3, 24, 11, 0, 0),
        sentence_type="$GPRMC",
        gps_time=datetime(2025, 3, 24, 17, 0, 0),
        diff_sec=-21600.0
    )
    flags = detect_gps_clock_and_position("TEST_ST", [rec])
    assert len(flags) == 1
    assert flags[0].issue == "clock timezone offset"
    assert flags[0].action == "correct"
    assert "-6.0h" in flags[0].note or "+6h" in flags[0].note


def test_detect_gps_metadata_mismatch():
    rec = GPSRecord(
        logger_time=datetime(2025, 3, 1, 0, 0, 0),
        sentence_type="$GPRMC",
        lat=39.7540,
        lon=-104.8957,
        is_valid_checksum=True
    )
    meta = StationMetadata(station_id="TEST_ST", lat=39.5700, lon=-104.8957)
    flags = detect_gps_clock_and_position("TEST_ST", [rec], meta)
    assert len(flags) == 1
    assert flags[0].channel == "metadata"
    assert flags[0].action == "correct"
    assert "20.4 km" in flags[0].note
