import json
import os
import sys
from dataclasses import dataclass
from typing import List

from drunner import ScannerRunner
from results import ResultsReport, Finding, Priority, Scanner, SpanObject, SrcExtra


ScoutCodeCategories = {}


class ScoutRunner(ScannerRunner):
    IMAGE = 'coinfabrik/scout:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(ScannerRunner.OUTPUT_DIR_NAME, 'report.json')

    def _get_version(self):
        ex = self.exec([f'docker run -i --rm -e INPUT_SCOUT_ARGS=--version {self.IMAGE}'])
        ex.scan.scanner_version = self.version = ex.output
        ex.scan.save()

    def run_image(self):
        self._get_version()

        cmd = (f'docker run -i --rm -e CARGO_TARGET_DIR=/tmp '
               f'-e INPUT_TARGET=/scoutme/srcs/{self.path} '
               f'-e RUST_BACKTRACE=full '
               f'-e INPUT_SCOUT_ARGS=" --output-format json --output-path /scoutme/{self.CONTAINER_RAW_REPORT_NAME}" '
               f'-v {self.tmpdir}:/scoutme {self.IMAGE}')
        self.exec([cmd])

    def process_report(self, raw_report):
        report = ResultsReport(
            name=f"Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
            date=self.m.timestamp,
            composite=False,
            scanners=[self.m.scanner])

        for line in raw_report.splitlines():
            try:
                # disable: unsafe-unwrap
                msg = json.loads(line)
                sv = ScoutVulnerability.FromJsonObj(msg)
                if sv is None: continue
                report.addFinding(sv.asFinding())
                # report.addFinding(Finding(name=msg['message']['message'], category='',
                #         level=Priority.Medium,
                #         scanner=self.m.scanner))
            except:
                print(f"Invalid line in output: '{line}'. ignoring..", file=sys.stderr)
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
