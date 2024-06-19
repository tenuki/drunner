import datetime
import json
import os
import time
from queue import Queue
import queue
import sys
import threading
from contextlib import contextmanager
from subprocess import Popen, PIPE

from model import Execution, OutputLine, db, ScannerExec


BSIZE = 100


def add_line(ex, is_out, idx, line):
    OutputLine.Create(ex, is_out, idx, line)


def db_save(q, debug=False):
    tot = 0
    done = False
    while not done:
        lines = []
        while not q.empty():
            new_lines = q.get()
            done = new_lines is None
            if done:
                break
            lines += new_lines
        if lines:
            with db.atomic():
                for idx in range(0, len(lines), BSIZE):
                    OutputLine.insert_many(lines[idx:idx + BSIZE]).execute()
                    tot += len(lines[idx:idx + BSIZE])
                    if debug:
                        for line in lines[idx:idx+BSIZE]:
                            print(f" -> {line} ")
    if debug:
        print(f"LINES->{tot}")


def savelines(ex, fd, isOut, q):
    idx = 0
    lines = []
    last = time.time()
    while True:
        line = fd.readline()
        if not line:
            # print(f"line recvd: {repr(line)}")
            break
        line = line.strip()
        # print(f"({idx}) `{line.decode('utf-8')}'")
        lines.append((ex, isOut, idx, line))
        idx += 1
        try:
            q.put_nowait(lines)
            lines = []
            last = time.time()
        except queue.Full:
            if time.time() - last > 0.3:
                q.put(lines)
                lines = []
                last = time.time()
    q.put(lines)


@contextmanager
def launch_thread(*args):
    thread = threading.Thread(target=savelines, args=args)
    thread.start()
    try:
        yield thread
    finally:
        thread.join()


def _exec(ex: Execution, cmdargs, wd='.', env=None, debug=True) -> Execution:
    ex.timestamp = datetime.datetime.now()
    if not (env is None):
        base = os.environ.copy()
        base.update(env)
        env = base
    p = Popen(cmdargs, cwd=wd, env=env, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
    (child_stdin, child_stdout, child_stderr) = (p.stdin, p.stdout, p.stderr)
    q = Queue()
    thread = threading.Thread(target=db_save, args=(q, debug))
    thread.start()
    try:
        with launch_thread(ex, child_stdout, True, q):
            with launch_thread(ex, child_stderr, False, q):
                p.wait()
    except Exception as e:
        print(f"Error while running: {e}", file=sys.stderr)
    finally:
        q.put(None)
        ex.set_end(p.returncode)
        try:
            ex.save()
        except Exception as err:
            print(f"Failed to save: {err}", file=sys.stderr)
        thread.join()
    return ex


# @dramatiq.actor
def exec(cmdargs=None, wd=None, env=None, de: ScannerExec=None, e:Execution=None) -> Execution:
    if e is None and cmdargs is None:
        raise Exception("Either cmdargs or cmdargs must not be None")
    if e is None:
        e = Execution.Create(cmdargs, wd, env, scan=de)
    else:
        e.wd = wd
        cmdargs = json.loads(e.cmdargs)
        e.save()
    e = _exec(e, cmdargs=cmdargs, wd=wd, env=env)
    e.save()
    return Execution.get_by_id(e.id)


def testme(argscmd):
    exec([argscmd])


if __name__ == '__main__':
    testme(' '.join(sys.argv[1:]))
