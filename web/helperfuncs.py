import datetime
import json
from random import random
from traceback import print_exc

from flask import url_for, render_template

from model import get_scans, get_batchs


def enumwid(it):
    for el in iter(it):
        yield mkrand(), el


def short_date(d):
    if d is None:
        return '<not set>'
    try:
        return str(d).split('.')[0].split('-', 1)[1].rsplit(':', 1)[0]
    except:
        print_exc()
        print("source d: %r" % repr(d) )
        return str(d).split('.')[0]

def mkrand():
    return str(random()).split('.')[1]


def lines(x):
    if x is None: return 0
    return len(x.splitlines())


def render(template, **kwargs):
    class Funcs: pass
    funcs = Funcs()

    new = {'scans': get_scans(),
           'batchs': get_batchs(),
           'None': None,
           'short_repo':lambda x: '../'+x.rsplit('/', 1)[1].replace('.git', ''),
           'datetime': datetime.datetime,
           }
    for k, v in new.items():
        setattr(funcs, k, v)

    for f in [list, len, url_for, repr, type, json, enumwid, short_date, mkrand, lines]:
        new[f.__name__] = f
        setattr(funcs, f.__name__, f)
    new['funcs'] = funcs
    new.update(kwargs)
    return render_template(template, **new)


to_str = lambda x: str(x) if type(x) != type('') else x
