import subprocess, json

# Query PostgreSQL
cmd = "PGPASSWORD=InefablePg2026 psql -h 127.0.0.1 -U inefable_user -d inefablestore -c \"SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE '%rev%' OR table_name LIKE '%catalog%' ORDER BY table_name\""
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print("TABLES:", result.stdout)
if result.stderr:
    print("ERR:", result.stderr)

cmd2 = "PGPASSWORD=InefablePg2026 psql -h 127.0.0.1 -U inefable_user -d inefablestore -c \"SELECT COUNT(*) as cnt FROM rev_catalog_items WHERE active=true\""
result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
print("ACTIVE ITEMS:", result2.stdout)

cmd3 = "PGPASSWORD=InefablePg2026 psql -h 127.0.0.1 -U inefable_user -d inefablestore -c \"SELECT remote_product_name, COUNT(*) as cnt FROM rev_catalog_items WHERE active=true GROUP BY remote_product_name ORDER BY cnt DESC LIMIT 12\""
result3 = subprocess.run(cmd3, shell=True, capture_output=True, text=True)
print("BY GAME:", result3.stdout)

cmd4 = "PGPASSWORD=InefablePg2026 psql -h 127.0.0.1 -U inefable_user -d inefablestore -c \"SELECT COUNT(*) as cnt FROM rev_mappings\""
result4 = subprocess.run(cmd4, shell=True, capture_output=True, text=True)
print("MAPPINGS:", result4.stdout)
