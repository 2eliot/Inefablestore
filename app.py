import os
import shutil
from datetime import datetime
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create Flask app
app = Flask(__name__, instance_relative_config=True)
load_dotenv()

# Ensure instance folder exists for local SQLite default
os.makedirs(app.instance_path, exist_ok=True)

# Basic configuration with DATABASE_URL (Postgres) or persistent Disk (SQLite)
DB_URL = os.environ.get("DATABASE_URL", "").strip()
if DB_URL:
    # Normalize scheme for SQLAlchemy/psycopg2
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
else:
    SQLITE_PATH = os.environ.get("SQLITE_PATH", "").strip()
    if SQLITE_PATH:
        try:
            os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
        except Exception:
            pass
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{SQLITE_PATH}"
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "inefablestore.sqlite")

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

DEFAULT_UPLOAD = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", DEFAULT_UPLOAD)
# Public URL prefix that points to where images are served from.
# If using persistent Disk (outside static), set UPLOAD_URL_PREFIX=/uploads and UPLOAD_FOLDER to the mounted path.
app.config["UPLOAD_URL_PREFIX"] = os.environ.get("UPLOAD_URL_PREFIX", "/static/uploads")
try:
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
except Exception:
    pass
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable static caching in debug
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@inefablestore.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")
# Email settings (use app password)
MAIL_USER = os.environ.get("MAIL_USER", "")
MAIL_APP_PASSWORD = os.environ.get("MAIL_APP_PASSWORD", "")
MAIL_SMTP_HOST = os.environ.get("MAIL_SMTP_HOST", "smtp.gmail.com")
MAIL_SMTP_PORT = int(os.environ.get("MAIL_SMTP_PORT", "587"))
ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "")  # default destination for new order alerts

db = SQLAlchemy(app)

# ==============================
# Serve uploaded files (runtime uploads)
# ==============================
# This enables serving files stored in UPLOAD_FOLDER under a public URL.
# Recommended for Render: set UPLOAD_FOLDER to a writable path (e.g. /var/tmp/uploads)
# and UPLOAD_URL_PREFIX to '/uploads'.
prefix = (app.config.get("UPLOAD_URL_PREFIX") or "/uploads").rstrip("/")
if prefix == "":
    prefix = "/uploads"

@app.route(f"{prefix}/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Models
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    # associations
    store_package_id = db.Column(db.Integer, nullable=False)
    item_id = db.Column(db.Integer, nullable=True)
    # buyer info
    customer_name = db.Column(db.String(200), default="")  # legacy support
    customer_id = db.Column(db.String(120), default="")  # game ID
    customer_zone = db.Column(db.String(120), default="")  # optional Zone ID
    name = db.Column(db.String(200), default="")
    email = db.Column(db.String(200), default="")
    phone = db.Column(db.String(80), default="")
    # payment
    method = db.Column(db.String(20), default="")  # pm | binance
    currency = db.Column(db.String(10), default="USD")
    amount = db.Column(db.Float, default=0.0)
    reference = db.Column(db.String(120), default="")
    price = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)
    # Gift card or delivery code (for gift category)
    delivery_code = db.Column(db.String(200), default="")
    # Optional: multiple gift codes for gift card orders
    delivery_codes_json = db.Column(db.Text, default="")
    # Special referral code support
    special_code = db.Column(db.String(80), default="")
    special_user_id = db.Column(db.Integer, nullable=True)
    # Optional: JSON string with multiple items: [{"item_id": int, "qty": int, "title": str, "price": float}]
    items_json = db.Column(db.Text, default="")

# ==============================
# Email helper
# ==============================
def _smtp_send_starttls(msg, to_email):
    # STARTTLS on port (default 587)
    with smtplib.SMTP(MAIL_SMTP_HOST, MAIL_SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(MAIL_USER, (MAIL_APP_PASSWORD or '').replace(' ', ''))
        server.sendmail(MAIL_USER, to_email, msg.as_string())


def _smtp_send_ssl(msg, to_email):
    # SSL on 465 (fallback)
    port = 465
    with smtplib.SMTP_SSL(MAIL_SMTP_HOST, port, timeout=15) as server:
        server.login(MAIL_USER, (MAIL_APP_PASSWORD or '').replace(' ', ''))
        server.sendmail(MAIL_USER, to_email, msg.as_string())


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not MAIL_USER or not MAIL_APP_PASSWORD or not to_email:
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body or "", 'plain'))
        try:
            _smtp_send_starttls(msg, to_email)
            return True
        except Exception:
            # Fallback to SSL 465
            _smtp_send_ssl(msg, to_email)
            return True
    except Exception:
        return False

def send_email_async(to_email: str, subject: str, body: str) -> None:
    def _runner():
        try:
            send_email(to_email, subject, body)
        except Exception:
            pass
    try:
        t = threading.Thread(target=_runner, daemon=True)
        t.start()
    except Exception:
        # fallback to sync (best effort)
        try:
            send_email(to_email, subject, body)
        except Exception:
            pass

# HTML email support
def send_email_html(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    if not MAIL_USER or not MAIL_APP_PASSWORD or not to_email:
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body or "", 'html', 'utf-8'))
        try:
            _smtp_send_starttls(msg, to_email)
            return True
        except Exception:
            _smtp_send_ssl(msg, to_email)
            return True
    except Exception:
        return False

