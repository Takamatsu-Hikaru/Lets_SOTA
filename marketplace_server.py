#!/usr/bin/env python3
"""
CortexNodus Marketplace Server
提供子图市场、项目市场、用户注册/登录，以及管理员后台。

独立运行: python marketplace_server.py
默认端口: 5100

环境变量:
  PORT             监听端口 (默认 5100)
  ADMIN_PASSWORD   管理员密码 (默认 admin)
  SECRET_KEY       Flask session 密钥
"""

import os
import json
import uuid
import hashlib
import hmac
import secrets
import functools
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string

# ── App setup ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

MARKET_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_data")
SUBGRAPHS_DIR   = os.path.join(MARKET_DATA_DIR, "subgraphs")
PROJECTS_DIR    = os.path.join(MARKET_DATA_DIR, "projects")
CATALOG_PATH    = os.path.join(MARKET_DATA_DIR, "catalog.json")
USERS_PATH      = os.path.join(MARKET_DATA_DIR, "users.json")
SESSIONS_PATH   = os.path.join(MARKET_DATA_DIR, "sessions.json")

# 确保目录在模块加载时就存在（WSGI 部署时 __main__ 块不会执行）
os.makedirs(SUBGRAPHS_DIR, exist_ok=True)
os.makedirs(PROJECTS_DIR, exist_ok=True)


# ── CORS ───────────────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return jsonify({}), 200


# ── Storage helpers ────────────────────────────────────────────────────────────

def ensure_dirs():
    os.makedirs(SUBGRAPHS_DIR, exist_ok=True)
    os.makedirs(PROJECTS_DIR, exist_ok=True)

def _load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_catalog():   return _load_json(CATALOG_PATH, {"subgraphs": [], "projects": []})
def save_catalog(c):  _save_json(CATALOG_PATH, c)
def load_users():     return _load_json(USERS_PATH, {"users": []})
def save_users(u):    _save_json(USERS_PATH, u)
def load_sessions():  return _load_json(SESSIONS_PATH, {"tokens": {}})
def save_sessions(s): _save_json(SESSIONS_PATH, s)


# ── Password utilities ─────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return salt, dk.hex()

def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    _, dk = _hash_password(password, salt)
    return hmac.compare_digest(dk, stored_hash)


# ── Token utilities ────────────────────────────────────────────────────────────

def _issue_token(user_id: str) -> str:
    token = secrets.token_hex(32)
    sessions = load_sessions()
    sessions["tokens"][token] = {
        "user_id": user_id,
        "created_at": datetime.now().isoformat(),
    }
    save_sessions(sessions)
    return token

def _resolve_token(token: str):
    """Return user dict or None."""
    sessions = load_sessions()
    entry = sessions["tokens"].get(token)
    if not entry:
        return None
    users = load_users()
    for u in users["users"]:
        if u["id"] == entry["user_id"]:
            return u
    return None

