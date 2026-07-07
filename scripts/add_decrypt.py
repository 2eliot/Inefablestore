#!/usr/bin/env python3
"""Add pin_crypto import and decrypt pins from PostgreSQL stock"""
path = '/home/apps/web-b-revendedores/connection_api.py'
with open(path, 'r') as f:
    c = f.read()

# Add pin_crypto import
if 'from pin_crypto import' not in c:
    c = c.replace(
        "from pin_manager import create_pin_manager",
        "from pin_crypto import decrypt_pin\nfrom pin_manager import create_pin_manager"
    )
    print("Added pin_crypto import")

# Decrypt pins from PostgreSQL query
old_pg_pins = """                    pins_list = [row['pin_codigo'] for row in pg_rows]
                    ids_list = [row['id'] for row in pg_rows]"""
new_pg_pins = """                    pins_list = [decrypt_pin(row['pin_codigo']) for row in pg_rows]
                    ids_list = [row['id'] for row in pg_rows]"""
if old_pg_pins in c:
    c = c.replace(old_pg_pins, new_pg_pins)
    print("Added decrypt_pin to PostgreSQL PIN list")

# Also decrypt legacy SQLite pins (they may also be encrypted)
old_sqlite_pins = """        pins_list = [row['pin_codigo'] for row in rows]
        ids_list = [row['id'] for row in rows]
        ph = ','.join(['?'] * len(ids_list))
        conn.execute('UPDATE pines_freefire SET usado=1 WHERE id IN (' + ph + ')', ids_list)"""
new_sqlite_pins = """        pins_list = [decrypt_pin(row['pin_codigo']) for row in rows]
        ids_list = [row['id'] for row in rows]
        ph = ','.join(['?'] * len(ids_list))
        conn.execute('UPDATE pines_freefire SET usado=1 WHERE id IN (' + ph + ')', ids_list)"""
if old_sqlite_pins in c:
    c = c.replace(old_sqlite_pins, new_sqlite_pins)
    print("Added decrypt_pin to legacy SQLite PIN list")

with open(path, 'w') as f:
    f.write(c)
print("Done")
