"""Login for a small private testing team.

- Users come from the USERS env var:  USERS="ali:pass1,omar:pass2,me:pass3"
- ADMIN_USER is the only account that can open /admin (the activity log).
- Each user only ever sees their own documents and math history.
"""
import hmac
import html
import json
import os
import secrets
import threading
import time
from collections import deque
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from pathlib import Path as _P

from dotenv import load_dotenv
from fastapi import HTTPException, Request

load_dotenv(_P(__file__).resolve().parent / ".env", encoding="utf-8-sig")

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
ADMINS = {a.strip() for a in (os.getenv("ADMIN_USER") or "").split(",") if a.strip()}
ON_RENDER = bool(os.getenv("RENDER"))
LOG_FILE = Path(os.getenv("ACTIVITY_LOG", "activity.jsonl"))

MAX_FAILS = 5
LOCK_SECONDS = 60

current_user = ContextVar("current_user", default="")


def _load_users():
    users = {}
    for pair in (os.getenv("USERS") or "").split(","):
        name, sep, password = pair.partition(":")
        name, password = name.strip(), password.strip()
        if sep and name and password:
            users[name] = password
    return users


USERS = _load_users()
if not USERS:
    print("WARNING: USERS is not set - nobody can log in.")
if not os.getenv("SECRET_KEY"):
    print("WARNING: SECRET_KEY is not set - everyone is logged out on every restart.")


def check_login(username, password):
    """Constant-time check. Always compares something so timing doesn't reveal valid names."""
    expected = USERS.get(username, "")
    ok = hmac.compare_digest(expected.encode(), (password or "").encode())
    return bool(expected) and ok


# ---- brute-force protection (per client IP) ----
_fails = {}
_fails_lock = threading.Lock()


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")


def locked_for(ip):
    with _fails_lock:
        count, until = _fails.get(ip, (0, 0))
        return max(0, int(until - time.time())) if count >= MAX_FAILS else 0


def register_fail(ip):
    with _fails_lock:
        count, until = _fails.get(ip, (0, 0))
        if count >= MAX_FAILS and until < time.time():
            count = 0
        count += 1
        _fails[ip] = (count, time.time() + LOCK_SECONDS)


def clear_fails(ip):
    with _fails_lock:
        _fails.pop(ip, None)


# ---- activity log (visible only to the admin) ----
_activity = deque(maxlen=5000)
_log_lock = threading.Lock()


def log(user, action, detail=""):
    entry = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "user": user,
             "action": action, "detail": detail[:200]}
    with _log_lock:
        _activity.append(entry)
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def activity(user=None, limit=500):
    with _log_lock:
        rows = [e for e in _activity if not user or e["user"] == user]
    return list(reversed(rows))[:limit]


def is_admin(user):
    return user in ADMINS


# ---- request dependency ----
PUBLIC = {"/login", "/logout", "/health"}


class LoginRedirect(Exception):
    pass


async def require_login(request: Request):
    path = request.url.path
    if path in PUBLIC:
        return
    user = request.session.get("user")
    if not user or user not in USERS:       # حساب اتشال من USERS يتفصل فوراً
        if request.method == "GET" and path == "/":
            raise LoginRedirect()
        raise HTTPException(status_code=401, detail="Not logged in")
    current_user.set(user)
    request.state.user = user
    if not path.startswith("/assets/"):
        log(user, f"{request.method} {path}")


def require_admin(request: Request):
    user = getattr(request.state, "user", "")
    if not is_admin(user):
        raise HTTPException(status_code=404, detail="Not found")   # 404 عشان الصفحة متتكشفش


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Login</title>
<style>body{{font-family:system-ui,sans-serif;background:#111;color:#eee;display:grid;place-items:center;min-height:100vh;margin:0}}
form{{background:#1c1c1c;padding:28px;border-radius:14px;width:min(320px,90vw);display:grid;gap:12px}}
input,button{{padding:11px;border-radius:8px;border:1px solid #444;background:#222;color:#eee;font-size:16px}}
button{{background:#3b82f6;border:0;cursor:pointer}}.err{{color:#f87171;font-size:14px}}</style></head>
<body><form method="post" action="/login"><h2 style="margin:0">Login</h2>{error}
<input name="username" placeholder="Username" autocomplete="username" required>
<input name="password" type="password" placeholder="Password" autocomplete="current-password" required>
<button type="submit">Sign in</button></form></body></html>"""


def login_page(error=""):
    return LOGIN_PAGE.format(error=f'<div class="err">{html.escape(error)}</div>' if error else "")
