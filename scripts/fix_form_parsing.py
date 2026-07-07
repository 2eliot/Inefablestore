#!/usr/bin/env python3
"""Quick fix: use request.values for form parsing with operator precedence fix"""
path = '/home/apps/web-b-revendedores/connection_api.py'
with open(path, 'r') as f:
    c = f.read()

old = "    package_id = request.form.get('package_id') or request.json.get('package_id') if request.is_json else None"
new = "    package_id = request.values.get('package_id') or (request.json.get('package_id') if request.is_json else None)"
if old in c:
    c = c.replace(old, new)
    print("Fixed package_id parsing")
else:
    print("Old string not found, checking...")
    import re
    matches = re.findall(r'package_id.*=.*request', c)
    for m in matches:
        print(f"  Found: {m}")

old2 = "    quantity = request.form.get('quantity') or '1'"
new2 = "    quantity = request.values.get('quantity') or '1'"
if old2 in c:
    c = c.replace(old2, new2)
    print("Fixed quantity parsing")

with open(path, 'w') as f:
    f.write(c)
print("Done")
