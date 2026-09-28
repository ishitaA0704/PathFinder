# models.py – Pathfinder database models
# Each class here becomes one table in the SQLite database.
# SQLAlchemy reads these class definitions and creates the matching SQL tables.

from datetime import datetime, timezone

# 'db' is the SQLAlchemy object we create in app.py.
# We import it here so both files share the SAME db instance.
from extensions import db


class FocusSession(db.Model):
    """
    Represents a study session the user has started.
    Each row = one topic the user decided to focus on.

    SQL equivalent:
        CREATE TABLE focus_session (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            topic      TEXT    NOT NULL,
            started_at DATETIME
        );
    """

    # __tablename__ tells SQLAlchemy what to call the table in SQLite.
    # Without it, SQLAlchemy would guess a name from the class name.
    __tablename__ = "focus_session"

    # db.Column defines one column. The first argument is the SQL data type.
    # primary_key=True means SQLite will auto-number these rows (1, 2, 3 …).
    id = db.Column(db.Integer, primary_key=True)

    # nullable=False means the database will REFUSE to save a row without a topic.
    topic = db.Column(db.String(255), nullable=False)

    # default= is evaluated by Python, not SQL, when you create a new row in code.
    # timezone.utc ensures we always store UTC, avoiding timezone bugs.
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Return a plain Python dictionary so Flask can serialize it to JSON."""
        return {
            "id": self.id,
            "topic": self.topic,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


class VideoLog(db.Model):
    """
    One row is saved every time the extension checks a YouTube video title.
    This lets us show a history of blocked/allowed videos for the demo.

    SQL equivalent:
        CREATE TABLE video_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            focus_topic TEXT    NOT NULL,
            score       REAL    NOT NULL,
            allowed     BOOLEAN NOT NULL,
            mode_used   TEXT    NOT NULL,
            created_at  DATETIME
        );
    """

    __tablename__ = "video_log"

    id = db.Column(db.Integer, primary_key=True)

    # The YouTube video title sent by the extension.
    title = db.Column(db.String(500), nullable=False)

    # The topic the user set in the extension popup.
    focus_topic = db.Column(db.String(255), nullable=False)

    # The relevance score: a float between 0.0 and 1.0.
    # db.Float maps to SQL REAL (a decimal number column).
    score = db.Column(db.Float, nullable=False)

    # True if the video was allowed, False if it was blocked.
    # db.Boolean maps to SQL INTEGER (0 or 1) in SQLite.
    allowed = db.Column(db.Boolean, nullable=False)

    # Which scorer produced the result: "gemini" or "fallback".
    mode_used = db.Column(db.String(50), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Return a plain Python dictionary so Flask can serialize it to JSON."""
        return {
            "id": self.id,
            "title": self.title,
            "focus_topic": self.focus_topic,
            "score": self.score,
            "allowed": self.allowed,
            "mode_used": self.mode_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
