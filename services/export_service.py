import csv
import io
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
import reportlab.pdfbase.pdfdoc as _pdfdoc

# Compatibility patch for ReportLab on Windows OpenSSL builds where openssl_md5 rejects usedforsecurity
try:
    if hasattr(_pdfdoc, "md5"):
        _orig_pdfdoc_md5 = _pdfdoc.md5
        _pdfdoc.md5 = lambda *args, **kwargs: _orig_pdfdoc_md5(*args, **{k: v for k, v in kwargs.items() if k != "usedforsecurity"})
except Exception:
    pass

from models.action_item import ActionItem
from models.meeting import Meeting


def export_to_csv(action_items: List[ActionItem], meeting_title: Optional[str] = None) -> io.StringIO:
    """
    Generates a CSV export of action items.
    Returns a StringIO buffer ready to be streamed or saved.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header row
    writer.writerow([
        "ID",
        "Meeting Title",
        "Task Description",
        "Owner",
        "Deadline",
        "Status",
        "Confidence (%)",
        "Validation Message",
        "Is Overdue",
        "Is Duplicate",
        "Missing Owner",
        "Missing Deadline",
        "Source Sentence",
        "Created At"
    ])

    for item in action_items:
        writer.writerow([
            item.id,
            item.meeting.title if item.meeting else (meeting_title or "N/A"),
            item.task,
            item.owner,
            item.deadline,
            item.current_status,
            item.to_dict()["confidence_percent"],
            item.validation_message or "Valid",
            "Yes" if item.is_overdue else "No",
            "Yes" if item.is_duplicate else "No",
            "Yes" if item.missing_owner else "No",
            "Yes" if item.missing_deadline else "No",
            item.source_sentence or "",
            item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else ""
        ])

    output.seek(0)
    return output


def export_to_json(meeting: Optional[Meeting] = None, action_items: Optional[List[ActionItem]] = None) -> str:
    """
    Generates a formatted JSON string export for a meeting or list of action items.
    """
    if meeting:
        data = {
            "meeting": meeting.to_dict(include_items=True),
            "export_timestamp": datetime.utcnow().isoformat() + "Z"
        }
    else:
        items = action_items or []
        data = {
            "total_items": len(items),
            "export_timestamp": datetime.utcnow().isoformat() + "Z",
            "action_items": [item.to_dict() for item in items]
        }

    return json.dumps(data, indent=2)


class NumberedCanvas(canvas.Canvas):
    """Custom canvas that adds page numbers and footer to each page."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Footer
        footer_text = f"AI Meeting Action-Item Extractor  |  Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 40, 30, footer_text)
        
        # Timestamp
        date_str = datetime.now().strftime("%B %d, %Y %H:%M")
        self.drawString(40, 30, f"Generated: {date_str}")
        
        # Decorative footer line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 44, letter[0] - 40, 44)
        
        self.restoreState()


