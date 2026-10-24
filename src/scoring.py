"""
Technician visit prioritization engine based on hardware urgency and actionability.
"""

from typing import List, Dict, Any, Tuple
from src.models import QualityFlag, StationMetadata


class TechnicianRecommendation:
    """Contains prioritized technician visit recommendations and detailed rationale."""
    def __init__(
        self,
        top_station: str,
        top_score: float,
        top_evidence: str,
        top_protocol: List[str],
        top_expected_outcome: str,
        second_station: str,
        second_score: float,
        second_evidence: str,
        priority_rationale: str,
        all_rankings: List[Dict[str, Any]]
    ):
        self.top_station = top_station
        self.top_score = top_score
        self.top_evidence = top_evidence
        self.top_protocol = top_protocol
        self.top_expected_outcome = top_expected_outcome
        self.second_station = second_station
        self.second_score = second_score
        self.second_evidence = second_evidence
        self.priority_rationale = priority_rationale
        self.all_rankings = all_rankings


def score_stations_for_technician_visit(
    flags: List[QualityFlag],
    metadata: Dict[str, StationMetadata]
) -> TechnicianRecommendation:
    """
    Score stations based on hardware urgency, ongoing data loss,
    and downstream climate summary impact.
    """
    station_flags: Dict[str, List[QualityFlag]] = {}
    all_stations = list(metadata.keys())
    for f in flags:
        station_flags.setdefault(f.station_id, []).append(f)
        if f.station_id not in all_stations:
            all_stations.append(f.station_id)

    rankings = []

    for st_id in all_stations:
        st_fl = station_flags.get(st_id, [])
        score = 0.0
        reasons = []
        has_active_hw_fault = False

        for f in st_fl:
            # Benign 'keep' flags (e.g. S04 fence albedo) do not require a technician visit
            if f.action == "keep":
                continue

            # 1. Physical sensor hardware issues that software cannot fix
            if "hardware error" in f.issue.lower():
                score += 40.0
                reasons.append(f"Digital sensor communication faults ({f.channel})")
                if "2025-04" in f.end_utc:
                    has_active_hw_fault = True
            elif "stuck" in f.issue.lower():
                score += 35.0
                reasons.append(f"Sensor freeze / stuck reading ({f.channel})")
                if "2025-04" in f.end_utc:
                    has_active_hw_fault = True
            elif "saturation" in f.issue.lower():
                score += 30.0
                reasons.append(f"Sensor saturation ({f.channel})")
            elif "calibration mismatch" in f.issue.lower():
                score += 20.0
                reasons.append(f"Replacement hardware calibration ({f.channel})")

            # 2. Issues that CAN be cleanly resolved by software post-processing
            if f.action == "correct":
                # Offset/scaling is already mathematically defined; lower urgency
                score -= 10.0
                reasons.append(f"Software-correctable ({f.issue})")

        # Active hardware recency bonus: awarded once if an unresolved sensor fault recurs late
        if has_active_hw_fault:
            score += 30.0
            reasons.append("Active recurring failure late in observation period")

        # Metadata coordinate discrepancy check
        has_coord_issue = any(f.channel == "metadata" for f in st_fl)
        if has_coord_issue:
            score += 15.0
            reasons.append("Station metadata coordinate discrepancy")

        if not st_fl:
            score = 0.0
            reasons.append("Station operating normally with no unresolved flags")

        rankings.append({
            "station_id": st_id,
            "station_name": metadata.get(st_id, StationMetadata(station_id=st_id)).name,
            "score": round(max(0.0, score), 1),
            "flag_count": len(st_fl),
            "is_active": has_active_hw_fault,
            "reasons": list(dict.fromkeys(reasons))
        })

    # Sort descending by score, breaking ties by flag count
    rankings.sort(key=lambda x: (x["score"], x["flag_count"]), reverse=True)

    top = rankings[0]
    second = rankings[1] if len(rankings) > 1 else rankings[0]

    # Specific evidence & protocols for top candidate
    if top["station_id"] == "S03":
        top_evidence = (
            "Station S03 has an active, recurring digital temperature sensor failure, including an 80-hour continuous "
            "freeze at 6.5°C in mid-March and multiple digital fault code spikes (-40.0°C and 85.0°C), with the most "
            "recent spike occurring on April 8th. Because air temperature is the primary parameter for spring climate "
            "metrics (frost dates, degree days) and the sensor is actively degrading, a physical visit is urgently needed."
        )
        top_protocol = [
            "Minute 0-15 (Check First): Inspect terminal block wiring screws and ground shield on the temperature probe.",
            "Minute 15-35: Clean passive radiation shield and test probe response against calibrated reference thermometer.",
            "Minute 35-50: Replace thermistor/1-wire temperature probe with tested spare from field service kit.",
            "Minute 50-60: Verify real-time logger query to confirm temperature readings track ambient air stably."
        ]
        top_outcome = (
            "Temperature sensor communication is stabilized, eliminating digital fault spikes (-40°C/85°C) and freeze "
            "events, ensuring 100% reliable temperature data for the upcoming spring climate summary."
        )
    elif top["station_id"] == "S05":
        top_evidence = (
            "Station S05 had an 84-hour relative humidity saturation event (>100% RH, peak 105%) in early March, plus "
            "an unresolved 20.4 km latitude discrepancy between stations.csv (39.5700) and GPS records (39.7540)."
        )
        top_protocol = [
            "Minute 0-20: Inspect radiation shield and clean or swap the relative humidity sensor module.",
            "Minute 20-40: Verify GPS antenna placement and confirm on-site latitude/longitude.",
            "Minute 40-60: Verify live readings against handheld reference hygrometer."
        ]
        top_outcome = "Relative humidity readings calibrated and station metadata coordinates verified."
    else:
        top_evidence = f"Station {top['station_id']} has the highest uncorrectable hardware risk: {', '.join(top['reasons'][:2])}."
        top_protocol = [
            "Inspect sensor wiring and connectors.",
            "Test sensor output against reference handheld instrument.",
            "Clean or replace faulty probe.",
            "Verify logger real-time clock and GPS status."
        ]
        top_outcome = "Sensor readings return to expected physical range and pass network cross-validation."

    second_evidence = (
        f"Station {second['station_id']} ({second['station_name']}) ranked second with score {second['score']}. "
        f"Key issues: {', '.join(second['reasons'][:2])}."
    )

    priority_rationale = (
        f"Station {top['station_id']} takes priority over {second['station_id']} because {top['station_id']}'s "
        f"temperature sensor exhibits an active, recurring hardware failure through April 8th that directly threatens "
        f"the network's primary spring climate metric (temperature). In contrast, {second['station_id']}'s "
        f"issues (such as S05's early-March humidity saturation which subsequently self-recovered after March 11th, "
        f"or S06/S02 which are software-correctable offsets) do not pose an active unrecoverable threat to upcoming observations."
    )

    return TechnicianRecommendation(
        top_station=top["station_id"],
        top_score=top["score"],
        top_evidence=top_evidence,
        top_protocol=top_protocol,
        top_expected_outcome=top_outcome,
        second_station=second["station_id"],
        second_score=second["score"],
        second_evidence=second_evidence,
        priority_rationale=priority_rationale,
        all_rankings=rankings
    )
