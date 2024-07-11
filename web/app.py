import json
import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from flask import Flask, request, url_for, redirect, Response

from model import BatchExec, ScannerExec, Execution, Report, get_scans
from helperfuncs import render, to_str

from drunner import generic_task_runner, execute_batch, ScannerRunner


app = Flask(__name__)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
redis_broker = RedisBroker(host=REDIS_HOST)
dramatiq.set_broker(redis_broker)


def get_app():
    return app


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
                  big_fields={
                      'output': '\r\n'.join(line.line
                                            for line in lines)})

@app.route('/batch/<id>/composite')
def batch_composite(id: int):  # put application's code here
    batch = BatchExec().get_by_id(id)
    full = []
    for scan, finding in batch.composite_report():
        full.append(','.join([
            finding['scanner'],
            scan.repo,
            scan.path,
            finding['name'],
            finding['level'],
            finding['filename']+":"+str(finding['lineno'])
        ]))
    return Response(
        '\r\n'.join(full),
        mimetype='text/plain',
        headers={'Content-disposition':
                     f'attachment; filename=batch-{batch.name}-{id}.csv'})


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


def split_ms(a_str:str):
    if a_str is None: return ''
    return a_str.split('.')[0] if '.' in a_str else a_str


@app.route('/scan/<scan_id>/rebuild')
def rebuild(scan_id: int):
    scan = ScannerRunner.FromId(scan_id)
    scan.rebuild()
    return redirect(url_for('scan_exec', id=scan_id))


@app.route('/scan-exec/<id>')
def scan_exec(id: int):  # put application's code here
    scanner, repo, path, commit, _id, timestamp = 'scanner', 'repo', 'path', 'commit', "id", 'timestamp'
    # STATICS = {_id, scanner}
    scan = ScannerExec().get_by_id(id)
    exec_fields = {}
    for k in [scanner, repo, path, commit, _id, timestamp]:
        field_value = to_str(getattr(scan, k))
        exec_fields[k] = (split_ms(field_value) if k==timestamp else field_value, # field_value
                          (k == scanner), # is static
                          'datetime-local' if k==timestamp else None, # special_field
                          )
    big_fields = {}
    for k in ['errors']:
        big_fields[k] = to_str(getattr(scan, k))

    reports = list(scan.reports)
    if len(reports)>=2:
        gen = [r for r in reports if not r.is_raw ][0]
        # print(gen)
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
        e = Execution.Create('custom-clone', ['git clone ' + request.form['site']],
                             env={'GIT_SSH_COMMAND': "ssh -oStrictHostKeyChecking=no "})
        generic_task_runner.send(e.id)
        return redirect(url_for('exec', eid=e.id), code=302)
    return render('add_site.html')


@app.route('/build/<scanner>', methods=['GET', 'POST'])
def build(scanner: str):
    if request.method == 'POST':
        e = ScannerRunner.Build(scanner)
        generic_task_runner.send(e.id)
        return redirect(url_for('exec', eid=e.id), code=302)
    return render('build_test.html', scanner=scanner, action='build')


@app.route('/update/<scanner>', methods=['GET', 'POST'])
def update(scanner: str):
    if request.method == 'POST':
        e = ScannerRunner.Update(scanner)
        generic_task_runner.send(e.id)
        return redirect(url_for('exec', eid=e.id), code=302)
    return render('build_test.html', scanner=scanner, action='update')


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


@app.route('/rebuild_reports', methods=('GET',))
def rebuild_reports():
    for scan in ScannerExec.select():
        scanner = ScannerRunner.FromId(scan.id)
        scanner.rebuild()
    return redirect('/')


# @dramatiq.actor
# def add_keys_for_site(e_id: int):
#     pass

# @dramatiq.actor(time_limit=1200000)
# def execute_batch(batch, tasks=()):
#     pass


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
    # testme() # app.run()
    app.run(host=os.environ.get('LISTEN_IP', '127.0.0.1'))
