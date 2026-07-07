"""
Add Stock Games to api_whitelabel.py catalog.
Stock games live in PostgreSQL (juegos_stock, paquetes_stock, pines_stock).
"""
import shutil

filepath = '/home/apps/web-b-revendedores/api_whitelabel.py'
shutil.copy2(filepath, filepath + '.bak_stock')

with open(filepath, 'r') as f:
    lines = f.readlines()

STOCK_OFFSET = 200
changes = 0

# === 1. Catalog: add stock games after Free Fire Global, before account = request._ws_account ===
insert_catalog_at = None
for i, line in enumerate(lines):
    if "account = request._ws_account" in line and 480 < i < 560:
        insert_catalog_at = i
        break

if insert_catalog_at:
    stock_block = [
        '\n',
        '    # 5. Juegos Stock (PINs manuales desde PostgreSQL)\n',
        '    try:\n',
        '        conn_sg = _get_conn()\n',
        '        stock_games_rows = conn_sg.execute(\n',
        '            "SELECT id, nombre, slug, icono, descripcion FROM juegos_stock WHERE activo = TRUE ORDER BY nombre"\n',
        '        ).fetchall()\n',
        '        conn_sg.close()\n',
        '        for sg in stock_games_rows:\n',
        '            conn_sp = _get_conn()\n',
        '            stock_pkgs = conn_sp.execute(\n',
        '                "SELECT id, nombre, precio, descripcion FROM paquetes_stock WHERE juego_stock_id = ? AND activo = TRUE ORDER BY orden, id",\n',
        '                (sg["id"],)\n',
        '            ).fetchall()\n',
        '            conn_sp.close()\n',
        f'            stock_game_id = -{STOCK_OFFSET} - sg["id"]\n',
        '            packages = []\n',
        '            for p in stock_pkgs:\n',
        '                packages.append({\n',
        '                    "package_id": p["id"],\n',
        '                    "name": p["nombre"],\n',
        '                    "price": float(p["precio"]),\n',
        '                    "description": p.get("descripcion", ""),\n',
        '                })\n',
        '            if packages:\n',
        '                games.append({\n',
        '                    "game_type": "stock",\n',
        '                    "game_id": stock_game_id,\n',
        '                    "name": sg["nombre"],\n',
        '                    "slug": "stock-" + (sg.get("slug") or ""),\n',
        '                    "mode": "pin",\n',
        '                    "icon": sg.get("icono", "\\U0001f4e6"),\n',
        '                    "description": sg.get("descripcion", "") or "Juego con stock propio",\n',
        '                    "packages": packages,\n',
        '                })\n',
        '    except Exception as e:\n',
        "        logger.warning(f'[WL API] Error leyendo juegos stock: {e}')\n",
    ]
    for j, block_line in enumerate(stock_block):
        lines.insert(insert_catalog_at + j, block_line)
    changes += 1
    print(f"1. Catalog: inserted {len(stock_block)} lines before line {insert_catalog_at+1}")
else:
    print("ERROR: Could not find catalog insertion point")

# === 2. Resolve: add stock game resolution before final return None ===
resolve_start = -1
resolve_end = -1
for i, line in enumerate(lines):
    if line.strip().startswith('def _resolve_package('):
        resolve_start = i
    if resolve_start >= 0 and i > resolve_start + 50:
        stripped = line.strip()
        if stripped == 'return (None, None, None, None, None, None, None)':
            resolve_end = i
            break

