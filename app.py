import json
import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename
from io import BytesIO


# Database path: allow override via env, default to container volume
DB_PATH = os.environ.get('DB_PATH', '/app/data/data.sqlite3')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source TEXT,
            notes TEXT,
            tags TEXT,
            pinned INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            current_version_id INTEGER,
            require_password INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id INTEGER NOT NULL,
            version TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT,
            parent_version_id INTEGER,
            FOREIGN KEY(prompt_id) REFERENCES prompts(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    # 默认阈值 200
    cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('version_cleanup_threshold', '200')")
    # 简易认证默认设置
    cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('auth_mode', 'off')")
    cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('auth_password_hash', '')")
    conn.commit()
    conn.close()


def now_ts():
    return datetime.utcnow().isoformat()


def parse_tags(s):
    if not s:
        return []
    if isinstance(s, list):
        return s
    # 输入支持中文逗号/英文逗号/空格；保留层级如“场景/客服”
    parts = []
    for raw in s.replace('，', ',').split(','):
        p = raw.strip()
        if p:
            parts.append(p)
    return parts


def tags_to_text(tags):
    return ', '.join(tags)


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def bump_version(current, kind='patch'):
    if not current:
        return '1.0.0'
    try:
        major, minor, patch = [int(x) for x in current.split('.')]
    except Exception:
        # 容错：无法解析直接回到 1.0.0
        return '1.0.0'
    if kind == 'major':
        major += 1
        minor = 0
        patch = 0
    elif kind == 'minor':
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def prune_versions(conn, prompt_id):
    threshold_s = get_setting(conn, 'version_cleanup_threshold', '200')
    try:
        threshold = int(threshold_s)
    except Exception:
        threshold = 200
    rows = conn.execute(
        "SELECT id FROM versions WHERE prompt_id=? ORDER BY created_at DESC", (prompt_id,)
    ).fetchall()
    if len(rows) > threshold:
        to_delete = [r['id'] for r in rows[threshold:]]
        conn.executemany("DELETE FROM versions WHERE id=?", [(vid,) for vid in to_delete])


def compute_current_version(conn, prompt_id):
    row = conn.execute(
        "SELECT id FROM versions WHERE prompt_id=? ORDER BY created_at DESC LIMIT 1",
        (prompt_id,),
    ).fetchone()
    if row:
        conn.execute("UPDATE prompts SET current_version_id=?, updated_at=? WHERE id=?",
                     (row['id'], now_ts(), prompt_id))


def get_all_tags(conn):
    all_rows = conn.execute("SELECT tags FROM prompts WHERE tags IS NOT NULL AND tags != ''").fetchall()
    tags = set()
    for r in all_rows:
        try:
            arr = json.loads(r['tags'])
            for t in arr:
                tags.add(t)
        except Exception:
            pass
    return sorted(tags)


def ensure_db():
    # Ensure parent directory exists to avoid 'unable to open database file'
    try:
        os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    except Exception:
        # best-effort; continue to let sqlite raise helpful error if needed
        pass
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        # best-effort migrations for new versions
        migrate_schema()


def migrate_schema():
    """Run lightweight schema migrations to add new columns/settings if missing."""
    try:
        conn = get_db()
        cur = conn.cursor()
        # ensure prompts.require_password exists
        cols = [r['name'] for r in cur.execute('PRAGMA table_info(prompts)').fetchall()]
        if 'require_password' not in cols:
            cur.execute("ALTER TABLE prompts ADD COLUMN require_password INTEGER DEFAULT 0")
        # ensure auth settings keys exist
        cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('auth_mode', 'off')")
        cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('auth_password_hash', '')")
        conn.commit()
    except Exception:
        # ignore migration failures to avoid blocking the app
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')
# Jinja 过滤器：JSON 反序列化
app.jinja_env.filters['loads'] = json.loads


@app.before_request
def _before():
    ensure_db()
    # 全局密码模式拦截：除登录与静态资源外均需认证
    try:
        conn = get_db()
        mode = get_setting(conn, 'auth_mode', 'off') or 'off'
        conn.close()
    except Exception:
        mode = 'off'
    if mode == 'global':
        # Allow login and static assets without auth
        allowed = (request.endpoint in {'login', 'static'}) or request.path.startswith('/static/')
        if not allowed and not session.get('auth_ok'):
            nxt = request.url
            return redirect(url_for('login', next=nxt))


@app.route('/')
def index():
    conn = get_db()
    auth_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    q = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'updated')  # updated|created|name|tags
    # 多选筛选：支持 ?tag=a&tag=b 与 ?tags=a,b，两者合并
    selected_tags = [t for t in request.args.getlist('tag') if t.strip()]
    if not selected_tags and request.args.get('tags'):
        selected_tags = [t.strip() for t in request.args.get('tags', '').replace('，', ',').split(',') if t.strip()]
    selected_sources = [s for s in request.args.getlist('source') if s.strip()]
    if not selected_sources and request.args.get('sources'):
        selected_sources = [s.strip() for s in request.args.get('sources', '').replace('，', ',').split(',') if s.strip()]
    order_clause = 'pinned DESC,'
    if sort == 'created':
        order_clause += ' created_at DESC, id DESC'
    elif sort == 'name':
        order_clause += ' name COLLATE NOCASE ASC'
    elif sort == 'tags':
        order_clause += ' tags COLLATE NOCASE ASC'
    else:
        order_clause += ' updated_at DESC, id DESC'

    # join 当前版本进行搜索
    sql = f"""
        SELECT p.*, v.content as current_content, v.version as current_version
        FROM prompts p
        LEFT JOIN versions v ON v.id = p.current_version_id
    """
    params = []
    if q:
        like = f"%{q}%"
        sql += " WHERE (p.name LIKE ? OR p.source LIKE ? OR p.notes LIKE ? OR p.tags LIKE ? OR v.content LIKE ?)"
        params.extend([like, like, like, like, like])
    sql += f" ORDER BY {order_clause}"
    prompts = conn.execute(sql, params).fetchall()
    # 需要密码且未解锁的提示词（仅在“指定提示词密码”模式下生效）
    unlocked = set(session.get('unlocked_prompts') or [])
    locked_ids = set()
    if auth_mode == 'per':
        for r in prompts:
            try:
                if r['require_password'] and (r['id'] not in unlocked):
                    locked_ids.add(r['id'])
            except Exception:
                pass

    # 在当前搜索范围内统计标签与来源计数（便于侧边栏显示）
    tag_counts = {}
    source_counts = {}
    def norm_source(s):
        return (s or '').strip() or '(empty)'
    for r in prompts:
        # tags 存储为 JSON 文本
        if auth_mode == 'per' and r['id'] in locked_ids:
            # 锁定项不参与侧边栏统计
            continue
        try:
            arr = json.loads(r['tags']) if r['tags'] else []
        except Exception:
            arr = []
        for t in arr:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        s = norm_source(r['source'])
        source_counts[s] = source_counts.get(s, 0) + 1

    # 应用多选筛选：同一维度内为 OR；不同维度之间 AND
    def include_row(row):
        # 解析行 tags
        try:
            row_tags = json.loads(row['tags']) if row['tags'] else []
        except Exception:
            row_tags = []
        # 锁定项在应用筛选时不参与匹配
        if (selected_tags or selected_sources) and (auth_mode == 'per') and (row['id'] in locked_ids):
            return False
        ok_tag = True
        if selected_tags:
            ok_tag = any(t in row_tags for t in selected_tags)
        ok_src = True
        if selected_sources:
            ok_src = norm_source(row['source']) in selected_sources
        return ok_tag and ok_src

    if selected_tags or selected_sources:
        prompts = [r for r in prompts if include_row(r)]

    # 标签汇总用于输入联想（排除未解锁的受保护提示词）
    tag_suggestions = []
    all_rows = conn.execute("SELECT id, tags, require_password FROM prompts").fetchall()
    for r in all_rows:
        if auth_mode == 'per' and r['require_password'] and (r['id'] not in unlocked):
            continue
        try:
            arr = json.loads(r['tags']) if r['tags'] else []
            for t in arr:
                if t not in tag_suggestions:
                    tag_suggestions.append(t)
        except Exception:
            pass
    conn.close()
    return render_template(
        'index.html',
        prompts=prompts,
        q=q,
        sort=sort,
        tag_suggestions=tag_suggestions,
        tag_counts=tag_counts,
        source_counts=source_counts,
        selected_tags=selected_tags,
        selected_sources=selected_sources,
        auth_mode=auth_mode,
        locked_ids=list(locked_ids),
    )


