import os
import unittest

os.environ['DB_NAME'] = 'drunner.test.sqlite.db'

from drunner import ScannerRunner
import model
from app import get_app


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
        self.assertNotEquals(len(ret), 0)


if __name__ == '__main__':
    unittest.main()