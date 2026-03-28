import os
import json
import re
import time
import zlib
import sqlite3
import urllib.request
import urllib.error
import html as _html
import hashlib
import hmac as _hmac_module
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import requests as _requests_lib

# Create Flask app
app = Flask(__name__, instance_relative_config=True)
load_dotenv()

# Configure Venezuela timezone (GMT-4)
VE_TIMEZONE = timezone(timedelta(hours=-4))

# ... (rest of the code remains the same)
def now_ve():
    """Return current datetime in Venezuela timezone (GMT-4)"""
    return datetime.now(VE_TIMEZONE)

# Make now_ve available in all templates
@app.context_processor
def inject_now_ve():
    return dict(now_ve=now_ve)

# Ensure instance folder exists for local SQLite default
os.makedirs(app.instance_path, exist_ok=True)

# Basic configuration with DATABASE_URL (Postgres) or persistent Disk (SQLite)
DB_URL = os.environ.get("DATABASE_URL", "").strip()
if DB_URL:
    # Normalize scheme for SQLAlchemy/psycopg (v3)
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DB_URL.startswith("postgresql://") and "+" not in DB_URL.split("://", 1)[0]:
        DB_URL = DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    elif "postgresql+psycopg2://" in DB_URL:
        DB_URL = DB_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
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
# Session lifetime: keep login active for 3 hours
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=3)

@app.before_request
def _make_session_permanent():
    try:
        session.permanent = True
    except Exception:
        pass

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

# ── Binance Pay Auto-Verification ──
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "").strip()
BINANCE_PROXY = os.environ.get("BINANCE_PROXY", "").strip()
BINANCE_REQUEST_TIMEOUT = float(os.environ.get("BINANCE_REQUEST_TIMEOUT_SECONDS", "4"))
BINANCE_TOTAL_TIMEOUT = float(os.environ.get("BINANCE_TOTAL_TIMEOUT_SECONDS", "8"))

db = SQLAlchemy(app)

_PLAYER_SCRAPE_CACHE = {}


def _player_cache_get(key: str):
    try:
        ent = _PLAYER_SCRAPE_CACHE.get(key)
        if not ent:
            return None
        exp = float(ent.get("exp") or 0)
        if exp and time.time() > exp:
            _PLAYER_SCRAPE_CACHE.pop(key, None)
            return None
        return ent.get("val")
    except Exception:
        return None


def _player_cache_set(key: str, val, ttl_seconds: int = 600):
    try:
        _PLAYER_SCRAPE_CACHE[key] = {"val": val, "exp": time.time() + int(ttl_seconds or 0)}
    except Exception:
        pass


def _scrape_ffmania_nick(uid: str) -> str:
    url = f"https://www.freefiremania.com.br/cuenta/{uid}.html"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read() or b""
    except urllib.error.HTTPError as e:
        if int(getattr(e, "code", 0) or 0) == 404:
            return ""
        raise
    html_txt = raw.decode("utf-8", errors="ignore")

    # Convert HTML to plain-ish text to make extraction resilient to markup changes/ads.
    txt = html_txt
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\\1>", " ", txt)
    txt = re.sub(r"(?i)<br\\s*/?>", "\n", txt)
    txt = re.sub(r"(?i)</(p|div|tr|li|h1|h2|h3|table|section|article)>", "\n", txt)
    txt = re.sub(r"(?is)<[^>]+>", " ", txt)
    txt = _html.unescape(txt)
    txt = re.sub(r"[\t\r]+", " ", txt)
    txt = re.sub(r"[ ]{2,}", " ", txt)
    txt = re.sub(r"\n{2,}", "\n", txt)

    patterns = [
        r"(?im)^\s*Nombre\s*:\s*(.+?)\s*$",
        r"(?im)^\s*Nome\s*:\s*(.+?)\s*$",
        r"(?im)^\s*Nick\s*:\s*(.+?)\s*$",
        r"\"nick\"\s*:\s*\"([^\"]+)\"",
    ]
    nick = ""
    for pat in patterns:
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if m:
            nick = (m.group(1) or "").strip()
            break
    nick = re.sub(r"\s+", " ", nick).strip()
    return nick


