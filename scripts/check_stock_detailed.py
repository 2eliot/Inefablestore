"""Check stock tables in Revendedores database"""
import sqlite3, os

path = '/home/apps/web-b-revendedores/data/usuarios.db'
conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)

# Check which stock tables exist
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('pines_stock','juegos_stock','paquetes_stock')").fetchall()
print(f'Tables found: {[t[0] for t in tables]}')

if any(t[0] == 'juegos_stock' for t in tables):
    print('\n=== juegos_stock ===')
    for row in conn.execute('SELECT * FROM juegos_stock'):
        print(dict(row))

if any(t[0] == 'paquetes_stock' for t in tables):
    print('\n=== paquetes_stock ===')
    for row in conn.execute('SELECT id, nombre, juego_stock_id, precio, activo FROM paquetes_stock'):
        print(dict(row))

if any(t[0] == 'pines_stock' for t in tables):
    print('\n=== pines_stock (sample) ===')
    for row in conn.execute('SELECT * FROM pines_stock LIMIT 3'):
        print(dict(row))
    cnt = conn.execute('SELECT COUNT(*) FROM pines_stock WHERE usado=0').fetchone()[0]
    print(f'Unused PIN stock: {cnt}')

conn.close()
