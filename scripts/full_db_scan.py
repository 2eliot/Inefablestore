import sqlite3, os, glob

patterns = [
    '/home/apps/web-b-revendedores/**/*.db',
    '/home/apps/web-b-revendedores/*.db',
]

for pattern in patterns:
    for path in glob.glob(pattern, recursive=True):
        try:
            conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tnames = [t[0] for t in tables]
            game_tables = [t for t in tnames if any(k in t for k in ['stock', 'pin', 'juego', 'paquete'])]
            if game_tables:
                print(f'\n=== {path} ({len(tnames)} tables) ===')
                for gt in game_tables:
                    cnt = conn.execute(f'SELECT COUNT(*) FROM {gt}').fetchone()[0]
                    print(f'  {gt}: {cnt} rows')
            conn.close()
        except Exception as e:
            pass

# Also check data/usuarios.db specifically for pin-related tables
path = '/home/apps/web-b-revendedores/data/usuarios.db'
if os.path.exists(path):
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    print(f'\n=== {path} - PIN tables ===')
    tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%pin%' OR name LIKE '%stock%' OR name LIKE '%juego%' OR name LIKE '%paquete%')").fetchall()]
    for t in tables:
        cols = conn.execute(f'PRAGMA table_info({t})').fetchall()
        col_info = ', '.join(f'{c[1]} {c[2]}' for c in cols)
        cnt = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t}: {cnt} rows ({col_info})')
        # Show a few rows for game-related tables
        if cnt > 0 and 'pin' in t.lower():
            rows = conn.execute(f'SELECT * FROM {t} LIMIT 3').fetchall()
            for r in rows:
                print(f'    {r}')
    conn.close()