def export_to_pdf(meeting: Meeting, action_items: Optional[List[ActionItem]] = None) -> io.BytesIO:
    """
    Generates a high-quality PDF report for a meeting and its extracted action items.
    Returns a BytesIO stream.
    """
    items = action_items if action_items is not None else meeting.action_items
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A")
    )
    
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569")
    )

    heading2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=12,
        spaceAfter=8
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )

    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=1  # Center
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("AI Meeting Action-Item Report", title_style))
    story.append(Spacer(1, 4))
    
    created_str = meeting.created_at.strftime("%B %d, %Y %I:%M %p") if meeting.created_at else "N/A"
    meeting_meta = f"<b>Meeting:</b> {meeting.title} &nbsp;|&nbsp; <b>Source:</b> {meeting.file_name} &nbsp;|&nbsp; <b>Extracted On:</b> {created_str}"
    story.append(Paragraph(meeting_meta, subtitle_style))
    story.append(Spacer(1, 12))

    # Metric Summary Cards (Table layout)
    total_count = len(items)
    completed_count = sum(1 for item in items if item.status == "Completed")
    pending_count = sum(1 for item in items if item.status == "Pending" and not item.is_overdue)
    overdue_count = sum(1 for item in items if item.is_overdue)
    avg_confidence = (sum(item.confidence for item in items) / total_count * 100) if total_count > 0 else 0

    summary_data = [
        [
            Paragraph(f"<b>Total Action Items</b><br/><font size='14' color='#2563EB'><b>{total_count}</b></font>", subtitle_style),
            Paragraph(f"<b>Completed</b><br/><font size='14' color='#16A34A'><b>{completed_count}</b></font>", subtitle_style),
            Paragraph(f"<b>Pending</b><br/><font size='14' color='#D97706'><b>{pending_count}</b></font>", subtitle_style),
            Paragraph(f"<b>Overdue</b><br/><font size='14' color='#DC2626'><b>{overdue_count}</b></font>", subtitle_style),
            Paragraph(f"<b>Avg Confidence</b><br/><font size='14' color='#4F46E5'><b>{avg_confidence:.0f}%</b></font>", subtitle_style),
        ]
    ]

    summary_table = Table(summary_data, colWidths=[108, 108, 108, 108, 108])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # Action Items Table
    story.append(Paragraph("Action Items Breakdown", heading2_style))

    if not items:
        story.append(Paragraph("<i>No action items extracted for this meeting.</i>", subtitle_style))
    else:
        table_rows = [
            [
                Paragraph("<b>#</b>", table_header_style),
                Paragraph("<b>Task Description</b>", table_header_style),
                Paragraph("<b>Owner</b>", table_header_style),
                Paragraph("<b>Deadline</b>", table_header_style),
                Paragraph("<b>Status</b>", table_header_style),
                Paragraph("<b>Confidence</b>", table_header_style),
            ]
        ]

        for idx, item in enumerate(items, 1):
            # Status styling
            if item.current_status == "Completed":
                status_color = "#16A34A"
            elif item.current_status == "Overdue":
                status_color = "#DC2626"
            else:
                status_color = "#D97706"

            status_cell = f"<font color='{status_color}'><b>{item.current_status}</b></font>"

            # Warning notes for missing owner/deadline or duplicate
            warnings = []
            if item.missing_owner or item.owner == "Unassigned":
                warnings.append("<font color='#DC2626'>[Missing Owner]</font>")
            if item.missing_deadline or item.deadline == "Not specified":
                warnings.append("<font color='#D97706'>[No Deadline]</font>")
            if item.is_duplicate:
                warnings.append("<font color='#6366F1'>[Duplicate]</font>")

            warning_text = ("<br/>" + " ".join(warnings)) if warnings else ""
            task_text = f"<b>{item.task}</b>{warning_text}"
            if item.source_sentence:
                task_text += f"<br/><font size='7' color='#64748B'><i>\"{item.source_sentence}\"</i></font>"

            # Confidence color
            conf_pct = int(round(item.confidence * 100))
            if conf_pct >= 75:
                conf_color = "#16A34A"
            elif conf_pct >= 50:
                conf_color = "#2563EB"
            else:
                conf_color = "#D97706"

            table_rows.append([
                Paragraph(str(idx), table_cell_style),
                Paragraph(task_text, table_cell_style),
                Paragraph(f"<b>{item.owner}</b>", table_cell_style),
                Paragraph(item.deadline, table_cell_style),
                Paragraph(status_cell, table_cell_style),
                Paragraph(f"<font color='{conf_color}'><b>{conf_pct}%</b></font>", table_cell_style),
            ])

        # Widths total 540 pt (matching letter width 612 - 72 margins)
        items_table = Table(
            table_rows,
            colWidths=[24, 230, 85, 85, 60, 56],
            repeatRows=1
        )
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (4, 0), (5, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(items_table)

    # Optional: Meeting Transcript snippet
    if meeting.transcript:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Meeting Transcript Reference", heading2_style))
        transcript_snippet = meeting.transcript.strip()
        if len(transcript_snippet) > 800:
            transcript_snippet = transcript_snippet[:800] + "... [truncated for brevity in report]"
        
        # Replace newlines with <br/> for ReportLab Paragraph
        transcript_formatted = transcript_snippet.replace("\n", "<br/>")
        story.append(Paragraph(
            f"<font color='#475569'>{transcript_formatted}</font>",
            table_cell_style
        ))

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
