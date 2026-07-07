import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM configuracion_fuentes_pines WHERE activo=1").fetchall()
print(f"Source configs: {len(rows)}")
for r in rows:
    print(f"  monto_id={r['monto_id']}, fuente={r['fuente']}")
conn.close()
