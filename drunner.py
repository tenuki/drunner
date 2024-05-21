import json
import os
import tempfile
import traceback
from contextlib import contextmanager

import dramatiq

import worker
import model


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


class DockerRunner(object):
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
            with tempfile.TemporaryDirectory() as self.tmpdir:
                with SwitchDir(self.tmpdir):
                    return self._run()
        except:
            self.m.errors = traceback.format_exc()
            self.m.save()

    def _run(self):
        self.prepare_image()
        self.run_image()
        raw_report = self.fetch_raw_output()
        report = self.process_report(raw_report)
        return report

    @property
    def output_fname(self):
        return os.path.join(self.tmpdir, self.OUTPUT_DIR_NAME, 'report.json')

    def prepare_image(self):
        """
        tmpdir\
          +- srcs\       // dir with the checkout
          +- out\       // dir for the output

        - tmpdir is expected to be mounted somewhere in the container
        """
        ret = worker.exec([f'git clone {self.repo} srcs'], de=self.m)
        if ret!=0:
            raise CloneFailed('git clone failed')
        with SwitchDir('srcs'):
            ret2 = worker.exec([f'git checkout {self.commit}'], de=self.m)
            if ret2!=0:
                raise CheckoutFailed('git checkout failed')
        os.mkdir(self.OUTPUT_DIR_NAME)

    def process_report(self, raw_report):
        findings = []
        for line in raw_report.splitlines():
            findings.append(self.convert_from('scout', line))
        report = {"report": "this report",
                  "findings": findings}
        model.Report.Create(docker=self.m, is_raw=False, content=report)
        return report

    def fetch_raw_output(self):
        with open(self.CONTAINER_RAW_REPORT_NAME, 'rb') as f:
            raw_report = f.read()
        model.Report.Create(docker=self.m, is_raw=True, content=raw_report)
        return raw_report


class ScoutRunner(DockerRunner):
    IMAGE = 'coinfabrik/scout-image:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(DockerRunner.OUTPUT_DIR_NAME, 'report.json')

    def run_image(self):
        cmd = (f'docker run -i --rm -e CARGO_TARGET_DIR=/tmp '
               # f'-e RUST_BACKTRACE=full '
               f'-e INPUT_TARGET=/scoutme/srcs/{self.path} '
               f'-e INPUT_SCOUT_ARGS=" --output-format json --output-path /scoutme/{self.CONTAINER_RAW_REPORT_NAME}" '
               f'-v {self.tmpdir}:/scoutme {self.IMAGE}')
        worker.exec([cmd], de=self.m)

    @staticmethod
    def convert_from(scanner, line):
        return json.loads(line)


class TestScanRunner(DockerRunner):
    IMAGE = 'drunner/testscan:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(DockerRunner.OUTPUT_DIR_NAME, 'output.txt')

    def run_image(self):
        cmd = (f'docker run -i --rm '
               f'-e INPUT_TARGET=/scanme/srcs/{self.path} '
               f'-e OUTPUT_NAME=/scanme/{self.CONTAINER_RAW_REPORT_NAME} '
               f'-v {self.tmpdir}:/scanme {self.IMAGE}')
        worker.exec([cmd], de=self.m)

    @staticmethod
    def convert_from(scanner, line):
        finding = json.loads(line)
        return finding


@dramatiq.actor
def execute_task(task_id):
    a_task = model.DockerExec.get_by_id(task_id)
    runner = DockerRunner.Get(a_task)
    return runner.run()


@dramatiq.actor
def execute_batch(batch_id, tasks_ids=()):
    for task_id in tasks_ids:
        execute_task.send(task_id)


if __name__ == '__main__':
    # dr = DockerRunner.Create('git@github.com:CoinFabrik/scout-soroban-examples.git', 'main', 'vesting/', scanner='scout')
    dr = DockerRunner.Create('git@github.com:tenuki/no-code.git','main','.', scanner='test')
    dr.run()
