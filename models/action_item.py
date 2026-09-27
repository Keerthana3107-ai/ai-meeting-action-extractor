import re
from datetime import datetime, date
from typing import Optional, Any, Union
from models.database import db

if False:
    from models.meeting import Meeting


class ActionItem(db.Model):
    __tablename__ = "action_items"

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    task = db.Column(db.Text, nullable=False)
    owner = db.Column(db.String(120), nullable=False, default="Unassigned")
    deadline = db.Column(db.String(100), nullable=False, default="Not specified")
    status = db.Column(db.String(50), nullable=False, default="Pending")
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    source_sentence = db.Column(db.Text, nullable=True)
    validation_message = db.Column(db.String(255), nullable=True)
    
    # Validation and Quality Flags
    missing_owner = db.Column(db.Boolean, default=False)
    missing_deadline = db.Column(db.Boolean, default=False)
    is_duplicate = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(
        self,
        task: str = "",
        owner: str = "Unassigned",
        deadline: str = "Not specified",
        status: str = "Pending",
        confidence: float = 0.0,
        source_sentence: Optional[str] = None,
        validation_message: Optional[str] = None,
        meeting_id: Optional[int] = None,
        missing_owner: Optional[bool] = None,
        missing_deadline: Optional[bool] = None,
        is_duplicate: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        deadline_date: Optional[Any] = None,
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self.task = task
        self.owner = owner or "Unassigned"
        
        # Consistent deadline handling: accept deadline or deadline_date
        if deadline and deadline != "Not specified":
            self.deadline = deadline
        elif deadline_date:
            self.deadline = deadline_date.isoformat() if hasattr(deadline_date, "isoformat") else str(deadline_date)
        else:
            self.deadline = "Not specified"

        self.status = status or "Pending"
        self.confidence = float(confidence) if confidence is not None else 0.0
        self.source_sentence = source_sentence

        # Quality flags
        if missing_owner is not None:
            self.missing_owner = missing_owner
        else:
            self.missing_owner = (self.owner in ["Unassigned", "", None])

        if missing_deadline is not None:
            self.missing_deadline = missing_deadline
        else:
            self.missing_deadline = (self.deadline in ["Not specified", "", None])

        self.is_duplicate = bool(is_duplicate)

        # Validation message
        if validation_message is not None:
            self.validation_message = validation_message
        else:
            msgs = []
            if self.missing_owner:
                msgs.append("Missing owner")
            if self.missing_deadline:
                msgs.append("Missing deadline")
            if self.is_duplicate:
                msgs.append("Potential duplicate task")
            self.validation_message = "; ".join(msgs) if msgs else None

        if meeting_id is not None:
            self.meeting_id = meeting_id

        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def deadline_date(self) -> Optional[date]:
        """
        Dynamically resolves a date object from the deadline string for overdue calculation and sorting.
        """
        if not self.deadline or self.deadline == "Not specified":
            return None
        # Try ISO format YYYY-MM-DD
        try:
            match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", self.deadline)
            if match:
                return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except Exception:
            pass
        # Fallback to dateparser
        try:
            import dateparser
            parsed = dateparser.parse(self.deadline, settings={"PREFER_DATES_FROM": "future"})
            if parsed:
                return parsed.date()
        except Exception:
            pass
        return None

    @deadline_date.setter
    def deadline_date(self, value: Optional[Any]):
        if value is None:
            if self.deadline and re.match(r"^\d{4}-\d{2}-\d{2}$", self.deadline):
                self.deadline = "Not specified"
        elif hasattr(value, "isoformat"):
            self.deadline = value.isoformat()
        else:
            self.deadline = str(value)

    @property
    def is_overdue(self) -> bool:
        """Returns True if the deadline date is strictly before today and status is not Completed."""
        if self.status == "Completed":
            return False
        d = self.deadline_date
        if d:
            return d < date.today()
        return False

    @property
    def current_status(self) -> str:
        """Calculates effective status, returning Overdue if past deadline."""
        if self.status == "Completed":
            return "Completed"
        if self.is_overdue:
            return "Overdue"
        return self.status

    def to_dict(self):
        d_date = self.deadline_date
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "meeting_title": self.meeting.title if self.meeting else None,
            "task": self.task,
            "owner": self.owner,
            "deadline": self.deadline,
            "deadline_date": d_date.isoformat() if d_date else None,
            "status": self.current_status,
            "raw_status": self.status,
            "is_overdue": self.is_overdue,
            "confidence": round(self.confidence, 2),
            "confidence_percent": int(round(self.confidence * 100)),
            "source_sentence": self.source_sentence,
            "validation_message": self.validation_message,
            "missing_owner": self.missing_owner or (self.owner in ["Unassigned", "", None]),
            "missing_deadline": self.missing_deadline or (self.deadline in ["Not specified", "", None]),
            "is_duplicate": self.is_duplicate,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ActionItem {self.id}: {self.task[:30]} ({self.owner})>"
