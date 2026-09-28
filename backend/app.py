# app.py – Pathfinder Flask backend entry point
# Run this file to start the server: python app.py
# The server listens on http://127.0.0.1:5000

import os

from dotenv import load_dotenv  # reads key=value pairs from a .env file into os.environ
from flask import Flask, jsonify, request
from flask_cors import CORS  # allows the Chrome extension (a different "origin") to call us

from extensions import db  # the shared SQLAlchemy object
from models import VideoLog  # the table we write to on every /check-title call
from services.gemini_client import GeminiUnavailableError, get_gemini_score
from services.fallback_classifier import score_title

# ---------------------------------------------------------------------------
# CONSTANT: the single place that controls "allowed vs. blocked"
# Keeping it here means you only change one number to adjust sensitivity.
# ---------------------------------------------------------------------------
RELEVANCE_THRESHOLD = 0.6


def create_app():
    """
    Factory function: builds and configures the Flask app.
    Using a factory (instead of module-level code) makes the app easier to test
    and avoids problems with global state.
    """

    # Step 1 – Load environment variables from the .env file.
    # After this call, os.environ["GEMINI_API_KEY"] will work if the key is in .env.
    load_dotenv()

    # Step 2 – Create the Flask application object.
    # __name__ tells Flask where to look for templates and static files.
    app = Flask(__name__)

    # Step 3 – Configure the SQLite database.
    # Flask uses app.config as a dictionary of settings.
    # SQLALCHEMY_DATABASE_URI tells SQLAlchemy which database file to use.
    # "sqlite:///pathfinder.db" means: SQLite, stored in the Flask "instance" folder
    # (Flask auto-creates a folder called 'instance/' next to app.py for database files).
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pathfinder.db"

    # Disable a feature that tracks every database modification; we don't need it
    # and leaving it on prints annoying deprecation warnings.
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Step 4 – Attach the SQLAlchemy object to THIS Flask app.
    # Until now, 'db' in extensions.py had no app; db.init_app() links them.
    db.init_app(app)

    # Step 5 – Enable CORS (Cross-Origin Resource Sharing).
    # Browsers block requests from one origin (e.g. the extension) to another
    # (localhost:5000) by default. CORS(app) adds the headers that lift that block.
    CORS(app)

    # Step 6 – Create the database tables.
    # WHY app_context: Flask keeps a "context" (a bundle of per-request globals like
    # current_app, g, and the database connection). Outside of a request, that context
    # doesn't exist automatically. db.create_all() needs to reach 'app.config' through
    # that context, so we manually push one with app.app_context().
    # Think of it as: "Hey Flask, pretend we're inside a request so db can work."
    with app.app_context():
        # Reads all the db.Model subclasses (FocusSession, VideoLog) and issues
        # CREATE TABLE IF NOT EXISTS for each one. Safe to call on every startup.
        db.create_all()

    # -----------------------------------------------------------------------
    # ROUTES
    # -----------------------------------------------------------------------

    @app.route("/health", methods=["GET"])
    def health():
        """
        A simple heartbeat endpoint.
        Useful to confirm the server is running before you test anything else.
        """
        return jsonify({"status": "ok"})

    @app.route("/check-title", methods=["POST"])
    def check_title():
        """
        Main endpoint. The extension calls this with a video title and a focus topic.
        Returns whether the video is allowed and the relevance score.

        Request body (JSON):
            { "title": "...", "focus_topic": "..." }

        Response (JSON):
            { "allowed": true/false, "score": 0.0-1.0, "mode": "gemini"|"fallback" }
        """

        # request.get_json() parses the incoming HTTP body as JSON.
        # If the body is not valid JSON, it returns None.
        data = request.get_json()

        # Guard clause: if the body was empty or not JSON, tell the caller clearly.
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        # Pull the two required fields out of the JSON dictionary.
        # .get() returns None if the key doesn't exist (safer than data["title"]).
        title = data.get("title")
        focus_topic = data.get("focus_topic")

        # Validate: both fields must be present AND non-empty strings.
        if not title or not focus_topic:
            return (
                jsonify(
                    {
                        "error": "Both 'title' and 'focus_topic' are required and must be non-empty strings."
                    }
                ),
                400,  # 400 Bad Request is the correct HTTP status for invalid input
            )

        # ── Scoring ──────────────────────────────────────────────────────────
        # Read FORCE_FALLBACK from the environment each request (not once at startup)
        # so you can toggle it by editing .env and restarting, handy for demos.
        force_fallback = os.environ.get("FORCE_FALLBACK", "false").lower() == "true"

        if force_fallback:
            # Skip Gemini entirely.  Useful when demoing offline or when you
            # want a deterministic result without burning API quota.
            score = score_title(title, focus_topic)
            mode = "fallback"
        else:
            # ── Try Gemini first ─────────────────────────────────────────────
            # The try block runs normally.  If Gemini works, 'mode' becomes
            # "gemini" and we skip the except block entirely.
            try:
                score = get_gemini_score(title, focus_topic)
                mode = "gemini"

            except GeminiUnavailableError as e:
                # ── Fallback ─────────────────────────────────────────────────
                # Gemini failed for SOME reason (no key, no internet, timeout,
                # rate limit, bad response).  We don't crash – we gracefully
                # switch to the local classifier.
                # 'as e' captures the error message so we can log it to the
                # server console for debugging, but we don't expose it to the
                # extension (no need to leak internal errors).
                print(f"[Pathfinder] Gemini unavailable, using fallback. Reason: {e}")
                score = score_title(title, focus_topic)
                mode = "fallback"

        # Apply the threshold: score >= 0.6 means "on your path", allow the video.
        allowed = score >= RELEVANCE_THRESHOLD

        # ── Persist to database ───────────────────────────────────────────────
        # Create a new VideoLog object (this does NOT write to the DB yet).
        log_entry = VideoLog(
            title=title,
            focus_topic=focus_topic,
            score=score,
            allowed=allowed,
            mode_used=mode,
        )

        # db.session is a staging area ("unit of work").
        # add() says "include this object in the next commit".
        db.session.add(log_entry)

        # commit() actually writes the row to the SQLite file and closes the transaction.
        db.session.commit()

        # Return the result to the extension.
        return jsonify({"allowed": allowed, "score": score, "mode": mode})

    @app.route("/logs", methods=["GET"])
    def get_logs():
        """
        Returns the last 20 video checks as JSON.
        Useful for demoing the database during the hackathon pitch.
        """

        # Query the video_log table, sort by newest first, take only 20 rows.
        # .all() executes the SQL and returns a Python list of VideoLog objects.
        logs = VideoLog.query.order_by(VideoLog.created_at.desc()).limit(20).all()

        # Convert each SQLAlchemy object to a plain dict so jsonify can handle it.
        return jsonify([log.to_dict() for log in logs])

    return app

# Entry point
# Only runs when you execute "python app.py" directly,
# NOT when a WSGI server (like gunicorn) imports this file.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    # debug=True: auto-reloads the server when you save a file and shows
    # detailed error pages. NEVER use debug=True in production.
    app.run(debug=True, port=5000)
