from datetime import datetime
from typing import List, Optional, Any
from models.database import db

if False:
    from models.action_item import ActionItem


class Meeting(db.Model):
    __tablename__ = "meetings"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, default="Untitled Meeting")
    transcript = db.Column(db.Text, nullable=False)
    file_name = db.Column(db.String(255), default="Direct Input")
    file_type = db.Column(db.String(50), default="text")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    meeting_date = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to ActionItem (1 Meeting -> Many ActionItems)
    action_items = db.relationship(
        "ActionItem",
        backref="meeting",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="ActionItem.id"
    )

    def __init__(
        self,
        title: str = "Untitled Meeting",
        transcript: str = "",
        file_name: str = "Direct Input",
        file_type: str = "text",
        meeting_date: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self.title = title or "Untitled Meeting"
        self.transcript = transcript or ""
        self.file_name = file_name or "Direct Input"
        self.file_type = file_type or "text"
        self.meeting_date = meeting_date or datetime.utcnow()
        self.created_at = created_at or datetime.utcnow()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self, include_items: bool = True):
        items = self.action_items or []
        data = {
            "id": self.id,
            "title": self.title,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "meeting_date": self.meeting_date.strftime("%Y-%m-%d") if self.meeting_date else None,
            "transcript_snippet": (self.transcript[:180] + "...") if len(self.transcript) > 180 else self.transcript,
            "total_action_items": len(items),
            "pending_count": sum(1 for item in items if item.status == "Pending"),
            "completed_count": sum(1 for item in items if item.status == "Completed"),
            "overdue_count": sum(1 for item in items if item.is_overdue),
        }
        if include_items:
            data["transcript"] = self.transcript
            data["action_items"] = [item.to_dict() for item in items]
        return data

    def __repr__(self):
        return f"<Meeting {self.id}: {self.title}>"