if resolve_end >= 0:
    stock_resolve_block = [
        '\n',
        f'    # 5. Juegos Stock (product_id <= -{STOCK_OFFSET+1}, IDs con offset -{STOCK_OFFSET})\n',
        f'    if product_id is not None and product_id <= -{STOCK_OFFSET + 1}:\n',
        '        try:\n',
        f'            real_juego_id = -{STOCK_OFFSET} - product_id\n',
        '            conn = _get_conn()\n',
        '            juego = conn.execute(\n',
        '                "SELECT id, nombre FROM juegos_stock WHERE id = ? AND activo = TRUE",\n',
        '                (real_juego_id,)\n',
        '            ).fetchone()\n',
        '            conn.close()\n',
        '            if juego:\n',
        '                conn2 = _get_conn()\n',
        '                pkg = conn2.execute(\n',
        '                    "SELECT id, nombre, precio FROM paquetes_stock WHERE id = ? AND juego_stock_id = ? AND activo = TRUE",\n',
        '                    (package_id, real_juego_id)\n',
        '                ).fetchone()\n',
        '                conn2.close()\n',
        '                if pkg:\n',
        '                    return (\n',
        '                        "stock",\n',
        '                        juego["nombre"],\n',
        '                        pkg["nombre"],\n',
        '                        float(pkg["precio"]),\n',
        '                        None,\n',
        '                        None,\n',
        '                        {"provider": "stock_pin", "real_juego_id": real_juego_id, "real_paquete_id": pkg["id"]},\n',
        '                    )\n',
        '        except Exception:\n',
        '            pass\n',
    ]
    for j, block_line in enumerate(stock_resolve_block):
        lines.insert(resolve_end + j, block_line)
    changes += 1
    print(f"2. Resolve: inserted {len(stock_resolve_block)} lines at line {resolve_end+1}")
else:
    print(f"ERROR: resolve_start={resolve_start} resolve_end={resolve_end}")

# === 3. Execute switch: add stock case after freefire_global ===
found_switch = False
for i, line in enumerate(lines):
    if "game_type == 'freefire_global':" in line:
        if i+1 < len(lines) and 'result = _execute_freefire_global_recharge' in lines[i+1]:
            lines.insert(i + 2, "        elif game_type == 'stock':\n")
            lines.insert(i + 3, "            result = _execute_stock_recharge(order_id, package_id, player_id, provider_meta)\n")
            found_switch = True
            changes += 1
            print(f"3. Execute switch: inserted after line {i+1}")
            break

if not found_switch:
    print("ERROR: Could not find execute switch for freefire_global")

# === 4. Function: _execute_stock_recharge before GET /api/v1/orders ===
insert_func_at = -1
for i, line in enumerate(lines):
    if i > 1080 and 'GET /api/v1/orders' in line:
        insert_func_at = i
        break

if insert_func_at >= 0:
    stock_func = [
        '\n',
        'def _execute_stock_recharge(order_id, package_id, player_id, provider_meta=None):\n',
        '    """Ejecuta recarga de Juego Stock - entrega PIN directo del stock PostgreSQL."""\n',
        '    real_paquete_id = (provider_meta or {}).get("real_paquete_id") or int(package_id)\n',
        '    from stock_games import get_available_pin_stock\n',
        '\n',
        '    pin_disponible = get_available_pin_stock(real_paquete_id, user_id=0)\n',
        '    if not pin_disponible:\n',
        "        return {'ok': False, 'error': f'Sin stock para paquete {real_paquete_id}'}\n",
        '\n',
        "    pin_codigo = pin_disponible['pin_codigo']\n",
        '    return {\n',
        "        'ok': True,\n",
        "        'player_name': player_id,\n",
        "        'reference_no': pin_codigo,\n",
        "        'redeemed_pin': pin_codigo,\n",
        '    }\n',
        '\n',
    ]
    for j, block_line in enumerate(stock_func):
        lines.insert(insert_func_at + j, block_line)
    changes += 1
    print(f"4. Function: inserted at line {insert_func_at}")
else:
    print("ERROR: Could not find function insertion point")

# Write
with open(filepath, 'w') as f:
    f.writelines(lines)

if changes == 4:
    print(f"\nSUCCESS: All {changes}/4 changes applied. Backup at {filepath}.bak_stock")
else:
    print(f"\nPARTIAL: {changes}/4 changes applied. Restore from bak if broken.")