def _get_current_user():
    """Parse Bearer token from request header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _resolve_token(auth[7:])
    return None


# ── Admin decorator ────────────────────────────────────────────────────────────

def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            if request.path.startswith("/admin/api/"):
                return jsonify({"error": "未授权"}), 401
            return redirect(url_for("admin_login_page"))
        return fn(*args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# USER AUTH API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if len(username) < 2 or len(username) > 32:
        return jsonify({"error": "用户名长度应在 2–32 个字符之间"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少 6 个字符"}), 400

    users = load_users()
    for u in users["users"]:
        if u["username"].lower() == username.lower():
            return jsonify({"error": "用户名已存在"}), 409

    salt, pw_hash = _hash_password(password)
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "username": username,
        "salt": salt,
        "password_hash": pw_hash,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    users["users"].append(user)
    save_users(users)

    token = _issue_token(user_id)
    return jsonify({"ok": True, "token": token, "username": username})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "请填写用户名和密码"}), 400

    users = load_users()
    user = next((u for u in users["users"] if u["username"].lower() == username.lower()), None)
    if not user or not _verify_password(password, user["salt"], user["password_hash"]):
        return jsonify({"error": "用户名或密码错误"}), 401

    token = _issue_token(user["id"])
    return jsonify({"ok": True, "token": token, "username": user["username"]})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401
    return jsonify({"ok": True, "username": user["username"], "created_at": user["created_at"]})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        sessions = load_sessions()
        sessions["tokens"].pop(token, None)
        save_sessions(sessions)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# MARKET STATUS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/market/status", methods=["GET"])
def market_status():
    catalog = load_catalog()
    users   = load_users()
    return jsonify({
        "ok": True,
        "subgraphs": len(catalog.get("subgraphs", [])),
        "projects":  len(catalog.get("projects", [])),
        "users":     len(users.get("users", [])),
    })


# ══════════════════════════════════════════════════════════════════════════════
# SUBGRAPHS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/market/subgraphs", methods=["GET"])
def list_subgraphs():
    catalog = load_catalog()
    q = request.args.get("q", "").strip().lower()
    items = catalog.get("subgraphs", [])
    if q:
        items = [i for i in items if
                 q in i.get("name", "").lower() or
                 q in i.get("description", "").lower() or
                 any(q in t.lower() for t in i.get("tags", []))]
    return jsonify({"items": items})


@app.route("/api/market/subgraphs/<item_id>", methods=["GET"])
def get_subgraph(item_id):
    path = os.path.join(SUBGRAPHS_DIR, f"{item_id}.json")
    if not os.path.exists(path):
        return jsonify({"error": "Not found"}), 404
    catalog = load_catalog()
    for item in catalog.get("subgraphs", []):
        if item["id"] == item_id:
            item["downloads"] = item.get("downloads", 0) + 1
            break
    save_catalog(catalog)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/market/subgraphs", methods=["POST"])
def publish_subgraph():
    data  = request.get_json(force=True)
    name  = (data.get("name") or "").strip()
    desc  = (data.get("description") or "").strip()
    raw_tags = data.get("tags", [])
    graph_data = data.get("graph")

    if not name or not graph_data:
        return jsonify({"error": "name 和 graph 字段不能为空"}), 400

    # Must be logged in to publish
    user = _get_current_user()
    if not user:
        return jsonify({"error": "请先登录后再发布"}), 401
    author = user["username"]

    tags = raw_tags if isinstance(raw_tags, list) else [t.strip() for t in raw_tags.split(",") if t.strip()]
    item_id = str(uuid.uuid4())[:8]
    meta = {
        "id": item_id,
        "name": name,
        "description": desc,
        "tags": tags,
        "author": author,
        "author_id": user["id"],
        "downloads": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    catalog = load_catalog()
    catalog.setdefault("subgraphs", []).insert(0, meta)
    save_catalog(catalog)
    with open(os.path.join(SUBGRAPHS_DIR, f"{item_id}.json"), "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "id": item_id})


@app.route("/api/market/subgraphs/<item_id>", methods=["DELETE"])
def delete_subgraph(item_id):
    catalog = load_catalog()
    catalog["subgraphs"] = [i for i in catalog.get("subgraphs", []) if i["id"] != item_id]
    save_catalog(catalog)
    path = os.path.join(SUBGRAPHS_DIR, f"{item_id}.json")
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/market/projects", methods=["GET"])
def list_projects():
    catalog = load_catalog()
    q = request.args.get("q", "").strip().lower()
    items = catalog.get("projects", [])
    if q:
        items = [i for i in items if
                 q in i.get("name", "").lower() or
                 q in i.get("description", "").lower() or
                 any(q in t.lower() for t in i.get("tags", []))]
    return jsonify({"items": items})


@app.route("/api/market/projects/<item_id>", methods=["GET"])
def get_project(item_id):
    path = os.path.join(PROJECTS_DIR, f"{item_id}.json")
    if not os.path.exists(path):
        return jsonify({"error": "Not found"}), 404
    catalog = load_catalog()
    for item in catalog.get("projects", []):
        if item["id"] == item_id:
            item["downloads"] = item.get("downloads", 0) + 1
            break
    save_catalog(catalog)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/market/projects", methods=["POST"])
def publish_project():
    data  = request.get_json(force=True)
    name  = (data.get("name") or "").strip()
    desc  = (data.get("description") or "").strip()
    raw_tags = data.get("tags", [])
    graph_data = data.get("graph")

    if not name or not graph_data:
        return jsonify({"error": "name 和 graph 字段不能为空"}), 400

    # Must be logged in to publish
    user = _get_current_user()
    if not user:
        return jsonify({"error": "请先登录后再发布"}), 401
    author = user["username"]

    tags = raw_tags if isinstance(raw_tags, list) else [t.strip() for t in raw_tags.split(",") if t.strip()]
    item_id = str(uuid.uuid4())[:8]
    meta = {
        "id": item_id,
        "name": name,
        "description": desc,
        "tags": tags,
        "author": author,
        "author_id": user["id"],
        "downloads": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    catalog = load_catalog()
    catalog.setdefault("projects", []).insert(0, meta)
    save_catalog(catalog)
    with open(os.path.join(PROJECTS_DIR, f"{item_id}.json"), "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "id": item_id})


@app.route("/api/market/projects/<item_id>", methods=["DELETE"])
def delete_project(item_id):
    catalog = load_catalog()
    catalog["projects"] = [i for i in catalog.get("projects", []) if i["id"] != item_id]
    save_catalog(catalog)
    path = os.path.join(PROJECTS_DIR, f"{item_id}.json")
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/login", methods=["POST"])
def admin_do_login():
    if request.is_json:
        pwd = (request.get_json(force=True, silent=True) or {}).get("password", "")
        is_json = True
    else:
        pwd = request.form.get("password", "")
        is_json = False

    if hmac.compare_digest(str(pwd), ADMIN_PASSWORD):
        session["admin_logged_in"] = True
        return jsonify({"ok": True}) if is_json else redirect(url_for("admin_dashboard"))

    if is_json:
        return jsonify({"error": "密码错误"}), 401
    return redirect(url_for("admin_login_page") + "?error=1")


@app.route("/admin/logout", methods=["GET", "POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login_page"))


@app.route("/admin/api/stats")
@admin_required
def admin_api_stats():
    catalog = load_catalog()
    users   = load_users()
    sessions = load_sessions()
    return jsonify({
        "users":    len(users.get("users", [])),
        "subgraphs": len(catalog.get("subgraphs", [])),
        "projects":  len(catalog.get("projects", [])),
        "sessions":  len(sessions.get("tokens", {})),
    })


@app.route("/admin/api/users")
@admin_required
def admin_api_users():
    users = load_users()
    safe = [{"id": u["id"], "username": u["username"], "created_at": u["created_at"]}
            for u in users.get("users", [])]
    return jsonify({"users": safe})


@app.route("/admin/api/users/<user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    users = load_users()
    users["users"] = [u for u in users.get("users", []) if u["id"] != user_id]
    save_users(users)
    # revoke tokens
    sessions = load_sessions()
    sessions["tokens"] = {t: v for t, v in sessions["tokens"].items() if v["user_id"] != user_id}
    save_sessions(sessions)
    return jsonify({"ok": True})


@app.route("/admin/api/subgraphs")
@admin_required
def admin_api_subgraphs():
    catalog = load_catalog()
    return jsonify({"items": catalog.get("subgraphs", [])})


@app.route("/admin/api/subgraphs/<item_id>", methods=["DELETE"])
@admin_required
def admin_delete_subgraph(item_id):
    catalog = load_catalog()
    catalog["subgraphs"] = [i for i in catalog.get("subgraphs", []) if i["id"] != item_id]
    save_catalog(catalog)
    path = os.path.join(SUBGRAPHS_DIR, f"{item_id}.json")
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})


@app.route("/admin/api/projects")
@admin_required
def admin_api_projects():
    catalog = load_catalog()
    return jsonify({"items": catalog.get("projects", [])})


@app.route("/admin/api/projects/<item_id>", methods=["DELETE"])
@admin_required
def admin_delete_project(item_id):
    catalog = load_catalog()
    catalog["projects"] = [i for i in catalog.get("projects", []) if i["id"] != item_id]
    save_catalog(catalog)
    path = os.path.join(PROJECTS_DIR, f"{item_id}.json")
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — HTML PAGES
# ══════════════════════════════════════════════════════════════════════════════

_ADMIN_BASE_STYLE = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,Arial;background:#0e0e0e;color:#eaeaea;min-height:100vh}
a{color:#9fb1ff;text-decoration:none}
.topbar{background:#1e1e1e;border-bottom:1px solid #333;padding:12px 24px;
        display:flex;align-items:center;gap:16px}
.topbar .brand{font-size:16px;font-weight:bold;color:#c8a0ff}
.topbar .spacer{flex:1}
.topbar a,.topbar button{font-size:13px;padding:5px 14px;border-radius:4px;
  background:#2b3a55;color:#fff;border:1px solid #3b4a66;cursor:pointer}
.topbar a:hover,.topbar button:hover{background:#3b4a66}
.container{max-width:1100px;margin:0 auto;padding:24px}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:28px}
.stat-card{background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:20px;text-align:center}
.stat-card .num{font-size:36px;font-weight:bold;color:#c8a0ff}
.stat-card .lbl{font-size:13px;color:#888;margin-top:4px}
.tabs{display:flex;gap:0;border-bottom:1px solid #333;margin-bottom:20px}
.tab-btn{padding:10px 20px;background:transparent;border:none;border-bottom:3px solid transparent;
         color:#888;cursor:pointer;font-size:14px;font-weight:bold}
.tab-btn.active{color:#fff;border-bottom-color:#c8a0ff}
.tab-btn:hover{color:#ccc;background:#1a1a1a}
.pane{display:none}.pane.active{display:block}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#252526;padding:10px 12px;text-align:left;color:#aaa;
   border-bottom:1px solid #333;font-weight:bold}
td{padding:9px 12px;border-bottom:1px solid #222;vertical-align:middle}
tr:hover td{background:#1a1a1a}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;
       background:#3a2b55;color:#c8a0ff;border:1px solid #5a4a77;margin:1px}
.btn-del{background:#552b2b;border:1px solid #663b3b;color:#faa;padding:4px 10px;
         border-radius:4px;cursor:pointer;font-size:12px}
.btn-del:hover{background:#6b3535}
.empty{color:#666;text-align:center;padding:30px;font-size:14px}
</style>
"""

