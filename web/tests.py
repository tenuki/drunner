import json
import os
import sys
import unittest
os.environ['DB_NAME'] = 'drunner.test.sqlite.db'

from drunner import ScannerRunner
import model
from results import Priority
from app import get_app


class TestPriorities(unittest.TestCase):
    def test_prioritiesFromString(self):
        self.assertEqual(Priority.High, Priority.FromStr("high"))
        self.assertEqual(Priority.High, Priority.FromStr("hIGH"))
        self.assertEqual(Priority.Low, Priority.FromStr("lOw"))
        self.assertEqual(Priority.Medium, Priority.FromStr("medium"))
        self.assertEqual(Priority.Enhancement, Priority.FromStr("enhancement"))

    def test_json_support(self):
        json.dumps(Priority.FromStr("high"))
        self.assertEqual(json.loads(json.dumps(Priority.FromStr("hIGH"))), Priority.FromStr("hIGH"))

class MyRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model.init()
        cls.app = get_app()
        cls.client = cls.app.test_client()
        cls.dr = ScannerRunner.Create('git@github.com:tenuki/no-code.git', 'main', '.', scanner='test')
        cls.dr.run()

    def test_no_id_function_leak(self):
        ret = self.client.get(f'/scan-exec/{self.dr.m.id}')
        self.assertNotIn(b'built-in function id', ret.data,
                         msg="we are returning the id function instead of the oject value")

    def test_there_are_scans(self):
        ret = model.get_scans()
        self.assertNotEqual(len(ret), 0)


if __name__ == '__main__':
    sys.argv.append("-v")
    unittest.main()