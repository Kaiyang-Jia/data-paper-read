#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta


DATABASE_PATH = os.environ.get(
    'LOCAL_USER_DB_PATH',
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local_users.db')
)


class LocalUserDB:
    """用于本地预览和测试的 SQLite 用户数据库。"""

    @staticmethod
    @contextmanager
    def get_connection():
        connection = sqlite3.connect(
            DATABASE_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        try:
            # sqlite3's context manager commits/rolls back but does not close.
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def initialize_tables():
        with LocalUserDB.get_connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    research_field TEXT NOT NULL,
                    email_subscribed INTEGER NOT NULL DEFAULT 0,
                    email_frequency TEXT NOT NULL DEFAULT 'weekly',
                    unsubscribe_token TEXT UNIQUE,
                    last_email_sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    article_key TEXT NOT NULL,
                    doi TEXT,
                    url TEXT,
                    title TEXT,
                    title_cn TEXT,
                    journal TEXT,
                    subject TEXT,
                    publish_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, article_key),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_reading_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    article_key TEXT NOT NULL,
                    doi TEXT,
                    url TEXT,
                    title TEXT,
                    title_cn TEXT,
                    journal TEXT,
                    subject TEXT,
                    publish_date TEXT,
                    view_count INTEGER NOT NULL DEFAULT 1,
                    first_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, article_key),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
        return True

    @staticmethod
    def _as_dict(row):
        return dict(row) if row else None

    @staticmethod
    def create_user(email, password_hash, display_name, research_field):
        try:
            with LocalUserDB.get_connection() as connection:
                cursor = connection.execute("""
                    INSERT INTO users (
                        email, password_hash, display_name, research_field,
                        unsubscribe_token
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    email, password_hash, display_name, research_field,
                    secrets.token_urlsafe(32)
                ))
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    @staticmethod
    def get_user_by_email(email):
        with LocalUserDB.get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
            return LocalUserDB._as_dict(row)

    @staticmethod
    def get_user_by_id(user_id):
        with LocalUserDB.get_connection() as connection:
            row = connection.execute("""
                SELECT id, email, display_name, research_field,
                       email_subscribed, email_frequency, unsubscribe_token,
                       last_email_sent_at, created_at, updated_at
                FROM users WHERE id = ?
            """, (user_id,)).fetchone()
            return LocalUserDB._as_dict(row)

    @staticmethod
    def update_user_profile(user_id, display_name, research_field):
        with LocalUserDB.get_connection() as connection:
            cursor = connection.execute("""
                UPDATE users
                SET display_name = ?, research_field = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (display_name, research_field, user_id))
            return cursor.rowcount > 0

    @staticmethod
    def update_email_subscription(user_id, subscribed, frequency):
        with LocalUserDB.get_connection() as connection:
            cursor = connection.execute("""
                UPDATE users
                SET email_subscribed = ?, email_frequency = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (int(bool(subscribed)), frequency, user_id))
            return cursor.rowcount > 0

    @staticmethod
    def get_due_email_subscribers(now=None):
        current_time = now or datetime.now()
        with LocalUserDB.get_connection() as connection:
            rows = connection.execute("""
                SELECT id, email, display_name, research_field, email_frequency,
                       unsubscribe_token, last_email_sent_at
                FROM users
                WHERE email_subscribed = 1
                ORDER BY id
            """).fetchall()
        users = []
        for row in rows:
            user = dict(row)
            last_sent = user.get('last_email_sent_at')
            interval = timedelta(days=1 if user['email_frequency'] == 'daily' else 7)
            if not last_sent or last_sent <= current_time - interval:
                users.append(user)
        return users

    @staticmethod
    def mark_subscription_email_sent(user_id, sent_at=None):
        with LocalUserDB.get_connection() as connection:
            cursor = connection.execute("""
                UPDATE users SET last_email_sent_at = ? WHERE id = ?
            """, (sent_at or datetime.now(), user_id))
            return cursor.rowcount > 0

    @staticmethod
    def get_user_by_unsubscribe_token(token):
        with LocalUserDB.get_connection() as connection:
            row = connection.execute("""
                SELECT id, email, display_name, email_subscribed
                FROM users WHERE unsubscribe_token = ?
            """, (token,)).fetchone()
            return LocalUserDB._as_dict(row)

    @staticmethod
    def toggle_favorite(user_id, article, should_favorite):
        with LocalUserDB.get_connection() as connection:
            if should_favorite:
                connection.execute("""
                    INSERT INTO user_favorites (
                        user_id, article_key, doi, url, title, title_cn,
                        journal, subject, publish_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, article_key) DO UPDATE SET
                        doi = excluded.doi,
                        url = excluded.url,
                        title = excluded.title,
                        title_cn = excluded.title_cn,
                        journal = excluded.journal,
                        subject = excluded.subject,
                        publish_date = excluded.publish_date
                """, (
                    user_id, article['article_key'], article.get('doi'),
                    article.get('url'), article.get('title'), article.get('titleCn'),
                    article.get('journal'), article.get('Subject'),
                    article.get('publishDate')
                ))
            else:
                connection.execute("""
                    DELETE FROM user_favorites
                    WHERE user_id = ? AND article_key = ?
                """, (user_id, article['article_key']))
        return should_favorite

    @staticmethod
    def record_article_read(user_id, article):
        with LocalUserDB.get_connection() as connection:
            connection.execute("""
                INSERT INTO user_reading_history (
                    user_id, article_key, doi, url, title, title_cn,
                    journal, subject, publish_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, article_key) DO UPDATE SET
                    doi = excluded.doi,
                    url = excluded.url,
                    title = excluded.title,
                    title_cn = excluded.title_cn,
                    journal = excluded.journal,
                    subject = excluded.subject,
                    publish_date = excluded.publish_date,
                    view_count = user_reading_history.view_count + 1,
                    last_read_at = CURRENT_TIMESTAMP
            """, (
                user_id, article['article_key'], article.get('doi'),
                article.get('url'), article.get('title'), article.get('titleCn'),
                article.get('journal'), article.get('Subject'),
                article.get('publishDate')
            ))
        return True

    @staticmethod
    def get_user_favorites(user_id, limit=100):
        with LocalUserDB.get_connection() as connection:
            rows = connection.execute("""
                SELECT article_key, doi, url, title, title_cn AS titleCn,
                       journal, subject AS Subject, publish_date AS publishDate,
                       created_at
                FROM user_favorites
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_user_reading_history(user_id, limit=100):
        with LocalUserDB.get_connection() as connection:
            rows = connection.execute("""
                SELECT article_key, doi, url, title, title_cn AS titleCn,
                       journal, subject AS Subject, publish_date AS publishDate,
                       view_count, first_read_at, last_read_at
                FROM user_reading_history
                WHERE user_id = ?
                ORDER BY last_read_at DESC
                LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_user_library_state(user_id):
        with LocalUserDB.get_connection() as connection:
            rows = connection.execute(
                "SELECT article_key FROM user_favorites WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            return [row['article_key'] for row in rows]

    @staticmethod
    def clear_reading_history(user_id):
        with LocalUserDB.get_connection() as connection:
            connection.execute(
                "DELETE FROM user_reading_history WHERE user_id = ?",
                (user_id,)
            )
        return True