_LOGIN_PAGE = _ADMIN_BASE_STYLE + """
<div style="display:flex;justify-content:center;align-items:center;min-height:100vh">
  <div style="background:#1e1e1e;border:1px solid #444;border-radius:10px;padding:36px 40px;width:340px">
    <div style="text-align:center;margin-bottom:24px">
      <div style="font-size:28px;margin-bottom:6px">🛬</div>
      <div style="font-size:18px;font-weight:bold;color:#c8a0ff">CortexNodus 管理后台</div>
    </div>
    {% if error %}<div style="background:#3a1a1a;border:1px solid #663b3b;color:#faa;
      padding:8px 12px;border-radius:4px;margin-bottom:14px;font-size:13px">密码错误</div>{% endif %}
    <form method="post" action="/admin/login">
      <div style="margin-bottom:14px">
        <label style="font-size:12px;color:#aaa;display:block;margin-bottom:4px">管理员密码</label>
        <input type="password" name="password" autofocus
          style="width:100%;padding:9px 12px;background:#111;border:1px solid #444;color:#eee;
                 border-radius:4px;font-size:14px">
      </div>
      <button type="submit"
        style="width:100%;padding:10px;background:#3a2b55;border:1px solid #5a4a77;color:#fff;
               border-radius:4px;font-size:14px;cursor:pointer;font-weight:bold">登录</button>
    </form>
  </div>
</div>
"""

