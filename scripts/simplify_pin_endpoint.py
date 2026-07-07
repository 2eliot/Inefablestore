#!/usr/bin/env python3
"""Replace pin_purchase_by_key with simplified version - no DB dependency"""
import re

with open('/home/apps/web-b-revendedores/connection_api.py', 'r') as f:
    content = f.read()

# The new simple endpoint - only uses PinManager, no DB queries
new_endpoint = '''
# --- PIN purchase by API Key (for InefableStore gift cards) ---
@connection_app.route('/api/connection/pin-purchase', methods=['POST'])
def pin_purchase_by_key():
    """Obtiene PIN del stock usando solo PinManager (sin BD de Revendedores).
    Valida por X-API-Key."""
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

        # --- Get PIN from stock (only PinManager, no Revendedores DB) ---
        pin_manager = create_pin_manager(DATABASE)
        
        if quantity == 1:
            result = pin_manager.request_pin(package_id)
            if result.get('status') != 'success':
                return jsonify({
                    'ok': False,
                    'error': f'Sin stock disponible: {result.get("message", "Error desconocido")}'
                }), 400
            pin_code = result.get('pin_code')
            return jsonify({
                'ok': True,
                'pin': pin_code,
                'source': result.get('source', 'unknown'),
                'package_id': package_id,
            })
        else:
            result = pin_manager.request_multiple_pins(package_id, quantity)
            if result.get('status') not in ['success', 'partial_success']:
                return jsonify({
                    'ok': False,
                    'error': f'Error al obtener PINs: {result.get("message", "Error desconocido")}'
                }), 400
            pines_data = result.get('pins', [])
            pins_list = [pin['pin_code'] for pin in pines_data]
            return jsonify({
                'ok': True,
                'pins': pins_list,
                'quantity': len(pins_list),
                'source': result.get('status', 'unknown'),
                'package_id': package_id,
            })

    except Exception as e:
        return jsonify({'ok': False, 'error': f'Error al procesar compra de PIN: {str(e)}'}), 500

'''

# Find the old endpoint and replace it
# The old endpoint starts with "@connection_app.route('/api/connection/pin-purchase'"
# and ends before "@connection_app.route('/api/connection/stock'"
old_pattern = r"# --- PIN purchase by API Key.*?@connection_app\.route\('/api/connection/pin-purchase'.*?(?=@connection_app\.route\('/api/connection/stock')"
replacement = new_endpoint.strip() + "\n\n"

content = re.sub(old_pattern, replacement, content, flags=re.DOTALL)

with open('/home/apps/web-b-revendedores/connection_api.py', 'w') as f:
    f.write(content)

# Verify syntax
import py_compile
try:
    py_compile.compile('/home/apps/web-b-revendedores/connection_api.py', doraise=True)
    print('Syntax OK - endpoint replaced successfully')
except py_compile.PyCompileError as e:
    print(f'Syntax error: {e}')
