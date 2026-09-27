from datetime import datetime
from flask import Blueprint, request, jsonify, make_response

from models.database import db
from models.meeting import Meeting
from models.action_item import ActionItem
from services.nlp_extractor import extract_action_items
from services.file_extractor import clean_transcript
from services.export_service import export_to_csv, export_to_json

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/extract", methods=["POST"])
def api_extract():
    """
    API endpoint for programmatic action item extraction from raw transcript text.
    """
    data = request.get_json(silent=True) or {}
    transcript = data.get("transcript", "")
    threshold = float(data.get("similarity_threshold", 0.75))

    cleaned = clean_transcript(transcript)
    if not cleaned:
        return jsonify({"error": "No transcript provided"}), 400

    items = extract_action_items(cleaned, similarity_threshold=threshold)
    
    # Format dates to iso strings for JSON serialization
    serialized_items = []
    for item in items:
        item_copy = dict(item)
        if item_copy.get("deadline_date"):
            item_copy["deadline_date"] = item_copy["deadline_date"].isoformat()
        serialized_items.append(item_copy)

    return jsonify({
        "success": True,
        "total_extracted": len(items),
        "action_items": serialized_items
    })


@api_bp.route("/meetings/<int:meeting_id>")
def api_get_meeting(meeting_id: int):
    """
    Returns complete details of a specific meeting including action items.
    """
    meeting = db.get_or_404(Meeting, meeting_id)
    return jsonify(meeting.to_dict(include_items=True))


@api_bp.route("/analytics")
def api_analytics_data():
    """
    Returns aggregated JSON analytics ready for frontend Chart.js visualization.
    """
    all_items = ActionItem.query.all()
    
    completed = sum(1 for i in all_items if i.status == "Completed")
    pending = sum(1 for i in all_items if i.status == "Pending" and not i.is_overdue)
    overdue = sum(1 for i in all_items if i.is_overdue)

    # Owner workload top 8
    owner_dict = {}
    for item in all_items:
        owner = item.owner or "Unassigned"
        if owner not in owner_dict:
            owner_dict[owner] = {"completed": 0, "pending": 0, "overdue": 0}
        if item.status == "Completed":
            owner_dict[owner]["completed"] += 1
        elif item.is_overdue:
            owner_dict[owner]["overdue"] += 1
        else:
            owner_dict[owner]["pending"] += 1

    top_owners = sorted(
        owner_dict.items(),
        key=lambda x: x[1]["completed"] + x[1]["pending"] + x[1]["overdue"],
        reverse=True
    )[:8]

    owner_labels = [o[0] for o in top_owners]
    owner_completed = [o[1]["completed"] for o in top_owners]
    owner_pending = [o[1]["pending"] for o in top_owners]
    owner_overdue = [o[1]["overdue"] for o in top_owners]

    # Confidence distribution
    high_conf = sum(1 for i in all_items if i.confidence >= 0.75)
    med_conf = sum(1 for i in all_items if 0.50 <= i.confidence < 0.75)
    low_conf = sum(1 for i in all_items if i.confidence < 0.50)

    # Quality flags
    unassigned = sum(1 for i in all_items if i.missing_owner or i.owner == "Unassigned")
    no_deadline = sum(1 for i in all_items if i.missing_deadline or i.deadline == "Not specified")
    duplicates = sum(1 for i in all_items if i.is_duplicate)

    return jsonify({
        "status_distribution": {
            "labels": ["Completed", "Pending", "Overdue"],
            "data": [completed, pending, overdue],
            "colors": ["#10B981", "#F59E0B", "#EF4444"]
        },
        "owner_workload": {
            "labels": owner_labels,
            "completed": owner_completed,
            "pending": owner_pending,
            "overdue": owner_overdue
        },
        "confidence_distribution": {
            "labels": ["High (>=75%)", "Medium (50-74%)", "Low (<50%)"],
            "data": [high_conf, med_conf, low_conf],
            "colors": ["#10B981", "#3B82F6", "#F59E0B"]
        },
        "quality_metrics": {
            "unassigned": unassigned,
            "no_deadline": no_deadline,
            "duplicates": duplicates
        }
    })


@api_bp.route("/export/all/csv")
def api_export_all_csv():
    """
    Exports all action items across all meetings in CSV format.
    """
    items = ActionItem.query.order_by(ActionItem.created_at.desc()).all()
    csv_buffer = export_to_csv(items, meeting_title="All Meetings")
    filename = f"all_action_items_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    response = make_response(csv_buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


@api_bp.route("/export/all/json")
def api_export_all_json():
    """
    Exports all meetings and action items in JSON format.
    """
    meetings = Meeting.query.order_by(Meeting.created_at.desc()).all()
    data = {
        "export_date": datetime.utcnow().isoformat() + "Z",
        "total_meetings": len(meetings),
        "meetings": [m.to_dict(include_items=True) for m in meetings]
    }
    filename = f"all_meetings_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    response = make_response(jsonify(data))
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
