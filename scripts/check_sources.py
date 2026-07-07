import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')
rows = conn.execute("SELECT * FROM configuracion_fuentes_pines WHERE activo=1").fetchall()
print(f"Source configs: {len(rows)}")
for r in rows:
    print(dict(r))
conn.close()
