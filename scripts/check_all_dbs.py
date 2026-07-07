"""Check all Revendedores DBs for PIN tables"""
import sqlite3, os

dbs = [
    '/tmp/test_pines.db',
]

base = '/home/apps/web-b-revendedores'
for path in ['revendedores_local.db', 'usuarios.db', 'data/revendedores.db', 'data/usuarios.db']:
    full = os.path.join(base, path)
    if not os.path.exists(full):
        print(f'NOT FOUND: {full}')
        continue
    try:
        conn = sqlite3.connect(f'file:{full}?mode=ro', uri=True)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f'\n=== {full} ===')
        print(f'Tables: {[t[0] for t in tables]}')
        # Check pines_stock
        if any('pines_stock' in t[0] for t in tables):
            cnt = conn.execute('SELECT COUNT(*) FROM pines_stock').fetchone()[0]
            print(f'pines_stock rows: {cnt}')
            # Show sample
            rows = conn.execute('SELECT * FROM pines_stock LIMIT 5').fetchall()
            for r in rows:
                print(f'  {r}')
        conn.close()
    except Exception as e:
        print(f'ERROR {full}: {e}')
