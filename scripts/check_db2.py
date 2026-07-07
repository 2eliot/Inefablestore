import sqlite3, os

db_path = '/home/apps/web-a-inefablestore/instance/store.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f'SQLite tables ({len(tables)}): {tables[:30]}')
    conn.close()
else:
    print(f'No SQLite DB at {db_path}')

env_path = '/home/apps/web-a-inefablestore/.env'
if os.path.exists(env_path):
    for line in open(env_path).readlines():
        ul = line.upper().strip()
        if any(k in ul for k in ('DB', 'DATABASE', 'SQL', 'POSTGRES')):
            print(line.strip())
        elif line.startswith('REVENDEDORES'):
            print(line.strip())
else:
    print('.env not found')
