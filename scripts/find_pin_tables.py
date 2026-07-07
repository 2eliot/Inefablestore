import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%pin%' OR name LIKE '%stock%')")
for r in cur.fetchall():
    print(r[0])
conn.close()
