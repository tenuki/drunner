import json
import os
import sys
import tempfile
import traceback
from contextlib import contextmanager

import dramatiq

import worker
import model
from results import ResultsReport, Finding, Priority


@contextmanager
def SwitchDir(dirname: str):
    prev = os.getcwd()
    os.chdir(dirname)
    try:
        yield
    finally:
        os.chdir(prev)


class RunnerException(Exception):
    pass


class CloneFailed(RunnerException):
    pass


class CheckoutFailed(RunnerException):
    pass


class ScannerRunner(object):
    OUTPUT_DIR_NAME = 'out'

    @classmethod
    def Create(cls, repo: str, commit: str, path: str = '.', scanner: str='scout'):
        m = model.DockerExec.create(repo=repo, commit=commit, path=path, scanner=scanner)
        return cls.Get(m)

    @classmethod
    def Get(cls, m: model.DockerExec):
        if m.scanner.lower() == 'scout':
            return ScoutRunner(m)
        elif 'test' in m.scanner.lower():
            return TestScanRunner(m)
        raise RuntimeError(f'Unknown Docker scanner: {m.scanner}.')

    def __init__(self, m: model.DockerExec):
        self.path = m.path
        self.commit = m.commit
        self.repo = m.repo
        self.m = m
        self.tmpdir = None

    def run(self):
        try:
            self.m.save()
            with tempfile.TemporaryDirectory(prefix='drunner-'+self.m.scanner,
                                             suffix='tmp') as self.tmpdir:
                # with SwitchDir(self.tmpdir):
                return self._run()
        except:
            self.m.errors = traceback.format_exc()
            self.m.save()

    def _run(self):
        self.prepare_image()
        self.run_image()
        raw_report = self.fetch_raw_output()
        model.Report.Create(docker=self.m, is_raw=True, content=raw_report)
        report = self.process_report(raw_report)
        model.Report.Create(docker=self.m, is_raw=False, content=report.to_json())
        return report

    @property
    def output_fname(self):
        return os.path.join(self.tmpdir, self.OUTPUT_DIR_NAME, 'report.json')

    def exec(self, cmdargs, wd=None, env=None):
        if wd is None:
            wd = self.tmpdir
        else:
            if not os.path.isabs(wd):
                wd = os.path.join(self.tmpdir, wd)
        return worker.exec(cmdargs, wd=wd, env=env, de=self.m)

    def prepare_image(self):
        """
        tmpdir\
          +- srcs\       // dir with the checkout
          +- out\       // dir for the output

        - tmpdir is expected to be mounted somewhere in the container
        """
        ret = self.exec([f'pwd'])
        ret = self.exec([f'ls -la'])
        ret = self.exec([f'git clone {self.repo} srcs'])
        if ret!=0:
            raise CloneFailed('git clone failed')
        ret2 = self.exec([f'git checkout {self.commit}'], 'srcs')
        if ret2!=0:
            raise CheckoutFailed('git checkout failed')
        os.mkdir(os.path.join(self.tmpdir, self.OUTPUT_DIR_NAME))

    def fetch_raw_output(self):
        with open(os.path.join(self.tmpdir, self.CONTAINER_RAW_REPORT_NAME), 'rb') as f:
            return f.read()


class ScoutRunner(ScannerRunner):
    IMAGE = 'coinfabrik/scout-image:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(ScannerRunner.OUTPUT_DIR_NAME, 'report.json')

    def run_image(self):
        cmd = (f'docker run -i --rm -e CARGO_TARGET_DIR=/tmp '
               # f'-e RUST_BACKTRACE=full '
               f'-e INPUT_TARGET=/scoutme/srcs/{self.path} '
               f'-e INPUT_SCOUT_ARGS=" --output-format json --output-path /scoutme/{self.CONTAINER_RAW_REPORT_NAME}" '
               f'-v {self.tmpdir}:/scoutme {self.IMAGE}')
        self.exec([cmd])

    def process_report(self, raw_report):
        report = ResultsReport(
            name=f"Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
            date=self.m.timestamp,
            composite=False,
            scanners=[self.m.scanner],
        )

        for line in raw_report.splitlines():
            try:
                msg = json.loads(line)
                if not 'reason' in msg or msg['reason']!='compiler-message': continue
                if not 'message' in msg: continue
                if not 'level' in msg['message']: continue

                report.addFinding(Finding(name=msg['message']['message'], category='',
                        priority=Priority.Medium,
                        scanner=self.m.scanner))
            except:
                print(f"Invalid line in output: '{line}'. ignoring..", file=sys.stderr)
        return report



class TestScanRunner(ScannerRunner):
    IMAGE = 'drunner/testscan:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(ScannerRunner.OUTPUT_DIR_NAME, 'output.txt')

    def run_image(self):
        cmd = (f'docker run -i --rm '
               f'-e INPUT_TARGET=/scanme/srcs/{self.path} '
               f'-e OUTPUT_NAME=/scanme/{self.CONTAINER_RAW_REPORT_NAME} '
               f'-v {self.tmpdir}:/scanme {self.IMAGE}')
        self.exec([cmd])

    def process_report(self, raw_report):
        report = ResultsReport(
            name=f"Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
            date=self.m.timestamp,
            composite=False,
            scanners=[self.m.scanner])
        report.addFinding(Finding(name="vuln1 at x", category='vuln1',
                            priority=Priority.Medium, scanner=self.m.scanner))
        report.addFinding(Finding(name="vuln9 at y", category='vuln9',
                            priority=Priority.Low, scanner=self.m.scanner))
        report.addFinding(Finding(name="vuln5 at z", category='vuln5',
                            priority=Priority.High, scanner=self.m.scanner))
        report.addFinding(Finding(name="vuln9 at t", category='vuln9',
                            priority=Priority.Low, scanner=self.m.scanner))
        return report


@dramatiq.actor(time_limit=1200000)
def execute_task(task_id):
    a_task = model.DockerExec.get_by_id(task_id)
    runner = ScannerRunner.Get(a_task)
    runner.run()


@dramatiq.actor(time_limit=1200000)
def execute_batch(batch_id, tasks_ids=()):
    for task_id in tasks_ids:
        execute_task.send(task_id)


if __name__ == '__main__':
    # dr = DockerRunner.Create('git@github.com:CoinFabrik/scout-soroban-examples.git', 'main', 'vesting/', scanner='scout')
    # dr = ScannerRunner.Create('git@github.com:tenuki/no-code.git', 'main', '.', scanner='test')
    # dr.run()

    report = ResultsReport(
        name="Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
        date='self.m.timestamp',
        composite=False,
        scanners=['self.m.scanner'])
    report.addFinding(Finding(name="vuln1 at x", category='vuln1',
                              priority=Priority.Medium, scanner='self.m.scanner'))
    report.addFinding(Finding(name="vuln9 at y", category='vuln9',
                              priority=Priority.Low, scanner='self.m.scanner'))
    report.addFinding(Finding(name="vuln5 at z", category='vuln5',
                              priority=Priority.High, scanner='self.m.scanner'))
    report.addFinding(Finding(name="vuln9 at t", category='vuln9',
                              priority=Priority.Low, scanner='self.m.scanner'))
    # print(report.to_json())


