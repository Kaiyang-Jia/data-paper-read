"""New web accounts: isolated storage, revocation, migration and concurrency."""
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as server
from get_data import local_user_db as db
from research.account_store import AccountStore, NoteConflict

PAPER = {'doi': '10.1234/account-test', 'title': 'Account test paper', 'titleCn': '账户验收文献'}
KEY = 'doi:10.1234/account-test'
PASSWORD = 'test-password-only'


class AccountAPITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = patch.object(db, 'DATABASE_PATH', str(Path(self.temp.name) / 'users.db'))
        self.backend = patch.object(server, 'USER_DB', db.LocalUserDB)
        self.database.start()
        self.backend.start()
        db.LocalUserDB.initialize_tables()
        self.client = server.app.test_client()
        self.headers = {}

    def tearDown(self):
        self.backend.stop()
        self.database.stop()
        self.temp.cleanup()

    def start(self, client=None, email='first@example.invalid', register=True):
        client = client or self.client
        csrf = client.get('/api/account/session').get_json()['csrfToken']
        result = client.post('/api/account/' + ('register' if register else 'login'),
            json={'email': email, 'password': PASSWORD, 'confirmPassword': PASSWORD, 'displayName': '测试账号'},
            headers={'X-CSRF-Token': csrf})
        self.assertEqual(result.status_code, 200, result.get_json())
        data = result.get_json()
        headers = {'X-CSRF-Token': data['csrfToken'], 'X-Account-User': str(data['user']['id'])}
        if client is self.client:
            self.headers = headers
        return headers

    def post(self, path, data):
        return self.client.post('/api/account/' + path, json=data, headers=self.headers)

    def library(self, client=None, headers=None):
        result = (client or self.client).get('/api/account/library', headers=headers or self.headers)
        self.assertEqual(result.status_code, 200, result.get_json())
        return result.get_json()

    def test_persistence_isolation_profile_and_history(self):
        self.start()
        self.assertEqual(self.post('profile', {'displayName': '更新昵称', 'researchField': ''}).status_code, 200)
        self.assertEqual(self.post('favorite', {'article': PAPER, 'favorite': True, 'user_id': 999}).status_code, 200)
        self.assertEqual(self.post('note', {'article': PAPER, 'text': '私人笔记', 'revision': 0}).status_code, 200)
        self.assertEqual(self.post('read', {'article': PAPER}).status_code, 200)
        self.assertEqual(len(self.library()['history']), 1)
        other = server.app.test_client()
        other_headers = self.start(other, 'other@example.invalid')
        self.assertEqual(self.library(other, other_headers), {'favorites': [], 'notes': {}, 'history': []})
        mismatch = other.post('/api/account/note', json={'article': PAPER, 'text': 'attack', 'revision': 1},
            headers={**other_headers, 'X-Account-User': self.headers['X-Account-User']})
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(self.post('logout', {}).status_code, 200)
        self.assertEqual(self.client.get('/api/account/library', headers=self.headers).status_code, 401)
        self.start(register=False)
        saved = self.library()
        self.assertEqual(len(saved['favorites']), 1)
        self.assertEqual(saved['notes'][KEY]['text'], '私人笔记')
        self.post('history/clear', {})
        self.assertEqual(self.library()['history'], [])
        self.assertEqual(len(self.library()['favorites']), 1)

    def test_csrf_validation_and_no_private_caching(self):
        self.start()
        response = self.client.post('/api/account/favorite', json={'article': PAPER, 'favorite': True})
        self.assertEqual(response.status_code, 403)
        response = self.client.get('/api/account/library', headers=self.headers)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(self.post('favorite', {'article': PAPER, 'favorite': 'false'}).status_code, 400)
        self.assertEqual(self.post('note', {'article': PAPER, 'text': 'x', 'revision': True}).status_code, 400)
        self.assertEqual(self.post('profile', []).status_code, 400)

    def test_logout_revokes_replayed_cookie(self):
        self.start()
        cookie = self.client.get_cookie('session').value
        self.post('logout', {})
        replay = server.app.test_client()
        replay.set_cookie('session', cookie)
        self.assertIsNone(replay.get('/api/account/session').get_json()['user'])

    def test_password_change_revokes_all_devices_and_old_token(self):
        self.start()
        other = server.app.test_client()
        other_headers = self.start(other, register=False)
        token = server.issue_miniprogram_token(int(self.headers['X-Account-User']))
        self.assertEqual(self.post('password', {'currentPassword': PASSWORD, 'password': 'new-test-password',
                                             'confirmPassword': 'new-test-password'}).status_code, 200)
        self.assertIsNone(other.get('/api/account/session').get_json()['user'])
        self.assertEqual(other.get('/api/account/library', headers=other_headers).status_code, 401)
        with server.app.test_request_context(headers={'Authorization': 'Bearer ' + token}):
            self.assertIsNone(server.get_miniprogram_user())
        csrf = self.client.get('/api/account/session').get_json()['csrfToken']
        self.assertEqual(self.client.post('/api/account/login', json={'email': 'first@example.invalid', 'password': 'new-test-password'},
                                         headers={'X-CSRF-Token': csrf}).status_code, 200)

    def test_note_conflict_and_tombstone_do_not_lose_other_device_edits(self):
        self.start()
        self.post('note', {'article': PAPER, 'text': '设备一', 'revision': 0})
        conflict = self.post('note', {'article': PAPER, 'text': '设备二', 'revision': 0})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.get_json()['note']['text'], '设备一')
        self.post('note', {'article': PAPER, 'text': '', 'revision': 1})
        self.assertEqual(self.post('note', {'article': PAPER, 'text': '旧内容', 'revision': 1}).status_code, 409)
        # Lost response retry is idempotent even after revision increment.
        self.assertEqual(self.post('note', {'article': PAPER, 'text': '', 'revision': 1}).status_code, 200)

    def test_import_merges_preserves_original_and_can_retry(self):
        self.start()
        self.post('note', {'article': PAPER, 'text': '账号版本', 'revision': 0})
        data = {'entries': [{'article': PAPER, 'favorite': True, 'note': '浏览器版本'}]}
        first = self.post('import', data).get_json()
        self.assertEqual(first['conflicts'], 1)
        second = self.post('import', data).get_json()
        self.assertTrue(second['alreadyImported'])
        saved = self.library()
        self.assertEqual(len(saved['favorites']), 1)
        self.assertEqual(saved['notes'][KEY]['text'].count('浏览器版本'), 1)
        self.assertIn('账号版本', saved['notes'][KEY]['text'])
        # Catalog corrections and local favorite changes do not duplicate notes.
        data['entries'][0]['article'] = {**PAPER, 'titleCn': '更新后的题名'}
        self.assertTrue(self.post('import', data).get_json()['alreadyImported'])
        data['entries'][0]['favorite'] = False
        self.assertEqual(self.post('import', data).status_code, 200)
        self.assertEqual(self.library()['notes'][KEY]['text'].count('浏览器版本'), 1)

    def test_oversized_import_rolls_back_without_changing_favorites(self):
        self.start()
        self.post('note', {'article': PAPER, 'text': 'a' * 19000, 'revision': 0})
        result = self.post('import', {'entries': [{'article': PAPER, 'favorite': True, 'note': 'b' * 2000}]})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.library()['favorites'], [])
        self.assertEqual(self.library()['notes'][KEY]['text'], 'a' * 19000)

    def test_legacy_login_cannot_bypass_rate_or_origin_protection(self):
        self.start()
        self.assertEqual(self.client.post('/login', data={'email': 'first@example.invalid', 'password': PASSWORD},
            headers={'Origin': 'https://untrusted.example'}).status_code, 403)
        accounts = AccountStore(db.LocalUserDB)
        for _ in range(10):
            accounts.permit_attempt('email:first@example.invalid')
        self.assertEqual(self.client.post('/login', data={'email': 'first@example.invalid', 'password': PASSWORD}).status_code, 429)

    def test_concurrent_note_creates_cannot_overwrite_each_other(self):
        self.start()
        store = AccountStore(db.LocalUserDB)
        paper = server.normalize_user_article(PAPER)
        def write(body):
            try:
                store.save_note(int(self.headers['X-Account-User']), paper, body, 0)
                return 'saved'
            except NoteConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ['one', 'two']))
        self.assertCountEqual(results, ['saved', 'conflict'])

    def test_rate_limit_and_legacy_user_compatibility(self):
        user_id = db.LocalUserDB.create_user('legacy@example.invalid', server.generate_password_hash(PASSWORD), '旧账号', '')
        db.LocalUserDB.toggle_favorite(user_id, server.normalize_user_article(PAPER), True)
        self.start(email='legacy@example.invalid', register=False)
        self.assertEqual(len(self.library()['favorites']), 1)
        for _ in range(10):
            response = self.post('login', {'email': 'legacy@example.invalid', 'password': 'wrong-password'})
        self.assertEqual(response.status_code, 429)


if __name__ == '__main__':
    unittest.main()
