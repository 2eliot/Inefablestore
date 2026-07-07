import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')

for table in ['pines_freefire', 'pines_freefire_global', 'precios_freefire_global', 'precios_freefire_id']:
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"{table}: {cur.fetchone()[0]} rows")

cur = conn.execute("SELECT COUNT(*) FROM precios_freefire_global WHERE activo=1")
print(f"precios_freefire_global active: {cur.fetchone()[0]}")

cur = conn.execute("SELECT id, nombre, precio FROM precios_freefire_global WHERE activo=1 LIMIT 10")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}, ${r[2]}")

cur = conn.execute("SELECT COUNT(*) FROM precios_freefire_id WHERE activo=1")
print(f"precios_freefire_id active: {cur.fetchone()[0]}")

cur = conn.execute("SELECT id, nombre, precio FROM precios_freefire_id WHERE activo=1 LIMIT 5")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}, ${r[2]}")

cur = conn.execute("SELECT id, nombre FROM juegos_dinamicos WHERE activo=1")
print("\njuegos_dinamicos:")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}")

conn.close()
