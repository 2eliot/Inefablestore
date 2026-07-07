import urllib.request, json
d = json.loads(urllib.request.urlopen("http://127.0.0.1:5000/store/package/3/items").read())
print("direct_to_pin:", d.get("direct_to_pin"))
print("ok:", d.get("ok"))
