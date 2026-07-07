import sqlite3
conn = sqlite3.connect('/home/apps/web-b-revendedores/data/usuarios.db')
conn.execute("UPDATE configuracion_fuentes_pines SET fuente='api_externa' WHERE monto_id=1")
conn.commit()
row = conn.execute('SELECT monto_id, fuente FROM configuracion_fuentes_pines WHERE monto_id=1').fetchone()
print(f'Done: monto_id={row[0]}, fuente={row[1]}')
conn.close()
