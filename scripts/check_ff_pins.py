import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')
conn.row_factory = sqlite3.Row

# Check pines_freefire_global structure
cur = conn.execute("SELECT * FROM pines_freefire_global LIMIT 1")
print("pines_freefire_global columns:", [d[0] for d in cur.description])

# Count by monto_id
cur = conn.execute("SELECT monto_id, COUNT(*) as cnt FROM pines_freefire_global WHERE usado=0 GROUP BY monto_id")
for r in cur.fetchall():
    print(f"  monto_id={r['monto_id']}, available={r['cnt']}")

# Check pines_freefire
cur = conn.execute("SELECT COUNT(*) FROM pines_freefire WHERE usado=0")
print(f"pines_freefire available: {cur.fetchone()[0]}")

conn.close()
