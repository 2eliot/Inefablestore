import psycopg2
conn = psycopg2.connect('postgresql://inefable_user:InefablePg2026@127.0.0.1:5432/inefablestore')
cur = conn.cursor()

# Enable Roblox mappings (items 32-36) and fix remote_package_id for 35-36
# Items 35-36 have remote_package_id=51,52 -> should be 1 for paquetes_stock Robux
cur.execute("""
    UPDATE rev_item_mappings 
    SET active=TRUE, auto_enabled=TRUE, direct_to_pin=TRUE, remote_package_id=1
    WHERE store_item_id IN (32,33,34,35,36)
""")
conn.commit()

# Verify
cur.execute("SELECT id, store_item_id, remote_package_id, auto_enabled, direct_to_pin, active FROM rev_item_mappings WHERE store_item_id IN (32,33,34,35,36) ORDER BY id")
for r in cur.fetchall(): print(r)

cur.close()
conn.close()
print("Done - Roblox mappings enabled")
