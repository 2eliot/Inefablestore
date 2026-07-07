import psycopg2
conn = psycopg2.connect('postgresql://inefable_user:InefablePg2026@127.0.0.1:5432/inefablestore')
cur = conn.cursor()
# Columns first
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='rev_catalog_items' ORDER BY ordinal_position")
print("rev_catalog_items:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT * FROM rev_catalog_items WHERE store_package_id=3 ORDER BY id")
for r in cur.fetchall(): print("ITEM:", r)

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='rev_item_mappings' ORDER BY ordinal_position")
print("rev_item_mappings:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT * FROM rev_item_mappings ORDER BY id LIMIT 5")
for r in cur.fetchall(): print("MAP:", r)

cur.close()
conn.close()

