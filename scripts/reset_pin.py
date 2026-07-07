import psycopg2
conn = psycopg2.connect('postgresql://revendedores_user:InefablePg2026@127.0.0.1:5432/revendedores')
cur = conn.cursor()
cur.execute("UPDATE pines_stock SET usado=FALSE, fecha_usado=NULL WHERE id=1")
conn.commit()
cur.execute("SELECT id, paquete_id, usado FROM pines_stock")
for r in cur.fetchall(): print(r)
cur.close()
conn.close()
