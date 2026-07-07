#!/usr/bin/env python3
import subprocess, os

os.environ['PGPASSWORD'] = 'InefablePg2026'
r = subprocess.run([
    'psql', '-h', 'localhost', '-U', 'inefable_user', '-d', 'inefablestore',
    '-c', """SELECT sp.id, sp.name, COUNT(gp.id) as items
FROM store_packages sp
LEFT JOIN game_packages gp ON gp.store_package_id = sp.id AND gp.active = TRUE
WHERE sp.active = TRUE
GROUP BY sp.id, sp.name
ORDER BY sp.id;"""
], capture_output=True, text=True)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr)
