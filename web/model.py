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
        os.path.dirname(os.path.abspath(__file__)),
        os.environ.get('DB_NAME','drunner.sqlite.db')))
db = SqliteDatabase(DB_FILE)


class BaseModel(Model):
    class Meta:
        database = db

    def __repr__(self):
        return str(self)


class BatchExec(BaseModel):
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)
    name = CharField(null=True)
    author = CharField(null=True)
    email = CharField(null=True)
    comments = TextField(null=True)

    def __str__(self):
        return f'<{self.id}: {self.name} / {self.author} / {self.email} / {self.comments[:20]}>'

    def composite_report(self):
        vulns = []
        for scan in self.scans:
            for vuln in scan.get_common_report().findings:
                vulns.append((scan, vuln))
        return vulns


class ScannerExec(BaseModel):
    batch = ForeignKeyField(BatchExec, null=True,  backref='scans')
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)
    repo = CharField(unique=False)
    commit = CharField(unique=False)
    rev_hash = CharField(unique=False, null=True)
    path = CharField(unique=False)
    scanner = CharField(unique=False, default="Scout", index=True)
    scanner_version = CharField(unique=False, null=True)
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

    def get_common_report(self):
        try:
            return Report.select().where(Report.docker==self, Report.is_raw==False)[0]
        except IndexError:
            return None

    def get_raw_report(self):
        try:
            return Report.select().where(Report.docker==self, Report.is_raw==True)[0]
        except IndexError:
            return None


class PrioritySum:
    SKeys = {'High', 'Medium', 'Low', 'Enhancement'}
    def __init__(self, **kwargs):
        self.d = {k: kwargs.get(k, 0) for k in PrioritySum.SKeys}
    def __contains__(self, key):
        return key in self.SKeys
    def __getitem__(self, key):
        if not key in self.SKeys:
            raise KeyError(key)
        return self.d[key]
    def __setitem__(self, key, value):
        if not key in self.SKeys:
            raise KeyError(key)
        self.d[key] = value
    def __delitem__(self, key):
        if not key in self.SKeys:
            raise KeyError(key)
        self.d[key] = 0
    def get(self, key, default=None):
        if not key in self.SKeys:
            raise KeyError(key)
        return self.d.get(key, default)
    def sum(self):
        return self['High'] + (self['Medium']/2) + (self['Low']/4) + (self['Enhancement']/10)


class Report(BaseModel):
    docker = ForeignKeyField(ScannerExec, backref='reports')
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
        # for f in d['findings']:
        #     print(repr(f['level']))
        found = defaultdict(int)
        for vuln in d['findings']:
            found[vuln['level']]+=1
        return PrioritySum(**found)

    @property
    def vulnlist(self):
        d = self.data
        return '\r\n'.join([ '%s: %s'%(vuln['category'], vuln['name'])
            for vuln in d['findings']
        ])


class Execution(BaseModel):
    scan = ForeignKeyField(ScannerExec, backref='execs', null=True)
    kind = CharField(unique=False, null=False, index=True)
    cmdargs = CharField(unique=False, null=True)
    wd = CharField(unique=False, null=True)
    env = CharField(unique=False, null=True)
    ret = IntegerField(unique=False, null=True)
    timestamp = DateTimeField(null=True)
    duration = FloatField(null=True)

    def __str__(self):
        return f'<{self.id}: {self.cmdargs[:30]}  ({self.ret})>'

    @classmethod
    def Create(cls, kind, cmdargs=None, wd=None, env=None, scan=None):
        return Execution.create(
            kind=kind,
            scan=scan,
            cmdargs=json.dumps(cmdargs),
            wd=wd,
            env=json.dumps(env))

    @property
    def output(self):
        return '\n'.join(ol.line for ol in self.output_line)

    def set_end(self, retcode):
        end = datetime.datetime.now()
        self.duration = (end - self.timestamp).total_seconds()
        self.ret = retcode

    def get_output_fname(self):
        from helperfuncs import short_date
        cmd = ' '.join(json.loads(self.cmdargs))
        for c in ' :/"\'':
            cmd = cmd.replace(c, '_')
        date = short_date(self.timestamp)
        return f'{date}-id_{self.id}-{cmd}.txt'

    def get_output_info(self):
        return self.get_output_fname(), 'text/plain'

    def avg_duration(self):
        avg = (Execution.select(fn.AVG(Execution.duration))
                            .where(Execution.kind==self.kind).scalar())
        if avg is None:
            return 0
        avg = int((avg*10)+0.5)/10
        return avg

    def elapsed(self):
        if not(self.duration is None):
            return self.duration
        if self.timestamp is None:
            return 0
        return datetime.datetime.now().timestamp() - self.timestamp.timestamp()

class OutputLine(BaseModel):
    execution = ForeignKeyField(Execution, backref='output_line')
    is_out = BooleanField(default=True)
    idx = IntegerField(null=False, index=True)
    line = CharField(null=False)

    @classmethod
    def Create(cls, execution, is_out, idx, line):
        return OutputLine.create(execution=execution, is_out=is_out, idx=idx, line=line)


def init():
    db = SqliteDatabase(DB_FILE)
    # Connect to our database.
    db.connect()
    # Create the tables.
    db.create_tables([BatchExec, ScannerExec, Report, Execution, OutputLine])


if __name__ == '__main__':
    init()
else:
    def invalid(fname):
        file_stats = os.stat(fname)
        return file_stats.st_size==0
    if (not os.path.exists(DB_FILE)) or invalid(DB_FILE):
        init()


def get_scans():
    return [x.as_dict() for x in ScannerExec.select()
                .where(ScannerExec.batch == None)
                .order_by(ScannerExec.timestamp.desc())]


def get_batchs():
    return [x for x in
            BatchExec.select().order_by(BatchExec.timestamp.desc())]


