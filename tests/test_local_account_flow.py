"""Check legacy local account persistence and isolation without production users."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as server
from get_data import local_user_db as db


class LocalAccountFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = patch.object(db, 'DATABASE_PATH', str(Path(self.temp.name) / 'users.db'))
        self.backend = patch.object(server, 'USER_DB', db.LocalUserDB)
        self.retrieval = patch.object(server, 'retrieve_research_candidates', return_value=[])
        self.database.start()
        self.backend.start()
        self.retrieval.start()
        db.LocalUserDB.initialize_tables()
        self.client = server.app.test_client()

    def tearDown(self):
        self.retrieval.stop()
        self.backend.stop()
        self.database.stop()
        self.temp.cleanup()

    def register(self, client, email):
        response = client.post('/register', data={'email': email, 'display_name': '功能验收', 'research_field': '城市热岛', 'password': 'test-only-password', 'confirm_password': 'test-only-password'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/profile'))

    def test_favorites_survive_login_and_remain_private(self):
        self.register(self.client, 'module-check@example.invalid')
        self.assertEqual(self.client.get('/profile').status_code, 200)
        paper = {'doi': '10.5194/essd-18-3289-2026', 'title': 'OasisMap30'}
        key = 'doi:' + paper['doi']
        response = self.client.post('/api/library/favorite', json={'article': paper, 'favorite': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/library/state').get_json()['favoriteKeys'], [key])
        other = server.app.test_client()
        self.assertEqual(other.get('/api/library/state').status_code, 401)
        self.register(other, 'other-check@example.invalid')
        self.assertEqual(other.get('/api/library/state').get_json()['favoriteKeys'], [])
        self.assertEqual(self.client.post('/api/library/read', json={'article': paper}).status_code, 200)
        self.assertEqual(self.client.post('/logout').status_code, 302)
        self.assertEqual(self.client.get('/api/library/state').status_code, 401)
        self.assertEqual(self.client.post('/login', data={'email': 'module-check@example.invalid', 'password': 'test-only-password'}).status_code, 302)
        self.assertEqual(self.client.get('/api/library/state').get_json()['favoriteKeys'], [key])

    def test_feedback_saves_to_isolated_file(self):
        target = Path(self.temp.name) / 'feedback.csv'
        with patch.object(server, 'FEEDBACK_FILE', str(target)):
            response = self.client.post('/submit_feedback', data={'title': '验收样例', 'content': '只保存到隔离测试目录'})
        self.assertTrue(response.get_json()['success'])
        self.assertIn('验收样例', target.read_text(encoding='utf-8'))
