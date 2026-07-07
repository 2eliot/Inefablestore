#!/usr/bin/env python3
"""Replace pin_purchase_by_key with version that uses pines_freefire_global directly"""
import re

with open('/home/apps/web-b-revendedores/connection_api.py', 'r') as f:
    content = f.read()

new_endpoint = '''
# --- PIN purchase by API Key (for InefableStore gift cards) ---
@connection_app.route('/api/connection/pin-purchase', methods=['POST'])
def pin_purchase_by_key():
    """Obtiene PIN del stock global (pines_freefire_global) validando por X-API-Key.
    No depende de paquetes_dinamicos ni del saldo de usuarios de Revendedores."""
    try:
        # --- API Key validation ---
        env_key = os.environ.get('WEBB_API_KEY', '').strip()
        req_key = (
            (request.headers.get('X-API-Key') or '').strip()
            or (request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
            or (request.form.get('api_key') or '').strip()
            or (request.form.get('webb_api_key') or '').strip()
        )
        if not env_key or not req_key or req_key != env_key:
            return jsonify({'ok': False, 'error': 'API key invalida o no proporcionada'}), 401

        # --- Parse parameters ---
        package_id = request.form.get('package_id', '').strip()
        if not package_id:
            data = request.get_json(silent=True) or {}
            package_id = str(data.get('package_id', '')).strip()
        if not package_id:
            return jsonify({'ok': False, 'error': 'package_id es requerido'}), 400
        
        try:
            package_id = int(package_id)
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'package_id debe ser numerico'}), 400

        quantity_raw = request.form.get('quantity', '1').strip()
        try:
            quantity = int(quantity_raw)
        except (ValueError, TypeError):
            quantity = 1
        quantity = max(1, min(quantity, 10))

        # --- Get PIN directly from pines_freefire_global ---
        conn = get_db_connection()
        try:
            # Lock and get unused PINs
            rows = conn.execute('''
                SELECT id, pin_codigo FROM pines_freefire_global
                WHERE monto_id = ? AND usado = 0
                ORDER BY id ASC
                LIMIT ?
            ''', (package_id, quantity)).fetchall()
            
            if not rows:
                conn.close()
                return jsonify({
                    'ok': False,
                    'error': f'Sin stock disponible para monto_id={package_id}'
                }), 400
            
            pins_list = [row['pin_codigo'] for row in rows]
            ids_list = [row['id'] for row in rows]
            
            # Mark as used
            placeholders = ','.join(['?'] * len(ids_list))
            conn.execute(
                f'UPDATE pines_freefire_global SET usado=1, fecha_usado=CURRENT_TIMESTAMP WHERE id IN ({placeholders})',
                ids_list
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        
        pin_count = len(pins_list)
        if pin_count == 1:
            return jsonify({
                'ok': True,
                'pin': pins_list[0],
                'quantity': 1,
                'package_id': package_id,
                'source': 'pines_freefire_global',
            })
        else:
            return jsonify({
                'ok': True,
                'pins': pins_list,
                'quantity': pin_count,
                'package_id': package_id,
                'source': 'pines_freefire_global',
            })

    except Exception as e:
        return jsonify({'ok': False, 'error': f'Error al procesar compra de PIN: {str(e)}'}), 500

'''

old_pattern = r"# --- PIN purchase by API Key.*?@connection_app\.route\('/api/connection/pin-purchase'.*?(?=@connection_app\.route\('/api/connection/stock')"
content = re.sub(old_pattern, new_endpoint.strip() + "\n\n", content, flags=re.DOTALL)

with open('/home/apps/web-b-revendedores/connection_api.py', 'w') as f:
    f.write(content)

import py_compile
try:
    py_compile.compile('/home/apps/web-b-revendedores/connection_api.py', doraise=True)
    print('Syntax OK - endpoint replaced')
except py_compile.PyCompileError as e:
    print(f'Syntax error: {e}')
