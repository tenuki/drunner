import json
import os
import sys
import unittest

import json5
import semver

from web.scout import ScoutVulnerability

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

class TestVersions(unittest.TestCase):
    v0116 = semver.Version.parse('0.1.16')
    v0214 = semver.Version.parse('0.2.14')
    v0216 = semver.Version.parse('0.2.16')
    v0316 = semver.Version.parse('0.3.16')
    v1000 = semver.Version.parse('1.0.0')

    def test_semver1(self):
        self.assertLess(self.v0116, self.v0216)
    def test_semver2(self):
        self.assertLess(self.v0214, self.v0216)
    def test_semver3(self):
        self.assertLessEqual(self.v0216, self.v0216)
    def test_semver4(self):
        self.assertGreater(self.v0316, self.v0216)
    def test_semver5(self):
        self.assertGreater(self.v1000, self.v0216)



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


class RawReportPre0216(unittest.TestCase):
    RAW_LINE_BASIC_v0216_pre_TEST = r"""{
  "reason": "compiler-message",
  "package_id": "avoid-core-mem-forget-vulnerable-1 0.1.0 (path+file:///scoutme/srcs/test-cases/avoid-core-mem-forget/avoid-core-mem-forget-1/vulnerable-example)",
  "manifest_path": "/scoutme/srcs/test-cases/avoid-core-mem-forget/avoid-core-mem-forget-1/vulnerable-example/Cargo.toml",
  "target": {
    "kind": [
      "cdylib"
    ],
    "crate_types": [
      "cdylib"
    ],
    "name": "avoid-core-mem-forget-vulnerable-1",
    "src_path": "/scoutme/srcs/test-cases/avoid-core-mem-forget/avoid-core-mem-forget-1/vulnerable-example/src/lib.rs",
    "edition": "2021",
    "doc": true,
    "doctest": false,
    "test": true
  },
  "message": {
    "rendered": "warning: Use the latest version of Soroban\n  |\n  = help: The latest Soroban version is \"21.1.1\", and your version is \"20.0.0\"\n  = note: `#[warn(soroban_version)]` on by default\n\n",
    "$message_type": "diagnostic",
    "children": [
      {
        "children": [],
        "code": null,
        "level": "help",
        "message": "The latest Soroban version is \"21.1.1\", and your version is \"20.0.0\"",
        "rendered": null,
        "spans": []
      },
      {
        "children": [],
        "code": null,
        "level": "note",
        "message": "`#[warn(soroban_version)]` on by default",
        "rendered": null,
        "spans": []
      }
    ],
    "code": {
      "code": "soroban_version",
      "explanation": null
    },
    "level": "warning",
    "message": "Use the latest version of Soroban",
    "spans": [
      {
        "byte_end": 0,
        "byte_start": 0,
        "column_end": 1,
        "column_start": 1,
        "expansion": null,
        "file_name": "avoid-core-mem-forget-1/vulnerable-example/src/lib.rs",
        "is_primary": true,
        "label": null,
        "line_end": 1,
        "line_start": 1,
        "suggested_replacement": null,
        "suggestion_applicability": null,
        "text": []
      }
    ]
  }
}"""
    RAW_LINE_BASIC_from_v0216_TEST = r"""{
  "$message_type": "diagnostic",
  "children": [
    {
      "children": [],
      "code": null,
      "level": "help",
      "message": "Instead, use the `let _ = ...` pattern or `.drop` method to forget the value.",
      "rendered": null,
      "spans": []
    },
    {
      "children": [],
      "code": null,
      "level": "note",
      "message": "`#[warn(avoid_core_mem_forget)]` on by default",
      "rendered": null,
      "spans": []
    }
  ],
  "code": {
    "code": "avoid_core_mem_forget",
    "explanation": null
  },
  "crate": "avoid_core_mem_forget_vulnerable_1",
  "level": "warning",
  "message": "Use the `let _ = ...` pattern or `.drop()` method to forget the value",
  "rendered": "\u001b[0m\u001b[1m\u001b[33mwarning\u001b[0m\u001b[0m\u001b[1m: Use the `let _ = ...` pattern or `.drop()` method to forget the value\u001b[0m\n\u001b[0m  \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m--> \u001b[0m\u001b[0mavoid-core-mem-forget-1/vulnerable-example/src/lib.rs:23:9\u001b[0m\n\u001b[0m   \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m|\u001b[0m\n\u001b[0m\u001b[1m\u001b[38;5;12m23\u001b[0m\u001b[0m \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m|\u001b[0m\u001b[0m \u001b[0m\u001b[0m        core::mem::forget(n);\u001b[0m\n\u001b[0m   \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m|\u001b[0m\u001b[0m         \u001b[0m\u001b[0m\u001b[1m\u001b[33m^^^^^^^^^^^^^^^^^^^^\u001b[0m\n\u001b[0m   \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m|\u001b[0m\n\u001b[0m   \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m= \u001b[0m\u001b[0m\u001b[1mhelp\u001b[0m\u001b[0m: Instead, use the `let _ = ...` pattern or `.drop` method to forget the value.\u001b[0m\n\u001b[0m   \u001b[0m\u001b[0m\u001b[1m\u001b[38;5;12m= \u001b[0m\u001b[0m\u001b[1mnote\u001b[0m\u001b[0m: `#[warn(avoid_core_mem_forget)]` on by default\u001b[0m\n\n",
  "spans": [
    {
      "byte_end": 433,
      "byte_start": 413,
      "column_end": 29,
      "column_start": 9,
      "expansion": null,
      "file_name": "avoid-core-mem-forget-1/vulnerable-example/src/lib.rs",
      "is_primary": true,
      "label": null,
      "line_end": 23,
      "line_start": 23,
      "suggested_replacement": null,
      "suggestion_applicability": null,
      "text": [
        {
          "highlight_end": 29,
          "highlight_start": 9,
          "text": "        core::mem::forget(n);"
        }
      ]
    }
  ]
}
"""
    def test_basic_vuln_format(self):
        obj_json = json5.loads(self.RAW_LINE_BASIC_v0216_pre_TEST)
        vuln = ScoutVulnerability.FromJsonObjOriginal(obj_json)
        print(repr(vuln))
        self.assertTrue(isinstance(vuln, ScoutVulnerability))
        self.assertEqual(vuln.level, "warning")

    def test_basic_vuln_format_post(self):
        obj_json = json5.loads(self.RAW_LINE_BASIC_from_v0216_TEST)
        vuln = ScoutVulnerability.FromJsonObj0216(obj_json)
        self.assertTrue(isinstance(vuln, ScoutVulnerability))
        self.assertEqual(vuln.level, "warning")
