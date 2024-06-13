import datetime
import json
import logging
import os
import time
from collections import defaultdict

from peewee import *

## debug queries..
logger = logging.getLogger('peewee')
if os.environ.get('DBLOG', 'false').lower() == 'true':
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())


DB_FILE = os.environ.get("DB", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'drunner.sqlite.db'))
idx=0
while not os.path.exists(DB_FILE):
    print(idx)
    idx+=1
    time.sleep(1)
db = SqliteDatabase(DB_FILE)


class BaseModel(Model):
    class Meta:
        database = db

    def __repr__(self):
        return str(self)


class BatchExec(BaseModel):
    timestamp = DateTimeField(default=datetime.datetime.now)
    name = CharField(null=True)
    author = CharField(null=True)
    email = CharField(null=True)
    comments = TextField(null=True)

    def __str__(self):
        return f'<{self.id}: {self.name} / {self.author} / {self.email} / {self.comments[:20]}>'


class DockerExec(BaseModel):
    batch = ForeignKeyField(BatchExec, null=True,  backref='scans')
    timestamp = DateTimeField(default=datetime.datetime.now)
    repo = CharField(unique=False)
    commit = CharField(unique=False)
    path = CharField(unique=False)
    scanner = CharField(unique=False, default="Scout")
    errors = TextField(null=True)

    def __str__(self):
        return f'<{self.id}: B:{self.batch} {self.scanner}({self.repo}@{self.commit}:{self.path})>'

    def as_json(self):
        return json.dumps(self.as_dict())

    def as_dict(self):
        return {
            "id": self.id,
            'timestamp': self.timestamp,
            'repo':self.repo,
            'commit': self.commit,
            'path': self.path,
            'scanner': self.scanner,
            'errors': self.errors,}

    @property
    def report(self):
        reps = [r for r in self.reports if not r.is_raw]
        if len(reps) == 0:
            return None
        return reps[0]

class Report(BaseModel):
    docker = ForeignKeyField(DockerExec, backref='reports')
    is_raw = BooleanField(default=True)
    content = TextField(null=False)
    def __str__(self):
        return f'<{self.id}: D:{self.docker} {"raw" if self.is_raw else "json"} {self.content[:20]}>'

    @classmethod
    def Create(cls, docker, is_raw, content):
        return Report.create(docker=docker, is_raw=is_raw, content=content)

    @property
    def data(self):
        return json.loads(self.content)

    @property
    def findings(self):
        return self.data['findings']

    @property
    def vulnstats(self):
        d = self.data
        found = defaultdict(int)
        for vuln in d['findings']:
            found[vuln['priority']]+=1
        return dict(found)

    @property
    def vulnlist(self):
        d = self.data
        return '\r\n'.join([ '%s: %s'%(vuln['category'], vuln['name'])
            for vuln in d['findings']
        ])



class Execution(BaseModel):
    docker = ForeignKeyField(DockerExec, backref='execs', null=True)
    cmdargs = CharField(unique=False, null=True)
    wd = CharField(unique=False, null=True)
    env = CharField(unique=False, null=True)
    ret = IntegerField(unique=False, null=True)
    timestamp = DateTimeField(null=True)
    duration = FloatField(null=True)

    def __str__(self):
        return f'<{self.id}: {self.cmdargs[:30]}  ({self.ret})>'

    @classmethod
    def Create(cls, cmdargs=None, wd=None, env=None, docker=None):
        return Execution.create(
            docker=docker,
            cmdargs=json.dumps(cmdargs),
            wd=wd,
            env=json.dumps(env))

    def set_end(self, retcode):
        end = datetime.datetime.now()
        self.duration = (end - self.timestamp).total_seconds()
        self.ret = retcode


class OutputLine(BaseModel):
    execution = ForeignKeyField(Execution, backref='output_line')
    is_out = BooleanField(default=True)
    idx = IntegerField(null=False)
    line = CharField(null=False)

    @classmethod
    def Create(cls, execution, is_out, idx, line):
        return OutputLine.create(execution=execution, is_out=is_out, idx=idx, line=line)


def init():
    # Connect to our database.
    db.connect()
    # Create the tables.
    db.create_tables([BatchExec, DockerExec, Report,  Execution, OutputLine])


if __name__ == '__main__':
    init()
