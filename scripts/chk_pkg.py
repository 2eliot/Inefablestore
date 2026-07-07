#!/usr/bin/env python3
import subprocess
import os

os.environ['PGPASSWORD'] = 'InefablePg2026'
r = subprocess.run([
    'psql', '-h', 'localhost', '-U', 'inefable_user', '-d', 'inefablestore',
    '-c', 'SELECT id, name, active FROM store_packages ORDER BY id;'
], capture_output=True, text=True)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr)
