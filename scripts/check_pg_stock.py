import psycopg2, os
url = os.environ.get('DATABASE_URL') or 'postgresql://revendedores_user:InefablePg2026@127.0.0.1:5432/revendedores'
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("SELECT id, paquete_id, usado, substring(pin_codigo,1,35) FROM pines_stock")
for r in cur.fetchall(): print(r)
cur.close()
conn.close()
