#!/usr/bin/env python3
"""Restore pin-purchase endpoint and add PostgreSQL game stock routing"""
import sys

path = '/home/apps/web-b-revendedores/connection_api.py'
with open(path, 'r') as f:
    content = f.read()

# Add psycopg2 import if not present
if 'import psycopg2' not in content:
    content = content.replace("import sqlite3", "import sqlite3\nimport psycopg2\nimport psycopg2.extras")
    print("  Added psycopg2 import")

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
if get_db_marker in content and '_get_pg_stock_connection' not in content:
    content = content.replace(get_db_marker, get_db_marker + pg_helper)
    print("  Added _get_pg_stock_connection")

# Add pin-purchase endpoint before @connection_app.route('/api/connection/stock')
pin_purchase_endpoint = '''
@connection_app.route('/api/connection/pin-purchase', methods=['POST'])
def pin_purchase_by_key():
    """
    Purchase PIN using X-API-Key auth (used by InefableStore).
    Routes to game-specific PostgreSQL stock first, falls back to legacy SQLite Free Fire stock.
    Accepts: form data (package_id, quantity)
    """
    # Verify API key
    expected_key = os.environ.get('WEBB_API_KEY', '').strip()
    provided_key = (request.headers.get('X-API-Key') or '').strip()
    if not expected_key or provided_key != expected_key:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    package_id = request.form.get('package_id') or request.json.get('package_id') if request.is_json else None
    quantity = request.form.get('quantity') or '1'
    if not package_id:
        return jsonify({'ok': False, 'error': 'package_id required'}), 400
    try:
        package_id = int(package_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Invalid package_id or quantity'}), 400
    if quantity < 1 or quantity > 10:
        return jsonify({'ok': False, 'error': 'Quantity must be between 1 and 10'}), 400

    # First try: PostgreSQL game-specific stock (pines_stock by paquete_id)
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
                    pg_cur.close()
                    pg_conn.close()
                    source = 'pines_stock/paquete_' + str(package_id)
                    if len(pins_list) == 1:
                        return jsonify({
                            'ok': True, 'pin': pins_list[0], 'quantity': 1,
                            'package_id': package_id, 'source': source,
                            'package_name': pkg['nombre']
                        })
                    else:
                        return jsonify({
                            'ok': True, 'pins': pins_list,
                            'quantity': len(pins_list), 'package_id': package_id,
                            'source': source, 'package_name': pkg['nombre']
                        })
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

    # Fallback: SQLite legacy Free Fire global PIN stock
    conn = get_db_connection()
    try:
        rows = conn.execute(
            'SELECT id, pin_codigo FROM pines_freefire WHERE monto_id = ? AND usado = FALSE ORDER BY id ASC LIMIT ?',
            (package_id, quantity)
        ).fetchall()
        if not rows:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin stock disponible para package_id=' + str(package_id)}), 400

        pins_list = [row['pin_codigo'] for row in rows]
        ids_list = [row['id'] for row in rows]
        ph = ','.join(['?'] * len(ids_list))
        conn.execute('UPDATE pines_freefire SET usado=1 WHERE id IN (' + ph + ')', ids_list)
        conn.commit()
        conn.close()
        source = 'pines_freefire/monto_' + str(package_id)
        if len(pins_list) == 1:
            return jsonify({
                'ok': True, 'pin': pins_list[0], 'quantity': 1,
                'package_id': package_id, 'source': source
            })
        else:
            return jsonify({
                'ok': True, 'pins': pins_list,
                'quantity': len(pins_list), 'package_id': package_id,
                'source': source
            })
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 500

'''

# Insert before the stock endpoint
stock_marker = "@connection_app.route('/api/connection/stock', methods=['GET'])"
if stock_marker in content and 'pin-purchase' not in content:
    content = content.replace(stock_marker, pin_purchase_endpoint + stock_marker)
    print("  Added pin-purchase endpoint")

with open(path, 'w') as f:
    f.write(content)
print("PATCH APPLIED SUCCESSFULLY")
print("\nVerification:")
import re
for tag in ['pin-purchase', '_get_pg_stock_connection', 'import psycopg2', 'pines_stock', 'pines_freefire']:
    count = content.count(tag)
    print(f"  '{tag}' found: {count} times")
