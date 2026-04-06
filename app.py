import os
import json
import re
import time
import zlib
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
import html as _html
import hashlib
import hmac as _hmac_module
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory, current_app
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
import google.generativeai as genai
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

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


@app.after_request
def _disable_admin_cache(response):
    try:
        req_path = (request.path or "").strip()
        if req_path == "/admin" or req_path.endswith("/admin") or req_path == "/static/js/admin.js":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    except Exception:
        pass
    return response

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
FAVICON_FILENAME = "561553627_18409264204136226_1099017029378111495_n.ico"
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
GENAI_API_KEY = (
    os.environ.get("GENAI_API_KEY", "")
    or os.environ.get("GEMINI_API_KEY", "")
    or os.environ.get("GOOGLE_API_KEY", "")
).strip()
GENAI_MODEL_NAME = (os.environ.get("GENAI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()
_GENAI_MODEL = None
_GENAI_MODEL_READY = False

db = SQLAlchemy(app)

_PLAYER_SCRAPE_CACHE = {}
_PLAYER_LOOKUP_INFLIGHT = {}
_PLAYER_LOOKUP_LOCK = threading.Lock()
_FFMANIA_TIMEOUT = (
    float(os.environ.get("FFMANIA_CONNECT_TIMEOUT_SECONDS", "2.5")),
    float(os.environ.get("FFMANIA_READ_TIMEOUT_SECONDS", "3.5")),
)
_FFMANIA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,pt-BR;q=0.7",
    "Cache-Control": "no-cache",
}
_FFMANIA_SESSION = _requests_lib.Session()
try:
    _ffmania_adapter = _requests_lib.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)
    _FFMANIA_SESSION.mount("https://", _ffmania_adapter)
    _FFMANIA_SESSION.mount("http://", _ffmania_adapter)
except Exception:
    pass


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


def _player_lookup_singleflight(key: str, loader, wait_timeout: float = 6.5):
    created = False
    with _PLAYER_LOOKUP_LOCK:
        state = _PLAYER_LOOKUP_INFLIGHT.get(key)
        if not state:
            state = {"event": threading.Event(), "result": None, "error": None}
            _PLAYER_LOOKUP_INFLIGHT[key] = state
            created = True
    if created:
        try:
            state["result"] = loader()
            return state["result"]
        except Exception as exc:
            state["error"] = exc
            raise
        finally:
            state["event"].set()
            with _PLAYER_LOOKUP_LOCK:
                _PLAYER_LOOKUP_INFLIGHT.pop(key, None)
    state["event"].wait(wait_timeout)
    if state.get("error"):
        raise state["error"]
    return state.get("result")


def _extract_ffmania_nick(raw_html: str) -> str:
    if not raw_html:
        return ""
    direct_patterns = [
        r'"nick"\s*:\s*"([^"\\]+(?:\\.[^"\\]*)*)"',
        r'"nickname"\s*:\s*"([^"\\]+(?:\\.[^"\\]*)*)"',
        r'class="nome"[^>]*>\s*([^<]+?)\s*</',
        r'<strong>[^<]*(?:Nombre|Nome|Nick)\s*:?\s*</strong>\s*([^<]+?)\s*</',
        r'(?is)<[^>]*>\s*(?:Nombre|Nome|Nick)\s*:?\s*</[^>]*>\s*<[^>]*>\s*([^<]+?)\s*</',
        r'(?im)\b(?:Nombre|Nome|Nick)\s*:\s*([^\n<]+)',
    ]
    for pat in direct_patterns:
        m = re.search(pat, raw_html, flags=re.IGNORECASE)
        if m:
            nick = (m.group(1) or "").replace('\\/', '/').replace('\\"', '"')
            nick = _html.unescape(nick)
            nick = re.sub(r"\s+", " ", nick).strip()
            if nick:
                return nick

    txt = raw_html
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\\1>", " ", txt)
    txt = re.sub(r"(?i)<br\\s*/?>", "\n", txt)
    txt = re.sub(r"(?i)</(p|div|tr|li|h1|h2|h3|table|section|article|span)>", "\n", txt)
    txt = re.sub(r"(?is)<[^>]+>", " ", txt)
    txt = _html.unescape(txt)
    txt = re.sub(r"[\t\r]+", " ", txt)
    txt = re.sub(r"[ ]{2,}", " ", txt)
    txt = re.sub(r"\n{2,}", "\n", txt)

    fallback_patterns = [
        r"(?im)^\s*Nombre\s*:\s*(.+?)\s*$",
        r"(?im)^\s*Nome\s*:\s*(.+?)\s*$",
        r"(?im)^\s*Nick\s*:\s*(.+?)\s*$",
    ]
    for pat in fallback_patterns:
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if m:
            nick = re.sub(r"\s+", " ", (m.group(1) or "")).strip()
            if nick:
                return nick
    return ""


def _scrape_ffmania_nick(uid: str) -> str:
    url = f"https://www.freefiremania.com.br/cuenta/{uid}.html"
    try:
        resp = _FFMANIA_SESSION.get(url, headers=_FFMANIA_HEADERS, timeout=_FFMANIA_TIMEOUT)
    except _requests_lib.HTTPError as e:
        if int(getattr(getattr(e, "response", None), "status_code", 0) or 0) == 404:
            return ""
        raise
    except _requests_lib.RequestException:
        raise

    if int(resp.status_code or 0) == 404:
        return ""
    resp.raise_for_status()
    return _extract_ffmania_nick(resp.text or "")


