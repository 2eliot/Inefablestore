import json
d = json.load(open("/tmp/cat3.json"))
print(len(d.get("games", [])), "games")
for g in d.get("games", []):
    pkgs = g.get("packages", [])
    pkg_ids = [p["package_id"] for p in pkgs]
    print(f"{g['name']} ({g.get('game_type', '?')}) -> {len(pkgs)} packages: {pkg_ids}")
