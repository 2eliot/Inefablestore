"""Fix connection_api.py to use paquetes_dinamicos instead of precios_paquetes."""
import shutil

filepath = '/home/apps/web-b-revendedores/connection_api.py'
shutil.copy2(filepath, filepath + '.bak')

with open(filepath, 'r') as f:
    content = f.read()

old_func = """def get_package_info_with_prices():
    \"\"\"Obtiene información de paquetes con precios dinámicos\"\"\"
    conn = get_db_connection()
    packages = conn.execute('''
        SELECT id, nombre, precio, descripcion 
        FROM precios_paquetes 
        WHERE activo = TRUE 
        ORDER BY id
    ''').fetchall()
    conn.close()
    
    # Convertir a diccionario para fácil acceso
    package_dict = {}
    for package in packages:
        package_dict[package['id']] = {
            'nombre': package['nombre'],
            'precio': package['precio'],
            'descripcion': package['descripcion']
        }
    
    return package_dict"""

new_func = """def get_package_info_with_prices():
    \"\"\"Obtiene informacion de paquetes con precios dinamicos\"\"\"
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
            'nombre': f\"{package['nombre']} ({package['juego']})\",
            'precio': package['precio'],
            'descripcion': package['descripcion'] or package['nombre']
        }
    
    return package_dict"""

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(filepath, 'w') as f:
        f.write(content)
    print("OK: Function replaced successfully")
else:
    print("ERROR: old function not found in file")
    # Show what's around line 269
    lines = open(filepath).readlines()
    for i in range(267, 290):
        if i < len(lines):
            print(f"  {i+1}: {lines[i].rstrip()}")