_DASHBOARD_PAGE = _ADMIN_BASE_STYLE + """
<div class="topbar">
  <span class="brand">🛬 CortexNodus 管理后台</span>
  <span class="spacer"></span>
  <a href="/admin/logout">退出登录</a>
</div>
<div class="container">
  <div class="stats" id="stats-area">
    <div class="stat-card"><div class="num" id="st-users">…</div><div class="lbl">注册用户</div></div>
    <div class="stat-card"><div class="num" id="st-subgraphs">…</div><div class="lbl">子图</div></div>
    <div class="stat-card"><div class="num" id="st-projects">…</div><div class="lbl">项目</div></div>
    <div class="stat-card"><div class="num" id="st-sessions">…</div><div class="lbl">活跃 Token</div></div>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('users',this)">用户管理</button>
    <button class="tab-btn" onclick="switchTab('subgraphs',this)">子图管理</button>
    <button class="tab-btn" onclick="switchTab('projects',this)">项目管理</button>
  </div>

  <!-- Users -->
  <div class="pane active" id="pane-users">
    <table id="tbl-users">
      <thead><tr><th>用户名</th><th>注册时间</th><th>ID</th><th>操作</th></tr></thead>
      <tbody id="tbody-users"><tr><td colspan="4" class="empty">加载中…</td></tr></tbody>
    </table>
  </div>

  <!-- Subgraphs -->
  <div class="pane" id="pane-subgraphs">
    <table>
      <thead><tr><th>名称</th><th>作者</th><th>标签</th><th>下载</th><th>发布时间</th><th>ID</th><th>操作</th></tr></thead>
      <tbody id="tbody-subgraphs"><tr><td colspan="7" class="empty">加载中…</td></tr></tbody>
    </table>
  </div>

  <!-- Projects -->
  <div class="pane" id="pane-projects">
    <table>
      <thead><tr><th>名称</th><th>作者</th><th>标签</th><th>下载</th><th>发布时间</th><th>ID</th><th>操作</th></tr></thead>
      <tbody id="tbody-projects"><tr><td colspan="7" class="empty">加载中…</td></tr></tbody>
    </table>
  </div>
</div>

<script>
function switchTab(id, btn) {
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('pane-' + id).classList.add('active');
  btn.classList.add('active');
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadStats() {
  const d = await fetch('/admin/api/stats').then(r=>r.json());
  document.getElementById('st-users').textContent = d.users;
  document.getElementById('st-subgraphs').textContent = d.subgraphs;
  document.getElementById('st-projects').textContent = d.projects;
  document.getElementById('st-sessions').textContent = d.sessions;
}

async function loadUsers() {
  const d = await fetch('/admin/api/users').then(r=>r.json());
  const tb = document.getElementById('tbody-users');
  if (!d.users.length) { tb.innerHTML='<tr><td colspan="4" class="empty">暂无用户</td></tr>'; return; }
  tb.innerHTML = d.users.map(u => `<tr>
    <td><strong>${esc(u.username)}</strong></td>
    <td>${esc(u.created_at)}</td>
    <td style="font-family:monospace;font-size:11px;color:#666">${esc(u.id)}</td>
    <td><button class="btn-del" onclick="delUser('${u.id}','${esc(u.username)}',this)">删除</button></td>
  </tr>`).join('');
}

async function loadItems(type) {
  const d = await fetch('/admin/api/'+type).then(r=>r.json());
  const tb = document.getElementById('tbody-'+type);
  if (!d.items.length) { tb.innerHTML=`<tr><td colspan="7" class="empty">暂无内容</td></tr>`; return; }
  tb.innerHTML = d.items.map(i => `<tr>
    <td><strong>${esc(i.name)}</strong></td>
    <td>${esc(i.author)}</td>
    <td>${(i.tags||[]).map(t=>`<span class="badge">${esc(t)}</span>`).join('')}</td>
    <td>${i.downloads||0}</td>
    <td>${esc(i.created_at)}</td>
    <td style="font-family:monospace;font-size:11px;color:#666">${esc(i.id)}</td>
    <td><button class="btn-del" onclick="delItem('${type}','${i.id}','${esc(i.name)}',this)">删除</button></td>
  </tr>`).join('');
}

async function delUser(id, name, btn) {
  if (!confirm('删除用户 "'+name+'" 及其所有 Token？')) return;
  await fetch('/admin/api/users/'+id, {method:'DELETE'});
  btn.closest('tr').remove();
  loadStats();
}

async function delItem(type, id, name, btn) {
  if (!confirm('从市场删除 "'+name+'"？')) return;
  await fetch('/admin/api/'+type+'/'+id, {method:'DELETE'});
  btn.closest('tr').remove();
  loadStats();
}

loadStats();
loadUsers();
loadItems('subgraphs');
loadItems('projects');
</script>
"""


