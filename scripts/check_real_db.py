import sqlite3, os

db_path = '/home/apps/web-b-revendedores/data/usuarios.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables ({len(tables)}): {tables[:30]}")
    
    if 'precios_paquetes' in tables:
        cnt = conn.execute("SELECT COUNT(*) FROM precios_paquetes WHERE activo=1").fetchone()[0]
        print(f"Active precios_paquetes: {cnt}")
        rows = conn.execute("SELECT id, nombre, precio FROM precios_paquetes WHERE activo=1 LIMIT 5").fetchall()
        for r in rows:
            print(f"  {r}")
    else:
        print("precios_paquetes table NOT found")
    conn.close()
else:
    print(f"{db_path} not found")
