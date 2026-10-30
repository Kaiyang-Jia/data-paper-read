"""Account persistence in the configured user database (never a fallback database).

SQLite is used by the local launcher; the same additions can live alongside the
existing MariaDB users. Notes use compare-and-swap revisions, including deletes.
"""
from contextlib import contextmanager
import hashlib
import json
import secrets
import time

from get_data.local_user_db import LocalUserDB


class NoteConflict(Exception):
    def __init__(self, note):
        self.note = note


class NoteTooLong(Exception):
    pass


class AccountStore:
    def __init__(self, backend):
        self.backend = backend
        self.sqlite = backend is LocalUserDB

    @contextmanager
    def transaction(self):
        if self.sqlite:
            with self.backend.get_connection() as connection:
                # Serialize read/modify/write operations, including imports.
                connection.execute('BEGIN IMMEDIATE')
                yield connection
        else:
            import pymysql
            connection = self.backend.get_connection()
            if connection is None:
                raise RuntimeError('User database unavailable')
            try:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    yield cursor
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def execute(self, connection, sql, params=()):
        if self.sqlite:
            return connection.execute(sql, params)
        connection.execute(sql.replace('?', '%s'), params)
        return connection

    def initialize(self):
        # Additive migrations: the existing users/favorites/history stay intact.
        statements = [
            '''CREATE TABLE IF NOT EXISTS account_sessions (
                token_hash VARCHAR(64) PRIMARY KEY, user_id INTEGER NOT NULL,
                expires_at BIGINT NOT NULL, credential_stamp VARCHAR(64) NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS account_notes (
                user_id INTEGER NOT NULL, key_hash VARCHAR(64) NOT NULL,
                article_key TEXT NOT NULL, article_json TEXT NOT NULL,
                body TEXT NOT NULL, revision INTEGER NOT NULL, updated_at BIGINT NOT NULL,
                PRIMARY KEY(user_id, key_hash))''',
            '''CREATE TABLE IF NOT EXISTS account_imports (
                user_id INTEGER NOT NULL, digest VARCHAR(64) NOT NULL,
                PRIMARY KEY(user_id, digest))''',
            '''CREATE TABLE IF NOT EXISTS account_rate_limits (
                bucket VARCHAR(64) PRIMARY KEY, attempts INTEGER NOT NULL,
                reset_at BIGINT NOT NULL)''',
        ]
        with self.transaction() as connection:
            for sql in statements:
                self.execute(connection, sql)

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def start_session(self, user):
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.transaction() as connection:
            self.execute(connection, 'DELETE FROM account_sessions WHERE expires_at < ?', (now,))
            self.execute(connection, 'INSERT INTO account_sessions VALUES (?, ?, ?, ?)',
                         (self.digest(token), user['id'], now + 7 * 86400,
                          self.digest(user['password_hash'])))
        return token

    def session_user(self, token):
        with self.transaction() as connection:
            row = self.execute(connection, '''SELECT s.user_id, s.credential_stamp,
                u.password_hash FROM account_sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ?''',
                (self.digest(token), int(time.time()))).fetchone()
        if not row or row['credential_stamp'] != self.digest(row['password_hash']):
            return None
        return self.backend.get_user_by_id(row['user_id'])

    def revoke(self, token):
        with self.transaction() as connection:
            self.execute(connection, 'DELETE FROM account_sessions WHERE token_hash = ?', (self.digest(token),))

    def change_password(self, user_id, previous_hash, password_hash):
        with self.transaction() as connection:
            self.lock_user(connection, user_id)
            result = self.execute(connection, 'UPDATE users SET password_hash = ? WHERE id = ? AND password_hash = ?',
                                  (password_hash, user_id, previous_hash))
            if result.rowcount != 1:
                return False
            self.execute(connection, 'DELETE FROM account_sessions WHERE user_id = ?', (user_id,))
        return True

    def permit_attempt(self, bucket, limit=10, seconds=900):
        now, key = int(time.time()), self.digest(bucket)
        with self.transaction() as connection:
            self.execute(connection, 'DELETE FROM account_rate_limits WHERE reset_at <= ?', (now,))
            row = self.execute(connection, 'SELECT attempts FROM account_rate_limits WHERE bucket = ?', (key,)).fetchone()
            if row and row['attempts'] >= limit:
                return False
            if row:
                self.execute(connection, 'UPDATE account_rate_limits SET attempts = attempts + 1 WHERE bucket = ?', (key,))
            else:
                self.execute(connection, 'INSERT INTO account_rate_limits VALUES (?, 1, ?)', (key, now + seconds))
        return True

    def notes(self, user_id):
        with self.transaction() as connection:
            rows = self.execute(connection, 'SELECT * FROM account_notes WHERE user_id = ?', (user_id,)).fetchall()
        return {row['article_key']: {'text': row['body'], 'revision': row['revision'],
                'article': json.loads(row['article_json'])} for row in rows}

    def _save_note(self, connection, user_id, article, body, revision, merge=False):
        key = article['article_key']
        key_hash = self.digest(key)
        row = self.execute(connection, 'SELECT body, revision FROM account_notes WHERE user_id = ? AND key_hash = ?',
                           (user_id, key_hash)).fetchone()
        current = {'text': row['body'] if row else '', 'revision': row['revision'] if row else 0}
        if merge:
            if body == current['text'] or not body:
                return current
            body = current['text'] + '\n\n—— 导入的本地笔记 ——\n' + body if current['text'] else body
        elif revision != current['revision']:
            # A retried request whose first response was lost is already saved.
            if body == current['text']:
                return current
            raise NoteConflict(current)
        if len(body) > 20000:
            raise NoteTooLong()
        revision = current['revision'] + 1
        payload = json.dumps(article, ensure_ascii=False)
        if row:
            self.execute(connection, '''UPDATE account_notes SET body = ?, revision = ?,
                article_json = ?, updated_at = ? WHERE user_id = ? AND key_hash = ?''',
                (body, revision, payload, int(time.time()), user_id, key_hash))
        else:
            self.execute(connection, 'INSERT INTO account_notes VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (user_id, key_hash, key, payload, body, revision, int(time.time())))
        return {'text': body, 'revision': revision}

    def save_note(self, user_id, article, body, revision):
        with self.transaction() as connection:
            self.lock_user(connection, user_id)
            return self._save_note(connection, user_id, article, body, revision)

    def lock_user(self, connection, user_id):
        if not self.sqlite:
            self.execute(connection, 'SELECT id FROM users WHERE id = ? FOR UPDATE', (user_id,)).fetchone()

    def import_library(self, user_id, entries):
        # Updating a catalog title must not make an old local note look new.
        identity = sorted([{'key': e['article']['article_key'], 'favorite': e['favorite'],
                            'note': e['note']} for e in entries], key=lambda e: (e['key'], e['note'], e['favorite']))
        digest = self.digest(json.dumps(identity, sort_keys=True, ensure_ascii=False))
        with self.transaction() as connection:
            self.lock_user(connection, user_id)
            if self.execute(connection, 'SELECT digest FROM account_imports WHERE user_id = ? AND digest = ?',
                            (user_id, digest)).fetchone():
                return {'favorites': 0, 'notes': 0, 'conflicts': 0, 'alreadyImported': True}
            counts = {'favorites': 0, 'notes': 0, 'conflicts': 0, 'alreadyImported': False}
            for entry in entries:
                article = entry['article']
                key = article['article_key']
                if entry['favorite']:
                    exists = self.execute(connection, 'SELECT id FROM user_favorites WHERE user_id = ? AND article_key = ?',
                                          (user_id, key)).fetchone()
                    if not exists:
                        self.execute(connection, '''INSERT INTO user_favorites
                            (user_id, article_key, doi, url, title, title_cn, journal, subject, publish_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (user_id, key, article.get('doi'), article.get('url'), article.get('title'),
                             article.get('titleCn'), article.get('journal'), article.get('Subject'), article.get('publishDate')))
                        counts['favorites'] += 1
                if entry['note']:
                    note_digest = self.digest('note:' + key + '\0' + entry['note'])
                    imported_note = self.execute(connection,
                        'SELECT digest FROM account_imports WHERE user_id = ? AND digest = ?',
                        (user_id, note_digest)).fetchone()
                    if imported_note:
                        continue
                    row = self.execute(connection, 'SELECT body FROM account_notes WHERE user_id = ? AND key_hash = ?',
                                       (user_id, self.digest(key))).fetchone()
                    if row and row['body'] and row['body'] != entry['note']:
                        counts['conflicts'] += 1
                    self._save_note(connection, user_id, article, entry['note'], 0, merge=True)
                    self.execute(connection, 'INSERT INTO account_imports VALUES (?, ?)', (user_id, note_digest))
                    counts['notes'] += 1
            self.execute(connection, 'INSERT INTO account_imports VALUES (?, ?)', (user_id, digest))
        return counts
