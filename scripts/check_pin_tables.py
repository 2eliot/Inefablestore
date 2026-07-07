"""Find PIN stock tables in Revendedores databases"""
import sqlite3, os

base = '/home/apps/web-b-revendedores'
for path in ['revendedores_local.db', 'usuarios.db', 'data/revendedores.db', 'data/usuarios.db']:
    full = os.path.join(base, path)
    if not os.path.exists(full):
        continue
    try:
        conn = sqlite3.connect(full)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%pin%' OR name LIKE '%stock%' OR name LIKE '%fuente%')").fetchall()
        if tables:
            print(f'=== {path} ===')
            for t in tables:
                tname = t[0]
                print(f'  TABLE: {tname}')
                cols = conn.execute(f'PRAGMA table_info({tname})').fetchall()
                for c in cols:
                    print(f'    {c[1]} {c[2]}')
                cnt = conn.execute(f'SELECT COUNT(*) FROM {tname}').fetchone()[0]
                print(f'    ROWS: {cnt}')
        conn.close()
    except Exception as e:
        print(f'  ERROR {path}: {e}')
