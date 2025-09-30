import os
import re
import sys
from typing import List, Dict

# Import Flask app context and models from the project
try:
    from app import app, db, ImageAsset
except Exception as e:
    print("[error] No se pudo importar app/db/ImageAsset desde app.py:", e)
    sys.exit(1)

TS_PATTERN = re.compile(r"^(?P<base>.*)_\d{8}\d{6,}\.\w+$")

def _fs_path(public_path: str) -> str:
    """Convierte una ruta pública /static/... a ruta de archivo del sistema."""
    p = (public_path or "").strip()
    if not p.startswith("/static/"):
        return ""
    return os.path.join(app.root_path, p.lstrip("/"))


def delete_images_by_ids(ids: List[int]) -> None:
    deleted = []
    missing = []
    with app.app_context():
        for img_id in ids:
            img = ImageAsset.query.get(img_id)
            if not img:
                missing.append(img_id)
                continue
            # Intentar borrar archivo físico si está bajo uploads
            try:
                if (img.path or "").startswith("/static/uploads/"):
                    fp = _fs_path(img.path)
                    if fp and os.path.isfile(fp):
                        os.remove(fp)
            except Exception:
                # no bloquear por errores de filesystem
                pass
            db.session.delete(img)
            deleted.append(img_id)
        db.session.commit()
    print("[ok] Eliminados:", deleted)
    if missing:
        print("[warn] No encontrados:", missing)


def dedupe_keep_latest() -> None:
    """Elimina duplicados por nombre base (antes del sufijo timestamp), conservando el más reciente."""
    with app.app_context():
        imgs = ImageAsset.query.order_by(ImageAsset.uploaded_at.desc()).all()
        groups: Dict[str, List[ImageAsset]] = {}
        for img in imgs:
            title = img.title or ""
            m = TS_PATTERN.match(title)
            base = m.group("base") if m else title
            groups.setdefault(base, []).append(img)

        to_delete: List[ImageAsset] = []
        for base, arr in groups.items():
            # arr ya está ordenado desc por fecha; conservar el primero y borrar el resto
            for dup in arr[1:]:
                to_delete.append(dup)

        if not to_delete:
            print("[ok] No se encontraron duplicados por nombre base")
            return

        ids = [img.id for img in to_delete]
        delete_images_by_ids(ids)


def main(argv: List[str]) -> None:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(
            "Uso:\n"
            "  python scripts/cleanup_images.py 12 15 20      # eliminar por IDs\n"
            "  python scripts/cleanup_images.py --dedupe      # eliminar duplicados conservando el más reciente"
        )
        return

    if argv[0] == "--dedupe":
        dedupe_keep_latest()
        return

    try:
        ids = [int(x) for x in argv]
    except ValueError:
        print("[error] IDs inválidos. Proporcione enteros.")
        sys.exit(2)

    delete_images_by_ids(ids)


if __name__ == "__main__":
    main(sys.argv[1:])
