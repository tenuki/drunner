import datetime
import time
from queue import Queue
import queue
import sys
import threading
from contextlib import contextmanager
from subprocess import Popen, PIPE

from model import Execution, OutputLine, db, DockerExec


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


def _exec(ex: Execution, cmdargs, wd='.', env=None, debug=True):
    ex.timestamp = datetime.datetime.now()
    p = Popen(cmdargs, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
    (child_stdin, child_stdout, child_stderr) = (p.stdin, p.stdout, p.stderr)
    q = Queue()
    thread = threading.Thread(target=db_save, args=(q, debug))
    thread.start()
    try:
        with launch_thread(ex, child_stdout, True, q):
            with launch_thread(ex, child_stderr, False, q):
                p.wait()
                ex.set_end(p.returncode)
    except Exception as e:
        print(f"Error while running: {e}", file=sys.stderr)
    finally:
        q.put(None)
        try:
            ex.save()
        except Exception as err:
            print(f"Failed to save: {err}", file=sys.stderr)
        thread.join()
        return p.returncode


# @dramatiq.actor
def exec(cmdargs, wd='.', env=None, de: DockerExec=None):
    e = Execution.Create(cmdargs, wd, env, docker=de)
    ret = _exec(e, cmdargs=cmdargs, wd=wd, env=env)
    e.save()
    return ret


def testme(argscmd):
    exec([argscmd])


if __name__ == '__main__':
    testme(' '.join(sys.argv[1:]))
