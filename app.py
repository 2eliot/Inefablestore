import os
import shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import smtplib
import socket
import threading
from email.mime.text import MIMEText

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
    # Special referral code support
    special_code = db.Column(db.String(80), default="")
    special_user_id = db.Column(db.Integer, nullable=True)

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

class GamePackageItem(db.Model):
    __tablename__ = "game_packages"
    id = db.Column(db.Integer, primary_key=True)
    store_package_id = db.Column(db.Integer, db.ForeignKey("store_packages.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, default=0.0)
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
            add_order_col('special_code', "special_code TEXT DEFAULT ''")
            add_order_col('special_user_id', "special_user_id INTEGER")
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
             "discount_percent": float(u.discount_percent or 0.0), "scope": u.scope or 'all', "scope_package_id": u.scope_package_id}
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
    su = SpecialUser(name=name, code=code, email=email or None, active=bool(data.get("active", True)), balance=float(data.get("balance") or 0.0),
                     discount_percent=discount_percent, scope=scope if scope in ("all","package") else "all", scope_package_id=scope_package_id)
    if password:
        su.password_hash = generate_password_hash(password)
    db.session.add(su)
    db.session.commit()
    return jsonify({"ok": True, "user": {"id": su.id, "name": su.name, "code": su.code, "email": su.email or "", "balance": su.balance, "active": su.active,
            "discount_percent": su.discount_percent, "scope": su.scope, "scope_package_id": su.scope_package_id }})

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
    disc = float(su.discount_percent or 0.0)
    return jsonify({"ok": True, "allowed": True, "discount": round(disc/100.0, 4)})

# Routes
@app.route("/")
def index():
    """Public storefront index page with header and configurable logo."""
    logo_url = get_config_value("logo_path", "")
    return render_template("index.html", logo_url=logo_url)

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
    return jsonify({"rate_bsd_per_usd": rate})


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
    }
    return jsonify({"ok": True, "payments": data})


@app.route("/store/packages")
def store_packages():
    category = (request.args.get("category") or '').strip().lower()
    q = StorePackage.query.filter_by(active=True)
    if category in ("mobile", "gift"):
        q = q.filter_by(category=category)
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
        # Fallback: latest active packages
        items = StorePackage.query.filter_by(active=True).order_by(StorePackage.created_at.desc()).limit(12).all()
        return jsonify({
            "packages": [
                {"id": p.id, "name": p.name, "image_path": p.image_path, "category": (p.category or 'mobile')}
                for p in items
            ]
        })
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
    # logo for header
    logo_url = get_config_value("logo_path", "")
    return render_template("details.html", game=game, logo_url=logo_url)


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
        special_code = (data.get("special_code") or "").strip()

        if not reference:
            return jsonify({"ok": False, "error": "Referencia requerida"}), 400
        if amount <= 0:
            return jsonify({"ok": False, "error": "Monto inválido"}), 400
        if method not in ("pm", "binance"):
            return jsonify({"ok": False, "error": "Método inválido"}), 400

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
            customer_name=name or email or customer_id,
            status="pending",
            special_code=special_code,
        )
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
                f"Paquete: {(it.title if it else 'N/A')}",
                f"Método: {o.method}  Moneda: {o.currency}",
                f"Monto: {o.amount}",
                f"Referencia: {o.reference}",
                f"Cliente: {o.name or o.email or o.customer_id}",
                f"Código especial: {o.special_code or '-'}",
                f"Fecha: {o.created_at.isoformat()}",
            ]
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
            "customer_id": x.customer_id,
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
    # Optional: allow passing delivery_code when approving gift card orders
    code = (data.get("delivery_code") or "").strip()
    if code:
        o.delivery_code = code
    o.status = status
    db.session.commit()
    # If approved, credit 10% commission to special user balance (in USD)
    try:
        if status == "approved" and (o.special_user_id or o.special_code):
            su = None
            if o.special_user_id:
                su = SpecialUser.query.get(o.special_user_id)
            if not su and o.special_code:
                su = SpecialUser.query.filter(db.func.lower(SpecialUser.code) == (o.special_code or '').lower()).first()
            if su and su.active:
                usd_total = 0.0
                it = GamePackageItem.query.get(o.item_id) if o.item_id else None
                if it:
                    usd_total = float(it.price or 0.0)
                else:
                    # fallback: derive from order amount/currency
                    if (o.currency or 'USD').upper() == 'USD':
                        usd_total = float(o.amount or 0.0)
                    else:
                        # convert using configured rate
                        try:
                            rate = float(get_config_value("exchange_rate_bsd_per_usd", "0") or 0)
                        except Exception:
                            rate = 0.0
                        usd_total = float(o.amount or 0.0) / rate if rate > 0 else 0.0
                commission = round(usd_total * 0.10, 2)
                if commission > 0:
                    su.balance = float(su.balance or 0.0) + commission
                    db.session.commit()
    except Exception:
        db.session.rollback()
    # Notify buyer on approval (professional tone)
    try:
        if status == "approved" and (o.email or o.name):
            pkg = StorePackage.query.get(o.store_package_id)
            it = GamePackageItem.query.get(o.item_id) if o.item_id else None
            to_addr = o.email or None
            if to_addr:
                juego = (pkg.name if pkg else '').strip()
                item_t = (it.title if it else 'N/A')
                monto = f"{o.amount} {o.currency}"
                body = (
                    "Estimado cliente,\n\n"
                    "Nos complace informarle que su recarga ha sido procesada con éxito.\n"
                    f"Orden #{o.id} – {juego}\n"
                    f"Paquete: {item_t}\n"
                    f"Monto: {monto}\n"
                )
                if (o.delivery_code or '').strip():
                    body += f"Código de entrega: {o.delivery_code}\n"
                body += (
                    "\n"
                    "Agradecemos su preferencia y confianza en Inefable Store. Si necesita asistencia adicional o tiene alguna consulta, no dude en contactarnos. ¡Estamos para servirle!"
                )
                send_email_async(to_addr, f"Orden #{o.id} aprobada – Inefable Store", body)
    except Exception:
        pass
    return jsonify({"ok": True, "id": o.id, "status": o.status, "delivery_code": o.delivery_code})

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
            {"id": it.id, "title": it.title, "price": it.price}
            for it in items
        ]
    })

