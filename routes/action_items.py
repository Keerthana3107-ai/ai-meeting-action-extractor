from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, jsonify

from models.database import db
from models.action_item import ActionItem
from models.meeting import Meeting
from services.nlp_extractor import parse_deadline

action_items_bp = Blueprint("action_items", __name__, url_prefix="/action-items")


@action_items_bp.route("/<int:item_id>/toggle-status", methods=["POST"])
def toggle_status(item_id: int):
    """
    Toggles the status of an action item between Pending and Completed.
    Supports both traditional POST forms and AJAX requests.
    """
    item = db.get_or_404(ActionItem, item_id)
    new_status = "Completed" if item.status != "Completed" else "Pending"
    item.status = new_status
    item.updated_at = datetime.utcnow()
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "id": item.id,
            "status": item.current_status,
            "raw_status": item.status,
            "is_overdue": item.is_overdue
        })

    flash(f"Task marked as '{new_status}'.", "success")
    return redirect(request.referrer or url_for("meetings.view_meeting", meeting_id=item.meeting_id))


@action_items_bp.route("/<int:item_id>/edit", methods=["POST"])
def edit_action_item(item_id: int):
    """
    Updates the task description, owner, deadline, and status of an action item.
    Re-evaluates deadline dates and validation flags dynamically.
    """
    item = db.get_or_404(ActionItem, item_id)

    data = request.get_json() if request.is_json else request.form

    task = data.get("task", "").strip()
    owner = data.get("owner", "").strip()
    deadline = data.get("deadline", "").strip()
    status = data.get("status", "Pending").strip()

    if not task:
        if request.is_json:
            return jsonify({"success": False, "error": "Task description cannot be empty"}), 400
        flash("Task description cannot be empty.", "warning")
        return redirect(request.referrer or url_for("meetings.view_meeting", meeting_id=item.meeting_id))

    item.task = task
    item.owner = owner if owner else "Unassigned"
    item.status = status if status in ["Pending", "Completed"] else "Pending"

    # Deadline handling
    if deadline:
        item.deadline = deadline
    else:
        item.deadline = "Not specified"

    # Update quality flags and validation message
    item.missing_owner = (item.owner == "Unassigned")
    item.missing_deadline = (item.deadline == "Not specified")

    msgs = []
    if item.missing_owner:
        msgs.append("Missing owner")
    if item.missing_deadline:
        msgs.append("Missing deadline")
    if item.is_duplicate:
        msgs.append("Potential duplicate task")
    item.validation_message = "; ".join(msgs) if msgs else None

    item.updated_at = datetime.utcnow()

    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "item": item.to_dict()
        })

    flash("Action item updated successfully.", "success")
    return redirect(request.referrer or url_for("meetings.view_meeting", meeting_id=item.meeting_id))


@action_items_bp.route("/<int:item_id>/delete", methods=["POST"])
def delete_action_item(item_id: int):
    """
    Deletes an individual action item.
    """
    item = db.get_or_404(ActionItem, item_id)
    meeting_id = item.meeting_id
    db.session.delete(item)
    db.session.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "id": item_id})

    flash("Action item removed.", "info")
    return redirect(request.referrer or url_for("meetings.view_meeting", meeting_id=meeting_id))


@action_items_bp.route("/create", methods=["POST"])
def create_action_item():
    """
    Allows manually adding an action item to an existing meeting.
    """
    meeting_id = request.form.get("meeting_id")
    meeting = db.get_or_404(Meeting, meeting_id)

    task = request.form.get("task", "").strip()
    owner = request.form.get("owner", "").strip() or "Unassigned"
    deadline = request.form.get("deadline", "").strip() or "Not specified"
    status = request.form.get("status", "Pending")

    if not task:
        flash("Task description cannot be empty.", "warning")
        return redirect(url_for("meetings.view_meeting", meeting_id=meeting.id))

    deadline_str = deadline if deadline else "Not specified"
    missing_owner = (owner == "Unassigned")
    missing_deadline = (deadline_str == "Not specified")

    msgs = []
    if missing_owner:
        msgs.append("Missing owner")
    if missing_deadline:
        msgs.append("Missing deadline")
    val_msg = "; ".join(msgs) if msgs else None

    new_item = ActionItem(
        meeting_id=meeting.id,
        task=task,
        owner=owner,
        deadline=deadline_str,
        status=status,
        confidence=1.0,  # User-created item has 100% confidence
        validation_message=val_msg,
        missing_owner=missing_owner,
        missing_deadline=missing_deadline,
        is_duplicate=False
    )
    db.session.add(new_item)
    db.session.commit()

    flash("Manual action item created successfully.", "success")
    return redirect(url_for("meetings.view_meeting", meeting_id=meeting.id))
