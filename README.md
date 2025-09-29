# InefableStore - Admin

Administrador tipo "suit" con pestañas (Órdenes, Paquetes, Imágenes, Configuración) usando Flask, HTML, CSS y JS con base de datos SQLite.

## Requisitos
- Python 3.10+
- Windows

## Instalación (Windows)
1. Crear y activar entorno virtual:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instalar dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
3. Ejecutar la app:
   ```powershell
   $env:FLASK_APP="app.py"
   flask run --debug
   ```

La primera ejecución creará automáticamente la base de datos SQLite en `instance/inefablestore.sqlite`.

## Estructura
- `app.py`: App Flask, modelos y rutas básicas (admin).
- `templates/`: Plantillas HTML (Jinja2).
- `static/css/`: Estilos de administrador.
- `static/js/`: Lógica de pestañas (sin funcionalidad de botones todavía).

## Notas
- Los botones aún no tienen funcionalidad; se implementarán por partes para actualizar la interfaz principal dinámicamente.
- Los modelos (`Order`, `Package`, `ImageAsset`, `AppConfig`) están listos para futuras ampliaciones.