@app.route("/admin")
@app.route("/admin/")
@admin_required
def admin_dashboard():
    return render_template_string(_DASHBOARD_PAGE)


@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    error = request.args.get("error")
    return render_template_string(_LOGIN_PAGE, error=error)


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA
# ══════════════════════════════════════════════════════════════════════════════

DEMO_SUBGRAPHS = [
    {"meta": {"id":"demo0001","name":"ResNet 残差块","description":"经典残差连接模块，包含两个 Conv2D + BatchNorm + ReLU 及跳连接，适用于深度图像网络。","tags":["cnn","residual","vision"],"author":"CortexNodus","downloads":128,"created_at":"2026-01-15 10:00"},
     "graph":{"nodes":[{"id":1,"type":"Conv2D","pos":[100,80],"properties":{"out_channels":64,"kernel_size":3,"padding":1}},{"id":2,"type":"BatchNorm2d","pos":[300,80],"properties":{}},{"id":3,"type":"ReLU","pos":[480,80],"properties":{}},{"id":4,"type":"Conv2D","pos":[100,220],"properties":{"out_channels":64,"kernel_size":3,"padding":1}},{"id":5,"type":"BatchNorm2d","pos":[300,220],"properties":{}},{"id":6,"type":"Add","pos":[660,160],"properties":{}},{"id":7,"type":"ReLU","pos":[840,160],"properties":{}}],"links":[[1,1,0,2,0],[2,2,0,3,0],[3,3,0,4,0],[4,4,0,5,0],[5,5,0,6,0],[6,1,0,6,1],[7,6,0,7,0]]}},
    {"meta": {"id":"demo0002","name":"Inception 并联模块","description":"Inception 风格的并联卷积块，包含 1×1、3×3、5×5 卷积路径及 MaxPool 路径，最终 Concat 合并。","tags":["cnn","inception","vision","parallel"],"author":"CortexNodus","downloads":74,"created_at":"2026-01-20 14:30"},
     "graph":{"nodes":[{"id":1,"type":"Conv2D","pos":[60,60],"properties":{"out_channels":32,"kernel_size":1}},{"id":2,"type":"Conv2D","pos":[60,180],"properties":{"out_channels":32,"kernel_size":3,"padding":1}},{"id":3,"type":"Conv2D","pos":[60,300],"properties":{"out_channels":16,"kernel_size":5,"padding":2}},{"id":4,"type":"MaxPool","pos":[60,420],"properties":{"kernel_size":3,"stride":1,"padding":1}},{"id":5,"type":"Concat","pos":[360,240],"properties":{}}],"links":[[1,1,0,5,0],[2,2,0,5,1],[3,3,0,5,2],[4,4,0,5,3]]}},
    {"meta": {"id":"demo0003","name":"MLP 分类头","description":"多层感知机分类头，适合接在卷积特征后：Flatten → Dense(512) → ReLU → Dropout(0.5) → Dense(num_classes)。","tags":["mlp","classification","head"],"author":"CortexNodus","downloads":56,"created_at":"2026-02-01 09:00"},
     "graph":{"nodes":[{"id":1,"type":"Flatten","pos":[60,100],"properties":{}},{"id":2,"type":"Dense","pos":[220,100],"properties":{"out_features":512}},{"id":3,"type":"ReLU","pos":[380,100],"properties":{}},{"id":4,"type":"Dropout","pos":[520,100],"properties":{"p":0.5}},{"id":5,"type":"Dense","pos":[680,100],"properties":{"out_features":10}}],"links":[[1,1,0,2,0],[2,2,0,3,0],[3,3,0,4,0],[4,4,0,5,0]]}},
    {"meta": {"id":"demo0004","name":"Transformer 编码层","description":"标准 Transformer 编码层，包含多头注意力 + LayerNorm + 前馈网络（FFN）结构。","tags":["transformer","attention","nlp"],"author":"CortexNodus","downloads":39,"created_at":"2026-02-10 16:00"},
     "graph":{"nodes":[{"id":1,"type":"MultiheadAttention","pos":[100,100],"properties":{"embed_dim":256,"num_heads":8}},{"id":2,"type":"LayerNorm","pos":[320,100],"properties":{}},{"id":3,"type":"Linear","pos":[100,260],"properties":{"out_features":1024}},{"id":4,"type":"GELU","pos":[280,260],"properties":{}},{"id":5,"type":"Linear","pos":[440,260],"properties":{"out_features":256}},{"id":6,"type":"LayerNorm","pos":[620,260],"properties":{}}],"links":[[1,1,0,2,0],[2,2,0,3,0],[3,3,0,4,0],[4,4,0,5,0],[5,5,0,6,0]]}},
]

