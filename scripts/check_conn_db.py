import sqlite3, os

db_path = '/home/apps/web-b-revendedores/usuarios.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables in usuarios.db: {tables}")
    
    if 'precios_paquetes' in tables:
        cnt = conn.execute("SELECT COUNT(*) FROM precios_paquetes WHERE activo=1").fetchone()[0]
        print(f"Active precios_paquetes: {cnt}")
    conn.close()
else:
    print("usuarios.db not found")
    # search
    for root, dirs, files in os.walk('/home/apps/web-b-revendedores/'):
        for f in files:
            if f.endswith('.db'):
                print(os.path.join(root, f))
