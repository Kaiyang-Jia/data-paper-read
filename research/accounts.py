"""JSON account API for the web workspace, sharing the legacy user database."""
import re
import secrets
from datetime import timedelta
from functools import wraps

from flask import Blueprint, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest

from research.account_store import AccountStore, NoteConflict, NoteTooLong


def register_account_api(app, backend, normalize_article):
    api = Blueprint('accounts', __name__, url_prefix='/api/account')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    def store():
        if not hasattr(g, 'account_store'):
            db = backend()
            if db is None:
                raise RuntimeError('User database unavailable')
            g.account_store = AccountStore(db)
            g.account_store.initialize()
        return g.account_store

    def public_user(user):
        return {'id': user['id'], 'email': user['email'], 'displayName': user['display_name'],
                'researchField': user['research_field']}

    def csrf():
        if not session.get('csrf'):
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    def signed_in(user):
        session.clear()
        session.permanent = True
        session['account_sid'] = store().start_session(user)
        session['user_id'] = user['id']
        session['credential_stamp'] = AccountStore.digest(user['password_hash'])
        return jsonify(user=public_user(user), csrfToken=csrf())

    @api.before_request
    def protect():
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            token = request.headers.get('X-CSRF-Token', '')
            if not token or not secrets.compare_digest(token, session.get('csrf', '')):
                return jsonify(message='页面验证已失效，请重新连接后重试。', code='csrf_expired'), 403
            if not request.is_json:
                return jsonify(message='请求格式不正确。'), 400
        g.account_user = None
        if session.get('account_sid'):
            g.account_user = store().session_user(session['account_sid'])

    @api.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['Vary'] = 'Cookie'
        return response

    @api.errorhandler(Exception)
    def failure(error):
        from werkzeug.exceptions import HTTPException
        if isinstance(error, NoteTooLong):
            return jsonify(message='合并后的笔记超过 20000 字，请先整理本地笔记。原记录未修改。'), 400
        if isinstance(error, HTTPException):
            return jsonify(message='请求格式不正确。'), error.code
        app.logger.error('Account API unavailable: %s', type(error).__name__)
        return jsonify(message='账户服务暂时不可用，未同步的笔记请保留后重试。'), 503

    def required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.account_user:
                return jsonify(message='登录已过期，请重新登录。'), 401
            if request.headers.get('X-Account-User') != str(g.account_user['id']):
                return jsonify(message='登录账号已改变，请重新加载。', code='account_changed'), 409
            return view(*args, **kwargs)
        return wrapped

    def payload():
        value = request.get_json()
        if not isinstance(value, dict):
            raise BadRequest('Invalid payload')
        return value

    def text(value, maximum):
        return value.strip() if isinstance(value, str) and len(value) <= maximum else ''

    def article(value):
        if not isinstance(value, dict):
            return None
        result = normalize_article(value)
        return result if result['article_key'] else None

    def library_data():
        user_id = g.account_user['id']
        return {'favorites': backend().get_user_favorites(user_id, limit=100000),
                'notes': store().notes(user_id),
                'history': backend().get_user_reading_history(user_id, limit=100)}

    @api.get('/session')
    def current_session():
        # A missing backend is an error, not a silent switch to guest storage.
        store()
        return jsonify(user=public_user(g.account_user) if g.account_user else None, csrfToken=csrf())

    @api.post('/register')
    @api.post('/login')
    def authenticate():
        data = payload()
        email = text(data.get('email'), 254).lower()
        password = data.get('password')
        registering = request.path.endswith('/register')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or not isinstance(password, str) or not 8 <= len(password) <= 128:
            return jsonify(message='请输入有效邮箱和 8–128 位密码。'), 400
        # Buckets never store raw email/IP and do not trust browser IP headers.
        if not store().permit_attempt('email:' + email) or not store().permit_attempt('ip:' + str(request.remote_addr), limit=60):
            return jsonify(message='尝试次数过多，请 15 分钟后重试。'), 429
        if registering:
            name = text(data.get('displayName'), 100)
            field = text(data.get('researchField', ''), 500)
            if not 2 <= len(name) <= 100 or password != data.get('confirmPassword'):
                return jsonify(message='昵称需为 2–100 字，且两次密码应一致。'), 400
            if not backend().initialize_tables():
                raise RuntimeError('Cannot initialize users')
            user_id = backend().create_user(email, generate_password_hash(password), name, field)
            if not user_id:
                return jsonify(message='该邮箱已经注册，请登录。'), 409
        user = backend().get_user_by_email(email)
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify(message='邮箱或密码不正确。'), 401
        if session.get('account_sid'):
            store().revoke(session['account_sid'])
        return signed_in(user)

    @api.post('/logout')
    def logout():
        if session.get('account_sid'):
            store().revoke(session['account_sid'])
        session.clear()
        return jsonify(user=None, csrfToken=csrf())

    @api.post('/profile')
    @required
    def profile():
        data = payload()
        name, field = text(data.get('displayName'), 100), text(data.get('researchField', ''), 500)
        if len(name) < 2 or not isinstance(data.get('researchField', ''), str) or len(data.get('researchField', '')) > 500:
            return jsonify(message='昵称需为 2–100 字，研究方向不超过 500 字。'), 400
        backend().update_user_profile(g.account_user['id'], name, field)
        return jsonify(user=public_user(backend().get_user_by_id(g.account_user['id'])))

    @api.post('/password')
    @required
    def password():
        data = payload()
        old, new = data.get('currentPassword'), data.get('password')
        if not isinstance(old, str) or len(old) > 128 or not isinstance(new, str) or not 8 <= len(new) <= 128 or new != data.get('confirmPassword'):
            return jsonify(message='新密码需为 8–128 位，且两次输入一致。'), 400
        if not store().permit_attempt('password:' + str(g.account_user['id'])):
            return jsonify(message='尝试次数过多，请 15 分钟后重试。'), 429
        user = backend().get_user_by_email(g.account_user['email'])
        if not check_password_hash(user['password_hash'], old):
            return jsonify(message='当前密码不正确。'), 400
        if not store().change_password(user['id'], user['password_hash'], generate_password_hash(new)):
            return jsonify(message='账户已更新，请重新登录。'), 409
        session.clear()
        return jsonify(user=None, csrfToken=csrf(), message='密码已修改，请使用新密码重新登录。')

    @api.get('/library')
    @required
    def library():
        return jsonify(library_data())

    @api.post('/favorite')
    @required
    def favorite():
        data = payload()
        paper = article(data.get('article'))
        if not paper or not isinstance(data.get('favorite'), bool):
            return jsonify(message='收藏格式不正确。'), 400
        backend().toggle_favorite(g.account_user['id'], paper, data['favorite'])
        return jsonify(ok=True)

    @api.post('/note')
    @required
    def note():
        data = payload()
        paper, body, revision = article(data.get('article')), data.get('text'), data.get('revision')
        if not paper or not isinstance(body, str) or len(body) > 20000 or type(revision) is not int or revision < 0:
            return jsonify(message='笔记格式不正确或超过 20000 字。'), 400
        try:
            return jsonify(store().save_note(g.account_user['id'], paper, body, revision))
        except NoteConflict as error:
            return jsonify(message='另一处已更新这篇笔记，请核对两个版本后保存。', note=error.note), 409

    @api.post('/read')
    @required
    def read():
        paper = article(payload().get('article'))
        if not paper:
            return jsonify(message='缺少论文标识。'), 400
        backend().record_article_read(g.account_user['id'], paper)
        return jsonify(ok=True)

    @api.post('/history/clear')
    @required
    def clear_history():
        backend().clear_reading_history(g.account_user['id'])
        return jsonify(ok=True)

    @api.post('/import')
    @required
    def import_library():
        entries = payload().get('entries')
        if not isinstance(entries, list) or len(entries) > 100:
            return jsonify(message='每批最多导入 100 篇文献。'), 400
        cleaned = []
        for entry in entries:
            if not isinstance(entry, dict):
                return jsonify(message='导入格式不正确。'), 400
            paper, body = article(entry.get('article')), entry.get('note', '')
            if not paper or not isinstance(body, str) or len(body) > 10000 or not isinstance(entry.get('favorite'), bool):
                return jsonify(message='导入条目不正确或笔记过长。'), 400
            cleaned.append({'article': paper, 'note': body, 'favorite': entry['favorite']})
        return jsonify(store().import_library(g.account_user['id'], cleaned))

    app.register_blueprint(api)