@app.route("/admin")
def admin():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return redirect(url_for("index"))
    return render_template("admin.html")

# ==============================
# Admin: Mail config and test
# ==============================
@app.route("/admin/config/mail", methods=["GET"])
def admin_config_mail_info():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({
        "ok": True,
        "mail_user": MAIL_USER or "",
        "admin_notify_email": get_config_value("admin_notify_email", ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL or ""),
        "smtp_host": MAIL_SMTP_HOST,
        "smtp_port": MAIL_SMTP_PORT,
    })

@app.route("/admin/config/mail", methods=["POST"])
def admin_config_mail_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    notify = (data.get("admin_notify_email") or "").strip()
    if not notify:
        return jsonify({"ok": False, "error": "Correo destino requerido"}), 400
    set_config_value("admin_notify_email", notify)
    return jsonify({"ok": True, "admin_notify_email": notify})


@app.route("/admin/config/mail/test", methods=["POST"])
def admin_config_mail_test():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    to_email = (data.get("to") or ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL or "").strip()
    subject = (data.get("subject") or "Prueba de correo - Inefable Store").strip()
    body = (data.get("body") or f"Correo de prueba enviado desde Admin a {to_email}.").strip()
    # Intentamos enviar aquí para poder reportar el error exacto
    try:
        if not MAIL_USER or not MAIL_APP_PASSWORD:
            return jsonify({"ok": False, "error": "Falta MAIL_USER o MAIL_APP_PASSWORD"}), 400
        msg = MIMEMultipart()
        msg['From'] = MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body or "", 'plain'))
        try:
            _smtp_send_starttls(msg, to_email)
            return jsonify({"ok": True, "to": to_email, "mode": "starttls"})
        except Exception as e1:
            try:
                _smtp_send_ssl(msg, to_email)
                return jsonify({"ok": True, "to": to_email, "mode": "ssl465"})
            except Exception as e2:
                return jsonify({"ok": False, "error": f"SMTP: starttls:{e1} | ssl:{e2}"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": f"SMTP: {str(e)}"}), 500


@app.route("/user")
def user_page():
    # Profile page for any user (logged or not). Frontend can query /orders/my
    logo_url = get_config_value("logo_path", "")
    role = (session.get("user") or {}).get("role")
    is_admin = role == "admin"
    is_affiliate = role == "affiliate"
    return render_template("user.html", logo_url=logo_url, is_admin=is_admin, is_affiliate=is_affiliate)


@app.route("/terms")
def terms_page():
    logo_url = get_config_value("logo_path", "")
    return render_template("terms.html", logo_url=logo_url)


@app.route("/orders/my")
def orders_my():
    """Return orders for the current session.
    - Admins: can filter by `email` or `customer_id` query params.
    - Users: only their own orders (by session email); query params are ignored.
    Returns up to 30 most recent.
    """
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    q = Order.query.filter(Order.status.in_(["approved", "rejected", "pending"]))
    if user.get("role") == "admin":
        email = (request.args.get("email") or "").strip()
        cid = (request.args.get("customer_id") or "").strip()
        if email:
            q = q.filter(Order.email == email)
        if cid:
            q = q.filter(Order.customer_id == cid)
        if not email and not cid:
            return jsonify({"ok": True, "orders": []})
    else:
        # Normal user: restrict by session email only
        email = (user.get("email") or "").strip()
        if not email:
            return jsonify({"ok": True, "orders": []})
        q = q.filter(Order.email == email)
    rows = q.order_by(Order.created_at.desc()).limit(30).all()
    out = []
    for x in rows:
        pkg = StorePackage.query.get(x.store_package_id)
        it = GamePackageItem.query.get(x.item_id) if x.item_id else None
        out.append({
            "id": x.id,
            "created_at": x.created_at.isoformat(),
            "package_name": pkg.name if pkg else "",
            "item_title": it.title if it else "",
            "item_price_usd": (it.price if it else 0.0),
            "reference": x.reference,
            "status": x.status,
            "method": x.method,
            "currency": x.currency,
            "amount": x.amount,
        })
    return jsonify({"ok": True, "orders": out})


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/admin/images/list")
def admin_images_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    images = ImageAsset.query.order_by(ImageAsset.uploaded_at.desc()).all()
    return jsonify([
        {
            "id": img.id,
            "title": img.title,
            "path": img.path,
            "alt_text": img.alt_text,
            "uploaded_at": img.uploaded_at.isoformat()
        }
        for img in images
    ])


@app.route("/admin/images/upload", methods=["POST"])
def admin_images_upload():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "No file part"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Tipo de archivo no permitido"}), 400

    # Deduplicate: if same filename is uploaded twice within 3 seconds in this session, skip
    try:
        now_ts = datetime.utcnow().timestamp()
        last = session.get("_last_img_upload") or {}
        last_name = last.get("name")
        last_ts = float(last.get("ts", 0))
        if last_name == file.filename and (now_ts - last_ts) < 3.0:
            # Update timestamp to avoid loops and return ok (frontend refreshes gallery anyway)
            session["_last_img_upload"] = {"name": file.filename, "ts": now_ts}
            return jsonify({"ok": True, "skipped": True})
        session["_last_img_upload"] = {"name": file.filename, "ts": now_ts}
    except Exception:
        pass

    filename = secure_filename(file.filename)
    # Avoid collisions by prefixing timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    name, ext = os.path.splitext(filename)
    final_name = f"{name}_{timestamp}{ext}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], final_name)
    file.save(save_path)

    # Build public path according to configured prefix (works for both static and Disk)
    prefix = (app.config.get("UPLOAD_URL_PREFIX") or "/static/uploads").rstrip("/")
    public_path = f"{prefix}/{final_name}"
    image = ImageAsset(title=final_name, path=public_path, alt_text=name)
    db.session.add(image)
    db.session.commit()

    return jsonify({
        "ok": True,
        "image": {
            "id": image.id,
            "title": image.title,
            "path": image.path,
            "alt_text": image.alt_text,
            "uploaded_at": image.uploaded_at.isoformat()
        }
    })


@app.route("/admin/images/<int:image_id>", methods=["DELETE"])
def admin_images_delete(image_id: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    img = ImageAsset.query.get(image_id)
    if not img:
        return jsonify({"ok": False, "error": "No existe"}), 404
    # Try to remove the physical file only if it is within the uploads folder
    try:
        path = (img.path or "").strip()
        prefix = (app.config.get("UPLOAD_URL_PREFIX") or "/static/uploads").rstrip("/")
        if path.startswith(prefix + "/"):
            rel = path[len(prefix):].lstrip("/")
            # If serving from static/uploads, rel is under app.root_path/static/uploads.
            # If serving from Disk, rel is under app.config['UPLOAD_FOLDER'].
            base = app.config.get("UPLOAD_FOLDER") or DEFAULT_UPLOAD
            fs_path = os.path.join(base, rel)
            if os.path.isfile(fs_path):
                os.remove(fs_path)
    except Exception:
        # ignore file removal errors to not block DB delete
        pass
    db.session.delete(img)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/images/<int:image_id>/delete", methods=["POST"])
def admin_images_delete_fallback(image_id: int):
    """Fallback for environments that block DELETE method."""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    img = ImageAsset.query.get(image_id)
    if not img:
        return jsonify({"ok": False, "error": "No existe"}), 404
    try:
        path = (img.path or "").strip()
        prefix = (app.config.get("UPLOAD_URL_PREFIX") or "/static/uploads").rstrip("/")
        if path.startswith(prefix + "/"):
            rel = path[len(prefix):].lstrip("/")
            base = app.config.get("UPLOAD_FOLDER") or DEFAULT_UPLOAD
            fs_path = os.path.join(base, rel)
            if os.path.isfile(fs_path):
                os.remove(fs_path)
    except Exception:
        pass
    db.session.delete(img)
    db.session.commit()
    return jsonify({"ok": True})


# Delete by path: fallback when client cannot resolve ID
@app.route("/admin/images/delete_by_path", methods=["POST"])
def admin_images_delete_by_path():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    path_in = (data.get("path") or "").strip()
    if not path_in:
        return jsonify({"ok": False, "error": "Ruta requerida"}), 400
    img = ImageAsset.query.filter_by(path=path_in).first()
    if not img:
        return jsonify({"ok": False, "error": "No existe"}), 404
    try:
        prefix = (app.config.get("UPLOAD_URL_PREFIX") or "/static/uploads").rstrip("/")
        if path_in.startswith(prefix + "/"):
            rel = path_in[len(prefix):].lstrip("/")
            base = app.config.get("UPLOAD_FOLDER") or DEFAULT_UPLOAD
            fs_path = os.path.join(base, rel)
            if os.path.isfile(fs_path):
                os.remove(fs_path)
    except Exception:
        pass
    db.session.delete(img)
    db.session.commit()
    return jsonify({"ok": True, "deleted_id": img.id})


@app.route("/admin/config/logo", methods=["GET"])
def admin_config_logo_get():
    row = AppConfig.query.filter_by(key="logo_path").first()
    return jsonify({"logo_path": row.value if row else ""})


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


# ==============================
# Admin: exchange rate config
# ==============================
@app.route("/admin/config/rate", methods=["GET"])
def admin_config_rate_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    val = get_config_value("exchange_rate_bsd_per_usd", "")
    return jsonify({"ok": True, "rate_bsd_per_usd": val})


@app.route("/admin/config/rate", methods=["POST"])
def admin_config_rate_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    raw = (data.get("rate_bsd_per_usd") or "").strip()
    try:
        val = float(raw)
        if val < 0:
            val = 0.0
        set_config_value("exchange_rate_bsd_per_usd", str(val))
    except Exception:
        return jsonify({"ok": False, "error": "Valor inválido"}), 400
    return jsonify({"ok": True, "rate_bsd_per_usd": get_config_value("exchange_rate_bsd_per_usd", "0")})


@app.route("/admin/config/payments", methods=["GET"])
def admin_config_payments_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = {
        "pm_bank": get_config_value("pm_bank", ""),
        "pm_name": get_config_value("pm_name", ""),
        "pm_phone": get_config_value("pm_phone", ""),
        "pm_id": get_config_value("pm_id", ""),
        "binance_email": get_config_value("binance_email", ""),
        "binance_phone": get_config_value("binance_phone", ""),
    }
    return jsonify({"ok": True, **data})


@app.route("/admin/config/payments", methods=["POST"])
def admin_config_payments_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    keys = [
        "pm_bank", "pm_name", "pm_phone", "pm_id",
        "binance_email", "binance_phone",
    ]
    for k in keys:
        v = (data.get(k) or "").strip()
        set_config_value(k, v)
    out = {k: get_config_value(k, "") for k in keys}
    return jsonify({"ok": True, **out})


@app.route("/admin/config/hero", methods=["POST"])
def admin_config_hero_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    for i in (1, 2, 3):
        key = f"hero_{i}"
        val = (data.get(key) or "").strip()
        set_config_value(key, val)
    return jsonify({
        "ok": True,
        "hero_1": get_config_value("hero_1", ""),
        "hero_2": get_config_value("hero_2", ""),
        "hero_3": get_config_value("hero_3", ""),
    })


@app.route("/admin/config/logo", methods=["POST"])
def admin_config_logo_set():
    data = request.get_json(silent=True) or {}
    logo_path = (data.get("logo_path") or "").strip()
    if not logo_path:
        # allow clearing the logo
        row = AppConfig.query.filter_by(key="logo_path").first()
        if row:
            db.session.delete(row)
            db.session.commit()
        return jsonify({"ok": True, "logo_path": ""})

    # simple validation: should start with /static/ or http
    if not (logo_path.startswith("/static/") or logo_path.startswith("http://") or logo_path.startswith("https://")):
        return jsonify({"ok": False, "error": "Ruta inválida. Debe ser /static/... o URL completa."}), 400

    row = AppConfig.query.filter_by(key="logo_path").first()
    if not row:
        row = AppConfig(key="logo_path", value=logo_path)
        db.session.add(row)
    else:
        row.value = logo_path
    db.session.commit()
    return jsonify({"ok": True, "logo_path": row.value})


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email y contraseña requeridos"}), 400
    # Admin login
    if email.lower() == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
        session["user"] = {"email": ADMIN_EMAIL, "role": "admin"}
        return jsonify({"ok": True, "user": session["user"]})
    # Affiliate login
    aff = SpecialUser.query.filter(db.func.lower(SpecialUser.email) == email.lower()).first()
    if aff and aff.password_hash and check_password_hash(aff.password_hash, password):
        session["user"] = {"email": aff.email or email, "role": "affiliate", "affiliate_id": aff.id, "name": aff.name}
        return jsonify({"ok": True, "user": session["user"]})
    # User login
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


# Admin: CRUD para items por juego
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
            {"id": it.id, "title": it.title, "price": it.price, "description": it.description, "active": it.active}
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
    try:
        price = float(data.get("price") or 0)
    except Exception:
        price = 0.0
    if not title:
        return jsonify({"ok": False, "error": "Título requerido"}), 400
    item = GamePackageItem(store_package_id=gid, title=title, description=description, price=price, active=True)
    db.session.add(item)
    db.session.commit()
    return jsonify({"ok": True, "item": {"id": item.id, "title": item.title, "price": item.price, "description": item.description, "active": item.active}})

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
    if active is not None:
        item.active = bool(active)
    db.session.commit()
    return jsonify({"ok": True, "package": {"id": item.id, "name": item.name, "image_path": item.image_path, "active": item.active, "category": item.category}})


# Admin packages management
@app.route("/admin/packages", methods=["GET"])
def admin_packages_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    items = StorePackage.query.order_by(StorePackage.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "packages": [
            {"id": p.id, "name": p.name, "image_path": p.image_path, "active": p.active, "category": (p.category or 'mobile'), "description": (p.description or '')}
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
    if category not in ("mobile", "gift"):
        category = "mobile"
    if not name or not image_path:
        return jsonify({"ok": False, "error": "Nombre e imagen requeridos"}), 400
    item = StorePackage(name=name, image_path=image_path, active=True, category=category, description=description)
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
