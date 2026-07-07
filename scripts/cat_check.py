import json
d = json.load(open("/tmp/cat4.json"))
games = d.get("games", [])
print(len(games), "games in catalog")
for g in games:
    print(f"  {g['name']:25s} | type={g.get('game_type','?'):18s} | game_id={g.get('game_id')}")
    for p in g.get("packages", []):
        print(f"    pkg_id={p['package_id']:6d}  {p['name']:20s}  ${p['price']}")
