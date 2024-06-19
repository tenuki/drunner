import json
import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from flask import Flask, render_template, request, url_for, redirect

from model import BatchExec, ScannerExec, Execution, Report

app = Flask(__name__)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
redis_broker = RedisBroker(host=REDIS_HOST)
dramatiq.set_broker(redis_broker)


def render(template, **kwargs):
    new = {'scans': get_scans(),
           'lines': lambda x: len(x.splitlines()),
           'batchs': get_batchs(),
           'None': None,
           'short_repo':lambda x: '../'+x.rsplit('/', 1)[1].replace('.git', ''),
           'short_date':lambda d: str(d).split('.')[0].split('-', 1)[1].rsplit(':', 1)[0],
           }
    for f in [list, len, url_for, repr, type, json]:
        new[f.__name__] = f
    # print ("---> ", list(new.keys()))
    new.update(kwargs)
    return render_template(template, **new)


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

@app.route('/scan-exec/<id>')
def scan_exec(id: int):  # put application's code here
    scan = ScannerExec().get_by_id(id)
    exec_fields = {}
    to_str = lambda x: str(x) if type(x)!=type('') else x
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


def get_scans():
    return [x.as_dict() for x in ScannerExec.select()
                .where(ScannerExec.batch != None)
                .order_by(ScannerExec.timestamp.desc())]


def get_batchs():
    return [x for x in
            BatchExec.select().order_by(BatchExec.timestamp.desc())]


@dramatiq.actor
def add_keys_for_site(e_id: int):
    pass

@dramatiq.actor(time_limit=1200000)
def execute_batch(batch, tasks=()):
    print("*****************EXECUTE BATCH ************************")
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
