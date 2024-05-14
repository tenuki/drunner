import datetime
import json
import os

from peewee import *


db = SqliteDatabase(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),'my_app.db'))


class BaseModel(Model):
    class Meta:
        database = db


class DockerExec(BaseModel):
    timestamp = DateTimeField(default=datetime.datetime.now)
    repo = CharField(unique=False)
    commit = CharField(unique=False)
    path = CharField(unique=False)


class Report(BaseModel):
    docker = ForeignKeyField(DockerExec, backref='reports')
    is_raw = BooleanField(default=True)
    content = TextField(null=False)

    @classmethod
    def Create(cls, docker, is_raw, content):
        return Report.create(docker=docker, is_raw=is_raw, content=content)


class Execution(BaseModel):
    docker = ForeignKeyField(DockerExec, backref='execs', null=True)
    cmdargs = CharField(unique=False)
    wd = CharField(unique=False, null=True)
    env = CharField(unique=False, null=True)
    ret = IntegerField(unique=False, null=True)
    timestamp = DateTimeField(null=True)
    duration = FloatField(null=True)

    @classmethod
    def Create(cls, cmdargs, wd, env, docker=None):
        return Execution.create(
            docker=docker,
            cmdargs=json.dumps(cmdargs),
            wd=wd,
            env=json.dumps(env))

    def set_end(self, retcode):
        end = datetime.datetime.now()
        self.duration = (end - self.timestamp).total_seconds()
        self.ret = retcode


class ExecOutputLine(BaseModel):
    execution = ForeignKeyField(Execution, backref='output_line')
    is_out = BooleanField(default=True)
    idx = IntegerField(null=False)
    line = CharField(null=False)

    @classmethod
    def Create(cls, execution, is_out, idx, line):
        return OutputLine.create(execution=execution, is_out=is_out, idx=idx, line=line)


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
    db.create_tables([DockerExec, Report,  Execution, OutputLine])


if __name__ == '__main__':
    init()