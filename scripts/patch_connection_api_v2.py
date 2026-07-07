#!/usr/bin/env python3
"""Patch connection_api.py to add PostgreSQL game stock routing"""
import sys

path = '/home/apps/web-b-revendedores/connection_api.py'
with open(path, 'r') as f:
    content = f.read()

# Add psycopg2 import if not present
if 'import psycopg2' not in content:
    content = content.replace("import sqlite3", "import sqlite3\nimport psycopg2\nimport psycopg2.extras")

# Add PostgreSQL helper function after get_db_connection
pg_helper = '''

def _get_pg_stock_connection():
    """Get a PostgreSQL connection for game-specific stock tables."""
    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        return None
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    try:
        conn = psycopg2.connect(url)
        return conn
    except Exception:
        return None
'''

get_db_marker = "def get_db_connection():\n    \"\"\"Obtiene una conexión a la base de datos\"\"\"\n    conn = sqlite3.connect(DATABASE)\n    conn.row_factory = sqlite3.Row\n    return conn"
if get_db_marker in content:
    content = content.replace(get_db_marker, get_db_marker + pg_helper)

# Target: the block that uses pin_manager for PIN purchase
old_block = """        # Usar pin manager para obtener PINs
        pin_manager = create_pin_manager(DATABASE)
        pins_list = []
        local_pins_reserved = []
        
        if quantity == 1:
            # Para un solo PIN
            result = pin_manager.request_pin(package_id)"""

new_block = """        # Intentar primero stock de juegos en PostgreSQL
        pins_list = []
        local_pins_reserved = []
        game_stock_used = False
        
        pg_conn = _get_pg_stock_connection()
        if pg_conn:
            try:
                pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                pkg = None
                try:
                    pg_cur.execute(
                        'SELECT id, nombre, juego_stock_id FROM paquetes_stock WHERE id = %s AND activo = TRUE',
                        (package_id,)
                    )
                    pkg = pg_cur.fetchone()
                except Exception:
                    pg_conn.rollback()
                if pkg:
                    pg_cur.execute(
                        'SELECT id, pin_codigo FROM pines_stock WHERE paquete_id = %s AND usado = FALSE ORDER BY id ASC LIMIT %s',
                        (package_id, quantity)
                    )
                    pg_rows = pg_cur.fetchall()
                    if pg_rows:
                        pins_list = [row['pin_codigo'] for row in pg_rows]
                        ids_list = [row['id'] for row in pg_rows]
                        ph = ','.join(['%s'] * len(ids_list))
                        pg_cur.execute(
                            'UPDATE pines_stock SET usado=TRUE, fecha_usado=CURRENT_TIMESTAMP WHERE id IN (' + ph + ')',
                            tuple(ids_list)
                        )
                        pg_conn.commit()
                        game_stock_used = True
                pg_cur.close()
            except Exception:
                try:
                    pg_conn.rollback()
                except Exception:
                    pass
            finally:
                try:
                    pg_conn.close()
                except Exception:
                    pass
        
        if game_stock_used:
            if len(pins_list) == 1:
                result = {'status': 'success', 'pin_code': pins_list[0], 'source': 'postgres_stock'}
            else:
                result = {
                    'status': 'success',
                    'pins': [{'pin_code': p, 'source': 'postgres_stock'} for p in pins_list]
                }
        else:
            # Fallback: usar pin_manager (SQLite pines_freefire)
            pin_manager = create_pin_manager(DATABASE)
        
        if not game_stock_used:
            if quantity == 1:
                # Para un solo PIN
                result = pin_manager.request_pin(package_id)"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(path, 'w') as f:
        f.write(content)
    print("PATCH APPLIED SUCCESSFULLY")
else:
    print("ERROR: old_block not found in file")
    # Show context around pin_manager
    idx = content.find('pin_manager = create_pin_manager(DATABASE)')
    if idx > 0:
        start = max(0, idx - 200)
        end = min(len(content), idx + 400)
        print(f"Context:\n{content[start:end]}")