DEMO_PROJECTS = [
    {"meta": {"id":"proj0001","name":"MNIST 手写数字识别","description":"经典 CNN 识别 MNIST 数据集，包含 Conv2D → MaxPool → Flatten → Dense 结构，3 个 Epoch 即可达到 99% 准确率。","tags":["mnist","cnn","classification","beginner"],"author":"CortexNodus","downloads":215,"created_at":"2026-01-10 08:00"},
     "graph":{"nodes":[{"id":1,"type":"MNIST","pos":[60,200],"properties":{"batch_size":64}},{"id":2,"type":"Conv2D","pos":[260,120],"properties":{"out_channels":32,"kernel_size":3}},{"id":3,"type":"ReLU","pos":[440,120],"properties":{}},{"id":4,"type":"MaxPool","pos":[580,120],"properties":{"kernel_size":2}},{"id":5,"type":"Conv2D","pos":[260,280],"properties":{"out_channels":64,"kernel_size":3}},{"id":6,"type":"ReLU","pos":[440,280],"properties":{}},{"id":7,"type":"MaxPool","pos":[580,280],"properties":{"kernel_size":2}},{"id":8,"type":"Flatten","pos":[760,200],"properties":{}},{"id":9,"type":"Dense","pos":[920,200],"properties":{"out_features":128}},{"id":10,"type":"ReLU","pos":[1100,200],"properties":{}},{"id":11,"type":"Dense","pos":[1280,200],"properties":{"out_features":10}},{"id":12,"type":"Loss","pos":[1460,200],"properties":{"loss_type":"CrossEntropy","epochs":3}}],"links":[[1,1,0,2,0],[2,2,0,3,0],[3,3,0,4,0],[4,4,0,5,0],[5,5,0,6,0],[6,6,0,7,0],[7,4,0,8,0],[8,7,0,8,0],[9,8,0,9,0],[10,9,0,10,0],[11,10,0,11,0],[12,11,0,12,0]]}},
    {"meta": {"id":"proj0002","name":"Fashion-MNIST 服饰分类","description":"基于 Fashion-MNIST 数据集的服饰分类项目，使用带 BatchNorm 的 CNN，验证准确率约 92%。","tags":["fashion-mnist","cnn","batchnorm","classification"],"author":"CortexNodus","downloads":98,"created_at":"2026-01-25 11:00"},
     "graph":{"nodes":[{"id":1,"type":"Fashion-MNIST","pos":[60,200],"properties":{"batch_size":128}},{"id":2,"type":"Conv2D","pos":[280,200],"properties":{"out_channels":64,"kernel_size":3,"padding":1}},{"id":3,"type":"BatchNorm2d","pos":[460,200],"properties":{}},{"id":4,"type":"ReLU","pos":[640,200],"properties":{}},{"id":5,"type":"MaxPool","pos":[800,200],"properties":{"kernel_size":2}},{"id":6,"type":"Flatten","pos":[960,200],"properties":{}},{"id":7,"type":"Dense","pos":[1120,200],"properties":{"out_features":10}},{"id":8,"type":"Loss","pos":[1300,200],"properties":{"loss_type":"CrossEntropy","epochs":5}}],"links":[[1,1,0,2,0],[2,2,0,3,0],[3,3,0,4,0],[4,4,0,5,0],[5,5,0,6,0],[6,6,0,7,0],[7,7,0,8,0]]}},
    {"meta": {"id":"proj0003","name":"简单自编码器","description":"基于 MNIST 的全连接自编码器，编码维度为 32，用于图像重建任务，使用 MSELoss。","tags":["autoencoder","mnist","unsupervised","reconstruction"],"author":"CortexNodus","downloads":61,"created_at":"2026-02-05 14:00"},
     "graph":{"nodes":[{"id":1,"type":"MNIST","pos":[60,200],"properties":{"batch_size":64}},{"id":2,"type":"Flatten","pos":[240,200],"properties":{}},{"id":3,"type":"Dense","pos":[400,200],"properties":{"out_features":128}},{"id":4,"type":"ReLU","pos":[580,200],"properties":{}},{"id":5,"type":"Dense","pos":[740,200],"properties":{"out_features":32}},{"id":6,"type":"Dense","pos":[900,200],"properties":{"out_features":128}},{"id":7,"type":"ReLU","pos":[1080,200],"properties":{}},{"id":8,"type":"Dense","pos":[1240,200],"properties":{"out_features":784}},{"id":9,"type":"Sigmoid","pos":[1420,200],"properties":{}},{"id":10,"type":"Loss","pos":[1600,200],"properties":{"loss_type":"MSE","epochs":10,"target":"Input"}}],"links":[[1,1,0,2,0],[2,2,0,3,0],[3,3,0,4,0],[4,4,0,5,0],[5,5,0,6,0],[6,6,0,7,0],[7,7,0,8,0],[8,8,0,9,0],[9,9,0,10,0]]}},
]


