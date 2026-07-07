"""Fix connection_api.py get_package_info_with_prices() to include ALL stock PIN sources."""
import shutil

filepath = '/home/apps/web-b-revendedores/connection_api.py'
shutil.copy2(filepath, filepath + '.bak2')

with open(filepath, 'r') as f:
    content = f.read()

# Find and replace the function
old_func = '''def get_package_info_with_prices():
    """Obtiene informacion de paquetes con precios dinamicos"""
    conn = get_db_connection()
    packages = conn.execute('''
        SELECT pd.id, pd.nombre, pd.precio, pd.descripcion, jd.nombre as juego
        FROM paquetes_dinamicos pd
        JOIN juegos_dinamicos jd ON pd.juego_id = jd.id
        WHERE pd.activo = TRUE
        ORDER BY pd.id
    ''').fetchall()
    conn.close()
    
    # Convertir a diccionario para facil acceso
    package_dict = {}
    for package in packages:
        package_dict[package['id']] = {
            'nombre': f"{package['nombre']} ({package['juego']})",
            'precio': package['precio'],
            'descripcion': package['descripcion'] or package['nombre']
        }
    
    return package_dict'''

new_func = '''def get_package_info_with_prices():
    """Obtiene TODOS los paquetes de stock con precios - incluye dinamicos + Free Fire."""
    conn = get_db_connection()
    all_packages = []
    
    # 1) paquetes_dinamicos (juegos creados con "Crear Juego Stock")
    try:
        pkgs = conn.execute('''
            SELECT pd.id, pd.nombre, pd.precio, pd.descripcion, jd.nombre as juego
            FROM paquetes_dinamicos pd
            JOIN juegos_dinamicos jd ON pd.juego_id = jd.id
            WHERE pd.activo = TRUE
            ORDER BY pd.id
        ''').fetchall()
        for p in pkgs:
            all_packages.append({
                'nombre': f"{p['nombre']} ({p['juego']})",
                'precio': p['precio'],
                'descripcion': p['descripcion'] or p['nombre'],
                'source': 'dinamico',
                'id': p['id']
            })
    except Exception:
        pass
    
    # 2) Free Fire Global - tabla legacy con PINs en stock
    try:
        ff_global = conn.execute('''
            SELECT id, nombre, precio, descripcion
            FROM precios_freefire_global
            WHERE activo = TRUE
            ORDER BY id
        ''').fetchall()
        for p in ff_global:
            all_packages.append({
                'nombre': f"{p['nombre']} (Free Fire Global)",
                'precio': p['precio'],
                'descripcion': p['descripcion'] or p['nombre'],
                'source': 'ff_global',
                'id': 10000 + p['id']  # offset para evitar colision de IDs
            })
    except Exception:
        pass
    
    # 3) Free Fire ID - tabla legacy con PINs en stock
    try:
        ff_id = conn.execute('''
            SELECT id, nombre, precio, descripcion
            FROM precios_freefire_id
            WHERE activo = TRUE
            ORDER BY id
        ''').fetchall()
        for p in ff_id:
            all_packages.append({
                'nombre': f"{p['nombre']} (Free Fire ID)",
                'precio': p['precio'],
                'descripcion': p['descripcion'] or p['nombre'],
                'source': 'ff_id',
                'id': 20000 + p['id']  # offset para evitar colision de IDs
            })
    except Exception:
        pass
    
    conn.close()
    
    # Convertir a diccionario para facil acceso
    package_dict = {}
    for p in all_packages:
        package_dict[p['id']] = {
            'nombre': p['nombre'],
            'precio': p['precio'],
            'descripcion': p['descripcion']
        }
    
    return package_dict'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(filepath, 'w') as f:
        f.write(content)
    print("OK: Function replaced successfully")
else:
    print("ERROR: old function not found")
    lines = open(filepath).readlines()
    for i in range(268, 295):
        if i < len(lines):
            print(f"  {i+1}: {lines[i].rstrip()}")
