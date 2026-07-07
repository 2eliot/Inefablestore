import os

with open('/home/apps/web-b-revendedores/connection_api.py', 'r') as f:
    content = f.read()

new_endpoint = '''
# --- PIN purchase by API Key (for InefableStore gift cards) ---
@connection_app.route('/api/connection/pin-purchase', methods=['POST'])
def pin_purchase_by_key():
    """Compra un PIN validando por X-API-Key (mismo esquema que Revendedores).
    Acepta form-data como /api/recharge/dynamic.
    
    Campos:
        package_id  - ID del paquete (requerido)
        quantity    - Cantidad (default 1, max 10)
        request_id  - Idempotencia (opcional)
        external_order_id - Para tracking (opcional)
    
    Respuesta:
        {"ok": true, "pin": "XXXX-XXXX-XXXX", ...}
        {"ok": false, "error": "..."}
    """
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

        request_id = (request.form.get('request_id') or '').strip()
        external_order_id = (request.form.get('external_order_id') or '').strip()

        # --- Get package info ---
        packages_info = get_package_info_with_prices()
        package_info = packages_info.get(package_id)
        if not package_info:
            return jsonify({'ok': False, 'error': f'Paquete {package_id} no encontrado'}), 404

        # --- Get PIN(s) from stock ---
        pin_manager = create_pin_manager(DATABASE)
        pins_list = []
        local_pins_reserved = []

        if quantity == 1:
            result = pin_manager.request_pin(package_id)
            if result.get('status') != 'success':
                return jsonify({
                    'ok': False,
                    'error': f'Sin stock disponible: {result.get("message", "Error desconocido")}'
                }), 400
            pin_code = result.get('pin_code')
            pins_list = [pin_code]
            if result.get('source') == 'local_stock' and pin_code:
                local_pins_reserved = [pin_code]
        else:
            result = pin_manager.request_multiple_pins(package_id, quantity)
            if result.get('status') not in ['success', 'partial_success']:
                return jsonify({
                    'ok': False,
                    'error': f'Error al obtener PINs: {result.get("message", "Error desconocido")}'
                }), 400
            pines_data = result.get('pins', [])
            pins_list = [pin['pin_code'] for pin in pines_data]
            local_pins_reserved = [pin['pin_code'] for pin in pines_data if pin.get('source') == 'local_stock' and pin.get('pin_code')]
            quantity = len(pins_list)

        if not pins_list:
            if local_pins_reserved:
                pin_manager.restore_local_pins(package_id, local_pins_reserved)
            return jsonify({'ok': False, 'error': 'No se pudieron obtener PINs del stock'}), 500

        # --- Create transaction record ---
        pins_texto = '\n'.join(pins_list)
        paquete_nombre = f"{package_info['nombre']} x{quantity}" if quantity > 1 else package_info['nombre']
        
        conn = get_db_connection()
        try:
            trans_data = create_transaction_record(0, pins_texto, paquete_nombre, package_info['precio'] * quantity, conn=conn, request_id=request_id or external_order_id)
            conn.commit()
        except Exception:
            conn.rollback()
            if local_pins_reserved:
                pin_manager.restore_local_pins(package_id, local_pins_reserved)
            raise
        finally:
            conn.close()

        response_data = {
            'ok': True,
            'package_name': package_info['nombre'],
            'package_description': package_info['descripcion'],
            'price_per_unit': float(package_info['precio']),
            'quantity': quantity,
            'total_price': float(package_info['precio'] * quantity),
            'transaction_id': trans_data['transaccion_id'],
            'reference_no': trans_data['numero_control'],
        }
        if quantity == 1:
            response_data['pin'] = pins_list[0]
        else:
            response_data['pins'] = pins_list

        return jsonify(response_data)

    except Exception as e:
        try:
            if 'pin_manager' in locals() and local_pins_reserved:
                pin_manager.restore_local_pins(package_id, local_pins_reserved)
        except Exception:
            pass
        return jsonify({'ok': False, 'error': f'Error al procesar compra de PIN: {str(e)}'}), 500

'''

insert_marker = "@connection_app.route('/api/connection/stock', methods=['GET'])"
content = content.replace(insert_marker, new_endpoint + insert_marker)

with open('/home/apps/web-b-revendedores/connection_api.py', 'w') as f:
    f.write(content)

print('Endpoint inserted successfully')
print(f'File size: {len(content)} bytes')