def build_order_approved_email(o: 'Order', pkg: 'StorePackage', it: 'GamePackageItem'):
    # Brand title instead of logo; support via WhatsApp if configured
    support_url = get_config_value("support_url", "") or "#"
    whatsapp_url = get_config_value("whatsapp_url", "https://api.whatsapp.com/send?phone=%2B584125712917&context=Aff7qdKb5GW1QQopWoY5hu5m7aqDlXIwIePiy5n9tHAbOwwr7S_MpuFfFShRCkwT3obW4f_deI_-Pn-lIqpXebAyMVygTiqDvi2nUus8r-8gIUZPXawe5ygyCSYTu_9gnBCaSb_Hpta6aVnEAFw&source=FB_Page&app=facebook&entry_point=page_cta&fbclid=IwY2xjawNIxQhleHRuA2FlbQIxMABicmlkETAzV1c0cGtnNWZ0NDRLeFBLAR7pcNiHoxI3HNYArGiUIh2FTQpQWZSpIC2UBGHmUgayIhB8A4ziqRKz2Ttq1g_aem_vO-bNFKE2SRZSSZHa_Faow") or support_url or "#"
    privacy_url = get_config_value("privacy_url", "") or "#"
    unsubscribe_url = get_config_value("unsubscribe_url", "") or "#"
    juego = (pkg.name if pkg else '').strip()
    item_t = (it.title if it else 'N/A')
    monto = f"{o.amount} {o.currency}"
    is_gift = (pkg.category or '').lower() == 'gift' if pkg else False
    # Delivery codes (single or multiple)
    code_row = ''
    try:
        codes = []
        if (o.delivery_codes_json or '').strip():
            parsed = json.loads(o.delivery_codes_json or '[]')
            if isinstance(parsed, list):
                codes = [str(x or '').strip() for x in parsed if str(x or '').strip()]
        if not codes and (o.delivery_code or '').strip():
            codes = [o.delivery_code.strip()]
        if codes:
            rows = []
            for idx, c in enumerate(codes, start=1):
                label = 'Código' if len(codes) == 1 else f'Código #{idx}'
                rows.append(f"""
            <tr>
                <td style=\"color: #bbbbbb; font-size: 14px; padding-left: 0;\"><strong>{label}:</strong></td>
                <td align=\"right\" style=\"color: #ffffff; font-size: 14px; padding-right: 0;\">{c}</td>
            </tr>
                """)
            code_row = "\n".join(rows)
    except Exception:
        code_row = code_row
    # Build items section for multi-item orders
    items_section = ""
    try:
        if (o.items_json or '').strip():
            items = json.loads(o.items_json or '[]')
            if isinstance(items, list) and items:
                # rows for each item
                item_rows = []
                for ent in items:
                    t = ent.get('title')
                    q = int(ent.get('qty') or 1)
                    try:
                        p = float(ent.get('price') or 0.0)
                    except Exception:
                        p = 0.0
                    item_rows.append(f"""
              <tr>
                <td style=\"color:#bbbbbb; font-size:14px; padding-left:0;\"><strong>{q} x</strong></td>
                <td align=\"right\" style=\"color:#ffffff; font-size:14px; padding-right:0;\">{t} · ${p:.2f} c/u</td>
              </tr>
                    """)
                items_section = "\n".join(item_rows)
    except Exception:
        items_section = ""

    # Compute total quantity and label
    qty_total = 1
    try:
        if (o.items_json or '').strip():
            items = json.loads(o.items_json or '[]')
            if isinstance(items, list) and items:
                qty_total = sum(int(ent.get('qty') or 1) for ent in items)
    except Exception:
        qty_total = 1
    qty_label = 'Cantidad de tarjetas' if is_gift else 'Recargas totales'
    qty_row = f"""
              <tr>
                <td style=\"color:#bbbbbb; font-size:14px; padding-left:0;\"><strong>{qty_label}:</strong></td>
                <td align=\"right\" style=\"color:#ffffff; font-size:14px; padding-right:0;\">{qty_total}</td>
              </tr>
    """

    html = f"""
<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Orden Aprobada - Inefable Store</title>
  <style type=\"text/css\">body, table, td, a {{ font-family: Arial, sans-serif; }}</style>
</head>
<body style=\"margin:0; padding:0; background-color:#1a1a1a;\">
  <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"table-layout:fixed; background-color:#1a1a1a;\">
    <tr><td align=\"center\" style=\"padding:20px 0;\">
      <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"max-width:600px; background-color:#2c2c2c; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.4);\">
        <tr>
          <td align=\"center\" style=\"padding:26px 20px 16px;\">
            <div style=\"display:inline-block; font-weight:900; font-size:22px; letter-spacing:1px; color:#ffffff;\">INEFABLESTOR</div>
          </td>
        </tr>
        <tr>
          <td align=\"center\" style=\"padding:10px 20px;\">
            <h1 style=\"color:#4CAF50; font-size:24px; margin:0; padding:0;\">¡{'Gift enviado' if is_gift else 'Recarga Exitosa'}!</h1>
          </td>
        </tr>
        <tr>
          <td style=\"padding:20px 40px;\">
            <p style=\"color:#f4f4f4; font-size:16px; line-height:24px; margin-top:0;\"><strong>Estimado cliente,</strong></p>
            <p style=\"color:#cccccc; font-size:16px; line-height:24px;\">Nos complace informarle que su orden ha sido procesada con éxito. A continuación, el detalle de su transacción:</p>
          </td>
        </tr>
        <tr>
          <td style=\"padding:10px 40px;\">
            <table border=\"0\" cellpadding=\"10\" cellspacing=\"0\" width=\"100%\" style=\"background-color:#383838; border:1px solid #444444; border-radius:4px;\">
              <tr>
                <td width=\"50%\" style=\"color:#bbbbbb; font-size:14px; padding-left:0;\"><strong>Orden #:</strong></td>
                <td width=\"50%\" align=\"right\" style=\"color:#ffffff; font-size:14px; padding-right:0;\">{o.id}</td>
              </tr>
              <tr>
                <td style=\"color:#bbbbbb; font-size:14px; padding-left:0;\"><strong>Producto:</strong></td>
                <td align=\"right\" style=\"color:#ffffff; font-size:14px; padding-right:0;\">{juego}</td>
              </tr>
              {items_section if items_section else f'<tr>\n                <td style=\\"color:#bbbbbb; font-size:14px; padding-left:0;\\"><strong>Paquete:</strong></td>\n                <td align=\\"right\\" style=\\"color:#ffffff; font-size:14px; padding-right:0;\\">{item_t}</td>\n              </tr>'}
              {code_row}
              {qty_row}
              <tr style=\"border-top:1px solid #555555;\">
                <td style=\"color:#ffffff; font-size:16px; font-weight:bold; padding-left:0;\"><strong>Monto Total:</strong></td>
                <td align=\"right\" style=\"color:#4CAF50; font-size:16px; font-weight:bold; padding-right:0;\">{monto}</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style=\"padding:30px 40px 20px;\">
            <p style=\"color:#cccccc; font-size:16px; line-height:24px;\">Agradecemos su preferencia y confianza en Inefable Store. Si necesita asistencia adicional o tiene alguna consulta, no dude en contactarnos. ¡Estamos para servirle!</p>
            <p style=\"color:#f4f4f4; font-size:16px; line-height:24px; margin-bottom:0;\">Atentamente,<br>El equipo de Inefable Store</p>
          </td>
        </tr>
        <tr>
          <td align=\"center\" style=\"padding: 20px 40px 30px;\">
            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\"><tr>
              <td align=\"center\" style=\"border-radius:5px;\" bgcolor=\"#009688\">
                <a href=\"{whatsapp_url}\" target=\"_blank\" style=\"font-size:16px; font-family:Arial, sans-serif; color:#ffffff; text-decoration:none; padding:12px 25px; border-radius:5px; border:1px solid #009688; display:inline-block;\">Contactar a Soporte</a>
              </td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td align=\"center\" style=\"padding:20px 40px; background-color:#383838; border-radius:0 0 8px 8px;\">
            <p style=\"color:#999999; font-size:12px; line-height:18px; margin:0;\">&copy; {datetime.utcnow().year} Inefable Store. Todos los derechos reservados.</p>
            <p style=\"color:#999999; font-size:12px; line-height:18px; margin-top:5px;\"><a href=\"{unsubscribe_url}\" target=\"_blank\" style=\"color:#009688; text-decoration:underline;\">Darse de baja</a> | <a href=\"{privacy_url}\" target=\"_blank\" style=\"color:#009688; text-decoration:underline;\">Política de Privacidad</a></p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
    # Plain text summary
    try:
        lines = [
            "Estimado cliente,\n",
            "Su orden ha sido procesada con éxito.",
            f"Orden #{o.id} – {juego}",
        ]
        if (o.items_json or '').strip():
            items = json.loads(o.items_json or '[]')
            if isinstance(items, list) and items:
                lines.append("Paquetes:")
                for ent in items:
                    t = ent.get('title')
                    q = int(ent.get('qty') or 1)
                    try:
                        p = float(ent.get('price') or 0.0)
                    except Exception:
                        p = 0.0
                    lines.append(f" - {q} x {t} (${p:.2f} c/u)")
        else:
            lines.append(f"Paquete: {item_t}")
        lines.append(f"{qty_label}: {qty_total}")
        lines.append(f"Monto: {monto}")
        # Include gift codes in text email
        try:
            codes_txt = []
            if (o.delivery_codes_json or '').strip():
                parsed = json.loads(o.delivery_codes_json or '[]')
                if isinstance(parsed, list):
                    codes_txt = [str(x or '').strip() for x in parsed if str(x or '').strip()]
            if not codes_txt and (o.delivery_code or '').strip():
                codes_txt = [o.delivery_code.strip()]
            if codes_txt:
                if len(codes_txt) == 1:
                    lines.append(f"Código: {codes_txt[0]}")
                else:
                    lines.append("Códigos:")
                    for i, c in enumerate(codes_txt, start=1):
                        lines.append(f" - #{i}: {c}")
        except Exception:
            pass
        if (o.delivery_code or '').strip():
            lines.append(f"Código: {o.delivery_code}")
        lines.append("\nGracias por su preferencia.")
        text = "\n".join(lines)
    except Exception:
        text = (
            "Estimado cliente,\n\n"
            "Su orden ha sido procesada con éxito.\n"
            f"Orden #{o.id} – {juego}\n"
            f"Paquete: {item_t}\n"
            f"Monto: {monto}\n"
            + (f"Código: {o.delivery_code}\n" if (o.delivery_code or '').strip() else "")
            + "\nGracias por su preferencia."
        )
    return html, text


class StorePackage(db.Model):
    __tablename__ = "store_packages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    image_path = db.Column(db.String(300), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # category: 'mobile' (JUEGOS MOBILE) or 'gift' (GIFT CARDS)
    category = db.Column(db.String(20), default="mobile")
    description = db.Column(db.Text, default="")
    # whether this game requires an extra Zone ID
    requires_zone_id = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

class GamePackageItem(db.Model):
    __tablename__ = "game_packages"
    id = db.Column(db.Integer, primary_key=True)
    store_package_id = db.Column(db.Integer, db.ForeignKey("store_packages.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, default=0.0)
    # Optional small label/badge to show on the package (e.g., HOT, NEW)
    sticker = db.Column(db.String(50), default="")
    # Optional small icon shown next to the item title in details page
    icon_path = db.Column(db.String(300), default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ImageAsset(db.Model):
    __tablename__ = "images"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    path = db.Column(db.String(300), nullable=False)  # relative path under static/img or uploads
    alt_text = db.Column(db.String(200), default="")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class AppConfig(db.Model):
    __tablename__ = "config"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")

class SpecialUser(db.Model):
    __tablename__ = "special_users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="")
    code = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=True)
    password_hash = db.Column(db.String(300), nullable=True)
    balance = db.Column(db.Float, default=0.0)  # earned commissions in USD
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Discount settings
    discount_percent = db.Column(db.Float, default=10.0)  # percent, e.g. 10 means 10%
    scope = db.Column(db.String(20), default="all")  # 'all' | 'package'
    scope_package_id = db.Column(db.Integer, nullable=True)
    # Category-specific discounts and commissions
    discount_mobile_percent = db.Column(db.Float, default=0.0)
    discount_gift_percent = db.Column(db.Float, default=0.0)
    commission_percent = db.Column(db.Float, default=10.0)
    commission_mobile_percent = db.Column(db.Float, default=0.0)
    commission_gift_percent = db.Column(db.Float, default=0.0)


class AffiliateWithdrawal(db.Model):
    __tablename__ = "affiliate_withdrawals"
    id = db.Column(db.Integer, primary_key=True)
    affiliate_id = db.Column(db.Integer, nullable=False)
    amount_usd = db.Column(db.Float, nullable=False, default=0.0)
    method = db.Column(db.String(20), default="pm")  # pm | binance | zinli
    pm_bank = db.Column(db.String(120), default="")
    pm_name = db.Column(db.String(200), default="")
    pm_phone = db.Column(db.String(80), default="")
    pm_id = db.Column(db.String(40), default="")
    binance_email = db.Column(db.String(200), default="")
    binance_phone = db.Column(db.String(80), default="")
    zinli_email = db.Column(db.String(200), default="")
    zinli_tag = db.Column(db.String(80), default="")
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="")
    email = db.Column(db.String(200), unique=True, nullable=False)
    phone = db.Column(db.String(80), default="")
    password_hash = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize
with app.app_context():
    db.create_all()
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    # Ensure legacy DB gets the new 'category' column (SQLite runtime migration)
    try:
        from sqlalchemy import text
        info = db.session.execute(text("PRAGMA table_info(store_packages)")).fetchall()
        cols = {row[1] for row in info}
        if "category" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN category TEXT DEFAULT 'mobile'"))
            db.session.commit()
        if "description" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN description TEXT DEFAULT ''"))
            db.session.commit()
        if "requires_zone_id" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN requires_zone_id INTEGER DEFAULT 0"))
            db.session.commit()
        if "sort_order" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN sort_order INTEGER DEFAULT 0"))
            db.session.commit()
        # Orders table migration: add missing columns if an older schema exists
        info_orders = db.session.execute(text("PRAGMA table_info(orders)")).fetchall()
        order_cols = {row[1] for row in info_orders}
        def add_order_col(name, ddl):
            if name not in order_cols:
                db.session.execute(text(f"ALTER TABLE orders ADD COLUMN {ddl}"))
        if info_orders:  # table exists
            add_order_col('customer_name', "customer_name TEXT DEFAULT ''")
            add_order_col('created_at', "created_at TEXT")
            add_order_col('status', "status TEXT DEFAULT 'pending'")
            add_order_col('store_package_id', "store_package_id INTEGER")
            add_order_col('item_id', "item_id INTEGER")
            add_order_col('customer_id', "customer_id TEXT DEFAULT ''")
            add_order_col('customer_zone', "customer_zone TEXT DEFAULT ''")
            add_order_col('name', "name TEXT DEFAULT ''")
            add_order_col('email', "email TEXT DEFAULT ''")
            add_order_col('phone', "phone TEXT DEFAULT ''")
            add_order_col('method', "method TEXT DEFAULT ''")
            add_order_col('currency', "currency TEXT DEFAULT 'USD'")
            add_order_col('amount', "amount REAL DEFAULT 0")
            add_order_col('reference', "reference TEXT DEFAULT ''")
            # Optional columns used in model defaults
            add_order_col('price', "price REAL DEFAULT 0")
            add_order_col('active', "active INTEGER DEFAULT 1")
            add_order_col('delivery_code', "delivery_code TEXT DEFAULT ''")
            add_order_col('delivery_codes_json', "delivery_codes_json TEXT DEFAULT ''")
            add_order_col('special_code', "special_code TEXT DEFAULT ''")
            add_order_col('special_user_id', "special_user_id INTEGER")
            add_order_col('items_json', "items_json TEXT DEFAULT ''")
            db.session.commit()
        # Special users table migration: ensure new columns
        try:
            info_aff = db.session.execute(text("PRAGMA table_info(special_users)")).fetchall()
            aff_cols = {row[1] for row in info_aff}
            if "email" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN email TEXT"))
            if "password_hash" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN password_hash TEXT"))
            if "discount_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN discount_percent REAL DEFAULT 10.0"))
            if "scope" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN scope TEXT DEFAULT 'all'"))
            if "scope_package_id" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN scope_package_id INTEGER"))
            if "discount_mobile_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN discount_mobile_percent REAL DEFAULT 0.0"))
            if "discount_gift_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN discount_gift_percent REAL DEFAULT 0.0"))
            if "commission_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN commission_percent REAL DEFAULT 10.0"))
            if "commission_mobile_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN commission_mobile_percent REAL DEFAULT 0.0"))
            if "commission_gift_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN commission_gift_percent REAL DEFAULT 0.0"))
            db.session.commit()
        except Exception:
            pass
        # Ensure affiliate_withdrawals exists (create_all covers it, but keep for safety)
        try:
            db.session.execute(text("SELECT 1 FROM affiliate_withdrawals LIMIT 1"))
        except Exception:
            try:
                db.create_all()
            except Exception:
                pass
        # Add zinli columns if missing
        try:
            info_wd = db.session.execute(text("PRAGMA table_info(affiliate_withdrawals)")).fetchall()
            wd_cols = {row[1] for row in info_wd}
            if "zinli_email" not in wd_cols:
                db.session.execute(text("ALTER TABLE affiliate_withdrawals ADD COLUMN zinli_email TEXT"))
            if "zinli_tag" not in wd_cols:
                db.session.execute(text("ALTER TABLE affiliate_withdrawals ADD COLUMN zinli_tag TEXT"))
            db.session.commit()
        except Exception:
            pass
    except Exception as e:
        # Safe to ignore if not SQLite or column already exists
        pass

    # Ensure new columns in game_packages (sticker)
    try:
        from sqlalchemy import text
        gp_info = db.session.execute(text("PRAGMA table_info(game_packages)")).fetchall()
        gp_cols = {row[1] for row in gp_info}
        if "sticker" not in gp_cols:
            db.session.execute(text("ALTER TABLE game_packages ADD COLUMN sticker TEXT DEFAULT ''"))
            db.session.commit()
        if "icon_path" not in gp_cols:
            db.session.execute(text("ALTER TABLE game_packages ADD COLUMN icon_path TEXT DEFAULT ''"))
            db.session.commit()
    except Exception:
        pass

# ==============================
# Special Users API
# ==============================

@app.route("/admin/special/users", methods=["GET"])
def admin_special_users_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    rows = SpecialUser.query.order_by(SpecialUser.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "users": [
            {"id": u.id, "name": u.name, "code": u.code, "email": u.email or "", "balance": float(u.balance or 0.0), "active": bool(u.active),
             "discount_percent": float(u.discount_percent or 0.0),
             "discount_mobile_percent": float(u.discount_mobile_percent or 0.0),
             "discount_gift_percent": float(u.discount_gift_percent or 0.0),
             "scope": u.scope or 'all', "scope_package_id": u.scope_package_id}
            for u in rows
        ]
    })

@app.route("/admin/special/users", methods=["POST"])
def admin_special_users_create():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    try:
        discount_percent = float(data.get("discount_percent") or 0)
    except Exception:
        discount_percent = 0.0
    scope = (data.get("scope") or "all").strip().lower()
    scope_package_id = data.get("scope_package_id")
    try:
        scope_package_id = int(scope_package_id) if scope_package_id is not None and f"{scope_package_id}" != "" else None
    except Exception:
        scope_package_id = None
    if not code:
        return jsonify({"ok": False, "error": "Código requerido"}), 400
    if SpecialUser.query.filter(db.func.lower(SpecialUser.code) == code.lower()).first():
        return jsonify({"ok": False, "error": "Código ya existe"}), 400
    if email:
        if SpecialUser.query.filter(db.func.lower(SpecialUser.email) == email.lower()).first():
            return jsonify({"ok": False, "error": "Email ya existe"}), 400
    # Optional extended fields
    def fget(key, default=0.0):
        try:
            return float(data.get(key) or default)
        except Exception:
            return default
    su = SpecialUser(name=name, code=code, email=email or None, active=bool(data.get("active", True)), balance=float(data.get("balance") or 0.0),
                     discount_percent=discount_percent,
                     discount_mobile_percent=fget("discount_mobile_percent", 0.0),
                     discount_gift_percent=fget("discount_gift_percent", 0.0),
                     commission_percent=fget("commission_percent", 10.0),
                     commission_mobile_percent=fget("commission_mobile_percent", 0.0),
                     commission_gift_percent=fget("commission_gift_percent", 0.0),
                     scope=scope if scope in ("all","package") else "all", scope_package_id=scope_package_id)
    if password:
        su.password_hash = generate_password_hash(password)
    db.session.add(su)
    db.session.commit()
    return jsonify({"ok": True, "user": {"id": su.id, "name": su.name, "code": su.code, "email": su.email or "", "balance": su.balance, "active": su.active,
            "discount_percent": su.discount_percent,
            "discount_mobile_percent": su.discount_mobile_percent,
            "discount_gift_percent": su.discount_gift_percent,
            "scope": su.scope, "scope_package_id": su.scope_package_id }})

@app.route("/admin/special/users/<int:uid>", methods=["PATCH", "PUT"])
def admin_special_users_update(uid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    su = SpecialUser.query.get(uid)
    if not su:
        return jsonify({"ok": False, "error": "No existe"}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data:
        su.name = (data.get("name") or '').strip()
    if "code" in data:
        new_code = (data.get("code") or '').strip()
        if new_code and new_code.lower() != (su.code or '').lower():
            if SpecialUser.query.filter(db.func.lower(SpecialUser.code) == new_code.lower()).first():
                return jsonify({"ok": False, "error": "Código ya existe"}), 400
            su.code = new_code
    if "email" in data:
        new_email = (data.get("email") or '').strip()
        if new_email and new_email.lower() != ((su.email or '').lower()):
            if SpecialUser.query.filter(db.func.lower(SpecialUser.email) == new_email.lower()).first():
                return jsonify({"ok": False, "error": "Email ya existe"}), 400
            su.email = new_email
    if "password" in data:
        pwd = (data.get("password") or '').strip()
        if pwd:
            su.password_hash = generate_password_hash(pwd)
    if "active" in data:
        su.active = bool(data.get("active"))
    if "balance" in data:
        try:
            su.balance = float(data.get("balance") or 0.0)
        except Exception:
            pass
    if "discount_percent" in data:
        try:
            su.discount_percent = float(data.get("discount_percent") or 0.0)
        except Exception:
            pass
    # Optional extended fields
    for k in ("discount_mobile_percent", "discount_gift_percent", "commission_percent", "commission_mobile_percent", "commission_gift_percent"):
        if k in data:
            try:
                setattr(su, k, float(data.get(k) or 0.0))
            except Exception:
                pass
    if "scope" in data:
        sc = (data.get("scope") or "all").strip().lower()
        if sc in ("all","package"):
            su.scope = sc
    if "scope_package_id" in data:
        val = data.get("scope_package_id")
        try:
            su.scope_package_id = int(val) if val is not None and f"{val}" != "" else None
        except Exception:
            su.scope_package_id = None
    db.session.commit()
    return jsonify({"ok": True})


# ==============================
# Affiliate summary API
# ==============================
@app.route("/affiliate/summary")
def affiliate_summary():
    user = session.get("user")
    if not user or user.get("role") != "affiliate":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    aff_id = user.get("affiliate_id")
    su = SpecialUser.query.get(aff_id) if aff_id else None
    if not su:
        return jsonify({"ok": False, "error": "Afiliado no encontrado"}), 404
    from sqlalchemy import or_
    approved_q = Order.query.filter(
        Order.status == "approved",
        or_(Order.special_user_id == su.id, Order.special_code == (su.code or ""))
    )
    approved_count = approved_q.count()
    return jsonify({
        "ok": True,
        "code": su.code or "",
        "approved_orders": int(approved_count),
        "balance_usd": float(su.balance or 0.0),
    })


# ==============================
# Affiliate withdrawals API (self-service)
# ==============================
@app.route("/affiliate/withdrawals", methods=["GET"])
def affiliate_withdrawals_list():
    user = session.get("user")
    if not user or user.get("role") != "affiliate":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    aff_id = user.get("affiliate_id")
    rows = AffiliateWithdrawal.query.filter_by(affiliate_id=aff_id).order_by(AffiliateWithdrawal.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "items": [
            {
                "id": r.id,
                "amount_usd": float(r.amount_usd or 0.0),
                "method": r.method,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "processed_at": (r.processed_at.isoformat() if r.processed_at else None),
                "pm_bank": r.pm_bank,
                "pm_name": r.pm_name,
                "pm_phone": r.pm_phone,
                "pm_id": r.pm_id,
                "binance_email": r.binance_email,
                "binance_phone": r.binance_phone,
                "zinli_email": r.zinli_email,
                "zinli_tag": r.zinli_tag,
            }
            for r in rows
        ]
    })


@app.route("/affiliate/withdrawals", methods=["POST"])
def affiliate_withdrawals_create():
    user = session.get("user")
    if not user or user.get("role") != "affiliate":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    aff_id = user.get("affiliate_id")
    su = SpecialUser.query.get(aff_id)
    if not su or not su.active:
        return jsonify({"ok": False, "error": "Afiliado inválido"}), 400
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount_usd") or 0)
    except Exception:
        amount = 0.0
    if amount <= 0:
        return jsonify({"ok": False, "error": "Monto inválido"}), 400
    if amount > float(su.balance or 0.0):
        return jsonify({"ok": False, "error": "Fondos insuficientes"}), 400
    method = (data.get("method") or "pm").strip().lower()
    if method not in ("pm", "binance", "zinli"):
        return jsonify({"ok": False, "error": "Método inválido"}), 400
    r = AffiliateWithdrawal(
        affiliate_id=aff_id,
        amount_usd=amount,
        method=method,
        pm_bank=(data.get("pm_bank") or ""),
        pm_name=(data.get("pm_name") or ""),
        pm_phone=(data.get("pm_phone") or ""),
        pm_id=(data.get("pm_id") or ""),
        binance_email=(data.get("binance_email") or ""),
        binance_phone=(data.get("binance_phone") or ""),
        zinli_email=(data.get("zinli_email") or ""),
        zinli_tag=(data.get("zinli_tag") or ""),
        status="pending",
    )
    db.session.add(r)
    db.session.commit()
    # Notify admin: new affiliate withdrawal request
    try:
        to_addr = get_config_value("admin_notify_email", ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL)
        lines = [
            f"Nuevo retiro de afiliado #{r.id}",
            f"Afiliado: {su.name or '#'} (ID {su.id})",
            f"Monto: ${float(r.amount_usd or 0.0):.2f}",
            f"Método: {r.method.upper()}",
        ]
        if r.method == 'pm':
            lines.append(f"Pago Móvil: {r.pm_bank} · {r.pm_name} · {r.pm_phone} · {r.pm_id}")
        elif r.method == 'binance':
            lines.append(f"Binance: {r.binance_email} · {r.binance_phone}")
        elif r.method == 'zinli':
            lines.append(f"Zinli: {r.zinli_email} · {r.zinli_tag}")
        lines.append(f"Fecha: {r.created_at.isoformat()}")
        send_email(to_addr, f"Retiro afiliado #{r.id} pendiente", "\n".join(lines))
    except Exception:
        pass
    return jsonify({"ok": True, "id": r.id})


# ==============================
# Admin: affiliate withdrawals moderation
# ==============================
@app.route("/admin/affiliate/withdrawals")
def admin_affiliate_withdrawals_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    rows = AffiliateWithdrawal.query.order_by(AffiliateWithdrawal.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "items": [
            {
                "id": r.id,
                "affiliate_id": r.affiliate_id,
                "affiliate_name": (SpecialUser.query.get(r.affiliate_id).name if SpecialUser.query.get(r.affiliate_id) else "#"),
                "amount_usd": float(r.amount_usd or 0.0),
                "method": r.method,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "processed_at": (r.processed_at.isoformat() if r.processed_at else None),
                "pm_bank": r.pm_bank,
                "pm_name": r.pm_name,
                "pm_phone": r.pm_phone,
                "pm_id": r.pm_id,
                "binance_email": r.binance_email,
                "binance_phone": r.binance_phone,
                "zinli_email": r.zinli_email,
                "zinli_tag": r.zinli_tag,
            }
            for r in rows
        ]
    })


@app.route("/admin/affiliate/withdrawals/<int:w_id>/status", methods=["POST"])
def admin_affiliate_withdrawals_set_status(w_id: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()  # approved | rejected
    r = AffiliateWithdrawal.query.get(w_id)
    if not r:
        return jsonify({"ok": False, "error": "Solicitud no existe"}), 404
    if r.status != "pending":
        return jsonify({"ok": False, "error": "Ya procesada"}), 400
    if status not in ("approved", "rejected"):
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    if status == "approved":
        su = SpecialUser.query.get(r.affiliate_id)
        if not su:
            return jsonify({"ok": False, "error": "Afiliado no existe"}), 400
        bal = float(su.balance or 0.0)
        if float(r.amount_usd or 0.0) > bal:
            return jsonify({"ok": False, "error": "Fondos insuficientes"}), 400
        su.balance = round(bal - float(r.amount_usd or 0.0), 2)
        r.status = "approved"
        r.processed_at = datetime.utcnow()
        db.session.commit()
        # Notify affiliate: withdrawal approved
        try:
            if su and (su.email or ""):
                lines = [
                    "Tu retiro ha sido aprobado",
                    f"Solicitud #{r.id}",
                    f"Monto: ${float(r.amount_usd or 0.0):.2f}",
                    f"Método: {r.method.upper()}",
                ]
                if r.method == 'pm':
                    lines.append(f"Pago Móvil: {r.pm_bank} · {r.pm_name} · {r.pm_phone} · {r.pm_id}")
                elif r.method == 'binance':
                    lines.append(f"Binance: {r.binance_email} · {r.binance_phone}")
                elif r.method == 'zinli':
                    lines.append(f"Zinli: {r.zinli_email} · {r.zinli_tag}")
                send_email(su.email, f"Retiro #{r.id} aprobado", "\n".join(lines))
        except Exception:
            pass
        return jsonify({"ok": True, "balance": su.balance})
    else:
        r.status = "rejected"
        r.processed_at = datetime.utcnow()
        db.session.commit()
        # Notify affiliate: withdrawal rejected
        try:
            su = SpecialUser.query.get(r.affiliate_id)
            if su and (su.email or ""):
                lines = [
                    "Tu retiro ha sido rechazado",
                    f"Solicitud #{r.id}",
                    f"Monto: ${float(r.amount_usd or 0.0):.2f}",
                ]
                send_email(su.email, f"Retiro #{r.id} rechazado", "\n".join(lines))
        except Exception:
            pass
        return jsonify({"ok": True})

@app.route("/admin/special/users/<int:uid>", methods=["DELETE"])
def admin_special_users_delete(uid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    su = SpecialUser.query.get(uid)
    if not su:
        return jsonify({"ok": False, "error": "No existe"}), 404
    db.session.delete(su)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/store/special/validate")
def store_special_validate():
    code = (request.args.get("code") or '').strip()
    gid_raw = request.args.get("gid")
    try:
        gid = int(gid_raw) if gid_raw is not None and f"{gid_raw}" != '' else None
    except Exception:
        gid = None
    if not code:
        return jsonify({"ok": False, "error": "Código vacío"}), 400
    su = SpecialUser.query.filter(db.func.lower(SpecialUser.code) == code.lower(), SpecialUser.active == True).first()
    if not su:
        return jsonify({"ok": False, "error": "Código inválido"}), 404
    # Enforce scope if restricted to a package
    if (su.scope or 'all') == 'package':
        if not gid or (su.scope_package_id and su.scope_package_id != gid):
            return jsonify({"ok": False, "error": "El código no aplica a este juego"}), 400
    # Determine category-based discount. For mobile, build per-item tiered discounts (low price -> higher %).
    disc = float(su.discount_percent or 0.0)
    item_discounts = []  # [{item_id, discount (fraction)}]
    try:
        if gid:
            pkg = StorePackage.query.get(gid)
            cat = (pkg.category or '').lower() if pkg else ''
            if cat == 'gift':
                # gift uses gift category percent if provided; no tiering
                if float(su.discount_gift_percent or 0.0) > 0:
                    disc = float(su.discount_gift_percent or 0.0)
            elif cat == 'mobile':
                # Tiered per-item discount for mobile
                # Define top/bottom percent (can be made configurable later)
                max_pct = 10.0  # cheapest items
                min_pct = 4.0   # most expensive items
                try:
                    # If affiliate set a mobile discount explicitly, use it as max, but clamp within [min_pct, 100]
                    mset = float(su.discount_mobile_percent or 0.0)
                    if mset > 0:
                        max_pct = max(min(mset, 100.0), min_pct)
                except Exception:
                    pass
                # Fetch items and sort by price asc
                items = (
                    GamePackageItem.query
                    .filter_by(store_package_id=gid, active=True)
                    .order_by(GamePackageItem.price.asc())
                    .all()
                )
                n = len(items)
                if n >= 1:
                    if n == 1:
                        # Single item: apply max_pct
                        item_discounts = [{"item_id": items[0].id, "discount": round(max_pct/100.0, 4)}]
                        disc = max_pct
                    else:
                        # Linear interpolation from max_pct (idx 0) down to min_pct (idx n-1)
                        step = (max_pct - min_pct) / (n - 1)
                        item_discounts = []
                        for idx, it in enumerate(items):
                            pct = max_pct - step * idx
                            pct = max(min_pct, min(max_pct, pct))
                            item_discounts.append({"item_id": it.id, "discount": round(pct/100.0, 4)})
                        # Fallback/general display percent: use the first item percent
                        disc = max_pct
    except Exception:
        pass
    resp = {"ok": True, "allowed": True, "discount": round(disc/100.0, 4)}
    if item_discounts:
        resp["item_discounts"] = item_discounts
    return jsonify(resp)

# Routes
@app.route("/")
def index():
    """Public storefront index page with header and configurable logo."""
    logo_url = get_config_value("logo_path", "")
    banner_url = get_config_value("mid_banner_path", "")
    return render_template("index.html", logo_url=logo_url, banner_url=banner_url)

@app.route("/terms")
def terms_page():
    return render_template("terms.html")

@app.route("/user")
def user_page():
    u = session.get("user") or {}
    role = u.get("role")
    is_admin = (role == "admin")
    is_affiliate = (role == "affiliate")
    logo_url = get_config_value("logo_path", "")
    return render_template("user.html", is_admin=is_admin, is_affiliate=is_affiliate, logo_url=logo_url)

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/store/hero")
def store_hero():
    return jsonify({
        "images": [
            get_config_value("hero_1", ""),
            get_config_value("hero_2", ""),
            get_config_value("hero_3", ""),
        ]
    })


@app.route("/store/rate")
def store_rate():
    """Public endpoint: returns the configured exchange rate (BsD per 1 USD)."""
    try:
        rate_str = get_config_value("exchange_rate_bsd_per_usd", "")
        rate = float(rate_str) if rate_str else 0.0
    except Exception:
        rate = 0.0
    resp = jsonify({"rate_bsd_per_usd": rate})
    # Avoid browser/proxy caching so updates from Admin reflect immediately
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/store/payments")
def store_payments():
    """Public: payment method configuration used by details page."""
    data = {
        "pm_bank": get_config_value("pm_bank", ""),
        "pm_name": get_config_value("pm_name", ""),
        "pm_phone": get_config_value("pm_phone", ""),
        "pm_id": get_config_value("pm_id", ""),
        "binance_email": get_config_value("binance_email", ""),
        "binance_phone": get_config_value("binance_phone", ""),
        "pm_image_path": get_config_value("pm_image_path", ""),
        "binance_image_path": get_config_value("binance_image_path", ""),
    }
    return jsonify({"ok": True, "payments": data})


 

# ==============================
# Admin: Config APIs
# ==============================
@app.route("/admin/config/logo", methods=["GET"])
def admin_config_logo_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "logo_path": get_config_value("logo_path", "")})


@app.route("/admin/config/logo", methods=["POST"])
def admin_config_logo_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    set_config_value("logo_path", (data.get("logo_path") or "").strip())
    return jsonify({"ok": True})


@app.route("/admin/config/mid_banner", methods=["GET"])
def admin_config_mid_banner_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "mid_banner_path": get_config_value("mid_banner_path", "")})


@app.route("/admin/config/mid_banner", methods=["POST"])
def admin_config_mid_banner_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    set_config_value("mid_banner_path", (data.get("mid_banner_path") or "").strip())
    return jsonify({"ok": True})


@app.route("/admin/config/rate", methods=["GET"])
def admin_config_rate_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "rate_bsd_per_usd": get_config_value("exchange_rate_bsd_per_usd", "")})


@app.route("/admin/config/rate", methods=["POST"])
def admin_config_rate_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    set_config_value("exchange_rate_bsd_per_usd", (data.get("rate_bsd_per_usd") or "").strip())
    return jsonify({"ok": True})


@app.route("/admin/config/payments", methods=["GET"])
def admin_config_payments_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({
        "ok": True,
        "pm_bank": get_config_value("pm_bank", ""),
        "pm_name": get_config_value("pm_name", ""),
        "pm_phone": get_config_value("pm_phone", ""),
        "pm_id": get_config_value("pm_id", ""),
        "binance_email": get_config_value("binance_email", ""),
        "binance_phone": get_config_value("binance_phone", ""),
        "pm_image_path": get_config_value("pm_image_path", ""),
        "binance_image_path": get_config_value("binance_image_path", ""),
    })


@app.route("/admin/config/payments", methods=["POST"])
def admin_config_payments_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    set_config_value("pm_bank", (data.get("pm_bank") or "").strip())
    set_config_value("pm_name", (data.get("pm_name") or "").strip())
    set_config_value("pm_phone", (data.get("pm_phone") or "").strip())
    set_config_value("pm_id", (data.get("pm_id") or "").strip())
    set_config_value("binance_email", (data.get("binance_email") or "").strip())
    set_config_value("binance_phone", (data.get("binance_phone") or "").strip())
    set_config_value("pm_image_path", (data.get("pm_image_path") or "").strip())
    set_config_value("binance_image_path", (data.get("binance_image_path") or "").strip())
    return jsonify({"ok": True})


@app.route("/admin/config/mail", methods=["GET"])
def admin_config_mail_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({
        "ok": True,
        "mail_user": MAIL_USER,
        "admin_notify_email": get_config_value("admin_notify_email", ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL)
    })


@app.route("/admin/config/mail", methods=["POST"])
def admin_config_mail_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    email = (data.get("admin_notify_email") or "").strip()
    if not email:
        return jsonify({"ok": False, "error": "Email requerido"}), 400
    set_config_value("admin_notify_email", email)
    return jsonify({"ok": True, "admin_notify_email": email})


@app.route("/admin/config/mail/test", methods=["POST"])
def admin_config_mail_test():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    to = (data.get("to") or "").strip()
    subject = (data.get("subject") or "").strip() or "Prueba de correo"
    body = (data.get("body") or "").strip() or "Mensaje de prueba"
    if not to:
        return jsonify({"ok": False, "error": "Destino requerido"}), 400
    send_email_async(to, subject, body)
    return jsonify({"ok": True, "to": to})


@app.route("/admin/config/hero", methods=["GET"])
def admin_config_hero_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({
        "ok": True,
        "hero_1": get_config_value("hero_1", ""),
        "hero_2": get_config_value("hero_2", ""),
        "hero_3": get_config_value("hero_3", ""),
    })


@app.route("/admin/config/hero", methods=["POST"])
def admin_config_hero_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    set_config_value("hero_1", (data.get("hero_1") or "").strip())
    set_config_value("hero_2", (data.get("hero_2") or "").strip())
    set_config_value("hero_3", (data.get("hero_3") or "").strip())
    return jsonify({"ok": True})


# ==============================
# Admin: Images APIs
# ==============================
@app.route("/admin/config/active_login_game", methods=["GET"])
def admin_config_active_login_game_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "active_login_game_id": get_config_value("active_login_game_id", "")})


@app.route("/admin/config/active_login_game", methods=["POST"])
def admin_config_active_login_game_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    val = (data.get("active_login_game_id") or "").strip()
    # allow empty to disable
    set_config_value("active_login_game_id", val)
    return jsonify({"ok": True, "active_login_game_id": val})
def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/admin/images/list", methods=["GET"])
def admin_images_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    items = ImageAsset.query.order_by(ImageAsset.uploaded_at.desc()).all()
    return jsonify([
        {"id": x.id, "title": x.title, "path": x.path, "alt_text": x.alt_text}
        for x in items
    ])


@app.route("/admin/images/upload", methods=["POST"])
def admin_images_upload():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "Archivo requerido"}), 400
    if not _allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Extensión no permitida"}), 400
    fname = secure_filename(file.filename)
    # Avoid collisions
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    base, ext = os.path.splitext(fname)
    fname = f"{base}_{ts}{ext}"
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    except Exception:
        pass
    fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
    file.save(fpath)
    public_path = f"{app.config['UPLOAD_URL_PREFIX'].rstrip('/')}/{fname}"
    img = ImageAsset(title=fname, path=public_path, alt_text="")
    db.session.add(img)
    db.session.commit()
    return jsonify({"ok": True, "image": {"id": img.id, "title": img.title, "path": img.path}})


def _delete_image_record_and_file(img: ImageAsset) -> None:
    # Try removing file if it lives under UPLOAD_FOLDER
    try:
        # If path is a URL prefix, map to file path by basename
        name = os.path.basename(img.path or "")
        if name:
            fpath = os.path.join(app.config["UPLOAD_FOLDER"], name)
            if os.path.isfile(fpath):
                os.remove(fpath)
    except Exception:
        pass
    try:
        db.session.delete(img)
        db.session.commit()
    except Exception:
        db.session.rollback()


@app.route("/admin/images/<int:img_id>", methods=["DELETE"])
def admin_images_delete(img_id: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    img = ImageAsset.query.get(img_id)
    if not img:
        return jsonify({"ok": False, "error": "No existe"}), 404
    _delete_image_record_and_file(img)
    return jsonify({"ok": True})


@app.route("/admin/images/<int:img_id>/delete", methods=["POST"])
def admin_images_delete_post(img_id: int):
    # Fallback for environments that block DELETE
    return admin_images_delete(img_id)


@app.route("/admin/images/delete_by_path", methods=["POST"])
def admin_images_delete_by_path():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    p = (data.get("path") or "").strip()
    if not p:
        return jsonify({"ok": False, "error": "Ruta requerida"}), 400
    img = ImageAsset.query.filter_by(path=p).first()
    if not img:
        return jsonify({"ok": False, "error": "No existe"}), 404
    _delete_image_record_and_file(img)
    return jsonify({"ok": True})


@app.route("/store/packages")
def store_packages():
    category = (request.args.get("category") or '').strip().lower()
    q = StorePackage.query.filter_by(active=True)
    # Accept common aliases
    if category:
        cat = category
        mobile_aliases = {"mobile", "movil", "móvil", "juegos", "games", "game"}
        gift_aliases = {"gift", "gif", "gifts", "giftcard", "giftcards", "card", "cards"}
        if cat in mobile_aliases:
            q = q.filter(StorePackage.category.in_(["mobile", "movil", "juegos"]))
        elif cat in gift_aliases:
            q = q.filter(StorePackage.category.in_(["gift", "gif", "giftcards"]))
    try:
        items = q.order_by(StorePackage.sort_order.asc(), StorePackage.created_at.desc()).all()
    except Exception:
        items = q.order_by(StorePackage.created_at.desc()).all()
    return jsonify({
        "packages": [
            {"id": p.id, "name": p.name, "image_path": p.image_path, "category": (p.category or 'mobile')}
            for p in items
        ]
    })


@app.route("/store/best_sellers")
def store_best_sellers():
    """Public: Top packages por ventas (pedidos aprobados).
    Retorna hasta 12 paquetes ordenados por cantidad de órdenes aprobadas desc.
    """
    # Aggregate count of approved orders by package id
    agg = (
        db.session.query(Order.store_package_id, db.func.count(Order.id).label("cnt"))
        .filter(Order.status == "approved")
        .group_by(Order.store_package_id)
        .order_by(db.text("cnt DESC"))
        .limit(12)
        .all()
    )
    ids = [row[0] for row in agg if row[0] is not None]
    if not ids:
        # No approved sales yet -> return empty list (do not show latest)
        return jsonify({"packages": []})
    # fetch package rows keeping order by counts
    rows = StorePackage.query.filter(StorePackage.id.in_(ids), StorePackage.active == True).all()
    by_id = {p.id: p for p in rows}
    ordered = [by_id[i] for i in ids if i in by_id]
    return jsonify({
        "packages": [
            {"id": p.id, "name": p.name, "image_path": p.image_path, "category": (p.category or 'mobile')}
            for p in ordered
        ]
    })

@app.route("/store/package/<int:gid>")
def store_game_detail(gid: int):
    """Detalles de un juego/paquete de la tienda."""
    game = StorePackage.query.get(gid)
    if not game or not game.active:
        return redirect(url_for("index"))
    logo_url = get_config_value("logo_path", "")
    active_login_game_id = get_config_value("active_login_game_id", "")
    player_lookup_region = get_config_value("player_lookup_default_region", "US")
    player_lookup_regions = get_config_value("player_lookup_regions_default", "US,BR,ME,PK,CIS,ID,LATAM,MX")
    scrape_enabled = (os.environ.get("SCRAPE_ENABLED", "true").strip().lower() == "true")
    # Related packages by same category
    try:
        rel_q = StorePackage.query.filter(
            StorePackage.active == True,
            StorePackage.category == (game.category or 'mobile'),
            StorePackage.id != game.id,
        )
        try:
            rel_q = rel_q.order_by(StorePackage.sort_order.asc(), StorePackage.created_at.desc())
        except Exception:
            rel_q = rel_q.order_by(StorePackage.created_at.desc())
        related = rel_q.limit(5).all()
    except Exception:
        related = []
    return render_template(
        "details.html",
        game=game,
        logo_url=logo_url,
        active_login_game_id=active_login_game_id,
        player_lookup_region=player_lookup_region,
        player_lookup_regions=player_lookup_regions,
        scrape_enabled=scrape_enabled,
        related_packages=[{"id": p.id, "name": p.name, "image_path": p.image_path, "category": (p.category or 'mobile')} for p in related],
    )


@app.route("/checkout/<int:gid>")
def store_checkout(gid: int):
    """Standalone checkout page optimized for mobile."""
    game = StorePackage.query.get(gid)
    if not game or not game.active:
        return redirect(url_for("index"))
    logo_url = get_config_value("logo_path", "")
    return render_template("checkout.html", gid=gid, logo_url=logo_url)


# ===============
# Orders API
# ===============

@app.route("/orders", methods=["POST"])
def create_order():
    try:
        data = request.get_json(silent=True) or {}
        gid_raw = data.get("store_package_id")
        if gid_raw is None:
            return jsonify({"ok": False, "error": "store_package_id requerido"}), 400
        gid = int(gid_raw)
        item_id = data.get("item_id")
        if item_id is not None:
            try:
                item_id = int(item_id)
            except Exception:
                item_id = None
        method = (data.get("method") or "").strip()
        currency = (data.get("currency") or "USD").strip()
        try:
            amount = float(data.get("amount") or 0)
        except Exception:
            amount = 0.0
        reference = (data.get("reference") or "").strip()
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        phone = (data.get("phone") or "").strip()
        customer_id = (data.get("customer_id") or "").strip()
        customer_zone = (data.get("customer_zone") or "").strip()
        special_code = (data.get("special_code") or "").strip()

        if not reference:
            return jsonify({"ok": False, "error": "Referencia requerida"}), 400
        if amount <= 0:
            return jsonify({"ok": False, "error": "Monto inválido"}), 400
        if method not in ("pm", "binance"):
            return jsonify({"ok": False, "error": "Método inválido"}), 400
        if not phone:
            return jsonify({"ok": False, "error": "Teléfono requerido"}), 400

        o = Order(
            store_package_id=gid,
            item_id=item_id,
            method=method,
            currency=currency,
            amount=amount,
            reference=reference,
            name=name,
            email=email,
            phone=phone,
            customer_id=customer_id,
            customer_zone=customer_zone,
            customer_name=name or email or customer_id,
            status="pending",
            special_code=special_code,
        )
        # If client sent multiple items, store them in items_json
        try:
            raw_items = data.get("items")
            items_list = []
            if isinstance(raw_items, list) and raw_items:
                for it_entry in raw_items:
                    try:
                        iid = int(it_entry.get("item_id"))
                    except Exception:
                        continue
                    qty = int(it_entry.get("qty") or 1)
                    if qty <= 0:
                        qty = 1
                    gi = GamePackageItem.query.get(iid)
                    if not gi:
                        continue
                    items_list.append({
                        "item_id": gi.id,
                        "qty": qty,
                        "title": gi.title,
                        "price": float(gi.price or 0.0),
                    })
            if items_list:
                o.items_json = json.dumps(items_list)
        except Exception:
            pass
        # Try to resolve special user id now for convenience
        try:
            if special_code:
                su = SpecialUser.query.filter(db.func.lower(SpecialUser.code) == special_code.lower(), SpecialUser.active == True).first()
                if su:
                    o.special_user_id = su.id
        except Exception:
            pass
        db.session.add(o)
        db.session.commit()
        # Notify admin by email about new pending order
        try:
            # Destination: AppConfig override > ENV > ADMIN_EMAIL
            to_addr = get_config_value("admin_notify_email", ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL)
            pkg = StorePackage.query.get(o.store_package_id)
            it = GamePackageItem.query.get(o.item_id) if o.item_id else None
            lines = [
                f"Nueva orden #{o.id} creada",
                f"Estado: {o.status}",
                f"Juego: {(pkg.name if pkg else o.store_package_id)}",
                f"Método: {o.method}  Moneda: {o.currency}",
                f"Monto: {o.amount}",
                f"Referencia: {o.reference}",
                f"Cliente: {o.name or o.email or o.customer_id}",
                f"Código especial: {o.special_code or '-'}",
                f"Fecha: {o.created_at.isoformat()}",
            ]
            # Breakdown for multiple items, if present
            try:
                if (o.items_json or '').strip():
                    items = json.loads(o.items_json or '[]')
                    if isinstance(items, list) and items:
                        lines.append("Paquetes:")
                        for ent in items:
                            t = ent.get("title")
                            q = ent.get("qty")
                            p = ent.get("price")
                            try:
                                p = float(p or 0.0)
                            except Exception:
                                p = 0.0
                            lines.append(f" - {q} x {t} (${p:.2f} c/u)")
                        try:
                            subtotal = sum(float((x.get('price') or 0.0)) * int(x.get('qty') or 1) for x in items)
                            lines.append(f"Subtotal USD: ${subtotal:.2f}")
                        except Exception:
                            pass
                else:
                    # Single item fallback
                    lines.insert(3, f"Paquete: {(it.title if it else 'N/A')}")
                # Quantity line (gift: cards, others: recharges)
                try:
                    qty_total = 1
                    if (o.items_json or '').strip():
                        items = json.loads(o.items_json or '[]')
                        if isinstance(items, list) and items:
                            qty_total = sum(int(x.get('qty') or 1) for x in items)
                    is_gift = (pkg.category or '').lower() == 'gift' if pkg else False
                    qty_label = 'Cantidad de tarjetas' if is_gift else 'Recargas totales'
                    lines.append(f"{qty_label}: {qty_total}")
                except Exception:
                    pass
            except Exception:
                pass
            # If affiliate code is present, include before/after discount prices
            try:
                disc_pct = 0.0
                su = None
                if o.special_user_id:
                    su = SpecialUser.query.get(o.special_user_id)
                if (not su) and (o.special_code or ''):
                    su = SpecialUser.query.filter(db.func.lower(SpecialUser.code) == (o.special_code or '').lower(), SpecialUser.active == True).first()
                # Category-based discount
                if su and su.active:
                    try:
                        disc_pct = float(su.discount_percent or 0.0)
                        if pkg and (pkg.category or '').lower() == 'gift' and float(su.discount_gift_percent or 0.0) > 0:
                            disc_pct = float(su.discount_gift_percent or 0.0)
                        elif pkg and (pkg.category or '').lower() == 'mobile' and float(su.discount_mobile_percent or 0.0) > 0:
                            disc_pct = float(su.discount_mobile_percent or 0.0)
                    except Exception:
                        disc_pct = 0.0
                base_usd = float((it.price if it else 0.0) or 0.0)
                if disc_pct > 0 and base_usd > 0:
                    after_usd = round(base_usd * (1.0 - disc_pct / 100.0), 2)
                    if (o.currency or 'USD').upper() == 'USD':
                        before_disp = f"${base_usd:.2f}"
                        after_disp = f"${after_usd:.2f}"
                    else:
                        # Convert to local currency using configured rate
                        try:
                            rate = float(get_config_value("exchange_rate_bsd_per_usd", "0") or 0)
                        except Exception:
                            rate = 0.0
                        before_loc = round(base_usd * (rate if rate > 0 else 0.0), 2)
                        after_loc = round(after_usd * (rate if rate > 0 else 0.0), 2)
                        before_disp = f"{before_loc} {o.currency}"
                        after_disp = f"{after_loc} {o.currency}"
                    lines.append(f"Precio antes del descuento: {before_disp}")
                    lines.append(f"Precio con descuento: {after_disp}")
                    lines.append(f"Descuento aplicado: {disc_pct:.0f}%")
            except Exception:
                pass
            send_email(to_addr, f"Nueva orden #{o.id} pendiente", "\n".join(lines))
        except Exception:
            pass
        # Purge per-user beyond latest 30 (by email or customer_id)
        try:
            uq = Order.query
            if email:
                uq = uq.filter(Order.email == email)
            if customer_id:
                uq = uq.filter(Order.customer_id == customer_id)
            ids = [r.id for r in uq.order_by(Order.created_at.desc()).limit(30).all()]
            if ids:
                del_q = uq.filter(~Order.id.in_(ids))
                del_q.delete(synchronize_session=False)
                db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"ok": True, "order_id": o.id})
    except Exception as e:
        # Return error to client to help diagnose instead of 500
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": f"Server error: {str(e)}"}), 500


@app.route("/admin/orders", methods=["GET"])
def admin_orders_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    orders = Order.query.order_by(Order.created_at.desc()).all()
    out = []
    for x in orders:
        pkg = StorePackage.query.get(x.store_package_id)
        it = GamePackageItem.query.get(x.item_id) if x.item_id else None
        # Parse items_json if available
        items_payload = []
        try:
            if (x.items_json or '').strip():
                parsed = json.loads(x.items_json or '[]')
                if isinstance(parsed, list):
                    items_payload = parsed
        except Exception:
            items_payload = []
        # Parse multiple delivery codes if available
        delivery_codes = []
        try:
            if (x.delivery_codes_json or '').strip():
                dc_parsed = json.loads(x.delivery_codes_json or '[]')
                if isinstance(dc_parsed, list):
                    delivery_codes = [str(c or '').strip() for c in dc_parsed if str(c or '').strip()]
        except Exception:
            delivery_codes = []
        out.append({
            "id": x.id,
            "created_at": x.created_at.isoformat(),
            "status": x.status,
            "store_package_id": x.store_package_id,
            "package_name": pkg.name if pkg else "",
            "package_category": (pkg.category if pkg and pkg.category else "mobile"),
            "item_id": x.item_id,
            "item_title": it.title if it else "",
            "item_price_usd": (it.price if it else 0.0),
            "items": items_payload,
            "customer_id": x.customer_id,
            "customer_zone": x.customer_zone or "",
            "name": x.name,
            "email": x.email,
            "phone": x.phone,
            "method": x.method,
            "currency": x.currency,
            "amount": x.amount,
            "reference": x.reference,
            "delivery_code": x.delivery_code or "",
            "delivery_codes": delivery_codes,
        })
    return jsonify({"ok": True, "orders": out})


@app.route("/orders/my", methods=["GET"])
def orders_my():
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    q = Order.query
    role = user.get("role")
    if role == "admin":
        email = (request.args.get("email") or "").strip()
        customer_id = (request.args.get("customer_id") or "").strip()
        if email:
            q = q.filter(Order.email == email)
        if customer_id:
            q = q.filter(Order.customer_id == customer_id)
        q = q.order_by(Order.created_at.desc()).limit(50)
    elif role == "user":
        email = (user.get("email") or "").strip()
        if not email:
            return jsonify({"ok": True, "orders": []})
        q = q.filter(Order.email == email).order_by(Order.created_at.desc()).limit(50)
    else:
        # Affiliates or other roles: do not expose buyer orders
        return jsonify({"ok": True, "orders": []})
    rows = q.all()
    out = []
    for x in rows:
        pkg = StorePackage.query.get(x.store_package_id)
        it = GamePackageItem.query.get(x.item_id) if x.item_id else None
        # Parse items_json if available
        items_payload = []
        try:
            if (x.items_json or '').strip():
                parsed = json.loads(x.items_json or '[]')
                if isinstance(parsed, list):
                    items_payload = parsed
        except Exception:
            items_payload = []
        out.append({
            "id": x.id,
            "created_at": (x.created_at.isoformat() if hasattr(x.created_at, 'isoformat') else str(x.created_at)),
            "status": x.status,
            "store_package_id": x.store_package_id,
            "package_name": pkg.name if pkg else "",
            "package_category": (pkg.category if pkg and pkg.category else "mobile"),
            "item_id": x.item_id,
            "item_title": it.title if it else "",
            "item_price_usd": (it.price if it else 0.0),
            "items": items_payload,
            "customer_id": x.customer_id,
            "customer_zone": x.customer_zone or "",
            "name": x.name,
            "email": x.email,
            "phone": x.phone,
            "method": x.method,
            "currency": x.currency,
            "amount": x.amount,
            "reference": x.reference,
            "delivery_code": x.delivery_code or "",
        })
    return jsonify({"ok": True, "orders": out})

@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
def admin_orders_set_status(oid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("approved", "rejected"):
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404
    # Optional: allow passing single or multiple gift codes when approving gift card orders
    code = (data.get("delivery_code") or "").strip()
    if code:
        o.delivery_code = code
    # Multiple codes support
    try:
        codes = data.get("delivery_codes")
        if isinstance(codes, list):
            clean = [str(c or '').strip() for c in codes]
            clean = [c for c in clean if c]
            if clean:
                o.delivery_codes_json = json.dumps(clean)
                # keep first for legacy compatibility
                o.delivery_code = o.delivery_code or clean[0]
    except Exception:
        pass
    prev_status = (o.status or '').lower()
    o.status = status
    db.session.commit()
    # Affiliate commission crediting
    try:
        if status == "approved" and prev_status != "approved":
            su = None
            if o.special_user_id:
                su = SpecialUser.query.get(o.special_user_id)
            if (not su) and (o.special_code or ''):
                su = SpecialUser.query.filter(
                    db.func.lower(SpecialUser.code) == (o.special_code or '').lower(),
                    SpecialUser.active == True
                ).first()
            if su and su.active:
                # Respect affiliate scope
                scope_ok = True
                sc = (su.scope or 'all')
                if sc == 'package':
                    try:
                        scope_ok = (su.scope_package_id == o.store_package_id)
                    except Exception:
                        scope_ok = False
                if scope_ok:
                    # Determine commission base (USD)
                    subtotal = 0.0
                    try:
                        if (o.items_json or '').strip():
                            items = json.loads(o.items_json or '[]')
                            if isinstance(items, list) and items:
                                for ent in items:
                                    q = int(ent.get('qty') or 1)
                                    try:
                                        p = float(ent.get('price') or 0.0)
                                    except Exception:
                                        p = 0.0
                                    subtotal += (p * q)
                    except Exception:
                        pass
                    if subtotal <= 0 and o.item_id:
                        try:
                            gi = GamePackageItem.query.get(o.item_id)
                            if gi:
                                subtotal = float(gi.price or 0.0)
                        except Exception:
                            pass
                    if subtotal <= 0:
                        try:
                            amt_usd = float(o.amount or 0.0)
                            cur = (o.currency or 'USD').upper()
                            if cur != 'USD':
                                try:
                                    rate = float(get_config_value("exchange_rate_bsd_per_usd", "0") or 0)
                                except Exception:
                                    rate = 0.0
                                if rate > 0:
                                    amt_usd = round(amt_usd / rate, 2)
                            subtotal = amt_usd
                        except Exception:
                            subtotal = 0.0
                    # Commission percent by category
                    comm_pct = 0.0
                    try:
                        pkg = StorePackage.query.get(o.store_package_id)
                        comm_pct = float(su.commission_percent or 0.0)
                        if pkg and (pkg.category or '').lower() == 'gift' and float(su.commission_gift_percent or 0.0) > 0:
                            comm_pct = float(su.commission_gift_percent or 0.0)
                        elif pkg and (pkg.category or '').lower() == 'mobile' and float(su.commission_mobile_percent or 0.0) > 0:
                            comm_pct = float(su.commission_mobile_percent or 0.0)
                    except Exception:
                        pass
                    if comm_pct > 0 and subtotal > 0:
                        try:
                            inc = round(subtotal * (comm_pct / 100.0), 2)
                            su.balance = round(float(su.balance or 0.0) + inc, 2)
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
    except Exception:
        pass
    # Notify buyer on approval (HTML email)
    try:
        if status == "approved" and (o.email or o.name):
            pkg = StorePackage.query.get(o.store_package_id)
            it = GamePackageItem.query.get(o.item_id) if o.item_id else None
            to_addr = o.email or None
            if to_addr:
                html, text = build_order_approved_email(o, pkg, it)
                # use HTML email; if async fails, ignore
                try:
                    send_email_html(to_addr, f"Orden #{o.id} aprobada – Inefable Store", html, text)
                except Exception:
                    send_email_async(to_addr, f"Orden #{o.id} aprobada – Inefable Store", text)
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/store/package/<int:gid>/items")
def store_game_items(gid: int):
    game = StorePackage.query.get(gid)
    if not game or not game.active:
        return jsonify({"ok": False, "error": "No existe"}), 404
    items = (
        GamePackageItem.query
        .filter_by(store_package_id=gid, active=True)
        .order_by(GamePackageItem.created_at.asc())
        .all()
    )
    return jsonify({
        "ok": True,
        "items": [
            {"id": it.id, "title": it.title, "price": it.price, "sticker": (it.sticker or ""), "icon_path": (it.icon_path or "")}
            for it in items
        ]
    })

@app.route("/admin/package/<int:gid>/items", methods=["GET"])
def admin_game_items_list(gid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    game = StorePackage.query.get(gid)
    if not game:
        return jsonify({"ok": False, "error": "Juego no existe"}), 404
    items = GamePackageItem.query.filter_by(store_package_id=gid).order_by(GamePackageItem.created_at.asc()).all()
    return jsonify({
        "ok": True,
        "items": [
            {"id": it.id, "title": it.title, "price": it.price, "description": it.description, "sticker": (it.sticker or ""), "icon_path": (it.icon_path or ""), "active": it.active}
            for it in items
        ]
    })

@app.route("/admin/package/<int:gid>/items", methods=["POST"])
def admin_game_items_create(gid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    game = StorePackage.query.get(gid)
    if not game:
        return jsonify({"ok": False, "error": "Juego no existe"}), 404
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    sticker = (data.get("sticker") or "").strip()
    icon_path = (data.get("icon_path") or "").strip()
    try:
        price = float(data.get("price") or 0)
    except Exception:
        price = 0.0
    if not title:
        return jsonify({"ok": False, "error": "Título requerido"}), 400
    item = GamePackageItem(store_package_id=gid, title=title, description=description, price=price, sticker=sticker, icon_path=icon_path, active=True)
    db.session.add(item)
    db.session.commit()
    return jsonify({"ok": True, "item": {"id": item.id, "title": item.title, "price": item.price, "description": item.description, "sticker": (item.sticker or ""), "icon_path": (item.icon_path or ""), "active": item.active}})

@app.route("/admin/package/item/<int:item_id>", methods=["PUT", "PATCH"])
def admin_game_items_update(item_id: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    item = GamePackageItem.query.get(item_id)
    if not item:
        return jsonify({"ok": False, "error": "No existe"}), 404
    data = request.get_json(silent=True) or {}
    if "title" in data:
        item.title = (data.get("title") or "").strip()
    if "description" in data:
        item.description = (data.get("description") or "").strip()
    if "sticker" in data:
        item.sticker = (data.get("sticker") or "").strip()
    if "icon_path" in data:
        item.icon_path = (data.get("icon_path") or "").strip()
    if "price" in data:
        try:
            item.price = float(data.get("price") or 0)
        except Exception:
            item.price = 0.0
    if "active" in data:
        item.active = bool(data.get("active"))
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/admin/package/item/<int:item_id>", methods=["DELETE"])
def admin_game_items_delete(item_id: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    item = GamePackageItem.query.get(item_id)
    if not item:
        return jsonify({"ok": False, "error": "No existe"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/packages/reorder", methods=["POST"])
def admin_packages_reorder():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "Lista vacía"}), 400
    try:
        # Assign sort_order by position
        pos = 0
        for pid in ids:
            try:
                pid_int = int(pid)
            except Exception:
                continue
            item = StorePackage.query.get(pid_int)
            if not item:
                continue
            item.sort_order = pos
            pos += 1
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": f"Error: {str(e)}"}), 500


@app.route("/admin/packages/<int:pid>", methods=["PUT", "PATCH"])
def admin_packages_update(pid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    item = StorePackage.query.get(pid)
    if not item:
        return jsonify({"ok": False, "error": "No existe"}), 404
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    image_path = data.get("image_path")
    category = data.get("category")
    description = data.get("description")
    requires_zone_id = data.get("requires_zone_id")
    active = data.get("active")
    if name is not None:
        item.name = (name or '').strip()
    if image_path is not None:
        item.image_path = (image_path or '').strip()
    if category is not None:
        c = (category or 'mobile').strip().lower()
        if c not in ("mobile", "gift"):
            c = "mobile"
        item.category = c
    if description is not None:
        item.description = (description or '').strip()
    if requires_zone_id is not None:
        item.requires_zone_id = bool(requires_zone_id)
    if active is not None:
        item.active = bool(active)
    db.session.commit()
    return jsonify({
        "ok": True,
        "package": {
            "id": item.id,
            "name": item.name,
            "image_path": item.image_path,
            "active": item.active,
            "category": item.category,
            "requires_zone_id": bool(item.requires_zone_id)
        }
    })


# Admin packages management
@app.route("/admin/packages", methods=["GET"])
def admin_packages_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    try:
        items = StorePackage.query.order_by(StorePackage.sort_order.asc(), StorePackage.created_at.desc()).all()
    except Exception:
        items = StorePackage.query.order_by(StorePackage.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "packages": [
            {"id": p.id, "name": p.name, "image_path": p.image_path, "active": p.active, "category": (p.category or 'mobile'), "description": (p.description or ''), "requires_zone_id": bool(p.requires_zone_id), "sort_order": int(p.sort_order or 0)}
            for p in items
        ]
    })


@app.route("/admin/packages", methods=["POST"])
def admin_packages_create():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    image_path = (data.get("image_path") or "").strip()
    category = (data.get("category") or "mobile").strip().lower()
    description = (data.get("description") or "").strip()
    requires_zone_id = bool(data.get("requires_zone_id", False))
    if category not in ("mobile", "gift"):
        category = "mobile"
    if not name or not image_path:
        return jsonify({"ok": False, "error": "Nombre e imagen requeridos"}), 400
    item = StorePackage(name=name, image_path=image_path, active=True, category=category, description=description, requires_zone_id=requires_zone_id)
    db.session.add(item)
    db.session.commit()
    return jsonify({"ok": True, "package": {"id": item.id, "name": item.name, "image_path": item.image_path, "active": item.active}})


@app.route("/admin/packages/<int:pid>", methods=["DELETE"])
def admin_packages_delete(pid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    item = StorePackage.query.get(pid)
    if not item:
        return jsonify({"ok": False, "error": "No existe"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


def get_config_value(key: str, default: str = "") -> str:
    row = AppConfig.query.filter_by(key=key).first()
    return row.value if row else default


def set_config_value(key: str, value: str) -> None:
    row = AppConfig.query.filter_by(key=key).first()
    if not row:
        row = AppConfig(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    db.session.commit()


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email y contraseña requeridos"}), 400
    # Admin login (env credentials)
    if email.lower() == (ADMIN_EMAIL or "").lower() and password == (ADMIN_PASSWORD or ""):
        session["user"] = {"email": ADMIN_EMAIL, "role": "admin"}
        return jsonify({"ok": True, "user": session["user"]})
    # Affiliate login
    su = SpecialUser.query.filter(db.func.lower(SpecialUser.email) == email.lower()).first()
    if su and su.password_hash and check_password_hash(su.password_hash, password):
        session["user"] = {"email": su.email or email, "role": "affiliate", "affiliate_id": su.id, "name": su.name}
        return jsonify({"ok": True, "user": session["user"]})
    # Normal user login
    u = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if u and check_password_hash(u.password_hash, password):
        session["user"] = {"email": u.email, "role": "user", "user_id": u.id, "name": u.name}
        return jsonify({"ok": True, "user": session["user"]})
    return jsonify({"ok": False, "error": "Credenciales inválidas"}), 401


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.pop("user", None)
    return jsonify({"ok": True})


@app.route("/auth/session", methods=["GET"])
def auth_session_info():
    u = session.get("user")
    return jsonify({"ok": True, "user": (u or None)})


@app.route("/auth/profile", methods=["GET"])
def auth_profile_get():
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    # Admin profile is kept in AppConfig
    if user.get("role") == "admin":
        name = get_config_value("profile_name", "")
        email = get_config_value("profile_email", user.get("email", ADMIN_EMAIL))
        phone = get_config_value("profile_phone", "")
        return jsonify({"ok": True, "profile": {"name": name, "email": email, "phone": phone}})
    # Affiliate profile comes from SpecialUser
    if user.get("role") == "affiliate":
        su = None
        aff_id = user.get("affiliate_id")
        if aff_id:
            su = SpecialUser.query.get(aff_id)
        if not su:
            return jsonify({"ok": False, "error": "Afiliado no encontrado"}), 404
        return jsonify({"ok": True, "profile": {"name": su.name or "", "email": su.email or "", "phone": ""}})
    # Normal user profile comes from Users table
    u = None
    if user.get("role") == "user":
        uid = user.get("user_id")
        if uid:
            u = User.query.get(uid)
    if not u:
        return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
    return jsonify({"ok": True, "profile": {"name": u.name, "email": u.email, "phone": u.phone}})


@app.route("/auth/profile", methods=["POST"])
def auth_profile_set():
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not email:
        return jsonify({"ok": False, "error": "El email es requerido"}), 400
    if user.get("role") == "admin":
        set_config_value("profile_name", name)
        set_config_value("profile_email", email)
        set_config_value("profile_phone", phone)
        return jsonify({"ok": True})
    # Normal user update
    if user.get("role") == "user":
        uid = user.get("user_id")
        u = User.query.get(uid) if uid else None
        if not u:
            return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
        # Email change: ensure unique
        if email.lower() != (u.email or '').lower():
            exists = User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if exists:
                return jsonify({"ok": False, "error": "Email ya está en uso"}), 400
        u.name = name
        u.email = email
        u.phone = phone
        db.session.commit()
        # refresh session email/name
        session["user"].update({"email": u.email, "name": u.name})
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Rol inválido"}), 400

@app.route("/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email y contraseña requeridos"}), 400
    # Unique email
    exists = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if exists or email.lower() == ADMIN_EMAIL.lower():
        return jsonify({"ok": False, "error": "Este email ya está registrado"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "La contraseña debe tener al menos 6 caracteres"}), 400
    u = User(name=name, email=email, phone=phone, password_hash=generate_password_hash(password))
    db.session.add(u)
    db.session.commit()
    session["user"] = {"email": u.email, "role": "user", "user_id": u.id, "name": u.name}
    return jsonify({"ok": True, "user": session["user"]})


if __name__ == "__main__":
    app.run(debug=True)
