import json
import os
import sys
from dataclasses import dataclass
from typing import List

import semver

from drunner import ScannerRunner
from model import ScannerExec
from results import ResultsReport, Finding, Priority, Scanner, SpanObject, SrcExtra

ScoutCodeCategories = {}


class ScoutRunner(ScannerRunner):
    IMAGE = 'coinfabrik/scout:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(ScannerRunner.OUTPUT_DIR_NAME, 'report.json')

    def _get_version(self):
        ex = self.exec('run-get-version',
                       [f'docker run -i --rm -e INPUT_SCOUT_ARGS=--version {self.IMAGE}'])
        ex.scan.scanner_version = self.version = ex.output
        ex.scan.save()

    def is_version(self, version):
        return self.version.endswith(version)

    def is_v0_2_10(self):
        return self.is_version('0.2.10')

    def is_v0_2_16(self):
        return self.is_version('0.2.16')

    def get_format(self):
        format_name = 'json' if self.is_v0_2_10() else 'raw-json'
        format_switch = '--output-format' if (not self.is_v0_2_16()) or (os.environ.get('FIXEDv0216')=='true') else '--output-formats'
        return f' {format_switch} {format_name}'

    def run_image(self):
        self._get_version()
        env = {
            'INPUT_TARGET': f'/scoutme/srcs/{self.path}',
            'RUST_BACKTRACE': 'full',
            'INPUT_SCOUT_ARGS': self.get_format() + f" --output-path /scoutme/{self.CONTAINER_RAW_REPORT_NAME}",
            'CARGO_TARGET_DIR': '/tmp',
        }
        envs = ' '.join(f'-e {key}="{value}"' for key, value in env.items())
        cmd = (f'docker run -i --rm {envs} -v {self.tmpdir}:/scoutme {self.IMAGE}')
        self.exec('run-image', [cmd])

    @staticmethod
    def _get_vulns_from_raw_report(raw_report):
        for line in raw_report.splitlines():
            try:
                msg = json.loads(line)
                sv = ScoutVulnerability.FromJsonObj(msg)
                if sv is None: continue
                yield sv.asFinding()
            except:
                print(f"Invalid line in output: '{line}'. ignoring..", file=sys.stderr)

    def process_report(self, raw_report):
        report = ResultsReport(
            name=f"Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
            date=self.m.timestamp,
            composite=False,
            scanners=[self.m.scanner])
        for vuln in self._get_vulns_from_raw_report(raw_report):
            report.addFinding(vuln)
        return report

ScannerRunner.Register(ScoutRunner, 'scout')


@dataclass
class ScoutVulnerability:
    message: str
    code: str
    level: str
    spans: List[SpanObject]
    src_path: str
    src_line: int
    src_extra: SrcExtra

    @property
    def category(self):
        return ScoutCodeCategories.get(self.code, 'unknown')

    def asFinding(self)->Finding:
        return Finding(
            name=self.code,
            desc=self.message,
            category=self.category,
            level=Priority.From(self.level),
            filename=self.src_path,
            lineno=self.src_line,
            scanner=Scanner('scout'),
            jsonextra=json.dumps({
                'spans': [s.as_dict() for s in self.spans],
                'extra': self.src_extra.as_dict()
            })
        )

    @classmethod
    def FromJsonObj(cls, version, json_obj):
        version = semver.Version.parse(version)
        v0216 = semver.Version.parse('0.2.16')
        if version<v0216:
            return cls.FromJsonObjOriginal(json_obj)
        return cls.FromJsonObj0216(json_obj)

    @classmethod
    def FromJsonObjOriginal(cls, json_obj):
        if ((not json_obj['reason'] == 'compiler-message') or
                (json_obj['message'] is None) or
                (json_obj['message']['code'] is None)):
            return None  # raise Exception("probably not a scout vuln.")
        return cls(
            message=json_obj['message']['message'],
            code=json_obj['message']['code']['code'],
            level=json_obj['message']['level'],
            spans=[SpanObject.FromJsonObj(o) for o in json_obj['message']['spans']],
            src_path=json_obj['message']['spans'][0]['file_name'],
            src_line=json_obj['message']['spans'][0]['line_start'],
            src_extra=SrcExtra(
                filename=json_obj['message']['spans'][0]['file_name'],
                manifest=json_obj['manifest_path']))

    @classmethod
    def FromJsonObj0216(cls, json_obj):
        if ((not json_obj['$message_type'] == 'diagnostic') or
                (json_obj['message'] is None) or
                (json_obj['level'] is None)):
            return None  # raise Exception("probably not a scout vuln.")
        return cls(
            message=json_obj['message'],
            code=json_obj['code']['code'],
            level=json_obj['level'],
            spans=[SpanObject.FromJsonObj(o) for o in json_obj['spans']],
            src_path=json_obj['spans'][0]['file_name'],
            src_line=json_obj['spans'][0]['line_start'],
            src_extra=SrcExtra(
                filename=json_obj['spans'][0]['file_name'],
                manifest=json_obj['crate']))


if __name__=="__main__":
    # show some
    scan = ScannerExec.get_by_id(14)
    sr = ScoutRunner(scan)
    rr = scan.get_raw_report()
    for v in ScoutRunner._get_vulns_from_raw_report(rr.content):
        print(v)
    rep = sr.process_report(rr.content)
    print(rr)

