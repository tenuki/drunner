import json
import os
import tempfile
from contextlib import contextmanager

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


class DockerRunner(object):
    OUTPUT_DIR_NAME = 'drunner-output'

    def __init__(self, repo, commit, path):
        self.m = model.DockerExec.create(repo=repo, commit=commit, path=path)
        self.path = path
        self.commit = commit
        self.repo = repo
        self.tmpdir = None

    def run(self):
        self.m.save()
        with tempfile.TemporaryDirectory() as self.tmpdir:
            with SwitchDir(self.tmpdir):
                # worker.exec([f'ls -laR .'], de=self.m)
                self.prepare_image()
                self.run_image()
                raw_report = self.fetch_output()
                re = model.Report.Create(docker=self.m, is_raw=True, content=raw_report)
                re.save()
                report = self.process_report(raw_report)
                re = model.Report.Create(docker=self.m, is_raw=False, content=report)
                re.save()
                self.m.save()

    @property
    def image(self):
        # return 'scout:latest'
        return 'coinfabrik/scout-image:latest'

    @property
    def output_fname(self):
        return os.path.join(self.tmpdir, self.OUTPUT_DIR_NAME, 'report.json')

    @property
    def base_output_fname(self):
        return os.path.join(self.OUTPUT_DIR_NAME, 'report.json')

    @property
    def sources_dir(self):
        return os.path.join(self.tmpdir, 'srcs')

    def prepare_image(self):
        ret = worker.exec([f'git clone {self.repo} srcs'], de=self.m)
        if ret!=0:
            raise Exception('git clone failed')
        # print(f"-> {self.tmpdir} ({ret})")
        with SwitchDir('srcs'):
            ret2 = worker.exec([f'git checkout {self.commit}'], de=self.m)
            if ret2!=0:
                raise Exception('git checkout failed')
        os.mkdir(os.path.dirname(self.output_fname))

    def run_image(self):
        # INPUT_TARGET=/scoutme/srcs/{self.path} CARGO_TARGET_DIR=/tmp
        cmd = (f'docker run -i --rm -e CARGO_TARGET_DIR=/tmp '
               f'-v {self.tmpdir}:/scoutme {self.image}')
        worker.exec([cmd], de=self.m)

    def fetch_output(self):
        with open(self.base_output_fname, 'rb') as f:
            return f.read()

    def process_report(self, raw_report):
        findings = []
        for line in raw_report.splitlines():
            findings.append(self.convert_from('scout', line))
        return {"report": "this report",
                "findings": findings}

    # @staticmethod
    # def convert_from(detector, line):
    #     if detector=="scout":
    #         finding = json.loads(line)
    #         return finding
    #     raise Exception(f"Unknown detector: {detector}")


class ScoutRunner(DockerRunner):
    def run_image(self):
        cmd = (f'docker run -i --rm -e CARGO_TARGET_DIR=/tmp '
               # f'-e RUST_BACKTRACE=full '
               f'-e INPUT_TARGET=/scoutme/srcs/{self.path} '
               f'-e INPUT_SCOUT_ARGS=" --output-format json --output-path /scoutme/{self.base_output_fname}" '
               f'-v {self.tmpdir}:/scoutme {self.image}')
        worker.exec([cmd], de=self.m)

    @staticmethod
    def convert_from(detector, line):
        finding = json.loads(line)
        return finding



if __name__ == '__main__':
    dr = ScoutRunner('git@github.com:CoinFabrik/scout-soroban-examples.git',
                      'main',
                      'vesting/')
    # 'governance/mock-contract/')
    dr.run()