@app.route('/prompt/new', methods=['GET', 'POST'])
def new_prompt():
    if request.method == 'POST':
        name = request.form.get('name', '').strip() or '未命名提示词'
        source = request.form.get('source', '').strip()
        notes = request.form.get('notes', '').strip()
        tags = parse_tags(request.form.get('tags', ''))
        content = request.form.get('content', '')
        bump_kind = request.form.get('bump_kind', 'patch')
        require_password = 1 if request.form.get('require_password') == '1' else 0

        conn = get_db()
        cur = conn.cursor()
        ts = now_ts()
        cur.execute(
            "INSERT INTO prompts(name, source, notes, tags, pinned, created_at, updated_at, require_password) VALUES(?,?,?,?,0,?,?,?)",
            (name, source, notes, json.dumps(tags, ensure_ascii=False), ts, ts, require_password)
        )
        pid = cur.lastrowid
        version = bump_version(None, bump_kind)
        cur.execute(
            "INSERT INTO versions(prompt_id, version, content, created_at, parent_version_id) VALUES(?,?,?,?,NULL)",
            (pid, version, content, ts)
        )
        vid = cur.lastrowid
        cur.execute("UPDATE prompts SET current_version_id=? WHERE id=?", (vid, pid))
        prune_versions(conn, pid)
        conn.commit()
        conn.close()
        flash('已创建提示词并保存首个版本', 'success')
        return redirect(url_for('prompt_detail', prompt_id=pid))
    # 读取认证模式控制复选框可用性
    conn = get_db()
    auth_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    conn.close()
    return render_template('prompt_detail.html', prompt=None, versions=[], current=None, auth_mode=auth_mode)


