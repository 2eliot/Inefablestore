#!/usr/bin/env python3
"""Fix the descripcion column issue in api_whitelabel.py"""
import sys

path = '/home/apps/web-b-revendedores/api_whitelabel.py'
with open(path, 'r') as f:
    content = f.read()

# Fix 1: Remove descripcion from juegos_stock SELECT (already done by sed)
# Fix 2: Replace sg.get("descripcion", "") or "Juego con stock propio"
old = 'sg.get("descripcion", "") or "Juego con stock propio"'
new = '"Juego con stock propio"'
if old in content:
    content = content.replace(old, new)
    print("Fix 2 applied: descripcion fallback replaced")
else:
    print("Fix 2: pattern not found (may already be fixed)")

with open(path, 'w') as f:
    f.write(content)

# Verify
with open(path, 'r') as f:
    for i, line in enumerate(f, 1):
        if 'juegos_stock' in line or 'Juego con stock' in line:
            print(f"  Line {i}: {line.rstrip()}")
