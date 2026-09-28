# extensions.py – Pathfinder shared extensions
# We create 'db' HERE in its own file so that both app.py and models.py
# can import it without creating a circular import.
#
# Circular import problem (why this file exists):
#   app.py imports models.py  ← models need 'db'
#   if models.py imported from app.py to get 'db', Python would see:
#     app.py → models.py → app.py → (not finished yet!) → ERROR
#   Putting 'db' in extensions.py breaks that loop.

from flask_sqlalchemy import SQLAlchemy

# Create the SQLAlchemy object. It has no app attached yet.
# We attach it to the Flask app later in app.py using db.init_app(app).
db = SQLAlchemy()
