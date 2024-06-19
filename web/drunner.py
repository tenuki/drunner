import json
import os
import tempfile
import traceback
from contextlib import contextmanager

import dramatiq
from dramatiq.brokers.redis import RedisBroker

import worker
import model
from results import ResultsReport, Finding, Priority

# from scanners.scout import ScoutRunner

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
redis_broker = RedisBroker(host=REDIS_HOST)
dramatiq.set_broker(redis_broker)


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
    Scanners = {}

    @classmethod
    def Create(cls, repo: str, commit: str, path: str = '.', scanner: str='scout'):
        m = model.ScannerExec.create(repo=repo, commit=commit, path=path, scanner=scanner)
        return cls.Get(m)

    @classmethod
    def Register(cls, klass, name):
        cls.Scanners[name] = klass

    @classmethod
    def Get(cls, m: model.ScannerExec):
        klass = cls.Scanners.get(m.scanner)
        if not klass is None:
            return klass(m)
        if 'test' in m.scanner.lower():
            return TestScanRunner(m)
        raise RuntimeError(f'Unknown Docker scanner: {m.scanner}.')

    def __init__(self, m: model.ScannerExec):
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

    def exec(self, cmdargs, wd=None, env=None) -> model.Execution:
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
        os.mkdir(os.path.join(self.tmpdir, self.OUTPUT_DIR_NAME))
        ex1 = self.exec([f'git clone {self.repo} srcs'])
        if ex1.ret!=0:
            raise CloneFailed('git clone failed')
        ex2 = self.exec([f'git checkout {self.commit}'], 'srcs')
        if ex2.ret!=0:
            raise CheckoutFailed('git checkout failed')
        ex3 = self.exec([f'git rev-parse HEAD'], 'srcs')
        if ex3.ret!=0:
            raise CheckoutFailed('git rev-parse HEAD failed')
        ex3.scan.rev_hash = ex3.output
        ex3.scan.save()

    def fetch_raw_output(self):
        with open(os.path.join(self.tmpdir, self.CONTAINER_RAW_REPORT_NAME), 'rb') as f:
            return f.read()

    @classmethod
    def Add_keys_for_site(cls, eid: int):
        try:
            with tempfile.TemporaryDirectory(prefix='drunner-addkey-',
                                             suffix='tmp') as tmpdir:
                e = model.Execution.get_by_id(eid)
                r = worker.exec(wd=tmpdir, e=e, env=json.loads(e.env) if e.env else None)
        except:
            traceback.print_exc()

    @classmethod
    def Build_test_scanner(cls, eid: int):
        try:
            # !!!!!! => getdir(__FILE__)...
            with tempfile.TemporaryDirectory(prefix='drunner-build-test-',
                                             suffix='tmp') as tmpdir:
                e = model.Execution.get_by_id(eid)
                r = worker.exec(wd=tmpdir, e=e, env=json.loads(e.env) if e.env else None)
        except:
            traceback.print_exc()


class TestScanRunner(ScannerRunner):
    IMAGE = 'drunner/testscan:latest'
    CONTAINER_RAW_REPORT_NAME = os.path.join(ScannerRunner.OUTPUT_DIR_NAME, 'output.txt')

    def run_image(self):
        cmd = (f'docker run -i --rm '
               f'-e INPUT_TARGET=/scanme/srcs/{self.path} '
               f'-e OUTPUT_NAME=/scanme/{self.CONTAINER_RAW_REPORT_NAME} '
               f'-v {self.tmpdir}:/scanme {self.IMAGE}')
        return self.exec([cmd])

    def process_report(self, raw_report):
        report = ResultsReport(
            name=f"Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
            date=self.m.timestamp,
            composite=False,
            scanners=[self.m.scanner])
        report.addFinding(Finding(name="vuln1 at x", category='vuln1',
                            level=Priority.Medium, scanner=self.m.scanner))
        report.addFinding(Finding(name="vuln9 at y", category='vuln9',
                            level=Priority.Low, scanner=self.m.scanner))
        report.addFinding(Finding(name="vuln5 at z", category='vuln5',
                            level=Priority.High, scanner=self.m.scanner))
        report.addFinding(Finding(name="vuln9 at t", category='vuln9',
                            level=Priority.Low, scanner=self.m.scanner))
        return report


@dramatiq.actor(time_limit=1200000)
def execute_task(task_id):
    a_task = model.ScannerExec.get_by_id(task_id)
    runner = ScannerRunner.Get(a_task)
    runner.run()


@dramatiq.actor(time_limit=1200000)
def execute_batch(batch_id, tasks_ids=()):
    for task_id in tasks_ids:
        execute_task.send(task_id)


@dramatiq.actor
def add_keys_for_site(e_id: int):
    ScannerRunner.Add_keys_for_site(e_id)


def test_add_site():
    e = model.Execution.Create(['git clone git@github.com:tenuki/no-code.git'],
                               env={'GIT_SSH_COMMAND': "ssh -oStrictHostKeyChecking=no "})
    add_keys_for_site(e.id)


from scanners.scout import ScoutRunner
ScannerRunner.Register(ScoutRunner, 'scout')

if __name__ == '__main__':
    from scanners.scout import ScoutRunner
    #test_add_site()
    pass
    # dr = DockerRunner.Create('git@github.com:CoinFabrik/scout-soroban-examples.git', 'main', 'vesting/', scanner='scout')
    # dr = ScannerRunner.Create('git@github.com:tenuki/no-code.git', 'main', '.', scanner='test')
    # dr.run()
    # report = ResultsReport(
    #     name="Single {self.m.scanner} execution on {self.repo}@{self.commit}.",
    #     date='self.m.timestamp',
    #     composite=False,
    #     scanners=['self.m.scanner'])
    # report.addFinding(Finding(name="vuln1 at x", category='vuln1',
    #                           priority=Priority.Medium, scanner='self.m.scanner'))
    # report.addFinding(Finding(name="vuln9 at y", category='vuln9',
    #                           priority=Priority.Low, scanner='self.m.scanner'))
    # report.addFinding(Finding(name="vuln5 at z", category='vuln5',
    #                           priority=Priority.High, scanner='self.m.scanner'))
    # report.addFinding(Finding(name="vuln9 at t", category='vuln9',
    #                           priority=Priority.Low, scanner='self.m.scanner'))
    # # print(report.to_json())
