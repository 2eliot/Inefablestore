import json
d = json.load(open("/tmp/api_catalog_active.json"))
print("ok:", d.get("ok"))
print("keys:", list(d.keys())[:10])
games = d.get("games", [])
print("games:", len(games))
items = d.get("items", [])
print("items:", len(items))

# Check if it's a stock/catalog format
if items:
    for it in items[:3]:
        print(json.dumps(it, indent=2)[:200])

if games:
    for g in games[:3]:
        pkgs = g.get("packages", [])
        name = g.get("name", "?")
        print(f"  {name}: {len(pkgs)} packages")
