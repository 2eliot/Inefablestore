import json
d = json.load(open("/tmp/api_response.json"))
print("ok:", d.get("ok"))
games = d.get("games", [])
print("games:", len(games))
for g in games[:10]:
    pkgs = g.get("packages", [])
    name = g.get("name", "?")
    print(f"  {name}: {len(pkgs)} packages")
    for p in pkgs[:2]:
        print(f"    - {p.get('name', '?')} (id={p.get('package_id', '?')})")
