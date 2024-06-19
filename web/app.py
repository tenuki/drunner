import json
import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from flask import Flask, request, url_for, redirect, Response

from model import BatchExec, ScannerExec, Execution, Report, get_scans
from helperfuncs import render, to_str


app = Flask(__name__)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
redis_broker = RedisBroker(host=REDIS_HOST)
dramatiq.set_broker(redis_broker)


@app.route('/')
def index():  # put application's code here
    return render("index.html")


@app.route('/exec/<eid>')
def exec(eid: int):  # put application's code here
    exec = Execution().get_by_id(eid)
    lines = [line for line in exec.output_line]
    lines.sort(key=lambda line: line.idx)
    return render("scan.html",
                  exec_fields={},
                  big_fields={'output': '\r\n'.join(line.line for line in lines)})

@app.route('/batch/<id>')
def batch(id: int):  # put application's code here
    batch = BatchExec().get_by_id(id)
    return render('batch.html', batch=batch)

@app.route('/report/<id>')
def report(id: int):  # put application's code here
    report = Report().get_by_id(id)
    return render('report.html', report=report)

@app.route('/report/<id>/download')
def report_download(id: int):  # put application's code here
    report = Report().get_by_id(id)
    return Response(
        report.content,
        mimetype='text/plain',
        headers={'Content-disposition': f'attachment; filename=report-{id}'})

@app.route('/report/<id>/name')
def report_name(id: int):  # put application's code here
    return f'report-{id}'

@app.route('/exec/<id>/output')
def get_exec_output(id: int):  # put application's code here
    exec = Execution().get_by_id(id)
    if not exec:
        return 'Not found', 404
    fname = exec.get_output_fname()
    return Response(
        exec.output,
        mimetype='text/plain',
        headers={'Content-disposition': f'attachment; filename={fname}'})


@app.route('/scan-exec/<id>')
def scan_exec(id: int):  # put application's code here
    scan = ScannerExec().get_by_id(id)
    exec_fields = {}
    for k in ["id",
                'timestamp',
                'repo',
                'commit',
                'path',
                'scanner']:
        exec_fields[k] = to_str(getattr(scan, k))

    big_fields = {}
    for k in ['errors']:
        big_fields[k] = to_str(getattr(scan, k))

    reports = list(scan.reports)
    if len(reports)>=2:
        gen = [r for r in reports if not r.is_raw ][0]
        print(gen)
        # big_fields['report'] = '\r\n'.join(str(finding) for finding in json.loads(gen.content))
        lines =  [str(finding) for finding in json.loads(gen.content)['findings'] ]
        big_fields['report'] = '\r\n'.join(lines)

        raw = [r for r in reports if r.is_raw][0]
        big_fields['raw'] = raw.content

    return render("scan.html",
                  scan=scan,
                  exec_fields=exec_fields,
                  big_fields=big_fields)


@app.route('/addsite/', methods=['GET', 'POST'])
def addsite():
    if request.method == 'POST':
        e = Execution.Create(['git clone ' + request.form['site']],
                             env={'GIT_SSH_COMMAND': "ssh -oStrictHostKeyChecking=no "})
        add_keys_for_site.send(e.id)
        return redirect(url_for('exec', eid=e.id), code=302)
    return render('add_site.html')


@app.route('/build/test', methods=['GET', 'POST'])
def buildtest():
    if request.method == 'POST':
        e = Execution.Create(['docker build -t drunner/testscan:latest .'])
        add_keys_for_site.send(e.id)
        return redirect(url_for('exec', eid=e.id), code=302)
    return render('build_test.html')


@app.route('/create/', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        b = BatchExec.create(name=request.form['batch'],
                             author=request.form['from'],
                             email=request.form['email'],
                             comments=request.form['comments'])
        des = []
        for line in request.form[('tasks')].splitlines():
            line = line.strip()
            if line=="": continue
            if (c:=line.count(","))<3:
                line += ","*(3-c)
            repo, commit, path, detector = [x.strip() for x in line.split(",")]
            if repo=="":
                continue
            if detector=="":
                detector = 'scout'
            if path=="":
                path = '.'
            if commit=="":
                commit = 'main'
            de = ScannerExec.create(batch=b, commit=commit, repo=repo, path=path, scanner=detector)
            des.append(de)
        execute_batch.send(b.id, [de.id for de in des])
    return render('create.html')


@app.route('/api/scans/all', methods=('GET',))
def scans():
    return get_scans()


@dramatiq.actor
def add_keys_for_site(e_id: int):
    pass

@dramatiq.actor(time_limit=1200000)
def execute_batch(batch, tasks=()):
    pass


def testme():
    b = BatchExec.create(name="pruebaX",
                         author="dave",
                         email="dave@example.com",
                         comments="no comments yet")
    line = 'git@github.com:tenuki/no-code.git,main,.,test'
    line = 'git@github.com:CoinFabrik/scout-soroban-examples.git,main,vesting/,scout'
    repo, commit, path, detector = line.split(",")
    de = ScannerExec.create(batch=b, commit=commit, repo=repo, path=path, scanner=detector)
    des=[de]
    # de.save()
    execute_batch.send(b.id, [de.id for de in des])



if __name__ == '__main__':
    # testme() # app.run()P3U
    app.run()
