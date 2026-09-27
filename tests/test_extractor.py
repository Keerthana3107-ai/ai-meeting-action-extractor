import pytest
from datetime import datetime
from app import create_app
from models.database import db
from models.meeting import Meeting
from models.action_item import ActionItem
from services.nlp_extractor import extract_action_items
from services.export_service import export_to_csv, export_to_json, export_to_pdf


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_meeting_and_action_item_models(app):
    with app.app_context():
        meeting = Meeting(
            title="Sprint Planning Meeting",
            transcript="Arun will prepare the API documentation by Friday.",
            file_name="direct_input.txt",
            file_type="txt",
            meeting_date=datetime(2024, 10, 15),
            created_at=datetime.utcnow()
        )
        db.session.add(meeting)
        db.session.commit()

        item = ActionItem(
            meeting_id=meeting.id,
            task="Prepare the API documentation",
            owner="Arun",
            deadline="Friday",
            status="Pending",
            confidence=0.95,
            source_sentence="Arun will prepare the API documentation by Friday.",
            validation_message=None,
            missing_owner=False,
            missing_deadline=False,
            is_duplicate=False
        )
        db.session.add(item)
        db.session.commit()

        # Check relationships
        retrieved_meeting = db.session.get(Meeting, meeting.id)
        assert len(retrieved_meeting.action_items) == 1
        assert retrieved_meeting.action_items[0].task == "Prepare the API documentation"
        assert item.meeting.title == "Sprint Planning Meeting"

        # Check serialization
        item_dict = item.to_dict()
        assert item_dict["task"] == "Prepare the API documentation"
        assert item_dict["owner"] == "Arun"
        assert item_dict["deadline"] == "Friday"
        assert "validation_message" in item_dict


def test_sample_extraction(app):
    transcript = (
        "David (Product Lead): Good morning everyone. "
        "Arun will prepare the API documentation by Friday. "
        "Priya is responsible for the presentation deck. "
        "John needs to send the report by Monday."
    )
    items = extract_action_items(transcript, similarity_threshold=0.75)
    assert len(items) >= 3

    tasks = [i["task"] for i in items]
    owners = [i["owner"] for i in items]
    assert "Arun" in owners
    assert any("API documentation" in t for t in tasks)


def test_routes(client, app):
    with app.app_context():
        meeting = Meeting(
            title="Test Sync",
            transcript="Test transcript content",
            meeting_date=datetime.utcnow()
        )
        db.session.add(meeting)
        db.session.commit()

        item = ActionItem(
            meeting_id=meeting.id,
            task="Review code",
            owner="David",
            deadline="tomorrow",
            status="Pending",
            confidence=0.9
        )
        db.session.add(item)
        db.session.commit()

        # Test GET routes
        assert client.get("/").status_code == 200
        assert client.get("/extract").status_code == 200
        assert client.get("/history").status_code == 200
        assert client.get("/analytics").status_code == 200
        assert client.get("/api/analytics").status_code == 200
        assert client.get(f"/meetings/{meeting.id}").status_code == 200
        assert client.get(f"/meetings/{meeting.id}/export/csv").status_code == 200
        assert client.get(f"/meetings/{meeting.id}/export/json").status_code == 200
        assert client.get(f"/meetings/{meeting.id}/export/pdf").status_code == 200

        # Test status toggle
        res = client.post(f"/action-items/{item.id}/toggle-status", headers={"X-Requested-With": "XMLHttpRequest"})
        assert res.status_code == 200
        assert res.get_json()["status"] == "Completed"
