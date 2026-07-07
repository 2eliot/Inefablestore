#!/usr/bin/env python3
"""Parse catalog JSON and print all games with packages"""
import json, sys

cat_file = sys.argv[1] if len(sys.argv) > 1 else '/tmp/cat6.json'
with open(cat_file) as f:
    data = json.load(f)

games = data.get('games', [])
print(f"{len(games)} games in catalog")
for g in games:
    gtype = g.get('game_type', '?')
    gid = g.get('game_id', '?')
    print(f"  {g['name']:<25} | type={gtype:<20} | game_id={gid}")
    for p in g.get('packages', []):
        print(f"    pkg_id={p['package_id']:>6}  {p['name']:<25} ${p['price']}")
