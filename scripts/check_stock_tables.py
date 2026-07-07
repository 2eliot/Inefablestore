import sqlite3, os

dbs = {
    'revendedores_local.db': '/home/apps/web-b-revendedores/revendedores_local.db',
    'data/usuarios.db': '/home/apps/web-b-revendedores/data/usuarios.db',
}

for name, full in dbs.items():
    if not os.path.exists(full):
        print(f'NOT FOUND: {full}')
        continue
    try:
        conn = sqlite3.connect(f'file:{full}?mode=ro', uri=True)
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f'\n=== {name} ===')
        print(f'Tables ({len(tables)}): {sorted(tables)}')
        
        # Check for game/stock tables
        for tname in ['pines_stock', 'paquetes_stock', 'juegos_stock']:
            if tname in tables:
                cnt = conn.execute(f'SELECT COUNT(*) FROM {tname}').fetchone()[0]
                print(f'  {tname}: {cnt} rows')
        conn.close()
    except Exception as e:
        print(f'ERROR {name}: {e}')
