"""
Core data structures for weather station network quality assurance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class QualityFlag:
    """Represents a data-quality finding matching the exact assignment schema."""
    station_id: str
    channel: str
    start_utc: str  # YYYY-MM-DD HH:MM
    end_utc: str    # YYYY-MM-DD HH:MM
    issue: str
    action: str     # 'exclude', 'correct', or 'keep'
    note: str
    severity: str = "warning"  # 'critical', 'warning', 'info'
    confidence: float = 1.0    # 0.0 to 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_csv_dict(self) -> Dict[str, str]:
        """Return exactly the 7 columns required by the assignment."""
        return {
            "station_id": self.station_id,
            "channel": self.channel,
            "start_utc": self.start_utc,
            "end_utc": self.end_utc,
            "issue": self.issue,
            "action": self.action,
            "note": self.note,
        }


@dataclass
class StationMetadata:
    """Metadata for an individual weather station."""
    station_id: str
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    elevation_m: float = 0.0
    installed: str = ""
    logger_interval_min: int = 10


@dataclass
class MaintenanceEvent:
    """Represents an entry in the volunteers' maintenance log."""
    date_str: str
    station_id: str
    note: str


@dataclass
class GPSRecord:
    """Parsed GPS NMEA record and logger clock difference."""
    logger_time: datetime
    sentence_type: str
    gps_time: Optional[datetime] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude_m: Optional[float] = None
    status: Optional[str] = None
    diff_sec: Optional[float] = None
    is_valid_checksum: bool = True
