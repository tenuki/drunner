from model import BatchExec, ScannerExec, Execution


def list():
    for b in BatchExec.select():
        print(repr(b))
    for scanner in ScannerExec.select():
        print(repr(scanner))
    for exe in Execution.select():
        print(repr(exe))

if __name__ == '__main__':
    list()