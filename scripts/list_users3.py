import sqlite3
conn = sqlite3.connect("/home/apps/web-b-revendedores/data/usuarios.db")
conn.row_factory = sqlite3.Row
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Tables:", [t["name"] for t in tables])
rows = conn.execute("SELECT id, nombre, correo, role, saldo FROM usuarios LIMIT 10").fetchall()
for r in rows:
    print(r["id"], r["nombre"], r["correo"], r["role"], r["saldo"] if "saldo" in r.keys() else "")
