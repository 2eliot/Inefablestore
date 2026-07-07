"""Add subcat columns to store_packages and game_packages."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE store_packages ADD COLUMN subcat_label_a VARCHAR(60) DEFAULT "Diamantes"'))
        except Exception:
            pass  # column already exists
        try:
            conn.execute(text('ALTER TABLE store_packages ADD COLUMN subcat_label_b VARCHAR(60) DEFAULT "Tarjetas"'))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE game_packages ADD COLUMN is_subcat_b BOOLEAN DEFAULT FALSE"))
        except Exception:
            pass
        conn.commit()
    print("Migration done")
