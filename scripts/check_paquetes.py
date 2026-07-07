import sqlite3, os

db_path = '/home/apps/web-b-revendedores/data/usuarios.db'
conn = sqlite3.connect(db_path)

# Check paquetes_dinamicos
cur = conn.execute("SELECT COUNT(*) FROM paquetes_dinamicos WHERE activo=1")
print(f"Active paquetes_dinamicos: {cur.fetchone()[0]}")

cur = conn.execute("SELECT pd.id, pd.nombre, pd.precio, jd.nombre as juego FROM paquetes_dinamicos pd JOIN juegos_dinamicos jd ON pd.juego_id=jd.id WHERE pd.activo=1 LIMIT 10")
for r in cur.fetchall():
    print(f"  id={r[0]}, {r[1]}, ${r[2]}, juego={r[3]}")

# Check precios_paquetes (legacy)
cur = conn.execute("SELECT COUNT(*) FROM precios_paquetes")
print(f"Total precios_paquetes (legacy): {cur.fetchone()[0]}")

conn.close()
