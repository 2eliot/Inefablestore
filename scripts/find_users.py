import sqlite3
conn = sqlite3.connect("/home/apps/web-b-revendedores/data/usuarios.db")
conn.row_factory = sqlite3.Row
# Check schema
cols = conn.execute("PRAGMA table_info(usuarios)").fetchall()
print("Columnas:", [(c["name"], c["type"]) for c in cols])
# List users with balance > 0
rows = conn.execute("SELECT id, nombre, correo, saldo FROM usuarios WHERE saldo > 0 LIMIT 10").fetchall()
for r in rows:
    print(f"  id={r['id']} nombre={r['nombre']} correo={r['correo']} saldo={r['saldo']}")
