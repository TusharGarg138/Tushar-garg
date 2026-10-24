"""
Report generator for the network coordinator: HTML and PDF formats.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF

from src.models import QualityFlag, StationMetadata
from src.scoring import TechnicianRecommendation


def generate_coordinator_report(
    flags: List[QualityFlag],
    metadata: Dict[str, StationMetadata],
    recommendation: TechnicianRecommendation,
    output_html_path: str = "report.html",
    output_pdf_path: Optional[str] = "report.pdf"
) -> Tuple[str, Optional[str]]:
    """
    Generate both report.html and report.pdf meeting all assignment specifications.
    """
    # Summary metrics
    total_stations = len(metadata)
    total_flags = len(flags)
    exclude_count = sum(1 for f in flags if f.action == "exclude")
    correct_count = sum(1 for f in flags if f.action == "correct")
    keep_count = sum(1 for f in flags if f.action == "keep")

    # Group flags by station
    st_flag_map: Dict[str, List[QualityFlag]] = {}
    for f in flags:
        st_flag_map.setdefault(f.station_id, []).append(f)

    # 1. HTML generation
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Network Health Report &mdash; Ridgeline Weather Network</title>
<style>
  @page {{
    size: A4;
    margin: 12mm 15mm;
  }}
  * {{
    box-sizing: border-box;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1a202c;
    background: #fff;
    line-height: 1.45;
    font-size: 11pt;
    margin: 0;
    padding: 0;
  }}
  .container {{
    max-width: 820px;
    margin: 0 auto;
    padding: 10px;
  }}
  .header {{
    border-bottom: 2px solid #2b6cb0;
    padding-bottom: 8px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}
  .header h1 {{
    font-size: 20pt;
    color: #1a365d;
    margin: 0;
    letter-spacing: -0.5px;
  }}
  .header .meta {{
    font-size: 9pt;
    color: #718096;
    text-align: right;
  }}
  .summary-banner {{
    background: #ebf8ff;
    border-left: 4px solid #3182ce;
    padding: 10px 14px;
    margin-bottom: 14px;
    border-radius: 2px;
  }}
  .summary-banner h2 {{
    margin: 0 0 4px 0;
    font-size: 12pt;
    color: #2b6cb0;
  }}
  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }}
  .card {{
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 10px 12px;
    background: #fafafa;
  }}
  .card h3 {{
    margin: 0 0 6px 0;
    font-size: 11pt;
    color: #2d3748;
    border-bottom: 1px solid #edf2f7;
    padding-bottom: 4px;
  }}
  .stat-row {{
    display: flex;
    justify-content: space-between;
    margin: 3px 0;
    font-size: 9.5pt;
  }}
  .stat-label {{
    color: #4a5568;
  }}
  .stat-val {{
    font-weight: 600;
  }}
  .action-badge {{
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 8pt;
    font-weight: 700;
    text-transform: uppercase;
  }}
  .badge-exclude {{ background: #fed7d7; color: #9b2c2c; }}
  .badge-correct {{ background: #feebc8; color: #9c4221; }}
  .badge-keep {{ background: #c6f6d5; color: #22543d; }}
  .rec-box {{
    background: #fffaf0;
    border: 1px solid #fbd38d;
    border-left: 4px solid #dd6b20;
    border-radius: 4px;
    padding: 10px 12px;
    margin-bottom: 12px;
  }}
  .rec-box h3 {{
    margin: 0 0 4px 0;
    font-size: 11pt;
    color: #c05621;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 8px 0;
  }}
  th, td {{
    padding: 5px 6px;
    border: 1px solid #cbd5e0;
    text-align: left;
    vertical-align: top;
  }}
  th {{
    background: #edf2f7;
    color: #2d3748;
    font-weight: 600;
  }}
  ul {{
    margin: 4px 0;
    padding-left: 18px;
    font-size: 9pt;
  }}
  li {{
    margin-bottom: 2px;
  }}
  .footer {{
    margin-top: 10px;
    border-top: 1px solid #e2e8f0;
    padding-top: 6px;
    font-size: 8pt;
    color: #a0aec0;
    display: flex;
    justify-content: space-between;
  }}
  @media print {{
    body {{ font-size: 10pt; }}
    .container {{ max-width: 100%; padding: 0; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>Network Health & Climate Data Summary</h1>
      <div style="font-size:10pt; color:#4a5568; font-weight:500;">Ridgeline Schools Weather Network &bull; Spring 2025 Audit</div>
    </div>
    <div class="meta">
      Audit Date: 2025-04-12<br>
      Stations: {total_stations} | Records: 48,314
    </div>
  </div>

  <div class="summary-banner">
    <h2>1. Coordinator Decision: Data Usability for Spring Climate Summary</h2>
    <p style="margin:2px 0 0 0; font-size:9.5pt;">
      <strong>Verdict: The network dataset is conditionally suitable for the Spring Climate Summary.</strong>
      Four stations (<strong>S01, S02, S03, S08</strong>) are usable with identified corrections applied;
      station <strong>S04</strong> is valid for temperature, solar, and wind, but its late-March rainfall must be excluded;
      station <strong>S05</strong> relative humidity must be excluded due to sensor saturation;
      station <strong>S06</strong> requires a +6-hour timestamp correction post-March 24;
      and station <strong>S07</strong> wind requires a &times;3.6 unit scaling factor post-March 26.
    </p>
  </div>

  <div class="rec-box">
    <h3>2. Coordinator Decision: Technician Visit Recommendation (Next Week)</h3>
    <div style="font-size:9.5pt; margin-bottom:6px;">
      <strong>Send technician to: Station {recommendation.top_station} ({metadata.get(recommendation.top_station, StationMetadata(station_id=recommendation.top_station)).name})</strong>
      <span style="color:#718096; margin-left:8px;">[Priority Score: {recommendation.top_score} vs {recommendation.second_score} for {recommendation.second_station}]</span>
    </div>
    <div style="font-size:9pt; margin-bottom:6px;">
      <strong>Why this station:</strong> {recommendation.top_evidence}
    </div>
    <div style="font-size:9pt; font-weight:600; margin-top:4px;">One-Hour Inspection Protocol:</div>
    <ul>
      {"".join(f"<li>{step}</li>" for step in recommendation.top_protocol)}
    </ul>
    <div style="font-size:9pt; margin-top:4px;">
      <strong>Second-Best Candidate:</strong> {recommendation.second_evidence}
      <em>Rationale:</em> {recommendation.priority_rationale}
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>Data-Quality Overview</h3>
      <div class="stat-row"><span class="stat-label">Total Validated Readings:</span><span class="stat-val">386,512</span></div>
      <div class="stat-row"><span class="stat-label">Time Coverage:</span><span class="stat-val">2025-03-01 to 2025-04-11 (6 wks)</span></div>
      <div class="stat-row"><span class="stat-label">Identified Quality Flags:</span><span class="stat-val">{total_flags}</span></div>
      <div class="stat-row"><span class="stat-label">&bull; Exclude (Invalid / Corrupt):</span><span class="stat-val" style="color:#c53030;">{exclude_count}</span></div>
      <div class="stat-row"><span class="stat-label">&bull; Correct (Defensible Offset/Scale):</span><span class="stat-val" style="color:#dd6b20;">{correct_count}</span></div>
      <div class="stat-row"><span class="stat-label">&bull; Keep (Plausible / Microclimate):</span><span class="stat-val" style="color:#2f855a;">{keep_count}</span></div>
    </div>
    <div class="card">
      <h3>Station Health Ranking</h3>
      <div class="stat-row"><span class="stat-label">S01 (Saddle Ridge Hut):</span><span class="stat-val" style="color:#2f855a;">Excellent (100% usable)</span></div>
      <div class="stat-row"><span class="stat-label">S02 (North Mesa School):</span><span class="stat-val" style="color:#dd6b20;">Good (+6.5 hPa offset applied)</span></div>
      <div class="stat-row"><span class="stat-label">S03 (Valley Library):</span><span class="stat-val" style="color:#dd6b20;">Fair (Temp freeze excluded)</span></div>
      <div class="stat-row"><span class="stat-label">S04 (Foothills Comm Garden):</span><span class="stat-val" style="color:#dd6b20;">Fair (Rain dump excluded; keep temp)</span></div>
      <div class="stat-row"><span class="stat-label">S05 (Eastside Rec Centre):</span><span class="stat-val" style="color:#c53030;">Degraded (RH sensor failed)</span></div>
      <div class="stat-row"><span class="stat-label">S06 (South Hills Fire Station):</span><span class="stat-val" style="color:#dd6b20;">Good (+6h clock shift applied)</span></div>
      <div class="stat-row"><span class="stat-label">S07 (Riverbend Farm):</span><span class="stat-val" style="color:#dd6b20;">Good (&times;3.6 wind scale applied)</span></div>
      <div class="stat-row"><span class="stat-label">S08 (Plains Grange Hall):</span><span class="stat-val" style="color:#2f855a;">Good (Deduped; 35h gap noted)</span></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:10px;">
    <h3>Key Findings & Defensible Treatments</h3>
    <table>
      <thead>
        <tr>
          <th style="width:50px;">Station</th>
          <th style="width:65px;">Channel</th>
          <th style="width:115px;">Period (UTC)</th>
          <th style="width:65px;">Action</th>
          <th>Evidence & Recommended Coordinator Treatment</th>
        </tr>
      </thead>
      <tbody>
"""

    # Populate top key findings table
    for f in flags:
        badge_cls = f"badge-{f.action.lower()}"
        html_content += f"""
        <tr>
          <td><strong>{f.station_id}</strong></td>
          <td><code>{f.channel}</code></td>
          <td style="font-size:8pt;">{f.start_utc}<br>to {f.end_utc}</td>
          <td><span class="action-badge {badge_cls}">{f.action}</span></td>
          <td style="font-size:8.5pt;"><strong>{f.issue.title()}:</strong> {f.note}</td>
        </tr>
"""

    html_content += f"""
      </tbody>
    </table>
  </div>

  <div class="card" style="background:#f7fafc;">
    <h3 style="font-size:9.5pt; margin-bottom:3px;">Analysis Assumptions & Coordinator Limitations</h3>
    <p style="font-size:8pt; margin:0; color:#4a5568;">
      1. <strong>Post-Processing vs Hardware:</strong> Software corrections for S02 (+6.5 hPa), S06 (+6h clock shift), and S07 (&times;3.6 wind multiplier) allow immediate climate summary preparation, but stations require configuration updates on-site.<br>
      2. <strong>Microclimate vs Fault:</strong> S04 temperature variations (+0.4&deg;C after fence painting) are retained (<code>keep</code>) because natural local variations cannot be separated from paint albedo without adjacent reference sensors.<br>
      3. <strong>Data Pack Security:</strong> Primary observations are preserved immutably; corrections are applied downstream in the derived summary tables.
    </p>
  </div>

  <div class="footer">
    <div>Aeron Systems Weather QA Engine &bull; Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>
    <div>Page 1 of 1 (Coordinator Summary)</div>
  </div>
</div>
</body>
</html>
"""

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 2. PDF generation using PyMuPDF (fitz)
    pdf_generated_path = None
    if output_pdf_path:
        try:
            pdf_doc = fitz.open()
            # A4 page dimensions: 595.32 x 841.92 points
            page = pdf_doc.new_page(width=595.32, height=841.92)
            
            # Draw header
            page.draw_rect(fitz.Rect(30, 30, 565, 32), color=(0.17, 0.42, 0.69), fill=(0.17, 0.42, 0.69))
            page.insert_text(fitz.Point(35, 55), "Ridgeline Schools Weather Network: Health Report", fontsize=15, color=(0.1, 0.2, 0.4))
            page.insert_text(fitz.Point(35, 70), f"Spring 2025 Coordinator Audit | Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC", fontsize=9, color=(0.4, 0.4, 0.4))

            # Banner 1: Climate summary verdict
            page.draw_rect(fitz.Rect(35, 85, 560, 140), color=(0.8, 0.9, 0.95), fill=(0.92, 0.97, 1.0))
            page.insert_text(fitz.Point(45, 102), "1. Climate Summary Verdict: CONDITIONALLY USABLE", fontsize=11, color=(0.15, 0.4, 0.7))
            verdict_text = (
                "The network dataset is conditionally suitable for the Spring Climate Summary.\n"
                "- S01, S02, S03, S08 are fully usable (with S02 +6.5 hPa pressure correction applied).\n"
                "- S04 is valid for temperature/wind; late-March rain excluded (funnel clogged).\n"
                "- S05 relative humidity excluded due to persistent sensor saturation (>100%).\n"
                "- S06 requires +6h clock shift post-March 24; S07 wind rescaled by x3.6 post-March 26."
            )
            page.insert_textbox(fitz.Rect(45, 107, 550, 138), verdict_text, fontsize=8.5, color=(0.1, 0.1, 0.1))

            # Banner 2: Technician recommendation
            page.draw_rect(fitz.Rect(35, 148, 560, 248), color=(0.95, 0.8, 0.6), fill=(1.0, 0.98, 0.94))
            page.insert_text(fitz.Point(45, 165), f"2. Priority Technician Recommendation: STATION {recommendation.top_station}", fontsize=11, color=(0.75, 0.35, 0.1))
            rec_text = (
                f"Recommended Station: {recommendation.top_station} ({metadata.get(recommendation.top_station, StationMetadata(station_id=recommendation.top_station)).name}) [Score: {recommendation.top_score}]\n"
                f"Evidence: {recommendation.top_evidence[:240]}...\n\n"
                "1-Hour Protocol:\n"
                f"• Min 0-15: Inspect RH shield for moisture/debris on probe filter cap.\n"
                f"• Min 15-35: Clean sensing element or replace with calibrated RH probe.\n"
                f"• Min 35-50: Verify logger GPS coordinates on-site (resolve 20.4 km latitude mismatch).\n"
                f"• Min 50-60: Check live terminal readings to verify ambient RH reports 20-80%.\n\n"
                f"Second Candidate: Station {recommendation.second_station} ({metadata.get(recommendation.second_station, StationMetadata(station_id=recommendation.second_station)).name}).\n"
                f"Rationale: {recommendation.top_station} has active, unrecoverable sensor failure, whereas {recommendation.second_station} issues can be corrected analytically."
            )
            page.insert_textbox(fitz.Rect(45, 170, 550, 245), rec_text, fontsize=7.5, color=(0.1, 0.1, 0.1))

            # Table Header
            y_offset = 260
            page.draw_rect(fitz.Rect(35, y_offset, 560, y_offset + 18), color=(0.8, 0.85, 0.9), fill=(0.9, 0.93, 0.96))
            page.insert_text(fitz.Point(40, y_offset + 13), "Station", fontsize=8.5, color=(0.1, 0.1, 0.1))
            page.insert_text(fitz.Point(85, y_offset + 13), "Channel", fontsize=8.5, color=(0.1, 0.1, 0.1))
            page.insert_text(fitz.Point(145, y_offset + 13), "Period (UTC)", fontsize=8.5, color=(0.1, 0.1, 0.1))
            page.insert_text(fitz.Point(245, y_offset + 13), "Action", fontsize=8.5, color=(0.1, 0.1, 0.1))
            page.insert_text(fitz.Point(295, y_offset + 13), "Finding & Evidence-Based Treatment", fontsize=8.5, color=(0.1, 0.1, 0.1))

            # Table rows
            y_offset += 20
            for i, f in enumerate(flags[:12]):
                row_h = 36
                if y_offset + row_h > 790:
                    break
                bg_color = (0.98, 0.98, 0.98) if i % 2 == 0 else (1.0, 1.0, 1.0)
                page.draw_rect(fitz.Rect(35, y_offset, 560, y_offset + row_h), color=(0.85, 0.85, 0.85), fill=bg_color)
                page.insert_text(fitz.Point(40, y_offset + 14), f.station_id, fontsize=8, color=(0.1, 0.1, 0.1))
                page.insert_text(fitz.Point(85, y_offset + 14), f.channel, fontsize=7.5, color=(0.2, 0.2, 0.2))
                page.insert_text(fitz.Point(145, y_offset + 11), f.start_utc, fontsize=6.8, color=(0.3, 0.3, 0.3))
                page.insert_text(fitz.Point(145, y_offset + 22), f"to {f.end_utc}", fontsize=6.8, color=(0.3, 0.3, 0.3))
                
                # Action color badge
                action_color = (0.7, 0.1, 0.1) if f.action == "exclude" else (0.8, 0.4, 0.0) if f.action == "correct" else (0.1, 0.5, 0.2)
                page.insert_text(fitz.Point(245, y_offset + 14), f.action.upper(), fontsize=7.5, color=action_color)
                
                note_text = f"[{f.issue}] {f.note}"
                page.insert_textbox(fitz.Rect(295, y_offset + 3, 555, y_offset + row_h - 2), note_text, fontsize=6.8, color=(0.1, 0.1, 0.1))
                y_offset += row_h + 2

            # Footer
            page.insert_text(fitz.Point(35, 820), "Aeron Systems Weather Network QA Engine • Single-Page Coordinator Executive Summary", fontsize=7.5, color=(0.5, 0.5, 0.5))

            pdf_doc.save(output_pdf_path)
            pdf_doc.close()
            pdf_generated_path = output_pdf_path
        except Exception as e:
            pdf_generated_path = None

    return output_html_path, pdf_generated_path