def _scrape_smileone_bloodstrike_nick(role_id: str) -> str:
    """Consulta la API interna de Smile.One Brasil para obtener el nickname de Blood Strike."""
    try:
        sess = _requests_lib.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        # Step 1: GET the Blood Strike page to obtain session cookies + CSRF token
        page_url = "https://www.smile.one/br/merchant/game/bloodstrike?source=other"
        page = sess.get(page_url, timeout=8)
        print(f"[BS] page status={page.status_code} cookies={dict(sess.cookies)}")
        # Extract CSRF token from _csrf cookie (Yii2 PHP serialized format)
        # Cookie value: "...%3Bs%3A32%3A%220ze4k_...%22%7D" -> extract the 32-char token
        csrf = ""
        raw_csrf_cookie = sess.cookies.get("_csrf", "")
        try:
            import urllib.parse as _urlparse
            decoded = _urlparse.unquote(raw_csrf_cookie)
            # PHP serialized: i:1;s:32:"TOKEN_HERE";}
            m = re.search(r'i:1;s:\d+:"([^"]+)"', decoded)
            if m:
                csrf = m.group(1)
        except Exception:
            pass
        # Fallback: search in HTML
        if not csrf:
            for pat in [r'name="_csrf"\s+value="([^"]+)"', r'"csrf"\s*:\s*"([^"]+)"']:
                m = re.search(pat, page.text)
                if m:
                    csrf = m.group(1)
                    break
        print(f"[BS] csrf={csrf!r}")
        # Step 2: POST checkrole with session cookies + CSRF header
        post_headers = {
            "Referer": page_url,
            "Origin": "https://www.smile.one",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        if csrf:
            post_headers["X-CSRF-Token"] = csrf
        bs_pid = get_config_value("bs_package_id", "") or ""
        bs_sid = get_config_value("bs_server_id", "-1") or "-1"
        post_data = {
            "uid": role_id,
            "sid": bs_sid,
            "pid": bs_pid,
            "product": "bloodstrike",
            "checkrole": "1",
        }
        if csrf:
            post_data["_csrf"] = csrf
        # Try known endpoint variants
        for _endpoint in [
            "https://www.smile.one/br/merchant/game/checkrole?product=bloodstrike",
            "https://www.smile.one/merchant/bloodstrike/checkrole",
            "https://www.smile.one/merchant/checkrole",
        ]:
            resp = sess.post(_endpoint, data=post_data, headers=post_headers, timeout=8)
            print(f"[BS] {_endpoint} -> {resp.status_code} {resp.text[:150]}")
            if resp.status_code == 200:
                break
        if resp.status_code != 200:
            return ""
        try:
            data = resp.json()
        except Exception:
            # Some responses may be plain text
            txt = resp.text.strip()
            if txt.startswith('{"code":'):
                data = json.loads(txt)
            else:
                return ""
        # Handle error codes
        if int(data.get("code") or 0) != 200:
            # 201 = USER ID não existe, 404 = not found, etc.
            print(f"[BS] API error: {data.get('info', '')}")
            return ""
        # Extract username from various possible structures
        username = (
            (data.get("data") or {}).get("username")
            or (data.get("data") or {}).get("nickname")
            or (data.get("data") or {}).get("name")
            or data.get("username")
            or data.get("nickname")
            or data.get("name")
            or data.get("info")  # some APIs return username in info field
            or ""
        )
        if username:
            return username.strip()
        print(f"[BS] JSON completo: {data}")
        return ""
    except Exception as e:
        print(f"[BS] Error: {e}")
        return ""


def _scrape_smileone_mobilelegends_nick(role_id: str, zone_id: str) -> str:
    """Consulta la API interna de Smile.One para obtener el nickname de Mobile Legends."""
    try:
        sess = _requests_lib.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        page_url = "https://www.smile.one/merchant/mobilelegends?source=other"
        page = sess.get(page_url, timeout=8)
        print(f"[ML] page status={page.status_code} cookies={dict(sess.cookies)}")

        csrf = ""
        raw_csrf_cookie = sess.cookies.get("_csrf", "")
        try:
            import urllib.parse as _urlparse
            decoded = _urlparse.unquote(raw_csrf_cookie)
            m = re.search(r'i:1;s:\d+:"([^"]+)"', decoded)
            if m:
                csrf = m.group(1)
        except Exception:
            pass
        if not csrf:
            for pat in [r'name="_csrf"\s+value="([^"]+)"', r'"csrf"\s*:\s*"([^"]+)"']:
                m = re.search(pat, page.text)
                if m:
                    csrf = m.group(1)
                    break
        print(f"[ML] csrf={csrf!r}")

        post_headers = {
            "Referer": page_url,
            "Origin": "https://www.smile.one",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        if csrf:
            post_headers["X-CSRF-Token"] = csrf

        ml_pid = (
            get_config_value("ml_smile_pid", "")
            or get_config_value("ml_package_id", "")
            or ""
        )

        payload_variants = [
            {"user_id": role_id, "zone_id": zone_id},
            {"uid": role_id, "sid": zone_id},
            {"uid": role_id, "zoneid": zone_id},
        ]

        endpoints = [
            "https://www.smile.one/merchant/mobilelegends/checkrole",
            "https://www.smile.one/merchant/checkrole",
        ]

        def _extract_username(resp_json: dict) -> str:
            username = (
                (resp_json.get("data") or {}).get("username")
                or (resp_json.get("data") or {}).get("nickname")
                or (resp_json.get("data") or {}).get("name")
                or resp_json.get("username")
                or resp_json.get("nickname")
                or resp_json.get("name")
                or resp_json.get("info")
                or ""
            )
            return username.strip() if username else ""

        for endpoint in endpoints:
            for payload in payload_variants:
                # Exact payload matching Smile.One's real checkrole form
                post_data = {
                    "checkrole": "1",
                    "pid": ml_pid,
                    **payload,
                }
                if csrf:
                    post_data["_csrf"] = csrf

                resp = sess.post(endpoint, data=post_data, headers=post_headers, timeout=8)
                print(f"[ML] {endpoint} {payload} -> {resp.status_code} {resp.text[:200]}")
                if resp.status_code != 200:
                    continue

                # Smile.One may return HTML instead of JSON on some responses
                ct = (resp.headers.get("content-type") or "").lower()
                body = resp.text.strip()

                # Try JSON parse
                data_json = None
                try:
                    data_json = resp.json()
                except Exception:
                    if body.startswith("{"):
                        try:
                            data_json = json.loads(body)
                        except Exception:
                            pass

                if data_json is not None:
                    code = int(data_json.get("code") or 0)
                    if code == 200:
                        username = _extract_username(data_json)
                        if username:
                            return username
                    print(f"[ML] JSON code={code} info={data_json.get('info','')}")
                    # code 200 with username found → already returned above
                    # code != 200 with this payload → try next variant
                    continue

                # Some endpoints return the nickname as plain text or in HTML
                if body and len(body) < 200 and "<" not in body:
                    return body.strip('" \t\r\n')

                print(f"[ML] non-JSON body len={len(body)}")

        return ""
    except Exception as e:
        print(f"[ML] Error: {e}")
        return ""


@app.route("/store/player/verify/bloodstrike")
def store_player_verify_bloodstrike():
    scrape_enabled = (os.environ.get("SCRAPE_ENABLED", "true").strip().lower() == "true")
    if not scrape_enabled:
        return jsonify({"ok": False, "error": "Verificación deshabilitada"}), 403

    uid = (request.args.get("uid") or "").strip()
    gid_raw = (request.args.get("gid") or "").strip()
    if not uid or not uid.isdigit():
        return jsonify({"ok": False, "error": "ID inválido"}), 400

    bs_package_id = (get_config_value("bs_package_id", "") or "").strip()
    if not bs_package_id or bs_package_id != gid_raw:
        return jsonify({"ok": False, "error": "Verificación no disponible para este juego"}), 403

    cache_key = f"bs_smileone:{uid}"
    cached = _player_cache_get(cache_key)
    if cached is not None:
        if not cached:
            return jsonify({"ok": False, "error": "ID no encontrado"}), 404
        return jsonify({"ok": True, "uid": uid, "nick": cached, "cached": True})

    nick = _scrape_smileone_bloodstrike_nick(uid)

    _player_cache_set(cache_key, nick, ttl_seconds=600)
    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    return jsonify({"ok": True, "uid": uid, "nick": nick, "cached": False})


@app.route("/store/player/verify/mobilelegends")
def store_player_verify_mobilelegends():
    scrape_enabled = (os.environ.get("SCRAPE_ENABLED", "true").strip().lower() == "true")
    if not scrape_enabled:
        return jsonify({"ok": False, "error": "Verificación deshabilitada"}), 403

    uid = (request.args.get("uid") or "").strip()
    zid = (request.args.get("zid") or request.args.get("zone") or "").strip()
    gid_raw = (request.args.get("gid") or "").strip()
    if not uid or not uid.isdigit():
        return jsonify({"ok": False, "error": "ID inválido"}), 400
    if not zid or not zid.isdigit():
        return jsonify({"ok": False, "error": "Zona ID inválida"}), 400

    ml_package_id = (get_config_value("ml_package_id", "") or "").strip()
    if not ml_package_id or ml_package_id != gid_raw:
        return jsonify({"ok": False, "error": "Verificación no disponible para este juego"}), 403

    cache_key = f"ml_smileone:{uid}:{zid}"
    cached = _player_cache_get(cache_key)
    if cached is not None:
        if not cached:
            return jsonify({"ok": False, "error": "ID no encontrado"}), 404
        return jsonify({"ok": True, "uid": uid, "zid": zid, "nick": cached, "cached": True})

    nick = _scrape_smileone_mobilelegends_nick(uid, zid)

    _player_cache_set(cache_key, nick, ttl_seconds=600)
    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    return jsonify({"ok": True, "uid": uid, "zid": zid, "nick": nick, "cached": False})


@app.route("/store/player/verify")
def store_player_verify():
    scrape_enabled = (os.environ.get("SCRAPE_ENABLED", "true").strip().lower() == "true")
    if not scrape_enabled:
        return jsonify({"ok": False, "error": "Verificación deshabilitada"}), 403

    uid = (request.args.get("uid") or "").strip()
    gid_raw = (request.args.get("gid") or "").strip()
    if not uid or not uid.isdigit():
        return jsonify({"ok": False, "error": "ID inválido"}), 400
    if not gid_raw or not gid_raw.isdigit():
        return jsonify({"ok": False, "error": "Juego inválido"}), 400

    active_login_game_id = (get_config_value("active_login_game_id", "") or "").strip()
    if not active_login_game_id or active_login_game_id != gid_raw:
        return jsonify({"ok": False, "error": "Verificación no disponible para este juego"}), 403

    game = StorePackage.query.get(int(gid_raw))
    if not game or not getattr(game, "active", False):
        return jsonify({"ok": False, "error": "Juego no encontrado"}), 404

    cache_key = f"ffmania:{uid}"
    cached = _player_cache_get(cache_key)
    if cached is not None:
        if not cached:
            return jsonify({"ok": False, "error": "ID no encontrado"}), 404
        return jsonify({"ok": True, "uid": uid, "nick": cached, "cached": True})

    try:
        nick = _scrape_ffmania_nick(uid)
    except Exception:
        return jsonify({"ok": False, "error": "No se pudo verificar el ID"}), 502

    # Cache both hits and misses for short time to reduce external traffic
    _player_cache_set(cache_key, nick, ttl_seconds=600)
    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    return jsonify({"ok": True, "uid": uid, "nick": nick, "cached": False})

# ==============================
# Serve uploaded files (runtime uploads)
# ==============================
# This enables serving files stored in UPLOAD_FOLDER under a public URL.
# Recommended for Render: set UPLOAD_FOLDER to a writable path (e.g. /var/tmp/uploads)
# and UPLOAD_URL_PREFIX to '/uploads'.
prefix = (app.config.get("UPLOAD_URL_PREFIX") or "/uploads").rstrip("/")
if prefix == "":
    prefix = "/uploads"

def _serve_upload_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route(f"{prefix}/<path:filename>")
def serve_uploads(filename):
    return _serve_upload_file(filename)


# Backward-compat: old deployments may have stored paths under either prefix.
# Keep both routes alive so existing DB image paths continue working.
if prefix != "/uploads":
    @app.route("/uploads/<path:filename>")
    def serve_uploads_legacy_uploads(filename):
        return _serve_upload_file(filename)

if prefix != "/static/uploads":
    @app.route("/static/uploads/<path:filename>")
    def serve_uploads_legacy_static_uploads(filename):
        return _serve_upload_file(filename)

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
    # Revendedores API automation state (pending_verification, success, etc.)
    automation_json = db.Column(db.Text, default="")
    # Payment capture (voucher/comprobante image path relative to UPLOAD_FOLDER)
    payment_capture = db.Column(db.String(500), default="")


class OrderSummary(db.Model):
    __tablename__ = "order_summaries"
    id = db.Column(db.Integer, primary_key=True)
    period = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    store_package_id = db.Column(db.Integer, nullable=False)
    item_id = db.Column(db.Integer, nullable=True)
    package_name = db.Column(db.String(200), default="")
    item_title = db.Column(db.String(200), default="")
    status = db.Column(db.String(20), default="")
    method = db.Column(db.String(20), default="")
    currency = db.Column(db.String(10), default="USD")
    order_count = db.Column(db.Integer, default=0)
    total_amount = db.Column(db.Float, default=0.0)
    total_price_usd = db.Column(db.Float, default=0.0)
    __table_args__ = (
        db.UniqueConstraint("period", "store_package_id", "item_id", "status", "method", "currency", name="uq_order_summary"),
    )


_ORDER_CLEANUP_DAYS = int(os.environ.get("ORDER_CLEANUP_DAYS", "7"))
_ORDER_CLEANUP_INTERVAL_HOURS = float(os.environ.get("ORDER_CLEANUP_INTERVAL_HOURS", "6"))


def _calculate_profit_components_for_order(order: 'Order', items_by_id: dict[int, 'GamePackageItem']) -> tuple[float, float]:
    use_affiliate = False
    su = None
    if order.special_user_id:
        su = SpecialUser.query.get(order.special_user_id)
    if (not su) and (order.special_code or ""):
        su = SpecialUser.query.filter(
            db.func.lower(SpecialUser.code) == (order.special_code or "").lower(),
            SpecialUser.active == True,
        ).first()
    if su and su.active:
        scope_ok = True
        sc = (su.scope or "all")
        if sc == "package":
            try:
                scope_ok = (su.scope_package_id == order.store_package_id)
            except Exception:
                scope_ok = False
        use_affiliate = scope_ok

    items_map = {}
    try:
        if (order.items_json or "").strip():
            payload = json.loads(order.items_json or "[]")
            if isinstance(payload, list):
                for ent in payload:
                    try:
                        iid = int(ent.get("item_id") or 0)
                    except Exception:
                        iid = 0
                    if iid <= 0:
                        continue
                    q = max(int(ent.get("qty") or 1), 1)
                    p = float(ent.get("price") or 0.0)
                    it = items_by_id.get(iid)
                    cost_unit = float(ent.get("cost_unit_usd") or (it.profit_net_usd if it else 0.0) or 0.0)
                    cur = items_map.get(iid) or {"qty": 0, "revenue": 0.0, "cost_total": 0.0}
                    cur["qty"] += q
                    cur["revenue"] += (p * q)
                    cur["cost_total"] += (cost_unit * q)
                    items_map[iid] = cur
    except Exception:
        items_map = {}

    if not items_map and order.item_id:
        try:
            iid = int(order.item_id)
            if iid > 0:
                it = items_by_id.get(iid)
                if it:
                    cur = items_map.get(iid) or {"qty": 0, "revenue": 0.0, "cost_total": 0.0}
                    cur["qty"] += 1
                    cur["revenue"] += float(order.price or it.price or 0.0)
                    cur["cost_total"] += float(it.profit_net_usd or 0.0)
                    items_map[iid] = cur
        except Exception:
            pass

    comm_pct = float(su.commission_percent or 0.0) if use_affiliate and su else 0.0
    profit_total = 0.0
    commission_total = 0.0
    for iid, agg in items_map.items():
        it = items_by_id.get(iid)
        if not it:
            continue
        qty = int(agg.get("qty") or 0)
        revenue = float(agg.get("revenue") or 0.0)
        cost_total = float(agg.get("cost_total") or 0.0)
        if qty <= 0 or cost_total <= 0.0:
            continue
        if use_affiliate and comm_pct > 0:
            commission_item = round(revenue * (comm_pct / 100.0), 2)
            commission_total += commission_item
            profit_val = revenue - cost_total - commission_item
        else:
            profit_val = revenue - cost_total
        if profit_val < 0.0:
            profit_val = 0.0
        profit_total += profit_val
    return profit_total, commission_total


def _snapshot_closed_periods_from_orders(orders: list['Order']) -> None:
    successful_orders = [o for o in orders if o.status in ("approved", "delivered") and o.created_at]
    if not successful_orders:
        return

    current_cutoff = get_stats_reset_cutoff()
    periods = {}
    for order in successful_orders:
        period_start, period_end = get_stats_period_bounds(order.created_at)
        if period_end >= current_cutoff:
            continue
        periods.setdefault((period_start, period_end), []).append(order)

    if not periods:
        return

    items_by_id = {it.id: it for it in GamePackageItem.query.all()}
    for (period_start, period_end), period_orders in periods.items():
        existing = ProfitSnapshot.query.filter_by(period_start=period_start, period_end=period_end).first()
        if existing:
            continue
        profit = 0.0
        commission = 0.0
        for order in period_orders:
            try:
                order_profit, order_commission = _calculate_profit_components_for_order(order, items_by_id)
                profit += order_profit
                commission += order_commission
            except Exception:
                continue
        db.session.add(ProfitSnapshot(
            period_start=period_start,
            period_end=period_end,
            profit_usd=round(profit, 2),
            commission_usd=round(commission, 2),
        ))


def _aggregate_and_cleanup_orders():
    """Aggregate old terminal-state orders into OrderSummary, then delete them.
    Keeps ALL pending orders and recent orders (< ORDER_CLEANUP_DAYS days)."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=_ORDER_CLEANUP_DAYS)
        terminal = ("approved", "rejected", "delivered")
        old_orders = Order.query.filter(
            Order.status.in_(terminal),
            Order.created_at < cutoff,
        ).all()

        if not old_orders:
            return 0

        _snapshot_closed_periods_from_orders(old_orders)

        # Aggregate into OrderSummary
        agg = {}
        for o in old_orders:
            period = o.created_at.strftime("%Y-%m-%d") if o.created_at else "unknown"
            pkg = StorePackage.query.get(o.store_package_id)
            it = GamePackageItem.query.get(o.item_id) if o.item_id else None
            key = (period, o.store_package_id, o.item_id, o.status, o.method, o.currency or "USD")
            if key not in agg:
                agg[key] = {
                    "period": period,
                    "store_package_id": o.store_package_id,
                    "item_id": o.item_id,
                    "package_name": pkg.name if pkg else "",
                    "item_title": it.title if it else "",
                    "status": o.status,
                    "method": o.method,
                    "currency": o.currency or "USD",
                    "order_count": 0,
                    "total_amount": 0.0,
                    "total_price_usd": 0.0,
                }
            agg[key]["order_count"] += 1
            agg[key]["total_amount"] += float(o.amount or 0)
            agg[key]["total_price_usd"] += float(o.price or 0)

        for key, data in agg.items():
            row = OrderSummary.query.filter_by(
                period=data["period"],
                store_package_id=data["store_package_id"],
                item_id=data["item_id"],
                status=data["status"],
                method=data["method"],
                currency=data["currency"],
            ).first()
            if row:
                row.order_count += data["order_count"]
                row.total_amount += data["total_amount"]
                row.total_price_usd += data["total_price_usd"]
            else:
                db.session.add(OrderSummary(**data))

        count = len(old_orders)
        for o in old_orders:
            _delete_capture(o.payment_capture)
            db.session.delete(o)

        db.session.commit()
        return count
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[OrderCleanup] Error: {exc}")
        return -1


def _order_cleanup_loop():
    """Background thread: periodically clean up old orders."""
    import time as _t
    _t.sleep(60)  # Wait for app startup
    while True:
        try:
            with app.app_context():
                db.create_all()
                n = _aggregate_and_cleanup_orders()
                if n and n > 0:
                    print(f"[OrderCleanup] Eliminadas {n} órdenes antiguas (>{_ORDER_CLEANUP_DAYS} días)")
                elif n == 0:
                    pass  # Nothing to clean
        except Exception as exc:
            print(f"[OrderCleanup] Thread error: {exc}")
        _t.sleep(_ORDER_CLEANUP_INTERVAL_HOURS * 3600)


_cleanup_thread = threading.Thread(target=_order_cleanup_loop, daemon=True)
_cleanup_thread.start()


# ==============================
# Binance Pay Auto-Verification
# ==============================

_BINANCE_API_ENDPOINTS = [
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
    "https://api.binance.com",
]


def _binance_create_signature(query_string: str) -> str:
    return _hmac_module.new(
        BINANCE_API_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _binance_get_pay_transactions(start_time_ms: int, limit: int = 100):
    """Fetch Binance Pay transactions starting from start_time_ms (epoch ms).

    Returns a list of transaction dicts, or None on error.
    Uses BINANCE_PROXY env var and tries multiple Binance API endpoints.
    """
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        return None
    proxies = {"https": BINANCE_PROXY, "http": BINANCE_PROXY} if BINANCE_PROXY else None
    timestamp_ms = int(time.time() * 1000)
    params = {
        "startTime": start_time_ms,
        "limit": limit,
        "timestamp": timestamp_ms,
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    signature = _binance_create_signature(query_string)
    full_query = f"{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    path = "/sapi/v1/pay/transactions"
    for base_url in _BINANCE_API_ENDPOINTS:
        try:
            resp = _requests_lib.get(
                f"{base_url}{path}?{full_query}",
                headers=headers,
                proxies=proxies,
                timeout=BINANCE_REQUEST_TIMEOUT,
            )
            if resp.ok:
                data = resp.json()
                # API may return {data: [...]} or {rows: [...]} depending on version
                return data.get("data") or data.get("rows") or []
        except Exception:
            continue
    return None


def _binance_verify_payment(order_reference: str, expected_usdt: float, since_ms: int):
    """Return True if a Binance Pay transaction matches the reference and amount.

    Looks for order_reference string inside the transaction's beneficiary note
    (orderMemo / remark / note fields) AND verifies exact USDT amount (±0.01).
    """
    txs = _binance_get_pay_transactions(start_time_ms=since_ms)
    if txs is None:
        return None  # API error — caller decides whether to retry
    if not txs:
        return False
    ref_upper = str(order_reference).upper().strip()
    for tx in txs:
        # Extract note written by payer
        tx_note = (
            tx.get("orderMemo")
            or tx.get("remark")
            or tx.get("note")
            or ""
        )
        tx_note_upper = str(tx_note).upper().strip()
        if not tx_note_upper:
            continue
        if ref_upper not in tx_note_upper:
            continue
        # Verify currency is USDT
        tx_currency = ""
        funds = tx.get("fundsDetail") or []
        if isinstance(funds, list) and funds:
            tx_currency = str(funds[0].get("currency") or "").upper()
        if not tx_currency:
            tx_currency = str(tx.get("transactedCurrency") or tx.get("currency") or "").upper()
        if tx_currency and tx_currency != "USDT":
            continue
        # Verify amount
        tx_amount = 0.0
        if isinstance(funds, list) and funds:
            try:
                tx_amount = float(funds[0].get("amount") or 0)
            except Exception:
                pass
        if tx_amount == 0.0:
            try:
                tx_amount = float(tx.get("transactedAmount") or tx.get("amount") or 0)
            except Exception:
                pass
        if abs(tx_amount - expected_usdt) <= 0.01:
            return True
    return False



def _binance_auto_approve(order):
    """Approve a Binance-paid order and trigger Revendedores automation.

    Mirrors the approval logic of admin_orders_set_status but is called from
    the background thread after Binance API payment confirmation.
    ONLY triggers for orders where the item has auto_enabled=True in the mapping.
    """
    # Final safety check: order must still be pending
    if (order.status or "").lower() != "pending":
        print(f"[BinanceAuto] Order #{order.id} is '{order.status}', not pending. Aborting auto-approve.")
        return
    try:
        order.status = "approved"
        db.session.commit()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[BinanceAuto] DB error approving order #{order.id}: {exc}")
        return

    # Affiliate commission crediting (mirrors admin_orders_set_status)
    try:
        su = None
        if order.special_user_id:
            su = SpecialUser.query.get(order.special_user_id)
        if (not su) and (order.special_code or ""):
            su = SpecialUser.query.filter(
                db.func.lower(SpecialUser.code) == (order.special_code or "").lower(),
                SpecialUser.active == True,
            ).first()
        if su and su.active:
            sc = (su.scope or "all")
            scope_ok = True
            if sc == "package":
                try:
                    scope_ok = (su.scope_package_id == order.store_package_id)
                except Exception:
                    scope_ok = False
            if scope_ok:
                subtotal = 0.0
                try:
                    if (order.items_json or "").strip():
                        items = json.loads(order.items_json or "[]")
                        if isinstance(items, list):
                            for ent in items:
                                q = int(ent.get("qty") or 1)
                                subtotal += float(ent.get("price") or 0.0) * q
                except Exception:
                    pass
                if subtotal <= 0 and order.item_id:
                    gi = GamePackageItem.query.get(order.item_id)
                    if gi:
                        subtotal = float(gi.price or 0.0)
                comm_pct = float(su.commission_percent or 0.0)
                if comm_pct > 0 and subtotal > 0:
                    try:
                        inc = round(subtotal * (comm_pct / 100.0), 2)
                        su.balance = round(float(su.balance or 0.0) + inc, 2)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
    except Exception:
        pass

    # Notify buyer (HTML email)
    try:
        if order.email:
            pkg = StorePackage.query.get(order.store_package_id)
            it = GamePackageItem.query.get(order.item_id) if order.item_id else None
            brand = _email_brand()
            html, text = build_order_approved_email(order, pkg, it)
            try:
                send_email_html(order.email, f"Orden #{order.id} aprobada - {brand}", html, text)
            except Exception:
                send_email_async(order.email, f"Orden #{order.id} aprobada - {brand}", text)
    except Exception:
        pass

    # Revendedores automation (only for auto_enabled items)
    try:
        result = _dispatch_order_auto_recharges(order, binance_auto=True)
        if result.get("summary", {}).get("total_units"):
            print(
                f"[BinanceAuto] Order #{order.id}: "
                f"{result['summary'].get('completed_units', 0)}/{result['summary'].get('total_units', 0)} completadas"
            )
    except Exception as exc:
        print(f"[BinanceAuto] Revendedores error for order #{order.id}: {exc}")


def _binance_order_verification_loop():
    """Background thread: poll Binance Pay API every 30 s for pending Binance orders.

    For each pending Binance order whose item has auto_enabled=True in
    RevendedoresItemMapping, verify payment via Binance API. On confirmation,
    auto-approve and dispatch via Revendedores.
    """
    import time as _t
    _t.sleep(45)  # extra startup delay
    while True:
        try:
            with app.app_context():
                enabled = get_config_value("binance_auto_enabled", "0")
                if enabled != "1":
                    _t.sleep(30)
                    continue
                if not BINANCE_API_KEY or not BINANCE_API_SECRET:
                    _t.sleep(60)
                    continue
                pending_orders = Order.query.filter_by(
                    method="binance", status="pending"
                ).all()
                for order in pending_orders:
                    try:
                        if not _order_has_auto_recharges(order):
                            continue
                        if not order.reference:
                            continue
                        # Search from 5 minutes before order creation
                        since_ms = int(
                            (order.created_at - timedelta(minutes=5)).timestamp() * 1000
                        )
                        expected_usdt = float(order.amount or 0.0)
                        if expected_usdt <= 0:
                            continue
                        result = _binance_verify_payment(
                            order_reference=order.reference,
                            expected_usdt=expected_usdt,
                            since_ms=since_ms,
                        )
                        if result is True:
                            # Re-read from DB to avoid race with manual admin approval
                            db.session.refresh(order)
                            if (order.status or "").lower() != "pending":
                                print(f"[BinanceAuto] Order #{order.id} no longer pending (status={order.status}). Skipping.")
                                continue
                            print(f"[BinanceAuto] Payment verified for order #{order.id}. Auto-approving.")
                            _binance_auto_approve(order)
                        # None = API error, False = not found yet — both silently retry
                    except Exception as exc:
                        print(f"[BinanceAuto] Error processing order #{order.id}: {exc}")
                    _t.sleep(2)  # rate-limit between orders
        except Exception as exc:
            print(f"[BinanceAuto] Thread error: {exc}")
        _t.sleep(30)


_binance_thread = threading.Thread(target=_binance_order_verification_loop, daemon=True)
_binance_thread.start()


def _ensure_automation_json_column():
    try:
        with app.app_context():
            inspector = db.inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('orders')]
            if 'automation_json' not in cols:
                db.session.execute(db.text("ALTER TABLE orders ADD COLUMN automation_json TEXT DEFAULT ''"))
                db.session.commit()
                print("[Migration] Added automation_json column to orders table")
    except Exception as e:
        print(f"[Migration] automation_json check: {e}")

_ensure_automation_json_column()


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

def _email_style():
    """Color constants for Inefable Store email templates."""
    return {
        'bg': '#0b0f14',
        'card_bg': '#111827',
        'accent': '#1d4ed8',
        'accent_light': '#3b82f6',
        'text': '#e0e0e0',
        'muted': '#94a3b8',
        'border': '#1e293b',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#ef4444',
        'white': '#ffffff',
        'font': "'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    }


def _email_brand():
    return get_config_value("site_name", "InefableStore")


def _email_support_links():
    whatsapp = get_config_value("whatsapp_url", "")
    support = get_config_value("support_url", "")
    privacy = get_config_value("privacy_url", "")
    return {'whatsapp': whatsapp or '', 'support': support or '', 'privacy': privacy or ''}


def _email_wrap(title, body_content):
    """Wrap body content in a full HTML email structure."""
    s = _email_style()
    brand = _email_brand()
    sup = _email_support_links()

    links_html = ''
    if sup['whatsapp']:
        links_html += f'<a href="{sup["whatsapp"]}" style="color:{s["accent_light"]}; text-decoration:none; margin-right:16px;">WhatsApp</a>'
    if sup['support']:
        links_html += f'<a href="{sup["support"]}" style="color:{s["accent_light"]}; text-decoration:none; margin-right:16px;">Soporte</a>'
    if sup['privacy']:
        links_html += f'<a href="{sup["privacy"]}" style="color:{s["accent_light"]}; text-decoration:none;">Privacidad</a>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0; padding:0; background-color:{s['bg']}; font-family:{s['font']}; color:{s['text']}; -webkit-text-size-adjust:100%;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{s['bg']};">
<tr><td align="center" style="padding:24px 16px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background-color:{s['card_bg']}; border-radius:12px; overflow:hidden; border:1px solid {s['border']};">

<!-- Header -->
<tr>
<td style="background: linear-gradient(135deg, {s['accent']} 0%, #1e40af 100%); padding:28px 32px; text-align:center;">
    <h1 style="margin:0; font-size:24px; font-weight:700; color:{s['white']}; letter-spacing:0.5px;">{brand}</h1>
</td>
</tr>

<!-- Body -->
<tr>
<td style="padding:32px 32px 24px 32px;">
    {body_content}
</td>
</tr>

<!-- Footer -->
<tr>
<td style="padding:20px 32px 28px 32px; border-top:1px solid {s['border']}; text-align:center;">
    {f'<p style="margin:0 0 8px 0; font-size:13px; color:{s["muted"]};">¿Necesitas ayuda?</p><p style="margin:0 0 12px 0; font-size:13px;">{links_html}</p>' if links_html else ''}
    <p style="margin:0; font-size:12px; color:{s['muted']};">&copy; {now_ve().year} {brand} &mdash; Todos los derechos reservados</p>
</td>
</tr>

</table>
</td></tr></table>
</body>
</html>"""


def _email_detail_row(label, value, value_color=None):
    """Single detail row for order info tables."""
    s = _email_style()
    vc = value_color or s['white']
    return f"""<tr>
<td style="padding:8px 0; color:{s['muted']}; font-size:14px; border-bottom:1px solid {s['border']}; width:40%;">{label}</td>
<td style="padding:8px 0; color:{vc}; font-size:14px; font-weight:600; border-bottom:1px solid {s['border']}; text-align:right;">{value}</td>
</tr>"""


def _email_status_badge(label, color):
    """Inline status badge."""
    return f'<span style="display:inline-block; padding:4px 14px; background-color:{color}; color:#fff; border-radius:20px; font-size:13px; font-weight:600; letter-spacing:0.3px;">{label}</span>'


def _email_code_block(codes):
    """Render delivery code(s) as a highlighted block."""
    s = _email_style()
    if not codes:
        return ''
    rows = []
    for idx, c in enumerate(codes, start=1):
        label = 'Tu codigo' if len(codes) == 1 else f'Codigo #{idx}'
        rows.append(f"""
<div style="margin:{('16' if idx > 1 else '24')}px 0 0 0; padding:20px; background-color:#0b0f14; border:2px dashed {s['accent']}; border-radius:10px; text-align:center;">
    <p style="margin:0 0 8px 0; font-size:13px; color:{s['muted']}; text-transform:uppercase; letter-spacing:1px;">{label}</p>
    <p style="margin:0; font-size:28px; font-weight:700; color:{s['accent_light']}; letter-spacing:2px; font-family:monospace;">{c}</p>
    <p style="margin:8px 0 0 0; font-size:12px; color:{s['muted']};">Copia este codigo y canjealo en la plataforma correspondiente</p>
</div>""")
    return "\n".join(rows)


def _email_items_rows(o):
    """Build detail rows and compute metadata for multi-item or single-item orders."""
    items_html = ''
    qty_total = 1
    try:
        if (o.items_json or '').strip():
            items = json.loads(o.items_json or '[]')
            if isinstance(items, list) and items:
                qty_total = sum(int(ent.get('qty') or 1) for ent in items)
                for ent in items:
                    t = ent.get('title', 'N/A')
                    q = int(ent.get('qty') or 1)
                    try:
                        p = float(ent.get('price') or 0.0)
                    except Exception:
                        p = 0.0
                    items_html += _email_detail_row(f'{q} x', f'{t} - ${p:.2f} c/u')
    except Exception:
        pass
    return items_html, qty_total


def _email_delivery_codes(o):
    """Extract delivery codes from an order."""
    codes = []
    try:
        if (o.delivery_codes_json or '').strip():
            parsed = json.loads(o.delivery_codes_json or '[]')
            if isinstance(parsed, list):
                codes = [str(x or '').strip() for x in parsed if str(x or '').strip()]
        if not codes and (o.delivery_code or '').strip():
            codes = [o.delivery_code.strip()]
    except Exception:
        pass
    return codes


# ──────────────────────────────────────────────────────────────────────
# ORDEN APROBADA - se envia al cliente
# ──────────────────────────────────────────────────────────────────────

def build_order_approved_email(o: 'Order', pkg: 'StorePackage', it: 'GamePackageItem'):
    s = _email_style()
    brand = _email_brand()
    juego = (pkg.name if pkg else '').strip()
    item_t = (it.title if it else 'N/A')
    monto = f"{o.amount} {o.currency}"
    is_gift = (pkg.category or '').lower() == 'gift' if pkg else False

    codes = _email_delivery_codes(o)
    code_html = _email_code_block(codes)
    items_html, qty_total = _email_items_rows(o)
    qty_label = 'Cantidad de tarjetas' if is_gift else 'Recargas totales'

    body = f"""
<h2 style="margin:0 0 8px 0; font-size:20px; color:{s['white']};">{'Gift enviado' if is_gift else 'Recarga Exitosa'}</h2>
<p style="margin:0 0 20px 0; font-size:15px; color:{s['text']}; line-height:1.6;">
    Tu orden <strong style="color:{s['accent_light']};">#{o.id}</strong> ha sido procesada exitosamente.
    {('Aqui tienes tu codigo:' if codes else 'Tu recarga ha sido aplicada.')}
</p>

{_email_status_badge('Completada', s['success'])}

{code_html}

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
{_email_detail_row('Orden', f'#{o.id}')}
{_email_detail_row('Juego', juego or 'N/A')}
{items_html if items_html else _email_detail_row('Paquete', item_t)}
{_email_detail_row(qty_label, str(qty_total))}
{_email_detail_row('Monto', monto, s['accent_light'])}
{_email_detail_row('Jugador', o.customer_name or o.customer_id or 'N/A') if o.customer_id else ''}
</table>

<p style="margin:24px 0 0 0; font-size:14px; color:{s['text']}; line-height:1.5;">
    Gracias por tu compra! Esperamos verte pronto de nuevo.
</p>
"""

    html = _email_wrap(f'Orden #{o.id} aprobada - {brand}', body)

    # Plain text fallback
    try:
        lines = [f"Orden #{o.id} aprobada\n", f"Juego: {juego}", f"Paquete: {item_t}"]
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
        lines.append(f"{qty_label}: {qty_total}")
        lines.append(f"Monto: {monto}")
        if codes:
            for i, c in enumerate(codes, start=1):
                label = 'Codigo' if len(codes) == 1 else f'Codigo #{i}'
                lines.append(f"{label}: {c}")
        lines.append(f"\nGracias por tu compra!\n- {brand}")
        text = "\n".join(lines)
    except Exception:
        text = f"Orden #{o.id} aprobada - {juego} - {monto}\nGracias por tu compra!\n- {brand}"
    return html, text


# ──────────────────────────────────────────────────────────────────────
# ORDEN CREADA - se envia al cliente
# ──────────────────────────────────────────────────────────────────────

def build_order_created_email(o: 'Order', pkg: 'StorePackage', it: 'GamePackageItem'):
    s = _email_style()
    brand = _email_brand()
    juego = (pkg.name if pkg else '').strip()
    item_t = (it.title if it else 'N/A')
    monto = f"{o.amount} {o.currency}"

    body = f"""
<h2 style="margin:0 0 8px 0; font-size:20px; color:{s['white']};">Orden recibida!</h2>
<p style="margin:0 0 20px 0; font-size:15px; color:{s['text']}; line-height:1.6;">
    Hemos recibido tu orden <strong style="color:{s['accent_light']};">#{o.id}</strong>.
    Estamos verificando tu pago. Te notificaremos cuando sea procesada.
</p>

{_email_status_badge('Pendiente de verificacion', s['warning'])}

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
{_email_detail_row('Orden', f'#{o.id}')}
{_email_detail_row('Juego', juego or 'N/A')}
{_email_detail_row('Paquete', item_t)}
{_email_detail_row('Monto', monto, s['accent_light'])}
{_email_detail_row('Metodo de pago', (o.method or '').upper())}
{_email_detail_row('Referencia', o.reference or 'N/A')}
{_email_detail_row('Jugador', o.customer_name or o.customer_id or 'N/A') if o.customer_id else ''}
</table>

<p style="margin:24px 0 0 0; font-size:13px; color:{s['muted']}; line-height:1.5;">
    El tiempo de procesamiento habitual es de <strong>5 a 30 minutos</strong> en horario de atencion.
    Recibiras un correo cuando tu orden sea aprobada.
</p>
"""

    html = _email_wrap(f'Orden #{o.id} recibida - {brand}', body)

    text = (
        f"Orden recibida!\n\n"
        f"Tu orden #{o.id} ha sido registrada.\n"
        f"Juego: {juego}\nPaquete: {item_t}\nMonto: {monto}\n"
        f"Metodo: {(o.method or '').upper()}\nReferencia: {o.reference or 'N/A'}\n\n"
        f"Estamos verificando tu pago. Te notificaremos cuando sea procesada.\n\n- {brand}"
    )
    return html, text


# ──────────────────────────────────────────────────────────────────────
# ORDEN RECHAZADA - se envia al cliente
# ──────────────────────────────────────────────────────────────────────

def build_order_rejected_email(o: 'Order', pkg: 'StorePackage', it: 'GamePackageItem', reason=''):
    s = _email_style()
    brand = _email_brand()
    juego = (pkg.name if pkg else '').strip()
    item_t = (it.title if it else 'N/A')
    monto = f"{o.amount} {o.currency}"
    reason_text = reason or ''

    reason_html = ''
    if reason_text:
        reason_html = f"""
<div style="margin:20px 0; padding:16px; background-color:rgba(239,68,68,0.1); border-left:4px solid {s['danger']}; border-radius:6px;">
    <p style="margin:0 0 4px 0; font-size:12px; color:{s['danger']}; text-transform:uppercase; letter-spacing:0.5px; font-weight:600;">Motivo</p>
    <p style="margin:0; font-size:14px; color:{s['text']}; line-height:1.5;">{reason_text}</p>
</div>
"""

    body = f"""
<h2 style="margin:0 0 8px 0; font-size:20px; color:{s['white']};">Orden rechazada</h2>
<p style="margin:0 0 20px 0; font-size:15px; color:{s['text']}; line-height:1.6;">
    Lamentamos informarte que tu orden <strong style="color:{s['accent_light']};">#{o.id}</strong>
    no pudo ser procesada.
</p>

{_email_status_badge('Rechazada', s['danger'])}

{reason_html}

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
{_email_detail_row('Orden', f'#{o.id}')}
{_email_detail_row('Juego', juego or 'N/A')}
{_email_detail_row('Paquete', item_t)}
{_email_detail_row('Monto', monto, s['accent_light'])}
{_email_detail_row('Referencia', o.reference or 'N/A')}
</table>

<p style="margin:24px 0 0 0; font-size:14px; color:{s['text']}; line-height:1.5;">
    Si crees que esto es un error, por favor contactanos con tu numero de orden para que podamos revisar tu caso.
</p>
"""

    html = _email_wrap(f'Orden #{o.id} rechazada - {brand}', body)

    text = (
        f"Orden rechazada\n\n"
        f"Tu orden #{o.id} no pudo ser procesada.\n"
        + (f"Motivo: {reason_text}\n" if reason_text else "")
        + f"Juego: {juego}\nPaquete: {item_t}\nMonto: {monto}\n"
        f"Referencia: {o.reference or 'N/A'}\n\n"
        f"Si crees que es un error, contactanos con tu numero de orden.\n\n- {brand}"
    )
    return html, text


# ──────────────────────────────────────────────────────────────────────
# ADMIN - notificacion de nueva orden
# ──────────────────────────────────────────────────────────────────────

def build_admin_new_order_email(o: 'Order', pkg: 'StorePackage', it: 'GamePackageItem'):
    s = _email_style()
    brand = _email_brand()
    monto = f"{o.amount} {o.currency}"
    juego = (pkg.name if pkg else '').strip()
    item_t = (it.title if it else 'N/A')

    items_html, qty_total = _email_items_rows(o)

    body = f"""
<h2 style="margin:0 0 8px 0; font-size:20px; color:{s['white']};">Nueva orden recibida</h2>
<p style="margin:0 0 20px 0; font-size:15px; color:{s['text']}; line-height:1.6;">
    Se ha registrado una nueva orden <strong style="color:{s['accent_light']};">#{o.id}</strong>
    que requiere tu atencion.
</p>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;">
{_email_detail_row('Orden', f'#{o.id}')}
{_email_detail_row('Juego', juego or 'N/A')}
{items_html if items_html else _email_detail_row('Paquete', item_t)}
{_email_detail_row('Monto', monto, s['accent_light'])}
{_email_detail_row('Metodo', (o.method or '').upper())}
{_email_detail_row('Referencia', o.reference or 'N/A')}
{_email_detail_row('Email cliente', o.email or 'N/A')}
{_email_detail_row('Telefono', o.phone or 'N/A')}
{_email_detail_row('ID Jugador', o.customer_id or 'N/A') if o.customer_id else ''}
{_email_detail_row('Nickname', o.customer_name or 'N/A') if o.customer_name else ''}
{_email_detail_row('Zona ID', o.customer_zone) if o.customer_zone else ''}
{_email_detail_row('Codigo afiliado', o.special_code) if o.special_code else ''}
</table>

<div style="margin-top:24px; text-align:center;">
    <p style="margin:0; font-size:14px; color:{s['muted']};">Ingresa al panel de administracion para procesar esta orden.</p>
</div>
"""

    html = _email_wrap(f'Nueva orden #{o.id} - {brand}', body)

    text = (
        f"Nueva orden recibida\n\n"
        f"Orden: #{o.id}\nJuego: {juego}\nPaquete: {item_t}\n"
        f"Monto: {monto}\nMetodo: {(o.method or '').upper()}\n"
        f"Referencia: {o.reference or 'N/A'}\nEmail: {o.email or 'N/A'}\n"
        + (f"Jugador: {o.customer_name or o.customer_id}\n" if o.customer_id else "")
        + (f"Codigo afiliado: {o.special_code}\n" if o.special_code else "")
        + f"\nIngresa al panel de administracion para procesar esta orden.\n\n- {brand}"
    )
    return html, text


def amount_to_usd(amount: float, currency: str) -> float:
    """Convert a numeric amount to USD using configured exchange rate when currency is local.

    Currently the store supports BsD as local currency using the key
    "exchange_rate_bsd_per_usd". If the currency is already USD or the
    rate is missing/invalid, the amount is returned as-is.
    """
    try:
        amt = float(amount or 0.0)
    except Exception:
        amt = 0.0
    cur = (currency or "USD").upper()
    if cur == "USD":
        return amt
    # Treat any non-USD as local (BsD/VES) and use configured rate
    try:
        rate_str = get_config_value("exchange_rate_bsd_per_usd", "0")
        rate = float(rate_str or 0.0)
    except Exception:
        rate = 0.0
    if rate <= 0:
        return 0.0
    return round(amt / rate, 2)


def get_stats_period_bounds(for_dt: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the weekly stats window [start, end) in naive UTC."""
    if for_dt is None:
        ve_now = now_ve()
    else:
        base_dt = for_dt
        if base_dt.tzinfo is None:
            base_dt = base_dt.replace(tzinfo=timezone.utc)
        ve_now = base_dt.astimezone(VE_TIMEZONE)

    days_since_sunday = (ve_now.weekday() - 6) % 7
    ve_candidate = ve_now.replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=days_since_sunday)
    if ve_now < ve_candidate:
        ve_candidate = ve_candidate - timedelta(days=7)

    utc_start = ve_candidate.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = (ve_candidate + timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
    return utc_start, utc_end


def get_stats_reset_cutoff() -> datetime:
    """Return the datetime (naive, UTC) of the last weekly reset at 17:00 VET (GMT-4).

    Regla de negocio: el corte semanal es el domingo a las 17:00 hora de Venezuela.
    Para comparar con columnas almacenadas como naive UTC (datetime.utcnow()),
    se convierte el corte a UTC y se retorna naive.
    """
    return get_stats_period_bounds()[0]


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
    # independent description for special items (shown in 'Leer')
    special_description = db.Column(db.Text, default="")
    # whether this game requires an extra Zone ID (INTEGER on PG via ALTER TABLE)
    requires_zone_id = db.Column(db.Integer, default=0)
    sort_order = db.Column(db.Integer, default=0)

class GamePackageItem(db.Model):
    __tablename__ = "game_packages"
    id = db.Column(db.Integer, primary_key=True)
    store_package_id = db.Column(db.Integer, db.ForeignKey("store_packages.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, default=0.0)
    profit_net_usd = db.Column(db.Float, default=0.0)
    # Optional small label/badge to show on the package (e.g., HOT, NEW)
    sticker = db.Column(db.String(50), default="")
    # Optional small icon shown next to the item title in details page
    icon_path = db.Column(db.String(300), default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RevendedoresCatalogItem(db.Model):
    __tablename__ = "rev_catalog_items"
    id = db.Column(db.Integer, primary_key=True)
    remote_product_id = db.Column(db.Integer, nullable=True)
    remote_product_name = db.Column(db.String(200), default="")
    remote_package_id = db.Column(db.Integer, nullable=False)
    remote_package_name = db.Column(db.String(250), default="")
    active = db.Column(db.Boolean, default=True)
    raw_json = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint("remote_product_id", "remote_package_id", name="uq_rev_product_package"),
    )


class RevendedoresItemMapping(db.Model):
    __tablename__ = "rev_item_mappings"
    id = db.Column(db.Integer, primary_key=True)
    store_package_id = db.Column(db.Integer, nullable=False)
    store_item_id = db.Column(db.Integer, unique=True, nullable=False)
    remote_product_id = db.Column(db.Integer, nullable=True)
    remote_package_id = db.Column(db.Integer, nullable=False)
    remote_label = db.Column(db.String(250), default="")
    auto_enabled = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    secondary_code = db.Column(db.String(80), unique=True, nullable=True)
    email = db.Column(db.String(200), unique=True, nullable=True)
    password_hash = db.Column(db.String(300), nullable=True)
    balance = db.Column(db.Float, default=0.0)  # earned commissions in USD
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Discount for the customer (applied to all products)
    discount_percent = db.Column(db.Float, default=0.0)  # percent discount the buyer gets
    # Commission for the affiliate (earned on each approved sale)
    commission_percent = db.Column(db.Float, default=10.0)  # percent the affiliate earns
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


class SpecialCodeUsage(db.Model):
    __tablename__ = "special_code_usages"
    id = db.Column(db.Integer, primary_key=True)
    special_user_id = db.Column(db.Integer, nullable=False)
    code = db.Column(db.String(80), nullable=False)  # normalized (lower)
    customer_id = db.Column(db.String(120), nullable=False)
    order_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint("code", "customer_id", name="uq_special_code_customer"),
    )


class ProfitSnapshot(db.Model):
    __tablename__ = "profit_snapshots"
    id = db.Column(db.Integer, primary_key=True)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    profit_usd = db.Column(db.Float, default=0.0)
    commission_usd = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def resolve_special_user_for_code(raw_code: str):
    code = (raw_code or "").strip()
    if not code:
        return None, False
    lowered = code.lower()
    su = SpecialUser.query.filter(
        db.func.lower(SpecialUser.code) == lowered,
        SpecialUser.active == True,
    ).first()
    if su:
        return su, False
    su = SpecialUser.query.filter(
        db.func.lower(SpecialUser.secondary_code) == lowered,
        SpecialUser.active == True,
    ).first()
    if su:
        return su, True
    return None, False


def _revendedores_env():
    base_url = (os.environ.get("REVENDEDORES_BASE_URL") or os.environ.get("WEBB_URL") or "").strip().rstrip("/")
    api_key = (os.environ.get("REVENDEDORES_API_KEY") or os.environ.get("WEBB_API_KEY") or "").strip()
    catalog_path = "/api/v1/products"
    recharge_path = "/api/v1/recharge"
    return base_url, api_key, catalog_path, recharge_path


def _synthetic_product_id(label):
    txt = str(label or "").strip().lower()
    if not txt:
        return None
    return 900000000 + (zlib.crc32(txt.encode("utf-8")) % 99999999)


def _normalize_rev_catalog_payload(payload):
    """Normaliza la respuesta de /api/v1/products (API marca blanca).

    Formato esperado:
    {
      "ok": true,
      "games": [
        {
          "game_id": 3, "name": "Mobile Legends", "mode": "id",
          "packages": [
            {"package_id": 12, "name": "86 Diamonds", "price": 1.50}
          ]
        }
      ]
    }
    """
    if not isinstance(payload, dict):
        return []

    games = payload.get("games")
    if not isinstance(games, list):
        return []

    out = []
    for game in games:
        if not isinstance(game, dict):
            continue
        game_id = game.get("game_id")
        game_name = game.get("name") or game.get("slug") or ""
        game_mode = game.get("mode") or "id"
        packages = game.get("packages")
        if not isinstance(packages, list):
            continue

        try:
            product_id = int(game_id) if game_id is not None else _synthetic_product_id(game_name)
        except (ValueError, TypeError):
            product_id = _synthetic_product_id(game_name)

        for pkg in packages:
            if not isinstance(pkg, dict):
                continue
            pkg_id_raw = pkg.get("package_id") or pkg.get("id")
            try:
                package_id = int(pkg_id_raw)
            except (ValueError, TypeError):
                continue

            package_name = pkg.get("name") or pkg.get("title") or f"Paquete {package_id}"

            raw_obj = {**pkg, "game_id": game_id, "game_name": game_name, "mode": game_mode, "is_id_game": game_mode == "id"}

            out.append({
                "remote_product_id": product_id,
                "remote_product_name": str(game_name or "").strip(),
                "remote_package_id": package_id,
                "remote_package_name": str(package_name or "").strip(),
                "active": True,
                "raw_json": json.dumps(raw_obj, ensure_ascii=False),
            })

    return out




def _get_order_auto_mapping(order_obj):
    units = _build_order_auto_recharge_units(order_obj)
    if not units:
        return None
    try:
        return RevendedoresItemMapping.query.filter_by(
            store_item_id=int(units[0].get("store_item_id") or 0),
            active=True,
            auto_enabled=True,
        ).first()
    except Exception:
        return None


def _load_order_automation_state(order_obj):
    try:
        payload = json.loads(order_obj.automation_json or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_order_automation_state(order_obj, state):
    try:
        order_obj.automation_json = json.dumps(state or {}, ensure_ascii=False)
    except Exception:
        order_obj.automation_json = ""


def _get_order_item_entries(order_obj):
    entries = []
    try:
        parsed = json.loads(order_obj.items_json or "[]") if (order_obj.items_json or "").strip() else []
        if isinstance(parsed, list):
            for entry_index, ent in enumerate(parsed, start=1):
                try:
                    item_id = int(ent.get("item_id") or 0)
                except Exception:
                    item_id = 0
                if item_id <= 0:
                    continue
                try:
                    qty = max(int(ent.get("qty") or 1), 1)
                except Exception:
                    qty = 1
                entries.append({
                    "entry_index": entry_index,
                    "item_id": item_id,
                    "qty": qty,
                    "title": str(ent.get("title") or "").strip(),
                })
    except Exception:
        entries = []
    if entries:
        return entries
    try:
        if order_obj and order_obj.item_id:
            item = GamePackageItem.query.get(order_obj.item_id)
            entries.append({
                "entry_index": 1,
                "item_id": int(order_obj.item_id),
                "qty": 1,
                "title": str(item.title or "").strip() if item else "",
            })
    except Exception:
        pass
    return entries


def _get_auto_mappings_for_item_ids(item_ids):
    ids = sorted({int(x) for x in (item_ids or []) if int(x or 0) > 0})
    if not ids:
        return {}
    try:
        rows = RevendedoresItemMapping.query.filter(
            RevendedoresItemMapping.store_item_id.in_(ids),
            RevendedoresItemMapping.active == True,
            RevendedoresItemMapping.auto_enabled == True,
        ).all()
        return {int(row.store_item_id): row for row in rows}
    except Exception:
        return {}


def _legacy_auto_unit_seed(state):
    if not isinstance(state, dict) or not state:
        return None
    if state.get("success"):
        status = "completed"
    elif state.get("pending_verification"):
        status = "processing"
    elif state.get("verified_failed") or state.get("error"):
        status = "failed"
    else:
        status = "pending"
    seed = {
        "status": status,
        "external_order_id": state.get("external_order_id") or "",
        "player_name": state.get("player_name") or "",
        "reference_no": state.get("reference_no") or "",
        "error": state.get("error") or "",
    }
    return seed if any(seed.values()) else None


def _build_order_auto_recharge_units(order_obj, automation_state=None):
    state = automation_state if isinstance(automation_state, dict) else _load_order_automation_state(order_obj)
    entries = _get_order_item_entries(order_obj)
    mappings_by_item = _get_auto_mappings_for_item_ids([entry.get("item_id") for entry in entries])
    planned_units = []
    for entry in entries:
        mapping = mappings_by_item.get(int(entry.get("item_id") or 0))
        if not mapping:
            continue
        qty = max(int(entry.get("qty") or 1), 1)
        for repeat_index in range(1, qty + 1):
            planned_units.append({
                "unit_key": f"{entry.get('entry_index')}:{entry.get('item_id')}:{repeat_index}",
                "entry_index": int(entry.get("entry_index") or 0),
                "repeat_index": repeat_index,
                "store_item_id": int(entry.get("item_id") or 0),
                "title": (entry.get("title") or mapping.remote_label or "").strip(),
                "remote_product_id": mapping.remote_product_id,
                "remote_package_id": mapping.remote_package_id,
                "remote_label": (mapping.remote_label or "").strip(),
            })
    existing_units = {}
    for raw_unit in state.get("units") or []:
        if not isinstance(raw_unit, dict):
            continue
        unit_key = str(raw_unit.get("unit_key") or "").strip()
        if unit_key:
            existing_units[unit_key] = raw_unit
    legacy_seed = _legacy_auto_unit_seed(state)
    total_units = len(planned_units)
    units = []
    for index, planned in enumerate(planned_units, start=1):
        previous = existing_units.get(planned["unit_key"])
        if previous is None and legacy_seed and total_units == 1:
            previous = legacy_seed
        status = str((previous or {}).get("status") or "pending").strip().lower()
        if status not in {"pending", "processing", "completed", "failed", "not_found"}:
            status = "pending"
        default_external_order_id = f"INE-{order_obj.id}" if total_units == 1 else f"INE-{order_obj.id}-{index}"
        unit = {
            "unit_key": planned["unit_key"],
            "sequence": index,
            "entry_index": planned["entry_index"],
            "repeat_index": planned["repeat_index"],
            "store_item_id": planned["store_item_id"],
            "title": planned["title"],
            "remote_product_id": planned["remote_product_id"],
            "remote_package_id": planned["remote_package_id"],
            "remote_label": planned["remote_label"],
            "external_order_id": str((previous or {}).get("external_order_id") or default_external_order_id),
            "status": status,
            "player_name": str((previous or {}).get("player_name") or ""),
            "reference_no": str((previous or {}).get("reference_no") or ""),
            "remaining_balance": (previous or {}).get("remaining_balance"),
            "error": str((previous or {}).get("error") or ""),
            "last_attempt_at": str((previous or {}).get("last_attempt_at") or ""),
            "last_checked_at": str((previous or {}).get("last_checked_at") or ""),
        }
        units.append(unit)
    return units


def _summarize_order_auto_recharges(units):
    total_units = len(units or [])
    completed_units = sum(1 for unit in (units or []) if (unit.get("status") or "") == "completed")
    processing_units = sum(1 for unit in (units or []) if (unit.get("status") or "") == "processing")
    failed_units = sum(1 for unit in (units or []) if (unit.get("status") or "") in ("failed", "not_found"))
    pending_units = sum(1 for unit in (units or []) if (unit.get("status") or "") == "pending")
    retryable_units = failed_units + pending_units
    return {
        "total_units": total_units,
        "completed_units": completed_units,
        "processing_units": processing_units,
        "failed_units": failed_units,
        "pending_units": pending_units,
        "retryable_units": retryable_units,
    }


def _order_has_auto_recharges(order_obj):
    return _summarize_order_auto_recharges(_build_order_auto_recharge_units(order_obj)).get("total_units", 0) > 0


def _order_status_from_auto_summary(summary, fallback_status="approved"):
    total_units = int(summary.get("total_units") or 0)
    if total_units <= 0:
        return fallback_status
    if int(summary.get("completed_units") or 0) >= total_units:
        return "delivered"
    return "pending"


def _dispatch_order_auto_recharges(order_obj, *, binance_auto=False):
    state = _load_order_automation_state(order_obj)
    units = _build_order_auto_recharge_units(order_obj, state)
    summary = _summarize_order_auto_recharges(units)
    state.update({
        "source": "revendedores_api",
        "binance_auto": bool(binance_auto or state.get("binance_auto")),
        "units": units,
        "summary": summary,
    })
    if summary["total_units"] <= 0:
        _save_order_automation_state(order_obj, state)
        return {"ok": True, "summary": summary, "units": units}

    webb_url, webb_api_key, _, recharge_path = _revendedores_env()
    player_id = (order_obj.customer_id or "").strip()
    if not webb_url or not webb_api_key:
        state["error"] = "Falta configurar REVENDEDORES_BASE_URL y REVENDEDORES_API_KEY"
        state["pending_verification"] = False
        order_obj.status = "pending"
        _save_order_automation_state(order_obj, state)
        db.session.commit()
        return {
            "ok": False,
            "error": state["error"],
            "summary": summary,
            "units": units,
            "pending_verification": False,
            "order_id": order_obj.id,
        }
    if not player_id:
        state["error"] = "No se encontró ID de jugador para recarga automática"
        state["pending_verification"] = False
        order_obj.status = "pending"
        _save_order_automation_state(order_obj, state)
        db.session.commit()
        return {
            "ok": False,
            "error": state["error"],
            "summary": summary,
            "units": units,
            "pending_verification": False,
            "order_id": order_obj.id,
        }

    processing_units = [unit for unit in units if (unit.get("status") or "") == "processing"]
    if processing_units:
        summary = _summarize_order_auto_recharges(units)
        state["summary"] = summary
        state["pending_verification"] = True
        state["success"] = summary["total_units"] > 0 and summary["completed_units"] == summary["total_units"]
        order_obj.status = _order_status_from_auto_summary(summary)
        _save_order_automation_state(order_obj, state)
        db.session.commit()
        return {
            "ok": state["success"],
            "summary": summary,
            "units": units,
            "pending_verification": state["pending_verification"],
            "order_id": order_obj.id,
        }

    retryable_statuses = {"pending", "failed", "not_found"}
    last_error = ""
    while True:
        units_to_send = [unit for unit in units if (unit.get("status") or "") in retryable_statuses]
        if not units_to_send:
            break
        unit = units_to_send[0]
        payload = {
            "product_id": unit.get("remote_product_id"),
            "package_id": unit.get("remote_package_id"),
            "player_id": player_id,
            "external_order_id": unit.get("external_order_id"),
        }
        if (order_obj.customer_zone or "").strip():
            payload["player_id2"] = (order_obj.customer_zone or "").strip()
        unit["last_attempt_at"] = datetime.utcnow().isoformat()
        try:
            api_resp = _requests_lib.post(
                f"{webb_url}{recharge_path}",
                json=payload,
                headers={"X-API-Key": webb_api_key, "Content-Type": "application/json"},
                timeout=60,
            )
            try:
                api_data = api_resp.json()
            except Exception:
                api_data = {"ok": False, "error": f"Respuesta inválida HTTP {api_resp.status_code}"}
            if api_data.get("ok"):
                unit["status"] = "completed"
                unit["player_name"] = str(api_data.get("player_name") or "")
                unit["reference_no"] = str(api_data.get("reference_no") or "")
                unit["remaining_balance"] = api_data.get("remaining_balance")
                unit["error"] = ""
                last_error = ""
                continue
            else:
                unit["status"] = "processing"
                unit["error"] = str(api_data.get("error") or "Recarga no completada en Revendedores")
                last_error = unit["error"]
                break
        except _requests_lib.exceptions.Timeout:
            unit["status"] = "processing"
            unit["error"] = "Revendedores no respondió en 60 segundos"
            last_error = unit["error"]
            break
        except Exception as exc:
            unit["status"] = "processing"
            unit["error"] = str(exc)
            last_error = unit["error"]
            break

    summary = _summarize_order_auto_recharges(units)
    state["units"] = units
    state["summary"] = summary
    state["pending_verification"] = summary["processing_units"] > 0
    state["success"] = summary["total_units"] > 0 and summary["completed_units"] == summary["total_units"]
    state["last_attempt_at"] = datetime.utcnow().isoformat()
    if last_error:
        state["error"] = last_error
    elif summary["processing_units"] <= 0 and summary["retryable_units"] <= 0 and state.get("error"):
        state.pop("error", None)
    order_obj.status = _order_status_from_auto_summary(summary)
    _save_order_automation_state(order_obj, state)
    db.session.commit()
    return {
        "ok": state["success"],
        "summary": summary,
        "units": units,
        "error": state.get("error") or "",
        "pending_verification": state["pending_verification"],
        "order_id": order_obj.id,
    }

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="")
    email = db.Column(db.String(200), unique=True, nullable=False)
    phone = db.Column(db.String(80), default="")
    password_hash = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PasswordResetCode(db.Model):
    __tablename__ = "password_reset_codes"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False, index=True)
    code_hash = db.Column(db.String(300), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Customer ID blocks
class BlockedCustomer(db.Model):
    __tablename__ = "blocked_customers"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.String(200), nullable=False)
    reason = db.Column(db.String(300), default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize
with app.app_context():
    db.create_all()
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    # Ensure legacy DB gets the new 'category' column (SQLite runtime migration)
    try:
        from sqlalchemy import text
        _is_pg = db.engine.dialect.name == "postgresql"

        def _get_table_cols(table):
            """Return set of column names for *table*, works on both SQLite and PostgreSQL."""
            if _is_pg:
                rows = db.session.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
                    {"t": table},
                ).fetchall()
                return {row[0] for row in rows}
            else:
                rows = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
                return {row[1] for row in rows}

        cols = _get_table_cols("store_packages")
        if "category" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN category TEXT DEFAULT 'mobile'"))
            db.session.commit()
        if "description" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN description TEXT DEFAULT ''"))
            db.session.commit()
        # new: independent special_description used by 'Leer' for special items
        if "special_description" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN special_description TEXT DEFAULT ''"))
            db.session.commit()
        if "requires_zone_id" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN requires_zone_id INTEGER DEFAULT 0"))
            db.session.commit()
        if "sort_order" not in cols:
            db.session.execute(text("ALTER TABLE store_packages ADD COLUMN sort_order INTEGER DEFAULT 0"))
            db.session.commit()
        # Orders table migration: add missing columns if an older schema exists
        order_cols = _get_table_cols("orders")
        def add_order_col(name, ddl):
            if name not in order_cols:
                db.session.execute(text(f"ALTER TABLE orders ADD COLUMN {ddl}"))
        if order_cols:  # table exists
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
            add_order_col('automation_json', "automation_json TEXT DEFAULT ''")
            add_order_col('payment_capture', "payment_capture TEXT DEFAULT ''")
            db.session.commit()
        # Special users table migration: ensure new columns
        try:
            aff_cols = _get_table_cols("special_users")
            if "email" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN email TEXT"))
            if "secondary_code" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN secondary_code TEXT"))
            if "password_hash" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN password_hash TEXT"))
            if "discount_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN discount_percent REAL DEFAULT 10.0"))
            if "scope" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN scope TEXT DEFAULT 'all'"))
            if "scope_package_id" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN scope_package_id INTEGER"))
            if "commission_percent" not in aff_cols:
                db.session.execute(text("ALTER TABLE special_users ADD COLUMN commission_percent REAL DEFAULT 10.0"))
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
            wd_cols = _get_table_cols("affiliate_withdrawals")
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
        _is_pg2 = db.engine.dialect.name == "postgresql"
        if _is_pg2:
            _gp_rows = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'game_packages'")).fetchall()
            gp_cols = {row[0] for row in _gp_rows}
        else:
            gp_cols = {row[1] for row in db.session.execute(text("PRAGMA table_info(game_packages)")).fetchall()}
        if "sticker" not in gp_cols:
            db.session.execute(text("ALTER TABLE game_packages ADD COLUMN sticker TEXT DEFAULT ''"))
            db.session.commit()
        if "icon_path" not in gp_cols:
            db.session.execute(text("ALTER TABLE game_packages ADD COLUMN icon_path TEXT DEFAULT ''"))
            db.session.commit()
        if "profit_net_usd" not in gp_cols:
            db.session.execute(text("ALTER TABLE game_packages ADD COLUMN profit_net_usd REAL DEFAULT 0.0"))
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
            {"id": u.id, "name": u.name, "code": u.code, "secondary_code": u.secondary_code or "", "email": u.email or "", "balance": float(u.balance or 0.0), "active": bool(u.active),
             "discount_percent": float(u.discount_percent or 0.0),
             "commission_percent": float(u.commission_percent or 0.0),
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
    secondary_code = (data.get("secondary_code") or "").strip()
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
    if secondary_code:
        if SpecialUser.query.filter(db.func.lower(SpecialUser.code) == secondary_code.lower()).first():
            return jsonify({"ok": False, "error": "El código adicional ya está en uso"}), 400
        if SpecialUser.query.filter(db.func.lower(SpecialUser.secondary_code) == secondary_code.lower()).first():
            return jsonify({"ok": False, "error": "El código adicional ya existe"}), 400
        if secondary_code.lower() == code.lower():
            return jsonify({"ok": False, "error": "El código adicional debe ser diferente al principal"}), 400
    if email:
        if SpecialUser.query.filter(db.func.lower(SpecialUser.email) == email.lower()).first():
            return jsonify({"ok": False, "error": "Email ya existe"}), 400
    # Optional extended fields
    def fget(key, default=0.0):
        try:
            return float(data.get(key) or default)
        except Exception:
            return default
    su = SpecialUser(name=name, code=code, secondary_code=secondary_code or None, email=email or None, active=bool(data.get("active", True)), balance=float(data.get("balance") or 0.0),
                     discount_percent=discount_percent,
                     commission_percent=fget("commission_percent", 10.0),
                     scope=scope if scope in ("all","package") else "all", scope_package_id=scope_package_id)
    if password:
        su.password_hash = generate_password_hash(password)
    db.session.add(su)
    db.session.commit()
    return jsonify({"ok": True, "user": {"id": su.id, "name": su.name, "code": su.code, "secondary_code": su.secondary_code or "", "email": su.email or "", "balance": su.balance, "active": su.active,
            "discount_percent": su.discount_percent,
            "commission_percent": su.commission_percent,
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
            if SpecialUser.query.filter(db.func.lower(SpecialUser.secondary_code) == new_code.lower()).first():
                return jsonify({"ok": False, "error": "El código ya está en uso como código adicional"}), 400
            su.code = new_code
    if "secondary_code" in data:
        new_secondary = (data.get("secondary_code") or '').strip()
        if not new_secondary:
            su.secondary_code = None
        else:
            if new_secondary.lower() == (su.code or '').lower():
                return jsonify({"ok": False, "error": "El código adicional debe ser diferente al principal"}), 400
            current_secondary = (su.secondary_code or '').lower()
            if new_secondary.lower() != current_secondary:
                if SpecialUser.query.filter(db.func.lower(SpecialUser.code) == new_secondary.lower()).first():
                    return jsonify({"ok": False, "error": "El código adicional ya está en uso"}), 400
                if SpecialUser.query.filter(db.func.lower(SpecialUser.secondary_code) == new_secondary.lower()).first():
                    return jsonify({"ok": False, "error": "El código adicional ya existe"}), 400
            su.secondary_code = new_secondary
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
    # Commission percent
    if "commission_percent" in data:
        try:
            su.commission_percent = float(data.get("commission_percent") or 0.0)
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
        r.processed_at = now_ve()
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
        r.processed_at = now_ve()
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
    customer_id = (request.args.get("customer_id") or request.args.get("cid") or '').strip()
    gid_raw = request.args.get("gid")
    try:
        gid = int(gid_raw) if gid_raw is not None and f"{gid_raw}" != '' else None
    except Exception:
        gid = None
    if not code:
        return jsonify({"ok": False, "error": "Código vacío"}), 400
    su, is_secondary_code = resolve_special_user_for_code(code)
    if not su:
        return jsonify({"ok": False, "error": "Código inválido"}), 404
    # Enforce scope if restricted to a package
    if (su.scope or 'all') == 'package':
        if not gid or (su.scope_package_id and su.scope_package_id != gid):
            return jsonify({"ok": False, "error": "El código no aplica a este juego"}), 400
    if is_secondary_code:
        if not customer_id:
            return jsonify({"ok": False, "error": "Debes ingresar el ID del jugador para usar este código"}), 400
        used = SpecialCodeUsage.query.filter(
            SpecialCodeUsage.code == code.lower(),
            db.func.lower(SpecialCodeUsage.customer_id) == customer_id.lower(),
        ).first()
        if used:
            return jsonify({"ok": False, "error": "Este código adicional ya fue usado por este ID de jugador"}), 400
        return jsonify({"ok": True, "allowed": True, "discount": 0.10, "one_time": True})

    # Simple flat discount for all products
    disc = float(su.discount_percent or 0.0)
    resp = {"ok": True, "allowed": True, "discount": round(disc/100.0, 4)}
    return jsonify(resp)

# Routes
@app.route("/")
def index():
    """Public storefront index page with header and configurable logo."""
    logo_url = get_config_value("logo_path", "")
    banner_url = get_config_value("mid_banner_path", "")
    site_name = get_config_value("site_name", "InefableStore")
    return render_template("index.html", logo_url=logo_url, banner_url=banner_url, site_name=site_name)

@app.route("/terms")
def terms_page():
    site_name = get_config_value("site_name", "InefableStore")
    return render_template("terms.html", site_name=site_name)

@app.route("/user")
def user_page():
    u = session.get("user") or {}
    role = u.get("role")
    is_admin = (role == "admin")
    is_affiliate = (role == "affiliate")
    logo_url = get_config_value("logo_path", "")
    site_name = get_config_value("site_name", "InefableStore")
    return render_template("user.html", is_admin=is_admin, is_affiliate=is_affiliate, logo_url=logo_url, site_name=site_name)

@app.route("/admin")
def admin_page():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return redirect("/?next=/admin")
    site_name = get_config_value("site_name", "InefableStore")
    return render_template("admin.html", site_name=site_name, body_class="theme-admin-dark")

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
        "binance_auto_enabled": get_config_value("binance_auto_enabled", "0"),
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


@app.route("/admin/config/site_name", methods=["GET"])
def admin_config_site_name_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "site_name": get_config_value("site_name", "InefableStore")})


@app.route("/admin/config/site_name", methods=["POST"])
def admin_config_site_name_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    site_name = (data.get("site_name") or "").strip()
    if not site_name:
        return jsonify({"ok": False, "error": "El nombre del sitio no puede estar vacío"}), 400
    set_config_value("site_name", site_name)
    return jsonify({"ok": True, "site_name": site_name})


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


@app.route("/admin/config/thanks_image", methods=["GET"])
def admin_config_thanks_image_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "thanks_image_path": get_config_value("thanks_image_path", "")})


@app.route("/admin/config/thanks_image", methods=["POST"])
def admin_config_thanks_image_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    set_config_value("thanks_image_path", (data.get("thanks_image_path") or "").strip())
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
        "binance_auto_enabled": get_config_value("binance_auto_enabled", "0"),
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
    set_config_value("binance_auto_enabled", "1" if data.get("binance_auto_enabled") else "0")
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


@app.route("/admin/config/bs_package_id", methods=["GET"])
def admin_config_bs_package_id_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "bs_package_id": get_config_value("bs_package_id", "")})


@app.route("/admin/config/bs_package_id", methods=["POST"])
def admin_config_bs_package_id_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    val = (data.get("bs_package_id") or "").strip()
    set_config_value("bs_package_id", val)
    return jsonify({"ok": True, "bs_package_id": val})


@app.route("/admin/config/bs_server_id", methods=["GET"])
def admin_config_bs_server_id_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "bs_server_id": get_config_value("bs_server_id", "-1")})


@app.route("/admin/config/bs_server_id", methods=["POST"])
def admin_config_bs_server_id_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    val = (data.get("bs_server_id") or "").strip()
    set_config_value("bs_server_id", val)
    return jsonify({"ok": True, "bs_server_id": val})


@app.route("/admin/config/ml_package_id", methods=["GET"])
def admin_config_ml_package_id_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "ml_package_id": get_config_value("ml_package_id", "")})


@app.route("/admin/config/ml_package_id", methods=["POST"])
def admin_config_ml_package_id_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    val = (data.get("ml_package_id") or "").strip()
    set_config_value("ml_package_id", val)
    return jsonify({"ok": True, "ml_package_id": val})


@app.route("/admin/config/ml_smile_pid", methods=["GET"])
def admin_config_ml_smile_pid_get():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return jsonify({"ok": True, "ml_smile_pid": get_config_value("ml_smile_pid", "")})


@app.route("/admin/config/ml_smile_pid", methods=["POST"])
def admin_config_ml_smile_pid_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    val = (data.get("ml_smile_pid") or "").strip()
    set_config_value("ml_smile_pid", val)
    return jsonify({"ok": True, "ml_smile_pid": val})


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_capture(file) -> str:
    """Save a payment capture image to captures/ subfolder. Returns relative path."""
    if not file or not file.filename:
        return ""
    if not _allowed_file(file.filename):
        return ""
    fname = secure_filename(file.filename)
    ts = now_ve().strftime("%Y%m%d%H%M%S%f")
    fname = f"{ts}_{fname}"
    folder = os.path.join(app.config["UPLOAD_FOLDER"], "captures")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        pass
    file.save(os.path.join(folder, fname))
    return "captures/" + fname


def _delete_capture(relative_path: str):
    """Delete a payment capture file from disk if it exists."""
    if not relative_path:
        return
    try:
        fpath = os.path.join(app.config["UPLOAD_FOLDER"], relative_path)
        if os.path.exists(fpath):
            os.remove(fpath)
    except Exception:
        pass


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
    ts = now_ve().strftime("%Y%m%d%H%M%S%f")
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
    """Public: Top packages por ventas exitosas.

    Suma órdenes activas y órdenes históricas agregadas en OrderSummary para que
    la sección siga mostrando acumulado aunque la limpieza automática archive
    pedidos viejos fuera de la tabla orders.
    """
    successful_statuses = ["approved", "delivered"]
    sales_by_package = {}

    live_counts = (
        db.session.query(Order.store_package_id, db.func.count(Order.id).label("cnt"))
        .filter(Order.status.in_(successful_statuses))
        .group_by(Order.store_package_id)
        .all()
    )
    for package_id, count in live_counts:
        if package_id is None:
            continue
        sales_by_package[int(package_id)] = sales_by_package.get(int(package_id), 0) + int(count or 0)

    archived_counts = (
        db.session.query(
            OrderSummary.store_package_id,
            db.func.coalesce(db.func.sum(OrderSummary.order_count), 0).label("cnt"),
        )
        .filter(OrderSummary.status.in_(successful_statuses))
        .group_by(OrderSummary.store_package_id)
        .all()
    )
    for package_id, count in archived_counts:
        if package_id is None:
            continue
        sales_by_package[int(package_id)] = sales_by_package.get(int(package_id), 0) + int(count or 0)

    ids = [package_id for package_id, _ in sorted(sales_by_package.items(), key=lambda entry: entry[1], reverse=True)[:12]]
    if not ids:
        # No approved sales yet -> return a stable fallback list so the homepage
        # section doesn't appear to "disappear".
        try:
            items = (
                StorePackage.query
                .filter(StorePackage.active == True)
                .order_by(StorePackage.sort_order.asc(), StorePackage.created_at.desc())
                .limit(12)
                .all()
            )
        except Exception:
            items = (
                StorePackage.query
                .filter(StorePackage.active == True)
                .order_by(StorePackage.created_at.desc())
                .limit(12)
                .all()
            )
        return jsonify({
            "packages": [
                {"id": p.id, "name": p.name, "image_path": p.image_path, "category": (p.category or 'mobile')}
                for p in items
            ]
        })
    # Fetch active package rows preserving ranking by total successful sales.
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
    bs_package_id = get_config_value("bs_package_id", "")
    ml_package_id = get_config_value("ml_package_id", "")
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
        related = rel_q.limit(4).all()
    except Exception:
        related = []
    site_name = get_config_value("site_name", "InefableStore")
    return render_template(
        "details.html",
        game=game,
        logo_url=logo_url,
        site_name=site_name,
        active_login_game_id=active_login_game_id,
        bs_package_id=bs_package_id,
        ml_package_id=ml_package_id,
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
    site_name = get_config_value("site_name", "InefableStore")
    whatsapp_url = get_config_value("whatsapp_url", "https://api.whatsapp.com/send?phone=%2B584125712917")
    return render_template(
        "checkout.html",
        gid=gid,
        logo_url=logo_url,
        site_name=site_name,
        whatsapp_url=whatsapp_url,
        game_name=game.name,
        game_image=game.image_path,
    )


@app.route("/gracias/<int:oid>")
def thanks_order(oid: int):
    """Simple thank-you page after placing an order."""
    try:
        logo_url = get_config_value("logo_path", "")
        site_name = get_config_value("site_name", "InefableStore")
    except Exception:
        logo_url = ""
        site_name = "InefableStore"
    return render_template("thanks.html", order_id=oid, logo_url=logo_url, site_name=site_name)


# ===============
# Orders API
# ===============

def _generate_binance_auto_code():
    """Generate a unique 6-character alphanumeric code for Binance auto-verification.

    The code is uppercase letters + digits, e.g. 'A3K7B2'. Retries until unique
    among pending orders.
    """
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    for _ in range(50):
        code = ''.join(random.choices(chars, k=6))
        existing = Order.query.filter(
            Order.reference == code,
            Order.status == "pending",
        ).first()
        if not existing:
            return code
    # Fallback: use secrets for extra entropy
    return secrets.token_hex(3).upper()[:6]


@app.route("/store/item/<int:item_id>/auto-check", methods=["GET"])
def store_item_auto_check(item_id):
    """Public: check if a specific item has auto_enabled in RevendedoresItemMapping."""
    enabled = get_config_value("binance_auto_enabled", "0")
    if enabled != "1":
        return jsonify({"ok": True, "auto": False})
    mapping = RevendedoresItemMapping.query.filter_by(
        store_item_id=item_id, active=True, auto_enabled=True
    ).first()
    return jsonify({"ok": True, "auto": mapping is not None})


@app.route("/orders/generate-binance-code", methods=["GET"])
def generate_binance_code():
    """Public: generate a unique 6-char code for Binance auto-verification checkout."""
    enabled = get_config_value("binance_auto_enabled", "0")
    if enabled != "1":
        return jsonify({"ok": False, "error": "Verificación automática no activa"}), 400
    code = _generate_binance_auto_code()
    return jsonify({"ok": True, "code": code})


@app.route("/orders/check-reference", methods=["GET"])
def check_reference():
    """Check if a reference is already in use by a pending order"""
    reference = request.args.get("reference", "").strip()
    if not reference:
        return jsonify({"ok": False, "error": "Referencia requerida"}), 400
    
    # Check if reference exists in pending orders only
    existing = Order.query.filter(
        Order.reference == reference,
        Order.status == "pending"
    ).first()
    
    if existing:
        return jsonify({
            "ok": True,
            "exists": True,
            "message": "Su referencia ya fue subida y su recarga está siendo procesada"
        })
    
    return jsonify({"ok": True, "exists": False})

@app.route("/orders", methods=["POST"])
def create_order():
    try:
        # Support both JSON (legacy) and multipart/form-data (with file upload)
        content_type = request.content_type or ""
        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            data = request.form
            def _get(key, default=""):
                return (data.get(key) or default)
        else:
            data = request.get_json(silent=True) or {}
            def _get(key, default=""):
                return (data.get(key) or default)

        gid_raw = _get("store_package_id")
        if not gid_raw:
            return jsonify({"ok": False, "error": "store_package_id requerido"}), 400
        gid = int(gid_raw)
        item_id = _get("item_id") or None
        if item_id is not None:
            try:
                item_id = int(item_id)
            except Exception:
                item_id = None
        method = _get("method").strip()
        currency = (_get("currency") or "USD").strip()
        try:
            amount = float(_get("amount") or 0)
        except Exception:
            amount = 0.0
        reference = _get("reference").strip()
        name = _get("name").strip()
        email = _get("email").strip()
        phone = _get("phone").strip()
        customer_id = _get("customer_id").strip()
        customer_zone = _get("customer_zone").strip()
        special_code = _get("special_code").strip()
        verified_nick = _get("nn").strip()

        if not email:
            return jsonify({"ok": False, "error": "Correo requerido"}), 400

        if customer_id and not customer_id.isdigit():
            return jsonify({"ok": False, "error": "El ID de jugador debe ser numérico"}), 400

        if customer_zone and not customer_zone.isdigit():
            return jsonify({"ok": False, "error": "La Zona ID debe ser numérica"}), 400

        ml_package_id = (get_config_value("ml_package_id", "") or "").strip()
        if ml_package_id and str(gid) == ml_package_id and not customer_zone:
            return jsonify({"ok": False, "error": "La Zona ID es requerida para este juego"}), 400

        # Blocklist check for player IDs
        try:
            if customer_id:
                blk = BlockedCustomer.query.filter(
                    db.func.lower(BlockedCustomer.customer_id) == customer_id.lower(),
                    BlockedCustomer.active == True
                ).first()
                if blk:
                    return jsonify({"ok": False, "error": "Este ID de jugador está bloqueado. Contacta soporte"}), 403
        except Exception:
            pass

        if not reference:
            return jsonify({"ok": False, "error": "Referencia requerida"}), 400
        # Determine if this is a Binance auto-verification order (6-char alphanumeric code)
        _is_binance_auto = (
            method == "binance"
            and get_config_value("binance_auto_enabled", "0") == "1"
            and len(reference) == 6
            and reference.isalnum()
        )
        if _is_binance_auto:
            # Validate alphanumeric code format
            if not reference.isalnum() or len(reference) != 6:
                return jsonify({"ok": False, "error": "Código de verificación inválido"}), 400
        else:
            # Normal flow: validate reference is numeric with maximum 21 digits (1..21)
            if not (reference.isdigit() and 1 <= len(reference) <= 21):
                return jsonify({"ok": False, "error": "La referencia debe ser numérica (máximo 21 dígitos)"}), 400
        # Check if reference already exists in pending orders
        existing_pending = Order.query.filter(
            Order.reference == reference,
            Order.status == "pending"
        ).first()
        if existing_pending:
            return jsonify({"ok": False, "error": "Su referencia ya fue subida y su recarga está siendo procesada"}), 400
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
            customer_name=verified_nick or name or email or customer_id,
            status="pending",
            special_code=special_code,
        )
        # If client sent multiple items, store them in items_json
        # Apply influencer discount if special_code provided
        discount_fraction = 0.0
        used_secondary_code = False
        normalized_secondary_code = ""
        if special_code:
            try:
                su, is_secondary_code = resolve_special_user_for_code(special_code)
                if su:
                    if is_secondary_code:
                        if not customer_id:
                            return jsonify({"ok": False, "error": "El código adicional requiere ID de jugador"}), 400
                        already_used = SpecialCodeUsage.query.filter(
                            SpecialCodeUsage.code == special_code.lower(),
                            db.func.lower(SpecialCodeUsage.customer_id) == customer_id.lower(),
                        ).first()
                        if already_used:
                            return jsonify({"ok": False, "error": "Este código adicional ya fue usado por este ID de jugador"}), 400
                        discount_fraction = 0.10
                        used_secondary_code = True
                        normalized_secondary_code = special_code.lower()
                    else:
                        discount_fraction = float(su.discount_percent or 0.0) / 100.0
            except Exception:
                pass
        
        order_total_usd = amount_to_usd(amount, currency)

        try:
            raw_items = data.get("items")
            # When sent as form data, items is a JSON-encoded string
            if isinstance(raw_items, str):
                try:
                    raw_items = json.loads(raw_items)
                except Exception:
                    raw_items = []
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
                    
                    # Calculate actual price with discount if applicable
                    base_price = float(gi.price or 0.0)
                    actual_price = base_price * (1.0 - discount_fraction)
                    
                    items_list.append({
                        "item_id": gi.id,
                        "qty": qty,
                        "title": gi.title,
                        "price": round(actual_price, 2),  # Guardar precio con descuento aplicado
                        "cost_unit_usd": float(gi.profit_net_usd or 0.0),
                    })
            if (not items_list) and item_id:
                gi = GamePackageItem.query.get(item_id)
                if gi:
                    qty = 1
                    base_price = float(gi.price or 0.0)
                    actual_price = base_price * (1.0 - discount_fraction)
                    items_list.append({
                        "item_id": gi.id,
                        "qty": qty,
                        "title": gi.title,
                        "price": round(actual_price, 2),
                        "cost_unit_usd": float(gi.profit_net_usd or 0.0),
                    })
            if items_list:
                o.items_json = json.dumps(items_list)
                order_total_usd = round(sum(float(ent.get("price") or 0.0) * max(int(ent.get("qty") or 1), 1) for ent in items_list), 2)
        except Exception:
            pass
        o.price = round(float(order_total_usd or 0.0), 2)
        # Try to resolve special user id now for convenience
        try:
            if special_code:
                su, _ = resolve_special_user_for_code(special_code)
                if su:
                    o.special_user_id = su.id
        except Exception:
            pass
        db.session.add(o)
        db.session.flush()
        if used_secondary_code and o.special_user_id and customer_id:
            db.session.add(SpecialCodeUsage(
                special_user_id=o.special_user_id,
                code=normalized_secondary_code,
                customer_id=customer_id,
                order_id=o.id,
            ))
        # Save payment capture image if provided
        try:
            capture_file = request.files.get("payment_capture")
            if capture_file and capture_file.filename:
                capture_path = _save_capture(capture_file)
                if capture_path:
                    o.payment_capture = capture_path
        except Exception:
            pass
        db.session.commit()
        # Notify admin by email about new pending order (HTML)
        try:
            to_addr = get_config_value("admin_notify_email", ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL)
            pkg = StorePackage.query.get(o.store_package_id)
            it = GamePackageItem.query.get(o.item_id) if o.item_id else None
            admin_html, admin_text = build_admin_new_order_email(o, pkg, it)
            brand = _email_brand()
            try:
                send_email_html(to_addr, f"[{brand}] Nueva orden #{o.id}", admin_html, admin_text)
            except Exception:
                send_email(to_addr, f"Nueva orden #{o.id} pendiente", admin_text)
        except Exception:
            pass
        # Notify customer that order was received (HTML)
        try:
            if o.email:
                pkg = pkg if 'pkg' in dir() else StorePackage.query.get(o.store_package_id)
                it = it if 'it' in dir() else (GamePackageItem.query.get(o.item_id) if o.item_id else None)
                cust_html, cust_text = build_order_created_email(o, pkg, it)
                brand = _email_brand()
                try:
                    send_email_html(o.email, f"Orden #{o.id} recibida - {brand}", cust_html, cust_text)
                except Exception:
                    send_email_async(o.email, f"Orden #{o.id} recibida - {brand}", cust_text)
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
                to_purge = del_q.all()
                for op in to_purge:
                    _delete_capture(op.payment_capture)
                    db.session.delete(op)
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
        auto_summary = _summarize_order_auto_recharges(_build_order_auto_recharge_units(x))
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
            "is_auto_mapped": bool(auto_summary.get("total_units")),
            "auto_recharge_summary": auto_summary,
            "items": items_payload,
            "customer_id": x.customer_id,
            "customer_zone": x.customer_zone or "",
            "customer_name": x.customer_name or "",
            "name": x.name,
            "email": x.email,
            "phone": x.phone,
            "method": x.method,
            "currency": x.currency,
            "amount": x.amount,
            "reference": x.reference,
            "delivery_code": x.delivery_code or "",
            "delivery_codes": delivery_codes,
            "payment_capture": x.payment_capture or "",
            "payment_capture_url": (
                f"{app.config.get('UPLOAD_URL_PREFIX', '/static/uploads').rstrip('/')}/{x.payment_capture}"
                if x.payment_capture else ""
            ),
        })
    return jsonify({"ok": True, "orders": out})


# ==============================
# Blocked Customers (Player IDs) API
# ==============================

@app.route("/admin/blocked-customers", methods=["GET"])
def admin_blocked_customers_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    rows = BlockedCustomer.query.order_by(BlockedCustomer.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "blocked": [
            {
                "id": r.id,
                "customer_id": r.customer_id,
                "reason": r.reason or "",
                "active": bool(r.active),
                "created_at": (r.created_at.isoformat() if r.created_at else "")
            }
            for r in rows
        ]
    })

@app.route("/admin/blocked-customers", methods=["POST"])
def admin_blocked_customers_create():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    customer_id = (data.get("customer_id") or "").strip()
    reason = (data.get("reason") or "").strip()
    if not customer_id:
        return jsonify({"ok": False, "error": "customer_id requerido"}), 400
    # Avoid duplicates (case-insensitive)
    existing = BlockedCustomer.query.filter(db.func.lower(BlockedCustomer.customer_id) == customer_id.lower()).first()
    if existing:
        # If exists, update fields instead of creating a duplicate
        existing.reason = reason or existing.reason
        existing.active = bool(data.get("active", True))
        db.session.commit()
        return jsonify({"ok": True, "blocked": {"id": existing.id, "customer_id": existing.customer_id, "reason": existing.reason or "", "active": bool(existing.active)}})
    row = BlockedCustomer(customer_id=customer_id, reason=reason, active=bool(data.get("active", True)))
    db.session.add(row)
    db.session.commit()
    return jsonify({"ok": True, "blocked": {"id": row.id, "customer_id": row.customer_id, "reason": row.reason or "", "active": bool(row.active)}})

@app.route("/admin/blocked-customers/<int:bid>", methods=["PATCH", "PUT"])
def admin_blocked_customers_update(bid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    row = BlockedCustomer.query.get(bid)
    if not row:
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    if "customer_id" in data and str(data.get("customer_id") or "").strip():
        row.customer_id = str(data.get("customer_id")).strip()
    if "reason" in data:
        row.reason = (data.get("reason") or "").strip()
    if "active" in data:
        row.active = bool(data.get("active"))
    db.session.commit()
    return jsonify({"ok": True, "blocked": {"id": row.id, "customer_id": row.customer_id, "reason": row.reason or "", "active": bool(row.active)}})

@app.route("/admin/blocked-customers/<int:bid>", methods=["DELETE"])
def admin_blocked_customers_delete(bid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    row = BlockedCustomer.query.get(bid)
    if not row:
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True})

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
                    comm_pct = float(su.commission_percent or 0.0)
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
            brand = _email_brand()
            if to_addr:
                html, text = build_order_approved_email(o, pkg, it)
                try:
                    send_email_html(to_addr, f"Orden #{o.id} aprobada - {brand}", html, text)
                except Exception:
                    send_email_async(to_addr, f"Orden #{o.id} aprobada - {brand}", text)
    except Exception:
        pass
    # Notify buyer on rejection (HTML email)
    try:
        if status == "rejected" and o.email:
            pkg = StorePackage.query.get(o.store_package_id)
            it = GamePackageItem.query.get(o.item_id) if o.item_id else None
            reason = (data.get("reason") or "").strip()
            brand = _email_brand()
            html, text = build_order_rejected_email(o, pkg, it, reason=reason)
            try:
                send_email_html(o.email, f"Orden #{o.id} rechazada - {brand}", html, text)
            except Exception:
                send_email_async(o.email, f"Orden #{o.id} rechazada - {brand}", text)
    except Exception:
        pass

    # ── Auto-recarga vía API marca blanca de Revendedores ──
    auto_dispatch = None
    try:
        if status == "approved" and o.status in ("approved", "delivered") and _order_has_auto_recharges(o):
            auto_dispatch = _dispatch_order_auto_recharges(o)
    except Exception as exc:
        auto_dispatch = {
            "ok": False,
            "error": str(exc),
            "pending_verification": False,
            "order_id": o.id,
            "summary": _summarize_order_auto_recharges(_build_order_auto_recharge_units(o)),
        }

    response_payload = {"ok": True}
    if auto_dispatch and auto_dispatch.get("summary", {}).get("total_units"):
        response_payload["webb_recarga"] = {
            "ok": bool(auto_dispatch.get("ok")),
            "error": auto_dispatch.get("error") or "",
            "pending_verification": bool(auto_dispatch.get("pending_verification")),
            "order_id": o.id,
            "summary": auto_dispatch.get("summary") or {},
        }

    return jsonify(response_payload)


@app.route("/admin/orders/<int:oid>/verify-recharge", methods=["POST"])
def admin_orders_verify_recharge(oid: int):
    """Verifica en Revendedores51 si la recarga realmente se completó."""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404
    if o.status not in ("pending",):
        return jsonify({"ok": True, "result": "already_processed", "order_status": o.status})

    auto_resp = _load_order_automation_state(o)
    units = _build_order_auto_recharge_units(o, auto_resp)
    summary = _summarize_order_auto_recharges(units)

    if summary.get("total_units", 0) <= 0:
        return jsonify({"ok": True, "result": "no_verification_needed", "can_approve": True})
    if summary.get("processing_units", 0) <= 0:
        if summary.get("completed_units", 0) >= summary.get("total_units", 0):
            return jsonify({
                "ok": True,
                "result": "completed",
                "order_status": "delivered",
                "summary": summary,
            })
        return jsonify({
            "ok": True,
            "result": "no_verification_needed",
            "can_approve": summary.get("retryable_units", 0) > 0,
            "summary": summary,
        })

    webb_url, webb_api_key, _, _ = _revendedores_env()

    if not webb_url or not webb_api_key:
        return jsonify({"ok": False, "error": "Revendedores API no configurada"})

    processing_units = [unit for unit in units if (unit.get("status") or "") == "processing"]
    for unit in processing_units:
        ext_order_id = unit.get("external_order_id") or f"INE-{o.id}"
        try:
            resp = _requests_lib.get(
                f"{webb_url}/api/v1/order-status",
                params={"external_order_id": ext_order_id},
                headers={"X-API-Key": webb_api_key},
                timeout=15,
            )
            data = resp.json() if resp.ok else {}
        except Exception as e:
            return jsonify({"ok": False, "error": f"No se pudo verificar: {e}", "can_approve": False})

        if not data.get("ok"):
            return jsonify({"ok": False, "error": data.get("error", "Error consultando Revendedores"), "can_approve": False})

        found = data.get("found", False)
        rev_status = str(data.get("status") or "").strip().lower()
        rev_order = data.get("order", {}) or {}
        unit["last_checked_at"] = datetime.utcnow().isoformat()
        if found and rev_status == "completada":
            unit["status"] = "completed"
            unit["player_name"] = str(rev_order.get("player_name") or unit.get("player_name") or "")
            unit["reference_no"] = str(rev_order.get("reference_no") or unit.get("reference_no") or "")
            unit["error"] = ""
        elif found and rev_status == "fallida":
            unit["status"] = "failed"
            unit["error"] = str(rev_order.get("error") or unit.get("error") or "Recarga falló en Revendedores")
        elif found and rev_status == "procesando":
            unit["status"] = "processing"
        else:
            unit["status"] = "not_found"
            unit["error"] = "No se encontró la recarga en Revendedores"

    summary = _summarize_order_auto_recharges(units)
    auto_resp.update({
        "source": "revendedores_api",
        "units": units,
        "summary": summary,
        "pending_verification": summary.get("processing_units", 0) > 0,
        "success": summary.get("total_units", 0) > 0 and summary.get("completed_units", 0) == summary.get("total_units", 0),
    })
    if summary.get("retryable_units", 0) > 0:
        auto_resp["error"] = next((str(unit.get("error") or "") for unit in units if unit.get("error")), "")
    elif auto_resp.get("error"):
        auto_resp.pop("error", None)
    o.status = _order_status_from_auto_summary(summary)
    _save_order_automation_state(o, auto_resp)
    db.session.commit()

    if summary.get("processing_units", 0) <= 0 and summary.get("pending_units", 0) > 0 and summary.get("failed_units", 0) <= 0:
        queued_result = _dispatch_order_auto_recharges(o, binance_auto=bool(auto_resp.get("binance_auto")))
        queued_summary = queued_result.get("summary") or {}
        if queued_summary.get("completed_units", 0) >= queued_summary.get("total_units", 0) and queued_summary.get("total_units", 0) > 0:
            first_completed = next((unit for unit in (queued_result.get("units") or []) if (unit.get("status") or "") == "completed"), {})
            return jsonify({
                "ok": True,
                "result": "completed",
                "order_status": "delivered",
                "player_name": first_completed.get("player_name", ""),
                "reference_no": first_completed.get("reference_no", ""),
                "summary": queued_summary,
            })
        return jsonify({
            "ok": True,
            "result": "processing",
            "order_status": "pending",
            "can_approve": False,
            "message": f"Cola automática en curso: {queued_summary.get('completed_units', 0)}/{queued_summary.get('total_units', 0)} completadas.",
            "summary": queued_summary,
        })

    if summary.get("completed_units", 0) >= summary.get("total_units", 0):
        first_completed = next((unit for unit in units if (unit.get("status") or "") == "completed"), {})
        return jsonify({
            "ok": True,
            "result": "completed",
            "order_status": "delivered",
            "player_name": first_completed.get("player_name", ""),
            "reference_no": first_completed.get("reference_no", ""),
            "summary": summary,
        })
    if summary.get("processing_units", 0) > 0:
        return jsonify({
            "ok": True,
            "result": "processing",
            "order_status": "pending",
            "can_approve": False,
            "message": f"Hay {summary.get('processing_units', 0)} recarga(s) aún procesándose en Revendedores.",
            "summary": summary,
        })
    return jsonify({
        "ok": True,
        "result": "failed",
        "order_status": "pending",
        "can_approve": summary.get("retryable_units", 0) > 0,
        "message": f"Quedan {summary.get('retryable_units', 0)} recarga(s) por reenviar.",
        "summary": summary,
    })


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
            {"id": it.id, "title": it.title, "price": it.price, "description": (it.description or ""), "sticker": (it.sticker or ""), "icon_path": (it.icon_path or "")}
            for it in items
        ]
    })

@app.route("/admin/revendedores/sync", methods=["POST"])
def admin_revendedores_sync_catalog():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    base_url, api_key, catalog_path, _ = _revendedores_env()
    if not base_url:
        return jsonify({"ok": False, "error": "Configura REVENDEDORES_BASE_URL o WEBB_URL"}), 400
    if not api_key:
        return jsonify({"ok": False, "error": "Configura REVENDEDORES_API_KEY o WEBB_API_KEY"}), 400

    normalized = []
    remote_error = ""

    try:
        resp = _requests_lib.get(
            f"{base_url}{catalog_path}",
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        if not resp.ok:
            key_preview = (api_key[:12] + "...") if len(api_key) > 12 else "(vacía)"
            remote_error = f"HTTP {resp.status_code} en {catalog_path} (url={base_url}, key={key_preview}, len={len(api_key)})"
        else:
            try:
                payload = resp.json()
            except Exception:
                snippet = (resp.text or "").strip().replace("\n", " ")[:180]
                remote_error = f"Respuesta no JSON: {snippet or 'vacía'}"
            else:
                normalized = _normalize_rev_catalog_payload(payload)
                if not normalized:
                    remote_error = "Catálogo API sin paquetes válidos"
    except Exception as exc:
        remote_error = f"No se pudo consultar catálogo API: {str(exc)}"

    if not normalized:
        return jsonify({"ok": False, "error": f"No se pudo sincronizar catálogo de Revendedores: {remote_error}"}), 502

    # Per-game breakdown for debugging
    games_summary = {}
    for ent in normalized:
        gname = ent.get("remote_product_name") or "?"
        pid = ent.get("remote_product_id")
        k = f"{gname} (pid={pid})"
        games_summary[k] = games_summary.get(k, 0) + 1

    created = 0
    updated = 0
    seen_keys = set()

    try:
        for ent in normalized:
            key = (ent.get("remote_product_id"), ent.get("remote_package_id"))
            seen_keys.add(key)
            row = RevendedoresCatalogItem.query.filter_by(
                remote_product_id=ent.get("remote_product_id"),
                remote_package_id=ent.get("remote_package_id"),
            ).first()
            if not row:
                row = RevendedoresCatalogItem(**ent)
                db.session.add(row)
                created += 1
            else:
                row.remote_product_name = ent.get("remote_product_name", "")
                row.remote_package_name = ent.get("remote_package_name", "")
                row.active = bool(ent.get("active"))
                row.raw_json = ent.get("raw_json", "")
                updated += 1

        deactivated = 0
        for row in RevendedoresCatalogItem.query.all():
            key = (row.remote_product_id, row.remote_package_id)
            if key not in seen_keys:
                if row.active:
                    deactivated += 1
                row.active = False

        db.session.commit()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": f"Error guardando catálogo: {str(exc)}"}), 500

    active_count = RevendedoresCatalogItem.query.filter_by(active=True).count()

    return jsonify({
        "ok": True,
        "source": "api",
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
        "total_normalized": len(normalized),
        "active_in_db": active_count,
        "games": games_summary,
    })


@app.route("/admin/revendedores/mapping-data", methods=["GET"])
def admin_revendedores_mapping_data():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    packages = StorePackage.query.filter_by(active=True).order_by(StorePackage.sort_order.asc(), StorePackage.id.asc()).all()
    selected_package_id = request.args.get("store_package_id", type=int)

    store_items = []
    mappings_by_item = {}
    if selected_package_id:
        store_items = GamePackageItem.query.filter_by(
            store_package_id=selected_package_id,
            active=True,
        ).order_by(GamePackageItem.id.asc()).all()
    else:
        # Requiere selección explícita de juego para desplegar ítems.
        store_items = []

    item_ids = [it.id for it in store_items]
    if item_ids:
        rows = RevendedoresItemMapping.query.filter(
            RevendedoresItemMapping.store_item_id.in_(item_ids),
            RevendedoresItemMapping.active == True,
        ).all()
        mappings_by_item = {int(r.store_item_id): r for r in rows}

    package_name_by_id = {int(p.id): (p.name or "") for p in packages}

    catalog_rows = RevendedoresCatalogItem.query.filter_by(active=True).order_by(
        RevendedoresCatalogItem.remote_product_name.asc(),
        RevendedoresCatalogItem.remote_package_name.asc(),
        RevendedoresCatalogItem.id.asc(),
    ).all()

    def _extract_price(raw_json_str):
        try:
            obj = json.loads(raw_json_str or "{}")
            p = obj.get("price") or obj.get("precio") or obj.get("cost")
            if p is not None:
                return round(float(p), 2)
        except Exception:
            pass
        return None

    return jsonify({
        "ok": True,
        "selected_store_package_id": selected_package_id,
        "store_packages": [
            {"id": p.id, "name": p.name, "category": p.category or ""}
            for p in packages
        ],
        "store_items": [
            {
                "id": it.id,
                "title": it.title,
                "price": float(it.price or 0.0),
                "store_package_id": it.store_package_id,
                "store_package_name": package_name_by_id.get(int(it.store_package_id), ""),
                "mapping": {
                    "id": mappings_by_item[it.id].id,
                    "remote_product_id": mappings_by_item[it.id].remote_product_id,
                    "remote_package_id": mappings_by_item[it.id].remote_package_id,
                    "remote_label": mappings_by_item[it.id].remote_label or "",
                    "auto_enabled": bool(mappings_by_item[it.id].auto_enabled),
                } if it.id in mappings_by_item else None,
            }
            for it in store_items
        ],
        "remote_catalog": [
            {
                "catalog_id": r.id,
                "remote_product_id": r.remote_product_id,
                "remote_product_name": r.remote_product_name or "",
                "remote_package_id": r.remote_package_id,
                "remote_package_name": r.remote_package_name or "",
                "price": _extract_price(r.raw_json),
            }
            for r in catalog_rows
        ],
    })


@app.route("/admin/revendedores/mappings/bulk", methods=["POST"])
def admin_revendedores_mappings_bulk_save():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    entries = data.get("entries") or []
    if not isinstance(entries, list):
        return jsonify({"ok": False, "error": "Formato inválido"}), 400

    saved = 0
    disabled = 0

    try:
        for ent in entries:
            if not isinstance(ent, dict):
                continue
            try:
                store_item_id = int(ent.get("store_item_id"))
            except Exception:
                continue

            item = GamePackageItem.query.get(store_item_id)
            if not item:
                continue

            catalog_id_raw = ent.get("catalog_id")
            auto_enabled = bool(ent.get("auto_enabled"))

            row = RevendedoresItemMapping.query.filter_by(store_item_id=store_item_id).first()

            if not catalog_id_raw:
                if row:
                    row.active = False
                    row.auto_enabled = False
                    disabled += 1
                continue

            try:
                catalog_id = int(catalog_id_raw)
            except Exception:
                continue

            catalog = RevendedoresCatalogItem.query.get(catalog_id)
            if not catalog:
                continue

            remote_label = (
                f"{(catalog.remote_product_name or '').strip()} · {(catalog.remote_package_name or '').strip()}"
            ).strip(" ·")

            if not row:
                row = RevendedoresItemMapping(
                    store_package_id=item.store_package_id,
                    store_item_id=store_item_id,
                    remote_product_id=catalog.remote_product_id,
                    remote_package_id=catalog.remote_package_id,
                    remote_label=remote_label,
                    auto_enabled=auto_enabled,
                    active=True,
                )
                db.session.add(row)
            else:
                row.store_package_id = item.store_package_id
                row.remote_product_id = catalog.remote_product_id
                row.remote_package_id = catalog.remote_package_id
                row.remote_label = remote_label
                row.auto_enabled = auto_enabled
                row.active = True
            saved += 1

        db.session.commit()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": f"No se pudo guardar mapeo: {str(exc)}"}), 500

    return jsonify({"ok": True, "saved": saved, "disabled": disabled})


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
            {
                "id": it.id,
                "title": it.title,
                "price": it.price,
                "cost_unit_usd": float(it.profit_net_usd or 0.0),
                "description": it.description,
                "sticker": (it.sticker or ""),
                "icon_path": (it.icon_path or ""),
                "active": it.active,
            }
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
    special_description = (data.get("special_description") or "").strip()
    special_description = (data.get("special_description") or "").strip()
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
    # Treat profit_net_usd column as cost per unit (USD) in admin APIs
    if "cost_unit_usd" in data:
        try:
            item.profit_net_usd = float(data.get("cost_unit_usd") or 0.0)
        except Exception:
            item.profit_net_usd = 0.0
    elif "profit_net_usd" in data:
        # Backwards compatibility if any client still sends profit_net_usd
        try:
            item.profit_net_usd = float(data.get("profit_net_usd") or 0.0)
        except Exception:
            item.profit_net_usd = 0.0
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


@app.route("/admin/package/<int:gid>/items/bulk", methods=["PUT"])
def admin_game_items_bulk_update(gid: int):
    """Update multiple items of a package in one request."""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    game = StorePackage.query.get(gid)
    if not game:
        return jsonify({"ok": False, "error": "Juego no existe"}), 404
    data = request.get_json(silent=True) or {}
    items_data = data.get("items")
    if not isinstance(items_data, list):
        return jsonify({"ok": False, "error": "Se requiere una lista de items"}), 400
    updated = 0
    for entry in items_data:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        if not item_id:
            continue
        item = GamePackageItem.query.get(int(item_id))
        if not item or item.store_package_id != gid:
            continue
        if "title" in entry:
            item.title = (entry.get("title") or "").strip()
        if "sticker" in entry:
            item.sticker = (entry.get("sticker") or "").strip()
        if "icon_path" in entry:
            item.icon_path = (entry.get("icon_path") or "").strip()
        if "price" in entry:
            try:
                item.price = float(entry.get("price") or 0)
            except Exception:
                pass
        if "cost_unit_usd" in entry:
            try:
                item.profit_net_usd = float(entry.get("cost_unit_usd") or 0.0)
            except Exception:
                pass
        if "active" in entry:
            item.active = bool(entry.get("active"))
        updated += 1
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


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
    special_description = data.get("special_description")
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
    if special_description is not None:
        item.special_description = (special_description or '').strip()
    if requires_zone_id is not None:
        item.requires_zone_id = int(bool(requires_zone_id))
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
            {"id": p.id, "name": p.name, "image_path": p.image_path, "active": p.active, "category": (p.category or 'mobile'), "description": (p.description or ''), "special_description": (p.special_description or ''), "requires_zone_id": bool(p.requires_zone_id), "sort_order": int(p.sort_order or 0)}
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
    special_description = (data.get("special_description") or "").strip()
    requires_zone_id = int(bool(data.get("requires_zone_id", False)))
    if category not in ("mobile", "gift"):
        category = "mobile"
    if not name or not image_path:
        return jsonify({"ok": False, "error": "Nombre e imagen requeridos"}), 400
    item = StorePackage(name=name, image_path=image_path, active=True, category=category, description=description, special_description=special_description, requires_zone_id=requires_zone_id)
    try:
        db.session.add(item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] admin_packages_create: {e}")
        return jsonify({"ok": False, "error": f"Error DB: {str(e)[:200]}"}), 500
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


@app.context_processor
def inject_cfg_helpers():
    # Expose get_config_value so templates can access AppConfig values
    return dict(get_config_value=get_config_value)


@app.route("/admin/stats/packages", methods=["GET"])
def admin_stats_packages():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    rows = (
        StorePackage.query
        .order_by(StorePackage.category.asc(), StorePackage.sort_order.asc(), StorePackage.created_at.asc())
        .all()
    )
    return jsonify({
        "ok": True,
        "packages": [
            {
                "id": p.id,
                "name": p.name,
                "category": (p.category or ""),
                "active": bool(p.active),
            }
            for p in rows
        ],
    })


@app.route("/admin/stats/summary", methods=["GET"])
def admin_stats_summary():
    """Global summary of profits and affiliate commissions across all packages.

    This mirrors the logic of admin_stats_package but without filtering by
    package id. Only items with profit_net_usd > 0 are considered for
    profit totals.
    """
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    items = GamePackageItem.query.all()
    items_by_id = {it.id: it for it in items}

    total_profit_net = 0.0
    total_commission_affiliates = 0.0

    # Optional period filter
    period = (request.args.get("period") or "").strip().lower()
    if period == "weekly":
        cutoff = get_stats_reset_cutoff()
        approved_orders = Order.query.filter(
            Order.status.in_(["approved", "delivered"]),
            Order.created_at >= cutoff,
        ).all()
    else:
        # Lifetime stats: do not restrict by weekly cutoff so resets don't wipe accumulated totals
        approved_orders = Order.query.filter(Order.status.in_(["approved", "delivered"])).all()
    for o in approved_orders:
        try:
            use_affiliate = False
            su = None
            if o.special_user_id:
                su = SpecialUser.query.get(o.special_user_id)
            if (not su) and (o.special_code or ""):
                su = SpecialUser.query.filter(
                    db.func.lower(SpecialUser.code) == (o.special_code or "").lower(),
                    SpecialUser.active == True,
                ).first()
            if su and su.active:
                scope_ok = True
                sc = (su.scope or "all")
                if sc == "package":
                    try:
                        scope_ok = (su.scope_package_id == o.store_package_id)
                    except Exception:
                        scope_ok = False
                use_affiliate = scope_ok

            # items_map: iid -> {qty, revenue, cost_total}
            items_map = {}
            try:
                if (o.items_json or "").strip():
                    payload = json.loads(o.items_json or "[]")
                    if isinstance(payload, list):
                        for ent in payload:
                            try:
                                iid = int(ent.get("item_id") or 0)
                            except Exception:
                                iid = 0
                            if iid <= 0:
                                continue
                            q = int(ent.get("qty") or 1)
                            if q <= 0:
                                q = 1
                            try:
                                p = float(ent.get("price") or 0.0)
                            except Exception:
                                p = 0.0
                            # Usar costo guardado en la orden, o costo actual si no existe
                            it = items_by_id.get(iid)
                            cost_unit = float(ent.get("cost_unit_usd") or (it.profit_net_usd if it else 0.0) or 0.0)
                            
                            cur = items_map.get(iid) or {"qty": 0, "revenue": 0.0, "cost_total": 0.0}
                            cur["qty"] += q
                            cur["revenue"] += (p * q)
                            cur["cost_total"] += (cost_unit * q)
                            items_map[iid] = cur
            except Exception:
                items_map = {}
            if not items_map and o.item_id:
                # Legacy: single item orders without items_json
                try:
                    iid = int(o.item_id)
                    if iid > 0:
                        it = items_by_id.get(iid)
                        if it:
                            cur = items_map.get(iid) or {"qty": 0, "revenue": 0.0, "cost_total": 0.0}
                            cur["qty"] += 1
                            cur["revenue"] += float(it.price or 0.0)
                            cur["cost_total"] += float(it.profit_net_usd or 0.0)
                            items_map[iid] = cur
                except Exception:
                    pass

            # Determinar comisión del influencer una vez por orden (solo para registro)
            comm_pct = 0.0
            if use_affiliate and su:
                comm_pct = float(su.commission_percent or 0.0)

            # Calcular ganancia por cada ítem
            for iid, agg in items_map.items():
                it = items_by_id.get(iid)
                if not it:
                    continue
                qty = int(agg.get("qty") or 0)
                revenue = float(agg.get("revenue") or 0.0)
                cost_total = float(agg.get("cost_total") or 0.0)
                
                if qty <= 0 or cost_total <= 0.0:
                    continue
                
                # Registrar comisión del influencer (solo informativo)
                if use_affiliate and comm_pct > 0:
                    commission_item = round(revenue * (comm_pct / 100.0), 2)
                    total_commission_affiliates += commission_item
                    # Restar comisión del influencer de la ganancia
                    profit_val = revenue - cost_total - commission_item
                else:
                    # Ganancia = precio pagado por cliente - costo guardado en la orden
                    profit_val = revenue - cost_total
                if profit_val < 0.0:
                    profit_val = 0.0
                total_profit_net += profit_val
        except Exception:
            continue

    return jsonify({
        "ok": True,
        "summary": {
            "total_profit_net_usd": round(total_profit_net, 2),
            "total_affiliate_commission_usd": round(total_commission_affiliates, 2),
            "total_profit_after_affiliates_usd": round(total_profit_net, 2),
        },
    })


# ---------- Profit History (snapshots) ----------

def _maybe_snapshot_previous_period():
    """If the previous weekly period has no snapshot yet, compute and save one."""
    try:
        current_cutoff = get_stats_reset_cutoff()
        prev_cutoff = current_cutoff - timedelta(days=7)
        existing = ProfitSnapshot.query.filter_by(period_start=prev_cutoff, period_end=current_cutoff).first()
        if existing:
            return
        prev_orders = Order.query.filter(
            Order.status.in_(["approved", "delivered"]),
            Order.created_at >= prev_cutoff,
            Order.created_at < current_cutoff,
        ).all()
        if not prev_orders:
            return
        all_items = GamePackageItem.query.all()
        items_by_id = {it.id: it for it in all_items}
        profit = 0.0
        commission = 0.0
        for o in prev_orders:
            try:
                su = None
                use_affiliate = False
                if o.special_user_id:
                    su = SpecialUser.query.get(o.special_user_id)
                if (not su) and (o.special_code or ""):
                    su = SpecialUser.query.filter(
                        db.func.lower(SpecialUser.code) == (o.special_code or "").lower(),
                        SpecialUser.active == True,
                    ).first()
                if su and su.active:
                    sc = (su.scope or "all")
                    scope_ok = True
                    if sc == "package":
                        try:
                            scope_ok = (su.scope_package_id == o.store_package_id)
                        except Exception:
                            scope_ok = False
                    use_affiliate = scope_ok
                items_map = {}
                if (o.items_json or "").strip():
                    payload = json.loads(o.items_json or "[]")
                    if isinstance(payload, list):
                        for ent in payload:
                            iid = int(ent.get("item_id") or 0)
                            if iid <= 0:
                                continue
                            q = max(int(ent.get("qty") or 1), 1)
                            p = float(ent.get("price") or 0.0)
                            it = items_by_id.get(iid)
                            cu = float(ent.get("cost_unit_usd") or (it.profit_net_usd if it else 0.0) or 0.0)
                            cur = items_map.get(iid, {"rev": 0.0, "cost": 0.0})
                            cur["rev"] += p * q
                            cur["cost"] += cu * q
                            items_map[iid] = cur
                comm_pct = float(su.commission_percent or 0.0) if use_affiliate and su else 0.0
                for iid, agg in items_map.items():
                    rev = agg["rev"]
                    cost = agg["cost"]
                    if cost <= 0.0:
                        continue
                    if comm_pct > 0:
                        ci = round(rev * (comm_pct / 100.0), 2)
                        commission += ci
                        pv = rev - cost - ci
                    else:
                        pv = rev - cost
                    if pv > 0:
                        profit += pv
            except Exception:
                continue
        snap = ProfitSnapshot(
            period_start=prev_cutoff,
            period_end=current_cutoff,
            profit_usd=round(profit, 2),
            commission_usd=round(commission, 2),
        )
        db.session.add(snap)
        db.session.commit()
    except Exception:
        db.session.rollback()


@app.route("/admin/stats/history", methods=["GET"])
def admin_stats_history():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    _maybe_snapshot_previous_period()
    snaps = ProfitSnapshot.query.order_by(ProfitSnapshot.period_end.desc()).all()
    return jsonify({
        "ok": True,
        "history": [{
            "id": s.id,
            "period_start": s.period_start.strftime("%d/%m/%Y %H:%M") if s.period_start else "",
            "period_end": s.period_end.strftime("%d/%m/%Y %H:%M") if s.period_end else "",
            "profit_usd": round(s.profit_usd or 0, 2),
            "commission_usd": round(s.commission_usd or 0, 2),
        } for s in snaps],
    })


@app.route("/admin/stats/history/<int:snap_id>", methods=["DELETE"])
def admin_stats_history_delete(snap_id):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    snap = ProfitSnapshot.query.get(snap_id)
    if not snap:
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    db.session.delete(snap)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/stats/package/<int:pkg_id>", methods=["GET"])
def admin_stats_package(pkg_id: int):
    """Return per-item and aggregate profit stats for a given package.

    Uses GamePackageItem.profit_net_usd as the net profit per unit (USD).
    Influencer commissions are computed based on the same logic used when
    approving orders, using SpecialUser commission percentages.
    """
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    pkg = StorePackage.query.get(pkg_id)
    if not pkg:
        return jsonify({"ok": False, "error": "Paquete no existe"}), 404

    items = GamePackageItem.query.filter_by(store_package_id=pkg_id).all()
    items_by_id = {it.id: it for it in items}

    stats = {}
    total_profit_net = 0.0
    total_commission_affiliates = 0.0

    # Optional period filter per package
    period = (request.args.get("period") or "").strip().lower()
    if period == "weekly":
        cutoff = get_stats_reset_cutoff()
        approved_orders = Order.query.filter(
            Order.store_package_id == pkg_id,
            Order.status.in_(["approved", "delivered"]),
            Order.created_at >= cutoff,
        ).all()
    else:
        # Lifetime stats per package (no cutoff)
        approved_orders = Order.query.filter(
            Order.store_package_id == pkg_id,
            Order.status.in_(["approved", "delivered"]),
        ).all()
    for o in approved_orders:
        try:
            use_affiliate = False
            su = None
            if o.special_user_id:
                su = SpecialUser.query.get(o.special_user_id)
            if (not su) and (o.special_code or ""):
                su = SpecialUser.query.filter(
                    db.func.lower(SpecialUser.code) == (o.special_code or "").lower(),
                    SpecialUser.active == True,
                ).first()
            if su and su.active:
                scope_ok = True
                sc = (su.scope or "all")
                if sc == "package":
                    try:
                        scope_ok = (su.scope_package_id == o.store_package_id)
                    except Exception:
                        scope_ok = False
                use_affiliate = scope_ok

            # items_map: iid -> {qty, revenue, cost_total}
            items_map = {}
            try:
                if (o.items_json or "").strip():
                    payload = json.loads(o.items_json or "[]")
                    if isinstance(payload, list):
                        for ent in payload:
                            try:
                                iid = int(ent.get("item_id") or 0)
                            except Exception:
                                iid = 0
                            if iid <= 0:
                                continue
                            q = int(ent.get("qty") or 1)
                            if q <= 0:
                                q = 1
                            try:
                                p = float(ent.get("price") or 0.0)
                            except Exception:
                                p = 0.0
                            # Usar costo guardado en la orden, o costo actual si no existe
                            it = items_by_id.get(iid)
                            cost_unit = float(ent.get("cost_unit_usd") or (it.profit_net_usd if it else 0.0) or 0.0)
                            
                            cur = items_map.get(iid) or {"qty": 0, "revenue": 0.0, "cost_total": 0.0}
                            cur["qty"] += q
                            cur["revenue"] += (p * q)
                            cur["cost_total"] += (cost_unit * q)
                            items_map[iid] = cur
            except Exception:
                items_map = {}
            if not items_map and o.item_id:
                # Legacy: single item orders without items_json
                try:
                    iid = int(o.item_id)
                    if iid > 0:
                        it = items_by_id.get(iid)
                        if it:
                            cur = items_map.get(iid) or {"qty": 0, "revenue": 0.0, "cost_total": 0.0}
                            cur["qty"] += 1
                            cur["revenue"] += float(it.price or 0.0)
                            cur["cost_total"] += float(it.profit_net_usd or 0.0)
                            items_map[iid] = cur
                except Exception:
                    pass

            # Determinar comisión del influencer una vez por orden (solo para registro)
            comm_pct = 0.0
            if use_affiliate and su:
                comm_pct = float(su.commission_percent or 0.0)

            # Calcular ganancia por cada ítem
            for iid, agg in items_map.items():
                it = items_by_id.get(iid)
                if not it:
                    continue
                
                qty = int(agg.get("qty") or 0)
                revenue = float(agg.get("revenue") or 0.0)
                cost_total = float(agg.get("cost_total") or 0.0)
                
                if qty <= 0 or cost_total <= 0.0:
                    continue
                
                # Costo actual del ítem (para mostrar en UI)
                cost_unit = float(it.profit_net_usd or 0.0)
                # Precio estándar y ganancia estándar por unidad (informativa)
                price_std = float(it.price or 0.0)
                profit_unit_std = price_std - cost_unit
                if profit_unit_std < 0.0:
                    profit_unit_std = 0.0
                
                # Registrar comisión del influencer (solo informativo)
                if use_affiliate and comm_pct > 0:
                    commission_item = round(revenue * (comm_pct / 100.0), 2)
                    total_commission_affiliates += commission_item
                    # Restar comisión del influencer de la ganancia
                    profit_val = revenue - cost_total - commission_item
                else:
                    profit_val = revenue - cost_total
                rec = stats.setdefault(
                    iid,
                    {
                        "id": it.id,
                        "title": it.title,
                        "price": price_std,
                        "cost_unit_usd": cost_unit,
                        "profit_unit_std_usd": profit_unit_std,
                        "revenue_total_usd": 0.0,
                        "revenue_affiliate_usd": 0.0,
                        "qty_total": 0,
                        "qty_normal": 0,
                        "qty_with_affiliate": 0,
                        "profit_total_usd": 0.0,
                    },
                )
                rec["qty_total"] += qty
                if use_affiliate:
                    rec["qty_with_affiliate"] += qty
                    rec["revenue_affiliate_usd"] = rec.get("revenue_affiliate_usd", 0.0) + revenue
                else:
                    rec["qty_normal"] += qty
                # acumular revenue para poder calcular promedio real
                rec["revenue_total_usd"] = rec.get("revenue_total_usd", 0.0) + revenue
                if profit_val < 0.0:
                    profit_val = 0.0
                rec["profit_total_usd"] = rec.get("profit_total_usd", 0.0) + profit_val
                total_profit_net += profit_val
        except Exception:
            continue

    items_out = []
    for it in items:
        price_std = float(it.price or 0.0)
        cost_unit = float(it.profit_net_usd or 0.0)
        # profit estándar por unidad = precio estándar - costo
        profit_unit_std = price_std - cost_unit
        if profit_unit_std < 0.0:
            profit_unit_std = 0.0
        base = stats.get(
            it.id,
            {
                "id": it.id,
                "title": it.title,
                "price": price_std,
                "cost_unit_usd": cost_unit,
                "profit_unit_std_usd": profit_unit_std,
                "revenue_total_usd": 0.0,
                "revenue_affiliate_usd": 0.0,
                "qty_total": 0,
                "qty_normal": 0,
                "qty_with_affiliate": 0,
                "profit_total_usd": 0.0,
            },
        )
        rec_out = dict(base)
        # Calcular ganancia "Con descuento" usando datos reales de órdenes con afiliado
        qty_aff = int(rec_out.get("qty_with_affiliate") or 0)
        rev_aff = float(rec_out.get("revenue_affiliate_usd") or 0.0)
        if qty_aff > 0 and rev_aff > 0:
            avg_price_disc = rev_aff / qty_aff
            profit_with_disc = avg_price_disc - cost_unit
        else:
            # Sin datos reales: estimar con descuento promedio de afiliados activos
            avg_disc = 0.0
            try:
                active_affs = SpecialUser.query.filter_by(active=True).all()
                if active_affs:
                    avg_disc = sum(float(a.discount_percent or 0) for a in active_affs) / len(active_affs) / 100.0
            except Exception:
                pass
            profit_with_disc = (price_std * (1.0 - avg_disc)) - cost_unit
        if profit_with_disc < 0.0:
            profit_with_disc = 0.0
        rec_out["profit_unit_real_avg_usd"] = round(profit_with_disc, 2)
        rec_out["total_profit_net_usd"] = round(float(base.get("profit_total_usd") or 0.0), 2)
        items_out.append(rec_out)

    return jsonify({
        "ok": True,
        "package": {
            "id": pkg.id,
            "name": pkg.name,
            "category": (pkg.category or ""),
        },
        "items": items_out,
        "summary": {
            "total_profit_net_usd": round(total_profit_net, 2),
            "total_affiliate_commission_usd": round(total_commission_affiliates, 2),
            # total_profit_net ya tiene las comisiones descontadas por ítem
            "total_profit_after_affiliates_usd": round(total_profit_net, 2),
        },
    })


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
