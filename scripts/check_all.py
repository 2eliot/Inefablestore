import psycopg2
conn = psycopg2.connect('postgresql://inefable_user:InefablePg2026@127.0.0.1:5432/inefablestore')
cur = conn.cursor()

# Check all tables columns quickly
for tbl in ['store_packages', 'game_packages', 'rev_item_mappings', 'rev_catalog_items']:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (tbl,))
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n{tbl}: {cols}")

print("\n=== store_packages (categories) ===")
cur.execute("SELECT id, name, direct_to_pin FROM store_packages ORDER BY id")
for r in cur.fetchall(): print(r)

print("\n=== game_packages (items for sale) ===")
cur.execute("SELECT id, store_package_id, title, price FROM game_packages ORDER BY id LIMIT 10")
for r in cur.fetchall(): print(r)

print("\n=== game_packages for Roblox (store_package_id=3) ===")
cur.execute("SELECT id, store_package_id, title, price FROM game_packages WHERE store_package_id=3 ORDER BY id")
for r in cur.fetchall(): print(r)

print("\n=== rev_item_mappings (all) ===")
cur.execute("SELECT id, store_item_id, remote_product_id, remote_package_id, auto_enabled, direct_to_script, direct_to_pin, active FROM rev_item_mappings ORDER BY id")
for r in cur.fetchall(): print(r)

cur.close()
conn.close()