def _smileone_is_valid_username(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return False
    lower = text.lower()
    invalid_fragments = [
        "id inválido",
        "id invalido",
        "user id",
        "não existe",
        "nao existe",
        "not found",
        "network",
        "conexión de la red",
        "conexao de rede",
        "inténtalo de nuevo",
        "tente novamente",
        "try again",
        "problem with the network",
        "erro",
        "error",
        "inválido",
        "invalido",
    ]
    return not any(fragment in lower for fragment in invalid_fragments)


def _smileone_extract_username(resp_json: dict) -> str:
    candidates = [
        (resp_json.get("data") or {}).get("username"),
        (resp_json.get("data") or {}).get("nickname"),
        (resp_json.get("data") or {}).get("name"),
        resp_json.get("username"),
        resp_json.get("nickname"),
        resp_json.get("name"),
    ]
    for candidate in candidates:
        text = re.sub(r"\s+", " ", str(candidate or "")).strip()
        if _smileone_is_valid_username(text):
            return text
    info_text = re.sub(r"\s+", " ", str(resp_json.get("info") or "")).strip()
    if _smileone_is_valid_username(info_text):
        return info_text
    return ""


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
        # Extract username from various possible structures
        username = _smileone_extract_username(data)
        if username:
            return username
        # Handle error codes only after checking whether the API still returned a nickname.
        if int(data.get("code") or 0) != 200:
            # 201 = USER ID não existe, 404 = not found, etc.
            print(f"[BS] API error: {data.get('info', '')}")
            return ""
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
                    username = _smileone_extract_username(data_json)
                    if username:
                        return username
                    code = int(data_json.get("code") or 0)
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
    if cached:
        return jsonify({"ok": True, "uid": uid, "nick": cached, "cached": True})

    nick = _scrape_smileone_bloodstrike_nick(uid)

    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    _player_cache_set(cache_key, nick, ttl_seconds=600)
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
    if cached:
        return jsonify({"ok": True, "uid": uid, "zid": zid, "nick": cached, "cached": True})

    nick = _scrape_smileone_mobilelegends_nick(uid, zid)

    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    _player_cache_set(cache_key, nick, ttl_seconds=600)
    return jsonify({"ok": True, "uid": uid, "zid": zid, "nick": nick, "cached": False})


# ==============================
# Generic Smile.One verification (dynamic connections)
# ==============================
def _scrape_smileone_generic(conn, uid: str, zid: str = "") -> str:
    """Generic Smile.One checkrole using a SmileOneConnection config."""
    try:
        sess = _requests_lib.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        page_url = conn.page_url
        page = sess.get(page_url, timeout=8)
        print(f"[SO:{conn.name}] page status={page.status_code}")

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

        post_headers = {
            "Referer": page_url,
            "Origin": "https://www.smile.one",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        if csrf:
            post_headers["X-CSRF-Token"] = csrf

        slug = (conn.product_slug or "").strip()
        pid = (conn.smile_pid or "").strip()
        sid = (conn.server_id or "-1").strip()

        # Build payload variants depending on whether zone is needed
        if conn.requires_zone and zid:
            payload_variants = [
                {"user_id": uid, "zone_id": zid},
                {"uid": uid, "sid": zid},
                {"uid": uid, "zoneid": zid},
            ]
        else:
            payload_variants = [
                {"uid": uid, "sid": sid},
            ]

        # Derive checkrole endpoints from page_url
        # e.g. https://www.smile.one/br/merchant/game/bloodstrike -> checkrole
        base = page_url.split("?")[0].rstrip("/")
        endpoints = []
        if slug:
            endpoints.append(f"https://www.smile.one/merchant/{slug}/checkrole")
            # Try with /br/ prefix too
            endpoints.append(f"https://www.smile.one/br/merchant/game/checkrole?product={slug}")
        endpoints.append(base.rsplit("/", 1)[0] + "/checkrole")
        endpoints.append("https://www.smile.one/merchant/checkrole")
        # Deduplicate while preserving order
        seen = set()
        unique_endpoints = []
        for ep in endpoints:
            if ep not in seen:
                seen.add(ep)
                unique_endpoints.append(ep)

        for endpoint in unique_endpoints:
            for payload in payload_variants:
                post_data = {
                    "checkrole": "1",
                    "pid": pid,
                    **payload,
                }
                if slug:
                    post_data["product"] = slug
                if csrf:
                    post_data["_csrf"] = csrf
                resp = sess.post(endpoint, data=post_data, headers=post_headers, timeout=8)
                print(f"[SO:{conn.name}] {endpoint} -> {resp.status_code} {resp.text[:150]}")
                if resp.status_code != 200:
                    continue
                try:
                    data = resp.json()
                except Exception:
                    body = resp.text.strip()
                    if body.startswith("{"):
                        try:
                            data = json.loads(body)
                        except Exception:
                            continue
                    else:
                        if body and len(body) < 200 and "<" not in body:
                            return body.strip('" \t\r\n')
                        continue
                username = _smileone_extract_username(data)
                if username:
                    return username
                code = int(data.get("code") or 0)
                print(f"[SO:{conn.name}] code={code} info={data.get('info','')}")
        return ""
    except Exception as e:
        print(f"[SO:{conn.name}] Error: {e}")
        return ""


@app.route("/store/player/verify/smileone")
def store_player_verify_smileone():
    """Dynamic Smile.One verification using admin-configured connections."""
    scrape_enabled = (os.environ.get("SCRAPE_ENABLED", "true").strip().lower() == "true")
    if not scrape_enabled:
        return jsonify({"ok": False, "error": "Verificación deshabilitada"}), 403

    uid = (request.args.get("uid") or "").strip()
    zid = (request.args.get("zid") or request.args.get("zone") or "").strip()
    gid_raw = (request.args.get("gid") or "").strip()
    if not uid or not uid.isdigit():
        return jsonify({"ok": False, "error": "ID inválido"}), 400
    if not gid_raw or not gid_raw.isdigit():
        return jsonify({"ok": False, "error": "Juego inválido"}), 400

    conn = SmileOneConnection.query.filter_by(
        store_package_id=int(gid_raw), active=True
    ).first()
    if not conn:
        return jsonify({"ok": False, "error": "Verificación no disponible para este juego"}), 403

    if conn.requires_zone and (not zid or not zid.isdigit()):
        return jsonify({"ok": False, "error": "Zona ID inválida"}), 400

    cache_key = f"so_{conn.id}:{uid}" + (f":{zid}" if conn.requires_zone else "")
    cached = _player_cache_get(cache_key)
    if cached:
        result = {"ok": True, "uid": uid, "nick": cached, "cached": True}
        if conn.requires_zone:
            result["zid"] = zid
        return jsonify(result)

    nick = _scrape_smileone_generic(conn, uid, zid)

    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    _player_cache_set(cache_key, nick, ttl_seconds=600)
    result = {"ok": True, "uid": uid, "nick": nick, "cached": False}
    if conn.requires_zone:
        result["zid"] = zid
    return jsonify(result)


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
    if cached:
        return jsonify({"ok": True, "uid": uid, "nick": cached, "cached": True})

    try:
        nick = _player_lookup_singleflight(cache_key, lambda: _scrape_ffmania_nick(uid))
    except Exception:
        return jsonify({"ok": False, "error": "No se pudo verificar el ID"}), 502

    if not nick:
        return jsonify({"ok": False, "error": "ID no encontrado"}), 404
    _player_cache_set(cache_key, nick, ttl_seconds=600)
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


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        FAVICON_FILENAME,
        mimetype="image/x-icon",
    )

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
    capture_reference = db.Column(db.String(120), default="")
    price = db.Column(db.Float, default=0.0)
    active = db.Column(db.Boolean, default=True)
    # Gift card or delivery code (for gift category)
    delivery_code = db.Column(db.String(200), default="")
    # Optional: multiple gift codes for gift card orders
    delivery_codes_json = db.Column(db.Text, default="")
    # Special referral code support
    special_code = db.Column(db.String(80), default="")
    idempotency_key = db.Column(db.String(120), nullable=True, default=None)
    special_user_id = db.Column(db.Integer, nullable=True)
    # Optional: JSON string with multiple items: [{"item_id": int, "qty": int, "title": str, "price": float}]
    items_json = db.Column(db.Text, default="")
    # Revendedores API automation state (pending_verification, success, etc.)
    automation_json = db.Column(db.Text, default="")
    # Payment capture (voucher/comprobante image path relative to UPLOAD_FOLDER)
    payment_capture = db.Column(db.String(500), default="")
    payer_dni_type = db.Column(db.String(2), default="")
    payer_dni_number = db.Column(db.String(20), default="")
    payer_bank_origin = db.Column(db.String(20), default="")
    payer_phone = db.Column(db.String(20), default="")
    payer_payment_date = db.Column(db.String(10), default="")
    payer_movement_type = db.Column(db.String(20), default="")
    payment_verification_id = db.Column(db.String(120), default="")
    payment_verified_at = db.Column(db.DateTime, nullable=True)
    payment_verification_attempts = db.Column(db.Integer, default=0)
    payment_last_verification_at = db.Column(db.DateTime, nullable=True)


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


def _auto_approve_order(order, *, source_label: str = "AutoApprove", binance_auto: bool = False):
    """Approve a pending order, credit affiliate commission, notify user, and dispatch auto recharges."""
    if (order.status or "").lower() != "pending":
        print(f"[{source_label}] Order #{order.id} is '{order.status}', not pending. Aborting auto-approve.")
        return
    try:
        order.status = "approved"
        db.session.commit()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[{source_label}] DB error approving order #{order.id}: {exc}")
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

    has_auto_recharges = _order_has_auto_recharges(order)

    if not has_auto_recharges:
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
        result = _dispatch_order_auto_recharges(order, binance_auto=binance_auto)
        if result.get("summary", {}).get("total_units"):
            print(
                f"[{source_label}] Order #{order.id}: "
                f"{result['summary'].get('completed_units', 0)}/{result['summary'].get('total_units', 0)} completadas"
            )
        summary = result.get("summary") or {}
        if has_auto_recharges and summary.get("total_units", 0) > 0 and summary.get("completed_units", 0) >= summary.get("total_units", 0):
            _send_order_completed_email_if_needed(order)
    except Exception as exc:
        print(f"[{source_label}] Revendedores error for order #{order.id}: {exc}")



def _binance_auto_approve(order):
    """Approve a Binance-paid order and trigger Revendedores automation.

    Mirrors the approval logic of admin_orders_set_status but is called from
    the background thread after Binance API payment confirmation.
    ONLY triggers for orders where the item has auto_enabled=True in the mapping.
    """
    _auto_approve_order(order, source_label="BinanceAuto", binance_auto=True)


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


def amount_from_usd(amount_usd: float, currency: str) -> float:
    """Convert a USD amount into the order currency using the configured rate."""
    try:
        usd_amount = Decimal(str(amount_usd or 0.0))
    except Exception:
        usd_amount = Decimal("0")
    cur = (currency or "USD").upper()
    if cur == "USD":
        return float(usd_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    try:
        rate = Decimal(str(get_config_value("exchange_rate_bsd_per_usd", "0") or "0"))
    except Exception:
        rate = Decimal("0")
    if rate <= 0:
        return 0.0
    return int((usd_amount * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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
    direct_to_script = db.Column(db.Boolean, default=False)
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


class SmileOneConnection(db.Model):
    __tablename__ = "smileone_connections"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    page_url = db.Column(db.String(400), nullable=False)
    store_package_id = db.Column(db.Integer, nullable=False)
    smile_pid = db.Column(db.String(60), default="")
    server_id = db.Column(db.String(60), default="-1")
    product_slug = db.Column(db.String(120), default="")
    requires_zone = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
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
    catalog_path = (os.environ.get("REVENDEDORES_CATALOG_PATH") or os.environ.get("WEBB_CATALOG_PATH") or "/api/catalog/active").strip()
    recharge_path = (os.environ.get("REVENDEDORES_RECHARGE_PATH") or os.environ.get("WEBB_RECHARGE_PATH") or "/api/recharge/dynamic").strip()
    return base_url, api_key, catalog_path, recharge_path


def _game_script_env():
    base_url = (os.environ.get("GAME_SCRIPT_BASE_URL") or "").strip().rstrip("/")
    secret = (os.environ.get("GAME_SCRIPT_SECRET") or "").strip()
    raw_timeout = (os.environ.get("GAME_SCRIPT_TIMEOUT") or "60").strip()
    try:
        timeout = max(5, int(raw_timeout))
    except Exception:
        timeout = 60
    return base_url, secret, timeout


def _game_script_headers():
    _, secret, _ = _game_script_env()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if secret:
        headers["X-Game-Script-Secret"] = secret
    return headers


def _game_script_request(method: str, endpoint_path: str, payload=None, timeout=None):
    base_url, _, default_timeout = _game_script_env()
    if not base_url:
        return None, {"success": False, "error": "Falta configurar GAME_SCRIPT_BASE_URL"}
    request_timeout = timeout if timeout is not None else default_timeout
    url = f"{base_url}/{str(endpoint_path or '').lstrip('/')}"
    try:
        response = _requests_lib.request(
            method=str(method or "GET").upper(),
            url=url,
            json=payload,
            headers=_game_script_headers(),
            timeout=request_timeout,
        )
        try:
            data = response.json()
        except Exception:
            data = {
                "success": bool(response.ok),
                "error": (response.text or "").strip() or f"HTTP {response.status_code}",
            }
        return response, data
    except Exception as exc:
        return None, {"success": False, "error": f"Error conectando al Game Script: {str(exc)}"}


def _unit_delivery_source(unit):
    if bool(unit.get("direct_to_script")):
        return "game_script_direct"
    return "revendedores_api"


def _automation_source_from_units(units):
    sources = {str(_unit_delivery_source(unit)) for unit in (units or [])}
    if not sources:
        return "revendedores_api"
    if len(sources) == 1:
        return next(iter(sources))
    return "mixed_auto"


def _apply_dispatch_result_to_unit(unit, result):
    unit["status"] = str(result.get("status") or unit.get("status") or "pending").strip().lower()
    if unit["status"] not in {"pending", "processing", "completed", "failed", "not_found"}:
        unit["status"] = "failed"
    unit["player_name"] = str(result.get("player_name") or unit.get("player_name") or "")
    unit["reference_no"] = str(result.get("reference_no") or unit.get("reference_no") or "")
    unit["remaining_balance"] = result.get("remaining_balance", unit.get("remaining_balance"))
    unit["error"] = str(result.get("error") or "")
    unit["last_provider"] = str(result.get("provider") or _unit_delivery_source(unit))
    return unit


def _dispatch_game_script_unit(unit, order_obj, remote_meta):
    package_key = str(remote_meta.get("provider_package_key") or remote_meta.get("script_package_key") or "").strip()
    if not package_key:
        return {
            "status": "failed",
            "error": "El paquete remoto no tiene provider_package_key para envío directo al script",
            "provider": "game_script_direct",
        }

    payload = {
        "roleId": str(order_obj.customer_id or "").strip(),
        "packageKey": package_key,
        "requestId": str(unit.get("external_order_id") or "").strip(),
    }
    response, data = _game_script_request("POST", "comprar", payload=payload)
    if response is None:
        return {
            "status": "failed",
            "error": str(data.get("error") or "No se pudo conectar al Game Script"),
            "provider": "game_script_direct",
        }

    raw_status = str(data.get("status") or "").strip().lower()
    if int(response.status_code or 0) == 202 or raw_status in {"queued", "processing"}:
        return {
            "status": "processing",
            "error": str(data.get("message") or data.get("error") or "Solicitud en cola en Game Script"),
            "reference_no": str(data.get("requestId") or payload["requestId"]),
            "provider": "game_script_direct",
        }

    if bool(data.get("success")) and int(response.status_code or 0) < 400:
        return {
            "status": "completed",
            "player_name": str(data.get("jugador") or ""),
            "reference_no": str(data.get("orden") or data.get("requestId") or payload["requestId"]),
            "error": "",
            "provider": "game_script_direct",
        }

    error_text = str(data.get("error") or data.get("message") or "Recarga no completada en Game Script")
    return {
        "status": "failed",
        "error": error_text,
        "reference_no": str(data.get("requestId") or payload["requestId"]),
        "provider": "game_script_direct",
    }


def _verify_game_script_unit(unit):
    request_id = str(unit.get("external_order_id") or "").strip()
    if not request_id:
        return {
            "status": "failed",
            "error": "La recarga directa no tiene requestId para verificar",
            "provider": "game_script_direct",
        }

    response, data = _game_script_request("GET", f"requests/{request_id}", payload=None, timeout=20)
    if response is None:
        return {
            "status": "failed",
            "error": str(data.get("error") or "No se pudo consultar el Game Script"),
            "provider": "game_script_direct",
        }

    if int(response.status_code or 0) == 404:
        return {
            "status": "not_found",
            "error": str(data.get("error") or "requestId no encontrado en Game Script"),
            "provider": "game_script_direct",
        }

    request_status = str(data.get("status") or "").strip().lower()
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    if request_status == "completed" and bool(result.get("success", True)):
        return {
            "status": "completed",
            "player_name": str(result.get("jugador") or unit.get("player_name") or ""),
            "reference_no": str(result.get("orden") or data.get("requestId") or request_id),
            "error": "",
            "provider": "game_script_direct",
        }
    if request_status in {"queued", "processing"}:
        return {
            "status": "processing",
            "error": str((result or {}).get("message") or data.get("message") or "Solicitud aún en proceso en Game Script"),
            "reference_no": str(data.get("requestId") or request_id),
            "provider": "game_script_direct",
        }

    error_text = str((result or {}).get("error") or data.get("error") or data.get("message") or "Recarga falló en Game Script")
    return {
        "status": "failed",
        "error": error_text,
        "reference_no": str(data.get("requestId") or request_id),
        "provider": "game_script_direct",
    }


def _revendedores_catalog_paths():
    configured = (os.environ.get("REVENDEDORES_CATALOG_PATH") or os.environ.get("WEBB_CATALOG_PATH") or "").strip()
    paths = []
    for path in (configured, "/api/catalog/active", "/api/v1/products"):
        path = str(path or "").strip()
        if path and path not in paths:
            paths.append(path)
    return paths


def _revendedores_recharge_paths():
    configured = (os.environ.get("REVENDEDORES_RECHARGE_PATH") or os.environ.get("WEBB_RECHARGE_PATH") or "").strip()
    paths = []
    for path in (configured, "/api/recharge/dynamic", "/api/v1/recharge"):
        path = str(path or "").strip()
        if path and path not in paths:
            paths.append(path)
    return paths


def _revendedores_catalog_meta(remote_product_id, remote_package_id):
    try:
        query = RevendedoresCatalogItem.query.filter_by(remote_package_id=remote_package_id)
        if remote_product_id is None:
            query = query.filter(RevendedoresCatalogItem.remote_product_id.is_(None))
        else:
            query = query.filter_by(remote_product_id=remote_product_id)
        row = query.order_by(RevendedoresCatalogItem.id.desc()).first()
        if not row:
            return {}
        payload = json.loads(row.raw_json or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _synthetic_product_id(label):
    txt = str(label or "").strip().lower()
    if not txt:
        return None
    return 900000000 + (zlib.crc32(txt.encode("utf-8")) % 99999999)


def _normalize_rev_catalog_payload(payload):
    """Normaliza el catálogo remoto en formato legado o moderno.

    Formato legado esperado:
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

    Formato moderno esperado:
    {
      "ok": true,
      "items": [
        {
          "package_id": 17,
          "name": "86 Diamonds",
          "product_id": 3,
          "product_name": "Mobile Legends",
          "provider_package_id": 112,
          "provider_package_key": null
        }
      ]
    }
    """
    if not isinstance(payload, dict):
        return []

    items = payload.get("items")
    if isinstance(items, list):
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue

            local_package_id = item.get("package_id") or item.get("id")
            provider_package_id = item.get("provider_package_id") or item.get("gamepoint_package_id")
            remote_package_id_raw = provider_package_id if provider_package_id not in (None, "", 0, "0") else local_package_id
            try:
                remote_package_id = int(remote_package_id_raw)
            except (ValueError, TypeError):
                continue

            product_id_raw = item.get("product_id")
            remote_product_id = None
            if product_id_raw not in (None, ""):
                try:
                    remote_product_id = int(product_id_raw)
                except (ValueError, TypeError):
                    remote_product_id = None

            product_name = item.get("product_name") or item.get("game_name") or ""
            package_name = item.get("name") or item.get("title") or f"Paquete {remote_package_id}"
            raw_obj = dict(item)
            raw_obj["remote_local_package_id"] = local_package_id
            raw_obj["remote_lookup_package_id"] = remote_package_id

            out.append({
                "remote_product_id": remote_product_id,
                "remote_product_name": str(product_name or "").strip(),
                "remote_package_id": remote_package_id,
                "remote_package_name": str(package_name or "").strip(),
                "active": bool(item.get("active", True)),
                "raw_json": json.dumps(raw_obj, ensure_ascii=False),
            })
        return out

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


def _payment_verification_provider() -> str:
    provider = (get_config_value("payment_verification_provider", "") or "").strip().lower()
    if provider in ("pabilo", "ubii"):
        return provider
    if get_config_value("ubii_auto_verify_enabled", "0") == "1":
        return "ubii"
    if get_config_value("pabilo_auto_verify_enabled", "0") == "1":
        return "pabilo"
    return ""


def _payment_verification_provider_label(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "ubii":
        return "Ubii"
    if normalized == "pabilo":
        return "Pabilo"
    return ""


def _pabilo_config():
    enabled = (
        get_config_value("pabilo_auto_verify_enabled", "0") == "1"
        and _payment_verification_provider() == "pabilo"
    )
    method = (get_config_value("pabilo_method", "pm") or "pm").strip().lower()
    if method not in ("pm", "binance"):
        method = "pm"
    api_key = (get_config_value("pabilo_api_key", "") or "").strip()
    user_bank_id = (get_config_value("pabilo_user_bank_id", "") or "").strip()
    pm_user_bank_id = (get_config_value("pabilo_pm_user_bank_id", "") or "").strip()
    binance_user_bank_id = (get_config_value("pabilo_binance_user_bank_id", "") or "").strip()
    base_url = (
        get_config_value("pabilo_base_url", "")
        or os.environ.get("PABILO_BASE_URL", "https://api.pabilo.app")
        or "https://api.pabilo.app"
    ).strip().rstrip("/")
    try:
        timeout = int(get_config_value("pabilo_timeout_seconds", str(int(os.environ.get("PABILO_TIMEOUT", "30")))))
    except Exception:
        timeout = int(os.environ.get("PABILO_TIMEOUT", "30"))
    try:
        timeout = max(timeout, 5)
    except Exception:
        timeout = 30
    enforce_method = get_config_value("pabilo_enforce_method", "1") == "1"
    default_movement_type = (get_config_value("pabilo_default_movement_type", "") or "").strip().upper()
    if default_movement_type not in ("GENERIC", "MOVIL_PAY", "TRANSFER"):
        default_movement_type = ""
    user_bank_ids = {
        "pm": pm_user_bank_id,
        "binance": binance_user_bank_id,
    }
    if user_bank_id and not user_bank_ids.get(method):
        user_bank_ids[method] = user_bank_id
    return {
        "enabled": enabled,
        "method": method,
        "api_key": api_key,
        "user_bank_id": user_bank_id,
        "pm_user_bank_id": pm_user_bank_id,
        "binance_user_bank_id": binance_user_bank_id,
        "user_bank_ids": user_bank_ids,
        "base_url": base_url,
        "timeout": timeout,
        "enforce_method": enforce_method,
        "default_movement_type": default_movement_type,
    }


def _ubii_config():
    method = (get_config_value("ubii_method", "pm") or "pm").strip().lower()
    if method not in ("pm", "binance"):
        method = "pm"
    text_field = (get_config_value("ubii_text_field", "texto") or "texto").strip()
    if not text_field:
        text_field = "texto"
    amount_regex = (
        get_config_value("ubii_amount_regex", r"Bs\.\s*([\d\.,]+)")
        or r"Bs\.\s*([\d\.,]+)"
    ).strip()
    reference_regex = _ubii_normalize_reference_regex(get_config_value("ubii_reference_regex", r"referencia\D*(\d+)"))
    webhook_secret = (get_config_value("ubii_webhook_secret", "") or "").strip()
    return {
        "enabled": _payment_verification_provider() == "ubii",
        "method": method,
        "text_field": text_field,
        "amount_regex": amount_regex,
        "reference_regex": reference_regex,
        "webhook_secret": webhook_secret,
    }


def _pabilo_normalize_method(raw_method: str) -> str:
    method = (raw_method or "pm").strip().lower()
    return method if method in ("pm", "binance") else "pm"


def _pabilo_user_bank_id_for_method(method: str) -> str:
    cfg = _pabilo_config()
    normalized = _pabilo_normalize_method(method)
    configured = str((cfg.get("user_bank_ids") or {}).get(normalized) or "").strip()
    if configured:
        return configured
    legacy = str(cfg.get("user_bank_id") or "").strip()
    if legacy and normalized == _pabilo_normalize_method(cfg.get("method") or "pm"):
        return legacy
    return ""


def _pabilo_verify_endpoint(user_bank_id: str, base_url: str = "") -> str:
    raw_base_url = str(base_url or "").strip()
    if not raw_base_url:
        raw_base_url = "https://api.pabilo.app"
    if raw_base_url.startswith("http://"):
        raw_base_url = "https://" + raw_base_url[len("http://"):]
    elif not raw_base_url.startswith("https://"):
        raw_base_url = "https://" + raw_base_url.lstrip("/")

    lowered = raw_base_url.lower()
    if "pabilo.app/docs" in lowered or lowered.endswith("pabilo.app"):
        raw_base_url = "https://api.pabilo.app"
        lowered = raw_base_url.lower()
    raw_base_url = raw_base_url.rstrip("/")

    if "/userbankpayment/" in lowered:
        if not lowered.endswith("/betaserio"):
            raw_base_url = raw_base_url + "/betaserio"
        return raw_base_url

    return f"{raw_base_url}/userbankpayment/{str(user_bank_id or '').strip()}/betaserio"


def _pabilo_datetime_to_iso(value) -> str:
    if isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return ""
    return str(value or "")


def _pabilo_get_payment_state(order_obj):
    state = _load_order_automation_state(order_obj)
    raw = state.get("payment_verify")
    raw_state = raw if isinstance(raw, dict) else {}
    attempts = 0
    try:
        attempts = int(order_obj.payment_verification_attempts or raw_state.get("attempts") or 0)
    except Exception:
        attempts = 0
    verified = bool(order_obj.payment_verified_at or raw_state.get("verified"))
    verification_id = str(order_obj.payment_verification_id or raw_state.get("verification_id") or "")
    last_checked_at = _pabilo_datetime_to_iso(order_obj.payment_last_verification_at) or str(raw_state.get("last_checked_at") or "")
    provider = str(raw_state.get("provider") or ("pabilo" if (attempts or verified or verification_id) else ""))
    return {
        **raw_state,
        "provider": provider,
        "attempts": attempts,
        "verified": verified,
        "verification_id": verification_id,
        "last_checked_at": last_checked_at,
    }


def _pabilo_set_payment_state(order_obj, payment_state: dict):
    state = _load_order_automation_state(order_obj)
    state["payment_verify"] = payment_state or {}
    _save_order_automation_state(order_obj, state)


def _ubii_parse_amount(raw_value):
    cleaned = str(raw_value or "").strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace(" ", "")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _ubii_normalize_reference_regex(raw_value) -> str:
    regex = str(raw_value or "").strip()
    if not regex or regex in (r"referencia\s+(\d+)", r"referencia\s*(\d+)"):
        return r"referencia\D*(\d+)"
    return regex


def _ubii_collect_payload_text(payload: dict, cfg: dict | None = None) -> str:
    if not isinstance(payload, dict):
        return ""

    config = cfg or _ubii_config()
    text_field = str(config.get("text_field") or "texto").strip() or "texto"
    preferred_keys = [
        text_field,
        "texto",
        "text",
        "message",
        "body",
        "cuerpo",
        "notification_text",
        "notification_body",
        "title",
        "titulo",
        "notification_title",
        "subject",
    ]
    for key in preferred_keys:
        raw_value = payload.get(key)
        if raw_value is None or isinstance(raw_value, (dict, list, tuple, set)):
            continue
        text = str(raw_value).strip()
        if not text:
            continue
        return text
    return ""


def _ubii_extract_notification_data(payload: dict, cfg: dict | None = None):
    config = cfg or _ubii_config()
    source_text = _ubii_collect_payload_text(payload, config)

    amount_raw = ""
    reference_raw = ""

    amount_match = None
    reference_match = None
    amount_pattern = str(config.get("amount_regex") or "").strip()
    reference_pattern = str(config.get("reference_regex") or "").strip()
    try:
        if amount_pattern and source_text:
            amount_match = re.search(amount_pattern, source_text, re.IGNORECASE)
    except re.error:
        amount_match = None
    try:
        if reference_pattern and source_text:
            reference_match = re.search(reference_pattern, source_text, re.IGNORECASE)
    except re.error:
        reference_match = None

    if not amount_raw:
        amount_raw = (amount_match.group(1) if amount_match else "") or ""
    if not reference_raw:
        reference_raw = (reference_match.group(1) if reference_match else "") or ""
    return {
        "text": source_text,
        "amount_raw": amount_raw.strip(),
        "amount": _ubii_parse_amount(amount_raw),
        "reference": _pabilo_normalize_reference_value(reference_raw),
    }


def _ubii_order_amount_matches(order_obj, expected_amount: Decimal | None) -> bool:
    if expected_amount is None:
        return False
    try:
        order_amount = Decimal(str(order_obj.amount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return False
    return expected_amount >= order_amount


def _ubii_normalize_reference_value(value) -> str:
    normalized = _pabilo_normalize_reference_value(value)
    if not normalized:
        return ""
    if normalized.isdigit():
        stripped = normalized.lstrip("0")
        return stripped or "0"
    return normalized


def _ubii_reference_match_key(value) -> str:
    normalized = _pabilo_normalize_reference_value(value)
    if not normalized:
        return ""
    if normalized.isdigit():
        return normalized[-4:]
    return normalized


def _ubii_find_matching_order(reference: str, amount: Decimal | None, method: str):
    normalized_reference = _ubii_normalize_reference_value(reference)
    reference_match_key = _ubii_reference_match_key(reference)
    if not normalized_reference or not reference_match_key:
        return None, "Referencia no encontrada en la notificación", False

    normalized_method = _pabilo_normalize_method(method or "pm")
    pending_rows = Order.query.filter(Order.status == "pending").order_by(Order.created_at.desc()).all()
    candidates = [
        row for row in pending_rows
        if _ubii_reference_match_key(row.reference or "") == reference_match_key
        and _pabilo_normalize_method(row.method or "") == normalized_method
    ]

    if amount is not None:
        amount_candidates = [row for row in candidates if _ubii_order_amount_matches(row, amount)]
        if amount_candidates:
            candidates = amount_candidates
        elif candidates:
            return None, "La referencia existe pero el monto no coincide con ninguna orden pendiente", False

    if len(candidates) > 1:
        return None, "Hay varias órdenes pendientes con esa referencia; incluye el monto exacto para decidir", False
    if len(candidates) == 1:
        return candidates[0], "", False

    processed_rows = Order.query.filter(Order.status.in_(["approved", "delivered"]))\
        .order_by(Order.created_at.desc()).all()
    processed = [
        row for row in processed_rows
        if _ubii_reference_match_key(row.reference or "") == reference_match_key
        and _pabilo_normalize_method(row.method or "") == normalized_method
        and _ubii_order_amount_matches(row, amount)
    ]
    if processed:
        return processed[0], "La orden ya estaba procesada anteriormente", True

    return None, "No existe una orden pendiente que coincida con la referencia recibida", False


def _ubii_verify_and_update_order(order_obj, extracted: dict, *, payload: dict | None = None, source: str = "ubii_webhook"):
    current = _pabilo_get_payment_state(order_obj)
    attempts = 0
    try:
        attempts = int(order_obj.payment_verification_attempts or current.get("attempts") or 0)
    except Exception:
        attempts = 0

    checked_at = datetime.utcnow()
    now_iso = checked_at.isoformat()
    verification_id = str(extracted.get("reference") or order_obj.reference or order_obj.payment_verification_id or "")
    message = "Pago verificado desde webhook Ubii"
    request_url = "/webhook-ubii"
    if source == "admin_manual_ubii":
        message = "Coincidencia manual basada en texto de notificacion Ubii; no se consulto una API externa"
        request_url = f"/admin/orders/{order_obj.id}/verify-ubii"

    order_obj.payment_verification_attempts = attempts + 1
    order_obj.payment_last_verification_at = checked_at
    order_obj.payment_verified_at = checked_at
    order_obj.payment_verification_id = verification_id

    state = {
        "provider": "ubii",
        "enabled": bool(_ubii_config().get("enabled")),
        "method": _pabilo_normalize_method(order_obj.method or ""),
        "attempts": attempts + 1,
        "last_checked_at": now_iso,
        "verified": True,
        "verification_id": verification_id,
        "message": message,
        "source": source,
        "last_request_url": request_url,
        "last_request_payload": {
            "text": str(extracted.get("text") or ""),
            "amount": str(extracted.get("amount") or ""),
            "amount_raw": str(extracted.get("amount_raw") or ""),
            "reference": verification_id,
            "payload": payload or {},
        },
        "last_response_status": 200,
    }
    _pabilo_set_payment_state(order_obj, state)
    db.session.commit()

    if (order_obj.status or "").lower() == "pending":
        _auto_approve_order(order_obj, source_label="UbiiAuto", binance_auto=False)

    return {
        "ok": True,
        "verified": True,
        "verification_id": verification_id,
        "message": message,
        "order_status": order_obj.status,
        "request_meta": {
            "url": request_url,
            "payload": state.get("last_request_payload") or {},
            "status_code": 200,
        },
    }


def _validate_order_reference_value(order_obj, reference: str, *, exclude_order_id: int | None = None):
    ref = str(reference or "").strip()
    if not ref:
        return False, "Referencia requerida"

    method = (order_obj.method or "").strip().lower()
    is_binance_auto = (
        method == "binance"
        and get_config_value("binance_auto_enabled", "0") == "1"
        and len(ref) == 6
        and ref.isalnum()
    )
    if is_binance_auto:
        if not ref.isalnum() or len(ref) != 6:
            return False, "Código de verificación inválido"
    else:
        if not (ref.isdigit() and 1 <= len(ref) <= 21):
            return False, "La referencia debe ser numérica (máximo 21 dígitos)"

    existing_query = Order.query.filter(
        Order.reference == ref,
        Order.status == "pending",
    )
    if exclude_order_id:
        existing_query = existing_query.filter(Order.id != int(exclude_order_id))
    existing_pending = existing_query.first()
    if existing_pending:
        return False, "Esa referencia ya está asignada a otra orden pendiente"

    return True, ref


def _normalize_order_idempotency_key(raw_value) -> str:
    return str(raw_value or "").strip()[:120]


def _find_order_by_idempotency_key(key: str):
    safe_key = _normalize_order_idempotency_key(key)
    if not safe_key:
        return None
    return Order.query.filter(Order.idempotency_key == safe_key).order_by(Order.id.desc()).first()


def _reset_order_payment_verification_state(order_obj, *, message: str, source: str = "admin_reference_edit"):
    order_obj.payment_verification_id = ""
    order_obj.payment_verified_at = None
    order_obj.payment_verification_attempts = 0
    order_obj.payment_last_verification_at = None
    active_provider = _payment_verification_provider() or "pabilo"
    _pabilo_set_payment_state(order_obj, {
        "provider": active_provider,
        "enabled": bool(_pabilo_config().get("enabled")) if active_provider == "pabilo" else bool(_ubii_config().get("enabled")),
        "method": _pabilo_normalize_method(order_obj.method or ""),
        "attempts": 0,
        "verified": False,
        "verification_id": "",
        "last_checked_at": "",
        "message": str(message or ""),
        "source": str(source or "admin_reference_edit"),
        "last_request_url": "",
        "last_request_payload": {},
        "last_response_status": 0,
    })


def _pabilo_exact_amount_value(order_obj):
    if not order_obj:
        return None
    try:
        amount_decimal = Decimal(str(order_obj.amount or 0)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amount_decimal <= 0:
        return None
    if amount_decimal != amount_decimal.to_integral_value():
        return None
    return int(amount_decimal.to_integral_value())


def _pabilo_normalize_reference_value(value) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    return re.sub(r"[^a-z0-9]", "", raw_value.lower())


def _pabilo_integral_amount_value(value):
    if value in (None, ""):
        return None
    try:
        amount_decimal = Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amount_decimal <= 0:
        return None
    if amount_decimal != amount_decimal.to_integral_value():
        return None
    return int(amount_decimal.to_integral_value())


def _pabilo_extract_response_values(payload: dict, candidate_keys) -> list:
    normalized_keys = {re.sub(r"[^a-z0-9]", "", str(key).lower()) for key in candidate_keys}
    collected = []

    def _walk(node):
        if len(collected) >= 30:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized_key in normalized_keys and not isinstance(value, (dict, list, tuple, set)):
                    collected.append(value)
                if isinstance(value, (dict, list, tuple)):
                    _walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(payload or {})
    return collected


def _pabilo_response_match_info(response_data: dict, order_obj) -> dict:
    return _pabilo_response_match_info_for_reference(
        response_data,
        order_obj,
        str(order_obj.reference or "").strip(),
    )


def _pabilo_response_match_info_for_reference(response_data: dict, order_obj, reference_value: str) -> dict:
    expected_amount = _pabilo_exact_amount_value(order_obj)
    expected_reference = _pabilo_normalize_reference_value(reference_value)

    amount_candidates_raw = _pabilo_extract_response_values(
        response_data,
        (
            "amount",
            "monto",
            "payment_amount",
            "amount_payment",
            "amount_paid",
            "paid_amount",
            "transaction_amount",
            "transfer_amount",
        ),
    )
    reference_candidates_raw = _pabilo_extract_response_values(
        response_data,
        (
            "bank_reference",
            "bankreference",
            "reference",
            "payment_reference",
            "reference_payment",
            "operation_reference",
            "transfer_reference",
            "transaction_reference",
            "nro_referencia",
            "numero_referencia",
        ),
    )

    amount_candidates = []
    for candidate in amount_candidates_raw:
        normalized_amount = _pabilo_integral_amount_value(candidate)
        if normalized_amount is not None and normalized_amount not in amount_candidates:
            amount_candidates.append(normalized_amount)

    reference_candidates = []
    for candidate in reference_candidates_raw:
        normalized_reference = _pabilo_normalize_reference_value(candidate)
        if normalized_reference and normalized_reference not in reference_candidates:
            reference_candidates.append(normalized_reference)

    amount_present = len(amount_candidates) > 0
    reference_present = len(reference_candidates) > 0
    amount_matches = expected_amount is not None and expected_amount in amount_candidates
    reference_matches = bool(expected_reference) and expected_reference in reference_candidates
    amount_valid = (not amount_present) or amount_matches
    reference_valid = (not reference_present) or reference_matches

    return {
        "expected_amount": expected_amount,
        "expected_reference": expected_reference,
        "amount_present": amount_present,
        "reference_present": reference_present,
        "amount_matches": amount_matches,
        "reference_matches": reference_matches,
        "amount_valid": amount_valid,
        "reference_valid": reference_valid,
        "amount_candidates": amount_candidates,
        "reference_candidates": reference_candidates,
        "matched": amount_valid and reference_valid,
    }


def _pabilo_payload_movement_type(order_obj) -> str:
    movement_type = str(order_obj.payer_movement_type or _pabilo_config().get("default_movement_type") or "").strip().upper()
    if movement_type in ("GENERIC", "MOVIL_PAY", "TRANSFER"):
        return movement_type
    return ""


def _is_pabilo_payment_method_enforced_for_order(order_obj) -> bool:
    cfg = _pabilo_config()
    if not cfg.get("enabled") or not cfg.get("enforce_method"):
        return False
    return _order_has_auto_recharges(order_obj)


def _pabilo_request_info(order_obj) -> dict:
    return _pabilo_request_info_with_reference(order_obj, str(order_obj.reference or "").strip())


def _pabilo_request_info_with_reference(order_obj, reference_value: str) -> dict:
    cfg = _pabilo_config()
    order_method = _pabilo_normalize_method(order_obj.method or "")
    expected_method = _pabilo_normalize_method(cfg.get("method") or "pm")
    enabled = bool(cfg.get("enabled"))
    api_key = str(cfg.get("api_key") or "").strip()
    user_bank_id = _pabilo_user_bank_id_for_method(order_method)
    safe_reference = str(reference_value or "").strip()
    reasons = []

    if not enabled:
        reasons.append("Pabilo esta desactivado")
    if order_method != expected_method:
        reasons.append(
            f"Metodo incompatible: la orden usa {order_method.upper() or 'N/A'} y Pabilo exige {expected_method.upper()}"
        )
    if not api_key:
        reasons.append("Falta API key de Pabilo")
    if not user_bank_id:
        reasons.append(f"Falta UserBankId de Pabilo para {order_method.upper() or expected_method.upper()}")
    if not safe_reference:
        reasons.append("La orden no tiene referencia")
    if _pabilo_exact_amount_value(order_obj) is None:
        reasons.append("La orden no tiene un monto exacto valido para consultar en Pabilo")

    return {
        "requestable": len(reasons) == 0,
        "reason": "; ".join(reasons),
        "reasons": reasons,
        "enabled": enabled,
        "expected_method": expected_method,
        "order_method": order_method,
        "has_api_key": bool(api_key),
        "user_bank_id": user_bank_id,
    }


def _pabilo_build_payload(order_obj) -> dict:
    return _pabilo_build_payload_with_reference(order_obj, str(order_obj.reference or "").strip())


def _pabilo_build_payload_with_reference(order_obj, reference_value: str) -> dict:
    exact_amount = _pabilo_exact_amount_value(order_obj)
    payload = {
        "amount": exact_amount,
        "bank_reference": str(reference_value or "").strip(),
    }

    if str(order_obj.payer_dni_number or "").strip():
        payload["dni_pagador"] = {
            "dniType": str(order_obj.payer_dni_type or "V").strip().upper(),
            "dniNumber": str(order_obj.payer_dni_number or "").strip(),
        }
    if str(order_obj.payer_phone or "").strip():
        payload["phone_pagador"] = str(order_obj.payer_phone or "").strip()
    if str(order_obj.payer_bank_origin or "").strip():
        payload["bank_origin"] = str(order_obj.payer_bank_origin or "").strip()
    if order_obj.payer_payment_date:
        try:
            payload["fecha_pago"] = order_obj.payer_payment_date.strftime("%Y-%m-%d")
        except Exception:
            payload["fecha_pago"] = str(order_obj.payer_payment_date)

    movement_type = _pabilo_payload_movement_type(order_obj)
    if movement_type:
        payload["movement_type"] = movement_type

    return payload


def _pabilo_eligibility_info(order_obj) -> dict:
    request_info = _pabilo_request_info(order_obj)
    auto_mapped = bool(_order_has_auto_recharges(order_obj))
    reasons = list(request_info.get("reasons") or [])
    if not auto_mapped:
        reasons.append("La orden no tiene recargas mapeadas para automatizacion")

    return {
        "eligible": len(reasons) == 0,
        "reason": "; ".join(reasons),
        "reasons": reasons,
        "enabled": bool(request_info.get("enabled")),
        "expected_method": request_info.get("expected_method"),
        "order_method": request_info.get("order_method"),
        "auto_mapped": auto_mapped,
        "has_api_key": bool(request_info.get("has_api_key")),
        "user_bank_id": request_info.get("user_bank_id"),
        "requestable": bool(request_info.get("requestable")),
    }


def _order_is_pabilo_eligible(order_obj) -> bool:
    return bool(_pabilo_eligibility_info(order_obj).get("eligible"))


def _pabilo_verify_payment_once(order_obj, *, reference_override: str = "", reference_source: str = "manual"):
    if not order_obj:
        return {"ok": False, "verified": False, "message": "Orden inválida"}
    candidate_reference = str(reference_override or order_obj.reference or "").strip()
    request_info = _pabilo_request_info_with_reference(order_obj, candidate_reference)
    if not request_info.get("requestable"):
        return {
            "ok": False,
            "verified": False,
            "message": request_info.get("reason") or "La orden no se puede consultar en Pabilo",
            "eligibility": _pabilo_eligibility_info(order_obj),
            "request": request_info,
        }
    cfg = _pabilo_config()
    if not candidate_reference:
        return {"ok": False, "verified": False, "message": "La orden no tiene referencia"}

    order_method = _pabilo_normalize_method(order_obj.method or "")
    user_bank_id = _pabilo_user_bank_id_for_method(order_method)
    if not user_bank_id:
        return {"ok": False, "verified": False, "message": f"Falta UserBankId de Pabilo para {order_method.upper()}", "request": request_info}

    configured_url = _pabilo_verify_endpoint(user_bank_id, str(cfg.get('base_url') or '').strip())
    official_url = _pabilo_verify_endpoint(user_bank_id, "https://api.pabilo.app")
    url = configured_url
    payload = _pabilo_build_payload_with_reference(order_obj, candidate_reference)
    headers = {
        "Content-Type": "application/json",
        "appKey": cfg.get("api_key"),
    }
    max_attempts = 3
    retry_delay_seconds = 2

    def _decode_response_json(resp_obj):
        try:
            return resp_obj.json()
        except Exception:
            return {}

    def _post_verify(current_url, current_payload):
        try:
            current_resp = _requests_lib.post(
                current_url,
                json=current_payload,
                headers=headers,
                timeout=cfg.get("timeout", 30),
            )
        except _requests_lib.exceptions.Timeout:
            return None, current_url, current_payload, {
                "ok": False,
                "verified": False,
                "message": "Pabilo no respondió a tiempo",
                "request_meta": {"url": current_url, "payload": current_payload, "status_code": 0},
            }
        except _requests_lib.exceptions.ConnectionError:
            return None, current_url, current_payload, {
                "ok": False,
                "verified": False,
                "message": "No se pudo conectar con Pabilo",
                "request_meta": {"url": current_url, "payload": current_payload, "status_code": 0},
            }
        except Exception as exc:
            return None, current_url, current_payload, {
                "ok": False,
                "verified": False,
                "message": f"Error consultando Pabilo: {exc}",
                "request_meta": {"url": current_url, "payload": current_payload, "status_code": 0},
            }

        response_text = ""
        try:
            response_text = current_resp.text or ""
        except Exception:
            response_text = ""

        if "movement_type" in current_payload and int(current_resp.status_code or 0) >= 400:
            lowered_response = response_text.lower()
            if "movement_type is not available for this bank" in lowered_response:
                retry_payload = dict(current_payload)
                retry_payload.pop("movement_type", None)
                try:
                    current_resp = _requests_lib.post(
                        current_url,
                        json=retry_payload,
                        headers=headers,
                        timeout=cfg.get("timeout", 30),
                    )
                    current_payload = retry_payload
                except Exception:
                    pass

        if int(current_resp.status_code or 0) == 405 and official_url != configured_url:
            try:
                current_resp = _requests_lib.post(
                    official_url,
                    json=current_payload,
                    headers=headers,
                    timeout=cfg.get("timeout", 30),
                )
                current_url = official_url
            except Exception:
                pass

        return current_resp, current_url, current_payload, None

    last_result = None
    for attempt in range(1, max_attempts + 1):
        resp, url, payload, request_error = _post_verify(url, payload)
        if request_error is not None:
            request_meta = dict(request_error.get("request_meta") or {})
            request_meta["attempt"] = attempt
            request_meta["max_attempts"] = max_attempts
            request_error["request_meta"] = request_meta
            last_result = request_error
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            return request_error

        data = _decode_response_json(resp)
        payload_data = data.get("data") if isinstance(data.get("data"), dict) else data
        if not isinstance(payload_data, dict):
            payload_data = {}
        ub_payment = payload_data.get("user_bank_payment") if isinstance(payload_data.get("user_bank_payment"), dict) else {}

        accepted_statuses = {
            "verified", "approve", "approved", "aprobado",
            "success", "successful", "completed", "completada",
            "paid", "pagado",
        }
        payment_status = str(
            ub_payment.get("status")
            or payload_data.get("status_payment")
            or payload_data.get("status")
            or ""
        ).strip().lower()
        root_status = str(data.get("status") or "").strip().lower()
        root_message = str(data.get("message") or "").strip().lower()
        verified_flag = bool(payload_data.get("verified") or data.get("verified"))
        verified = (
            (payment_status in accepted_statuses)
            or (root_status in accepted_statuses)
            or ("payment confirmed" in root_message)
            or verified_flag
        )

        verification_id = (
            ub_payment.get("id")
            or ub_payment.get("bank_reference_id")
            or payload_data.get("id")
            or payload_data.get("verification_id")
            or payload_data.get("payment_id")
            or data.get("id")
            or data.get("verification_id")
        )
        request_meta = {
            "url": url,
            "payload": payload,
            "status_code": int(resp.status_code or 0),
            "attempt": attempt,
            "max_attempts": max_attempts,
        }

        if resp.status_code in (401, 403):
            return {
                "ok": False,
                "verified": False,
                "message": "La API key de Pabilo es inválida o no tiene permisos",
                "response": data,
                "request_meta": request_meta,
            }
        if resp.status_code == 402:
            return {
                "ok": False,
                "verified": False,
                "message": "La cuenta de Pabilo no tiene créditos suficientes",
                "response": data,
                "request_meta": request_meta,
            }
        if resp.status_code == 404:
            last_result = {
                "ok": True,
                "verified": False,
                "message": "El pago todavía no aparece en Pabilo",
                "response": data,
                "request_meta": request_meta,
            }
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            return last_result
        if resp.status_code >= 500:
            last_result = {
                "ok": False,
                "verified": False,
                "message": str(data.get("message") or data.get("error") or f"Error HTTP {resp.status_code} en Pabilo"),
                "response": data,
                "request_meta": request_meta,
            }
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            return last_result
        if resp.status_code >= 400:
            error_msg = str(data.get("message") or data.get("error") or f"Error HTTP {resp.status_code} en Pabilo").lower()
            bank_failure_keywords = [
                "banco", "bank", "timeout", "tiempo", "temporalmente",
                "temporarily", "unavailable", "no disponible", "intente",
                "try again", "reintentar", "service", "servicio",
                "fallo", "failed", "error de conexión", "connection",
            ]
            is_bank_failure = any(kw in error_msg for kw in bank_failure_keywords)
            if is_bank_failure and attempt < max_attempts:
                last_result = {
                    "ok": False,
                    "verified": False,
                    "message": str(data.get("message") or data.get("error") or f"Error HTTP {resp.status_code} en Pabilo"),
                    "response": data,
                    "request_meta": request_meta,
                }
                time.sleep(retry_delay_seconds)
                continue
            return {
                "ok": False,
                "verified": False,
                "message": str(data.get("message") or data.get("error") or f"Error HTTP {resp.status_code} en Pabilo"),
                "response": data,
                "request_meta": request_meta,
            }

        if not verified:
            last_result = {
                "ok": True,
                "verified": False,
                "message": str(data.get("message") or payload_data.get("message") or "La transacción aún no está verificada en Pabilo"),
                "response": data,
                "request_meta": request_meta,
            }
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            return last_result

        match_info = _pabilo_response_match_info_for_reference(data, order_obj, candidate_reference)
        if not match_info.get("matched"):
            mismatch_reasons = []
            if match_info.get("reference_present") and not match_info.get("reference_matches"):
                mismatch_reasons.append("la referencia devuelta por Pabilo no coincide con la orden")
            if match_info.get("amount_present") and not match_info.get("amount_matches"):
                mismatch_reasons.append("el monto devuelto por Pabilo no coincide con la orden")

            return {
                "ok": True,
                "verified": False,
                "message": "; ".join(mismatch_reasons) or "La respuesta de Pabilo no coincide con la orden",
                "response": data,
                "request_meta": request_meta,
                "validation": match_info,
                "matched_reference": candidate_reference,
                "matched_reference_source": reference_source,
            }

        if not verification_id:
            verification_id = f"fallback:{order_method}:{candidate_reference}"

        return {
            "ok": True,
            "verified": True,
            "verification_id": str(verification_id),
            "message": "Pago verificado en Pabilo",
            "response": data,
            "request_meta": request_meta,
            "validation": match_info,
            "matched_reference": candidate_reference,
            "matched_reference_source": reference_source,
        }

    return last_result or {
        "ok": False,
        "verified": False,
        "message": "No se pudo completar la verificación en Pabilo",
        "request_meta": {"url": url, "payload": payload, "status_code": 0, "attempt": max_attempts, "max_attempts": max_attempts},
    }


def _pabilo_should_try_capture_reference_fallback(result: dict) -> bool:
    validation = result.get("validation") or {}
    if isinstance(validation, dict) and bool(
        validation.get("reference_present")
        and not validation.get("reference_matches")
        and validation.get("amount_valid")
    ):
        return True

    request_meta = result.get("request_meta") or {}
    status_code = int((request_meta.get("status_code") or 0)) if isinstance(request_meta, dict) else 0
    message = str(result.get("message") or "").strip().lower()
    not_found_hints = (
        "todavía no aparece",
        "todavia no aparece",
        "no aparece en pabilo",
        "no se encontró",
        "no se encontro",
        "not found",
        "payment not found",
    )
    return bool(
        status_code == 404
        or any(hint in message for hint in not_found_hints)
    )


def _pabilo_verify_payment(order_obj):
    manual_reference = str(order_obj.reference or "").strip()
    capture_reference = str(getattr(order_obj, "capture_reference", "") or "").strip()

    primary_result = _pabilo_verify_payment_once(
        order_obj,
        reference_override=manual_reference,
        reference_source="manual",
    )
    if primary_result.get("verified"):
        return primary_result
    if not capture_reference:
        return primary_result
    if _pabilo_normalize_reference_value(capture_reference) == _pabilo_normalize_reference_value(manual_reference):
        return primary_result
    if not _pabilo_should_try_capture_reference_fallback(primary_result):
        return primary_result

    fallback_result = _pabilo_verify_payment_once(
        order_obj,
        reference_override=capture_reference,
        reference_source="capture",
    )
    fallback_result["fallback_used"] = True
    fallback_result["manual_result"] = {
        "verified": bool(primary_result.get("verified")),
        "message": str(primary_result.get("message") or ""),
        "validation": primary_result.get("validation") or {},
    }
    if not fallback_result.get("verified") and not fallback_result.get("message"):
        fallback_result["message"] = str(primary_result.get("message") or "")
    return fallback_result


def _pabilo_verify_and_update_order(order_obj, *, auto_approve_on_verified: bool = False, source: str = "manual"):
    current = _pabilo_get_payment_state(order_obj)
    attempts = 0
    try:
        attempts = int(order_obj.payment_verification_attempts or current.get("attempts") or 0)
    except Exception:
        attempts = 0

    result = _pabilo_verify_payment(order_obj)
    checked_at = datetime.utcnow()
    now_iso = checked_at.isoformat()
    order_obj.payment_verification_attempts = attempts + 1
    order_obj.payment_last_verification_at = checked_at
    if result.get("verified"):
        order_obj.payment_verified_at = checked_at
        order_obj.payment_verification_id = str(result.get("verification_id") or order_obj.payment_verification_id or "")

    state = {
        **current,
        "provider": "pabilo",
        "enabled": bool(_pabilo_config().get("enabled")),
        "method": _pabilo_normalize_method(order_obj.method or ""),
        "attempts": attempts + 1,
        "last_checked_at": now_iso,
        "verified": bool(result.get("verified")),
        "verification_id": str(result.get("verification_id") or order_obj.payment_verification_id or ""),
        "message": str(result.get("message") or ""),
        "source": source,
        "manual_reference": str(order_obj.reference or ""),
        "capture_reference": str(getattr(order_obj, "capture_reference", "") or ""),
        "matched_reference": str(result.get("matched_reference") or ""),
        "matched_reference_source": str(result.get("matched_reference_source") or ""),
        "fallback_used": bool(result.get("fallback_used")),
        "last_request_url": str(((result.get("request_meta") or {}).get("url") or "")),
        "last_request_payload": (result.get("request_meta") or {}).get("payload") or {},
        "last_response_status": int(((result.get("request_meta") or {}).get("status_code") or 0)),
    }
    _pabilo_set_payment_state(order_obj, state)
    db.session.commit()

    if result.get("verified") and auto_approve_on_verified and (order_obj.status or "").lower() == "pending":
        _auto_approve_order(order_obj, source_label="PabiloAuto", binance_auto=False)

    return {
        "ok": bool(result.get("ok")),
        "verified": bool(result.get("verified")),
        "verification_id": state.get("verification_id") or "",
        "message": state.get("message") or "",
        "order_status": order_obj.status,
        "request_meta": result.get("request_meta") or {},
    }


def _send_order_completed_email_if_needed(order_obj, state: dict | None = None) -> bool:
    if not order_obj or not (order_obj.email or "").strip():
        return False

    auto_state = state if isinstance(state, dict) else _load_order_automation_state(order_obj)
    if auto_state.get("completion_email_sent"):
        return False

    pkg = StorePackage.query.get(order_obj.store_package_id)
    it = GamePackageItem.query.get(order_obj.item_id) if order_obj.item_id else None
    brand = _email_brand()
    html, text = build_order_approved_email(order_obj, pkg, it)

    try:
        send_email_html(order_obj.email, f"Orden #{order_obj.id} aprobada - {brand}", html, text)
    except Exception:
        send_email_async(order_obj.email, f"Orden #{order_obj.id} aprobada - {brand}", text)

    auto_state["completion_email_sent"] = True
    auto_state["completion_email_sent_at"] = datetime.utcnow().isoformat()
    _save_order_automation_state(order_obj, auto_state)
    db.session.commit()
    return True


def _thanks_progress_payload(order_obj):
    """Build dynamic progress state for the thank-you page.

    Returns tracker visibility for orders mapped to auto-recharge + active
    payment verification provider flow.
    """
    auto_mapped = _order_has_auto_recharges(order_obj)
    pay_state = _pabilo_get_payment_state(order_obj)
    active_provider = _payment_verification_provider()
    provider = str(pay_state.get("provider") or active_provider or "").strip().lower()
    pabilo_cfg = _pabilo_config()
    ubii_cfg = _ubii_config()
    method = (order_obj.method or "").strip().lower()
    pabilo_like = bool(
        _order_is_pabilo_eligible(order_obj)
        or pay_state.get("provider") == "pabilo"
        or int(pay_state.get("attempts") or 0) > 0
    )
    ubii_like = bool(
        auto_mapped
        and active_provider == "ubii"
        and _pabilo_normalize_method(order_obj.method or "") == _pabilo_normalize_method(ubii_cfg.get("method") or "pm")
    )
    is_provider_auto = bool(auto_mapped and (ubii_like or pabilo_like))

    if not is_provider_auto:
        return {
            "ok": True,
            "visible": False,
            "order_id": order_obj.id,
            "status": (order_obj.status or "").lower(),
        }

    summary = _summarize_order_auto_recharges(_build_order_auto_recharge_units(order_obj))
    attempts = 0
    try:
        attempts = int(pay_state.get("attempts") or 0)
    except Exception:
        attempts = 0

    payment_checked = attempts > 0
    payment_verified = bool(pay_state.get("verified"))
    order_validated = (order_obj.status or "").lower() in ("approved", "delivered")
    recharge_connected = bool(
        summary.get("total_units", 0) > 0
        and (
            summary.get("processing_units", 0) > 0
            or summary.get("completed_units", 0) > 0
            or summary.get("failed_units", 0) > 0
        )
    )
    recharge_done = bool(
        summary.get("total_units", 0) > 0
        and summary.get("completed_units", 0) >= summary.get("total_units", 0)
    )

    is_ubii_flow = provider == "ubii" or ubii_like
    search_label = "Esperando notificación de Ubii" if is_ubii_flow else "Buscando pago en el sistema"
    payment_label = "Pago confirmado en Ubii" if is_ubii_flow else "Pago confirmado"

    steps = [
        {
            "id": "search",
            "label": search_label,
            "done": payment_checked if not is_ubii_flow else payment_verified,
        },
        {
            "id": "payment",
            "label": payment_label,
            "done": payment_verified,
        },
        {
            "id": "validate",
            "label": "Validando la orden",
            "done": order_validated,
        },
        {
            "id": "dispatch",
            "label": "Conectando con servidor",
            "done": recharge_connected,
        },
        {
            "id": "completed",
            "label": "Recarga procesada correctamente",
            "done": recharge_done,
        },
    ]

    current_message = "Procesando tu recarga..."
    if recharge_done:
        current_message = "Recarga completada"
    elif recharge_connected:
        current_message = "Conectando y procesando recarga"
    elif order_validated:
        current_message = "Orden validada, enviando recarga"
    elif payment_verified:
        current_message = "Pago confirmado en Ubii, validando orden" if is_ubii_flow else "Pago confirmado, validando orden"
    elif payment_checked:
        current_message = "Pago en revisión"
    elif is_ubii_flow:
        current_message = "Esperando confirmación de pago por Ubii"

    return {
        "ok": True,
        "visible": True,
        "order_id": order_obj.id,
        "status": (order_obj.status or "").lower(),
        "method": method,
        "provider": provider,
        "configured_method": ubii_cfg.get("method") if is_ubii_flow else pabilo_cfg.get("method"),
        "steps": steps,
        "summary": summary,
        "payment": {
            "checked": payment_checked,
            "verified": payment_verified,
            "attempts": attempts,
            "message": str(pay_state.get("message") or ""),
            "verification_id": str(pay_state.get("verification_id") or ""),
        },
        "completed": recharge_done,
        "current_message": current_message,
    }


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
                "direct_to_script": bool(getattr(mapping, "direct_to_script", False)),
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
            "direct_to_script": bool(planned.get("direct_to_script")),
            "external_order_id": str((previous or {}).get("external_order_id") or default_external_order_id),
            "status": status,
            "player_name": str((previous or {}).get("player_name") or ""),
            "reference_no": str((previous or {}).get("reference_no") or ""),
            "remaining_balance": (previous or {}).get("remaining_balance"),
            "error": str((previous or {}).get("error") or ""),
            "attempt_count": int((previous or {}).get("attempt_count") or 0),
            "last_attempt_at": str((previous or {}).get("last_attempt_at") or ""),
            "last_checked_at": str((previous or {}).get("last_checked_at") or ""),
            "last_provider": str((previous or {}).get("last_provider") or _unit_delivery_source(planned)),
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
    max_attempts = 3
    retry_delay_seconds = 2
    state = _load_order_automation_state(order_obj)
    units = _build_order_auto_recharge_units(order_obj, state)
    summary = _summarize_order_auto_recharges(units)
    state.update({
        "source": _automation_source_from_units(units),
        "binance_auto": bool(binance_auto or state.get("binance_auto")),
        "units": units,
        "summary": summary,
    })
    if summary["total_units"] <= 0:
        _save_order_automation_state(order_obj, state)
        return {"ok": True, "summary": summary, "units": units}

    needs_revendedores = any(_unit_delivery_source(unit) == "revendedores_api" for unit in units)
    webb_url, webb_api_key, _, _ = _revendedores_env()
    player_id = (order_obj.customer_id or "").strip()
    if needs_revendedores and (not webb_url or not webb_api_key):
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
        unit["last_provider"] = _unit_delivery_source(unit)
        legacy_payload = {
            "product_id": unit.get("remote_product_id"),
            "package_id": unit.get("remote_package_id"),
            "player_id": player_id,
            "external_order_id": unit.get("external_order_id"),
        }
        if (order_obj.customer_zone or "").strip():
            legacy_payload["player_id2"] = (order_obj.customer_zone or "").strip()

        remote_meta = _revendedores_catalog_meta(unit.get("remote_product_id"), unit.get("remote_package_id"))
        modern_payload = {
            "api_key": webb_api_key,
            "package_id": str(remote_meta.get("package_id") or remote_meta.get("remote_local_package_id") or unit.get("remote_package_id") or ""),
            "player_id": player_id,
            "request_id": str(unit.get("external_order_id") or ""),
            "external_order_id": str(unit.get("external_order_id") or ""),
        }
        if unit.get("remote_product_id") is not None:
            modern_payload["product_id"] = str(unit.get("remote_product_id"))
        provider_package_id = remote_meta.get("provider_package_id") or remote_meta.get("gamepoint_package_id")
        if provider_package_id not in (None, "", 0, "0"):
            modern_payload["provider_package_id"] = str(provider_package_id)
        provider_package_key = (remote_meta.get("provider_package_key") or remote_meta.get("script_package_key") or "").strip()
        if provider_package_key:
            modern_payload["provider_package_key"] = provider_package_key
        if (order_obj.customer_zone or "").strip():
            modern_payload["player_id2"] = (order_obj.customer_zone or "").strip()

        for attempt in range(1, max_attempts + 1):
            unit["last_attempt_at"] = datetime.utcnow().isoformat()
            unit["attempt_count"] = int(unit.get("attempt_count") or 0) + 1
            try:
                if _unit_delivery_source(unit) == "game_script_direct":
                    script_result = _dispatch_game_script_unit(unit, order_obj, remote_meta)
                    _apply_dispatch_result_to_unit(unit, script_result)
                else:
                    api_data = None
                    response_error = ""
                    api_resp = None
                    for path in _revendedores_recharge_paths():
                        use_legacy_api = path.strip().startswith("/api/v1/")
                        headers = {
                            "X-API-Key": webb_api_key,
                            "X-Request-ID": str(unit.get("external_order_id") or ""),
                        }
                        req_kwargs = {"headers": headers, "timeout": 60}
                        if use_legacy_api:
                            headers["Content-Type"] = "application/json"
                            req_kwargs["json"] = legacy_payload
                        else:
                            req_kwargs["data"] = modern_payload

                        api_resp = _requests_lib.post(f"{webb_url}{path}", **req_kwargs)
                        try:
                            api_data = api_resp.json()
                        except Exception:
                            api_data = None

                        if api_resp.status_code in (404, 405) and not use_legacy_api:
                            response_error = f"HTTP {api_resp.status_code} en {path}"
                            api_data = None
                            continue

                        if api_data is None:
                            response_error = f"Respuesta inválida HTTP {api_resp.status_code} en {path}"
                            if not use_legacy_api:
                                continue
                            api_data = {"ok": False, "error": response_error}

                        break

                    if api_data is None:
                        api_data = {"ok": False, "error": response_error or "No se pudo conectar con Revendedores"}
                    if api_data.get("ok"):
                        _apply_dispatch_result_to_unit(unit, {
                            "status": "completed",
                            "player_name": api_data.get("player_name"),
                            "reference_no": api_data.get("reference_no"),
                            "remaining_balance": api_data.get("remaining_balance"),
                            "provider": "revendedores_api",
                        })
                    else:
                        unit_status = str(api_data.get("purchase_status") or api_data.get("status") or "").strip().lower()
                        unit_error = str(api_data.get("error") or api_data.get("message") or "Recarga no completada en Revendedores")
                        if unit_status in {"processing", "procesando", "pending", "pendiente", "queued", "en_cola", "en cola"}:
                            mapped_status = "processing"
                        elif unit_status in {"not_found", "no_encontrada", "no encontrada"}:
                            mapped_status = "not_found"
                        elif api_resp is not None and api_resp.status_code == 404:
                            mapped_status = "not_found"
                        else:
                            mapped_status = "failed"
                        _apply_dispatch_result_to_unit(unit, {
                            "status": mapped_status,
                            "error": unit_error,
                            "provider": "revendedores_api",
                        })

                if unit.get("status") == "completed":
                    last_error = ""
                    break
                last_error = str(unit.get("error") or last_error)
            except _requests_lib.exceptions.Timeout:
                provider_name = "Game Script" if _unit_delivery_source(unit) == "game_script_direct" else "Revendedores"
                unit["status"] = "processing"
                unit["error"] = f"{provider_name} no respondió en 60 segundos"
                last_error = unit["error"]
            except Exception as exc:
                unit["status"] = "processing"
                unit["error"] = str(exc)
                last_error = unit["error"]

            if unit.get("status") == "completed":
                break
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)

        if unit.get("status") == "completed":
            continue
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
            add_order_col('capture_reference', "capture_reference TEXT DEFAULT ''")
            # Optional columns used in model defaults
            add_order_col('price', "price REAL DEFAULT 0")
            add_order_col('active', "active INTEGER DEFAULT 1")
            add_order_col('delivery_code', "delivery_code TEXT DEFAULT ''")
            add_order_col('delivery_codes_json', "delivery_codes_json TEXT DEFAULT ''")
            add_order_col('special_code', "special_code TEXT DEFAULT ''")
            add_order_col('idempotency_key', "idempotency_key TEXT")
            add_order_col('special_user_id', "special_user_id INTEGER")
            add_order_col('items_json', "items_json TEXT DEFAULT ''")
            add_order_col('automation_json', "automation_json TEXT DEFAULT ''")
            add_order_col('payment_capture', "payment_capture TEXT DEFAULT ''")
            add_order_col('payer_dni_type', "payer_dni_type TEXT DEFAULT ''")
            add_order_col('payer_dni_number', "payer_dni_number TEXT DEFAULT ''")
            add_order_col('payer_bank_origin', "payer_bank_origin TEXT DEFAULT ''")
            add_order_col('payer_phone', "payer_phone TEXT DEFAULT ''")
            add_order_col('payer_payment_date', "payer_payment_date TEXT DEFAULT ''")
            add_order_col('payer_movement_type', "payer_movement_type TEXT DEFAULT ''")
            add_order_col('payment_verification_id', "payment_verification_id TEXT DEFAULT ''")
            add_order_col('payment_verified_at', f"payment_verified_at {'TIMESTAMP' if _is_pg else 'TEXT'}")
            add_order_col('payment_verification_attempts', "payment_verification_attempts INTEGER DEFAULT 0")
            add_order_col('payment_last_verification_at', f"payment_last_verification_at {'TIMESTAMP' if _is_pg else 'TEXT'}")
            db.session.commit()
            try:
                db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_idempotency_key ON orders (idempotency_key)"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        try:
            rev_map_cols = _get_table_cols("rev_item_mappings")
            if "direct_to_script" not in rev_map_cols:
                if _is_pg:
                    db.session.execute(text("ALTER TABLE rev_item_mappings ADD COLUMN direct_to_script BOOLEAN DEFAULT FALSE"))
                else:
                    db.session.execute(text("ALTER TABLE rev_item_mappings ADD COLUMN direct_to_script INTEGER DEFAULT 0"))
                db.session.commit()
        except Exception:
            db.session.rollback()
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
        "payment_verification_provider": _payment_verification_provider(),
        "pabilo_auto_verify_enabled": get_config_value("pabilo_auto_verify_enabled", "0"),
        "pabilo_method": get_config_value("pabilo_method", "pm"),
        "pabilo_enforce_method": get_config_value("pabilo_enforce_method", "1"),
        "pabilo_default_movement_type": get_config_value("pabilo_default_movement_type", ""),
        "ubii_method": get_config_value("ubii_method", "pm"),
    }
    return jsonify({"ok": True, "payments": data})


@app.route("/store/item/<int:item_id>/automation-check", methods=["GET"])
def store_item_automation_check(item_id: int):
    method = _pabilo_normalize_method(request.args.get("method") or "pm")
    mapping = RevendedoresItemMapping.query.filter_by(
        store_item_id=item_id,
        active=True,
        auto_enabled=True,
    ).first()
    auto_recharge = mapping is not None
    pabilo_cfg = _pabilo_config()
    configured_method = _pabilo_normalize_method(pabilo_cfg.get("method") or "pm")
    collect_payer_data = bool(auto_recharge and pabilo_cfg.get("enabled") and method == configured_method)
    return jsonify({
        "ok": True,
        "auto_recharge": auto_recharge,
        "pabilo_enabled": bool(pabilo_cfg.get("enabled")),
        "pabilo_method": configured_method,
        "collect_payer_data": collect_payer_data,
    })


@app.route("/webhook-ubii", methods=["POST"])
def webhook_ubii():
    cfg = _ubii_config()
    if not cfg.get("enabled"):
        return jsonify({"status": "error", "message": "La verificación Ubii no está activa"}), 503

    raw_body = request.get_data(cache=True, as_text=True) or ""
    debug_enabled = (request.args.get("debug") or request.headers.get("X-Ubii-Debug") or "").strip().lower() in {"1", "true", "yes", "on"}
    request_json = request.get_json(silent=True)
    payload = request_json
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True) if request.form else {}
    if not isinstance(payload, dict):
        payload = {}
    initial_payload = dict(payload)

    configured_secret = str(cfg.get("webhook_secret") or "").strip()
    if configured_secret:
        provided_secret = (request.headers.get("X-Webhook-Secret") or request.args.get("secret") or "").strip()
        if provided_secret != configured_secret:
            return jsonify({"status": "error", "message": "Secret de webhook inválido"}), 401

    extracted = _ubii_extract_notification_data(payload, cfg)
    fallback_payload = {}
    if extracted.get("amount") is None or not extracted.get("reference"):
        stripped_body = str(raw_body or "").strip()
        if stripped_body:
            parsed_form = urllib.parse.parse_qs(stripped_body, keep_blank_values=True)
            for key, values in parsed_form.items():
                if not values:
                    continue
                fallback_payload[str(key)] = str(values[-1])
            if not fallback_payload:
                text_field = str(cfg.get("text_field") or "texto").strip() or "texto"
                fallback_payload[text_field] = stripped_body
                if text_field != "texto":
                    fallback_payload["texto"] = stripped_body

        if fallback_payload:
            fallback_extracted = _ubii_extract_notification_data({**payload, **fallback_payload}, cfg)
            if fallback_extracted.get("text"):
                extracted = fallback_extracted

    if debug_enabled:
        return jsonify({
            "status": "debug",
            "request": {
                "content_type": request.content_type,
                "mimetype": request.mimetype,
                "raw_body": raw_body,
                "json": request_json if isinstance(request_json, dict) else request_json,
                "form": request.form.to_dict(flat=True) if request.form else {},
                "args": request.args.to_dict(flat=True) if request.args else {},
            },
            "config": {
                "enabled": bool(cfg.get("enabled")),
                "method": cfg.get("method"),
                "text_field": cfg.get("text_field"),
                "amount_regex": cfg.get("amount_regex"),
                "reference_regex": cfg.get("reference_regex"),
            },
            "payload": {
                "initial": initial_payload,
                "fallback": fallback_payload,
                "final": {**initial_payload, **fallback_payload} if fallback_payload else initial_payload,
            },
            "extracted": {
                "text": extracted.get("text") or "",
                "amount_raw": extracted.get("amount_raw") or "",
                "amount": str(extracted.get("amount") or ""),
                "reference": extracted.get("reference") or "",
            },
        }), 200

    if not extracted.get("text") and extracted.get("amount") is None and not extracted.get("reference"):
        return jsonify({"status": "error", "message": "No data received"}), 400
    if extracted.get("amount") is None or not extracted.get("reference"):
        return jsonify({"status": "error", "message": "Formato no reconocido"}), 400

    order_obj, match_message, already_processed = _ubii_find_matching_order(
        extracted.get("reference") or "",
        extracted.get("amount"),
        cfg.get("method") or "pm",
    )
    if not order_obj:
        return jsonify({
            "status": "ignored",
            "message": match_message,
            "data": {
                "monto": extracted.get("amount_raw") or "No encontrado",
                "referencia": extracted.get("reference") or "No encontrada",
            },
        }), 200

    if already_processed:
        return jsonify({
            "status": "success",
            "message": match_message,
            "order_id": order_obj.id,
            "data": {
                "monto": extracted.get("amount_raw") or "No encontrado",
                "referencia": extracted.get("reference") or "No encontrada",
            },
        }), 200

    result = _ubii_verify_and_update_order(order_obj, extracted, payload=payload)
    return jsonify({
        "status": "success",
        "message": result.get("message") or "Pago verificado",
        "order_id": order_obj.id,
        "data": {
            "monto": extracted.get("amount_raw") or "No encontrado",
            "referencia": extracted.get("reference") or "No encontrada",
        },
    }), 200


 

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
    try:
        set_config_values({"logo_path": (data.get("logo_path") or "").strip()})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar logo: {exc}"}), 500
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
    try:
        set_config_values({"site_name": site_name})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar nombre del sitio: {exc}"}), 500
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
    try:
        set_config_values({"mid_banner_path": (data.get("mid_banner_path") or "").strip()})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar banner: {exc}"}), 500
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
    try:
        set_config_values({"thanks_image_path": (data.get("thanks_image_path") or "").strip()})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar imagen de gracias: {exc}"}), 500
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
    try:
        set_config_values({"exchange_rate_bsd_per_usd": (data.get("rate_bsd_per_usd") or "").strip()})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar tasa: {exc}"}), 500
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
        "payment_verification_provider": _payment_verification_provider(),
        "pabilo_auto_verify_enabled": get_config_value("pabilo_auto_verify_enabled", "0"),
        "pabilo_api_key": get_config_value("pabilo_api_key", ""),
        "pabilo_user_bank_id": get_config_value("pabilo_user_bank_id", ""),
        "pabilo_pm_user_bank_id": get_config_value("pabilo_pm_user_bank_id", ""),
        "pabilo_binance_user_bank_id": get_config_value("pabilo_binance_user_bank_id", ""),
        "pabilo_method": get_config_value("pabilo_method", "pm"),
        "pabilo_base_url": get_config_value("pabilo_base_url", os.environ.get("PABILO_BASE_URL", "https://api.pabilo.app")),
        "pabilo_timeout_seconds": get_config_value("pabilo_timeout_seconds", os.environ.get("PABILO_TIMEOUT", "30")),
        "pabilo_enforce_method": get_config_value("pabilo_enforce_method", "1"),
        "pabilo_default_movement_type": get_config_value("pabilo_default_movement_type", ""),
        "ubii_method": get_config_value("ubii_method", "pm"),
        "ubii_text_field": get_config_value("ubii_text_field", "texto"),
        "ubii_amount_regex": get_config_value("ubii_amount_regex", r"Bs\.\s*([\d\.,]+)"),
        "ubii_reference_regex": _ubii_normalize_reference_regex(get_config_value("ubii_reference_regex", r"referencia\D*(\d+)")),
        "ubii_webhook_secret": get_config_value("ubii_webhook_secret", ""),
        "ubii_webhook_path": "/webhook-ubii",
    })


@app.route("/admin/config/payments", methods=["POST"])
def admin_config_payments_set():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    values = {
        "pm_bank": (data.get("pm_bank") or "").strip(),
        "pm_name": (data.get("pm_name") or "").strip(),
        "pm_phone": (data.get("pm_phone") or "").strip(),
        "pm_id": (data.get("pm_id") or "").strip(),
        "binance_email": (data.get("binance_email") or "").strip(),
        "binance_phone": (data.get("binance_phone") or "").strip(),
        "pm_image_path": (data.get("pm_image_path") or "").strip(),
        "binance_image_path": (data.get("binance_image_path") or "").strip(),
        "binance_auto_enabled": "1" if data.get("binance_auto_enabled") else "0",
        "pabilo_auto_verify_enabled": "1" if data.get("pabilo_auto_verify_enabled") else "0",
        "pabilo_api_key": (data.get("pabilo_api_key") or "").strip(),
        "pabilo_user_bank_id": (data.get("pabilo_user_bank_id") or "").strip(),
        "pabilo_pm_user_bank_id": (data.get("pabilo_pm_user_bank_id") or "").strip(),
        "pabilo_binance_user_bank_id": (data.get("pabilo_binance_user_bank_id") or "").strip(),
        "ubii_text_field": (data.get("ubii_text_field") or "texto").strip() or "texto",
        "ubii_amount_regex": (data.get("ubii_amount_regex") or r"Bs\.\s*([\d\.,]+)").strip() or r"Bs\.\s*([\d\.,]+)",
        "ubii_reference_regex": _ubii_normalize_reference_regex((data.get("ubii_reference_regex") or r"referencia\D*(\d+)").strip() or r"referencia\D*(\d+)"),
        "ubii_webhook_secret": (data.get("ubii_webhook_secret") or "").strip(),
    }
    provider = (data.get("payment_verification_provider") or "").strip().lower()
    if provider not in ("", "pabilo", "ubii"):
        provider = ""
    values["payment_verification_provider"] = provider
    values["ubii_auto_verify_enabled"] = "1" if provider == "ubii" else "0"
    pabilo_method = (data.get("pabilo_method") or "pm").strip().lower()
    if pabilo_method not in ("pm", "binance"):
        pabilo_method = "pm"
    values["pabilo_method"] = pabilo_method
    selected_user_bank_id = values.get("pabilo_pm_user_bank_id", "") if pabilo_method == "pm" else values.get("pabilo_binance_user_bank_id", "")
    values["pabilo_user_bank_id"] = selected_user_bank_id or values.get("pabilo_user_bank_id", "")
    values["pabilo_base_url"] = (data.get("pabilo_base_url") or "").strip()
    timeout_raw = (data.get("pabilo_timeout_seconds") or "").strip()
    try:
        timeout_val = str(max(int(timeout_raw or "30"), 5))
    except Exception:
        timeout_val = "30"
    values["pabilo_timeout_seconds"] = timeout_val
    values["pabilo_enforce_method"] = "1" if data.get("pabilo_enforce_method", True) else "0"
    default_movement_type = (data.get("pabilo_default_movement_type") or "").strip().upper()
    if default_movement_type not in ("", "GENERIC", "MOVIL_PAY", "TRANSFER"):
        default_movement_type = ""
    values["pabilo_default_movement_type"] = default_movement_type
    ubii_method = (data.get("ubii_method") or "pm").strip().lower()
    if ubii_method not in ("pm", "binance"):
        ubii_method = "pm"
    values["ubii_method"] = ubii_method
    try:
        set_config_values(values)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar configuración de pagos: {exc}"}), 500
    return jsonify({
        "ok": True,
        "saved": {
            "pm_bank": values.get("pm_bank", ""),
            "pm_name": values.get("pm_name", ""),
            "pm_phone": values.get("pm_phone", ""),
            "pm_id": values.get("pm_id", ""),
            "binance_email": values.get("binance_email", ""),
            "binance_phone": values.get("binance_phone", ""),
            "pm_image_path": values.get("pm_image_path", ""),
            "binance_image_path": values.get("binance_image_path", ""),
            "binance_auto_enabled": values.get("binance_auto_enabled", "0"),
            "payment_verification_provider": values.get("payment_verification_provider", ""),
            "pabilo_auto_verify_enabled": values.get("pabilo_auto_verify_enabled", "0"),
            "pabilo_api_key": values.get("pabilo_api_key", ""),
            "pabilo_user_bank_id": values.get("pabilo_user_bank_id", ""),
            "pabilo_pm_user_bank_id": values.get("pabilo_pm_user_bank_id", ""),
            "pabilo_binance_user_bank_id": values.get("pabilo_binance_user_bank_id", ""),
            "pabilo_method": values.get("pabilo_method", "pm"),
            "pabilo_base_url": values.get("pabilo_base_url", ""),
            "pabilo_timeout_seconds": values.get("pabilo_timeout_seconds", "30"),
            "pabilo_enforce_method": values.get("pabilo_enforce_method", "1"),
            "pabilo_default_movement_type": values.get("pabilo_default_movement_type", ""),
            "ubii_method": values.get("ubii_method", "pm"),
            "ubii_text_field": values.get("ubii_text_field", "texto"),
            "ubii_amount_regex": values.get("ubii_amount_regex", r"Bs\.\s*([\d\.,]+)"),
            "ubii_reference_regex": _ubii_normalize_reference_regex(values.get("ubii_reference_regex", r"referencia\D*(\d+)")),
            "ubii_webhook_secret": values.get("ubii_webhook_secret", ""),
            "ubii_webhook_path": "/webhook-ubii",
        }
    })


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
    try:
        set_config_values({"admin_notify_email": email})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar correo: {exc}"}), 500
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
    try:
        set_config_values({
            "hero_1": (data.get("hero_1") or "").strip(),
            "hero_2": (data.get("hero_2") or "").strip(),
            "hero_3": (data.get("hero_3") or "").strip(),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar carrusel: {exc}"}), 500
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
    try:
        set_config_values({"active_login_game_id": val})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar juego activo: {exc}"}), 500
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
    try:
        set_config_values({"bs_package_id": val})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar bs_package_id: {exc}"}), 500
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
    try:
        set_config_values({"bs_server_id": val})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar bs_server_id: {exc}"}), 500
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
    try:
        set_config_values({"ml_package_id": val})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar ml_package_id: {exc}"}), 500
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
    try:
        set_config_values({"ml_smile_pid": val})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"No se pudo guardar ml_smile_pid: {exc}"}), 500
    return jsonify({"ok": True, "ml_smile_pid": val})


# ==============================
# Admin: Smile.One Connections CRUD
# ==============================
@app.route("/admin/smileone/connections", methods=["GET"])
def admin_smileone_connections_list():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    conns = SmileOneConnection.query.order_by(SmileOneConnection.id.asc()).all()
    return jsonify({"ok": True, "connections": [{
        "id": c.id,
        "name": c.name,
        "page_url": c.page_url,
        "store_package_id": c.store_package_id,
        "smile_pid": c.smile_pid or "",
        "server_id": c.server_id or "-1",
        "product_slug": c.product_slug or "",
        "requires_zone": bool(c.requires_zone),
        "active": bool(c.active),
    } for c in conns]})


@app.route("/admin/smileone/connections", methods=["POST"])
def admin_smileone_connections_create():
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    page_url = (data.get("page_url") or "").strip()
    store_pkg = data.get("store_package_id")
    smile_pid = (data.get("smile_pid") or "").strip()
    server_id = (data.get("server_id") or "-1").strip()
    product_slug = (data.get("product_slug") or "").strip()
    requires_zone = bool(data.get("requires_zone", False))
    if not name or not page_url or not store_pkg:
        return jsonify({"ok": False, "error": "Nombre, URL y Paquete son requeridos"}), 400
    try:
        store_pkg = int(store_pkg)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Paquete ID inválido"}), 400
    # Auto-derive product_slug from page_url if not given
    if not product_slug:
        # e.g. https://www.smile.one/br/merchant/game/bloodstrike?... -> bloodstrike
        try:
            slug_part = page_url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
            if slug_part and slug_part.isalpha():
                product_slug = slug_part
        except Exception:
            pass
    conn = SmileOneConnection(
        name=name, page_url=page_url, store_package_id=store_pkg,
        smile_pid=smile_pid, server_id=server_id, product_slug=product_slug,
        requires_zone=requires_zone, active=True,
    )
    db.session.add(conn)
    db.session.commit()
    return jsonify({"ok": True, "id": conn.id})


@app.route("/admin/smileone/connections/<int:cid>", methods=["PUT", "PATCH"])
def admin_smileone_connections_update(cid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    conn = SmileOneConnection.query.get(cid)
    if not conn:
        return jsonify({"ok": False, "error": "Conexión no encontrada"}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data:
        conn.name = (data["name"] or "").strip()
    if "page_url" in data:
        conn.page_url = (data["page_url"] or "").strip()
    if "store_package_id" in data:
        try:
            conn.store_package_id = int(data["store_package_id"])
        except (ValueError, TypeError):
            pass
    if "smile_pid" in data:
        conn.smile_pid = (data["smile_pid"] or "").strip()
    if "server_id" in data:
        conn.server_id = (data["server_id"] or "-1").strip()
    if "product_slug" in data:
        conn.product_slug = (data["product_slug"] or "").strip()
    if "requires_zone" in data:
        conn.requires_zone = bool(data["requires_zone"])
    if "active" in data:
        conn.active = bool(data["active"])
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/smileone/connections/<int:cid>", methods=["DELETE"])
def admin_smileone_connections_delete(cid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    conn = SmileOneConnection.query.get(cid)
    if not conn:
        return jsonify({"ok": False, "error": "Conexión no encontrada"}), 404
    db.session.delete(conn)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/store/smileone/connections", methods=["GET"])
def store_smileone_connections_public():
    """Public endpoint: returns active SmileOne connection package IDs for the details page."""
    conns = SmileOneConnection.query.filter_by(active=True).all()
    return jsonify({"ok": True, "connections": [{
        "store_package_id": c.store_package_id,
        "requires_zone": bool(c.requires_zone),
    } for c in conns]})


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


def _capture_absolute_path(relative_path: str) -> str:
    safe_path = str(relative_path or "").strip()
    if not safe_path:
        return ""
    return os.path.join(app.config["UPLOAD_FOLDER"], safe_path)


def _receipt_reference_prompt() -> str:
    return (
        "Reglas estrictas:\n\n"
        "Responde UNICAMENTE con los digitos del numero de referencia.\n"
        "No incluyas palabras como Referencia o Confirmacion.\n"
        "El numero buscado puede aparecer con etiquetas como: Referencia, Numero de referencia, Nro. de referencia, Operacion, Numero de operacion, Nro. de operacion, Codigo de operacion, Transaccion, Comprobante o Confirmacion.\n"
        "Prioriza el numero de la operacion bancaria o de la transaccion del comprobante, aunque el banco use un nombre distinto para ese campo.\n"
        "Ignora montos, fechas, telefonos, cedulas, cuentas origen/destino y cualquier otro numero que no identifique la operacion.\n"
        "Si hay varios numeros, prioriza el asociado a la transaccion.\n"
        "Si la imagen no es un comprobante de pago o no tiene una referencia clara, responde exactamente ERROR_NO_DETECTADO.\n"
        "No inventes numeros; si no estas seguro al 100%, responde ERROR_NO_DETECTADO."
    )


def _genai_model():
    global _GENAI_MODEL, _GENAI_MODEL_READY
    if _GENAI_MODEL_READY:
        return _GENAI_MODEL
    if not GENAI_API_KEY:
        raise RuntimeError("GENAI_API_KEY no configurada")
    genai.configure(api_key=GENAI_API_KEY)
    return None


def _genai_candidate_model_names() -> list[str]:
    candidates = []
    for raw_name in (
        GENAI_MODEL_NAME,
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
    ):
        model_name = str(raw_name or "").strip()
        if model_name and model_name not in candidates:
            candidates.append(model_name)
    return candidates


def _is_genai_model_not_found_error(exc: Exception) -> bool:
    detail = str(exc or "").strip().lower()
    return bool(
        "404 models/" in detail
        or "is not found for api version" in detail
        or "not supported for generatecontent" in detail
    )


def _normalize_extracted_capture_reference(raw_value) -> str:
    text = str(raw_value or "").strip()
    if not text or text.upper() == "ERROR_NO_DETECTADO":
        return ""
    if text.isdigit() and 1 <= len(text) <= 21:
        return text
    digit_groups = re.findall(r"\d+", text)
    if len(digit_groups) == 1 and 1 <= len(digit_groups[0]) <= 21:
        return digit_groups[0]
    return ""


def _extract_capture_reference(relative_path: str):
    global _GENAI_MODEL, _GENAI_MODEL_READY
    capture_path = _capture_absolute_path(relative_path)
    if not capture_path or not os.path.exists(capture_path):
        return "", "capture_not_found"
    uploaded_file = None
    try:
        _genai_model()
        uploaded_file = genai.upload_file(path=capture_path)
        last_model_error = None
        for model_name in _genai_candidate_model_names():
            model = genai.GenerativeModel(model_name)
            try:
                response = model.generate_content([_receipt_reference_prompt(), uploaded_file])
            except Exception as exc:
                if _is_genai_model_not_found_error(exc):
                    last_model_error = exc
                    continue
                raise
            _GENAI_MODEL = model
            _GENAI_MODEL_READY = True
            extracted_reference = _normalize_extracted_capture_reference(getattr(response, "text", ""))
            if extracted_reference:
                return extracted_reference, "ok"
            return "", "not_detected"
        if last_model_error is not None:
            raise RuntimeError(
                "Ningun modelo Gemini compatible estuvo disponible. "
                "Configura GENAI_MODEL con un nombre vigente, por ejemplo gemini-2.5-flash. "
                f"Detalle: {last_model_error}"
            )
        return "", "not_detected"
    except Exception as exc:
        return "", f"error:{exc}"
    finally:
        if uploaded_file is not None:
            try:
                genai.delete_file(name=uploaded_file.name)
            except Exception:
                pass


def _capture_reference_status_error_message(status: str) -> str:
    raw_status = str(status or "").strip()
    if not raw_status.startswith("error:"):
        return ""
    detail = raw_status.split(":", 1)[1].strip()
    lowered = detail.lower()
    if "genai_api_key no configurada" in lowered:
        return "La IA no está configurada todavía en el servidor. Falta GENAI_API_KEY."
    if "api key" in lowered or "api_key" in lowered:
        return "La clave de Gemini no es válida o no está disponible en este momento."
    if "quota" in lowered or "resource exhausted" in lowered:
        return "La cuenta de Gemini alcanzó el límite de uso. Intenta de nuevo más tarde."
    return detail or "No se pudo analizar el comprobante con la IA."


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
        other_aliases = {"other", "others", "otro", "otros", "service", "services", "servicio", "servicios"}
        if cat in mobile_aliases:
            q = q.filter(StorePackage.category.in_(["mobile", "movil", "juegos"]))
        elif cat in gift_aliases:
            q = q.filter(StorePackage.category.in_(["gift", "gif", "giftcards"]))
        elif cat in other_aliases:
            q = q.filter(StorePackage.category.in_(["other", "others", "otro", "otros", "services", "servicios"]))
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
    # SmileOne dynamic connections
    so_connections = []
    so_connections_json = "[]"
    try:
        so_conns = SmileOneConnection.query.filter_by(active=True).all()
        so_connections = [{"store_package_id": c.store_package_id, "requires_zone": bool(c.requires_zone)} for c in so_conns]
        so_connections_json = json.dumps(so_connections)
    except Exception:
        pass
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
        so_connections=so_connections,
        so_connections_json=so_connections_json,
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


@app.route("/gracias/<int:oid>/progress", methods=["GET"])
def thanks_order_progress(oid: int):
    """Public minimal progress endpoint for thank-you page polling."""
    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404
    return jsonify(_thanks_progress_payload(o))


def _start_checkout_automation(order_id: int, app_obj) -> None:
    def _runner():
        try:
            with app_obj.app_context():
                order_obj = Order.query.get(order_id)
                if not order_obj:
                    return

                try:
                    to_addr = get_config_value("admin_notify_email", ADMIN_NOTIFY_EMAIL or ADMIN_EMAIL)
                    if to_addr:
                        pkg = StorePackage.query.get(order_obj.store_package_id)
                        it = GamePackageItem.query.get(order_obj.item_id) if order_obj.item_id else None
                        admin_html, admin_text = build_admin_new_order_email(order_obj, pkg, it)
                        brand = _email_brand()
                        try:
                            send_email_html(to_addr, f"[{brand}] Nueva orden #{order_obj.id}", admin_html, admin_text)
                        except Exception:
                            send_email_async(to_addr, f"Nueva orden #{order_obj.id} pendiente", admin_text)
                except Exception:
                    pass

                if (order_obj.status or "").lower() != "pending":
                    return

                request_info = _pabilo_request_info(order_obj)
                eligibility = _pabilo_eligibility_info(order_obj)
                if request_info.get("requestable"):
                    _pabilo_verify_and_update_order(
                        order_obj,
                        auto_approve_on_verified=bool(eligibility.get("eligible")),
                        source="checkout",
                    )
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    try:
        threading.Thread(target=_runner, daemon=True, name=f"checkout-auto-{order_id}").start()
    except Exception:
        pass


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


@app.route("/orders/extract-capture-reference", methods=["POST"])
def extract_capture_reference_preview():
    capture_file = request.files.get("payment_capture")
    if not capture_file or not capture_file.filename:
        return jsonify({"ok": False, "error": "Comprobante requerido"}), 400
    if not _allowed_file(capture_file.filename):
        return jsonify({"ok": False, "error": "Formato de imagen no permitido"}), 400

    temp_capture_path = ""
    try:
        temp_capture_path = _save_capture(capture_file)
        if not temp_capture_path:
            return jsonify({"ok": False, "error": "No se pudo guardar el comprobante"}), 400

        extracted_reference, extraction_status = _extract_capture_reference(temp_capture_path)
        error_message = _capture_reference_status_error_message(extraction_status)
        if error_message:
            return jsonify({
                "ok": False,
                "error": error_message,
                "status": extraction_status,
            }), 503
        return jsonify({
            "ok": True,
            "reference": str(extracted_reference or ""),
            "status": extraction_status,
            "found": bool(extracted_reference),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        if temp_capture_path:
            _delete_capture(temp_capture_path)


@app.route("/admin/orders/<int:oid>/reference", methods=["POST"])
def admin_orders_update_reference(oid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404
    if (o.status or "").lower() != "pending":
        return jsonify({"ok": False, "error": "Solo puedes editar la referencia de órdenes pendientes"}), 409

    data = request.get_json(silent=True) or {}
    new_reference = (data.get("reference") or "").strip()
    ok, ref_or_error = _validate_order_reference_value(o, new_reference, exclude_order_id=o.id)
    if not ok:
        return jsonify({"ok": False, "error": ref_or_error}), 400

    previous_reference = str(o.reference or "").strip()
    if ref_or_error == previous_reference:
        return jsonify({
            "ok": True,
            "reference": previous_reference,
            "payment_verify": _pabilo_get_payment_state(o),
            "changed": False,
        })

    o.reference = ref_or_error
    _reset_order_payment_verification_state(
        o,
        message=f"Referencia actualizada por admin de {previous_reference or 'N/A'} a {ref_or_error}",
        source="admin_reference_edit",
    )
    db.session.commit()
    return jsonify({
        "ok": True,
        "reference": o.reference,
        "payment_verify": _pabilo_get_payment_state(o),
        "changed": True,
    })

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
        currency_upper = currency.upper()
        if method == "pm" or currency_upper in ("BSD", "VES", "BS"):
            amount = float(int(round(amount))) if amount > 0 else 0.0
        reference = _get("reference").strip()
        name = _get("name").strip()
        email = _get("email").strip()
        phone = _get("phone").strip()
        customer_id = _get("customer_id").strip()
        customer_zone = _get("customer_zone").strip()
        special_code = _get("special_code").strip()
        verified_nick = _get("nn").strip()
        payer_dni_type = (_get("payer_dni_type") or "").strip().upper()
        payer_dni_number = (_get("payer_dni_number") or "").strip()
        payer_bank_origin = (_get("payer_bank_origin") or "").strip()
        payer_phone = (_get("payer_phone") or "").strip()
        payer_payment_date = (_get("payer_payment_date") or "").strip()
        payer_movement_type = (_get("payer_movement_type") or "").strip().upper()
        capture_reference_preview = _normalize_extracted_capture_reference(_get("capture_reference_preview"))
        idempotency_key = _normalize_order_idempotency_key(
            request.headers.get("X-Idempotency-Key") or _get("idempotency_key")
        )

        if idempotency_key:
            existing_idempotent_order = _find_order_by_idempotency_key(idempotency_key)
            if existing_idempotent_order:
                return jsonify({"ok": True, "order_id": existing_idempotent_order.id, "idempotent": True})

        if payer_dni_type and payer_dni_type not in ("V", "E", "J", "P", "G"):
            payer_dni_type = ""
        if payer_payment_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", payer_payment_date):
            return jsonify({"ok": False, "error": "La fecha de pago es inválida"}), 400
        if payer_movement_type and payer_movement_type not in ("GENERIC", "MOVIL_PAY", "TRANSFER"):
            payer_movement_type = ""

        if not email:
            return jsonify({"ok": False, "error": "Correo requerido"}), 400

        if customer_id and not customer_id.isdigit():
            return jsonify({"ok": False, "error": "El ID de jugador debe ser numérico"}), 400

        if customer_zone and not customer_zone.isdigit():
            return jsonify({"ok": False, "error": "La Zona ID debe ser numérica"}), 400

        ml_package_id = (get_config_value("ml_package_id", "") or "").strip()
        if ml_package_id and str(gid) == ml_package_id and not customer_zone:
            return jsonify({"ok": False, "error": "La Zona ID es requerida para este juego"}), 400
        try:
            so_conn = SmileOneConnection.query.filter_by(store_package_id=gid, active=True).first()
        except Exception:
            so_conn = None
        if so_conn and bool(getattr(so_conn, "requires_zone", False)) and not customer_zone:
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
            capture_reference="",
            name=name,
            email=email,
            phone=phone,
            customer_id=customer_id,
            customer_zone=customer_zone,
            customer_name=verified_nick or name or email or customer_id,
            status="pending",
            special_code=special_code,
            idempotency_key=idempotency_key or None,
            payer_dni_type=payer_dni_type,
            payer_dni_number=payer_dni_number,
            payer_bank_origin=payer_bank_origin,
            payer_phone=payer_phone or phone,
            payer_payment_date=payer_payment_date,
            payer_movement_type=payer_movement_type,
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
        order_total_usd_raw = float(order_total_usd or 0.0)

        def _append_order_item(target_items, game_item, qty_value, *, apply_single_discount=False):
            qty_value = max(int(qty_value or 1), 1)
            base_price = round(float(game_item.price or 0.0), 2)
            discounted_price = round(base_price * (1.0 - discount_fraction), 2)
            base_price_raw = float(game_item.price or 0.0)
            discounted_price_raw = base_price_raw * (1.0 - discount_fraction)

            if apply_single_discount and discount_fraction > 0:
                target_items.append({
                    "item_id": game_item.id,
                    "qty": 1,
                    "title": game_item.title,
                    "price": discounted_price,
                    "cost_unit_usd": float(game_item.profit_net_usd or 0.0),
                })
                if qty_value > 1:
                    target_items.append({
                        "item_id": game_item.id,
                        "qty": qty_value - 1,
                        "title": game_item.title,
                        "price": base_price,
                        "cost_unit_usd": float(game_item.profit_net_usd or 0.0),
                    })
                return True, discounted_price_raw + (base_price_raw * max(qty_value - 1, 0))

            target_items.append({
                "item_id": game_item.id,
                "qty": qty_value,
                "title": game_item.title,
                "price": base_price,
                "cost_unit_usd": float(game_item.profit_net_usd or 0.0),
            })
            return False, base_price_raw * qty_value

        try:
            raw_items = data.get("items")
            # When sent as form data, items is a JSON-encoded string
            if isinstance(raw_items, str):
                try:
                    raw_items = json.loads(raw_items)
                except Exception:
                    raw_items = []
            items_list = []
            discount_already_applied = False
            order_total_usd_raw = 0.0
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
                    discount_used_now, line_total_raw = _append_order_item(
                        items_list,
                        gi,
                        qty,
                        apply_single_discount=bool(discount_fraction and not discount_already_applied),
                    )
                    order_total_usd_raw += float(line_total_raw or 0.0)
                    discount_already_applied = discount_already_applied or discount_used_now
            if (not items_list) and item_id:
                gi = GamePackageItem.query.get(item_id)
                if gi:
                    qty = 1
                    _, order_total_usd_raw = _append_order_item(
                        items_list,
                        gi,
                        qty,
                        apply_single_discount=bool(discount_fraction and not discount_already_applied),
                    )
            if items_list:
                o.items_json = json.dumps(items_list)
                order_total_usd = round(sum(float(ent.get("price") or 0.0) * max(int(ent.get("qty") or 1), 1) for ent in items_list), 2)
        except Exception:
            pass
        canonical_amount = amount_from_usd(order_total_usd_raw, currency)
        if canonical_amount <= 0:
            return jsonify({"ok": False, "error": "No se pudo calcular un monto válido para la orden"}), 400
        o.amount = canonical_amount
        o.price = round(float(order_total_usd or 0.0), 2)

        # Optional enforcement: mapped auto-recharge orders must use selected Pabilo method.
        if _is_pabilo_payment_method_enforced_for_order(o):
            required_method = (_pabilo_config().get("method") or "pm").strip().lower()
            if (method or "").strip().lower() != required_method:
                return jsonify({
                    "ok": False,
                    "error": f"Este juego solo acepta pagos por {required_method.upper()} para recarga automática.",
                }), 400

        # Try to resolve special user id now for convenience
        try:
            if special_code:
                su, _ = resolve_special_user_for_code(special_code)
                if su:
                    o.special_user_id = su.id
        except Exception:
            pass
        try:
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
                        extracted_reference, extraction_status = _extract_capture_reference(capture_path)
                        resolved_capture_reference = extracted_reference or capture_reference_preview
                        if resolved_capture_reference:
                            o.capture_reference = resolved_capture_reference
                        elif extracted_reference:
                            o.capture_reference = extracted_reference
                        current_payment_state = _pabilo_get_payment_state(o)
                        _pabilo_set_payment_state(o, {
                            **current_payment_state,
                            "capture_reference": str(o.capture_reference or ""),
                            "capture_reference_status": extraction_status,
                            "capture_reference_source": (
                                "server_extract" if extracted_reference else ("preview_extract" if capture_reference_preview else "")
                            ),
                        })
            except Exception:
                pass
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if idempotency_key:
                existing_idempotent_order = _find_order_by_idempotency_key(idempotency_key)
                if existing_idempotent_order:
                    return jsonify({"ok": True, "order_id": existing_idempotent_order.id, "idempotent": True})
            raise
        try:
            _start_checkout_automation(o.id, current_app._get_current_object())
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
    try:
        page = max(int(request.args.get("page", 1) or 1), 1)
    except Exception:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 50) or 50)
    except Exception:
        per_page = 50
    per_page = 50 if per_page <= 0 else min(per_page, 50)

    base_query = Order.query.order_by(Order.created_at.desc())
    total_orders = base_query.count()
    total_pages = max((total_orders + per_page - 1) // per_page, 1)
    if page > total_pages:
        page = total_pages

    orders = (
        base_query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    out = []
    active_payment_provider = _payment_verification_provider()
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
        payment_state = _pabilo_get_payment_state(x)
        pabilo_request = _pabilo_request_info(x)
        pabilo_eligibility = _pabilo_eligibility_info(x)
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
            "payment_verification_provider_active": active_payment_provider,
            "payment_verify": payment_state,
            "pabilo_request": pabilo_request,
            "pabilo_eligible": bool(pabilo_eligibility.get("eligible")),
            "pabilo_eligibility": pabilo_eligibility,
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
            "capture_reference": x.capture_reference or "",
            "delivery_code": x.delivery_code or "",
            "delivery_codes": delivery_codes,
            "payment_capture": x.payment_capture or "",
            "payment_capture_url": (
                f"{app.config.get('UPLOAD_URL_PREFIX', '/static/uploads').rstrip('/')}/{x.payment_capture}"
                if x.payment_capture else ""
            ),
        })
    return jsonify({
        "ok": True,
        "orders": out,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_orders": total_orders,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
    })


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
            "capture_reference": x.capture_reference or "",
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
    skip_payment_verification = bool(data.get("skip_payment_verification"))
    if status not in ("approved", "rejected"):
        return jsonify({"ok": False, "error": "Estado inválido"}), 400
    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404

    # Enforce payment verification via Pabilo for mapped auto-recharge orders when enabled.
    if status == "approved" and (o.status or "").lower() == "pending" and _order_is_pabilo_eligible(o) and not skip_payment_verification:
        payment_state = _pabilo_get_payment_state(o)
        if not payment_state.get("verified"):
            verification = _pabilo_verify_and_update_order(o, auto_approve_on_verified=False, source="admin_approve")
            if not verification.get("verified"):
                return jsonify({
                    "ok": False,
                    "error": verification.get("message") or "Pago no verificado en Pabilo",
                    "payment_verify": verification,
                }), 409
    elif status == "approved" and (o.status or "").lower() == "pending" and skip_payment_verification:
        pay_state = _pabilo_get_payment_state(o)
        pay_state["provider"] = str(pay_state.get("provider") or "pabilo")
        pay_state["manual_override"] = True
        pay_state["manual_override_at"] = datetime.utcnow().isoformat()
        pay_state["message"] = "Recarga aprobada manualmente por admin sin verificación Pabilo"
        _pabilo_set_payment_state(o, pay_state)
        db.session.commit()
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
        if status == "approved" and (o.email or o.name) and not _order_has_auto_recharges(o):
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
            auto_summary = auto_dispatch.get("summary") or {}
            if auto_summary.get("total_units", 0) > 0 and auto_summary.get("completed_units", 0) >= auto_summary.get("total_units", 0):
                _send_order_completed_email_if_needed(o)
    except Exception as exc:
        auto_dispatch = {
            "ok": False,
            "error": str(exc),
            "pending_verification": False,
            "order_id": o.id,
            "summary": _summarize_order_auto_recharges(_build_order_auto_recharge_units(o)),
        }

    response_payload = {"ok": True}
    if skip_payment_verification:
        response_payload["manual_override"] = True
    if auto_dispatch and auto_dispatch.get("summary", {}).get("total_units"):
        response_payload["webb_recarga"] = {
            "ok": bool(auto_dispatch.get("ok")),
            "error": auto_dispatch.get("error") or "",
            "pending_verification": bool(auto_dispatch.get("pending_verification")),
            "order_id": o.id,
            "summary": auto_dispatch.get("summary") or {},
        }

    return jsonify(response_payload)


@app.route("/admin/orders/<int:oid>/verify-payment", methods=["POST"])
def admin_orders_verify_payment(oid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404
    if (o.status or "").lower() not in ("pending", "approved", "delivered"):
        return jsonify({"ok": False, "error": "La orden no permite verificación"}), 400
    request_info = _pabilo_request_info(o)
    if not request_info.get("requestable"):
        return jsonify({
            "ok": False,
            "error": "Esta orden no se puede consultar en Pabilo",
            "request": request_info,
            "eligibility": _pabilo_eligibility_info(o),
        }), 400

    result = _pabilo_verify_and_update_order(
        o,
        auto_approve_on_verified=bool(_order_is_pabilo_eligible(o)),
        source="admin_manual",
    )
    return jsonify({"ok": True, "payment_verify": result, "order_status": o.status})


@app.route("/admin/orders/<int:oid>/verify-ubii", methods=["POST"])
def admin_orders_verify_ubii(oid: int):
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    o = Order.query.get(oid)
    if not o:
        return jsonify({"ok": False, "error": "No existe"}), 404
    if (o.status or "").lower() not in ("pending", "approved", "delivered"):
        return jsonify({"ok": False, "error": "La orden no permite verificación"}), 400

    cfg = _ubii_config()
    if _payment_verification_provider() != "ubii":
        return jsonify({"ok": False, "error": "Ubii no es el proveedor activo"}), 400

    data = request.get_json(silent=True) or {}
    text_field = str(cfg.get("text_field") or "texto").strip() or "texto"
    notification_text = _ubii_collect_payload_text(data, cfg)
    if not notification_text:
        return jsonify({
            "ok": False,
            "error": "Debes pegar el texto real de la notificacion de Ubii para verificar manualmente",
        }), 400

    extracted = _ubii_extract_notification_data({text_field: notification_text}, cfg)
    if notification_text and not extracted.get("text"):
        extracted["text"] = notification_text
    if extracted.get("amount") is None or not extracted.get("reference"):
        return jsonify({
            "ok": False,
            "error": "No se pudo extraer una referencia y un monto validos desde el texto de la notificacion de Ubii",
        }), 400

    expected_reference = _ubii_reference_match_key(o.reference or "")
    received_reference = _ubii_reference_match_key(extracted.get("reference") or "")
    if not expected_reference or expected_reference != received_reference:
        return jsonify({
            "ok": False,
            "error": "Los ultimos 4 digitos de la referencia de Ubii no coinciden con la orden",
            "payment_verify": {
                "provider": "ubii",
                "verified": False,
                "message": "Los ultimos 4 digitos de la referencia de Ubii no coinciden con la orden",
            },
        }), 400

    if _pabilo_normalize_method(o.method or "") != _pabilo_normalize_method(cfg.get("method") or "pm"):
        return jsonify({
            "ok": False,
            "error": "El método de pago de la orden no coincide con la configuración de Ubii",
            "payment_verify": {
                "provider": "ubii",
                "verified": False,
                "message": "El método de pago de la orden no coincide con la configuración de Ubii",
            },
        }), 400

    if not _ubii_order_amount_matches(o, extracted.get("amount")):
        return jsonify({
            "ok": False,
            "error": "El monto recibido en Ubii es menor al monto de la orden",
            "payment_verify": {
                "provider": "ubii",
                "verified": False,
                "message": "El monto recibido en Ubii es menor al monto de la orden",
            },
        }), 400

    result = _ubii_verify_and_update_order(
        o,
        extracted,
        payload=data,
        source="admin_manual_ubii",
    )
    return jsonify({"ok": True, "payment_verify": result, "order_status": o.status})


@app.route("/admin/orders/<int:oid>/verify-recharge", methods=["POST"])
def admin_orders_verify_recharge(oid: int):
    """Verifica si la recarga automática realmente se completó."""
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

    processing_units = [unit for unit in units if (unit.get("status") or "") == "processing"]
    webb_url, webb_api_key, _, _ = _revendedores_env()
    needs_revendedores = any(_unit_delivery_source(unit) == "revendedores_api" for unit in processing_units)

    if needs_revendedores and (not webb_url or not webb_api_key):
        return jsonify({"ok": False, "error": "Revendedores API no configurada"})

    for unit in processing_units:
        unit["last_checked_at"] = datetime.utcnow().isoformat()
        if _unit_delivery_source(unit) == "game_script_direct":
            verify_result = _verify_game_script_unit(unit)
            _apply_dispatch_result_to_unit(unit, verify_result)
            continue

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

        if resp.status_code in (404, 405):
            unit["last_checked_at"] = datetime.utcnow().isoformat()
            unit["status"] = "failed"
            unit["error"] = "El proveedor no expone order-status para esta recarga. Puedes reenviarla manualmente."
            continue

        if not data.get("ok"):
            unit["last_checked_at"] = datetime.utcnow().isoformat()
            unit["status"] = "failed"
            unit["error"] = str(data.get("error") or "Error consultando Revendedores")
            continue

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
        "source": _automation_source_from_units(units),
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
            _send_order_completed_email_if_needed(o)
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
        _send_order_completed_email_if_needed(o)
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
            "message": f"Hay {summary.get('processing_units', 0)} recarga(s) aún procesándose en el proveedor automático.",
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

    attempted_paths = []
    key_preview = (api_key[:12] + "...") if len(api_key) > 12 else "(vacía)"
    for path in _revendedores_catalog_paths():
        attempted_paths.append(path)
        try:
            resp = _requests_lib.get(
                f"{base_url}{path}",
                headers={"X-API-Key": api_key},
                timeout=30,
            )
            if not resp.ok:
                remote_error = f"HTTP {resp.status_code} en {path} (url={base_url}, key={key_preview}, len={len(api_key)})"
                continue
            try:
                payload = resp.json()
            except Exception:
                snippet = (resp.text or "").strip().replace("\n", " ")[:180]
                remote_error = f"Respuesta no JSON en {path}: {snippet or 'vacía'}"
                continue
            normalized = _normalize_rev_catalog_payload(payload)
            if normalized:
                catalog_path = path
                break
            remote_error = f"Catálogo API sin paquetes válidos en {path}"
        except Exception as exc:
            remote_error = f"No se pudo consultar catálogo API en {path}: {str(exc)}"

    if not normalized:
        tried_paths = ", ".join(attempted_paths) or catalog_path
        return jsonify({"ok": False, "error": f"No se pudo sincronizar catálogo de Revendedores: {remote_error}. Rutas probadas: {tried_paths}"}), 502

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
                    "direct_to_script": bool(getattr(mappings_by_item[it.id], "direct_to_script", False)),
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
            direct_to_script = bool(ent.get("direct_to_script"))

            row = RevendedoresItemMapping.query.filter_by(store_item_id=store_item_id).first()

            if not catalog_id_raw:
                if row:
                    row.active = False
                    row.auto_enabled = False
                    row.direct_to_script = False
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
                    direct_to_script=direct_to_script,
                    active=True,
                )
                db.session.add(row)
            else:
                row.store_package_id = item.store_package_id
                row.remote_product_id = catalog.remote_product_id
                row.remote_package_id = catalog.remote_package_id
                row.remote_label = remote_label
                row.auto_enabled = auto_enabled
                row.direct_to_script = direct_to_script
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
        if c not in ("mobile", "gift", "other"):
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
    if category not in ("mobile", "gift", "other"):
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


def set_config_value(key: str, value: str, *, commit: bool = True) -> None:
    values = {str(key): str(value)}
    if commit:
        set_config_values(values)
        return
    _upsert_config_values(values)


def set_config_values(values: dict[str, str]) -> None:
    """Persist multiple config keys in a single transaction."""
    try:
        _upsert_config_values(values or {})
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _upsert_config_values(values: dict[str, str]) -> None:
    rows = [
        {"key": str(cfg_key), "value": str(cfg_value)}
        for cfg_key, cfg_value in (values or {}).items()
    ]
    if not rows:
        return

    table = AppConfig.__table__
    bind = None
    try:
        bind = db.session.get_bind(mapper=AppConfig.__mapper__)
    except Exception:
        bind = None
    if bind is None:
        try:
            bind = db.engine
        except Exception:
            bind = None
    dialect = ((bind.dialect.name if bind is not None and getattr(bind, "dialect", None) is not None else "") or "").lower()

    if dialect == "postgresql":
        stmt = pg_insert(table).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.key],
            set_={"value": stmt.excluded.value},
        )
        db.session.execute(stmt)
        return

    if dialect == "sqlite":
        stmt = sqlite_insert(table).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.key],
            set_={"value": stmt.excluded.value},
        )
        db.session.execute(stmt)
        return

    # Fallback for other dialects.
    for row_data in rows:
        row = AppConfig.query.filter_by(key=row_data["key"]).first()
        if row:
            row.value = row_data["value"]
        else:
            db.session.add(AppConfig(key=row_data["key"], value=row_data["value"]))


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
        try:
            set_config_values({
                "profile_name": name,
                "profile_email": email,
                "profile_phone": phone,
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": f"No se pudo guardar perfil: {exc}"}), 500
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
