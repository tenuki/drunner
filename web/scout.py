import json
import os
import sys
from dataclasses import dataclass
from typing import List

from drunner import ScannerRunner
from results import ResultsReport, Finding, Priority, Scanner, SpanObject, SrcExtra

from model import ScannerExec


ScoutCodeCategories = {}


class ScoutRunner(ScannerRunner):
    IMAGE = 'coinfabrik/scout:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(ScannerRunner.OUTPUT_DIR_NAME, 'report.json')

    def _get_version(self):
        ex = self.exec('run-get-version',
                       [f'docker run -i --rm -e INPUT_SCOUT_ARGS=--version {self.IMAGE}'])
        ex.scan.scanner_version = self.version = ex.output
        ex.scan.save()

    def is_v0_2_10(self):
        return self.version.endswith('0.2.10')

    def run_image(self):
        self._get_version()
        format_name = 'json' if self.is_v0_2_10() else 'raw-json'
        env = {
            'INPUT_TARGET': f'/scoutme/srcs/{self.path}',
            'RUST_BACKTRACE': 'full',
            'INPUT_SCOUT_ARGS': f" --output-format {format_name} --output-path /scoutme/{self.CONTAINER_RAW_REPORT_NAME}",
            'CARGO_TARGET_DIR': '/tmp',
        }
        envs = ' '.join(f'-e {key}="{value}"' for key, value in env.items())
        cmd = (f'docker run -i --rm {envs} -v {self.tmpdir}:/scoutme {self.IMAGE}')
        self.exec('run-image', [cmd])

    @staticmethod
    def _get_vulns_from_raw_report(raw_report):
        for line in raw_report.splitlines():
            try:
                # disable: unsafe-unwrap
                msg = json.loads(line)
                sv = ScoutVulnerability.FromJsonObj(msg)
                if sv is None: continue
                yield sv.asFinding()
                # report.addFinding(Finding(name=msg['message']['message'], category='',
                #         level=Priority.Medium,
                #         scanner=self.m.scanner))
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
            level=self.level,
            filename=self.src_path,
            lineno=self.src_line,
            scanner=Scanner('scout'),
            jsonextra=json.dumps({
                'spans': [s.as_dict() for s in self.spans],
                'extra': self.src_extra.as_dict()
            })
        )

    @classmethod
    def FromJsonObj(cls, json_obj):
        if ((not json_obj['reason'] == 'compiler-message') or
                (json_obj['message'] is None) or
                (json_obj['message']['code'] is None)):
            return None  # raise Exception("probably not a scout vuln.")
        return cls(
            message=json_obj['message']['message'],
            code=json_obj['message']['code']['code'],
            level=json_obj['message']['level'],
            spans=[SpanObject.FromJsonObj(o) for o in json_obj['message']['spans']],
            src_path=json_obj['target']['src_path'],
            src_line=json_obj['message']['spans'][0]['line_start'],
            src_extra=SrcExtra(
                filename=json_obj['message']['spans'][0]['file_name'],
                manifest=json_obj['manifest_path']))


if __name__=="__main__":
    # show some
    scan = ScannerExec.get_by_id(14)
    sr = ScoutRunner(scan)
    rr = scan.raw_report
    for v in ScoutRunner._get_vulns_from_raw_report(rr.content):
        print(v)
    rep = sr.process_report(rr.content)
    print(rr)

