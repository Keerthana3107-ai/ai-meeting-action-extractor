from datetime import datetime, date
from flask import Blueprint, render_template, request, current_app
from sqlalchemy import func

from models.database import db
from models.meeting import Meeting
from models.action_item import ActionItem

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    """
    Main executive dashboard showing aggregated action-item statistics,
    health indicators, recent meetings, and urgent overdue items.
    """
    total_meetings = Meeting.query.count()
    all_items = ActionItem.query.all()
    total_items = len(all_items)

    completed_items = [i for i in all_items if i.status == "Completed"]
    completed_count = len(completed_items)
    
    # Overdue items
    overdue_items = [i for i in all_items if i.is_overdue]
    overdue_count = len(overdue_items)

    # Pending (excluding overdue for clean separation in UI)
    pending_count = sum(1 for i in all_items if i.status == "Pending" and not i.is_overdue)

    # Completion rate
    completion_rate = int(round((completed_count / total_items * 100))) if total_items > 0 else 0

    # Average confidence score
    avg_confidence = int(round((sum(i.confidence for i in all_items) / total_items * 100))) if total_items > 0 else 0

    # Quality flags
    unassigned_count = sum(1 for i in all_items if i.missing_owner or i.owner == "Unassigned")
    missing_deadlines_count = sum(1 for i in all_items if i.missing_deadline or i.deadline == "Not specified")
    duplicate_count = sum(1 for i in all_items if i.is_duplicate)

    # Recent meetings (last 5)
    recent_meetings = Meeting.query.order_by(Meeting.created_at.desc()).limit(5).all()

    # Urgent action items: Overdue or due soon (limit 6)
    urgent_items = sorted(
        [i for i in all_items if i.status != "Completed"],
        key=lambda x: (0 if x.is_overdue else 1, x.deadline_date or date.max)
    )[:6]

    return render_template(
        "dashboard.html",
        total_meetings=total_meetings,
        total_items=total_items,
        completed_count=completed_count,
        pending_count=pending_count,
        overdue_count=overdue_count,
        completion_rate=completion_rate,
        avg_confidence=avg_confidence,
        unassigned_count=unassigned_count,
        missing_deadlines_count=missing_deadlines_count,
        duplicate_count=duplicate_count,
        recent_meetings=recent_meetings,
        urgent_items=urgent_items
    )


@main_bp.route("/extract")
def extract_page():
    """
    Dedicated action item extraction studio:
    Supports file upload (.txt, .pdf, .docx), pasting raw transcript,
    and 1-click Sample Meeting Demo.
    """
    return render_template("extract.html")


@main_bp.route("/history")
def history():
    """
    Meeting history archive with live search, sorting, and item breakdowns.
    """
    search_query = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "newest")

    query = Meeting.query

    if search_query:
        query = query.filter(
            Meeting.title.ilike(f"%{search_query}%") |
            Meeting.transcript.ilike(f"%{search_query}%") |
            Meeting.file_name.ilike(f"%{search_query}%")
        )

    if sort_by == "oldest":
        query = query.order_by(Meeting.created_at.asc())
    elif sort_by == "title":
        query = query.order_by(Meeting.title.asc())
    else:  # newest
        query = query.order_by(Meeting.created_at.desc())

    meetings = query.all()

    return render_template(
        "history.html",
        meetings=meetings,
        search_query=search_query,
        sort_by=sort_by,
        total_meetings=len(meetings)
    )


@main_bp.route("/analytics")
def analytics():
    """
    Comprehensive visual analytics view tracking workload distribution,
    deadline adherence, model confidence brackets, and resolution velocity.
    """
    all_items = ActionItem.query.all()
    all_meetings = Meeting.query.all()

    total_tasks = len(all_items)
    completed_tasks = sum(1 for i in all_items if i.status == "Completed")
    overdue_tasks = sum(1 for i in all_items if i.is_overdue)
    pending_tasks = sum(1 for i in all_items if i.status == "Pending" and not i.is_overdue)

    # Workload breakdown by owner
    owner_stats = {}
    for item in all_items:
        owner = item.owner or "Unassigned"
        if owner not in owner_stats:
            owner_stats[owner] = {"total": 0, "completed": 0, "pending": 0, "overdue": 0}
        owner_stats[owner]["total"] += 1
        if item.status == "Completed":
            owner_stats[owner]["completed"] += 1
        elif item.is_overdue:
            owner_stats[owner]["overdue"] += 1
        else:
            owner_stats[owner]["pending"] += 1

    sorted_owners = sorted(owner_stats.items(), key=lambda x: x[1]["total"], reverse=True)

    # Confidence distribution
    high_conf = sum(1 for i in all_items if i.confidence >= 0.75)
    med_conf = sum(1 for i in all_items if 0.50 <= i.confidence < 0.75)
    low_conf = sum(1 for i in all_items if i.confidence < 0.50)

    avg_confidence = round(sum(i.confidence for i in all_items) / total_tasks * 100, 1) if total_tasks > 0 else 0

    return render_template(
        "analytics.html",
        total_tasks=total_tasks,
        total_meetings=len(all_meetings),
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        overdue_tasks=overdue_tasks,
        avg_confidence=avg_confidence,
        owner_stats=sorted_owners,
        high_conf=high_conf,
        med_conf=med_conf,
        low_conf=low_conf
    )
