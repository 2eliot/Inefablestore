import sqlite3
conn = sqlite3.connect("/home/apps/web-b-revendedores/usuarios.db")
conn.row_factory = sqlite3.Row
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Tables:", [t["name"] for t in tables])
for tbl in ["usuarios", "users", "user", "revendedores"]:
    try:
        rows = conn.execute(f"SELECT * FROM {tbl} LIMIT 1").fetchall()
        print(f"Table {tbl}: {len(rows)} rows, cols={list(rows[0].keys()) if rows else 'empty'}")
    except Exception as e:
        print(f"Table {tbl}: {e}")
