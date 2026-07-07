import sqlite3
conn = sqlite3.connect("/home/apps/web-b-revendedores/usuarios.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, nombre, correo, role FROM usuarios LIMIT 10").fetchall()
for r in rows:
    print(r["id"], r["nombre"], r["correo"], r["role"])
