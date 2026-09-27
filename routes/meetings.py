import os
from datetime import datetime
from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, make_response, current_app, jsonify
)

from models.database import db
from models.meeting import Meeting
from models.action_item import ActionItem
from services.file_extractor import extract_text_from_upload, clean_transcript
from services.nlp_extractor import extract_action_items
from services.export_service import export_to_csv, export_to_json, export_to_pdf

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")


@meetings_bp.route("/extract", methods=["POST"])
def extract_action_items_route():
    """
    Handles transcript extraction via file upload or direct text paste.
    Creates meeting record, executes NLP extraction pipeline, and persists action items.
    """
    meeting_title = request.form.get("title", "").strip() or "Untitled Meeting"
    raw_transcript = ""
    file_name = "Direct Input"
    file_type = "text"

    # 1. Check if a file was uploaded
    if "file" in request.files and request.files["file"].filename:
        file_obj = request.files["file"]
        file_name = file_obj.filename
        file_type = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "file"
        try:
            raw_transcript = extract_text_from_upload(file_obj)
        except Exception as e:
            flash(f"Error parsing uploaded file: {str(e)}", "danger")
            return redirect(url_for("main.extract_page"))

    # 2. Check if text was pasted directly
    elif request.form.get("transcript"):
        raw_transcript = clean_transcript(request.form.get("transcript", ""))
        file_name = "Direct Input"
        file_type = "text"

    # Validation
    if not raw_transcript or not raw_transcript.strip():
        flash("Please provide a meeting transcript by either uploading a file or pasting text.", "warning")
        return redirect(url_for("main.extract_page"))

    # Parse meeting date if provided
    meeting_date_str = request.form.get("meeting_date")
    meeting_date = datetime.utcnow()
    if meeting_date_str:
        try:
            meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d")
        except ValueError:
            pass

    # Threshold for duplicate similarity
    threshold = float(request.form.get("similarity_threshold", 0.75))

    try:
        # Create Meeting record
        meeting = Meeting(
            title=meeting_title,
            transcript=raw_transcript,
            file_name=file_name,
            file_type=file_type,
            meeting_date=meeting_date,
            created_at=datetime.utcnow()
        )
        db.session.add(meeting)
        db.session.flush()  # Allocate meeting.id

        # Run NLP extraction pipeline
        extracted_data = extract_action_items(raw_transcript, similarity_threshold=threshold)

        # Persist extracted items
        for item_data in extracted_data:
            action_item = ActionItem(
                meeting_id=meeting.id,
                task=item_data["task"],
                owner=item_data["owner"],
                deadline=item_data["deadline"],
                status="Pending",
                confidence=item_data["confidence"],
                source_sentence=item_data.get("source_sentence"),
                validation_message=item_data.get("validation_message"),
                missing_owner=item_data.get("missing_owner", False),
                missing_deadline=item_data.get("missing_deadline", False),
                is_duplicate=item_data.get("is_duplicate", False)
            )
            db.session.add(action_item)

        db.session.commit()

        flash(
            f"Successfully extracted {len(extracted_data)} action items from '{meeting_title}'!",
            "success"
        )
        return redirect(url_for("meetings.view_meeting", meeting_id=meeting.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Extraction failed: {str(e)}", "danger")
        return redirect(url_for("main.extract_page"))


@meetings_bp.route("/<int:meeting_id>")
def view_meeting(meeting_id: int):
    """
    Displays the Results Table and analysis for an extracted meeting.
    """
    meeting = db.get_or_404(Meeting, meeting_id)
    items = meeting.action_items

    total_count = len(items)
    completed_count = sum(1 for i in items if i.status == "Completed")
    pending_count = sum(1 for i in items if i.status == "Pending" and not i.is_overdue)
    overdue_count = sum(1 for i in items if i.is_overdue)
    avg_confidence = int(round((sum(i.confidence for i in items) / total_count * 100))) if total_count > 0 else 0
    duplicate_count = sum(1 for i in items if i.is_duplicate)
    unassigned_count = sum(1 for i in items if i.missing_owner or i.owner == "Unassigned")

    return render_template(
        "meeting_detail.html",
        meeting=meeting,
        items=items,
        total_count=total_count,
        completed_count=completed_count,
        pending_count=pending_count,
        overdue_count=overdue_count,
        avg_confidence=avg_confidence,
        duplicate_count=duplicate_count,
        unassigned_count=unassigned_count
    )


@meetings_bp.route("/<int:meeting_id>/delete", methods=["POST"])
def delete_meeting(meeting_id: int):
    """
    Deletes a meeting and all associated action items.
    """
    meeting = db.get_or_404(Meeting, meeting_id)
    title = meeting.title
    db.session.delete(meeting)
    db.session.commit()
    flash(f"Meeting '{title}' and its action items were permanently deleted.", "info")
    return redirect(url_for("main.history"))


@meetings_bp.route("/sample-demo")
def load_sample_demo():
    """
    Loads pre-bundled sample meeting transcript, runs extraction,
    and opens the results table.
    """
    base_dir = Path(__file__).resolve().parent.parent
    sample_file = base_dir / "sample_data" / "sample_transcript.txt"

    if not sample_file.exists():
        flash("Sample transcript file could not be found.", "warning")
        return redirect(url_for("main.extract_page"))

    with open(sample_file, "r", encoding="utf-8") as f:
        transcript_content = f.read()

    # Create meeting
    meeting = Meeting(
        title="Sprint Planning & Delivery Sync - Q3 (Demo)",
        transcript=transcript_content,
        file_name="sample_transcript.txt",
        file_type="txt",
        meeting_date=datetime(2024, 10, 14),
        created_at=datetime.utcnow()
    )
    db.session.add(meeting)
    db.session.flush()

    # Extract action items
    extracted_items = extract_action_items(transcript_content, similarity_threshold=0.75)
    for data in extracted_items:
        action_item = ActionItem(
            meeting_id=meeting.id,
            task=data["task"],
            owner=data["owner"],
            deadline=data["deadline"],
            status="Pending",
            confidence=data["confidence"],
            source_sentence=data.get("source_sentence"),
            validation_message=data.get("validation_message"),
            missing_owner=data.get("missing_owner", False),
            missing_deadline=data.get("missing_deadline", False),
            is_duplicate=data.get("is_duplicate", False)
        )
        db.session.add(action_item)

    db.session.commit()
    flash("Sample Meeting Demo successfully loaded with dynamic NLP extraction!", "success")
    return redirect(url_for("meetings.view_meeting", meeting_id=meeting.id))


@meetings_bp.route("/<int:meeting_id>/export/csv")
def export_meeting_csv(meeting_id: int):
    """
    Exports a meeting's action items as a downloadable CSV.
    """
    meeting = db.get_or_404(Meeting, meeting_id)
    csv_buffer = export_to_csv(meeting.action_items, meeting.title)
    
    filename = f"action_items_{meeting.id}_{datetime.now().strftime('%Y%m%d')}.csv"
    response = make_response(csv_buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


@meetings_bp.route("/<int:meeting_id>/export/json")
def export_meeting_json(meeting_id: int):
    """
    Exports a meeting's action items and metadata as a downloadable JSON file.
    """
    meeting = db.get_or_404(Meeting, meeting_id)
    json_str = export_to_json(meeting=meeting)
    
    filename = f"meeting_{meeting.id}_export.json"
    response = make_response(json_str)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "application/json"
    return response


@meetings_bp.route("/<int:meeting_id>/export/pdf")
def export_meeting_pdf(meeting_id: int):
    """
    Exports a meeting's action items as a beautifully styled PDF report.
    """
    meeting = db.get_or_404(Meeting, meeting_id)
    pdf_buffer = export_to_pdf(meeting)
    
    filename = f"meeting_{meeting.id}_report.pdf"
    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "application/pdf"
    return response
