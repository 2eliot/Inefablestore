import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')
conn.row_factory = sqlite3.Row

# Check tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%stock%'").fetchall()
print('Stock tables:', [t['name'] for t in tables])

# juegos_stock
juegos = conn.execute('SELECT * FROM juegos_stock').fetchall()
print('\n--- juegos_stock ---')
for j in juegos:
    print(dict(j))

# paquetes_stock
paquetes = conn.execute('SELECT * FROM paquetes_stock').fetchall()
print('\n--- paquetes_stock ---')
for p in paquetes:
    print(dict(p))

# Check for pines tables related to stock
pines_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'pines_%'").fetchall()
print('\n--- pines tables ---')
for pt in pines_tables:
    name = pt['name']
    count = conn.execute(f'SELECT COUNT(*) as cnt FROM {name}').fetchone()['cnt']
    print(f'{name}: {count} rows')

conn.close()
