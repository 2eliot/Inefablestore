import sqlite3
conn = sqlite3.connect('/home/apps/web-a-inefablestore/instance/store.db')
cur = conn.execute('SELECT COUNT(*) FROM rev_catalog_items WHERE active=1')
print('Active catalog items:', cur.fetchone()[0])
cur = conn.execute('SELECT COUNT(*) FROM rev_catalog_items')
print('Total catalog items:', cur.fetchone()[0])
cur = conn.execute('SELECT remote_product_name, COUNT(*) as cnt FROM rev_catalog_items WHERE active=1 GROUP BY remote_product_name ORDER BY cnt DESC LIMIT 12')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%rev%'")
print('\nRev tables:', [r[0] for r in cur.fetchall()])