def _init_demo_data():
    catalog = load_catalog()
    existing = {i["id"] for i in catalog.get("subgraphs", [])} | {i["id"] for i in catalog.get("projects", [])}
    changed = False
    for item in DEMO_SUBGRAPHS:
        if item["meta"]["id"] not in existing:
            catalog.setdefault("subgraphs", []).append(item["meta"])
            with open(os.path.join(SUBGRAPHS_DIR, f"{item['meta']['id']}.json"), "w", encoding="utf-8") as f:
                json.dump(item["graph"], f, ensure_ascii=False, indent=2)
            changed = True
    for item in DEMO_PROJECTS:
        if item["meta"]["id"] not in existing:
            catalog.setdefault("projects", []).append(item["meta"])
            with open(os.path.join(PROJECTS_DIR, f"{item['meta']['id']}.json"), "w", encoding="utf-8") as f:
                json.dump(item["graph"], f, ensure_ascii=False, indent=2)
            changed = True
    if changed:
        save_catalog(catalog)
        print("  [Market] 示例数据已初始化。")


# 模块加载时初始化示例数据（WSGI 部署兼容）
_init_demo_data()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _init_demo_data()
    port = int(os.environ.get("PORT", 5100))
    print(f"""
  ╔══════════════════════════════════════════╗
  ║    CortexNodus  Marketplace  Server      ║
  ║──────────────────────────────────────────║
  ║  市场:  http://localhost:{port:<16d}║
  ║  管理:  http://localhost:{port}/admin    ║
  ╚══════════════════════════════════════════╝
  管理员密码: {ADMIN_PASSWORD}
  Press Ctrl+C to quit.
""")
    app.run(host="0.0.0.0", port=port, debug=False)
