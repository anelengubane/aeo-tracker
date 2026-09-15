"""
Generates the 1-page Snapshot PDF report from scored data.

Built out: Sep 15 catch-up session (Phase 1).

Usage:
    python -m src.report <client_slug>

Requires scored_results.json to already exist for the client
(run data_collection.py then scoring.py first).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from src.config import CLIENTS_DIR, load_fact_sheet

# Mosia brand palette
DEEP_TECH_INDIGO = colors.HexColor("#0B111E")
CYBER_CLEAN = colors.HexColor("#F8FAFC")
NEON_ELECTRIC = colors.HexColor("#00D2FF")
MARKETING_GOLD = colors.HexColor("#FFC700")


def _compute_summary(scored_data: dict) -> dict:
    """Roll scored per-prompt/per-engine results up into headline stats."""
    total = 0
    mentioned = 0
    positions = []
    citations = 0
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    competitor_counts: dict[str, int] = {}
    scoring_errors = 0

    for item in scored_data["results"]:
        for engine_data in item["engines"].values():
            if "error" in engine_data:
                scoring_errors += 1
                continue
            total += 1
            if engine_data.get("mentioned"):
                mentioned += 1
                if isinstance(engine_data.get("position"), int):
                    positions.append(engine_data["position"])
                sentiment = engine_data.get("sentiment")
                if sentiment in sentiment_counts:
                    sentiment_counts[sentiment] += 1
            if engine_data.get("citation_present"):
                citations += 1
            for competitor in engine_data.get("competitors_mentioned", []) or []:
                competitor_counts[competitor] = competitor_counts.get(competitor, 0) + 1

    mention_rate = (mentioned / total * 100) if total else 0.0
    citation_rate = (citations / total * 100) if total else 0.0
    avg_position = (sum(positions) / len(positions)) if positions else None

    top_competitors = sorted(competitor_counts.items(), key=lambda kv: -kv[1])[:3]

    return {
        "total_checks": total,
        "mentioned": mentioned,
        "mention_rate": mention_rate,
        "avg_position": avg_position,
        "citation_rate": citation_rate,
        "sentiment_counts": sentiment_counts,
        "top_competitors": top_competitors,
        "scoring_errors": scoring_errors,
    }


def generate_report(client_slug: str) -> Path:
    fact_sheet = load_fact_sheet(client_slug)

    scored_path = CLIENTS_DIR / client_slug / "scored_results.json"
    if not scored_path.exists():
        raise FileNotFoundError(
            f"No scored_results.json for '{client_slug}' — run scoring.py first (expected {scored_path})"
        )
    with open(scored_path, "r", encoding="utf-8") as f:
        scored_data = json.load(f)

    summary = _compute_summary(scored_data)

    reports_dir = CLIENTS_DIR / client_slug / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = reports_dir / f"{client_slug}_snapshot_{date_str}.pdf"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SnapshotTitle", parent=styles["Title"], textColor=DEEP_TECH_INDIGO, fontSize=22, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "SnapshotSubtitle", parent=styles["Normal"], textColor=colors.HexColor("#5A6472"), fontSize=10, spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"], textColor=DEEP_TECH_INDIGO, fontSize=13, spaceBefore=10, spaceAfter=4,
    )
    tight_section_style = ParagraphStyle(
        "TightSectionHeading", parent=styles["Heading2"], textColor=DEEP_TECH_INDIGO, fontSize=13, spaceBefore=6, spaceAfter=4,
    )
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12)
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=7.5, leading=9.5)
    header_cell_style = ParagraphStyle("HeaderCell", parent=styles["Normal"], fontSize=7.5, leading=9.5, textColor=colors.white)
    stat_number_style = ParagraphStyle(
        "StatNumber", parent=styles["Normal"], fontSize=20, textColor=DEEP_TECH_INDIGO, alignment=TA_CENTER, leading=24,
    )
    stat_label_style = ParagraphStyle(
        "StatLabel", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#5A6472"), alignment=TA_CENTER,
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#5A6472"),
    )

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=14 * mm, bottomMargin=10 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    )
    story = []

    story.append(Paragraph("AEO Snapshot", title_style))
    story.append(Paragraph(
        f"{fact_sheet['name']} &middot; {fact_sheet['location']} &middot; "
        f"generated {datetime.now(timezone.utc).strftime('%d %b %Y')} by Answer Index (Mosia)",
        subtitle_style,
    ))

    avg_pos_display = f"{summary['avg_position']:.1f}" if summary["avg_position"] else "—"
    stats = [
        (f"{summary['mention_rate']:.0f}%", "Mention rate"),
        (avg_pos_display, "Avg. position\nwhen mentioned"),
        (f"{summary['citation_rate']:.0f}%", "Citation rate"),
        (f"{summary['total_checks']}", "Engine checks\nthis snapshot"),
    ]
    stat_table = Table(
        [[Paragraph(n, stat_number_style) for n, _ in stats],
         [Paragraph(l.replace(chr(10), "<br/>"), stat_label_style) for _, l in stats]],
        colWidths=[42 * mm] * 4,
    )
    stat_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("BACKGROUND", (0, 0), (-1, 0), CYBER_CLEAN),
        ("BACKGROUND", (0, 1), (-1, 1), CYBER_CLEAN),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ]))
    story.append(stat_table)

    sc = summary["sentiment_counts"]
    story.append(Paragraph("Sentiment when mentioned", section_style))
    story.append(Paragraph(
        f"Positive: <b>{sc['positive']}</b> &nbsp;&nbsp; Neutral: <b>{sc['neutral']}</b> &nbsp;&nbsp; "
        f"Negative: <b>{sc['negative']}</b>", body_style,
    ))

    if summary["top_competitors"]:
        comp_line = ", ".join(f"{name} ({count})" for name, count in summary["top_competitors"])
        story.append(Paragraph("Competitors AI engines mention instead", section_style))
        story.append(Paragraph(comp_line, body_style))

    story.append(Paragraph("Prompt-by-prompt breakdown", tight_section_style))
    header_row = [Paragraph(h, header_cell_style) for h in
                  ["Prompt", "Engine", "Mentioned", "Position", "Sentiment", "Citation"]]
    table_data = [header_row]
    for item in scored_data["results"]:
        prompt_text = item["prompt"]
        if len(prompt_text) > 55:
            prompt_text = prompt_text[:52] + "..."
        prompt_cell = Paragraph(prompt_text, cell_style)
        for engine_name, engine_data in item["engines"].items():
            if "error" in engine_data:
                table_data.append([prompt_cell, engine_name, "—", "—", "error", "—"])
                continue
            table_data.append([
                prompt_cell,
                engine_name,
                "Yes" if engine_data.get("mentioned") else "No",
                str(engine_data.get("position")) if engine_data.get("position") else "—",
                engine_data.get("sentiment", "—"),
                "Yes" if engine_data.get("citation_present") else "No",
            ])

    breakdown_table = Table(
        table_data,
        colWidths=[62 * mm, 24 * mm, 24 * mm, 18 * mm, 24 * mm, 20 * mm],
        repeatRows=1,
    )
    breakdown_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DEEP_TECH_INDIGO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (1, 1), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CYBER_CLEAN]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(breakdown_table)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Answer Index by Mosia &mdash; AI-mention tracking for local service businesses. "
        "anelengubane0@gmail.com &middot; 072 282 6357",
        footer_style,
    ))

    doc.build(story)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m src.report <client_slug>")
        sys.exit(1)

    saved_to = generate_report(sys.argv[1])
    print(f"Saved report to {saved_to}")
