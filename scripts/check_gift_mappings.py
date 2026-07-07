"""Check gift card mappings in InefableStore"""
import sys
sys.path.insert(0, '/home/apps/web-a-inefablestore')
from app import app, db

with app.app_context():
    with db.engine.connect() as conn:
        # Show all packages with direct_to_pin or gift category
        pkgs = conn.execute(db.text(
            "SELECT id, name, direct_to_pin, category FROM store_packages WHERE direct_to_pin = 1 OR category = 'gift' ORDER BY id"
        )).fetchall()

        for pkg in pkgs:
            print(f"Pkg {pkg[0]}: {pkg[1]} | direct_to_pin={pkg[2]} | category={pkg[3]}")
            items = conn.execute(db.text(
                "SELECT id, title FROM game_packages WHERE store_package_id = :pid ORDER BY id"
            ), {"pid": pkg[0]}).fetchall()
            for item in items:
                mapping = conn.execute(db.text(
                    "SELECT id, remote_package_id, direct_to_pin, auto_enabled, active FROM rev_item_mappings WHERE store_item_id = :iid"
                ), {"iid": item[0]}).fetchone()
                if mapping:
                    print(f"  Item {item[0]}: {item[1]} -> mapping#{mapping[0]} remote={mapping[1]} dp={mapping[2]} auto={mapping[3]} active={mapping[4]}")
                else:
                    print(f"  Item {item[0]}: {item[1]} -> NO MAPPING")