@app.route('/prompt/<int:prompt_id>', methods=['GET', 'POST'])
def prompt_detail(prompt_id):
    conn = get_db()
    auth_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    if request.method == 'POST':
        # 保存新版本或仅更新元信息
        name = request.form.get('name', '').strip() or '未命名提示词'
        source = request.form.get('source', '').strip()
        notes = request.form.get('notes', '').strip()
        tags = parse_tags(request.form.get('tags', ''))
        content = request.form.get('content', '')
        bump_kind = request.form.get('bump_kind', 'patch')
        do_save_version = request.form.get('do_save_version') == '1'
        require_password = 1 if request.form.get('require_password') == '1' else 0
        ts = now_ts()

        conn.execute("UPDATE prompts SET name=?, source=?, notes=?, tags=?, updated_at=?, require_password=? WHERE id=?",
                     (name, source, notes, json.dumps(tags, ensure_ascii=False), ts, require_password, prompt_id))

        if do_save_version:
            # 取当前版本号
            row = conn.execute("SELECT v.version FROM prompts p LEFT JOIN versions v ON v.id=p.current_version_id WHERE p.id=?",
                               (prompt_id,)).fetchone()
            current_ver = row['version'] if row else None
            new_ver = bump_version(current_ver, bump_kind)
            conn.execute(
                "INSERT INTO versions(prompt_id, version, content, created_at, parent_version_id) VALUES(?,?,?,?,(SELECT current_version_id FROM prompts WHERE id=?))",
                (prompt_id, new_ver, content, ts, prompt_id)
            )
            compute_current_version(conn, prompt_id)
            prune_versions(conn, prompt_id)
        else:
            # 如果仅更新元信息，不动 versions，但若没有版本也创建一个
            row = conn.execute("SELECT COUNT(*) AS c FROM versions WHERE prompt_id=?", (prompt_id,)).fetchone()
            if row['c'] == 0:
                conn.execute("INSERT INTO versions(prompt_id, version, content, created_at, parent_version_id) VALUES(?,?,?,?,NULL)",
                             (prompt_id, '1.0.0', content, ts))
                compute_current_version(conn, prompt_id)

        conn.commit()
        conn.close()
        flash('已保存', 'success')
        return redirect(url_for('prompt_detail', prompt_id=prompt_id))

    # GET: 展示
    prompt = conn.execute("SELECT * FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    if not prompt:
        conn.close()
        flash('未找到该提示词', 'error')
        return redirect(url_for('index'))
    # 指定提示词密码模式：未解锁则跳转解锁页
    if auth_mode == 'per' and prompt['require_password']:
        unlocked = set(session.get('unlocked_prompts') or [])
        if prompt['id'] not in unlocked:
            conn.close()
            return redirect(url_for('unlock_prompt', prompt_id=prompt_id, next=url_for('prompt_detail', prompt_id=prompt_id)))
    versions = conn.execute("SELECT * FROM versions WHERE prompt_id=? ORDER BY created_at DESC", (prompt_id,)).fetchall()
    current = conn.execute("SELECT * FROM versions WHERE id=?", (prompt['current_version_id'],)).fetchone() if prompt['current_version_id'] else None
    conn.close()
    return render_template('prompt_detail.html', prompt=prompt, versions=versions, current=current, auth_mode=auth_mode)


@app.route('/prompt/<int:prompt_id>/pin', methods=['POST'])
def toggle_pin(prompt_id):
    conn = get_db()
    row = conn.execute("SELECT pinned FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    if row:
        new_val = 0 if row['pinned'] else 1
        conn.execute("UPDATE prompts SET pinned=?, updated_at=? WHERE id=?", (new_val, now_ts(), prompt_id))
        conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/prompt/<int:prompt_id>/delete', methods=['POST'])
def delete_prompt(prompt_id):
    # 删除提示词：先删关联版本，再删提示词本身
    conn = get_db()
    row = conn.execute("SELECT id, name FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    if not row:
        conn.close()
        flash('提示词不存在或已被删除', 'error')
        return redirect(url_for('index'))

    try:
        conn.execute("DELETE FROM versions WHERE prompt_id=?", (prompt_id,))
        conn.execute("DELETE FROM prompts WHERE id=?", (prompt_id,))
        conn.commit()
        flash('已删除提示词及其所有版本', 'success')
    except Exception:
        conn.rollback()
        flash('删除失败，请重试', 'error')
    finally:
        conn.close()
    return redirect(url_for('index'))

@app.route('/prompt/<int:prompt_id>/rollback/<int:version_id>', methods=['POST'])
def rollback_version(prompt_id, version_id):
    bump_kind = request.form.get('bump_kind', 'patch')
    conn = get_db()
    ver = conn.execute("SELECT * FROM versions WHERE id=? AND prompt_id=?", (version_id, prompt_id)).fetchone()
    if not ver:
        conn.close()
        flash('版本不存在', 'error')
        return redirect(url_for('prompt_detail', prompt_id=prompt_id))
    # 计算新的版本号
    row = conn.execute("SELECT v.version FROM prompts p LEFT JOIN versions v ON v.id=p.current_version_id WHERE p.id=?",
                       (prompt_id,)).fetchone()
    current_ver = row['version'] if row else None
    new_ver = bump_version(current_ver, bump_kind)
    ts = now_ts()
    conn.execute(
        "INSERT INTO versions(prompt_id, version, content, created_at, parent_version_id) VALUES(?,?,?,?,(SELECT current_version_id FROM prompts WHERE id=?))",
        (prompt_id, new_ver, ver['content'], ts, prompt_id)
    )
    compute_current_version(conn, prompt_id)
    prune_versions(conn, prompt_id)
    conn.commit()
    conn.close()
    flash('已从历史版本回滚并创建新版本', 'success')
    return redirect(url_for('prompt_detail', prompt_id=prompt_id))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conn = get_db()
    if request.method == 'POST':
        threshold = request.form.get('version_cleanup_threshold', '200').strip()
        if not threshold.isdigit() or int(threshold) < 1:
            flash('阈值需为正整数', 'error')
        else:
            set_setting(conn, 'version_cleanup_threshold', threshold)
            conn.commit()
            flash('设置已保存', 'success')
        # 访问密码：模式 + 修改密码
        mode = request.form.get('auth_mode', 'off')
        if mode not in ('off', 'per', 'global'):
            mode = 'off'
        new_pw = (request.form.get('new_password') or '').strip()
        confirm_pw = (request.form.get('confirm_password') or '').strip()
        saved_hash = get_setting(conn, 'auth_password_hash', '') or ''
        prev_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
        mode_to_set = mode
        if mode != 'off':
            if not saved_hash and not new_pw:
                flash('请先设置访问密码（4-8 位）', 'error')
                mode_to_set = prev_mode  # 保持原状
            if new_pw:
                if new_pw != confirm_pw:
                    flash('两次输入的密码不一致', 'error')
                    mode_to_set = prev_mode
                elif not (4 <= len(new_pw) <= 8):
                    flash('密码长度需为 4-8 位', 'error')
                    mode_to_set = prev_mode
                else:
                    set_setting(conn, 'auth_password_hash', hash_pw(new_pw))
        set_setting(conn, 'auth_mode', mode_to_set)
        conn.commit()
        # 导入
        if 'import_file' in request.files and request.files['import_file']:
            f = request.files['import_file']
            data = json.load(f.stream)
            # 覆盖所有数据
            cur = conn.cursor()
            cur.execute("DELETE FROM versions")
            cur.execute("DELETE FROM prompts")
            # 可包含 settings
            if isinstance(data, dict) and 'prompts' in data:
                prompts = data['prompts']
            else:
                prompts = data
            for p in prompts:
                cur.execute(
                    "INSERT INTO prompts(id, name, source, notes, tags, pinned, created_at, updated_at, current_version_id, require_password) VALUES(?,?,?,?,?,?,?,?,NULL,?)",
                    (
                        p.get('id'),
                        p.get('name'),
                        p.get('source'),
                        p.get('notes'),
                        json.dumps(p.get('tags') or [], ensure_ascii=False),
                        1 if p.get('pinned') else 0,
                        p.get('created_at') or now_ts(),
                        p.get('updated_at') or now_ts(),
                        1 if p.get('require_password') else 0,
                    )
                )
                pid = cur.lastrowid if p.get('id') is None else p.get('id')
                for v in (p.get('versions') or []):
                    cur.execute(
                        "INSERT INTO versions(id, prompt_id, version, content, created_at, parent_version_id) VALUES(?,?,?,?,?,?)",
                        (
                            v.get('id'),
                            pid,
                            v.get('version'),
                            v.get('content') or '',
                            v.get('created_at') or now_ts(),
                            v.get('parent_version_id'),
                        )
                    )
                compute_current_version(conn, pid)
            conn.commit()
            flash('已导入并覆盖所有数据', 'success')
        conn.close()
        return redirect(url_for('settings'))

    threshold = get_setting(conn, 'version_cleanup_threshold', '200')
    auth_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    conn.close()
    return render_template('settings.html', threshold=threshold, auth_mode=auth_mode)


@app.route('/export')
def export_all():
    conn = get_db()
    prompts = conn.execute("SELECT * FROM prompts ORDER BY id ASC").fetchall()
    result = []
    for p in prompts:
        versions = conn.execute("SELECT * FROM versions WHERE prompt_id=? ORDER BY created_at ASC", (p['id'],)).fetchall()
        result.append({
            'id': p['id'],
            'name': p['name'],
            'source': p['source'],
            'notes': p['notes'],
            'tags': json.loads(p['tags']) if p['tags'] else [],
            'pinned': bool(p['pinned']),
            'require_password': bool(p['require_password']) if 'require_password' in p.keys() else False,
            'created_at': p['created_at'],
            'updated_at': p['updated_at'],
            'current_version_id': p['current_version_id'],
            'versions': [
                {
                    'id': v['id'],
                    'prompt_id': v['prompt_id'],
                    'version': v['version'],
                    'content': v['content'],
                    'created_at': v['created_at'],
                    'parent_version_id': v['parent_version_id'],
                } for v in versions
            ]
        })
    conn.close()
    payload = json.dumps({'prompts': result}, ensure_ascii=False, indent=2)
    bio = BytesIO(payload.encode('utf-8'))
    bio.seek(0)
    return send_file(bio, mimetype='application/json; charset=utf-8', as_attachment=True, download_name='prompts_export.json')


# Diff 视图
from markupsafe import Markup, escape
import re
import difflib


def word_diff_html(a: str, b: str) -> str:
    # 先按行对齐，然后对每对行做词级 diff
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    sm = difflib.SequenceMatcher(None, a_lines, b_lines)
    rows = []

    def tokens(s):
        # 用词与空白/标点作为分隔，并保留分隔符
        return re.findall(r"\w+|\s+|[^\w\s]", s, flags=re.UNICODE)

    def wrap_span(cls, s):
        return Markup(f'<span class="{cls}">{escape(s)}</span>')

    def highlight_pair(al, bl):
        ta = tokens(al)
        tb = tokens(bl)
        sm2 = difflib.SequenceMatcher(None, ta, tb)
        ra = []
        rb = []
        for tag, i1, i2, j1, j2 in sm2.get_opcodes():
            if tag == 'equal':
                ra.append(escape(''.join(ta[i1:i2])))
                rb.append(escape(''.join(tb[j1:j2])))
            elif tag == 'delete':
                ra.append(wrap_span('diff-del', ''.join(ta[i1:i2])))
            elif tag == 'insert':
                rb.append(wrap_span('diff-ins', ''.join(tb[j1:j2])))
            else:  # replace
                ra.append(wrap_span('diff-del', ''.join(ta[i1:i2])))
                rb.append(wrap_span('diff-ins', ''.join(tb[j1:j2])))
        return Markup('').join(ra), Markup('').join(rb)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                left = escape(a_lines[i1 + k])
                right = escape(b_lines[j1 + k])
                rows.append((left, right, ''))
        elif tag == 'delete':
            for line in a_lines[i1:i2]:
                rows.append((wrap_span('diff-del', line), '', 'del'))
        elif tag == 'insert':
            for line in b_lines[j1:j2]:
                rows.append(('', wrap_span('diff-ins', line), 'ins'))
        else:  # replace
            al = a_lines[i1:i2]
            bl = b_lines[j1:j2]
            maxlen = max(len(al), len(bl))
            for k in range(maxlen):
                l = al[k] if k < len(al) else ''
                r = bl[k] if k < len(bl) else ''
                hl, hr = highlight_pair(l, r)
                rows.append((hl, hr, 'chg'))

    # 生成表格 HTML
    html = [
        '<table class="diff-table">',
        '<thead><tr><th>旧版本</th><th>新版本</th></tr></thead>',
        '<tbody>'
    ]
    for l, r, cls in rows:
        html.append(f'<tr class="{cls}"><td class="cell-left">{l}</td><td class="cell-right">{r}</td></tr>')
    html.append('</tbody></table>')
    return Markup('\n'.join(html))


def line_diff_html(a: str, b: str) -> str:
    # 使用 HtmlDiff 生成左右并排行级 diff
    d = difflib.HtmlDiff(wrapcolumn=120)
    html = d.make_table(a.splitlines(), b.splitlines(), context=False, numlines=0)
    # 包装简化，覆写样式类名以与全站风格一致
    # 将 difflib 输出的表格包在容器内
    return Markup(f'<div class="line-diff">{html}</div>')


@app.route('/prompt/<int:prompt_id>/diff')
def diff_view(prompt_id):
    left_id = request.args.get('left')
    right_id = request.args.get('right')
    mode = request.args.get('mode', 'word')  # word|line
    conn = get_db()
    prompt = conn.execute("SELECT * FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    # 未解锁受保护提示词则跳转解锁
    auth_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    if auth_mode == 'per' and prompt and prompt['require_password'] and (prompt_id not in set(session.get('unlocked_prompts') or [])):
        conn.close()
        return redirect(url_for('unlock_prompt', prompt_id=prompt_id, next=url_for('diff_view', prompt_id=prompt_id, left=left_id, right=right_id, mode=mode)))
    versions = conn.execute("SELECT * FROM versions WHERE prompt_id=? ORDER BY created_at DESC", (prompt_id,)).fetchall()
    if not versions:
        conn.close()
        flash('暂无版本', 'info')
        return redirect(url_for('prompt_detail', prompt_id=prompt_id))
    # 默认对比：上一版本 vs 当前版本
    if not right_id and prompt['current_version_id']:
        right_id = str(prompt['current_version_id'])
    if not left_id:
        # 找到 right 的前一个版本
        idx = 0
        for i, v in enumerate(versions):
            if str(v['id']) == str(right_id):
                idx = i
                break
        if idx + 1 < len(versions):
            left_id = str(versions[idx + 1]['id'])
        else:
            left_id = str(versions[idx]['id'])

    left = conn.execute("SELECT * FROM versions WHERE id=? AND prompt_id=?", (left_id, prompt_id)).fetchone()
    right = conn.execute("SELECT * FROM versions WHERE id=? AND prompt_id=?", (right_id, prompt_id)).fetchone()
    conn.close()
    if not left or not right:
        flash('所选版本不存在', 'error')
        return redirect(url_for('prompt_detail', prompt_id=prompt_id))

    if mode == 'line':
        diff_html = line_diff_html(left['content'], right['content'])
    else:
        diff_html = word_diff_html(left['content'], right['content'])

    return render_template('diff.html', prompt=prompt, versions=versions, left=left, right=right, mode=mode, diff_html=diff_html)


@app.route('/prompt/<int:prompt_id>/versions')
def versions_page(prompt_id):
    conn = get_db()
    prompt = conn.execute("SELECT * FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    if not prompt:
        conn.close()
        flash('未找到该提示词', 'error')
        return redirect(url_for('index'))
    # 未解锁受保护提示词则跳转解锁
    auth_mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    if auth_mode == 'per' and prompt['require_password'] and (prompt_id not in set(session.get('unlocked_prompts') or [])):
        conn.close()
        return redirect(url_for('unlock_prompt', prompt_id=prompt_id, next=url_for('versions_page', prompt_id=prompt_id)))
    
    # Convert Row objects to dictionaries for JSON serialization
    versions = conn.execute("SELECT * FROM versions WHERE prompt_id=? ORDER BY created_at DESC", (prompt_id,)).fetchall()
    versions_dict = [dict(version) for version in versions]
    
    current = conn.execute("SELECT * FROM versions WHERE id=?", (prompt['current_version_id'],)).fetchone() if prompt['current_version_id'] else None
    current_dict = dict(current) if current else None
    
    prompt_dict = dict(prompt)
    
    conn.close()
    return render_template('versions.html', prompt=prompt_dict, versions=versions_dict, current=current_dict)


@app.route('/api/tags')
def api_tags():
    conn = get_db()
    tags = get_all_tags(conn)
    conn.close()
    return jsonify(tags)


# === 简易密码认证 ===
import hashlib


def hash_pw(pw: str) -> str:
    return hashlib.sha256((pw or '').encode('utf-8')).hexdigest()


@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = get_db()
    mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    saved_hash = get_setting(conn, 'auth_password_hash', '') or ''
    conn.close()
    nxt = request.values.get('next') or url_for('index')
    if request.method == 'POST':
        password = (request.form.get('password') or '').strip()
        if not (4 <= len(password) <= 8):
            flash('密码长度需为 4-8 位', 'error')
            return render_template('auth.html', mode=mode, action='login', next=nxt)
        if saved_hash and hash_pw(password) == saved_hash:
            session['auth_ok'] = True
            flash('已通过认证', 'success')
            return redirect(nxt)
        else:
            flash('密码不正确', 'error')
    return render_template('auth.html', mode=mode, action='login', next=nxt)


@app.route('/logout')
def logout():
    session.pop('auth_ok', None)
    session.pop('unlocked_prompts', None)
    flash('已退出登录', 'success')
    return redirect(url_for('index'))


@app.route('/prompt/<int:prompt_id>/unlock', methods=['GET', 'POST'])
def unlock_prompt(prompt_id):
    conn = get_db()
    mode = get_setting(conn, 'auth_mode', 'off') or 'off'
    saved_hash = get_setting(conn, 'auth_password_hash', '') or ''
    prompt = conn.execute("SELECT id, name FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    conn.close()
    if not prompt:
        flash('提示词不存在', 'error')
        return redirect(url_for('index'))
    nxt = request.values.get('next') or url_for('prompt_detail', prompt_id=prompt_id)
    if request.method == 'POST':
        password = (request.form.get('password') or '').strip()
        if not (4 <= len(password) <= 8):
            flash('密码长度需为 4-8 位', 'error')
            return render_template('auth.html', mode=mode, action='unlock', prompt=prompt, next=nxt)
        if saved_hash and hash_pw(password) == saved_hash:
            unlocked = set(session.get('unlocked_prompts') or [])
            unlocked.add(prompt_id)
            session['unlocked_prompts'] = list(unlocked)
            flash('已解锁该提示词', 'success')
            return redirect(nxt)
        else:
            flash('密码不正确', 'error')
    return render_template('auth.html', mode=mode, action='unlock', prompt=prompt, next=nxt)


def run():
    ensure_db()
    app.run(host='0.0.0.0', port=3501, debug=True)


if __name__ == '__main__':
    run()
