"""Run: python tests.py (tests never call paid APIs)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import actions
from agent import AgentError, offline_plan, validate_plan

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / 'workspace'
        self.workspace.mkdir()
        self._old_workspace = actions.WORKSPACE
        self._old_data = actions.DATA_DIR
        self._old_db = actions.DB_PATH
        self._old_log = actions.LOG_PATH
        actions.WORKSPACE = self.workspace
        actions.DATA_DIR = Path(self.tmp.name)
        actions.DB_PATH = Path(self.tmp.name) / 'test.db'
        actions.LOG_PATH = Path(self.tmp.name) / 'audit.jsonl'

    def tearDown(self):
        actions.WORKSPACE = self._old_workspace
        actions.DATA_DIR = self._old_data
        actions.DB_PATH = self._old_db
        actions.LOG_PATH = self._old_log
        self.tmp.cleanup()

    def test_file_create_read_list(self):
        self.assertIn('Created', actions.execute('write_file', {'filename': 'sample.md', 'content': 'Hello'}))
        self.assertIn('Hello', actions.execute('read_file', {'filename': 'sample.md'}))
        self.assertIn('sample.md', actions.execute('list_files', {}))

    def test_delete_confirmation(self):
        actions.execute('write_file', {'filename': 'sample.txt', 'content': 'X'})
        self.assertIn('ERROR:', actions.execute('delete_file', {'filename': 'sample.txt'}))
        self.assertTrue((self.workspace / 'sample.txt').exists())
        self.assertIn('Deleted', actions.execute('delete_file', {'filename': 'sample.txt'}, confirmed_delete=True))

    def test_block_traversal_and_bad_extensions(self):
        self.assertIn('ERROR:', actions.execute('write_file', {'filename': '../outside.txt', 'content': 'bad'}))
        self.assertIn('ERROR:', actions.execute('write_file', {'filename': 'attack.py', 'content': 'bad'}))

    def test_block_symlink_escape(self):
        outside = Path(self.tmp.name) / 'elsewhere'
        outside.mkdir()
        (self.workspace / 'link').symlink_to(outside, target_is_directory=True)
        self.assertIn('ERROR:', actions.execute('write_file', {'filename': 'link/escape.txt', 'content': 'bad'}))

    def test_safe_arithmetic(self):
        self.assertEqual(actions.safe_calculate('(2+3)*4'), 20)
        with self.assertRaises(ValueError):
            actions.safe_calculate('__import__("os").system("whoami")')
        with self.assertRaises(ValueError):
            actions.safe_calculate('9**999')

    def test_database_notes(self):
        self.assertIn('Saved note', actions.execute('add_note', {'title': 'Exam', 'body': 'Study tonight'}))
        self.assertIn('Exam', actions.execute('list_notes', {}))
        self.assertIn('Study tonight', actions.execute('search_notes', {'keyword': 'Study'}))

    def test_plan_rejects_invalid_actions(self):
        with self.assertRaises(AgentError):
            validate_plan({'message':'run', 'actions':[{'type':'shell','args':{'command':'rm -rf /'}}]})

    def test_offline(self):
        plan = offline_plan('calculate (25 + 15) * 3')
        self.assertEqual(plan['actions'][0]['type'], 'calculate')

    def test_weather_http_mock(self):
        class R:
            def __init__(self, data): self.data = data
            def raise_for_status(self): pass
            def json(self): return self.data
        with patch('actions.requests.get', side_effect=[
            R({'results':[{'name':'Pomona','country':'United States','latitude':34,'longitude':-117}]}),
            R({'current':{'temperature_2m':70,'relative_humidity_2m':40,'wind_speed_10m':5,'time':'2026-11-10T10:00'}})
        ]):
            self.assertIn('70 °F', actions.execute('weather', {'city':'Pomona'}))

if __name__ == '__main__':
    unittest.main(verbosity=2)
